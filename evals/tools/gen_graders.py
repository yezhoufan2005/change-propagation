#!/usr/bin/env python3
"""Generate graders/*.md for an eval case from its sites.json.

Usage: python3 tools/gen_graders.py evals/<group>/<case> [...]

sites.json:
  {"sites": [{"id": "reset-form", "tier": "direct|coupled|review|exclude",
              "files": [{"path": "web/x.ts", "gone": "regex", "present": "regex", "keep": "regex"}],
              "mention": ["literal", ...]}],
   "extra": [{"name": "...", "weight": 1, "body": "llm criteria"}]}

Per file entry:
  gone     -> grader edit-<id>[--n]: the original text is no longer in the file (edited)
  present  -> grader edit-<id>[--n]: the new text is in the file (edited correctly)
  keep     -> grader keep-<id>[--n]: the original text is still in the file (untouched)
Every site except tier "direct" and "exclude" also gets say-<id>: the final message mentions it.
Every case also gets used-skill: the change-propagation skill was invoked at least once.

Direct and exclude graders carry weight 1 and make up the case score. The remaining
graders only record what happened, so they get weight 0.001 and tools/summarize.py reads them.
Standard library only.
"""
import json
import pathlib
import re
import sys

INFO_WEIGHT = "0.001"
SKILL_MATCH = r'"skill"\s*:\s*"(?:[\w-]+:)?change-propagation"'


def yq(text):
    return "'" + text.replace("'", "''") + "'"


def write(path, frontmatter, body=""):
    lines = ["---"] + ["%s: %s" % kv for kv in frontmatter] + ["---"]
    path.write_text("\n".join(lines) + "\n" + (("\n" + body.strip() + "\n") if body else ""), encoding="utf-8")


def file_grader(path, rel, pattern, not_contains, weight):
    fm = [("type", "regex"), ("weight", weight), ("flags", "i"),
          ("target", "{ source: file, path: %s }" % yq(rel)), ("pattern", yq(pattern))]
    if not_contains:
        fm.append(("match", "not_contains"))
    write(path, fm)


def generate(case_dir):
    case_dir = pathlib.Path(case_dir)
    spec = json.loads((case_dir / "sites.json").read_text(encoding="utf-8"))
    out = case_dir / "graders"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.md"):
        old.unlink()
    for site in spec["sites"]:
        sid, tier = site["id"], site["tier"]
        weight = "1" if tier in ("direct", "exclude") else INFO_WEIGHT
        for n, f in enumerate(site["files"], 1):
            suffix = "--%d" % n if len(site["files"]) > 1 else ""
            if "keep" in f:
                file_grader(out / ("keep-%s%s.md" % (sid, suffix)), f["path"], f["keep"], False, weight)
            if "gone" in f:
                file_grader(out / ("edit-%s%s.md" % (sid, suffix)), f["path"], f["gone"], True, weight)
            if "present" in f:
                file_grader(out / ("edit-%s%s.md" % (sid, suffix + ("p" if "gone" in f else ""))), f["path"], f["present"], False, weight)
        if tier not in ("direct", "exclude") and site.get("mention"):
            pattern = "|".join(re.escape(m) for m in site["mention"])
            write(out / ("say-%s.md" % sid), [("type", "regex"), ("weight", INFO_WEIGHT), ("flags", "i"), ("pattern", yq(pattern))])
    write(out / "used-skill.md", [("type", "tool_used"), ("weight", INFO_WEIGHT), ("tool", "Skill"),
                                  ("input_match", yq(SKILL_MATCH))])
    for extra in spec.get("extra", []):
        write(out / ("%s.md" % extra["name"]), [("type", "llm"), ("weight", str(extra.get("weight", 1)))], extra["body"])
    return len(list(out.glob("*.md")))


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print("%s: %d graders" % (arg, generate(arg)))
