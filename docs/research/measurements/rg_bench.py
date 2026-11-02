#!/usr/bin/env python3
"""Time ripgrep queries over one or more roots (tier-0 retrieval measurement).

Each query runs twice ("first run", "repeat run") in two output modes:
  full  = rg -n --no-heading   (path:line:text, what an agent would read)
  files = rg -l                (paths only)
Records wall time (time.perf_counter, includes process spawn), matching lines,
files, output chars, est. tokens (chars/4), CJK chars, and the files that
contribute most output chars.

rg binary: $RG_BIN if set; else $CLAUDE_CODE_EXECPATH with argv[0]=rg (the
ripgrep embedded in Claude Code); else 'rg' on PATH.

Usage: python3 -I rg_bench.py --out OUT.json [--only id,id] ROOT [ROOT ...]
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import time

# (id, what it represents, extra rg flags, pattern)
QUERIES = [
    ('snake', 'payload field, snake_case', ['-F'], 'device_config_id'),
    ('camel', 'payload field, camelCase', ['-F'], 'deviceConfigId'),
    ('pascal', 'payload field, PascalCase', ['-F'], 'DeviceConfigId'),
    ('pascal_go', 'payload field, Go initialism', ['-F'], 'DeviceConfigID'),
    ('kebab', 'payload field, kebab-case', ['-F'], 'device-config-id'),
    ('variants_re', 'all variants in one regex', ['-i'], r'device[-_]?config[-_]?id'),
    ('mqtt_topic', 'MQTT topic literal', ['-F'], 'devices/telemetry/control'),
    ('ws_endpoint', 'WebSocket endpoint', ['-F'], 'online/status/ws'),
    ('date_fmt_re', 'regex: inline date formatting', [],
     r"""(dayjs|moment)\([^)]*\)\.format\(['"]YYYY-MM-DD [Hh]{2}:mm:ss"""),
]
CJK = re.compile('[　-〿㐀-䶿一-鿿＀-￯]')


def rg_cmd():
    if os.environ.get('RG_BIN'):
        return [os.environ['RG_BIN']], None
    exe = os.environ.get('CLAUDE_CODE_EXECPATH')
    if exe and os.access(exe, os.X_OK):
        return ['rg'], exe
    found = shutil.which('rg')
    if not found:
        sys.exit('ripgrep not found; set RG_BIN')
    return [found], None


def run_rg(argv0, exe, flags, pattern, roots):
    # Run from the roots' common parent with relative paths, as an agent working in a
    # workspace would; a single root is searched as cwd (paths print without './').
    if len(roots) == 1:
        cwd, rel = roots[0], []
    else:
        cwd = os.path.commonpath(roots)
        rel = [os.path.relpath(r, cwd) for r in roots]
    cmd = argv0 + ['--no-config', '--color', 'never'] + flags + ['-e', pattern, '--'] + rel
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, executable=exe, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dt = time.perf_counter() - t0
    if proc.returncode not in (0, 1):  # 1 = no match
        raise RuntimeError(proc.stderr.decode('utf-8', 'replace')[:500])
    return dt, proc.stdout.decode('utf-8', 'replace')


def root_of(path, roots):
    if len(roots) == 1:
        return os.path.basename(roots[0].rstrip('/'))
    first = path.split('/', 1)[0]
    for r in roots:
        if os.path.basename(r.rstrip('/')) == first:
            return first
    return '?'


def measure(qid, what, flags, pattern, roots, argv0, exe):
    rec = {'id': qid, 'what': what, 'pattern': pattern, 'flags': flags}
    for mode, mflags in (('full', ['-n', '--no-heading']), ('files', ['-l'])):
        runs = []
        for _ in range(2):
            dt, out = run_rg(argv0, exe, flags + mflags, pattern, roots)
            runs.append(dt)
        lines = out.splitlines()
        m = {'first_run_s': round(runs[0], 4), 'repeat_run_s': round(runs[1], 4),
             'lines': len(lines), 'chars': len(out), 'est_tokens': len(out) // 4,
             'cjk_chars': len(CJK.findall(out))}
        if mode == 'full':
            per_file = collections.Counter()
            per_root = collections.Counter()
            for ln in lines:
                path = ln.split(':', 1)[0]
                per_file[path] += len(ln) + 1
                per_root[root_of(path, roots)] += 1
            m['files'] = len(per_file)
            m['lines_per_root'] = dict(per_root)
            m['max_line_chars'] = max((len(ln) for ln in lines), default=0)
            m['top_files_by_chars'] = [(p, c) for p, c in per_file.most_common(3)]
        rec[mode] = m
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('roots', nargs='+')
    a = ap.parse_args()
    roots = [os.path.abspath(r) for r in a.roots]
    only = set(filter(None, a.only.split(',')))
    argv0, exe = rg_cmd()
    ver = subprocess.run(argv0 + ['--version'], executable=exe, stdout=subprocess.PIPE).stdout.decode()
    results = {'rg_version': ver.splitlines()[0], 'roots': roots, 'queries': []}
    t_all = time.perf_counter()
    for qid, what, flags, pattern in QUERIES:
        if only and qid not in only:
            continue
        rec = measure(qid, what, flags, pattern, roots, argv0, exe)
        results['queries'].append(rec)
        f, l = rec['full'], rec['files']
        print(f"{qid:12s} full {f['first_run_s']*1000:7.1f}/{f['repeat_run_s']*1000:7.1f} ms "
              f"{f['lines']:6d} lines {f['files']:5d} files {f['chars']:9d} ch ~{f['est_tokens']:7d} tok | "
              f"-l {l['first_run_s']*1000:7.1f}/{l['repeat_run_s']*1000:7.1f} ms {l['chars']:7d} ch "
              f"~{l['est_tokens']:6d} tok | per-root {f['lines_per_root']}", flush=True)
    results['total_s'] = round(time.perf_counter() - t_all, 3)
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print('total', results['total_s'], 's ->', a.out)


if __name__ == '__main__':
    main()
