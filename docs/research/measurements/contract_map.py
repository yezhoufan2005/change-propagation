#!/usr/bin/env python3
"""Tier-0 contract anchors between a Go backend and a Vue/TS frontend (regex only, stdlib only).

1. json:"..." struct tags in Go + case variants (snake, camel, Pascal, kebab, SCREAMING, and the
   Go-initialism forms pascal_go/camel_go); frontend references counted under the exact name and
   under any variant (whole-token matches).
2. MQTT topic-like literals + Subscribe/Publish call sites (Go code, frontend code, backend YAML
   config), grouped by normalized topic: + # %s {x} :x ${x} and a trailing '/' become '*'.
3. WebSocket endpoints and message keys/frames on both sides.

Usage:
  python3 -I contract_map.py --backend DIR [--backend DIR] --frontend DIR [--frontend DIR]
                             --out-dir DIR [--slice NAME ...]
Writes contract_map.json (details) and contract_summary.txt (one line per item) to --out-dir.
"""
import argparse
import collections
import difflib
import json
import math
import os
import re
import time

SKIP_DIRS = {'.git', 'node_modules', 'vendor', 'dist'}
FE_EXT = {'.vue', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
YAML_EXT = {'.yml', '.yaml'}
# golint's common initialisms, lower-cased
INITIALISMS = set('acl api ascii cpu css dns eof guid html http https id ip json lhs qps ram rhs rpc '
                  'sla smtp sql ssh tcp tls ttl udp ui uid uuid uri url utf8 vm xml xmpp xsrf xss'.split())


def walk(roots, exts):
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and not d.startswith('.'))
            for fn in sorted(fns):
                if os.path.splitext(fn)[1].lower() in exts:
                    p = os.path.join(dp, fn)
                    yield os.path.basename(root.rstrip('/')) + '/' + os.path.relpath(p, root), p


