#!/usr/bin/env python3
"""Winnowed token-shingle index over Go and TS/JS functions (tier-0 look-alike search, stdlib only).

Functions: Go top-level funcs and methods; TS/JS function declarations, const/let arrow or function
expressions, class/object methods, property arrows and Vue hook/computed/watch callbacks, in
.ts/.tsx/.js/.jsx/.mjs/.cjs files (.d.ts skipped) and the <script> blocks of .vue files. Bodies are
found by regex + brace matching (strings, template literals and comments are skipped; JS regex
literals are not understood). Nested functions are indexed too.
Tokens: identifiers, keywords, literals, operators; comments dropped. Two modes:
  raw  = tokens as written
  norm = identifiers -> I, string literals -> S, numbers -> N (keywords and operators kept)
Fingerprints: hash of each k=5 token k-gram; winnowing keeps the minimum of every window of 4
consecutive k-gram hashes (as a set). Similarity: Jaccard of fingerprint sets; containment =
|Q & F| / |Q| (how much of the query function appears in F).

Usage:
  python3 -I shingle_index.py build --out IDX.pkl [--jobs N] LABEL=DIR [LABEL=DIR ...]
  python3 -I shingle_index.py query --index IDX.pkl [--top 5] --func PATH_SUBSTR:NAME[:LINE] ...
  python3 -I shingle_index.py pairs --index IDX.pkl [--threshold 0.8] [--min-tokens 50] [--json OUT]
"""
import argparse
import array
import bisect
import collections
import json
import math
import multiprocessing
import os
import pickle
import re
import time
import zlib

K, W = 5, 4
MIN_INDEX_TOKENS = 8          # k + w - 1: shortest function that yields one full window
SKIP_DIRS = {'.git', 'node_modules', 'vendor', 'dist'}
JS_EXT = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
TEST_PATH = re.compile(r'_test\.go$|/(?:test|tests|__tests__|testdata|e2e)/|\.(?:test|spec)\.[jt]sx?$')


def walk(label, root):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and not d.startswith('.'))
        for fn in sorted(fns):
            ext = os.path.splitext(fn)[1].lower()
            if ext in ('.go', '.vue') or (ext in JS_EXT and not fn.endswith('.d.ts')):
                p = os.path.join(dp, fn)
                yield label + '/' + os.path.relpath(p, root), p


def skip_str(text, i):
    """text[i] is a quote; return the index after the literal ('' and "" stop at end of line)."""
    q, n, j = text[i], len(text), i + 1
    if q == '`':
        while j < n and text[j] != '`':
            j += 2 if text[j] == '\\' else 1
        return min(j + 1, n)
    while j < n and text[j] not in (q, '\n'):
        j += 2 if text[j] == '\\' else 1
    return min(j + 1, n)


def match_close(text, i, limit=400000):
    """text[i] is ( [ or {; return the index after its partner (strings and comments skipped)."""
    depth, n = 0, min(len(text), i + limit)
    while i < n:
        c = text[i]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
            if depth == 0:
                return i + 1
        elif c in '"\'`':
            i = skip_str(text, i)
            continue
        elif c == '/' and text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        elif c == '/' and text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        i += 1
    return n


GO_FUNC = re.compile(r'^func\s*(?:\([^)]*\)\s*)?([A-Za-z_]\w*)', re.M)


def go_funcs(text):
    """(name, start, end) of top-level Go funcs/methods; body = first depth-0 '{' after the name."""
    for m in GO_FUNC.finditer(text):
        i, depth, n = m.end(), 0, len(text)
        while i < n:
            c = text[i]
            if c in '([':
                depth += 1
            elif c in ')]':
                depth -= 1
            elif c == '{' and depth == 0:
                if text[max(0, i - 12):i].rstrip().endswith(('interface', 'struct')):
                    i = match_close(text, i)
                    continue
                yield m.group(1), m.start(), match_close(text, i)
                break
            elif c == '\n' and depth == 0 and text[i + 1:i + 5] == 'func':
                break                                   # declaration without body
            i += 1


