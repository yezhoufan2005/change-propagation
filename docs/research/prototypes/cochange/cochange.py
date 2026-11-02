#!/usr/bin/env python3
"""Stdlib-only TARMAQ co-change recommender + leave-one-out eval (research check)."""
import argparse, bisect, collections, json, re, subprocess, sys, time


def load(repo, n, max_files, mode):
    cmd = ['git', '-C', repo, 'log', '--no-renames', '--name-only',
           '--format=%x1e%H%x1f%at%x1f%s', '-n', str(n)]
    cmd += (['--first-parent', '--diff-merges=first-parent'] if mode == 'pr'
            else ['--no-merges'])
    t0 = time.time()
    out = subprocess.run(cmd, stdout=subprocess.PIPE, check=True).stdout
    out = out.decode('utf-8', 'replace')
    t_git = time.time() - t0
    txs, dropped, empty, sizes = [], 0, 0, []
    for rec in out.split('\x1e')[1:]:
        head, _, body = rec.partition('\n')
        parts = (head.split('\x1f') + ['', ''])[:3]
        files = frozenset(l for l in body.split('\n') if l.strip())
        if not files:
            empty += 1
            continue
        sizes.append(len(files))
        if len(files) > max_files:
            dropped += 1
        txs.append((parts[0][:10], int(parts[1] or 0), parts[2], files))
    index = collections.defaultdict(list)
    for j, t in enumerate(txs):  # j ascending = newest first
        if len(t[3]) > max_files:
            continue  # large commits are kept as test-set members but never learned from
        for f in t[3]:
            index[f].append(j)
    return txs, index, dict(git_s=round(t_git, 2), total_s=round(time.time() - t0, 2),
                            kept=len(txs) - dropped, dropped_large=dropped, empty=empty,
                            raw=len(sizes))


def tarmaq(txs, index, query, lo, hi):
    q = set(query)
    overlap = collections.Counter()
    for f in q:
        lst = index.get(f, [])
        for j in lst[bisect.bisect_left(lst, lo):bisect.bisect_left(lst, hi)]:
            overlap[j] += 1
    if not overlap:
        return [], 0
    k = max(overlap.values())
    ante, rule, ev = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for j, c in overlap.items():
        if c != k:
            continue
        t = txs[j][3]
        a = frozenset(q & t)
        ante[a] += 1
        for x in t - q:
            rule[(a, x)] += 1
            ev[(a, x)].append(j)
    best = {}
    for (a, x), s in rule.items():
        key = (s, s / ante[a])
        if x not in best or key > best[x][0]:
            best[x] = (key, a)
    ranked = sorted(best.items(), key=lambda kv: (-kv[1][0][0], -kv[1][0][1], kv[0]))
    return [(x, key[0], key[1], a, sorted(ev[(a, x)])) for x, (key, a) in ranked], k


def tier(s, c):
    if s >= 3 and c >= 0.5:
        return 'A_s3_c0.5'
    if s >= 2 and c >= 0.2:
        return 'B_s2_c0.2'
    return 'C_rest'


def cat(path):
    low = path.lower()
    base = low.rsplit('/', 1)[-1]
    if re.search(r'(^|/)(tests?|__tests__|spec|testing)(/|$)|[._-](test|spec)s?\.|^test_', low) \
            or base.startswith('test_'):
        return 'test'
    if base.endswith(('.md', '.rst', '.txt')) or base in (
            'package.json', 'pyproject.toml', 'setup.py', 'setup.cfg', 'pnpm-lock.yaml',
            'yarn.lock', 'package-lock.json', 'requirements.txt', 'tox.ini'):
        return 'docs_meta'
    return 'code'


def evaluate(txs, index, n_test, window, top, test_max):
    tests = [i for i, t in enumerate(txs) if 2 <= len(t[3]) <= test_max][:n_test]
    qn = hit = app = seen = 0
    rr = 0.0
    tiers = collections.defaultdict(lambda: [0, 0])
    bycat = collections.defaultdict(lambda: [0, 0])
    closure_alarm = warn = warn_recs = warn_hit = 0
    lat = []
    for i in tests:
        files = sorted(txs[i][3])
        lo, hi = i + 1, min(len(txs), i + 1 + window)
        full, _ = tarmaq(txs, index, files, lo, hi)
        if any(s >= 3 and c >= 0.9 for x, s, c, a, e in full):
            closure_alarm += 1
        for f in files:
            q = [g for g in files if g != f]
            t0 = time.time()
            recs, _ = tarmaq(txs, index, q, lo, hi)
            lat.append(time.time() - t0)
            warn_set = [x for x, s, c, a, e in recs if s >= 3 and c >= 0.9]
            if warn_set:
                warn += 1
                warn_recs += len(warn_set)
                warn_hit += f in warn_set
            qn += 1
            lst = index.get(f, [])
            if bisect.bisect_left(lst, lo) < bisect.bisect_left(lst, hi):
                seen += 1
            if recs:
                app += 1
            bycat[cat(f)][0] += 1
            for r, (x, s, c, a, e) in enumerate(recs[:top], 1):
                tiers[tier(s, c)][0] += 1
                if x == f:
                    tiers[tier(s, c)][1] += 1
                    bycat[cat(f)][1] += 1
                    hit += 1
                    rr += 1.0 / r
    lat.sort()
    return dict(test_commits=len(tests), queries=qn,
                prevention_s3_c09=dict(feedback=round(warn / qn, 3),
                                       heldout_in_warning=round(warn_hit / warn, 3) if warn else None,
                                       precision=round(warn_hit / warn_recs, 3) if warn_recs else None),
                closure_false_alarm=round(closure_alarm / len(tests), 3),
                hit_by_heldout_type={k: [v[0], round(v[1] / v[0], 3)] for k, v in sorted(bycat.items())},
                heldout_seen_in_history=round(seen / qn, 3),
                applicable=round(app / qn, 3), hit_at_top=round(hit / qn, 3),
                mrr=round(rr / qn, 3),
                tiers={k: dict(recs=v[0], hit_rate=round(v[1] / v[0], 3) if v[0] else None)
                       for k, v in sorted(tiers.items())},
                median_query_ms=round(1000 * lat[len(lat) // 2], 2),
                p95_query_ms=round(1000 * lat[int(len(lat) * 0.95)], 2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    p.add_argument('--max-commits', type=int, default=15000)
    p.add_argument('--max-files', type=int, default=8)
    p.add_argument('--mode', choices=['commit', 'pr'], default='commit')
    p.add_argument('--window', type=int, default=15000)
    p.add_argument('--eval', type=int, default=0)
    p.add_argument('--top', type=int, default=10)
    p.add_argument('--query', nargs='*', default=[])
    p.add_argument('--test-max-files', type=int, default=8)
    a = p.parse_args()
    txs, index, stats = load(a.repo, a.max_commits, a.max_files, a.mode)
    out = dict(load=stats)
    if a.query:
        recs, k = tarmaq(txs, index, a.query, 0, min(len(txs), a.window))
        out['k'] = k
        out['recs'] = [dict(file=x, support=s, confidence=round(c, 2), antecedent=sorted(an),
                            evidence=[txs[j][0] + ' ' + txs[j][2][:60] for j in e[:3]],
                            last_seen_commits_ago=e[0])
                       for x, s, c, an, e in recs[:a.top]]
    if a.eval:
        out['eval'] = evaluate(txs, index, a.eval, a.window, a.top, a.test_max_files)
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
