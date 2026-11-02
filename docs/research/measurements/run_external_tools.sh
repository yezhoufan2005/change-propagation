#!/usr/bin/env bash
# Measure ast-grep and jscpd on the two ThingsPanel clones: runtime, peak memory, output size,
# and whether .vue files can be searched. Results: /tmp/cpf-measure/external/results.jsonl
#
# Run it yourself in a terminal. Claude Code's auto mode blocks Claude from running npx downloads.
#   bash docs/research/measurements/run_external_tools.sh
#
# What it does:
# - downloads @ast-grep/cli and jscpd through npx, with the npm cache in /tmp/cpf-npm
# - only reads the clones under /tmp/cpf-measure/repos and never runs code from them
# - writes only under /tmp/cpf-measure/external, and deletes its scaled copy when done
set -u

REPOS=/tmp/cpf-measure/repos
BE=$REPOS/thingspanel-backend-community
FE_ROOT=$REPOS/thingspanel-frontend-community
FE=$FE_ROOT/src
OUT=/tmp/cpf-measure/external
RES=$OUT/results.jsonl
export npm_config_cache=/tmp/cpf-npm npm_config_update_notifier=false npm_config_fund=false npm_config_audit=false

command -v npx > /dev/null || { echo "npx not found; open a terminal where node is on PATH"; exit 1; }
[ -d "$BE" ] && [ -d "$FE" ] || { echo "clones missing under $REPOS"; exit 1; }
[ -d /tmp/cpf-measure/scaled ] && { echo "another measurement is running (/tmp/cpf-measure/scaled exists); try later"; exit 1; }
rm -rf "$OUT" && mkdir -p "$OUT"
echo "node $(node --version), npm $(npm --version)"; df -h /tmp | tail -n 1

# measure LABEL OUTFILE CMD...: run CMD with stdout to OUTFILE, append one JSON line to $RES
measure() {
  local label=$1 out=$2
  shift 2
  /usr/bin/time -l "$@" < /dev/null > "$out" 2> "$out.err"
  local code=$?
  python3 -I - "$label" "$out" "$code" "$RES" <<'PY'
import json, os, re, sys
label, out, code, res = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
err = open(out + '.err', encoding='utf-8', errors='replace').read()
cut = re.search(r'^\s*[\d.]+ real', err, re.M)
own = (err[:cut.start()] if cut else err).strip().splitlines()
real = re.search(r'([\d.]+) real', err)
rss = re.search(r'(\d+)\s+maximum resident set size', err)
row = {'label': label, 'exit': code, 'seconds': float(real.group(1)) if real else None,
       'max_rss_mb': round(int(rss.group(1)) / 2**20, 1) if rss else None, 'stdout_bytes': os.path.getsize(out)}
if out.endswith('.json'):
    try:
        row['items'] = len(json.load(open(out, encoding='utf-8')))
    except ValueError:
        row['items'] = None
if code:
    row['stderr_tail'] = own[-8:]
with open(res, 'a', encoding='utf-8') as f:
    f.write(json.dumps(row, ensure_ascii=False) + '\n')
print(f"{label}: exit={code} {row['seconds']}s rss={row['max_rss_mb']}MB out={row['stdout_bytes']}B items={row.get('items')}")
PY
}

echo "== tools (the first npx call of each package includes the download)"
measure npx-ast-grep-first "$OUT/ast-grep-version.txt" npx -y -p @ast-grep/cli ast-grep --version
measure npx-jscpd-first "$OUT/jscpd-version.txt" npx -y jscpd --version
measure npx-ast-grep-cached "$OUT/ast-grep-version-2.txt" npx -y -p @ast-grep/cli ast-grep --version
SG=$(npx -y -p @ast-grep/cli -c 'command -v ast-grep')
JSCPD=$(npx -y -p jscpd -c 'command -v jscpd')
[ -x "$SG" ] && [ -x "$JSCPD" ] || { echo "could not resolve tool paths: '$SG' '$JSCPD'"; exit 1; }
measure ast-grep-direct "$OUT/ast-grep-version-3.txt" "$SG" --version
echo "ast-grep: $(cat "$OUT/ast-grep-version.txt")  jscpd: $(cat "$OUT/jscpd-version.txt")"

echo "== ast-grep: Go backend and the .ts sources of the frontend"
measure sg-go-subscribe "$OUT/sg-go-subscribe.json" "$SG" run --lang go --pattern '$A.Subscribe($$$B)' --json=compact "$BE"
measure sg-go-publish "$OUT/sg-go-publish.json" "$SG" run --lang go --pattern '$A.Publish($$$B)' --json=compact "$BE"
measure sg-go-unmarshal "$OUT/sg-go-unmarshal.json" "$SG" run --lang go --pattern 'json.Unmarshal($A, $B)' --json=compact "$BE"
measure sg-ts-watch "$OUT/sg-ts-watch.json" "$SG" run --lang ts --pattern 'watch($$$A)' --json=compact "$FE"
measure sg-ts-get "$OUT/sg-ts-get.json" "$SG" run --lang ts --pattern '$A.get($$$B)' --json=compact "$FE"

