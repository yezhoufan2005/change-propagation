#!/usr/bin/env python3
"""Prototype: stdlib-only near-duplicate function finder (token normalization + k-gram Jaccard + difflib ratio).
Usage: python3 -I neardup.py ROOT [--k 5] [--min-tokens 30] [--threshold 0.7] [--mode blind|consistent|exact]
"""
import sys, os, re, json, difflib, argparse, itertools

EXTS = {'.ts', '.tsx', '.js', '.jsx', '.java', '.kt', '.go', '.swift', '.dart', '.py'}
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', 'out', 'vendor', '.next', 'Pods', '.dart_tool'}
KEYWORDS = set('''if else for while do return const let var function class new this super try catch finally throw
switch case default break continue import export from as async await yield typeof instanceof in of void delete
public private protected static final abstract interface extends implements package fun val when object data
func go defer chan select struct type map range nil true false null undefined def elif lambda pass with self
None True False and or not is guard let struct enum protocol extension init deinit override late required'''.split())

TOKEN_RE = re.compile(r'''
  (?P<ws>\s+)
 |(?P<lc>//[^\n]*|\#[^\n]*)
 |(?P<bc>/\*.*?\*/)
 |(?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)
 |(?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
 |(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)
 |(?P<op>=>|===|!==|==|!=|<=|>=|&&|\|\||\?\?|\?\.|\+\+|--|[-+*/%=<>!&|^~?:;,.(){}\[\]@])
''', re.S | re.X)

def tokenize(src):
    toks = []  # (kind, text, line)
    line = 1
    for m in TOKEN_RE.finditer(src):
        kind = m.lastgroup; text = m.group(kind)
        if kind not in ('ws', 'lc', 'bc'):
            toks.append((kind, text, line))
        line += text.count('\n')
    return toks

HEADER = re.compile(r'(?:function\s+\w+\s*\(|(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\(|func\s+(?:\([^)]*\)\s*)?\w+\s*\(|fun\s+\w+\s*\(|def\s+\w+\s*\()')

def functions(path, src, toks):
    """Very rough function extraction: header regex, then brace matching (or indentation for Python)."""
    frags = []
    lines = src.split('\n')
    if path.endswith('.py'):
        for i, l in enumerate(lines):
            m = re.match(r'(\s*)def\s+(\w+)', l)
            if not m: continue
            ind = len(m.group(1)); j = i + 1
            while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > ind): j += 1
            frags.append((m.group(2), i + 1, j))
        return frags
    for m in HEADER.finditer(src):
        start_line = src.count('\n', 0, m.start()) + 1
        name = re.findall(r'\w+', m.group(0))[1] if len(re.findall(r'\w+', m.group(0))) > 1 else '?'
        depth = 0; started = False; end_line = None
        for kind, text, ln in toks:
            if ln < start_line: continue
            if text == '{': depth += 1; started = True
            elif text == '}':
                depth -= 1
                if started and depth == 0: end_line = ln; break
        if end_line: frags.append((name, start_line, end_line))
    return frags

def normalize(ftoks, mode):
    out, mapping = [], {}
    for kind, text, _ in ftoks:
        if kind == 'id' and text not in KEYWORDS:
            if mode == 'blind': out.append('ID')
            elif mode == 'consistent': out.append('ID%d' % mapping.setdefault(text, len(mapping)))
            else: out.append(text)
        elif kind == 'str': out.append('STR' if mode != 'exact' else text)
        elif kind == 'num': out.append('NUM' if mode != 'exact' else text)
        else: out.append(text)
    return out

def kgrams(seq, k):
    return {tuple(seq[i:i + k]) for i in range(max(0, len(seq) - k + 1))}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root'); ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--min-tokens', type=int, default=30); ap.add_argument('--threshold', type=float, default=0.7)
    ap.add_argument('--mode', default='blind', choices=['blind', 'consistent', 'exact'])
    a = ap.parse_args()
    frags = []
    for d, dirs, files in os.walk(a.root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            p = os.path.join(d, f)
            if os.path.splitext(f)[1] not in EXTS: continue
            src = open(p, encoding='utf-8', errors='replace').read(); toks = tokenize(src)
            for name, s, e in functions(p, src, toks):
                ft = [t for t in toks if s <= t[2] <= e]
                if len(ft) < a.min_tokens: continue
                norm = normalize(ft, a.mode)
                frags.append({'file': os.path.relpath(p, a.root), 'name': name, 'lines': [s, e], 'n': len(ft), 'norm': norm, 'grams': kgrams(norm, a.k)})
    pairs = []
    for x, y in itertools.combinations(frags, 2):
        if x['file'] == y['file'] and x['lines'] == y['lines']: continue
        jac = len(x['grams'] & y['grams']) / max(1, len(x['grams'] | y['grams']))
        ratio = difflib.SequenceMatcher(None, x['norm'], y['norm'], autojunk=False).ratio()
        if max(jac, ratio) >= a.threshold:
            pairs.append({'a': f"{x['file']}:{x['lines'][0]}-{x['lines'][1]} {x['name']}", 'b': f"{y['file']}:{y['lines'][0]}-{y['lines'][1]} {y['name']}", 'jaccard': round(jac, 2), 'seq_ratio': round(ratio, 2)})
    print(json.dumps({'mode': a.mode, 'k': a.k, 'threshold': a.threshold, 'fragments': len(frags), 'pairs': sorted(pairs, key=lambda p: -p['seq_ratio'])}, indent=1))

if __name__ == '__main__':
    main()
