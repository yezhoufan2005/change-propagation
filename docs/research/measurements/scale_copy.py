#!/usr/bin/env python3
"""Build a scaled test workspace: copy selected source files of each ROOT N times.

Copy i of ROOT goes to OUT/<basename(ROOT)>-NN/ (NN = 01..N) with relative paths kept,
so every copy has a unique top-level name. Skips .git and node_modules. Plain copies
(not APFS clones), so each copy has its own pages in the file cache. The copies are
byte-identical, which makes the result good for timing and size, not for hit quality.

Usage: python3 -I scale_copy.py --out DIR --copies N [--ext .go,.vue,...] ROOT [ROOT ...]
"""
import argparse
import os
import shutil
import sys
import time

DEFAULT_EXT = '.go,.py,.vue,.ts,.js,.json,.sql,.yaml,.yml,.md'


def source_files(root, exts):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in ('.git', 'node_modules'))
        for fn in sorted(fns):
            if os.path.splitext(fn)[1].lower() in exts:
                yield os.path.relpath(os.path.join(dp, fn), root)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--copies', type=int, required=True)
    ap.add_argument('--ext', default=DEFAULT_EXT)
    ap.add_argument('roots', nargs='+')
    a = ap.parse_args()
    exts = set(a.ext.split(','))
    if os.path.isdir(a.out) and os.listdir(a.out):
        sys.exit(f'{a.out} is not empty; refusing to write into it')
    t0, n_files, n_bytes = time.perf_counter(), 0, 0
    for root in a.roots:
        root = os.path.abspath(root)
        rels = list(source_files(root, exts))
        size = sum(os.path.getsize(os.path.join(root, r)) for r in rels)
        for i in range(1, a.copies + 1):
            dst = os.path.join(a.out, f'{os.path.basename(root.rstrip("/"))}-{i:02d}')
            for rel in rels:
                os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
                shutil.copyfile(os.path.join(root, rel), os.path.join(dst, rel))
        n_files += len(rels) * a.copies
        n_bytes += size * a.copies
        print(f'{os.path.basename(root)}: {len(rels)} files x {a.copies}', flush=True)
    print(f'total {n_files} files, {n_bytes} bytes, {time.perf_counter() - t0:.1f} s -> {a.out}')


if __name__ == '__main__':
    main()
