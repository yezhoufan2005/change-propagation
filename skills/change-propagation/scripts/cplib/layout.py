"""Layout channel: Vue components with a given structure, whatever their names.

`header-in-scroll`: a column-title row (painted background or sticky, 2+ cells) that is the first
child of a vertical scroll container (overflow-y auto/scroll by style block, utility class or inline
style, or a library scrollbar component), so the scrollbar runs past the header. A header rendered by
a child component is followed one hop into that component. A library table inside a scroll container
is reported with a lower score, because its built-in header scrolls with it.

`--like FILE`: a feature card taken from an example component (tags, library components, imported
components, class words, style properties); other .vue files are ranked by how many features they
share. Use it for "all popups"-style requests whose members do not share a structure query yet.
"""
import os
import re

from . import sfc as S
from .channels import hit

LAYOUTS = ("header-in-scroll",)
STOP_WORDS = {"div", "span", "template", "slot", "p", "i", "a", "item", "row", "cell", "text", "title", "name",
              "wrapper", "container", "content", "body", "main", "flex", "items", "center", "justify", "between",
              "mb", "mt", "px", "py", "gap", "w", "h", "font", "text", "border", "rounded", "is", "active"}


def _child_header(sfc_obj, node, by_path, cache):
    """If `node` is a component tag imported from a .vue file whose root is a header, return that file."""
    f = _resolve(sfc_obj, node.tag, by_path)
    if f is None:
        return None
    child = cache.get(f.path) or cache.setdefault(f.path, S.Sfc(f))
    if child.root is None:
        return None
    roots = [c for c in child.root.children]
    if len(roots) == 1 and S.is_header(child, roots[0]):
        return f, roots[0]
    return None


def _resolve(sfc_obj, tag, by_path):
    target = sfc_obj.imports.get(tag)
    if not target:
        return None
    if target.startswith("@/"):
        root = sfc_obj.file.path.split("/src/")[0] if "/src/" in sfc_obj.file.path else ""
        return by_path.get(os.path.normpath(os.path.join(root, "src", target[2:])))
    if target.startswith("."):
        return by_path.get(os.path.normpath(os.path.join(os.path.dirname(sfc_obj.file.path), target)))
    return None


def _slot_in_scroll(child, slot_name):
    """The scroll container around <slot name=...> in a layout component, or None."""
    if child.root is None:
        return None
    for n in S.walk_nodes(child.root):
        if n.tag == "slot" and n.attrs.get("name", "default") == slot_name:
            p = n.parent
            while p is not None and p.tag != "#root":
                if S.is_vscroll(child, p):
                    return p
                p = p.parent
    return None


def tables_in_slot_scroll(sf, by_path, cache):
    """<Layout><template #list-view><NDataTable/></template></Layout> where the layout scrolls that slot."""
    out = []
    for node in S.walk_nodes(sf.root):
        if node.tag != "template":
            continue
        slot = next((k[1:] if k.startswith("#") else k.split(":", 1)[1] for k in node.attrs
                     if k.startswith("#") or k.startswith("v-slot:")), None)
        table = next((k for k in S.first_rows(node) if k.tag in S.TABLE_TAGS), None)
        if not slot or table is None or node.parent is None:
            continue
        f = _resolve(sf, node.parent.tag, by_path)
        if f is None:
            continue
        child = cache.get(f.path) or cache.setdefault(f.path, S.Sfc(f))
        box = _slot_in_scroll(child, slot)
        if box is not None:
            out.append((table, f, box))
    return out


