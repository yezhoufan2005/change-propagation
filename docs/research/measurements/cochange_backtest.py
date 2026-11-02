#!/usr/bin/env python3
"""Backtest the co-change channel on a repository's real history.

Usage: python3 -I cochange_backtest.py REPO [--test 300] [--support 2] [--conf 0.3] [--reverse 3,0.6]

For each of the last --test non-merge commits that touch 2..MAX_COMMIT_FILES files, every file of
the commit in turn plays the seed A. Co-change is computed only from older commits (the LOG_COMMITS
most recent before it, as cplib/history.py does), and the prediction is compared with the other
files the commit really changed.

A file B is predicted when n(A,B) >= --support and P(B|A) = n(A,B)/n(A) >= --conf. With --reverse
S,C it is also predicted when n(A,B) >= S and P(A|B) = n(A,B)/n(B) >= C: B rarely changes without A
(a file that follows a large, often-edited one). Only file names are read (git log --name-only
--no-renames), so a `--filter=blob:none` clone is enough. Standard library only.
"""
import argparse
import collections
import subprocess

MAX_COMMIT_FILES = 30
LOG_COMMITS = 3000


def commits(repo):
    out = subprocess.run(["git", "-C", repo, "log", "--no-merges", "--no-renames", "--name-only", "--format=tformat:@@%h"],
                         stdout=subprocess.PIPE, check=True).stdout.decode("utf-8", "replace")
    result = []
    for chunk in out.split("@@")[1:]:
        lines = [l for l in chunk.split("\n") if l]
        result.append((lines[0], set(lines[1:])))
    return result          # newest first


def usable(files):
    return 0 < len(files) <= MAX_COMMIT_FILES


def predict(history, seed, support, conf, reverse=None, counts=None, top=None):
    """Predicted partners of `seed` from `history` (older commits), and the seed's commit count.
    With `top`, only the `top` partners with the highest P(B|A), then n(A,B), are kept."""
    with_seed = [files for _, files in history if seed in files and usable(files)]
    if len(with_seed) < min(support, reverse[0] if reverse else support):
        return set(), len(with_seed)
    pair = collections.Counter(f for files in with_seed for f in files if f != seed)
    out = {f for f, n in pair.items() if n >= support and n / len(with_seed) >= conf}
    if reverse:
        if counts is None:
            counts = collections.Counter(f for _, files in history if usable(files) for f in files)
        out |= {f for f, n in pair.items() if n >= reverse[0] and n / counts[f] >= reverse[1]}
    if top:
        out = set(sorted(out, key=lambda f: (-pair[f], f))[:top])
    return out, len(with_seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--test", type=int, default=300)
    ap.add_argument("--support", type=int, default=2)
    ap.add_argument("--conf", type=float, default=0.3)
    ap.add_argument("--reverse", help="S,C: also predict B when n(A,B) >= S and P(A|B) >= C")
    ap.add_argument("--top", type=int, help="keep only the TOP partners per seed")
    a = ap.parse_args()
    reverse = None
    if a.reverse:
        s, c = a.reverse.split(",")
        reverse = (int(s), float(c))
    log = commits(a.repo)
    trials = covered = hit_any = 0
    tp = pred_total = truth_total = 0
    sizes = collections.Counter()
    # n(file) over the sliding window log[i+1 : i+1+LOG_COMMITS]
    counts = collections.Counter(f for _, files in log[1:1 + LOG_COMMITS] if usable(files) for f in files)
    for i, (_, files) in enumerate(log[:a.test]):
        if i:
            for f in (log[i][1] if usable(log[i][1]) else ()):
                counts[f] -= 1
            if i + LOG_COMMITS < len(log) and usable(log[i + LOG_COMMITS][1]):
                counts.update(log[i + LOG_COMMITS][1])
        if not 2 <= len(files) <= MAX_COMMIT_FILES:
            continue
        history = log[i + 1:i + 1 + LOG_COMMITS]
        for seed in sorted(files):
            truth = files - {seed}
            pred, n = predict(history, seed, a.support, a.conf, reverse, counts, a.top)
            trials += 1
            truth_total += len(truth)
            if n >= a.support:
                covered += 1
            if pred:
                sizes[min(len(pred), 10)] += 1
            got = pred & truth
            tp += len(got)
            pred_total += len(pred)
            hit_any += bool(got)
    print("repo %s: %d commits, tested the last %d (support >= %d, confidence >= %.2f%s%s)"
          % (a.repo, len(log), a.test, a.support, a.conf,
             ", reverse n >= %d and P(A|B) >= %.2f" % reverse if reverse else "",
             ", top %d per seed" % a.top if a.top else ""))
    print("seed trials %d; seed has enough history %d (%.0f%%)" % (trials, covered, 100.0 * covered / max(1, trials)))
    print("at least one real co-changed file predicted: %d (%.0f%%)" % (hit_any, 100.0 * hit_any / max(1, trials)))
    print("recall %.0f%% (%d of %d co-changed files), precision %.0f%% (%d of %d predictions)"
          % (100.0 * tp / max(1, truth_total), tp, truth_total, 100.0 * tp / max(1, pred_total), tp, pred_total))
    print("predictions per seed when any (10 = 10+): %s" % dict(sorted(sizes.items())))


if __name__ == "__main__":
    main()
