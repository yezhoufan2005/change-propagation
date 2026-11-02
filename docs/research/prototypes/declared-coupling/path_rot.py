#!/usr/bin/env python3
"""Path-pointer rot: do file paths named in sync-style comments still exist?

Usage: python3 -I path_rot.py <out_dir> <repos_dir>
For every path-like token in a hit's text (families sync/update_too/must_match/
mirror_of), classify: exact (root- or source-dir-relative), suffix (some tracked
path ends with it), basename-only, missing.
"""
import glob, json, os, posixpath, re, subprocess, sys
from collections import Counter

TOK = re.compile(r'(?:[\w@.\-]+/)+[\w@.\-]+\.(?:go|ts|tsx|js|jsx|mjs|cjs|py|kt|java|swift|dart|proto|sql|'
                 r'md|yml|yaml|json|toml|html|tmpl|hbs|css|scss|vue|svelte|rs|cc|h|m|mm|xml|gradle|kts)\b')


def main():
    out_dir, repos = sys.argv[1], sys.argv[2]
    total = Counter()
    for f in sorted(glob.glob(os.path.join(out_dir, '*.sync.json'))):
        name = os.path.basename(f).split('.')[0]
        root = os.path.join(repos, name, 'src')
        tracked = subprocess.run(['git', '-C', root, 'ls-files', '-z'], capture_output=True,
                                 check=True).stdout.decode('utf-8', 'replace').split('\0')
        tset = set(tracked)
        bases = Counter(p.rsplit('/', 1)[-1] for p in tracked)
        c = Counter()
        missing = []
        seen = set()
        for h in json.load(open(f))['hits']:
            if h['lang'] == 'doc':
                continue
            for t in TOK.findall(h['text']):
                t0 = t.lstrip('/')
                key = (h['file'], t0)
                if key in seen or t0.startswith(('http', 'www.')):
                    continue
                seen.add(key)
                rel = posixpath.normpath(posixpath.join(posixpath.dirname(h['file']), t0))
                if t0 in tset or rel in tset:
                    c['exact'] += 1
                elif any(p.endswith('/' + t0) for p in tracked):
                    c['suffix'] += 1
                elif bases[t0.rsplit('/', 1)[-1]]:
                    c['basename_only'] += 1
                    missing.append((h['file'], h['line'], t0, 'basename_only'))
                else:
                    c['missing'] += 1
                    missing.append((h['file'], h['line'], t0, 'missing'))
        total.update(c)
        print(name, dict(c))
        for m in missing[:12]:
            print('   ', m)
    print('TOTAL', dict(total))


if __name__ == '__main__':
    main()
