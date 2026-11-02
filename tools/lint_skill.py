#!/usr/bin/env python3
"""Lint SKILL.md files for rules that `claude plugin validate --strict` does not check.

Usage:
    python3 tools/lint_skill.py [--strict] [SKILL.md or skill directory ...]

With no paths, lints skills/*/SKILL.md under the repository root.
Prints one line per finding as `path:line: level: message`.
Exits 1 when there is an error, or a warning under --strict.
Standard library only (Python 3.9+).
"""
import argparse
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Frontmatter fields Claude Code reads (code.claude.com/docs/en/skills, frontmatter reference).
# Claude Code silently ignores any other field, so a typo would go unnoticed.
KNOWN_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
    "metadata", "license", "compatibility",
}
BOOLEAN_FIELDS = {"disable-model-invocation", "user-invocable", "background"}
BOOLEAN_VALUES = {"true", "false", "yes", "no", "on", "off", "1", "0"}
ENUM_FIELDS = {
    "context": {"fork"},
    "effort": {"low", "medium", "high", "xhigh", "max"},
    "shell": {"bash", "powershell"},
}
RESERVED_WORDS = ("anthropic", "claude")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024      # Agent Skills spec
MAX_LISTING = 1536          # Claude Code truncates description + when_to_use here
MAX_BODY_LINES = 500
COMPACT_TOKENS = 5000       # only this much of a skill is re-attached after compaction
FIRST_PERSON = re.compile(r"^(I|I'm|We|We're|You|You're|My|Our|Your)\b|^(我|你|您|咱)")
SKILL_DIR_REF = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([^\s`'\")*]+)")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")
TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$")


class Finding:
    def __init__(self, path, line, level, message):
        self.path, self.line, self.level, self.message = path, line, level, message

    def __str__(self):
        return "%s:%d: %s: %s" % (self.path, self.line, self.level, self.message)


def unquote(value):
    """Return a YAML flow scalar as text; quoted forms keep their content."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
        return re.sub(r"\\(.)", lambda m: escapes.get(m.group(1), m.group(0)), value[1:-1])
    if value.startswith("#"):
        return ""
    return re.sub(r"\s+#.*$", "", value)


def parse_frontmatter(lines):
    """Parse the top level of a simple YAML mapping.

    Returns (fields, problems). fields maps key -> (line number, value), where value is
    a string for scalars and block scalars, a list for flow or block lists, and the raw
    indented text for nested mappings. problems lists (line number, message).
    """
    fields, problems = {}, []
    i = 0
    while i < len(lines):
        number, text = i + 2, lines[i]   # +2: line 1 is the opening ---
        i += 1
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        match = TOP_KEY.match(text)
        if not match or text[0].isspace():
            problems.append((number, "cannot parse frontmatter line: %r" % text))
            continue
        key, raw = match.group(1), (match.group(2) or "").strip()
        block = []
        while i < len(lines) and (not lines[i].strip() or lines[i][0].isspace() or lines[i].startswith("- ")):
            block.append(lines[i])
            i += 1
        while block and not block[-1].strip():
            block.pop()
        if raw[:1] in ("|", ">"):
            parts = [b.strip() for b in block]
            value = ("\n" if raw[0] == "|" else " ").join(parts).strip()
        elif raw.startswith("["):
            value = [unquote(v) for v in raw.strip("[]").split(",") if v.strip()]
        elif raw:
            value = unquote(" ".join([raw] + [b.strip() for b in block]))
        elif block and all(b.strip().startswith("- ") for b in block if b.strip()):
            value = [unquote(b.strip()[2:]) for b in block if b.strip()]
        else:
            value = "\n".join(block)
        if key in fields:
            problems.append((number, "duplicate field %r" % key))
        fields[key] = (number, value)
    return fields, problems


def estimate_tokens(text):
    cjk = len(CJK.findall(text))
    return cjk + (len(text) - cjk) // 4


def lint_skill(skill_md):
    """Return the findings for one SKILL.md file."""
    path = pathlib.Path(skill_md)
    shown = path.resolve()
    try:
        shown = shown.relative_to(REPO_ROOT)
    except ValueError:
        pass
    findings = []

    def add(line, level, message):
        findings.append(Finding(shown, line, level, message))

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        add(1, "error", "frontmatter must open with --- on line 1, otherwise Claude Code reads no fields")
        return findings
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].rstrip() == "---")
    except StopIteration:
        add(1, "error", "frontmatter has no closing ---")
        return findings
    fields, problems = parse_frontmatter(lines[1:close])
    for number, message in problems:
        add(number, "error", message)

    for key, (number, _) in fields.items():
        if key not in KNOWN_FIELDS:
            add(number, "error", "unknown field %r; Claude Code ignores it without an error" % key)
    for key in BOOLEAN_FIELDS & fields.keys():
        number, value = fields[key]
        if not isinstance(value, str) or value.lower() not in BOOLEAN_VALUES:
            add(number, "error", "%s must be a boolean, got %r" % (key, value))
    for key in ENUM_FIELDS.keys() & fields.keys():
        number, value = fields[key]
        if value not in ENUM_FIELDS[key]:
            add(number, "error", "%s must be one of %s, got %r" % (key, sorted(ENUM_FIELDS[key]), value))

    dir_name = path.resolve().parent.name
    if "name" not in fields:
        add(1, "error", "name is missing; write it out and make it equal to the directory name %r" % dir_name)
    else:
        number, name = fields["name"]
        name = name if isinstance(name, str) else ""
        if not NAME_RE.match(name):
            add(number, "error", "name %r must be lowercase letters, digits and single hyphens" % name)
        if len(name) > MAX_NAME:
            add(number, "error", "name is %d characters, the limit is %d" % (len(name), MAX_NAME))
        if name != dir_name:
            add(number, "error", "name %r differs from its directory %r" % (name, dir_name))
        for word in RESERVED_WORDS:
            if word in name:
                add(number, "error", "name contains the reserved word %r" % word)

    if "description" not in fields or not fields["description"][1]:
        add(1, "error", "description is missing; Claude decides when to use the skill from it")
    else:
        number, description = fields["description"]
        description = description if isinstance(description, str) else " ".join(description)
        if len(description) > MAX_DESCRIPTION:
            add(number, "error", "description is %d characters, the limit is %d" % (len(description), MAX_DESCRIPTION))
        if "<" in description or ">" in description:
            add(number, "error", "description must not contain angle brackets")
        if FIRST_PERSON.match(description):
            add(number, "warning", "description should be written in the third person")
        when = fields.get("when_to_use", (0, ""))[1]
        listing = len(description) + len(when if isinstance(when, str) else " ".join(when))
        if listing > MAX_LISTING:
            add(number, "warning", "description + when_to_use is %d characters; the skill listing cuts it at %d" % (listing, MAX_LISTING))
    if "argument-hint" not in fields:
        add(1, "warning", "argument-hint is missing; this project's skills set one")

    body = lines[close + 1:]
    while body and not body[-1].strip():
        body.pop()
    if len(body) > MAX_BODY_LINES:
        add(close + 2, "error", "body is %d lines, keep it under %d and move detail to references/" % (len(body), MAX_BODY_LINES))
    tokens = estimate_tokens(text)
    if tokens > COMPACT_TOKENS:
        add(1, "warning", "about %d tokens; only the first %d are re-attached after compaction, so keep the rules first" % (tokens, COMPACT_TOKENS))

    skill_dir = path.resolve().parent
    allowed = fields.get("allowed-tools", (1, ""))
    allowed_text = allowed[1] if isinstance(allowed[1], str) else " ".join(allowed[1])
    for number, chunk in [(allowed[0], allowed_text)] + [(close + 2 + i, l) for i, l in enumerate(body)]:
        for ref in SKILL_DIR_REF.findall(chunk):
            if not (skill_dir / ref).exists():
                add(number, "error", "${CLAUDE_SKILL_DIR}/%s does not exist" % ref)
    in_fence = False
    for i, line in enumerate(body):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in MD_LINK.findall(line):
            if re.match(r"^[a-z][a-z0-9+.-]*:|^#", target):
                continue
            target = target.split("#", 1)[0]
            if target and not (skill_dir / target).exists():
                add(close + 2 + i, "error", "link target %s does not exist" % target)
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="*", help="SKILL.md files or skill directories")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)
    targets = []
    for p in args.paths or sorted(str(p) for p in (REPO_ROOT / "skills").glob("*/SKILL.md")):
        p = pathlib.Path(p)
        targets.append(p / "SKILL.md" if p.is_dir() else p)
    if not targets:
        print("no SKILL.md found", file=sys.stderr)
        return 1
    findings = []
    for target in targets:
        if not target.exists():
            findings.append(Finding(target, 1, "error", "file not found"))
            continue
        findings.extend(lint_skill(target))
    for finding in findings:
        print(finding)
    failing = [f for f in findings if f.level == "error" or args.strict]
    print("%d skill(s), %d error(s), %d warning(s)" % (
        len(targets), sum(f.level == "error" for f in findings), sum(f.level == "warning" for f in findings)))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
