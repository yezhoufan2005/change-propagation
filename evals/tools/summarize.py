#!/usr/bin/env python3
"""Summarize a `claude plugin eval --json` result per site.

Usage: python3 -I evals/tools/summarize.py RESULTS.json [--md OUT.md]

Reads each case's sites.json (case dir is relative to suite.root) and maps the grader
names written by gen_graders.py back to sites:
  direct/coupled/review: edited | mentioned | missed
  exclude:               intact | touched
Each arm (with, without) is reported separately; used-skill counts Skill invocations.
A file entry counts as edited when every edit- grader for it passed (gone and present);
a site counts as edited when any of its file entries did. Standard library only.
"""
import json
import pathlib
import sys


def site_status(site, passed):
    files = site["files"]
    multi = len(files) > 1
    edited, intact = [], []
    for n, f in enumerate(files, 1):
        suffix = "--%d" % n if multi else ""
        names = []
        if "gone" in f:
            names.append("edit-%s%s" % (site["id"], suffix))
        if "present" in f:
            names.append("edit-%s%s" % (site["id"], suffix + ("p" if "gone" in f else "")))
        if names:
            edited.append(all(passed.get(x) for x in names))
        if "keep" in f:
            intact.append(bool(passed.get("keep-%s%s" % (site["id"], suffix))))
    if site["tier"] == "exclude":
        return "intact" if all(intact) else "touched"
    if any(edited):
        return "edited"
    if passed.get("say-%s" % site["id"]):
        return "mentioned"
    return "missed"


ARM_ZH = {"with": "装了插件", "without": "不装插件"}


def summarize_arm(spec, runs):
    """Lines for one arm of one case."""
    ok = [r for r in runs if not r.get("error")]
    out = ["%d 次运行，%d 次出错" % (len(runs), len(runs) - len(ok))]
    if not ok:
        return out + ["全部运行出错：%s" % [r.get("error") for r in runs]]
    statuses = {s["id"]: [] for s in spec["sites"]}
    core, cost, turns, used, extras = [], 0.0, 0, [], {}
    scored = [s for s in spec["sites"] if s["tier"] in ("direct", "exclude")]
    for r in ok:
        passed = {g["name"]: g["passed"] for g in r["graders"]}
        for s in spec["sites"]:
            statuses[s["id"]].append(site_status(s, passed))
        core.append(sum(statuses[s["id"]][-1] in ("edited", "intact") for s in scored) / len(scored) if scored else 0.0)
        cost += r["costUsd"]
        turns += r["turns"]
        if "used-skill" in passed:
            used.append(bool(passed["used-skill"]))
        for e in spec.get("extra", []):
            extras.setdefault(e["name"], []).append(bool(passed.get(e["name"])))
    n = len(ok)
    out.append("核心分 %.2f（direct 已改、exclude 未误改的站点比例），平均 %d 轮，平均 $%.2f/次" % (sum(core) / n, turns / n, cost / n))
    if used:
        out.append("调用了 skill：%d/%d 次" % (sum(used), len(used)))
    kinds = ["edited", "mentioned", "missed", "intact", "touched"]
    out += ["", "| 站点 | 层级 | " + " | ".join(kinds) + " |", "|---|---|---|---|---|---|---|"]
    for s in spec["sites"]:
        st = statuses[s["id"]]
        out.append("| %s | %s | %s |" % (s["id"], s["tier"], " | ".join(str(st.count(k)) for k in kinds)))
    for name, vals in extras.items():
        out += ["", "llm 检查 `%s`：%d/%d 通过" % (name, sum(vals), len(vals))]
    out.append("")
    for tier in ("direct", "coupled", "review", "exclude"):
        ids = [s["id"] for s in spec["sites"] if s["tier"] == tier]
        if not ids:
            continue
        total = len(ids) * n
        hit = sum(1 for i in ids for k in statuses[i] if k in (("intact",) if tier == "exclude" else ("edited",)))
        line = "- %s：%s %d/%d" % (tier, "未误改" if tier == "exclude" else "改了", hit, total)
        if tier in ("coupled", "review"):
            said = sum(1 for i in ids for k in statuses[i] if k == "mentioned")
            line += "，只提到 %d，漏掉 %d" % (said, total - hit - said)
        out.append(line)
    return out


def main(argv):
    if not argv:
        sys.exit(__doc__)
    data = json.loads(pathlib.Path(argv[0]).read_text(encoding="utf-8"))
    root = pathlib.Path(data["suite"]["root"])
    out = ["# 评测汇总（%s，ablation=%s，model=%s）" % (data["startedAt"], data["suite"]["ablation"], data["suite"].get("modelOverride")), ""]
    for case in data["cases"]:
        spec = json.loads((root / case["dir"] / "sites.json").read_text(encoding="utf-8"))
        out += ["## %s" % case["name"], ""]
        for arm, runs in case["arms"].items():
            if len(case["arms"]) > 1:
                out += ["### %s" % ARM_ZH.get(arm, arm), ""]
            out += summarize_arm(spec, runs) + [""]
    text = "\n".join(out)
    if "--md" in argv:
        pathlib.Path(argv[argv.index("--md") + 1]).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
