"""Load the corpus once and run the name, value and rule channels over it."""
import os
import re

from . import names, walk

COMMENT_START = re.compile(r"^\s*(//|#|/\*|\*|<!--|--\s|\{/\*)")
COMMENT_INLINE = re.compile(r"\s(//|#)\s|/\*|<!--")
NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")
# Shapes that carry a rule: comparisons, length checks, validator tags, regex quantifiers, text.
# @V@ stands for the value with ASCII token boundaries (CJK counts as \w, so \b would miss 至少6位).
RULE_SHAPE = (
    r"[<>]=?\s*@V@|@V@\s*[<>]=?|(min|max|len|length|size)\w*\s*[=:(]\s*@V@"
    r"|\{@V@,|,@V@\}|@V@\s*(位|个字符|字符|characters?|chars?|digits?)|(at least|no less than|至少|不少于|不能少于|不小于|最少)\s*@V@"
    r"|(?-i:\b[A-Z][A-Z0-9_]*)\s*[:=]\s*@V@")


def token(value):
    return r"(?<![A-Za-z0-9_.])%s(?![A-Za-z0-9_])" % re.escape(value)
WINDOW = 2


class File:
    __slots__ = ("path", "full", "lines", "text", "stack", "layer", "generated", "root")

    def __init__(self, path, full, lines, stack, layer, root):
        self.path, self.full, self.lines, self.stack, self.layer, self.root = path, full, lines, stack, layer, root
        self.text = "\n".join(lines)
        self.generated = walk.is_generated(lines)


def display_path(full, base):
    rel = os.path.relpath(full, base)
    return full if rel.startswith("..") else rel


def load_corpus(roots, base):
    files, skipped = [], 0
    for root in roots:
        root = os.path.abspath(root)
        guesser = walk.StackGuesser(root)
        for rel in walk.list_files(root):
            full = os.path.join(root, rel)
            lines = walk.read_lines(full)
            if lines is None:
                skipped += 1
                continue
            stack = guesser.stack(rel)
            files.append(File(display_path(full, base), full, lines, stack, walk.layer(rel, stack), root))
    return files, skipped


def is_comment(line, inline=False):
    """Whole-line comment; with inline=True also a line that carries a trailing comment."""
    return bool(COMMENT_START.match(line) or (inline and COMMENT_INLINE.search(line)))


def hit(f, lineno, channel, score, why, seed, match=""):
    return {"path": f.path, "line": lineno, "text": f.lines[lineno - 1].strip()[:300], "channel": channel,
            "score": score, "why": why, "seed": seed, "match": match, "layer": f.layer, "stack": f.stack,
            "generated": f.generated, "comment": is_comment(f.lines[lineno - 1])}


def name_channel(files, seed):
    rx = names.name_regex(seed)
    out = []
    for f in files:
        if not rx.search(f.text):
            continue
        for i, line in enumerate(f.lines, 1):
            m = rx.search(line)
            if m:
                kind = names.spelling(m.group(0), seed)
                why = "名字 %s" % seed if kind == "exact" else "名字变体 %s（种子 %s）" % (m.group(0), seed)
                out.append(hit(f, i, "name", 60 if kind == "exact" else 50, why, seed, m.group(0)))
    return out


def value_regex(value):
    if NUMERIC.match(value) or names.is_identifier_like(value):
        return re.compile(token(value))
    return re.compile(re.escape(value))


def near_regex(words):
    words = [w for w in words if w]
    if not words:
        return None
    parts = []
    for w in words:
        parts.append(names.name_regex(w).pattern if names.is_identifier_like(w) else re.escape(w))
    return re.compile("|".join("(?:%s)" % p for p in parts), re.I)


def needs_near(value):
    return bool(NUMERIC.match(value)) or len(value) <= 2


def value_channel(files, value, near):
    """Literal values. Numbers and very short values only count next to a context word (rule channel)."""
    rx = value_regex(value)
    near_rx = near_regex(near)
    shape = re.compile(RULE_SHAPE.replace("@V@", token(value)), re.I)
    rule = near_rx is not None
    if needs_near(value) and not rule:
        raise ValueError("值 %r 太短或是数字，需要用 --near 给出上下文词" % value)
    out = []
    for f in files:
        if not rx.search(f.text) or (rule and not near_rx.search(f.text)):
            continue
        for i, line in enumerate(f.lines, 1):
            if not rx.search(line):
                continue
            if not rule:
                out.append(hit(f, i, "value", 55, "旧值 %s" % value, value, value))
                continue
            lo, hi = max(0, i - 1 - WINDOW), min(len(f.lines), i + WINDOW)
            same = near_rx.search(line)
            close = same or any(near_rx.search(l) for l in f.lines[lo:hi])
            if not close:
                continue
            has_shape = bool(shape.search(line))
            if not has_shape and not same:
                continue
            score = {(True, True): 65, (False, True): 50, (True, False): 40}[(bool(same), has_shape)]
            word = (same or next(near_rx.search(l) for l in f.lines[lo:hi] if near_rx.search(l))).group(0)
            why = "规则值 %s，旁边有 %s%s" % (value, word, "，像校验或文案" if has_shape else "")
            out.append(hit(f, i, "rule", score, why, value, value))
    return out
