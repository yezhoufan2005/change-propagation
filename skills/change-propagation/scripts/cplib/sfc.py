"""Vue SFC structure: template element tree, style rules per class, and layout queries.

Standard library only: the template is read with html.parser (tag names come back lower-case),
style blocks with a small brace parser that resolves SCSS nesting (`&__head`, `&:hover`).
"""
import html.parser
import os
import re

SCROLL_TAGS = {"n-scrollbar", "nscrollbar", "el-scrollbar", "elscrollbar", "a-scrollbar", "ascrollbar"}
TABLE_TAGS = {"n-data-table", "ndatatable", "el-table", "eltable", "a-table", "atable"}
SKIP_CHILD = {"nempty", "n-empty", "nspin", "n-spin", "template", "transition"}
INLINE = {"span", "i", "b", "strong", "em", "small", "ntag", "n-tag", "nicon", "n-icon", "icon", "svg", "img",
          "nellipsis", "n-ellipsis", "ntooltip", "n-tooltip", "br", "template"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = re.compile(r"^\s*<(template|script|style)\b([^>]*)>\s*$")
CLASS_WORD = re.compile(r"[A-Za-z_][\w-]*")
IMPORT = re.compile(r"""import\s+([A-Z][\w$]*)\s+from\s+['"]([^'"]+\.vue)['"]""")
UTILITY = [
    (re.compile(r"^overflow(-y)?-(auto|scroll)$"), ("overflow-y", "auto")),
    (re.compile(r"^overflow(-y)?-hidden$"), ("overflow-y", "hidden")),
    (re.compile(r"^(max-)?h-\d"), ("max-height", "set")),
    (re.compile(r"^sticky$"), ("position", "sticky")),
    (re.compile(r"^bg-(?!transparent$|white$|opacity)"), ("background", "set")),
]


class Node:
    __slots__ = ("tag", "attrs", "line", "children", "parent", "classes", "style")

    def __init__(self, tag, attrs, line, parent):
        self.tag, self.attrs, self.line, self.parent = tag, attrs, line, parent
        self.children = []
        self.classes = []
        self.style = {}
        for name in ("class", ":class", "v-bind:class"):
            if attrs.get(name):
                text = attrs[name]
                words = re.findall(r"['\"`]([^'\"`]+)['\"`]", text) if name != "class" else [text]
                for w in words:
                    self.classes += [c for c in w.split() if CLASS_WORD.fullmatch(c)]
        for part in (attrs.get("style") or "").split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                self.style[k.strip().lower()] = v.strip().lower()
        for m in re.finditer(r"([\w-]+)\s*:\s*['\"]([^'\"]+)['\"]", attrs.get(":style") or ""):
            self.style[re.sub(r"(?<=[a-z])([A-Z])", r"-\1", m.group(1)).lower()] = m.group(2).lower()

    def elements(self):
        return [c for c in self.children if c.tag not in SKIP_CHILD or c.tag == "template"]


class _TreeBuilder(html.parser.HTMLParser):
    def __init__(self, first_line):
        super().__init__(convert_charrefs=True)
        self.first_line = first_line      # HTMLParser uses self.offset for the column itself
        self.root = Node("#root", {}, first_line, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, self.first_line + self.getpos()[0] - 1, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, {k: (v or "") for k, v in attrs}, self.first_line + self.getpos()[0] - 1, self.cur))

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent


def blocks(lines):
    """[(kind, attrs, first body line index, end index)] for top-level template/script/style blocks."""
    out, i, n = [], 0, len(lines)
    while i < n:
        m = BLOCK.match(lines[i])
        if not m:
            i += 1
            continue
        kind, depth, j = m.group(1), 0, i
        while j < n:
            depth += len(re.findall(r"<%s\b" % kind, lines[j])) - len(re.findall(r"</%s\s*>" % kind, lines[j]))
            if depth <= 0:
                break
            j += 1
        out.append((kind, m.group(2), i + 1, j))
        i = j + 1
    return out


def parse_template(lines, start, end):
    builder = _TreeBuilder(start + 1)
    try:
        builder.feed("\n".join(lines[start:end]))
        builder.close()
    except Exception:  # html.parser raises only on pathological input; skip the file then
        return None
    return builder.root


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?m)(^|\s)//[^\n]*", " ", text)


