"""Print the block around a candidate: the enclosing function or style rule, not the whole file."""
import re

FUNC_START = re.compile(
    r"^(?!\s*(?:if|for|while|switch|catch|else|return|elif|do|try|with|\}\s*else)\b)\s*("
    r"func\s|def\s|async\s+def\s|class\s|(export\s+)?(default\s+)?(async\s+)?function\b|"
    r"(export\s+)?(const|let|var)\s+[\w$]+\s*(:[^=]+)?=\s*(async\s*)?(\([^)]*\)|[\w$]+)\s*(:[^=]+)?=>|"
    r"(public|private|protected|static|async|\s)*[\w$]+\s*\([^;=]*\)\s*(:\s*[^{=]+)?\{\s*$|"
    r"type\s+\w+\s+(struct|interface)|(export\s+)?interface\s+\w+)")
CSS_START = re.compile(r"^\s*[^\s{}][^{};]*\{\s*$")
SFC_TAG = re.compile(r"^\s*<(/?)(template|script|style)\b")
MAX_LINES = 80
MAX_UP = 80
WINDOW = 10


def in_style(lines, i, path):
    if path.endswith((".css", ".scss", ".sass", ".less")):
        return True
    for j in range(i, -1, -1):
        m = SFC_TAG.match(lines[j])
        if m:
            return m.group(2) == "style" and not m.group(1)
    return False


def block_range(lines, line, path=""):
    """1-based inclusive (start, end) of the block holding `line`, or a window around it."""
    return enclosing_block(lines, line, path) or (max(1, line - WINDOW), min(len(lines), line + WINDOW))


def enclosing_block(lines, line, path=""):
    """1-based inclusive (start, end) of the function or style rule holding `line`, or None."""
    i = line - 1
    starter = CSS_START if in_style(lines, i, path) else FUNC_START
    indent = len(lines[i]) - len(lines[i].lstrip())
    start = None
    for j in range(i, max(-1, i - MAX_UP), -1):
        text = lines[j]
        if text.strip() and starter.match(text) and (j == i or len(text) - len(text.lstrip()) < indent or
                                                     len(text) == len(text.lstrip())):
            start = j
            break
        if SFC_TAG.match(text) and j != i:
            break
    if start is None:
        return None
    end = None
    head = lines[start].lstrip()
    if head.startswith(("def ", "async def ", "class ")) and not path.endswith((".ts", ".js", ".vue", ".tsx")):
        lead = len(lines[start]) - len(head)
        for k in range(start + 1, min(len(lines), start + MAX_LINES)):
            t = lines[k]
            if t.strip() and len(t) - len(t.lstrip()) <= lead:
                end = k - 1
                break
    else:
        depth, opened = 0, False
        for k in range(start, min(len(lines), start + MAX_LINES)):
            t = lines[k]
            depth += t.count("{") + t.count("(") - t.count("}") - t.count(")")
            opened = opened or "{" in t
            if opened and depth <= 0:
                end = k
                break
    if end is None or end < i:
        return None
    if end - start + 1 > MAX_LINES:
        start, end = max(start, i - MAX_LINES // 2), min(end, max(start, i - MAX_LINES // 2) + MAX_LINES - 1)
    return start + 1, end + 1


def render(lines, line, context=None, path=""):
    if context is not None:
        start, end = max(1, line - context), min(len(lines), line + context)
    else:
        start, end = block_range(lines, line, path)
    width = len(str(end))
    out = []
    for n in range(start, end + 1):
        mark = ">" if n == line else " "
        out.append("%s%*d  %s" % (mark, width, n, lines[n - 1].rstrip()[:200]))
    return "\n".join(out)
