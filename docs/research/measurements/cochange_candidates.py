#!/usr/bin/env python3
"""Find real commits where co-change predicts a file that a text search from the seed would miss.

Usage: python3 -I cochange_candidates.py HISTORY_REPO SNAPSHOT_DIR [--test 600] [--max-files 8]

HISTORY_REPO is a clone with history (file names are enough: --filter=blob:none). SNAPSHOT_DIR is a
checkout of a recent commit, used to judge whether the predicted file B is linked to the seed A by
text: B or A mentions the other's name (import, component tag), they are locale counterparts, or they
sit in the same directory. Unlinked correct predictions are the cases where only the history channel
would surface B. Standard library only; nothing in either repository is run.
"""
import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cochange_backtest import MAX_COMMIT_FILES, LOG_COMMITS, commits, predict  # noqa: E402

LOCALE = re.compile(r"(zh[-_]?cn|en[-_]?us|zh[-_]?tw|ja[-_]?jp)", re.I)


def stem(path):
    base, _ = os.path.splitext(os.path.basename(path))
    if base.lower() in ("index", "main", "mod", "types", "type", "api", "model", "service", "handler"):
        base = os.path.basename(os.path.dirname(path)) or base
    return base


def spellings(word):
    parts = [p.lower() for p in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", word.replace("-", " ").replace("_", " "))]
    if not parts:
        return {word.lower()}
    return {"".join(parts), "-".join(parts), "_".join(parts)}


def text(snapshot, path, cache):
    if path not in cache:
        try:
            with open(os.path.join(snapshot, path), encoding="utf-8", errors="replace") as fh:
                cache[path] = fh.read().lower()
        except OSError:
            cache[path] = None
    return cache[path]


def mentions(body, name):
    if body is None:
        return False
    flat = body.replace("-", "").replace("_", "")
    return any(len(s) >= 4 and (s in body or s.replace("-", "").replace("_", "") in flat) for s in spellings(name))


def link(snapshot, a, b, cache):
    if LOCALE.sub("@", a) == LOCALE.sub("@", b) and a != b:
        return "locale pair"
    if os.path.dirname(a) == os.path.dirname(b):
        return "same dir"
    ta, tb = text(snapshot, a, cache), text(snapshot, b, cache)
    if ta is None or tb is None:
        return "gone"
    if mentions(tb, stem(a)) or mentions(ta, stem(b)):
        return "name"
    return "unlinked"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("snapshot")
    ap.add_argument("--test", type=int, default=600)
    ap.add_argument("--max-files", type=int, default=8)
    ap.add_argument("--support", type=int, default=3)
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--show", type=int, default=25)
    a = ap.parse_args()
    log = commits(a.repo)
    kinds, found, cache = collections.Counter(), [], {}
    for i, (sha, files) in enumerate(log[:a.test]):
        if not 2 <= len(files) <= min(a.max_files, MAX_COMMIT_FILES):
            continue
        history = log[i + 1:i + 1 + LOG_COMMITS]
        for seed in sorted(files):
            pred, n = predict(history, seed, a.support, a.conf)
            for b in sorted(pred & (files - {seed})):
                k = link(a.snapshot, seed, b, cache)
                kinds[k] += 1
                if k == "unlinked":
                    found.append((sha, seed, b, n, len(files)))
    print("correct predictions by link to the seed: %s" % dict(kinds.most_common()))
    pairs = collections.Counter((s, b) for _, s, b, _, _ in found)
    print("unlinked: %d predictions, %d distinct pairs" % (len(found), len(pairs)))
    for (s, b), k in pairs.most_common(a.show):
        shas = [x[0] for x in found if (x[1], x[2]) == (s, b)][:4]
        print("%2d  %s  ->  %s   (%s)" % (k, s, b, " ".join(shas)))


if __name__ == "__main__":
    main()
