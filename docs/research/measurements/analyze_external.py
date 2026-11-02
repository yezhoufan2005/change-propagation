#!/usr/bin/env python3
"""Check the outputs of run_external_tools.sh against plain-regex counts and summarize the jscpd reports.

Usage: python3 -I analyze_external.py [OUT_DIR]
  OUT_DIR defaults to /tmp/cpf-measure/external; the clones are read from /tmp/cpf-measure/repos.
Prints one JSON line per check and writes all of them to OUT_DIR/analysis.json.
"""
import collections
import json
import os
import re
import statistics
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/cpf-measure/external'
REPOS = '/tmp/cpf-measure/repos'
BE = os.path.join(REPOS, 'thingspanel-backend-community')
FE = os.path.join(REPOS, 'thingspanel-frontend-community', 'src')
SKIP_DIRS = {'.git', 'node_modules'}
WATCH = r'(?<![\w$.])watch\s*\('
# ast-grep run label -> (root, file extension, regex for the same calls)
BASELINES = {
    'sg-go-subscribe': (BE, '.go', r'\.Subscribe\s*\('),
    'sg-go-publish': (BE, '.go', r'\.Publish\s*\('),
    'sg-go-unmarshal': (BE, '.go', r'(?<![\w.])json\.Unmarshal\s*\('),
    'sg-ts-watch': (FE, '.ts', WATCH),
    'sg-ts-get': (FE, '.ts', r'\.get\s*\('),
}
SCRIPT = re.compile(r'<script\b([^>]*)>(.*?)</script\s*>', re.S | re.I)


def load(path):
    with open(os.path.join(OUT, path), encoding='utf-8') as f:
        return json.load(f)


def sources(root, ext):
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for name in sorted(names):
            if name.endswith(ext):
                path = os.path.join(d, name)
                with open(path, encoding='utf-8', errors='replace') as f:
                    yield os.path.relpath(path, root), f.read()


def rel(path, root):
    return os.path.relpath(path, root) if os.path.isabs(path) else path


def pct(xs, q):
    return sorted(xs)[min(len(xs) - 1, int(len(xs) * q))]


def baseline(label, root, ext, pattern):
    items = load(label + '.json')
    found = collections.Counter(rel(i['file'], root) for i in items)
    regex = re.compile(pattern)
    counts = {r: n for r, n in ((r, len(regex.findall(text))) for r, text in sources(root, ext)) if n}
    diff = sorted(r for r in set(found) | set(counts) if found.get(r, 0) != counts.get(r, 0))
    return {'label': label, 'ast_grep': len(items), 'regex': sum(counts.values()),
            'files_ast_grep': len(found), 'files_regex': len(counts), 'files_differing': len(diff),
            'differing_sample': [f'{r} sg={found.get(r, 0)} re={counts.get(r, 0)}' for r in diff[:6]]}


def vue_coverage():
    items = load('sg-vue-html-ts-flag.json')
    key = lambda xs: sorted((rel(i['file'], FE), i['range']['start']['line']) for i in xs)
    hit_lines = collections.defaultdict(set)
    for i in items:
        hit_lines[rel(i['file'], FE)].add(i['range']['start']['line'])
    blocks, calls, missed = collections.Counter(), collections.Counter(), []
    regex_lines = collections.defaultdict(set)
    for r, text in sources(FE, '.vue'):
        spans = []
        for m in SCRIPT.finditer(text):
            lang = re.search(r'\blang\s*=\s*["\']?(\w+)', m.group(1))
            lang = lang.group(1).lower() if lang else 'js'
            blocks[lang + ('+setup' if re.search(r'\bsetup\b', m.group(1)) else '')] += 1
            spans.append((m.start(2), m.end(2), lang))
        for m in re.finditer(WATCH, text):
            line = text.count('\n', 0, m.start())
            regex_lines[r].add(line)
            where = next((lang for a, b, lang in spans if a <= m.start() < b), 'outside')
            hit = line in hit_lines.get(r, ())
            calls[f'{where}:{"found" if hit else "missed"}'] += 1
            if not hit:
                start = text.rfind('\n', 0, m.start()) + 1
                end = text.find('\n', m.start())
                missed.append(f'{r}:{line + 1} [{where}] {text[start:end if end >= 0 else None].strip()[:90]}')
    extra = sum(1 for r, lines in hit_lines.items() if r.endswith('.vue') for n in lines if n not in regex_lines.get(r, ()))
    return {'label': 'vue-coverage', 'ast_grep_items': len(items),
            'ast_grep_by_ext': dict(collections.Counter(os.path.splitext(i['file'])[1] for i in items)),
            'cwd_and_flag_identical': key(items) == key(load('sg-vue-html-ts-cwd.json')),
            'script_blocks': dict(blocks), 'regex_calls': dict(calls),
            'ast_grep_lines_without_regex_hit': extra, 'missed_sample': missed[:12]}


def clone_stats(name):
    rep = load(os.path.join(name, 'jscpd-report.json'))
    dups, stats = rep['duplicates'], rep['statistics']
    lines = [d['lines'] for d in dups]
    pairs = [(d['firstFile']['name'], d['secondFile']['name']) for d in dups]
    partners = collections.defaultdict(set)
    for a, b in pairs:
        partners[a].add(b)
        partners[b].add(a)
    per_file = [len(v) for v in partners.values()]
    compact = '\n'.join(f"{d['firstFile']['name']}:{d['firstFile']['start']}-{d['firstFile']['end']} "
                        f"{d['secondFile']['name']}:{d['secondFile']['start']}-{d['secondFile']['end']}" for d in dups)
    return {'label': name, 'clones': len(dups), 'kinds': dict(collections.Counter(d['kind'] for d in dups)),
            'formats': {k: [v['sources'], v['clones'], v['lines']] for k, v in stats['formats'].items()},
            'lines_min_median_p90_max': [min(lines), statistics.median(lines), pct(lines, .9), max(lines)],
            'tokens_min': min(d['tokens'] for d in dups),
            'same_file': sum(a == b for a, b in pairs),
            'same_dir_other_file': sum(a != b and os.path.dirname(a) == os.path.dirname(b) for a, b in pairs),
            'cross_dir': sum(os.path.dirname(a) != os.path.dirname(b) for a, b in pairs),
            'test_or_mock_path': sum(bool(re.search(r'test|mock', a + b, re.I)) for a, b in pairs),
            'files_with_clones': len(partners),
            'partners_per_file_median_p90_max': [statistics.median(per_file), pct(per_file, .9), max(per_file)],
            'top_dirs': collections.Counter('/'.join(f.split('/')[:2]) for p in pairs for f in p).most_common(6),
            'name_sample': pairs[0],
            'one_line_per_clone_bytes': len(compact.encode())}


rows = [baseline(label, *spec) for label, spec in BASELINES.items()]
rows.append(vue_coverage())
rows += [clone_stats(n) for n in ('jscpd-frontend', 'jscpd-backend')]
with open(os.path.join(OUT, 'analysis.json'), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
for row in rows:
    print(json.dumps(row, ensure_ascii=False))
