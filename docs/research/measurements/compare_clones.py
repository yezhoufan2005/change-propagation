#!/usr/bin/env python3
"""Check which near-duplicate function pairs from shingle_index.py are also reported by jscpd.

Usage: python3 -I compare_clones.py [PAIRS_JSON [QUERY_JSON [EXTERNAL_DIR]]]
  PAIRS_JSON    shingle_index.py pairs output (default /tmp/cpf-measure/out/pairs_base.json)
  QUERY_JSON    shingle_index.py query output, a fallback source for the named pairs
                (default /tmp/cpf-measure/out/shingle_query_run1.json)
  EXTERNAL_DIR  run_external_tools.sh output (default /tmp/cpf-measure/external); the jscpd reports of
                run_external_followup.sh under EXTERNAL_DIR/followup are compared too when present
A pair counts as found when one jscpd clone overlaps the line ranges of both functions, and as linked when
the two functions overlap clones that are joined through shared or overlapping fragments.
Prints one JSON line per jscpd report and writes them to EXTERNAL_DIR/compare_clones.json.
"""
import collections
import glob
import json
import os
import re
import sys

OUT = '/tmp/cpf-measure/out'
PAIRS = sys.argv[1] if len(sys.argv) > 1 else f'{OUT}/pairs_base.json'
QUERY = sys.argv[2] if len(sys.argv) > 2 else f'{OUT}/shingle_query_run1.json'
EXT = sys.argv[3] if len(sys.argv) > 3 else '/tmp/cpf-measure/external'
FE_SRC = '/tmp/cpf-measure/repos/thingspanel-frontend-community/src'
# shingle label prefix -> (path prefix that jscpd names lack, files jscpd scanned)
SIDES = {'fe': ('src/', re.compile(r'\.(?:ts|js|vue)$')), 'be': ('', re.compile(r'\.go$'))}
SCOPES = {'frontend': 'fe-fe', 'backend': 'be-be'}
LABEL = re.compile(r'^(fe|be)/(.*):(\d+)-(\d+) (\S+) ntok=\d+$')
# Frontend pairs judged by reading the code in 04-scale-measurements.md: (function, path part A, path part B, verdict)
NAMED = [('normalizeAlarmLevel', 'ThingsVisAppFrame.vue', 'ThingsVisWidget.vue', 'true copy'),
         ('actionValueChange', 'linkage-edit/', 'scene-edit/', 'true copy, drifted'),
         ('password', 'change-information copy.vue', 'change-information.vue', 'true copy'),
         ('handleCopy', 'secret-key-modal.vue', 'copy/index.vue', 'true copy, drifted'),
         ('viewerPlatformDevices', 'telemetry-chart.vue', 'device-details-app/', 'true copy, renamed variables'),
         ('connectDeviceStatusWs', 'ThingsVisViewer.vue', 'ThingsVisAppFrame.vue', 'same logic, Q3 top 1'),
         ('render', 'rule-engine/index.vue', 'custom-commands.vue', 'boilerplate'),
         ('createDefaultFormModel', 'rule-engine/', 'apply/service/', 'false positive')]


def parse(label):
    m = LABEL.match(label)
    if not m:
        return None
    side, path, start, end, name = m.groups()
    return {'label': label, 'side': side, 'path': path, 'start': int(start), 'end': int(end), 'name': name}


def reports():
    for side in SCOPES:
        path = os.path.join(EXT, f'jscpd-{side}', 'jscpd-report.json')
        if os.path.isfile(path):
            yield side, 'default', path
    for path in sorted(glob.glob(os.path.join(EXT, 'followup', 'jscpd-*', 'jscpd-report.json'))):
        side, mode = re.match(r'jscpd-(frontend|backend)-(.+)$', os.path.basename(os.path.dirname(path))).groups()
        yield side, 'followup/' + mode, path


def clones(path):
    dups = json.load(open(path, encoding='utf-8'))['duplicates']
    idx = collections.defaultdict(list)
    for d in dups:
        f, s = d['firstFile'], d['secondFile']
        idx[frozenset((f['name'], s['name']))].append(((f['name'], f['start'], f['end']), (s['name'], s['start'], s['end'])))
    return idx, dups


def coverage(fn, ranges):
    lines = set()
    for a, b in ranges:
        lines.update(range(max(a, fn['start']), min(b, fn['end']) + 1))
    return len(lines) / (fn['end'] - fn['start'] + 1)


def check(idx, p, q):
    """Smaller share of the two functions covered by clones that overlap both; None if jscpd skipped a file."""
    prefix, scanned = SIDES[p['side']]
    if not all(fn['path'].startswith(prefix) and scanned.search(fn['path']) for fn in (p, q)):
        return None
    names = (p['path'][len(prefix):], q['path'][len(prefix):])
    rp, rq = [], []
    for x, y in idx.get(frozenset(names), ()):
        for (n1, a1, b1), (n2, a2, b2) in ((x, y), (y, x)):
            if (n1, n2) == names and a1 <= p['end'] and b1 >= p['start'] and a2 <= q['end'] and b2 >= q['start']:
                rp.append((a1, b1))
                rq.append((a2, b2))
    return round(min(coverage(p, rp), coverage(q, rq)), 2) if rp else 0.0


