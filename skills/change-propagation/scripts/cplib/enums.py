"""Enum-mapping channel: other tables that map the same set of values.

A change to how one enum value looks or behaves (info shown blue, a new status) has to reach every
table that maps that enum: style maps, switch statements, chart colours chosen by share, tag types.
They are written differently and rarely share a name, but they mention two or more sibling values
close together. A table that mentions the siblings but not the changed value is flagged: the value
probably falls through to a default branch (`default: return 'transparent'`).
"""
import re

from .channels import hit
from .shingle import match_close

WINDOW = 6
# A value counts only where code maps it: a string literal ('info'), an object or YAML key (info:),
# a class or BEM suffix (.tip--info, tip-info), or a member of a map (LEVEL.INFO, colors.info).
# Bare identifiers and words (success: true is a key, but console.error( is a call) are skipped.
SHAPES = [
    r"""(["'`])@V@\1""",
    r"""(?<![\w$.])@V@\s*:(?!:)""",
    r"""[.\w](--|-|__)@V@(?![\w-])""",
    r"""\.@V@(?![\w$(])""",
]
FALLBACK = re.compile(r"\bdefault\s*:|\?\?|\|\||\belse\b|\bdefault\b|getOrDefault|\.get\(|^\s*:\s*\S")
MAP_NAME = re.compile(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)|([A-Za-z_$][\w$]*)\s*[:=]\s*\{\s*$")
BOOL_KEY = re.compile(r"(?<![\w$.])(success|error|ok)\s*:\s*(true|false|null|undefined)\b|\.(success|error|ok)\b(?!\s*\()")


def _shape(value):
    v = re.escape(value)
    return re.compile("|".join("(?:%s)" % sh.replace("@V@", v) for sh in SHAPES), re.I)


def _values_on(line, shapes):
    if BOOL_KEY.search(line):
        line = BOOL_KEY.sub(" ", line)
    return {v for v, rx in shapes.items() if rx.search(line)}


def _blocks(per_line, start, last):
    """Split a run at blank lines; yield (first, last) of each part that maps 2+ values."""
    i = start
    while i <= last:
        j = i
        while j <= last and per_line[j] is not None:
            j += 1
        part = [k for k in range(i, j) if per_line[k]]
        if part and len(set().union(*(per_line[k] for k in part))) >= 2:
            yield part[0], part[-1]
        i = j + 1


def _has_fallback(lines, first, last):
    """A fallback branch right after the block, or a later line that reads the block's map with one."""
    if any(FALLBACK.search(l) for l in lines[first:min(len(lines), last + WINDOW)]):
        return True
    m = MAP_NAME.search(lines[first]) or (first and MAP_NAME.search(lines[first - 1]))
    name = m and (m.group(1) or m.group(2))
    if not name:
        return False
    use = re.compile(r"(?<![\w$])%s(?![\w$])" % re.escape(name))
    return any(use.search(l) and FALLBACK.search(l) for l in lines[last + 1:])


def tables(files, values):
    """Yield (file, first line, values seen, has fallback) for each block that maps 2+ sibling values.

    Lines with values form a run when gaps are at most WINDOW lines; a run is then split at blank
    lines, so a status map next to a list of sample data stays a separate table, while a CSS map
    whose rules are one per block is reported once for the whole run.
    """
    values = [v.lower() for v in values]
    shapes = {v: _shape(v) for v in values}
    alt = re.compile("|".join(re.escape(v) for v in values), re.I)
    for f in files:
        if len({v for v in values if re.search(re.escape(v), f.text, re.I)}) < 2:
            continue
        # None marks a blank line, an empty set a line without values.
        per_line = [None if not l.strip() else (_values_on(l, shapes) if alt.search(l) else set()) for l in f.lines]
        i, n = 0, len(per_line)
        while i < n:
            if not per_line[i] or len(set().union(*(x for x in per_line[i:i + WINDOW] if x))) < 2:
                i += 1
                continue
            start, last = i, i
            j = i + 1
            while j < n and j - last <= WINDOW:
                if per_line[j]:
                    last = j
                j += 1
            run = set().union(*(x for x in per_line[start:last + 1] if x))
            parts = list(_blocks(per_line, start, last))
            if len(parts) <= 1:
                yield f, start + 1, run, _has_fallback(f.lines, start, last)
            else:
                for a, b in parts:
                    seen = set().union(*(x for x in per_line[a:b + 1] if x))
                    yield f, a + 1, seen, _has_fallback(f.lines, a, b)
            i = last + 1


ARRAY_START = re.compile(r"(?:[:=(,]|\breturn)\s*\[(?=\s*[^\s\]])")
QUOTED = re.compile(r"""^\s*(["'`])([^"'`]*)\1\s*$""")
NEAR_LINES = 20
MAX_ARRAY = 1200


def _items(text, i):
    """Items of the array literal whose '[' is at text[i]: [(item text, offset)], end offset."""
    end = match_close(text, i, MAX_ARRAY)
    if end - i >= MAX_ARRAY or text[end - 1] != "]":
        return None, end
    items, depth, start = [], 0, i + 1
    for k in range(i + 1, end - 1):
        c = text[k]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            items.append((text[start:k], start))
            start = k + 1
    last = text[start:end - 1]
    if last.strip():
        items.append((last, start))
    return [(t.strip(), o + len(t) - len(t.lstrip())) for t, o in items], end


def parallel_arrays(files, values):
    """Arrays indexed alongside an array of the enum values: ['info','success'] and ['transparent', '#18a058'].

    A colour picked by position (COLORS[LEVELS.indexOf(level)], ECharts `color` in the order of the
    levels) has no value name near it, so the table search cannot see it."""
    values = [v.lower() for v in values]
    changed = values[0]
    for f in files:
        low = f.text.lower()
        if sum(1 for v in values if v in low) < 2:
            continue
        arrays = []
        for m in ARRAY_START.finditer(f.text):
            i = m.end() - 1
            items, _ = _items(f.text, i)
            if items:
                arrays.append((i, items))
        keys = []
        for i, items in arrays:
            names = [QUOTED.match(t) and QUOTED.match(t).group(2).lower() for t, _ in items]
            if all(names) and len(set(names) & set(values)) >= 2:
                keys.append((i, names))
        for ki, names in keys:
            kline = f.text.count("\n", 0, ki) + 1
            for i, items in arrays:
                if i == ki or len(items) != len(names) or abs(f.text.count("\n", 0, i) + 1 - kline) > NEAR_LINES:
                    continue
                if any(QUOTED.match(t) and QUOTED.match(t).group(2).lower() in values for t, _ in items):
                    continue
                if changed in names:
                    k = names.index(changed)
                    line = f.text.count("\n", 0, items[k][1]) + 1
                    why = "和第 %d 行的 %s 数组按下标对应：%s 是第 %d 项，这里第 %d 项是 %s" % (
                        kline, "、".join(names), changed, k + 1, k + 1, items[k][0][:40])
                    score = 70
                else:
                    line = f.text.count("\n", 0, i) + 1
                    why = "和第 %d 行的 %s 数组按下标对应，那个数组没有 %s" % (kline, "、".join(names), changed)
                    score = 60
                yield f, line, why, score


def enum_channel(files, values):
    """values[0] is the value being changed; the rest are its siblings."""
    changed = values[0].lower()
    out = []
    for f, line, why, score in parallel_arrays(files, values):
        h = hit(f, line, "enum", score, why, ",".join(values), changed)
        h["role"] = "parallel"
        out.append(h)
    for f, line, seen, fallback in tables(files, values):
        others = sorted(seen - {changed})
        if changed in seen:
            why, score = "映射表含 %s 和 %s" % (changed, "、".join(others)), 60
        elif fallback:
            why, score = "映射表含 %s，没有 %s，走 default 或兜底分支" % ("、".join(others), changed), 70
        else:
            why, score = "同一组值 %s 写在一起，没有 %s" % ("、".join(others), changed), 40
        h = hit(f, line, "enum", score, why, ",".join(values), changed)
        h["role"] = "table"
        out.append(h)
    return out