def header_in_scroll(files):
    vue = [f for f in files if f.path.endswith(".vue")]
    by_path = {os.path.normpath(f.path): f for f in vue}
    cache, out = {}, []
    for f in vue:
        if not re.search(r"overflow|scroll|<template\s+(#|v-slot)", f.text, re.I):
            continue
        sf = cache.get(f.path) or cache.setdefault(f.path, S.Sfc(f))
        if sf.root is None:
            continue
        for table, lf, box in tables_in_slot_scroll(sf, by_path, cache):
            why = "表格组件 %s 放进 %s 的插槽，插槽外层 %s 会滚动，表头跟着滚动" % (table.tag, lf.path.rsplit("/", 2)[-2], S.label(box))
            out.append(_hit(f, table.line, 45, why))
        for node in S.walk_nodes(sf.root):
            if not S.is_vscroll(sf, node):
                continue
            kids = S.first_rows(node)
            if not kids:
                continue
            first = kids[0]
            # The rows must follow the header directly: the next element repeats, or holds the repeat.
            nxt = kids[1] if len(kids) > 1 else None
            rows = [] if nxt is None else ([nxt] if "v-for" in nxt.attrs else
                                           [g for g in nxt.children if "v-for" in g.attrs])
            repeated = bool(rows)
            # A header lines up with the rows below it: about as many cells as one row.
            ncells = len([c for c in first.children if c.tag not in S.SKIP_CHILD])
            aligned = any(abs(len([c for c in r.children if c.tag not in S.SKIP_CHILD]) - ncells) <= 1 or
                          any("v-for" in c.attrs for c in first.children) for r in rows)
            if S.is_header(sf, first) and repeated and aligned:
                why = "顶栏 %s 是滚动容器 %s 的第一个子元素，滚动条会盖到顶栏" % (S.label(first), S.label(node))
                out.append(_hit(f, first.line, 70, why))
                continue
            child = _child_header(sf, first, by_path, cache) if repeated else None
            if child:
                cf, cnode = child
                why = "滚动容器 %s 里第一个子组件 %s 渲染顶栏（%s:%d）" % (S.label(node), first.tag, cf.path, cnode.line)
                out.append(_hit(f, first.line, 70, why))
                out.append(_hit(cf, cnode.line, 55, "被 %s 用在滚动容器里的顶栏组件" % f.path))
                continue
            table = next((k for k in kids if k.tag in S.TABLE_TAGS), None)
            if table is not None:
                why = "表格组件 %s 包在滚动容器 %s 里，表头跟着滚动" % (table.tag, S.label(node))
                out.append(_hit(f, table.line, 50, why))
                continue
            # A table a few wrappers below a scrolling page box also scrolls its header away.
            for t in S.walk_nodes(node):
                if t.tag in S.TABLE_TAGS and _depth_below(t, node) <= NEAR_DEPTH and not _has_scroll_between(sf, t, node):
                    why = "表格组件 %s 在滚动容器 %s 下 %d 层，表头会随页面滚走" % (t.tag, S.label(node), _depth_below(t, node))
                    out.append(_hit(f, t.line, 40, why))
    return out


NEAR_DEPTH = 3


def _depth_below(node, ancestor):
    d, p = 0, node
    while p is not None and p is not ancestor:
        p, d = p.parent, d + 1
    return d


def _has_scroll_between(sf, node, ancestor):
    p = node.parent
    while p is not None and p is not ancestor:
        if S.is_vscroll(sf, p):
            return True
        p = p.parent
    return False


def _hit(f, line, score, why):
    h = hit(f, line, "layout", score, why, "header-in-scroll", "")
    h["role"] = "structure"
    return h


CSS_DECL = re.compile(r"(position|overflow(?:-y)?|z-index|animation|transition|opacity|inset|transform|"
                      r"backdrop-filter|pointer-events)\s*:\s*([\w.#()-]+)", re.I)
API = re.compile(r"\b(createPortal|Teleport|v-model:show|onClickOutside|click-outside|keydown|Escape|aria-modal|"
                 r"role=.dialog.|mask|overlay|backdrop|dialog|modal|drawer|popup|popover|sheet|lightbox|layer)\b", re.I)
CLASS_ATTR = re.compile(r"""(?:class|className)\s*=\s*\{?\s*["'`]([^"'`]+)""")
SCRIPT_EXT = (".vue", ".tsx", ".jsx", ".ts", ".js")
STYLE_IMPORT = re.compile(r"""import\s+(?:[\w$]+\s+from\s+)?['"](\.{1,2}/[^'"]+\.(?:css|scss|less))['"]""")