def read(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def line_of(text, pos):
    return text.count('\n', 0, pos) + 1


# ---------------------------------------------------------------- case variants
WORD_RE = re.compile(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+')


def split_words(name):
    out = []
    for part in re.split(r'[^A-Za-z0-9]+', name):
        for w in WORD_RE.findall(part):
            if w.isdigit() and out:
                out[-1] += w          # keep digits on the previous word: device_id2 -> id2
            else:
                out.append(w.lower())
    return out


def variants(name):
    w = split_words(name)
    if not w:
        return {}
    cap = [x.capitalize() for x in w]
    goc = [x.upper() if x in INITIALISMS else x.capitalize() for x in w]
    return {'snake': '_'.join(w), 'camel': w[0] + ''.join(cap[1:]), 'pascal': ''.join(cap),
            'kebab': '-'.join(w), 'screaming': '_'.join(w).upper(),
            'pascal_go': ''.join(goc), 'camel_go': w[0] + ''.join(goc[1:])}


# ---------------------------------------------------------------- 1. json tags
TAG_RE = re.compile(r'json:"([^",]*)')
FIELD_RE = re.compile(r'^\s*([A-Za-z_]\w*)\s+[^`\n]*`[^`\n]*json:"')
IDENT_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
KEBAB_RE = re.compile(r'[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+')
WORDLIKE = re.compile(r'^(?:[A-Za-z_][A-Za-z0-9_]*|[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+)$')


def extract_tags(go_texts):
    tags = {}
    for rel, text in go_texts:
        if 'json:"' not in text:
            continue
        is_test = rel.endswith('_test.go')
        is_gen = 'Code generated' in text[:600]
        for lineno, line in enumerate(text.split('\n'), 1):
            if 'json:"' not in line:
                continue
            fm = FIELD_RE.match(line)
            for m in TAG_RE.finditer(line):
                name = m.group(1).strip()
                if not name or name == '-':
                    continue
                t = tags.setdefault(name, {'defs': 0, 'files': set(), 'first': f'{rel}:{lineno}',
                                           'fields': collections.Counter(), 'nontest': False,
                                           'nongen': False})
                t['defs'] += 1
                t['files'].add(rel)
                t['nontest'] |= not is_test
                t['nongen'] |= not is_gen
                if fm:
                    t['fields'][fm.group(1)] += 1
    return tags


def count_fe_tokens(fe_texts, odd_names):
    """Whole-token counts (occurrences, files) for identifiers and kebab words in frontend code."""
    occ, nfiles = collections.Counter(), collections.Counter()
    odd = collections.Counter()
    for _rel, text in fe_texts:
        toks = IDENT_RE.findall(text) + KEBAB_RE.findall(text)
        occ.update(toks)
        nfiles.update(set(toks))
        for n in odd_names:   # tag names that are not plain words ($schema, a.b, ...)
            c = text.count(n)
            if c:
                odd[n] += c
    return occ, nfiles, odd


def classify_tags(tags, occ, nfiles, odd):
    stats = collections.Counter()
    via = collections.Counter()
    for name, t in tags.items():
        v = variants(name)
        t['words'] = len(split_words(name))
        exact = odd[name] if not WORDLIKE.match(name) else occ[name]
        t['fe_exact'], t['fe_exact_files'] = exact, (nfiles[name] if WORDLIKE.match(name) else 0)
        hits = {}
        for kind, tok in v.items():
            if tok != name and occ[tok]:
                hits.setdefault(tok, {'kinds': [], 'occ': occ[tok], 'files': nfiles[tok]})['kinds'].append(kind)
        t['fe_variants'] = hits
        cls = 'exact' if exact else ('variant_only' if hits else 'none')
        t['class'] = cls
        multi = 'multi' if t['words'] >= 2 else 'single'
        stats[(cls, multi)] += 1
        if cls == 'variant_only':
            for tok, h in hits.items():
                for k in h['kinds']:
                    via[k] += 1
    return stats, via


def locate_tokens(fe_texts, wanted, per_token=3):
    """First file:line:snippet locations of each wanted token (whole-token) in frontend code."""
    found = collections.defaultdict(list)
    if not wanted:
        return found
    rx = re.compile(r'(?<![A-Za-z0-9_\-])(' + '|'.join(sorted(map(re.escape, wanted), key=len, reverse=True))
                    + r')(?![A-Za-z0-9_\-])')
    for rel, text in fe_texts:
        for m in rx.finditer(text):
            tok = m.group(1)
            if len(found[tok]) < per_token:
                ls = text.rfind('\n', 0, m.start()) + 1
                le = text.find('\n', m.end())
                snippet = text[ls:le if le >= 0 else None].strip()[:120]
                found[tok].append(f'{rel}:{line_of(text, m.start())}: {snippet}')
    return found


# ---------------------------------------------------------------- 2. MQTT topics
STR_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`([^`\n]*)`')
TOPIC_SHAPE = re.compile(r'^[A-Za-z0-9_+#%{}:$.\-]+(?:/[A-Za-z0-9_+#%{}:$.\-]*)+$')
TOPIC_KW = re.compile(r'topic|subscribe|publish|mqtt', re.I)
NOT_TOPIC_LINE = re.compile(r'\.(GET|POST|PUT|DELETE|PATCH|Group|Any|Handle|HandleFunc|Static)\(|@Router'
                            r'|https?://|\brequest\.|axios|fetch\(|^\s*import\b|require\(|\bfrom\s+[\'"]')
MIME = re.compile(r'^(application|text|image|audio|video|multipart|font)/')
FILE_END = re.compile(r'\.(go|json|ya?ml|vue|tsx?|jsx?|png|jpe?g|svg|gif|md|html?|s?css|sql|so|exe|sh|txt|ico'
                      r'|woff2?|ttf|proto|mod|sum|py|log|pem|key|crt|csv|xlsx?|zip|tar|gz)$', re.I)
YAML_TOPIC = re.compile(r'^\s*([\w.\-]*topic[\w.\-]*)\s*:\s*[\'"]?([^\s\'"]+)[\'"]?\s*(?:\s#.*)?$', re.I)
WILD_SEG = re.compile(r'^(?:\+|#|%[a-zA-Z]|\{[^}]*\}|:\w+|\$\{[^}]*\})$')
INLINE_PH = re.compile(r'%[a-zA-Z]|\{[^}]*\}|\$\{[^}]*\}')
TEST_PATH = re.compile(r'_test\.go$|/(?:test|tests|__tests__|testdata|e2e)/|\.(?:test|spec)\.[jt]sx?$')


def is_test(rel):
    return bool(TEST_PATH.search(rel))


def topic_ok(s):
    if not (3 <= len(s) <= 200) or s[0] in '/.' or '//' in s or '..' in s:
        return False
    if not TOPIC_SHAPE.match(s) or MIME.match(s) or FILE_END.search(s):
        return False
    return bool(re.match(r'[A-Za-z+#$%{]', s))


def norm_topic(s):
    segs = s.split('/')
    out = ['*' if WILD_SEG.match(g) else INLINE_PH.sub('*', g) for g in segs]
    if out and out[-1] == '':
        out[-1] = '*'          # prefix that gets an id appended at runtime
    return '/'.join(out)


def string_literals(line):
    for m in STR_RE.finditer(line):
        yield next(g for g in m.groups() if g is not None)


MQTT_CALL = re.compile(r'\.(Subscribe|SubscribeMultiple|Publish|Unsubscribe)\(\s*([^,)]*)')
GO_IMPORT_MQTT = re.compile(r'"[^"\n]*(paho\.mqtt|mochi-mqtt|gmqtt|mqtt\.golang)[^"\n]*"')
FE_IMPORT_MQTT = re.compile(r'''from\s+['"]mqtt['"]|require\(\s*['"]mqtt['"]\s*\)''')


def extract_topics(go_texts, fe_texts, yaml_texts):
    """Pass 1: literals on lines whose code (string literals removed) mentions topic/subscribe/
    publish/mqtt, plus YAML values of *topic* keys; their first segments become topic roots (learned
    from non-test files only). Pass 2: other topic-shaped literals whose first segment is a root."""
    occ = []      # (side, rel, line, raw, kind, is_test)
    roots = collections.Counter()
    pending = []
    for side, texts in (('go', go_texts), ('fe', fe_texts)):
        for rel, text in texts:
            test, in_imp = is_test(rel), False
            for lineno, line in enumerate(text.split('\n'), 1):
                if side == 'go' and (in_imp or line.startswith('import')):   # skip Go import paths
                    in_imp = (not line.startswith(')')) if in_imp else line.rstrip().endswith('(')
                    continue
                if '/' not in line or NOT_TOPIC_LINE.search(line):
                    continue
                lits = [s for s in string_literals(line) if topic_ok(s)]
                if not lits:
                    continue
                if TOPIC_KW.search(STR_RE.sub('""', line)):
                    for s in lits:
                        occ.append((side, rel, lineno, s, 'kw-line', test))
                        if not test:
                            roots[s.split('/')[0]] += 1
                else:
                    pending.append((side, rel, lineno, lits, test))
    for rel, text in yaml_texts:
        for lineno, line in enumerate(text.split('\n'), 1):
            m = YAML_TOPIC.match(line)
            if m and topic_ok(m.group(2)):
                occ.append(('cfg', rel, lineno, m.group(2), 'yaml:' + m.group(1), is_test(rel)))
                roots[m.group(2).split('/')[0]] += 1
    roots = {r for r in roots if re.match(r'^[A-Za-z][\w\-]*$', r)}
    for side, rel, lineno, lits, test in pending:
        for s in lits:
            if s.split('/')[0] in roots:
                occ.append((side, rel, lineno, s, 'root', test))
    return occ, sorted(roots)



def extract_mqtt_calls(go_texts, fe_texts):
    calls = []
    for side, texts in (('go', go_texts), ('fe', fe_texts)):
        imp = GO_IMPORT_MQTT if side == 'go' else FE_IMPORT_MQTT
        for rel, text in texts:
            if not imp.search(text):
                continue
            lines = text.split('\n')
            for i, line in enumerate(lines):
                m = MQTT_CALL.search(line)
                if not m or line.lstrip().startswith('func ') or re.match(r'\s*//', line):
                    continue
                arg = m.group(2).strip()
                if arg.startswith(('ctx', 'context.')):
                    continue                      # redis / domain methods take a context first
                lits = [s for s in string_literals(arg + line[m.end():]) if topic_ok(s)][:1]
                expr = arg
                if not lits and re.match(r'^[A-Za-z_]\w*$', arg):
                    for j in range(i - 1, max(-1, i - 26), -1):
                        am = re.match(r'\s*' + re.escape(arg) + r'\s*:?=\s*(.+)$', lines[j])
                        if am:
                            expr = am.group(1).strip()[:100]
                            lits = [s for s in string_literals(expr) if topic_ok(s)][:1]
                            break
                calls.append({'side': side, 'loc': f'{rel}:{i + 1}', 'op': m.group(1), 'arg': arg[:60],
                              'expr': expr, 'topic': norm_topic(lits[0]) if lits else None,
                              'test': is_test(rel)})
    return calls


# ---------------------------------------------------------------- 3. WebSocket
def match_brace(text, i):
    """text[i] == '{'; return the index after its matching '}' (skips strings, runes, comments)."""
    depth, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        elif c in '"\'`':
            j = i + 1
            if c == '`':
                j = text.find('`', j)
                j = n if j < 0 else j
            else:
                while j < n and text[j] not in (c, '\n'):
                    j += 2 if text[j] == '\\' else 1
            i = j
        elif text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 1
        i += 1
    return n