JN = r'[A-Za-z_$][\w$]*'
GEN = r'(?:<[^<>()]*>\s*)?'
HOOKS = 'onMounted|onBeforeMount|onBeforeUnmount|onUnmounted|onActivated|onDeactivated|onUpdated|watch|watchEffect|computed'
JS_START = re.compile(
    r'\bfunction\b\s*\*?\s*(?P<f>' + JN + r')\s*' + GEN + r'\('                        # function f(
    r'|\b(?:const|let|var)\s+(?P<c>' + JN + r')\s*(?::[^=\n]{1,80})?=\s*(?:async\s+)?'   # const f = ...
    r'(?P<cf>function\b\s*\*?\s*(?:' + JN + r')?\s*)?' + GEN + r'(?:\(|' + JN + r'\s*=>)'
    r'|^[ \t]*(?:const\s+(?P<hv>' + JN + r')\s*=\s*)?(?P<h>' + HOOKS + r')\s*\('          # onMounted(..
    r'|^[ \t]*(?P<p>' + JN + r'|\'[^\'\n]+\'|"[^"\n]+")\s*:\s*(?:async\s+)?'              # key: (..) =>
    r'(?P<pf>function\b\s*\*?\s*)?' + GEN + r'(?:\(|' + JN + r'\s*=>)'
    r'|^[ \t]*(?:(?:public|private|protected|static|async|override|get|set)\s+)*\*?\s*'  # method(..) {
    r'(?P<m>' + JN + r')\s*' + GEN + r'\(', re.M)
CONTROL = set('if for while switch catch return function typeof new await super import export else do try '
              'throw delete void yield case with'.split())
EXPR_BODY = re.compile(r'[(.\[`\'"?+\-*/!=&|]')     # an expression, not a type such as '=> void'


def after_params(text, j, limit=300):
    """Skip whitespace and a ': ReturnType' after ')'; return (pos, '{' | '=>' | None)."""
    n = len(text)
    while j < n and text[j] in ' \t\r\n':
        j += 1
    if text.startswith('=>', j):
        return j + 2, '=>'
    if j < n and text[j] == '{':
        return j, '{'
    if j >= n or text[j] != ':':
        return j, None
    depth, end, j = 0, min(n, j + limit), j + 1
    while j < end:
        c = text[j]
        if depth == 0 and text.startswith('=>', j):
            return j + 2, '=>'
        if c in '(<[':
            depth += 1
        elif c in ')>]':
            depth -= 1
        elif depth == 0 and c == '{':
            return j, '{'
        elif depth == 0 and c in ';\n':
            break
        j += 1
    return j, None


def expr_end(text, i, limit=3000):
    """End of an arrow's expression body: depth-0 , ; ) ] } or a newline not followed by . ? : etc."""
    depth, n = 0, min(len(text), i + limit)
    while i < n:
        c = text[i]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            if depth == 0:
                return i
            depth -= 1
        elif c in '"\'`':
            i = skip_str(text, i)
            continue
        elif depth == 0 and c in ',;':
            return i
        elif depth == 0 and c == '\n':
            j = i + 1
            while j < n and text[j] in ' \t':
                j += 1
            if j >= n or text[j] not in '.?:|&+-*/':
                return i
        i += 1
    return i


