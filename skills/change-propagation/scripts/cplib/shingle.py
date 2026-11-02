"""Function-fingerprint channel: copies of a function that were renamed or drifted.

`--func PATH:NAME` takes the body of that function as the query. Every TS/JS/Vue-script and Go
function in the roots is tokenized; identifiers become I, strings S, numbers N (keywords and
operators kept), so renamed variables still match. Each body becomes a set of winnowed 5-token
fingerprints, and candidates are ranked by containment: the share of the query's fingerprints
found in the candidate. Adapted from the research prototype measurements/shingle_index.py.
"""
import os
import re
import zlib

from .channels import hit

K, W = 5, 4
MIN_TOKENS = 25
MIN_CONTAINMENT = 0.35
SIZE_RATIO = 2.0
TOP = 15
JS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue")


def skip_str(text, i):
    q, n, j = text[i], len(text), i + 1
    if q == "`":
        while j < n and text[j] != "`":
            j += 2 if text[j] == "\\" else 1
        return min(j + 1, n)
    while j < n and text[j] not in (q, "\n"):
        j += 2 if text[j] == "\\" else 1
    return min(j + 1, n)


def match_close(text, i, limit=200000):
    """text[i] is ( [ or {; return the index after its partner (strings and comments skipped)."""
    depth, n = 0, min(len(text), i + limit)
    while i < n:
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        elif c in "\"'`":
            i = skip_str(text, i)
            continue
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        i += 1
    return n


GO_FUNC = re.compile(r"^func\s*(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", re.M)
JN = r"[A-Za-z_$][\w$]*"
JS_START = re.compile(
    r"\bfunction\b\s*\*?\s*(?P<f>" + JN + r")\s*(?:<[^<>()]*>\s*)?\("
    r"|\b(?:const|let|var)\s+(?P<c>" + JN + r")\s*(?::[^=\n]{1,80})?=\s*(?:async\s+)?(?:function\b[^(]*)?\("
    r"|^[ \t]*(?P<p>" + JN + r")\s*:\s*(?:async\s+)?(?:function\b[^(]*)?\("
    r"|^[ \t]*(?:(?:public|private|protected|static|async)\s+)*(?P<m>" + JN + r")\s*\(", re.M)
CONTROL = set("if for while switch catch return function typeof new await super import export else do try "
              "throw delete void yield case with".split())
SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
TOKEN = re.compile(r"\s+|//[^\n]*|/\*.*?\*/|(\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`"
                   r"|\d[\w.]*|[A-Za-z_$][\w$]*|===|!==|\.\.\.|&&|\|\||\?\?|\?\.|=>|\+\+|--|[-+*/%&|^!=<>:]=|\S)", re.S)
KEYWORDS = set("break case catch class const continue default delete do else export extends finally for "
               "function if import in instanceof let new return super switch this throw try typeof var void "
               "while yield async await of null undefined true false nil func go defer range map struct "
               "interface chan select type package".split())


def vue_script(text):
    """Only the <script> blocks; other text becomes newlines so line numbers stay right."""
    out, last = [], 0
    for m in SCRIPT.finditer(text):
        out.append("\n" * text.count("\n", last, m.start(1)))
        out.append(m.group(1))
        last = m.end(1)
    out.append("\n" * text.count("\n", last))
    return "".join(out)


def functions(path, text):
    """(name, start offset, end offset) for Go funcs and named TS/JS functions with a block body."""
    if path.endswith(".go"):
        for m in GO_FUNC.finditer(text):
            i = text.find("{", m.end())
            if i > 0 and "\n\nfunc" not in text[m.end():i]:
                yield m.group(1), m.start(), match_close(text, i)
        return
    for m in JS_START.finditer(text):
        name = m.group("f") or m.group("c") or m.group("p") or m.group("m")
        if not name or name in CONTROL:
            continue
        j = match_close(text, m.end() - 1)
        k = j
        while k < len(text) and text[k] in " \t\r\n":
            k += 1
        if text.startswith(":", k):                       # return type
            brace = text.find("{", k)
            arrow = text.find("=>", k)
            k = arrow + 2 if 0 <= arrow < brace else brace
            while 0 <= k < len(text) and text[k] in " \t\r\n":
                k += 1
        elif text.startswith("=>", k):
            k += 2
            while k < len(text) and text[k] in " \t\r\n":
                k += 1
        if 0 <= k < len(text) and text[k] == "{":
            yield name, m.start(), match_close(text, k)


def fingerprints(body):
    toks = [m.group(1) for m in TOKEN.finditer(body) if m.group(1)]
    ids = []
    for t in toks:
        c = t[0]
        norm = "S" if c in "\"'`" else "N" if c.isdigit() else (t if t in KEYWORDS else "I") if (c.isalpha() or c in "_$") else t
        ids.append(zlib.crc32(norm.encode()))
    if len(ids) < MIN_TOKENS:
        return len(ids), set()
    grams = [hash(tuple(ids[i:i + K])) for i in range(len(ids) - K + 1)]
    if len(grams) < W:
        return len(ids), {min(grams)}
    return len(ids), {min(grams[i:i + W]) for i in range(len(grams) - W + 1)}


def _source(f):
    if f.path.endswith(".vue"):
        return vue_script(f.text)
    return f.text


def index(files):
    out = []
    for f in files:
        if not f.path.endswith(JS_EXT + (".go",)) or f.path.endswith(".d.ts"):
            continue
        text = _source(f)
        for name, start, end in functions(f.path, text):
            n, fp = fingerprints(text[start:end])
            if fp:
                out.append((f, name, text.count("\n", 0, start) + 1, n, fp))
    return out


def func_channel(files, spec):
    """spec is PATH:NAME; the query is that function's body."""
    path, _, name = spec.rpartition(":")
    if not path or not name:
        raise ValueError("--func 要写成 path:函数名，%r 不是" % spec)
    idx = index(files)
    want = os.path.normpath(path)
    query = [e for e in idx if os.path.normpath(e[0].path).endswith(want) and e[1] == name]
    if not query:
        raise ValueError("--func 没找到 %s 里的函数 %s（只认识带花括号函数体的具名函数）" % (path, name))
    qf, qname, qline, qn, qfp = query[0]
    scored = []
    for f, fname, line, n, fp in idx:
        if f is qf and fname == qname:
            continue
        shared = len(qfp & fp)
        contain = shared / len(qfp)
        if contain >= MIN_CONTAINMENT:
            jacc = shared / len(qfp | fp)
            # A much larger function contains most short queries by chance; rank it down.
            rank = contain * min(1.0, SIZE_RATIO * len(qfp) / len(fp))
            scored.append((rank, contain, jacc, f, fname, line, n))
    scored.sort(key=lambda t: (-t[0], -t[2]))
    out = []
    for rank, contain, jacc, f, fname, line, n in scored[:TOP]:
        if f is qf and qline <= line:
            continue        # a nested function of the query itself
        same = "同名" if fname == qname else "名字不同（%s）" % fname
        why = "和 %s 的函数体相似：包含度 %.0f%%，Jaccard %.0f%%，%s" % (qname, contain * 100, jacc * 100, same)
        if rank < contain * 0.6:
            why += "；对方大得多，可能只是包含了相似的片段"
        score = 40 + int(rank * 35)
        h = hit(f, line, "func", min(75, score), why, spec, fname)
        h["role"] = "copy"
        out.append(h)
    return out
