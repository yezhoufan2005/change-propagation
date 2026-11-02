"""Shared tokenizer and abstraction for the fix-seeded variant experiment.

Language-agnostic enough for Go, TS/JS and Vue SFC script/template text.
"""
import re

TOK = re.compile(r'''
    (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`[^`]*`)
  | (?P<num>\b0[xX][0-9a-fA-F]+\b|\b\d+(?:\.\d+)?\b)
  | (?P<id>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<op>===|!==|==|!=|<=|>=|&&|\|\||:=|=>|\?\?|\?\.|\+\+|--|<-|[-+*/%=<>!&|^~?:;,.(){}\[\]@#])
''', re.X)

KEYWORDS = set('''
break case chan const continue default defer else fallthrough for func go goto if
import interface map package range return select struct switch type var nil true false
let function new this typeof instanceof in of void delete throw try catch finally
class extends super export from as async await yield null undefined while do
string int int64 int32 float64 bool byte error any
'''.split())

COMMENT = re.compile(r'^\s*(//|/\*|\*|<!--|#)')


def tokens(line):
    out = []
    for m in TOK.finditer(line):
        out.append((m.lastgroup, m.group(0)))
    return out


def abs2(toks):
    """VUDDY-like: abstract lowercase local names; keep keywords, member names,
    call names, capitalized (exported/type/component) names and literals."""
    out = []
    n = len(toks)
    for i, (kind, t) in enumerate(toks):
        prev = toks[i - 1][1] if i else None
        nxt = toks[i + 1][1] if i + 1 < n else None
        if kind == 'id' and t not in KEYWORDS and prev not in ('.', '?.') and nxt != '(' \
                and not t[:1].isupper():
            out.append('$')
        else:
            out.append(t)
    return out


def delta_window(rem_lines, add_lines, pad=3):
    """Abstracted (abs2) token window around the removed-side change, ReDeBug/MOVERY-style core."""
    rt, at = [], []
    for l in rem_lines:
        if not trivial_line(l):
            rt.extend(tokens(l))
    for l in add_lines:
        if not trivial_line(l):
            at.extend(tokens(l))
    ra, aa = abs2(rt), abs2(at)
    import difflib
    sm = difflib.SequenceMatcher(None, ra, aa, autojunk=False)
    lo, hi = None, None
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != 'equal':
            s, e = (i1, i2) if i2 > i1 else (max(0, i1 - 1), i1 + 1)
            lo = s if lo is None else min(lo, s)
            hi = e if hi is None else max(hi, e)
    if lo is None:
        return None
    return ra[max(0, lo - pad):min(len(ra), hi + pad)]


def abs3(toks):
    """Abstract every identifier and literal (VUDDY level-4-like)."""
    out = []
    for kind, t in toks:
        if kind == 'id' and t not in KEYWORDS:
            out.append('$')
        elif kind == 'str':
            out.append('S')
        elif kind == 'num':
            out.append('N')
        else:
            out.append(t)
    return out


def norm0(line):
    return re.sub(r'\s+', '', line)


def trivial_line(line):
    s = line.strip()
    if not s or COMMENT.match(s):
        return True
    if re.fullmatch(r'[{}()\[\];,]*', s):
        return True
    if s.startswith('import ') or re.fullmatch(r'"[^"]+"', s):  # Go import block entry
        return True
    return False
