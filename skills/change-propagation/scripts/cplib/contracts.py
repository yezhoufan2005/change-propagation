"""Contract channel: both ends of a JSON field, an MQTT topic or WebSocket path, and an i18n key.

Each hit gets a role (producer, consumer, schema, definition, use) and a side (frontend or
backend). A field spelled one way by the backend and read another way by the frontend is
flagged, because one of the two ends is wrong (last_visit_time written, lastVisitTime read).
"""
import re

from . import names
from .channels import hit

DYN = "\x00"
TOPIC_LITERAL = re.compile(r"""(["'`])((?:[A-Za-z0-9_+#%{}$:.\-]*/)+[A-Za-z0-9_+#%{}$:.\-]*)\1""")
I18N_KEY = re.compile(r"^[A-Za-z_][\w-]*(\.[A-Za-z_][\w-]*)+$")

FIELD_ROLES = [
    ("schema", re.compile(r"""json:"@K@[",]""")),
    ("schema", re.compile(r"""(?:alias|serialization_alias|validation_alias|db|gorm:"column)\s*[=:]\s*["']?@K@""")),
    ("producer", re.compile(r"""["']@K@["']\s*:|\[["']@K@["']\]\s*=""")),
    ("consumer", re.compile(r"""\[["']@K@["']\]|\.get\(\s*["']@K@["']""")),
    ("consumer", re.compile(r"""[\w$\])?]\??\.@K@(?![\w$])""")),
    ("schema", re.compile(r"""^\s*@K@\??\s*:\s*[\w'"\[{|<]""")),
    ("producer", re.compile(r"""(?<![\w$.])@K@\s*:""")),
]
MQTT_PUB = re.compile(r"\b(Publish|publish|emit|send)\w*\s*\(")
MQTT_SUB = re.compile(r"\b(Subscribe|subscribe|on|addListener|message_callback_add|AddRoute)\w*\s*\(")
I18N_USE = re.compile(r"""\b(\$?t|i18n\.t|\$t|tc|te|translate|gettext|_)\s*\(\s*["'`]@K@["'`]""")


def kind_of(key):
    if "/" in key:
        return "topic"
    if I18N_KEY.match(key):
        return "i18n"
    return "field"


def _topic_levels(s):
    s = re.sub(r"%[-+# 0]*\d*(?:\.\d+)?[sdvqxXfg]", DYN, s)
    s = re.sub(r"\$\{[^}]*\}|\{[^{}]*\}|^:\w+$", DYN, s)
    if s.startswith("$share/"):
        s = s.split("/", 2)[2] if s.count("/") >= 2 else s
    return [DYN if re.fullmatch(r":\w+", lv) else lv for lv in s.strip("/").split("/")]


def topics_compatible(a, b):
    """True when some concrete topic or path could match both, treating + # and placeholders as wild.

    '#' is only a wildcard as the last level (MQTT 4.7.1.2), so '#/components/x' is not a topic.
    At least two concrete levels (or all of them, if fewer) must be equal, so 'a/+' alone does not
    pair with every two-level path.
    """
    x, y = _topic_levels(a), _topic_levels(b)
    if "#" in x[:-1] or "#" in y[:-1]:
        return False
    same = sum(1 for p, q in zip(x, y) if p == q and p not in ("+", "#", DYN))
    concrete = min(sum(1 for lv in z if lv not in ("+", "#", DYN)) for z in (x, y))
    if same < min(2, concrete) or concrete == 0:
        return False
    for i in range(max(len(x), len(y))):
        p = x[i] if i < len(x) else None
        q = y[i] if i < len(y) else None
        if p == "#" or q == "#":
            return True
        if p is None or q is None:
            return False
        if p in ("+", DYN) or q in ("+", DYN) or p == q:
            continue
        return False
    return True


def _field_role(line, spelled):
    k = re.escape(spelled)
    for role, rx in FIELD_ROLES:
        if re.search(rx.pattern.replace("@K@", k), line):
            return role
    return "ref"


def field_channel(files, key):
    rx = names.name_regex(key)
    out = []
    for f in files:
        if not rx.search(f.text):
            continue
        for i, line in enumerate(f.lines, 1):
            for m in rx.finditer(line):
                role = _field_role(line, m.group(0))
                if role == "ref":
                    continue
                h = hit(f, i, "contract", 55, "字段 %s 的%s" % (m.group(0), ROLE_ZH[role]), key, m.group(0))
                h["role"] = role
                out.append(h)
                break
    _flag_spelling_mismatch(out)
    return out


ROLE_ZH = {"schema": "定义", "producer": "写入方", "consumer": "读取方", "definition": "定义", "use": "使用处",
           "publisher": "发布方", "subscriber": "订阅方"}


def _flag_spelling_mismatch(hits):
    """Frontend readers whose spelling no backend schema or producer uses, and the reverse."""
    sides = {"frontend": set(), "backend": set()}
    for h in hits:
        if h["role"] in ("schema", "producer") and h["stack"] in sides:
            sides[h["stack"]].add(h["match"])
    back = sides["backend"]
    if not back:
        return
    for h in hits:
        if h["stack"] == "frontend" and h["role"] == "consumer" and h["match"] not in back:
            h["score"] += 25
            h["why"] += "；后端只写 %s，这里读的是 %s" % ("/".join(sorted(back)), h["match"])
            h["mismatch"] = True


def topic_channel(files, key):
    out = []
    for f in files:
        if "/" not in f.text:
            continue
        for i, line in enumerate(f.lines, 1):
            for m in TOPIC_LITERAL.finditer(line):
                lit = m.group(2)
                if len(lit) < 3 or lit.startswith(("http", "./", "../", "@/", "~/")) or "." in lit.rsplit("/", 1)[-1]:
                    continue
                if not topics_compatible(lit, key):
                    continue
                role = "publisher" if MQTT_PUB.search(line) else "subscriber" if MQTT_SUB.search(line) else "ref"
                why = "topic 或路径 %s 与 %s 相容%s" % (lit, key, "，" + ROLE_ZH[role] if role != "ref" else "")
                h = hit(f, i, "contract", 60 if lit == key else 50, why, key, lit)
                h["role"] = role
                out.append(h)
                break
    return out


def i18n_channel(files, key):
    last = key.rsplit(".", 1)[-1]
    flat_def = re.compile(r"""["']%s["']\s*:""" % re.escape(key))
    nested_def = re.compile(r"""^\s*["']?%s["']?\s*:""" % re.escape(last))
    use = re.compile(I18N_USE.pattern.replace("@K@", re.escape(key)))
    out = []
    for f in files:
        has_flat = key in f.text
        if not has_flat and not (f.layer == "locale" and last in f.text):
            continue
        for i, line in enumerate(f.lines, 1):
            role = None
            if has_flat and flat_def.search(line):
                role = "definition"
            elif has_flat and use.search(line):
                role = "use"
            elif has_flat and key in line:
                role = "use"
            elif f.layer == "locale" and not has_flat and nested_def.search(line):
                role = "definition"
            if role:
                h = hit(f, i, "contract", 60 if role == "definition" else 55,
                        "i18n key %s 的%s" % (key, ROLE_ZH[role]), key, key)
                h["role"] = role
                out.append(h)
    return out


def contract_channel(files, key):
    return {"topic": topic_channel, "i18n": i18n_channel, "field": field_channel}[kind_of(key)](files, key)