GO_FUNC = re.compile(r'^func\s*(?:\([^)]*\)\s*)?([A-Za-z_]\w*)', re.M)


def go_funcs(text):
    """Yield (name, start, end) of top-level Go functions; body found by brace matching."""
    for m in GO_FUNC.finditer(text):
        i, depth = m.end(), 0
        while i < len(text):
            c = text[i]
            if c in '([':
                depth += 1
            elif c in ')]':
                depth -= 1
            elif c == '{' and depth == 0:
                if text[max(0, i - 12):i].rstrip().endswith(('interface', 'struct')):
                    i = match_brace(text, i)
                    continue
                yield m.group(1), m.start(), match_brace(text, i)
                break
            i += 1


GO_ROUTE = re.compile(r'\.(GET|Any|Handle|HandleFunc)\(\s*"([^"]*)"\s*,\s*([\w.]+)')
MAP_KEY = re.compile(r'\b(\w+)\["([A-Za-z_]\w*)"\]')
FRAME = re.compile(r'"(ping|pong|heartbeat)"|\'(ping|pong|heartbeat)\'')
FE_WS_PATH = re.compile(r'(/(?:[A-Za-z0-9_\-]+/)*ws(?:/[A-Za-z0-9_\-]+)*)(?=[\'"`?])')
FE_WS_NEW = re.compile(r'new\s+WebSocket\s*\(|useWebSocket\s*\(')
SEND_OBJ = re.compile(r'send\(\s*JSON\.stringify\(\s*\{')
SEND_ID = re.compile(r'send\(\s*JSON\.stringify\(\s*([A-Za-z_$][\w$]*)\s*\)')