def components(dups):
    """{file: [(start, end, root)]}: the fragments of one clone, and overlapping fragments of one file, share a root.
    jscpd links each copy to one earlier copy, so three copies can come back as two clones; this joins them."""
    frags = [(f['name'], f['start'], f['end']) for d in dups for f in (d['firstFile'], d['secondFile'])]
    parent = list(range(len(frags)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(0, len(frags), 2):
        parent[find(i)] = find(i + 1)
    by_file = collections.defaultdict(list)
    for i, (name, a, b) in enumerate(frags):
        by_file[name].append((a, b, i))
    for spans in by_file.values():
        spans.sort()
        rep, end = None, -1
        for a, b, i in spans:
            if rep is not None and a <= end:
                parent[find(i)] = find(rep)
                end = max(end, b)
            else:
                rep, end = i, b
    return {name: [(a, b, find(i)) for a, b, i in spans] for name, spans in by_file.items()}


def linked(comp, p, q):
    """True if some fragment overlapping p and some fragment overlapping q share a root."""
    prefix = SIDES[p['side']][0]
    roots = [{r for a, b, r in comp.get(fn['path'][len(prefix):], ()) if a <= fn['end'] and b >= fn['start']} for fn in (p, q)]
    return bool(roots[0] & roots[1])


def vue_lines_match(dups, limit=200):
    """[matches, checked]: .vue clones whose fragment's first line is on the reported start line of the file."""
    ok = n = 0
    for d in dups:
        f = d['firstFile']
        if n >= limit or not f['name'].endswith('.vue'):
            continue
        n += 1
        lines = open(os.path.join(FE_SRC, f['name']), encoding='utf-8', errors='replace').read().split('\n')
        first = next((x.strip() for x in d['fragment'].split('\n') if x.strip()), '')
        ok += f['start'] <= len(lines) and first[:40] in lines[f['start'] - 1]
    return [ok, n]


doc = json.load(open(PAIRS, encoding='utf-8'))
groups = {}
for mode, m in doc['modes'].items():
    for scope, s in m['scopes'].items():
        groups[scope, mode] = [(j, parse(a), parse(b)) for j, a, b in s['examples']]
        if len(s['examples']) < s['cross_file']:
            print(f'note: {scope} {mode}: {len(s["examples"])} of {s["cross_file"]} clean cross-file pairs listed')
key = lambda p, q: frozenset((p['label'], q['label']))
for scope in SCOPES.values():
    raw = {key(p, q) for _, p, q in groups[scope, 'raw']}
    groups[scope, 'norm-only'] = [g for g in groups[scope, 'norm'] if key(g[1], g[2]) not in raw]

cands = [(p, q) for g in groups.values() for _, p, q in g]
for qr in json.load(open(QUERY, encoding='utf-8'))['queries']:
    qf = parse(qr['query'])
    for res in qr['modes'].values():
        cands += [(qf, parse(t[2])) for t in res.get('top_jaccard', []) if qf and parse(t[2])]
named = []
for name, a, b, verdict in NAMED:
    hit = next(((p, q) for p, q in cands + [(q, p) for p, q in cands] if p['name'] == q['name'] == name
                and a in p['path'] and b in q['path'] and p['path'] != q['path']), None)
    if hit:
        named.append((name, verdict) + hit)
    else:
        print(f'note: named pair {name} not found in the shingle outputs')

rows = []
for side, mode, path in reports():
    idx, dups = clones(path)
    comp = components(dups)
    row = {'report': mode, 'side': side, 'clones': len(dups)}
    if side == 'frontend':
        row['vue_start_line_matches'] = vue_lines_match(dups)
    for gmode in ('raw', 'norm', 'norm-only'):
        pairs = groups[SCOPES[side], gmode]
        res = [check(idx, p, q) for _, p, q in pairs]
        scanned = [(r, p, q) for r, (_, p, q) in zip(res, pairs) if r is not None]
        row[gmode] = {'pairs': len(res), 'scanned': len(scanned), 'found': sum(r > 0 for r, _, _ in scanned),
                      'half_covered': sum(r >= 0.5 for r, _, _ in scanned),
                      'linked': sum(linked(comp, p, q) for _, p, q in scanned)}
        if gmode == 'raw':
            row['raw_unlinked_sample'] = [f'{j:.2f} {p["label"]} | {q["label"]}' for j, p, q in pairs
                                          if check(idx, p, q) is not None and not linked(comp, p, q)][:4]
    if side == 'frontend':
        row['named'] = {f'{name} ({verdict})': [check(idx, p, q), linked(comp, p, q)] for name, verdict, p, q in named}
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False))
with open(os.path.join(EXT, 'compare_clones.json'), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