echo "== ast-grep: can it search the script blocks of .vue files?"
measure sg-vue-globs "$OUT/sg-vue-globs.json" "$SG" run --lang ts --pattern 'watch($$$A)' --globs '*.vue' --json=compact "$FE"
mkdir -p "$OUT/vuecfg/rules"
printf 'ruleDirs: [rules]\nlanguageGlobs:\n  html: ["*.vue"]\n' > "$OUT/vuecfg/sgconfig.yml"
for lang in ts js; do
  measure "sg-vue-html-$lang-flag" "$OUT/sg-vue-html-$lang-flag.json" "$SG" run -c "$OUT/vuecfg/sgconfig.yml" --lang "$lang" --pattern 'watch($$$A)' --json=compact "$FE"
  (cd "$OUT/vuecfg" && measure "sg-vue-html-$lang-cwd" "$OUT/sg-vue-html-$lang-cwd.json" "$SG" run --lang "$lang" --pattern 'watch($$$A)' --json=compact "$FE")
done
# Reference count: watch( calls in .vue files found by a plain regex
python3 -I - "$FE" "$RES" <<'PY'
import json, os, re, sys
fe, res = sys.argv[1:3]
call = re.compile(r'(?<![\w$.])watch\s*\(')
n = files = 0
for d, dirs, names in os.walk(fe):
    for name in names:
        if name.endswith('.vue'):
            files += 1
            n += len(call.findall(open(os.path.join(d, name), encoding='utf-8', errors='replace').read()))
row = {'label': 'regex-vue-watch-calls', 'vue_files': files, 'count': n}
open(res, 'a', encoding='utf-8').write(json.dumps(row) + '\n')
print(row)
PY

echo "== ast-grep on about 100k files (the .go/.ts/.js/.vue files copied N times)"
SC=$OUT/scaled
python3 -I - "$BE" "$FE_ROOT" "$SC" <<'PY'
import os, shutil, sys
roots, dst = sys.argv[1:3], sys.argv[3]
files = []
for root in roots:
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ('.git', 'node_modules')]
        files += [os.path.join(d, n) for n in names if os.path.splitext(n)[1] in ('.go', '.ts', '.js', '.vue')]
copies = -(-100000 // len(files))
base = os.path.dirname(roots[0])
for i in range(copies):
    for f in files:
        target = os.path.join(dst, f'copy{i:03d}', os.path.relpath(f, base))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(f, target)
print(f'{len(files)} source files x {copies} copies = {len(files) * copies} files')
PY
du -sh "$SC"
measure sg-scaled-go "$OUT/sg-scaled-go.json" "$SG" run --lang go --pattern '$A.Subscribe($$$B)' --json=compact "$SC"
measure sg-scaled-ts "$OUT/sg-scaled-ts.json" "$SG" run --lang ts --pattern 'watch($$$A)' --json=compact "$SC"
rm -rf "$SC"

echo "== jscpd clone detection (default thresholds: 50 tokens, 5 lines)"
measure jscpd-frontend "$OUT/jscpd-frontend.txt" "$JSCPD" --silent --reporters json --output "$OUT/jscpd-frontend" --pattern '**/*.{ts,js,vue}' "$FE"
measure jscpd-backend "$OUT/jscpd-backend.txt" "$JSCPD" --silent --reporters json --output "$OUT/jscpd-backend" --pattern '**/*.go' "$BE"
python3 -I - "$OUT" "$RES" <<'PY'
import json, os, sys
out, res = sys.argv[1:3]
for name in ('jscpd-frontend', 'jscpd-backend'):
    path = os.path.join(out, name, 'jscpd-report.json')
    if not os.path.exists(path):
        print(f'{name}: no report written')
        continue
    stats = json.load(open(path, encoding='utf-8'))['statistics']
    total = stats.get('total', {})
    row = {'label': f'{name}-report', 'report_bytes': os.path.getsize(path),
           'formats': {k: v.get('sources') for k, v in stats.get('formats', {}).items()},
           **{k: total.get(k) for k in ('sources', 'lines', 'clones', 'duplicatedLines', 'percentage')}}
    open(res, 'a', encoding='utf-8').write(json.dumps(row) + '\n')
    print(row)
PY

echo "== done. Results: $RES"
echo "Tell Claude the run has finished; it reads the results from there."