def ws_norm(p):
    return re.sub(r'^api/v\d+/', '', p.strip('/'))


def obj_keys(text, brace):
    """Top-level keys of the object literal starting at text[brace] == '{'."""
    inner = text[brace + 1:match_brace(text, brace) - 1]
    keys, depth, cur = [], 0, []
    for ch in inner + ',':
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if ch == ',' and depth == 0:
            part = ''.join(cur).strip()
            m = re.match(r'''^['"]?([A-Za-z_$][\w$]*)['"]?\s*(?::|$)''', part)
            if m and not part.startswith('...'):
                keys.append(m.group(1))
            cur = []
        else:
            cur.append(ch)
    return keys


def extract_ws(go_texts, fe_texts):
    eps = {}

    def ep(p):
        return eps.setdefault(p, {'go': [], 'fe': [], 'go_keys': set(), 'fe_keys': set(),
                                  'go_frames': set(), 'fe_frames': set()})
    by_dir = collections.defaultdict(list)
    for rel, text in go_texts:
        by_dir[os.path.dirname(rel)].append(text)
    helper_cache = {}

    def helper_keys(d, fname):   # one hop: map keys read by a same-package helper
        if (d, fname) not in helper_cache:
            keys = set()
            rx = re.compile(r'^func\s*(?:\([^)]*\)\s*)?' + re.escape(fname) + r'\b', re.M)
            for text in by_dir[d]:
                if rx.search(text):
                    for name, s, e in go_funcs(text):
                        if name == fname:
                            keys |= {k for _v, k in MAP_KEY.findall(text[s:e])}
            helper_cache[(d, fname)] = keys
        return helper_cache[(d, fname)]

    handlers = {}
    for rel, text in go_texts:
        if '.Upgrade(' not in text:
            continue
        for name, s, e in go_funcs(text):
            body = text[s:e]
            if '.Upgrade(' not in body:
                continue
            pairs = MAP_KEY.findall(body)
            keys, mapvars = {k for _v, k in pairs}, {v for v, _k in pairs}
            for hm in re.finditer(r'\b([A-Za-z_]\w*)\(([^()]*)\)', body):
                if {x.strip() for x in hm.group(2).split(',')} & mapvars:
                    keys |= helper_keys(os.path.dirname(rel), hm.group(1))
            frames = {a or b for a, b in FRAME.findall(body)}
            handlers[name] = (f'{rel}:{line_of(text, s)}', keys, frames)
    for rel, text in go_texts:
        for m in GO_ROUTE.finditer(text):
            path, handler = m.group(2), m.group(3).split('.')[-1]
            if not (re.search(r'(^|/)ws(/|$)', path) or handler in handlers):
                continue
            e, h = ep(ws_norm(path)), handlers.get(handler)
            e['go'].append(f'{rel}:{line_of(text, m.start())} {m.group(1)} {handler}'
                           + (f' @{strip(h[0])}' if h else ''))
            if h:
                e['go_keys'] |= h[1]
                e['go_frames'] |= h[2]
    for rel, text in fe_texts:
        paths = [(m.group(1), m.start()) for m in FE_WS_PATH.finditer(text)]
        if not paths:
            continue
        opens = bool(FE_WS_NEW.search(text))
        keys = set()
        for m in SEND_OBJ.finditer(text):
            keys |= set(obj_keys(text, m.end() - 1))
        for m in SEND_ID.finditer(text):
            last = None
            for last in re.finditer(r'\b' + re.escape(m.group(1)) + r'\s*(?::[^=\n;]+)?=\s*\{', text[:m.start()]):
                pass
            if last:
                keys |= set(obj_keys(text, last.end() - 1))
        frames = {a or b for a, b in FRAME.findall(text)}
        for p, pos in paths:
            e = ep(ws_norm(p))
            e['fe'].append(f'{rel}:{line_of(text, pos)}' + ('' if opens else ' (no WebSocket open in file)'))
            e['fe_keys'] |= keys
            e['fe_frames'] |= frames
    return eps, handlers