def parse_style(text):
    """{class name: {property: value}} for the last class of each selector, with SCSS nesting resolved."""
    rules, stack, buf = {}, [], ""
    for ch in _strip_comments(text):
        if ch == "{":
            sel = buf.strip()
            buf = ""
            parents = stack[-1] if stack and stack[-1] is not None else [""]
            if sel.startswith("@"):
                stack.append(stack[-1] if stack else None)
                continue
            resolved = []
            for p in parents:
                for s in sel.split(","):
                    s = s.strip()
                    resolved.append(s.replace("&", p) if "&" in s else ("%s %s" % (p, s)).strip())
            stack.append(resolved)
        elif ch == "}":
            _declare(rules, stack[-1] if stack else None, buf)
            buf = ""
            if stack:
                stack.pop()
        elif ch == ";":
            _declare(rules, stack[-1] if stack else None, buf)
            buf = ""
        else:
            buf += ch
    return rules


def _declare(rules, selectors, decl):
    if not selectors or ":" not in decl:
        return
    prop, value = decl.split(":", 1)
    prop, value = prop.strip().lower(), value.strip().lower()
    if not re.fullmatch(r"[a-z-]+", prop):
        return
    for sel in selectors:
        last = sel.split()[-1] if sel.split() else ""
        if re.search(r":(hover|focus|active|last-child|first-child|nth|not|before|after)|deep\(", last):
            continue
        for cls in re.findall(r"\.([A-Za-z_][\w-]*)", last)[-1:]:
            rules.setdefault(cls, {})[prop] = value


class Sfc:
    """One parsed .vue file: template tree, class rules, and its imported .vue components."""

    def __init__(self, f):
        self.file = f
        self.root, self.rules, self.imports = None, {}, {}
        for kind, attrs, start, end in blocks(f.lines):
            if kind == "template" and self.root is None:
                self.root = parse_template(f.lines, start, end)
            elif kind == "style":
                for cls, decls in parse_style("\n".join(f.lines[start:end])).items():
                    self.rules.setdefault(cls, {}).update(decls)
            elif kind == "script":
                for m in IMPORT.finditer("\n".join(f.lines[start:end])):
                    self.imports[m.group(1).lower()] = m.group(2)
                    self.imports[_kebab(m.group(1))] = m.group(2)

    def props(self, node):
        out = {}
        for cls in node.classes:
            out.update(self.rules.get(cls, {}))
            for rx, (k, v) in UTILITY:
                if rx.match(cls):
                    out.setdefault(k, v)
        out.update(node.style)
        if "background-color" in out:
            out.setdefault("background", out["background-color"])
        if "overflow" in out:
            out.setdefault("overflow-y", out["overflow"].split()[-1])
        if node.attrs.get("max-height") or node.attrs.get(":max-height"):
            out.setdefault("max-height", "set")
        return out


def _kebab(name):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", name).lower()


def is_vscroll(sfc, node):
    if node.tag in SCROLL_TAGS:
        return True
    p = sfc.props(node)
    return p.get("overflow-y") in ("auto", "scroll")


def is_header(sfc, node):
    """A row of column titles: not repeated, has a background or is sticky, and holds 2+ cells."""
    if any(a in node.attrs for a in ("v-for", "v-if")) and "v-for" in node.attrs:
        return False
    p = sfc.props(node)
    bg = p.get("background", "")
    painted = bool(bg) and not re.match(r"(transparent|none|inherit|initial|unset|#fff\b|#ffffff|white)", bg)
    sticky = p.get("position") == "sticky"
    cells = [c for c in node.children if c.tag not in SKIP_CHILD]
    # Column titles are text cells; a block of nested panels (progress bar, info rows) is not a header.
    nested = [c for c in cells if any(g.tag not in INLINE for g in c.children)]
    return (painted or sticky) and len(cells) >= 2 and len(nested) * 2 < len(cells)


def first_rows(node, depth=2):
    """Element children in order, looking through wrappers such as NSpin, up to `depth` levels."""
    out = []
    for c in node.children:
        if c.tag in ("nspin", "n-spin", "transition") and depth:
            out += first_rows(c, depth - 1)
        elif c.tag not in ("nempty", "n-empty"):
            out.append(c)
    return out


def walk_nodes(node):
    for c in node.children:
        yield c
        yield from walk_nodes(c)


def label(node):
    return "<%s%s>" % (node.tag, " ." + node.classes[0] if node.classes else "")
