#!/usr/bin/env python3
"""Grade pilot baseline runs of the shopfront fixture against gt.json.

Usage: python3 grade.py META_DIR FINALS_JSON RUN_ID [RUN_ID ...]
  META_DIR     holds fixture/shopfront (or pristine/shopfront) and gt.json
  FINALS_JSON  {"T1-r1": "<agent final message>", ...}; "-" if none
  RUN_ID       e.g. T2-r1, graded from $CP_RUN_ROOT/cp-run-<RUN_ID>/shopfront (CP_RUN_ROOT defaults to /tmp)
"""
import difflib
import json
import os
import re
import sys

META, FINALS_PATH, RUNS = sys.argv[1], sys.argv[2], sys.argv[3:]
RUN_ROOT = os.environ.get('CP_RUN_ROOT', '/tmp')
PRISTINE = next(p for p in (os.path.join(META, d, 'shopfront') for d in ('fixture', 'pristine')) if os.path.isdir(p))
GT = json.load(open(os.path.join(META, 'gt.json'), encoding='utf-8'))
FINALS = json.load(open(FINALS_PATH, encoding='utf-8')) if FINALS_PATH != '-' else {}

# T2: a shared stylesheet may animate a component through its selector instead of editing its files.
SELECTORS = {
    'modal': ['.modal-mask', '.modal-panel'],
    'bottom-sheet': ['.backdrop', '.sheet'],
    'image-lightbox': ['.lightbox-overlay'],
    'address-picker-inline': ['.address-picker'],
    'coupon-layer': ['.coupon-layer'],
    'drawer': ['.drawer'],
    'toast': ['.toast'],
    'tooltip': ['.tooltip'],
}


def walk(root):
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ('node_modules', '.git')]
        for name in filenames:
            path = os.path.join(dirpath, name)
            files[os.path.relpath(path, root)] = path
    return files


def lines(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def added(before, after):
    diff = difflib.unified_diff(before, after, lineterm='', n=0)
    return [l[1:] for l in diff if l.startswith('+') and not l.startswith('+++')]


def grade(run):
    task = run.split('-')[0]
    spec = GT[task]
    before, after = walk(PRISTINE), walk(os.path.join(RUN_ROOT, f'cp-run-{run}', 'shopfront'))
    changed = sorted(k for k in after if k not in before or lines(before[k]) != lines(after[k]))
    deleted = sorted(k for k in before if k not in after)
    plus = {k: added(lines(before[k]) if k in before else [], lines(after[k])) for k in changed}
    marker = re.compile(spec['edit_marker'], re.I) if spec['edit_marker'] else None
    final = FINALS.get(run, '').lower()
    rows, site_files = [], set()
    for site in spec['sites']:
        site_files.update(site['files'])
        hit = [f for f in site['files'] if f in changed or f in deleted]
        if marker:
            hit = [f for f in hit if f in deleted or any(marker.search(l) for l in plus[f])]
            for sel in SELECTORS.get(site['id'], []):
                for f, new in plus.items():
                    if f not in site['files'] and any(sel in l for l in new) and any(marker.search(l) for l in new):
                        hit.append(f'{f} (via selector {sel})')
        mentioned = any(m.lower() in final for m in site['mention'])
        status = 'edited' if hit else ('mentioned' if mentioned else 'missed')
        rows.append({'id': site['id'], 'tier': site['tier'], 'status': status, 'evidence': sorted(set(hit))})
    extra = [f for f in changed if f not in site_files]
    return {'run': run, 'rows': rows, 'extra_changed': extra, 'deleted': deleted}


def summarize(result):
    counts = {}
    for row in result['rows']:
        tier = counts.setdefault(row['tier'], {'edited': 0, 'mentioned': 0, 'missed': 0})
        tier[row['status']] += 1
    return counts


if __name__ == '__main__':
    results = [grade(run) for run in RUNS]
    for r in results:
        r['summary'] = summarize(r)
    print(json.dumps(results, ensure_ascii=False, indent=2))