def near_miss(a, keys):
    """Closest other group that differs from `a` in exactly one non-wildcard segment (typo/drift)."""
    sa, best = a.split('/'), None
    for b in keys:
        sb = b.split('/')
        if b == a or len(sa) != len(sb):
            continue
        diff = [(x, y) for x, y in zip(sa, sb) if x != y]
        if len(diff) != 1 or '*' in diff[0]:
            continue
        r = difflib.SequenceMatcher(None, *diff[0]).ratio()
        if r >= 0.75 and (best is None or r > best[1]):
            best = (b, round(r, 2))
    return best


# ---------------------------------------------------------------- summary lines
def strip(loc):
    return loc.split('/', 1)[1] if '/' in loc else loc     # drop the repo directory


def locs(lst, k=2):
    lst = [strip(x) for x in lst]
    return ', '.join(lst[:k]) + (f' +{len(lst) - k}' if len(lst) > k else '')


def tag_line(name, t):
    s = f"tag {name} | go {t['defs']}x/{len(t['files'])}f"
    s += '' if t['nontest'] else ' test-only'
    s += '' if t['nongen'] else ' gen-only'
    if t['class'] == 'exact':
        s += f" | fe ={t['fe_exact']}x/{t['fe_exact_files']}f"
    else:
        s += ' | fe none' if t['class'] == 'none' else ' | fe =0'
    if t['fe_variants']:
        top = sorted(t['fe_variants'].items(), key=lambda kv: -kv[1]['occ'])[:3]
        s += ' | ~' + ', '.join(f"{tok} {h['occ']}x/{h['files']}f" for tok, h in top)
    return s


