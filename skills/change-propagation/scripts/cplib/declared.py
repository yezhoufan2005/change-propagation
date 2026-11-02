"""Declared-coupling channel: "keep in sync" style comments, in English and Chinese.

Forward: a sync comment inside a seed file points somewhere; the named path or identifier is a
candidate. Reverse: a sync comment anywhere that names a seed file or seed name is a candidate.
"""
import collections
import os
import re

from . import names
from .channels import hit, is_comment

SYNC = re.compile(
    r"\bin[\s-]?sync\b|\bsync(ed|hronized)?\s+with\b|\bkeep\b[^.\n]{0,40}\b(same|consistent|aligned)\b"
    r"|\b(must|should|needs? to|has to)\s+(also\s+)?(be\s+)?(match(ed)?|mirror(ed)?|equal|consistent with|"
    r"aligned with|identical to|the same as|updated|changed)\b"
    r"|\b(if|when(ever)?)\s+(you\s+)?(change|update|modify|rename|edit)\w*\b[^.\n]{0,60}?\b(also|update|change)\b"
    r"|\b(also|remember to|don.?t forget to|make sure to)\s+(update|change|modify|edit|adjust)\b"
    r"|\b(mirrors?|mirrored|duplicated?|copied|counterpart)\s+(of|from|in)\b|LINT\.(IfChange|ThenChange)"
    r"|保持一致|保持同步|同步修改|同步更新|一起修改|一起改|同时修改|同时更新|也要改|也需要改|也要修改|也需要修改|需要同步|需同步"
    r"|注意同步|对应修改|与[^\n]{1,30}一致|和[^\n]{1,30}一致|同[^\n]{1,30}保持", re.I)
# Literal prefilter, run on the lower-cased file: every SYNC alternative contains one of these.
# SYNC itself starts with \b alternatives that Python's re cannot skip ahead on, so it only runs on
# the lines this finds (about 4x faster on 2.3k files).
HINT = re.compile(r"sync|match|mirror|equal|consistent|aligned|identical|the same|also |update |updated|changed|"
                  r"remember to|forget to|make sure to|copied|counterpart|duplicat|lint\.|一致|同步|一起|同时|也要|"
                  r"也需要|对应|保持")
PATH_TOKEN = re.compile(r"(?:[\w@.\-]+/)+[\w@.\-]+\.[A-Za-z]{1,6}\b|\b[\w\-]+\.(?:go|ts|tsx|js|jsx|mjs|py|vue|java|kt|"
                        r"sql|md|ya?ml|json|toml|proto|scss|css|html)\b")
IDENT = re.compile(r"\b(?:[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+|[a-z]+(?:[A-Z][a-z0-9]+)+|[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+)\b")
MAX_IDENT_FILES = 5
MAX_SAME_NAME = 3       # a file name shared by more files (index.vue) is matched with its directory


def comment_text(lines, i):
    """The comment on line i plus up to 2 following comment lines, where targets often are."""
    out = [lines[i].strip()]
    for j in range(i + 1, min(i + 3, len(lines))):
        if is_comment(lines[j], inline=True):
            out.append(lines[j].strip())
        else:
            break
    return " ".join(out)[:400]


def sync_comments(files):
    for f in files:
        low = f.text.lower()
        seen, lineno, pos = set(), 0, 0
        for m in HINT.finditer(low):
            lineno += low.count("\n", pos, m.start())
            pos = m.start()
            if lineno in seen:
                continue
            seen.add(lineno)
            line = f.lines[lineno]
            if SYNC.search(line) and (f.layer == "docs" or is_comment(line, inline=True)):
                yield f, lineno + 1, comment_text(f.lines, lineno)


def _resolve(files, text, origin):
    """Lines that a comment's path or identifier tokens point to (first line mentioning them)."""
    by_base = {}
    for f in files:
        by_base.setdefault(os.path.basename(f.path), []).append(f)
    targets = []
    for tok in PATH_TOKEN.findall(text):
        tok = tok.strip("./")
        for f in by_base.get(os.path.basename(tok), [])[:3]:
            if f.path.endswith(tok) and f.path != origin:
                targets.append((f, 1, "注释点名了文件 %s" % tok, tok))
    for ident in set(IDENT.findall(text)):
        if len(ident) < 5:
            continue
        rx = re.compile(r"(?<![\w$])%s(?![\w$])" % re.escape(ident))
        found = [f for f in files if f.path != origin and ident in f.text and rx.search(f.text)]
        if 0 < len(found) <= MAX_IDENT_FILES:
            for f in found:
                line = next(i for i, l in enumerate(f.lines, 1) if rx.search(l))
                targets.append((f, line, "注释点名了 %s" % ident, ident))
    return targets


def _mention_keys(files, seed_files):
    """What a comment must contain to name a seed file: its stem (Register for Register.vue), or for
    a name that many files share, the directory too (scene-edit/index, not every index.vue)."""
    counts = collections.Counter(os.path.basename(f.path) for f in files)
    out = set()
    for p in seed_files:
        name = os.path.basename(p)
        key = os.path.splitext(name)[0]
        if counts[name] > MAX_SAME_NAME and os.path.dirname(p):
            key = os.path.basename(os.path.dirname(p)) + "/" + key
        if len(key) >= 4:
            out.add(key)
    return out


def declared_channel(files, seed_files, seed_names):
    seed_files = {os.path.normpath(p) for p in seed_files}
    seed_keys = _mention_keys(files, seed_files)
    name_rx = [names.name_regex(n) for n in seed_names]
    out = []
    for f, line, text in sync_comments(files):
        if os.path.normpath(f.path) in seed_files:
            h = hit(f, line, "declared", 45, "被改文件里的同步注释：%s" % text[:80], f.path)
            out.append(h)
            for tf, tline, why, tok in _resolve(files, text, f.path):
                out.append(hit(tf, tline, "declared", 70, "%s 的同步注释%s" % (f.path, why), tok, tok))
            continue
        named = any(re.search(r"(?<![\w-])%s\b" % re.escape(k), text) for k in seed_keys)
        if named or any(rx.search(text) for rx in name_rx):
            out.append(hit(f, line, "declared", 60, "同步注释提到了被改的位置：%s" % text[:80], f.path))
    return out
