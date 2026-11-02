"""Mine -U0 hunks from git history and key them by abstracted edit.

usage: python3 -I mine.py <repo> <go|web> <out.json>
"""
import json, re, subprocess, sys, difflib
sys.path.insert(0, '/tmp/va-scripts')
from vtok import tokens, abs2, trivial_line, norm0

repo, lang, out = sys.argv[1], sys.argv[2], sys.argv[3]
if lang == 'go':
    specs = ['*.go', ':(exclude)vendor/*', ':(exclude)docs/*', ':(exclude)*_test.go',
             ':(exclude)*.pb.go', ':(exclude)internal/query/*', ':(exclude)internal/model/*',
             ':(exclude)third_party/*']
else:
    specs = ['*.vue', '*.ts', '*.js', '*.tsx', ':(exclude)*node_modules/*', ':(exclude)*dist/*',
             ':(exclude)*.d.ts', ':(exclude)*locales/*', ':(exclude)*i18n/*', ':(exclude)public/*',
             ':(exclude)*.min.js', ':(exclude)*mock*']
MAXFILES = 40

cmd = ['git', '-C', repo, '-c', 'core.quotepath=off', 'log', '--no-merges', '--reverse',
       '--no-renames', '-p', '-U0', '--format=@@@COMMIT %H %ct %s', '--'] + specs
p = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
lines = p.stdout.split('\n')

HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
commits, hunks = [], []
cur = None; fpath = None; h = None


def flush():
    global h
    if h is not None:
        hunks.append(h)
    h = None


for ln in lines:
    if ln.startswith('@@@COMMIT '):
        flush()
        _, sha, ts, *subj = ln.split(' ', 3)
        cur = {'i': len(commits), 'sha': sha, 'ts': int(ts), 'subj': subj[0] if subj else '', 'files': set()}
        commits.append(cur)
        continue
    if ln.startswith('diff --git '):
        flush(); fpath = None; continue
    if ln.startswith('+++ '):
        fpath = ln[6:] if ln.startswith('+++ b/') else None
        if fpath: cur['files'].add(fpath)
        continue
    if ln.startswith('--- '):
        continue
    m = HUNK.match(ln)
    if m and fpath:
        flush()
        o, ol, n, nl = m.group(1), m.group(2), m.group(3), m.group(4)
        h = {'c': cur['i'], 'f': fpath, 'os': int(o), 'ol': int(ol) if ol is not None else 1,
             'ns': int(n), 'nl': int(nl) if nl is not None else 1, 'rem': [], 'add': []}
        continue
    if h is not None:
        if ln.startswith('-'):
            h['rem'].append(ln[1:])
        elif ln.startswith('+'):
            h['add'].append(ln[1:])
flush()


def seq(ls):
    t = []
    for l in ls:
        if not trivial_line(l):
            t.extend(tokens(l))
    return t


kept = []
for h in hunks:
    c = commits[h['c']]
    if len(c['files']) > MAXFILES:
        continue
    rem = [l for l in h['rem'] if not trivial_line(l)]
    add = [l for l in h['add'] if not trivial_line(l)]
    if not rem and not add:
        continue
    if [norm0(x) for x in rem] == [norm0(x) for x in add]:
        continue  # whitespace-only
    if len(rem) > 8 or len(add) > 8:
        continue
    rt, at = seq(h['rem']), seq(h['add'])
    ra, aa = abs2(rt), abs2(at)
    sm = difflib.SequenceMatcher(None, ra, aa, autojunk=False)
    delta = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != 'equal':
            delta += ['-' + x for x in ra[i1:i2]] + ['+' + x for x in aa[j1:j2]]
    if not delta:  # pure local-identifier rename: keep raw tokens
        sm = difflib.SequenceMatcher(None, [t for _, t in rt], [t for _, t in at], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != 'equal':
                delta += ['-' + t for _, t in rt[i1:i2]] + ['+' + t for _, t in at[j1:j2]]
    h['kline'] = ' '.join(ra) + ' => ' + ' '.join(aa)
    h['kdelta'] = ' '.join(delta)
    h['kind'] = 'mod' if rem else 'add'
    h['rem'], h['add'] = rem, add
    kept.append(h)

for c in commits:
    c['files'] = len(c['files'])
json.dump({'commits': commits, 'hunks': kept}, open(out, 'w'))
print('commits', len(commits), 'hunks_raw', len(hunks), 'kept', len(kept),
      'mod', sum(1 for h in kept if h['kind'] == 'mod'), 'add', sum(1 for h in kept if h['kind'] == 'add'))