def topic_line(k, g):
    s = f'topic {k}' + (' test-only' if g['test_only'] else '')
    if 0 < g['n_test'] < g['n']:
        s += f" (tests {g['n_test']}/{g['n']})"
    for side in ('go', 'cfg', 'fe'):
        if g[side]:
            s += f' | {side} {len(g[side])}: {locs(g[side])}'
    if g['calls']:
        s += f" | calls {len(g['calls'])}: {locs(g['calls'])}"
    if g.get('prefix_of'):
        s += f" | prefix-of {', '.join(g['prefix_of'][:2])}" + (f" +{len(g['prefix_of']) - 2}" if len(g['prefix_of']) > 2 else '')
    if g.get('near'):
        s += f" | near {g['near'][0]} ({g['near'][1]})"
    return s


def ws_line(k, e):
    def side(name):
        if not e[name]:
            return f' | {name} none'
        s = f" | {name} {len(e[name])}: {locs(e[name], 1 if name == 'go' else 2)}"
        s += f" keys={','.join(sorted(e[name + '_keys'])) or '-'}"
        return s + (f" frames={','.join(sorted(e[name + '_frames']))}" if e[name + '_frames'] else '')
    s = f'ws {k}' + side('go') + side('fe')
    if e['go'] and e['fe']:
        fo, go = sorted(e['fe_keys'] - e['go_keys']), sorted(e['go_keys'] - e['fe_keys'])
        if fo or go:
            s += f" | key-diff fe-only={','.join(fo) or '-'} go-only={','.join(go) or '-'}"
    return s


