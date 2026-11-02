#!/usr/bin/env python3
"""Count files and lines by extension under one or more roots, skipping .git and node_modules.

Usage: python3 repo_stats.py ROOT [ROOT ...]
"""
import collections
import os
import sys

SKIP_DIRS = {'.git', 'node_modules'}
TEXT_EXT = {'.go', '.py', '.js', '.ts', '.tsx', '.jsx', '.vue', '.json', '.yaml', '.yml', '.md', '.css',
            '.scss', '.less', '.html', '.sql', '.sh', '.toml', '.mod', '.sum', '.txt', '.svg'}

for root in sys.argv[1:]:
    files, lines = collections.Counter(), collections.Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower() or '(none)'
            files[ext] += 1
            if ext in TEXT_EXT:
                try:
                    with open(os.path.join(dirpath, name), 'rb') as f:
                        lines[ext] += f.read().count(b'\n')
                except OSError:
                    pass
    print(f'== {os.path.basename(root.rstrip("/"))}: {sum(files.values())} files, {sum(lines.values())} text lines')
    print('   ' + ', '.join(f'{ext} {n} ({lines[ext]} lines)' if ext in TEXT_EXT else f'{ext} {n}'
                           for ext, n in files.most_common(14)))
