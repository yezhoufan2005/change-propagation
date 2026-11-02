#!/usr/bin/env python3
"""Check cplib/gitread.py against the git binary on a real repository.

Usage: python3 -I gitread_check.py REPO [--seeds 40]

Compares, for the repository at REPO (a work tree):
  - the HEAD file list with `git ls-tree -r HEAD`;
  - for --seeds files (the most changed ones and a spread of others), the changed-file sets of
    `git log --no-merges --no-renames --full-diff --name-only -n 3000 -- FILE`;
  - after editing, deleting and adding files in a throwaway clone, the changed files and the removed
    and added lines of `git diff --no-renames -U0 HEAD`.
Runs git and reads the repository; writes only the throwaway clone under the system temp dir.
"""
import argparse
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                "skills", "change-propagation", "scripts"))
from cplib import gitread  # noqa: E402

LOG_COMMITS, MAX_FILES = 3000, 30


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "core.quotePath=false"] + list(args), stdout=subprocess.PIPE,
                          check=True).stdout.decode("utf-8", "replace")


def git_log(repo, path):
    out = git(repo, "log", "--no-merges", "--no-renames", "--full-diff", "--name-only", "--format=tformat:@@",
              "-n", str(LOG_COMMITS), "--", path)
    return [set(filter(None, c.split("\n"))) for c in out.split("@@")[1:]]


def capped(sets):
    """Sets larger than MAX_FILES only count as 'too big', as cp.py treats them."""
    return [frozenset(s) if len(s) <= MAX_FILES else "big" for s in sets]


def git_hunks(repo):
    out = git(repo, "diff", "--no-color", "--no-renames", "-U0", "HEAD")
    rem, add = collections.Counter(), collections.Counter()
    path, old, r, a = None, None, 0, 0
    for line in out.split("\n"):
        if r and line.startswith("-"):
            rem[(path, line[1:].strip())] += 1
            r -= 1
        elif a and line.startswith("+"):
            add[(path, line[1:].strip())] += 1
            a -= 1
        elif line.startswith("--- "):
            old = line[6:] if line.startswith("--- a/") else None
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            path = path or ("DELETED:" + old if old else None)
        elif line.startswith("@@"):
            r, a = hunk_sizes(line)
    return rem, add


def hunk_sizes(line):
    m = gitread_hunk.match(line)
    return int(m.group(1) or 1), int(m.group(2) or 1)


gitread_hunk = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--log-only", action="store_true", help="skip the diff part (a clone without file contents)")
    a = ap.parse_args()
    top, gitdir = gitread.find_repo(a.repo)
    repo = gitread.Repo(gitdir)
    ok = True

    t = time.time()
    mine = {p for p in gitread.head_files(repo)}
    theirs = set(filter(None, git(top, "ls-tree", "-r", "--name-only", "HEAD").split("\n")))
    subs = {l.split("\t")[1] for l in git(top, "ls-tree", "-r", "HEAD").split("\n") if l.startswith("160000")}
    theirs -= subs
    print("HEAD files: gitread %d, git %d, same %s (%.1f s)" % (len(mine), len(theirs), mine == theirs, time.time() - t))
    ok &= mine == theirs

    counts = collections.Counter()
    for s in capped(git_log(top, ".")):
        if s != "big":
            counts.update(s)
    ranked = [p for p, _ in counts.most_common() if p in mine]
    step = max(1, len(ranked) // max(1, a.seeds // 2))
    seeds = list(dict.fromkeys(ranked[:a.seeds // 2] + ranked[::step]))[:a.seeds]
    bad, t_mine, t_git = [], 0.0, 0.0
    for p in seeds:
        t = time.time()
        g = capped(git_log(top, p))
        t_git += time.time() - t
        t = time.time()
        m = capped(gitread.log(top, repo, [p], LOG_COMMITS, MAX_FILES))
        t_mine += time.time() - t
        if collections.Counter(g) != collections.Counter(m):
            bad.append((p, len(g), len(m)))
    print("log: %d seeds, %d differ; git %.1f s, gitread %.1f s" % (len(seeds), len(bad), t_git, t_mine))
    for p, ng, nm in bad[:10]:
        print("   differs: %s  git %d commits, gitread %d" % (p, ng, nm))
    ok &= not bad

    if a.log_only:
        print("ALL SAME" if ok else "DIFFERENCES FOUND")
        return 0 if ok else 1
    tmp = tempfile.mkdtemp(prefix="gitread-check-")
    try:
        work = os.path.join(tmp, "w")
        subprocess.run(["git", "clone", "--quiet", "--shared", top, work], check=True)
        files = sorted(p for p in gitread.head_files(gitread.Repo(os.path.join(work, ".git")))
                       if p.endswith((".vue", ".ts", ".go", ".md", ".json")))
        picks = files[::max(1, len(files) // 6)][:6]
        for i, p in enumerate(picks):
            full = os.path.join(work, p)
            with open(full, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().split("\n")
            if i == 0:
                os.remove(full)                                   # deleted file
                continue
            mid = len(lines) // 2
            lines[mid:mid + 2] = ["-- starts with dashes %d" % i, "changed line %d" % i]
            lines.insert(1, "added line %d" % i)
            if i % 2:
                del lines[-3:-1]
            with open(full, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        with open(os.path.join(work, "new-file.txt"), "w") as fh:
            fh.write("untracked\n")
        wrepo = gitread.Repo(os.path.join(work, ".git"))
        mine_changed = set(gitread.changed_files(work, wrepo))
        git_changed = set(filter(None, git(work, "diff", "--name-only", "--no-renames", "HEAD").split("\n")))
        print("changed files: gitread %d, git %d, same %s" % (len(mine_changed), len(git_changed), mine_changed == git_changed))
        ok &= mine_changed == git_changed
        g_rem, g_add = git_hunks(work)
        m_rem, m_add = collections.Counter(), collections.Counter()
        for path, rem, add in gitread.diff_hunks(work, wrepo):
            key = path or "DELETED:" + picks[0]
            m_rem.update((key, l) for l in rem)
            m_add.update((key, l) for l in add)
        same = g_rem == m_rem and g_add == m_add
        print("diff lines: removed git %d / gitread %d, added git %d / gitread %d, same %s"
              % (sum(g_rem.values()), sum(m_rem.values()), sum(g_add.values()), sum(m_add.values()), same))
        ok &= same
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL SAME" if ok else "DIFFERENCES FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