def js_funcs(text):
    """(name, start, end) of named TS/JS functions (see module docstring)."""
    for m in JS_START.finditer(text):
        g = m.groupdict()
        if g['f']:
            name, kind = g['f'], 'block'
        elif g['c']:
            name, kind = g['c'], 'block' if g['cf'] else 'arrow'
        elif g['h']:
            yield g['hv'] or g['h'], m.start(), match_close(text, m.end() - 1)
            continue
        elif g['p']:
            name, kind = g['p'].strip('\'"'), 'block' if g['pf'] else 'arrow'
        else:
            name, kind = g['m'], 'block'
            if name in CONTROL:
                continue
        if text[m.end() - 1] == '(':
            j, tail = after_params(text, match_close(text, m.end() - 1))
        else:
            j, tail = m.end(), '=>'                     # single-parameter arrow: x => ...
        if tail is None or (tail == '=>') != (kind == 'arrow'):
            continue
        if tail == '=>':
            while j < len(text) and text[j] in ' \t\r\n':
                j += 1
            if text.startswith('{', j):
                end = match_close(text, j)
            else:
                end = expr_end(text, j)
                if not EXPR_BODY.search(text, j, end):
                    continue
        else:
            end = match_close(text, j)
        yield name, m.start(), end


SCRIPT = re.compile(r'<script\b[^>]*>(.*?)</script>', re.S | re.I)


def vue_script(text):
    """Keep only <script> blocks of a .vue file; other text becomes newlines (line numbers kept)."""
    out, last = [], 0
    for m in SCRIPT.finditer(text):
        out.append('\n' * text.count('\n', last, m.start(1)))
        out.append(m.group(1))
        last = m.end(1)
    out.append('\n' * text.count('\n', last))
    return ''.join(out)


TOKEN = re.compile(r'\s+|//[^\n]*|/\*.*?\*/|("(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`'
                   r'|\d[\w.]*|[A-Za-z_$][\w$]*|===|!==|\.\.\.|&&|\|\||\?\?|\?\.|=>|<-|\+\+|--'
                   r'|[-+*/%&|^!=<>:]=|\S)', re.S)
GO_KW = set('break case chan const continue default defer else fallthrough for func go goto if import '
            'interface map package range return select struct switch type var nil true false iota'.split())
JS_KW = set('break case catch class const continue debugger default delete do else export extends finally '
            'for function if import in instanceof let new return super switch this throw try typeof var void '
            'while with yield async await of null undefined true false static enum implements interface '
            'private protected public readonly abstract declare as keyof type'.split())
_RAW, _NORM = {}, {'go': {}, 'js': {}}       # per-process token -> int caches


def tok_ids(toks, lang):
    raw, norm, kw = _RAW, _NORM[lang], (GO_KW if lang == 'go' else JS_KW)
    r, q = [], []
    for t in toks:
        v = raw.get(t)
        if v is None:
            v = raw[t] = zlib.crc32(t.encode('utf-8', 'replace'))
        r.append(v)
        u = norm.get(t)
        if u is None:
            c = t[0]
            nt = ('S' if c in '"\'`' else 'N' if c.isdigit() else
                  (t if t in kw else 'I') if (c.isalpha() or c in '_$') else t)
            u = norm[t] = zlib.crc32(nt.encode('utf-8', 'replace'))
        q.append(u)
    return r, q


def winnow(ids):
    """Set of winnowed fingerprints: min hash of each window of W consecutive K-gram hashes."""
    if len(ids) < K:
        return set()
    hs = list(map(hash, zip(*[ids[i:] for i in range(K)])))
    if len(hs) < W:
        return {min(hs)}
    return set(map(min, *[hs[i:] for i in range(W)]))


def process_file(item):
    rel, path = item
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError:
        return rel, 'go' if rel.endswith('.go') else 'js', False, 0, []
    lang = 'go' if rel.endswith('.go') else 'js'
    if rel.endswith('.vue'):
        text = vue_script(text)
    gen = (lang == 'go' and 'Code generated' in text[:600]) or rel.endswith('.min.js')
    funcs = []
    for name, s, e in (go_funcs(text) if lang == 'go' else js_funcs(text)):
        toks = [t for t in TOKEN.findall(text, s, e) if t]
        if len(toks) >= MIN_INDEX_TOKENS:
            r, q = tok_ids(toks, lang)
            funcs.append([name, s, e, len(toks), array.array('q', sorted(winnow(r))).tobytes(),
                          array.array('q', sorted(winnow(q))).tobytes()])
    if funcs:
        nls = [m.start() for m in re.finditer('\n', text)]
        for fr in funcs:
            fr[1:3] = [bisect.bisect_left(nls, fr[1]) + 1, bisect.bisect_left(nls, fr[2] - 1) + 1, fr[1], fr[2]]
    return rel, lang, gen, len(text), funcs


