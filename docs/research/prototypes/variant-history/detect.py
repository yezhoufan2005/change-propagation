"""Would a signature from the first fix have found the sites a later commit patched the same way?

usage: python3 -I detect.py <repo> <go|web> <hunks.json> <multi.json> <out.json>
"""
import json, re, subprocess, sys, time, collections
sys.path.insert(0, '/tmp/va-scripts')
from vtok import tokens, abs2, abs3, trivial_line, norm0, delta_window

repo, lang, hf, mf, outf = sys.argv[1:6]
D = json.load(open(hf)); C = D['commits']
M = json.load(open(mf))
FIX = re.compile(r'\bfix|bug|修复|修正|解决|问题|错误|hotfix', re.I)
if lang == 'go':
    keep = lambda p: p.endswith('.go') and not p.endswith('_test.go') and not p.endswith('.pb.go') and \
        not p.startswith(('vendor/', 'docs/', 'internal/query/', 'internal/model/', 'third_party/'))
else:
    keep = lambda p: p.endswith(('.vue', '.ts', '.js', '.tsx')) and not p.endswith(('.d.ts', '.min.js')) and \
        not re.search(r'node_modules/|dist/|locales/|i18n/|^public/|mock', p)


def git(*a, inp=None):
    return subprocess.run(['git', '-C', repo] + list(a), input=inp, capture_output=True).stdout


def read_blobs(rev, paths):
    req = ''.join(f'{rev}:{p}\n' for p in paths).encode()
    raw = git('cat-file', '--batch', inp=req)
    out, i = {}, 0
    for p in paths:
        j = raw.index(b'\n', i)
        hdr = raw[i:j].split()
        if len(hdr) < 3 or hdr[1] == b'missing':
            i = j + 1; continue
        n = int(hdr[2]); out[p] = raw[j + 1:j + 1 + n].decode('utf-8', 'replace'); i = j + 1 + n + 1
    return out


def prep(text):
    rows = []
    for no, line in enumerate(text.split('\n'), 1):
        if trivial_line(line):
            continue
        t = tokens(line)
        rows.append((no, norm0(line), ' '.join(abs2(t)), ' '.join(abs3(t))))
    return rows


LV = {'L0': 1, 'L1': 2, 'L2': 3}


def keyseq(lines, lv):
    out = []
    for l in lines:
        if trivial_line(l):
            continue
        t = tokens(l)
        out.append({1: norm0(l), 2: ' '.join(abs2(t)), 3: ' '.join(abs3(t))}[lv])
    return out


def find(rows, seq, lv):
    n = len(seq); hits = []
    if n == 0:
        return hits
    col = [r[lv] for r in rows]
    for i in range(len(rows) - n + 1):
        if col[i] == seq[0] and col[i:i + n] == seq:
            hits.append(i)
    return hits


def context_before(text, lineno, k=2):
    ls = text.split('\n'); out = []
    i = min(lineno, len(ls)) - 1
    while i >= 0 and len(out) < k:
        if not trivial_line(ls[i]):
            out.insert(0, ls[i])
        i -= 1
    return out


tree_cache = {}


def tree(rev):
    if rev not in tree_cache:
        names = [p for p in git('ls-tree', '-r', '--name-only', rev).decode('utf-8', 'replace').split('\n') if p and keep(p)]
        blobs = read_blobs(rev, names)
        tree_cache.clear()
        tree_cache[rev] = {p: (blobs[p], prep(blobs[p])) for p in blobs}
    return tree_cache[rev]


results = []
sel = [g for g in M if FIX.search(C[g['c1']]['subj'])]
sel.sort(key=lambda g: g['c1'])
for g in sel:
    c1 = C[g['c1']]; F = g['first'][0]
    t0 = time.time()
    T = tree(c1['sha'])
    load = time.time() - t0
    # seed signature
    if F['kind'] == 'mod':
        sig_lines = F['rem']; patch_lines = F['add']
    else:
        par = read_blobs(c1['sha'] + '^', [F['f']]).get(F['f'], '')
        sig_lines = context_before(par, F['os']); patch_lines = F['add']
    patch1 = keyseq(patch_lines, 2)
    t1 = time.time()
    cands = {}
    for lvn, lv in LV.items():
        seq = keyseq(sig_lines, lv); cs = []
        for p, (txt, rows) in T.items():
            for i in find(rows, seq, lv):
                if F['kind'] == 'add':  # exclude windows already followed by the patch lines
                    nxt = [r[2] for r in rows[i + len(seq):i + len(seq) + len(patch1)]]
                    if patch1 and nxt == patch1:
                        continue
                cs.append((p, rows[i][0]))
        cands[lvn] = cs
    scan = time.time() - t1
    # ground truth sites for later hunks, located in the C1 tree
    sites = []
    for L in g['later']:
        c2 = C[L['c']]
        if L['kind'] == 'mod':
            fp = L['rem']
        else:
            par2 = read_blobs(c2['sha'] + '^', [L['f']]).get(L['f'], '')
            fp = context_before(par2, L['os'])
        seq0 = keyseq(fp, 1)
        loc = None
        if L['f'] in T and seq0:
            hits = find(T[L['f']][1], seq0, 1)
            if hits:
                loc = [(L['f'], T[L['f']][1][h][0]) for h in hits]
        sites.append({'f': L['f'], 'sha': c2['sha'][:8], 'kind': L['kind'], 'existed_at_c1': loc is not None, 'loc': loc})
    found = {}
    for lvn, cs in cands.items():
        cset = set(cs)
        found[lvn] = [bool(s['loc']) and any(x in cset for x in s['loc']) for s in sites]
    confirmed = {}
    allloc = set(x for s in sites if s['loc'] for x in s['loc'])
    for lvn, cs in cands.items():
        confirmed[lvn] = sum(1 for x in set(cs) if x in allloc)
    results.append({'c1': c1['sha'][:8], 'subj': c1['subj'][:80], 'kind': F['kind'], 'k': g['k'][:160],
                    'seed_file': F['f'], 'sig_lines': len(keyseq(sig_lines, 1)), 'files_in_tree': len(T),
                    'load_s': round(load, 3), 'scan_s': round(scan, 3),
                    'n_cand': {k: len(set(v)) for k, v in cands.items()}, 'confirmed': confirmed,
                    'sites': sites, 'found': found})
json.dump(results, open(outf, 'w'), ensure_ascii=False, indent=0)
print('groups', len(results))
