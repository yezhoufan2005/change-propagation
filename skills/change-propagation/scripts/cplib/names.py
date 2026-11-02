"""Identifier splitting and spelling variants.

`AGVTaskID` -> ['agv', 'task', 'id'] -> agvTaskId, AgvTaskId, AGVTaskID, agv_task_id,
agv-task-id, AGV_TASK_ID. One regex matches all of them, ignoring case, '-', '_' and '.'.
"""
import re

WORD_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
# golint's common initialisms, plus a few seen in IoT and AGV code
INITIALISMS = set(
    "acl agv api ascii cpu css dns eof guid html http https id ip json lhs mqtt qps ram rhs rpc "
    "sla smtp sql ssh tcp tls ttl udp ui uid uuid uri url utf8 vm ws xml xmpp xsrf xss".split())
IDENT_CHARS = "A-Za-z0-9_$"


def split_words(name):
    return [w.lower() for w in WORD_RE.findall(name)]


def fold(name):
    """Case-, '-'-, '_'- and '.'-insensitive form: AGV_Task-id -> agvtaskid."""
    return re.sub(r"[-_.\s]", "", name).lower()


def variants(name):
    words = split_words(name)
    if not words:
        return {name}
    cap = [w.capitalize() for w in words]
    init = [w.upper() if w in INITIALISMS else c for w, c in zip(words, cap)]
    out = {
        words[0] + "".join(cap[1:]), "".join(cap), "".join(init), words[0] + "".join(init[1:]),
        "_".join(words), "-".join(words), "_".join(words).upper(),
    }
    out.add(name)
    return out


def is_identifier_like(text):
    return bool(re.fullmatch(r"[A-Za-z_$][\w$-]*", text))


def name_regex(name):
    """Regex for every spelling of `name`, bounded so `id` does not match inside `width`.

    Multi-word names allow an optional separator between words; single-word names are matched
    as whole tokens only.
    """
    words = split_words(name)
    if not words or not is_identifier_like(name):
        return re.compile(r"(?<![%s])%s(?![%s])" % (IDENT_CHARS, re.escape(name), IDENT_CHARS))
    body = r"[-_.]?".join(re.escape(w) for w in words)
    # A word boundary inside camelCase is an upper-case letter, so allow a lower-case letter
    # before the match only when the match starts with upper case (onLastVisitTime).
    return re.compile(r"(?:(?<![%s])|(?<=[a-z0-9])(?=[A-Z]))(?i:%s)(?![a-z0-9])" % (IDENT_CHARS, body))


def spelling(match_text, seed):
    """'exact' when the text is spelled like the seed, 'variant' otherwise."""
    return "exact" if match_text == seed else "variant"