def cmd_build(a):
    T, t0 = {}, time.perf_counter()
    items = []
    for spec in a.roots:
        label, root = spec.split('=', 1)
        items.extend(walk(label, os.path.abspath(root)))
    T['walk'] = time.perf_counter() - t0
    t = time.perf_counter()
    files, funcs, fps = [], [], {'raw': [], 'norm': []}
    with multiprocessing.Pool(a.jobs) as pool:
        for rel, lang, gen, nch, fl in pool.imap(process_file, items, chunksize=16):
            fi = len(files)
            files.append((rel, lang, gen, bool(TEST_PATH.search(rel)), nch))
            for name, ls, le, s, e, ntok, fr, fn in fl:
                funcs.append((fi, name, ls, le, s, e, ntok))
                fps['raw'].append(fr)
                fps['norm'].append(fn)
    T['read_extract_tokenize_winnow'] = time.perf_counter() - t
    modes = {}
    for mode in ('raw', 'norm'):
        t = time.perf_counter()
        off, vals = array.array('q', [0]), array.array('q')
        for b in fps[mode]:
            vals.frombytes(b)
            off.append(len(vals))
        fps[mode] = None
        inv = {}
        for fid in range(len(funcs)):
            for h in vals[off[fid]:off[fid + 1]]:
                p = inv.get(h)
                if p is None:
                    inv[h] = p = array.array('i')
                p.append(fid)
        modes[mode] = {'off': off, 'vals': vals, 'inv': inv}
        T['index_' + mode] = time.perf_counter() - t
    t = time.perf_counter()
    idx = {'k': K, 'w': W, 'files': files, 'funcs': funcs, 'modes': modes}
    with open(a.out, 'wb') as f:
        pickle.dump(idx, f, protocol=pickle.HIGHEST_PROTOCOL)
    T['pickle_write'] = time.perf_counter() - t
    T['total'] = time.perf_counter() - t0
    st = {'files': len(files), 'chars': sum(x[4] for x in files), 'functions': len(funcs),
          'tokens_in_functions': sum(x[6] for x in funcs), 'index_bytes': os.path.getsize(a.out),
          'timings_s': {k: round(v, 3) for k, v in T.items()}}
    by = collections.Counter((files[x[0]][0].split('/', 1)[0], files[x[0]][1]) for x in funcs)
    st['functions_by_label_lang'] = {f'{l}/{g}': n for (l, g), n in sorted(by.items())}
    st['files_by_label_lang'] = {f'{l}/{g}': n for (l, g), n in sorted(collections.Counter(
        (x[0].split('/', 1)[0], x[1]) for x in files).items())}
    st['functions_gen'] = sum(1 for x in funcs if files[x[0]][2])
    st['functions_test'] = sum(1 for x in funcs if files[x[0]][3])
    for mode, m in modes.items():
        st[mode] = {'fingerprints': len(m['vals']), 'distinct': len(m['inv']),
                    'per_function_avg': round(len(m['vals']) / max(1, len(funcs)), 1),
                    'max_posting': max((len(p) for p in m['inv'].values()), default=0)}
    print(json.dumps(st, indent=1))
    if a.stats:
        with open(a.stats, 'w', encoding='utf-8') as f:
            json.dump(st, f, indent=1)


def load(path):
    t = time.perf_counter()
    with open(path, 'rb') as f:
        idx = pickle.load(f)
    return idx, time.perf_counter() - t


def nested(idx, a, b):
    fa, fb = idx['funcs'][a], idx['funcs'][b]
    return fa[0] == fb[0] and ((fa[4] <= fb[4] and fb[5] <= fa[5]) or (fb[4] <= fa[4] and fa[5] <= fb[5]))


