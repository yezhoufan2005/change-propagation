"""Group mined hunks by abstracted edit delta and report repeated-edit statistics.

usage: python3 -I groups.py <hunks.json> [window_days]
"""
import json, re, sys, collections
d = json.load(open(sys.argv[1]))
WIN = int(sys.argv[2]) if len(sys.argv) > 2 else 180
commits, hunks = d['commits'], d['hunks']
FIX = re.compile(r'\bfix|bug|修复|修正|解决|问题|错误|hotfix', re.I)


def informative(delta):
    toks = delta.split()
    if len(toks) < 2:
        return False
    core = [t[1:] for t in toks]
    # need at least one non-abstract, non-punctuation token
    return any(re.match(r'[A-Za-z_一-鿿"\'`0-9]', t) and t != '$' for t in core)


groups = collections.defaultdict(list)
for h in hunks:
    if informative(h['kdelta']):
        groups[h['kdelta']].append(h)

stat = collections.Counter()
multi = []
for k, hs in groups.items():
    cs = sorted(set(h['c'] for h in hs))
    if len(hs) < 2:
        stat['singleton'] += 1
        continue
    if len(hs) > 40:
        stat['too_generic'] += 1
        continue
    if len(cs) == 1:
        stat['one_commit'] += 1
        continue
    c1 = cs[0]
    t1 = commits[c1]['ts']
    later = [h for h in hs if h['c'] != c1 and commits[h['c']]['ts'] - t1 <= WIN * 86400]
    if not later:
        stat['multi_commit_outside_window'] += 1
        continue
    first = [h for h in hs if h['c'] == c1]
    stat['multi_commit_in_window'] += 1
    multi.append((k, c1, first, later))

print('groups', len(groups), dict(stat))
fixc = [c for c in commits if FIX.search(c['subj'])]
print('fix commits', len(fixc), 'of', len(commits))
fix_with_follow = collections.defaultdict(list)
for k, c1, first, later in multi:
    if FIX.search(commits[c1]['subj']):
        fix_with_follow[c1].append((k, first, later))
print('fix commits whose abstracted edit recurs later within', WIN, 'days:', len(fix_with_follow))
kinds = collections.Counter(f[0]['kind'] for _, _, f, _ in multi)
print('kind of first hunk in multi-commit groups', dict(kinds))
same_file = sum(1 for _, _, f, l in multi if any(x['f'] in {y['f'] for y in f} for x in l))
print('groups where some later hunk is in a file the first commit touched:', same_file, 'of', len(multi))
lag = sorted((commits[l[0]['c']]['ts'] - commits[c1]['ts']) / 86400 for _, c1, _, l in multi)
if lag:
    print('lag days to first recurrence: median %.1f p25 %.1f p75 %.1f' % (lag[len(lag)//2], lag[len(lag)//4], lag[3*len(lag)//4]))
json.dump([{'k': k, 'c1': c1, 'first': f, 'later': l} for k, c1, f, l in multi], open(sys.argv[1].replace('.json', '_multi.json'), 'w'))
for k, c1, f, l in multi[:0]:
    pass