def call_line(c):
    tgt = c['topic'] or ('<- ' + c['expr'] if c['expr'] != c['arg'] else '(unresolved)')
    return f"mqtt-call {c['op']} {c['side']} {strip(c['loc'])} arg={c['arg']} {tgt}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', action='append', required=True)
    ap.add_argument('--frontend', action='append', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--slice', action='append', default=[])
    ap.add_argument('--spot', type=int, default=12, help='variant-only tags sampled for spot checks')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    T, t0 = {}, time.perf_counter()
    go_texts = [(rel, read(p)) for rel, p in walk(a.backend, {'.go'})]
    yaml_texts = [(rel, read(p)) for rel, p in walk(a.backend, YAML_EXT)]
    fe_texts = [(rel, read(p)) for rel, p in walk(a.frontend, FE_EXT)]
    T['walk_read'] = time.perf_counter() - t0

    t = time.perf_counter()
    tags = extract_tags(go_texts)
    odd = [n for n in tags if not WORDLIKE.match(n)]
    occ, nfiles, oddc = count_fe_tokens(fe_texts, odd)
    stats, via = classify_tags(tags, occ, nfiles, oddc)
    import random
    vo = sorted(n for n, x in tags.items() if x['class'] == 'variant_only' and x['words'] >= 2)
    sample = random.Random(0).sample(vo, min(a.spot, len(vo)))
    where = locate_tokens(fe_texts, {tok for n in sample for tok in tags[n]['fe_variants']})
    T['tags'] = time.perf_counter() - t

    t = time.perf_counter()
    tocc, roots = extract_topics(go_texts, fe_texts, yaml_texts)
    calls = extract_mqtt_calls(go_texts, fe_texts)
    groups = {}

    def group(k):
        return groups.setdefault(k, {'go': [], 'cfg': [], 'fe': [], 'calls': [], 'raw': collections.Counter(),
                                     'n': 0, 'n_test': 0})
    for side, rel, line, raw, kind, test in tocc:
        g = group(norm_topic(raw))
        if f'{rel}:{line}' not in g[side][-1:]:
            g[side].append(f'{rel}:{line}')
        g['raw'][raw] += 1
        g['n'] += 1
        g['n_test'] += test
    for c in calls:
        if c['topic']:
            g = group(c['topic'])
            g['calls'].append(c['loc'])
            g['n'] += 1
            g['n_test'] += c['test']
    for g in groups.values():
        g['test_only'] = g['n_test'] == g['n']
        for s in ('go', 'cfg', 'fe', 'calls'):
            g[s].sort(key=lambda x: is_test(x.rsplit(':', 1)[0]))     # non-test locations first
    live = [k for k, g in groups.items() if not g['test_only']]
    for k in live:   # a prefix literal ('a/b/', id appended at runtime) covers longer groups under it
        if k.count('/') >= 2 and any(r.endswith('/') for r in groups[k]['raw']):
            ext = sorted(b for b in live if b != k and b.startswith(k[:-1]))
            if ext:
                groups[k]['prefix_of'] = ext
    for k in live:   # near-miss only among groups with non-test occurrences
        if sum(bool(groups[k][s]) for s in ('go', 'cfg', 'fe')) == 1 and 'prefix_of' not in groups[k]:
            groups[k]['near'] = near_miss(k, live)
    T['topics'] = time.perf_counter() - t

    t = time.perf_counter()
    eps, handlers = extract_ws(go_texts, fe_texts)
    T['ws'] = time.perf_counter() - t

    t = time.perf_counter()
    sections = {
        'tags': [tag_line(n, tags[n]) for n in sorted(tags)],
        'topics': [topic_line(k, groups[k]) for k in sorted(groups) if not groups[k]['test_only']],
        'topics_test_only': [topic_line(k, groups[k]) for k in sorted(groups) if groups[k]['test_only']],
        'mqtt_calls': [call_line(c) for c in calls],
        'ws': [ws_line(k, eps[k]) for k in sorted(eps)],
    }
    summary = '\n'.join(ln for sec in sections.values() for ln in sec) + '\n'
    with open(os.path.join(a.out_dir, 'contract_summary.txt'), 'w', encoding='utf-8') as f:
        f.write(summary)
    detail = {
        'tags': {n: {**{k: v for k, v in x.items() if k not in ('files', 'fields')}, 'files': len(x['files']),
                     'go_fields': x['fields'].most_common(3)} for n, x in tags.items()},
        'topic_roots': roots,
        'topics': {k: {**{s: g[s] for s in ('go', 'cfg', 'fe', 'calls')}, 'raw': dict(g['raw']),
                       'n': g['n'], 'n_test': g['n_test'], 'test_only': g['test_only'],
                       'prefix_of': g.get('prefix_of'), 'near': g.get('near')} for k, g in groups.items()},
        'mqtt_calls': calls,
        'ws': {k: {kk: sorted(v) if isinstance(v, set) else v for kk, v in e.items()} for k, e in eps.items()},
        'ws_handlers': {k: [v[0], sorted(v[1]), sorted(v[2])] for k, v in handlers.items()},
        'spot_sample': {n: {'variants': tags[n]['fe_variants'],
                            'where': {tok: where[tok] for tok in tags[n]['fe_variants']}} for n in sample},
    }
    with open(os.path.join(a.out_dir, 'contract_map.json'), 'w', encoding='utf-8') as f:
        json.dump(detail, f, ensure_ascii=False, indent=1)
    T['write'] = time.perf_counter() - t
    T['total'] = time.perf_counter() - t0
    report(a, go_texts, fe_texts, yaml_texts, tags, stats, via, groups, calls, eps, sections, summary, T, roots)


def report(a, go_texts, fe_texts, yaml_texts, tags, stats, via, groups, calls, eps, sections, summary, T, roots):
    p = print
    p(f"files: go={len(go_texts)} yaml={len(yaml_texts)} fe={len(fe_texts)}; chars go="
      f"{sum(len(x) for _, x in go_texts)} fe={sum(len(x) for _, x in fe_texts)}")
    n = len(tags)
    multi = sum(1 for x in tags.values() if x['words'] >= 2)
    p(f"json tags: distinct={n} (multi-word {multi}, single-word {n - multi}) occurrences="
      f"{sum(x['defs'] for x in tags.values())} test-only={sum(1 for x in tags.values() if not x['nontest'])}"
      f" gen-only={sum(1 for x in tags.values() if not x['nongen'])}")
    for scope in ('all', 'multi', 'single'):
        row = {c: sum(v for (cc, m), v in stats.items() if cc == c and scope in ('all', m))
               for c in ('exact', 'variant_only', 'none')}
        tot = sum(row.values()) or 1
        p(f"  {scope:6s} " + '  '.join(f"{c}={row[c]} ({100 * row[c] / tot:.1f}%)" for c in row))
    p(f"  variant-only tags matched via: {dict(via)}")
    live = {k: g for k, g in groups.items() if not g['test_only']}
    side_of = lambda g: '+'.join(s for s in ('go', 'cfg', 'fe') if g[s]) or 'calls-only'
    p(f"topics: groups={len(groups)} (test-only {len(groups) - len(live)}) literal occurrences="
      f"{sum(len(g['go']) + len(g['cfg']) + len(g['fe']) for g in groups.values())}"
      f" (in test files {sum(g['n_test'] for g in groups.values())}); roots learned={len(roots)}: {roots}")
    p(f"  non-test groups by side={dict(collections.Counter(side_of(g) for g in live.values()))}")
    p(f"  test-only groups by side={dict(collections.Counter(side_of(g) for k, g in groups.items() if k not in live))}")
    p(f"  mqtt call sites={len(calls)} (in test files {sum(1 for c in calls if c['test'])})"
      f" resolved-to-topic={sum(1 for c in calls if c['topic'])}"
      f" near-miss among non-test groups={sum(1 for g in live.values() if g.get('near'))}"
      f" prefix-linked={sum(1 for g in live.values() if g.get('prefix_of'))}")
    for k, g in sorted(live.items()):
        if g.get('prefix_of'):
            p(f"    prefix {k} [{side_of(g)}] -> {g['prefix_of']}")
    for k, g in sorted(live.items()):
        if g.get('near'):
            p(f"    near-miss {k} [{side_of(g)} {g['n']}x] ~ {g['near'][0]} ({g['near'][1]})")
    p(f"ws endpoints={len(eps)} with go+fe={sum(1 for e in eps.values() if e['go'] and e['fe'])}")
    for k, sec in sections.items():
        ch = sum(len(x) + 1 for x in sec)
        p(f"summary[{k}]: {len(sec)} lines, {ch} chars, ~{ch // 4} tokens")
    p(f"summary total: {summary.count(chr(10))} lines, {len(summary)} chars, ~{len(summary) // 4} tokens")
    core = sum(len(x) + 1 for k, sec in sections.items() if k != 'topics_test_only' for x in sec)
    p(f"summary without test-only topics: {core} chars, ~{core // 4} tokens")
    p('timings_s: ' + ', '.join(f'{k}={v:.3f}' for k, v in T.items()))
    for term in a.slice:
        if '/' in term:
            hit = lambda ln, term=term: term in ln
        else:
            vs = set(variants(term).values()) | {term}
            rx = re.compile(r'(?<![\w-])(' + '|'.join(map(re.escape, vs)) + r')(?![\w-])')
            hit = lambda ln, rx=rx: bool(rx.search(ln))
        lines = [ln for sec in sections.values() for ln in sec if hit(ln)]
        text = '\n'.join(lines)
        p(f"\n--slice {term}: {len(lines)} lines, {len(text)} chars, ~{len(text) // 4} tokens")
        for ln in lines[:40]:
            p('  ' + ln[:300])


if __name__ == '__main__':
    main()