def find_func(idx, spec):
    parts = spec.split(':')
    sub, name, line = parts[0], parts[1], (int(parts[2]) if len(parts) > 2 else None)
    c = [i for i, x in enumerate(idx['funcs']) if x[1] == name and sub in idx['files'][x[0]][0]]
    if line is not None:
        c.sort(key=lambda i: abs(idx['funcs'][i][2] - line))
    return c[0] if c else None


def search(idx, mode, qid, top):
    m = idx['modes'][mode]
    off, vals, inv = m['off'], m['vals'], m['inv']
    q = vals[off[qid]:off[qid + 1]]
    cnt = collections.Counter()
    for h in q:
        cnt.update(inv[h])
    nq, res = len(q), []
    for fid, c in cnt.items():
        if fid != qid and not nested(idx, fid, qid):
            nf = off[fid + 1] - off[fid]
            res.append((c / (nq + nf - c), c / nq, fid))
    by_j = sorted(res, reverse=True)[:top]
    by_c = sorted(res, key=lambda r: (r[1], r[0]), reverse=True)[:top]
    return by_j, by_c, len(res), nq


def fmt(idx, fid):
    fi, name, ls, le, _s, _e, ntok = idx['funcs'][fid]
    rel, _lang, gen, test, _n = idx['files'][fi]
    return f"{rel}:{ls}-{le} {name} ntok={ntok}" + (' [gen]' if gen else '') + (' [test]' if test else '')


def cmd_query(a):
    idx, load_s = load(a.index)
    out = {'index_load_s': round(load_s, 3), 'queries': []}
    print(f'index load {load_s:.3f} s, functions={len(idx["funcs"])}')
    for spec in a.func:
        qid = find_func(idx, spec)
        if qid is None:
            print(f'\n## {spec}: NOT FOUND')
            out['queries'].append({'spec': spec, 'found': False})
            continue
        rec = {'spec': spec, 'found': True, 'query': fmt(idx, qid), 'modes': {}}
        print(f'\n## {spec} -> {rec["query"]}')
        for mode in ('raw', 'norm'):
            times = []
            for _ in range(2):
                t = time.perf_counter()
                by_j, by_c, ncand, nq = search(idx, mode, qid, a.top)
                times.append(time.perf_counter() - t)
            rec['modes'][mode] = {'first_run_s': round(times[0], 4), 'repeat_run_s': round(times[1], 4),
                                  'query_fingerprints': nq, 'candidates': ncand,
                                  'top_jaccard': [(round(j, 3), round(c, 3), fmt(idx, f)) for j, c, f in by_j],
                                  'top_containment': [(round(j, 3), round(c, 3), fmt(idx, f)) for j, c, f in by_c]}
            print(f'  [{mode}] fps={nq} candidates={ncand} time {times[0] * 1000:.1f}/{times[1] * 1000:.1f} ms')
            for tag, lst in (('J', by_j), ('C', by_c)):
                for j, c, f in lst:
                    print(f'    by{tag} J={j:.2f} C={c:.2f} {fmt(idx, f)}')
        out['queries'].append(rec)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


def all_pairs(sets, t):
    """Exact pairs with Jaccard >= t (AllPairs prefix filter + size filter); sets: fid -> frozenset."""
    df = collections.Counter()
    for s in sets.values():
        df.update(s)
    index, out = collections.defaultdict(list), []
    for x in sorted(sets, key=lambda f: len(sets[f])):
        sx = sets[x]
        nx = len(sx)
        pre = sorted(sx, key=lambda h: (df[h], h))[:nx - math.ceil(t * nx - 1e-9) + 1]
        seen = set()
        for h in pre:
            for y in index[h]:
                if y in seen:
                    continue
                seen.add(y)
                ny = len(sets[y])
                if ny >= t * nx - 1e-9:
                    inter = len(sx & sets[y])
                    j = inter / (nx + ny - inter)
                    if j >= t - 1e-12:
                        out.append((y, x, j))
        for h in pre:
            index[h].append(x)
    return out


