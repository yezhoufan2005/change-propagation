#!/usr/bin/env python3
"""Local checks: (1) post-consolidation leftover detection using saved pre-edit bodies as seeds;
(2) noise floor of blind-normalized similarity on random function pairs (stdlib, vendored code excluded)."""
import sys, os, random, statistics, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neardup2 as n2

BEFORE, AFTER = '/tmp/cp_fixtures/src', '/tmp/cp_fixtures/after'
STD = '/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9'

def part1():
    before = n2.load(BEFORE, 5, 20); after = n2.load(AFTER, 5, 20)
    seed = [f for f in before if f['file'] == 'cart/price.ts'][0]
    group = [f for f in before if max(n2.score(seed, f)) >= 0.8]  # pre-edit clone group incl. seed
    print('pre-edit group:', [n2.tag(f) for f in group])
    print('post-edit fragments:', [n2.tag(f) for f in after])
    shared = [f for f in after if f['file'].startswith('shared/')][0]
    for f in after:
        best = max(max(n2.score(g, f)) for g in group)
        via_shared = max(n2.score(shared, f)) if f is not shared else None
        print('  %-42s best-vs-saved-bodies=%.2f  vs-shared=%s' % (n2.tag(f), best, 'self' if via_shared is None else '%.2f' % via_shared))
    for pat in [r'\.unitPrice \* ', r'Math\.round\(\(']:
        r = subprocess.run(['grep', '-rnE', pat, AFTER], capture_output=True, text=True)
        hits = [l.split(':')[0].replace(AFTER + '/', '') for l in r.stdout.splitlines()]
        print('  grep %-20s -> %s' % (pat, hits))

def part2():
    t0 = time.time()
    fr = [f for f in n2.load(STD, 5, 50) if 'site-packages' not in f['file'] and '_vendor' not in f['file']]
    random.seed(7); rs, js = [], []
    for _ in range(3000):
        x, y = random.sample(fr, 2)
        j, r = n2.score(x, y); rs.append(r); js.append(j)
    def q(v, p): return sorted(v)[int(p * (len(v) - 1))]
    print('random pairs n=3000 over %d non-vendored stdlib functions (%.1fs)' % (len(fr), time.time() - t0))
    for name, v in (('seq_ratio', rs), ('jaccard_k5', js)):
        print('  %-10s median=%.2f p90=%.2f p99=%.2f p99.9=%.2f max=%.2f  >=0.7: %d  >=0.8: %d' % (
            name, statistics.median(v), q(v, .9), q(v, .99), q(v, .999), max(v), sum(a >= .7 for a in v), sum(a >= .8 for a in v)))

if __name__ == '__main__':
    part1(); part2()
