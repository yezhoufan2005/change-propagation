#!/usr/bin/env python3
"""Find string literals shared between server-side and client-side tiers.

Usage: python3 -I shared_literals.py <repo_root> <repo_key> <out_json>
Tiers are path-prefix based (see TIERS). Literal classes: msg (human text),
key (dotted/snake ids), rx (regex-looking). Reports shared counts + samples.
"""
import json, os, random, re, subprocess, sys
from collections import defaultdict

TIERS = {
    'immich': {'server': ['server/src/'], 'web': ['web/src/'], 'mobile': ['mobile/lib/']},
    'gitea': {'server': ['models/', 'modules/', 'routers/', 'services/', 'cmd/'],
              'web': ['web_src/'], 'tpl': ['templates/']},
    'mattermost': {'server': ['server/'], 'web': ['webapp/']},
    'zulip': {'server': ['zerver/', 'corporate/', 'analytics/', 'zilencer/', 'zproject/', 'confirmation/'],
              'web': ['web/src/', 'web/templates/'], 'tpl': ['templates/']},
}
CODE_EXT = ('.go', '.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte', '.dart',
            '.tmpl', '.hbs', '.html')
SKIP = re.compile(r'(^|/)(node_modules|vendor|i18n|locale|locales|dist|build|testdata|fixtures?|'
                  r'__snapshots__|openapi|generated)(/|$)|_test\.go$|\.test\.|\.spec\.|/tests?/|'
                  r'\.min\.js$|\.g\.dart$|\.freezed\.dart$|\.gen\.', re.I)
STR = re.compile(r'"((?:[^"\\\n]|\\.){4,240})"|\'((?:[^\'\\\n]|\\.){4,240})\'|`([^`$\n]{4,240})`')
JSRX = re.compile(r'(?:[(=,:!&|?]|return)\s*/((?:[^/\\\n*]|\\.)(?:[^/\\\n]|\\.){3,200})/[dgimsuy]*\s*[),;.\n]')
KEY = re.compile(r'^[a-z][a-z0-9]*(?:[._][a-z0-9]+){2,}$')
RXH = re.compile(r'\\[dwsbDWS]|\[[a-zA-Z0-9]-[a-zA-Z0-9]|\{\d+,?\d*\}|^\^|\$$')
ERRW = re.compile(r'\b(must|invalid|cannot|can\'t|not allowed|too (long|short|many|large)|at (least|most)|'
                  r'required|exceed\w*|maximum|minimum|error|failed|only)\b', re.I)


def classify(s):
    if '://' in s or s.startswith(('<', '/', '.', '#', '@')):
        return None if not RXH.search(s) else 'rx'
    if RXH.search(s) and ' ' not in s.strip():
        return 'rx'
    words = re.findall(r'[A-Za-z]{2,}', s)
    if len(s) >= 12 and s.count(' ') >= 2 and len(words) >= 3 and not re.search(r'[{}<>;=]{2}', s):
        return 'msg'
    if len(s) >= 10 and KEY.match(s):
        return 'key'
    return None


def tier_of(p, tiers):
    for t, prefs in tiers.items():
        if any(p.startswith(x) for x in prefs):
            return t
    return None


def main():
    root, key, out = sys.argv[1], sys.argv[2], sys.argv[3]
    tiers = TIERS[key]
    files = subprocess.run(['git', '-C', root, 'ls-files', '-z'], capture_output=True,
                           check=True).stdout.decode('utf-8', 'replace').split('\0')
    occ = defaultdict(lambda: defaultdict(set))  # lit -> tier -> files
    cls = {}
    nfiles = defaultdict(int)
    for p in files:
        if not p.endswith(CODE_EXT) or SKIP.search(p):
            continue
        t = tier_of(p, tiers)
        if t is None:
            continue
        try:
            with open(os.path.join(root, p), 'rb') as fh:
                txt = fh.read(1_000_000).decode('utf-8', 'replace')
        except OSError:
            continue
        nfiles[t] += 1
        lits = [next(g for g in m.groups() if g is not None) for m in STR.finditer(txt)]
        lits += [m.group(1) for m in JSRX.finditer(txt)] if p.endswith(('.ts', '.tsx', '.js', '.jsx', '.vue',
                                                                       '.svelte', '.mjs', '.cjs')) else []
        for s in lits:
            c = cls.get(s) or classify(s)
            if c:
                cls[s] = c
                occ[s][t].add(p)
    shared = {s: v for s, v in occ.items() if len(v) >= 2}
    summ = {'files_per_tier': dict(nfiles), 'distinct_by_class': {}, 'shared_by_class': {},
            'shared_errorish_msg': 0}
    for c in ('msg', 'key', 'rx'):
        summ['distinct_by_class'][c] = sum(1 for s in occ if cls[s] == c)
        summ['shared_by_class'][c] = sum(1 for s in shared if cls[s] == c)
    summ['shared_errorish_msg'] = sum(1 for s in shared if cls[s] == 'msg' and ERRW.search(s))
    random.seed(11)
    samples = {}
    for c in ('msg', 'key', 'rx'):
        pool = sorted(s for s in shared if cls[s] == c)
        pick = random.sample(pool, min(30, len(pool)))
        samples[c] = [{'lit': s, 'where': {t: sorted(fs)[:3] for t, fs in shared[s].items()}} for s in pick]
    err = sorted(s for s in shared if cls[s] == 'msg' and ERRW.search(s))
    samples['errorish_msg'] = [{'lit': s, 'where': {t: sorted(fs)[:3] for t, fs in shared[s].items()}}
                               for s in err[:60]]
    with open(out, 'w') as fh:
        json.dump({'summary': summ, 'samples': samples}, fh, indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
