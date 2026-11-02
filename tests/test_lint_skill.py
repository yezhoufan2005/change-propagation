import pathlib
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import lint_skill  # noqa: E402

GOOD = """\
---
name: demo-skill
description: Finds things that need the same change. Use when one object is fixed and look-alikes exist.
argument-hint: "[change]"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *)
---

# demo

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py scan`. See [ledger](references/ledger.md).
"""


class LintSkillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, text, dir_name="demo-skill", files=("scripts/run.py", "references/ledger.md")):
        skill_dir = self.root / dir_name
        for f in files:
            (skill_dir / f).parent.mkdir(parents=True, exist_ok=True)
            (skill_dir / f).write_text("x\n", encoding="utf-8")
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / "SKILL.md"
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return lint_skill.lint_skill(path)

    def messages(self, findings, level=None):
        return [f.message for f in findings if level is None or f.level == level]

    def assertFinds(self, findings, fragment, level="error"):
        hits = [m for m in self.messages(findings, level) if fragment in m]
        self.assertTrue(hits, "no %s containing %r in %s" % (level, fragment, self.messages(findings)))

    def test_good_skill_is_clean(self):
        self.assertEqual(self.messages(self.make(GOOD)), [])

    def test_repo_skill_is_clean(self):
        repo_skill = lint_skill.REPO_ROOT / "skills" / "change-propagation" / "SKILL.md"
        self.assertEqual([str(f) for f in lint_skill.lint_skill(repo_skill) if f.level == "error"], [])

    def test_name_must_match_directory(self):
        self.assertFinds(self.make(GOOD, dir_name="other-dir"), "differs from its directory")

    def test_name_must_be_kebab_case(self):
        findings = self.make(GOOD.replace("name: demo-skill", "name: Demo_Skill"))
        self.assertFinds(findings, "lowercase letters")

    def test_name_too_long(self):
        long_name = "a" * 65
        self.assertFinds(self.make(GOOD.replace("demo-skill", long_name), dir_name=long_name), "limit is 64")

    def test_reserved_word(self):
        self.assertFinds(self.make(GOOD.replace("demo-skill", "claude-helper"), dir_name="claude-helper"), "reserved word")

    def test_missing_name(self):
        self.assertFinds(self.make(GOOD.replace("name: demo-skill\n", "")), "name is missing")

    def test_angle_brackets_in_description(self):
        self.assertFinds(self.make(GOOD.replace("look-alikes exist", "a <Modal> exists")), "angle brackets")

    def test_description_too_long(self):
        self.assertFinds(self.make(GOOD.replace("look-alikes exist.", "x" * 1100)), "the limit is 1024")

    def test_first_person_description_warns(self):
        findings = self.make(GOOD.replace("description: Finds", "description: I find"))
        self.assertFinds(findings, "third person", level="warning")

    def test_block_scalar_description(self):
        text = GOOD.replace(
            "description: Finds things that need the same change. Use when one object is fixed and look-alikes exist.",
            "description: >\n  Finds things that need\n  the same change.")
        self.assertEqual(self.messages(self.make(text), "error"), [])

    def test_unknown_field(self):
        self.assertFinds(self.make(GOOD.replace("argument-hint", "argument_hint")), "unknown field 'argument_hint'")

    def test_bad_boolean(self):
        text = GOOD.replace("argument-hint", "disable-model-invocation: sometimes\nargument-hint")
        self.assertFinds(self.make(text), "must be a boolean")

    def test_frontmatter_must_start_on_line_one(self):
        self.assertFinds(self.make("\n" + GOOD), "line 1")

    def test_missing_script(self):
        self.assertFinds(self.make(GOOD, files=("references/ledger.md",)), "scripts/run.py does not exist")

    def test_missing_link_target(self):
        self.assertFinds(self.make(GOOD, files=("scripts/run.py",)), "references/ledger.md does not exist")

    def test_links_inside_code_fence_are_ignored(self):
        text = GOOD + "\n```\n[x](missing.md)\n```\n"
        self.assertEqual(self.messages(self.make(text), "error"), [])

    def test_body_too_long(self):
        self.assertFinds(self.make(GOOD + "line\n" * 520), "under 500")

    def test_duplicate_field(self):
        self.assertFinds(self.make(GOOD.replace("argument-hint", "name: demo-skill\nargument-hint")), "duplicate field")

    def test_strict_exit_code(self):
        path = self.root / "demo-skill" / "SKILL.md"
        self.make(GOOD.replace('argument-hint: "[change]"\n', ""))
        self.assertEqual(lint_skill.main([str(path)]), 0)
        self.assertEqual(lint_skill.main(["--strict", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
