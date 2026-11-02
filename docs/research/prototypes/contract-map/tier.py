import re, sys, os
sys.path.insert(0, '/tmp/cp-contracts')
import importlib.util
s = importlib.util.spec_from_file_location('proto', '/tmp/cp-contracts/proto.py'); P = importlib.util.module_from_spec(s); s.loader.exec_module(P)
EXTS = ('.py', '.js', '.ts', '.mjs', '.cjs', '.vue', '.go')
roots, seeds = sys.argv[1:3], sys.argv[3].split(',')
lines = []
for r in roots:
    for d, _, fs in os.walk(r):
        for f in fs:
            if f.endswith(EXTS):
                with open(os.path.join(d, f), encoding='utf-8', errors='ignore') as fh:
                    lines.extend(fh.read().splitlines())
for seed in seeds:
    w = P.words(seed); fseed = ''.join(w)
    tok = re.compile(r'[A-Za-z0-9_]*' + r'[-_]?'.join(w) + r'[A-Za-z0-9_]*', re.I)
    prose = re.compile(r'(?i)\b' + r'[ .]'.join(w) + r's?\b')
    a = b = c = 0
    for ln in lines:
        toks = [t for t in tok.findall(ln)]
        if any(P.fold(t) == fseed for t in toks): a += 1
        elif toks: b += 1
        elif prose.search(ln): c += 1
    print('seed=%-13s A(identifier folds to seed)=%d  B(seed inside longer identifier)=%d  C(prose/dotted only)=%d' % (seed, a, b, c))
