#!/usr/bin/env python3
"""neardup2 (stdlib only): k-gram inverted index prefilter -> difflib verify -> clone groups; or 1-vs-N query.
Usage: python3 -I neardup2.py ROOT [--threshold 0.8] [--min-tokens 50] [--k 5] [--prefilter 0.3] [--brute]
       python3 -I neardup2.py ROOT --query REL/FILE:LINE [--top 10]
"""
import sys, os, json, difflib, argparse, time, bisect
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neardup as nd

def load(root, k, min_tokens):
    frags = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in nd.SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1] not in nd.EXTS: continue
            p = os.path.join(d, f)
            src = open(p, encoding='utf-8', errors='replace').read(); toks = nd.tokenize(src)
            tl = [t[2] for t in toks]
            for name, s, e in nd.functions(p, src, toks):
                ft = toks[bisect.bisect_left(tl, s):bisect.bisect_right(tl, e)]
                if len(ft) < min_tokens: continue
                norm = nd.normalize(ft, 'blind')
                frags.append({'file': os.path.relpath(p, root), 'name': name, 'lines': [s, e],
                              'raw': [t[1] for t in ft], 'norm': norm, 'grams': {hash(g) for g in nd.kgrams(norm, k)}})
    return frags

def label(x, y, ratio):
    if x['raw'] == y['raw']: return 'type1'
    if x['norm'] == y['norm']: return 'type2'
    return 'near-miss %.2f' % ratio

def score(x, y):
    jac = len(x['grams'] & y['grams']) / max(1, len(x['grams'] | y['grams']))
    ratio = difflib.SequenceMatcher(None, x['norm'], y['norm'], autojunk=False).ratio()
    return jac, ratio

def tag(f): return '%s:%d-%d %s' % (f['file'], f['lines'][0], f['lines'][1], f['name'])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root'); ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--min-tokens', type=int, default=50); ap.add_argument('--threshold', type=float, default=0.8)
    ap.add_argument('--prefilter', type=float, default=0.3); ap.add_argument('--df-cap', type=float, default=0.05)
    ap.add_argument('--brute', action='store_true'); ap.add_argument('--query'); ap.add_argument('--top', type=int, default=10)
    a = ap.parse_args(); t0 = time.time()
    frags = load(a.root, a.k, a.min_tokens)
    if a.query:
        qf, ql = a.query.rsplit(':', 1); ql = int(ql)
        q = [f for f in frags if f['file'] == qf and f['lines'][0] <= ql <= f['lines'][1]]
        if not q: print(json.dumps({'error': 'no function >= min-tokens at ' + a.query})); return
        q = q[-1]; res = []
        for f in frags:
            if f is q: continue
            jac, ratio = score(q, f)
            res.append({'match': tag(f), 'kind': label(q, f, ratio), 'jaccard': round(jac, 2), 'seq_ratio': round(ratio, 2),
                        'above_threshold': max(jac, ratio) >= a.threshold})
        res.sort(key=lambda r: -max(r['jaccard'], r['seq_ratio']))
        print(json.dumps({'query': tag(q), 'fragments': len(frags), 'results': res[:a.top], 'secs': round(time.time() - t0, 2)}, indent=1)); return
    n = len(frags); cand = []
    if a.brute:
        cand = [(i, j) for i in range(n) for j in range(i + 1, n)]
    else:
        index = defaultdict(list)
        for i, f in enumerate(frags):
            for g in f['grams']: index[g].append(i)
        cap = max(2, int(a.df_cap * n)) if n > 40 else n
        for i, f in enumerate(frags):
            shared = defaultdict(int)
            for g in f['grams']:
                ids = index[g]
                if len(ids) > cap: continue
                for j in ids:
                    if j > i: shared[j] += 1
            for j, c in shared.items():
                if c / max(1, min(len(f['grams']), len(frags[j]['grams']))) >= a.prefilter: cand.append((i, j))
    parent = list(range(n))
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    pairs = []
    for i, j in cand:
        x, y = frags[i], frags[j]
        if x['file'] == y['file'] and x['lines'] == y['lines']: continue
        jac, ratio = score(x, y)
        if max(jac, ratio) >= a.threshold:
            pairs.append((i, j, jac, ratio)); parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i, j, jac, ratio in pairs: groups[find(i)].append((i, j, jac, ratio))
    out = []
    for g in groups.values():
        members = sorted({m for i, j, _, _ in g for m in (i, j)})
        out.append({'size': len(members), 'min_seq_ratio': round(min(p[3] for p in g), 2),
                    'kinds': sorted({label(frags[i], frags[j], r) .split(' ')[0] for i, j, _, r in g}),
                    'members': [tag(frags[m]) for m in members]})
    out.sort(key=lambda o: (-o['size'], o['min_seq_ratio']))
    print(json.dumps({'fragments': n, 'candidates': len(cand), 'pairs': len(pairs), 'groups': out, 'secs': round(time.time() - t0, 2)}, indent=1))

if __name__ == '__main__':
    main()