def _with_styles(f, by_path):
    """The file's text plus the stylesheets it imports, since a component's layout often lives there."""
    text = f.text
    for m in STYLE_IMPORT.finditer(f.text):
        sheet = by_path.get(os.path.normpath(os.path.join(os.path.dirname(f.path), m.group(1))))
        if sheet is not None:
            text += "\n" + sheet.text
    return text


def features(f, by_path=None):
    """Feature card of one file: library and custom tags, words from class names and popup-ish APIs,
    layout CSS (position, overflow, z-index, animation...), imports. Words are shared between class
    names and API words, so `.modal-mask` and `mask` count once."""
    text, feats = (_with_styles(f, by_path) if by_path else f.text), set()
    if f.path.endswith(".vue"):
        sf = S.Sfc(f)
        if sf.root is not None:
            for n in S.walk_nodes(sf.root):
                if "-" in n.tag or (n.tag.startswith("n") and len(n.tag) > 2 and n.tag not in ("nav",)):
                    feats.add("tag:" + n.tag)
        feats |= {"import:" + name for name in sf.imports if "-" not in name}
    for m in re.finditer(r"<([A-Z][\w.]*)", text):
        feats.add("tag:" + m.group(1).lower())
    for m in CLASS_ATTR.finditer(text):
        for c in m.group(1).split():
            for w in re.split(r"[-_]+", c.lower()):
                if len(w) > 2 and w not in STOP_WORDS and not w.isdigit():
                    feats.add("word:" + w)
    for m in re.finditer(r"\.([a-z][\w-]*)\s*[{,]", text):
        for w in re.split(r"[-_]+", m.group(1).lower()):
            if len(w) > 2 and w not in STOP_WORDS:
                feats.add("word:" + w)
    for m in CSS_DECL.finditer(text):
        feats.add("css:%s:%s" % (m.group(1).lower(), re.sub(r"\d+(\.\d+)?", "N", m.group(2).lower())))
    for m in API.finditer(text):
        word = m.group(1).lower()
        feats.add(("word:" if word.isalpha() and word not in ("createportal", "teleport", "keydown", "escape")
                   else "api:") + word)
    return feats


def like_channel(files, example_paths, top=40):
    wanted = {os.path.normpath(p) for p in example_paths}
    examples = [f for f in files if os.path.normpath(f.path) in wanted]
    if not examples:
        raise ValueError("--like 的样例不在搜索的根目录里：%s" % ",".join(example_paths))
    by_path = {os.path.normpath(f.path): f for f in files}
    card = set()
    for e in examples:
        card |= features(e, by_path)
    pool = [f for f in files if f.path.endswith(SCRIPT_EXT) and f not in examples and f.stack == "frontend"
            and f.layer == "frontend"]
    feats = {f.path: features(f, by_path) & card for f in pool}
    df = {}
    for fs in feats.values():
        for x in fs:
            df[x] = df.get(x, 0) + 1
    n = max(1, len(pool))
    scored = []
    for f in pool:
        shared = {x for x in feats[f.path] if df[x] <= max(3, n // 3)}   # drop features most files have
        if len(shared) < 2:
            continue
        weight = sum(1.0 / (1 + df[x]) ** 0.5 for x in shared)
        scored.append((weight, f, shared))
    scored.sort(key=lambda t: -t[0])
    out = []
    for weight, f, shared in scored[:top]:
        names = sorted(shared, key=lambda x: df[x])[:5]
        why = "和样例共有 %d 个特征：%s" % (len(shared), "、".join(x.split(":", 1)[1] for x in names))
        h = hit(f, _feature_line(f, names), "like", min(70, 30 + int(weight * 8)), why, "like", "")
        h["role"] = "feature"
        out.append(h)
    return out


def _feature_line(f, feats):
    """First line of the file that shows one of the rarest shared features, so `show` lands on it."""
    for x in feats:
        word = x.split(":")[1]
        rx = re.compile(re.escape(word).replace("N", r"\d"), re.I)
        for i, line in enumerate(f.lines, 1):
            if rx.search(line):
                return i
    return 1
