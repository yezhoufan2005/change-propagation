"""Summarize detect.py output."""
import json, sys, statistics as st, collections
R = json.load(open(sys.argv[1]))
tot = collections.Counter()
per_lv = {lv: collections.Counter() for lv in ('L0', 'L1', 'L2')}
ncand = {lv: [] for lv in per_lv}
scan = []; files = []
for r in R:
    scan.append(r['scan_s'] + r['load_s']); files.append(r['files_in_tree'])
    ex = [s for s in r['sites'] if s['existed_at_c1']]
    tot['groups'] += 1; tot['later_sites'] += len(r['sites']); tot['existed'] += len(ex)
    tot['groups_with_existing_site'] += 1 if ex else 0
    tot['kind_' + r['kind']] += 1
    same_file = sum(1 for s in ex if s['f'] == r['seed_file'])
    tot['existed_same_file'] += same_file
    for lv in per_lv:
        f = r['found'][lv]
        per_lv[lv]['found_sites'] += sum(f)
        per_lv[lv]['groups_any_found'] += 1 if any(f) else 0
        per_lv[lv]['cand'] += r['n_cand'][lv]
        per_lv[lv]['confirmed'] += r['confirmed'][lv]
        per_lv[lv]['found_' + r['kind']] += sum(f)
        if ex:
            ncand[lv].append(r['n_cand'][lv])
print(dict(tot))
for lv, c in per_lv.items():
    nc = sorted(ncand[lv])
    print(lv, dict(c), 'recall_vs_existing=%.2f' % (c['found_sites'] / max(1, tot['existed'])),
          'precision_lb=%.2f' % (c['confirmed'] / max(1, c['cand'])),
          'cand median %s p90 %s max %s' % (nc[len(nc)//2] if nc else '-', nc[int(len(nc)*.9)] if nc else '-', nc[-1] if nc else '-'))
print('scan seconds per seed: median %.2f max %.2f; files per tree median %d' % (st.median(scan), max(scan), st.median(files)))
ex_kind = collections.Counter()
for r in R:
    for s in r['sites']:
        if s['existed_at_c1']:
            ex_kind[r['kind']] += 1
print('existing sites by seed kind', dict(ex_kind))