def clusters(edges):
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for x, y in edges:
        parent[find(x)] = find(y)
    groups = collections.Counter(find(x) for x in list(parent))
    return len(groups), sum(groups.values()), max(groups.values(), default=0)


def cmd_pairs(a):
    idx, load_s = load(a.index)
    files, funcs = idx['files'], idx['funcs']

    def label(fid):
        return files[funcs[fid][0]][0].split('/', 1)[0]

    def clean(fid):                                   # neither generated nor test code
        return not files[funcs[fid][0]][2] and not files[funcs[fid][0]][3]
    res = {'index_load_s': round(load_s, 3), 'threshold': a.threshold, 'min_tokens': a.min_tokens, 'modes': {}}
    for mode in ('raw', 'norm'):
        off, vals = idx['modes'][mode]['off'], idx['modes'][mode]['vals']
        t = time.perf_counter()
        sets = {i: frozenset(vals[off[i]:off[i + 1]]) for i, x in enumerate(funcs) if x[6] >= a.min_tokens}
        sets = {i: s for i, s in sets.items() if s}
        prs = [(x, y, j) for x, y, j in all_pairs(sets, a.threshold) if not nested(idx, x, y)]
        r = {'time_s': round(time.perf_counter() - t, 3), 'considered': dict(collections.Counter(map(label, sets))),
             'scopes': {}}
        for scope in sorted({'-'.join(sorted((label(x), label(y)))) for x, y, _ in prs}):
            sp = [p for p in prs if '-'.join(sorted((label(p[0]), label(p[1])))) == scope]
            cl = [p for p in sp if clean(p[0]) and clean(p[1])]
            cross = [p for p in cl if funcs[p[0]][0] != funcs[p[1]][0]]
            nc, nfun, big = clusters([(x, y) for x, y, _ in cl])
            ex = sorted(cross, key=lambda p: (-p[2], -min(funcs[p[0]][6], funcs[p[1]][6])))[:a.examples]
            r['scopes'][scope] = {'pairs': len(sp), 'pairs_no_gen_test': len(cl),
                                  'exact_1.0': sum(1 for p in cl if p[2] >= 1 - 1e-12), 'cross_file': len(cross),
                                  'clusters': nc, 'functions_in_clusters': nfun, 'largest_cluster': big,
                                  'examples': [(round(j, 3), fmt(idx, x), fmt(idx, y)) for x, y, j in ex]}
        res['modes'][mode] = r
        print(f"[{mode}] J>={a.threshold} min_tokens={a.min_tokens} considered={r['considered']} time={r['time_s']} s")
        for scope, s in r['scopes'].items():
            print(f"  {scope}: " + ', '.join(f'{k}={v}' for k, v in s.items() if k != 'examples'))
            for j, x, y in s['examples']:
                print(f'    {j:.2f} {x}  <->  {y}')
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--out', required=True)
    b.add_argument('--stats')
    b.add_argument('--jobs', type=int, default=os.cpu_count())
    b.add_argument('roots', nargs='+', help='LABEL=DIR')
    q = sub.add_parser('query')
    q.add_argument('--index', required=True)
    q.add_argument('--top', type=int, default=5)
    q.add_argument('--func', action='append', required=True, help='PATH_SUBSTR:NAME[:LINE]')
    q.add_argument('--json')
    p = sub.add_parser('pairs')
    p.add_argument('--index', required=True)
    p.add_argument('--threshold', type=float, default=0.8)
    p.add_argument('--min-tokens', type=int, default=50)
    p.add_argument('--examples', type=int, default=12)
    p.add_argument('--json')
    a = ap.parse_args()
    {'build': cmd_build, 'query': cmd_query, 'pairs': cmd_pairs}[a.cmd](a)


if __name__ == '__main__':
    main()
