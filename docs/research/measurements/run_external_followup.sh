#!/usr/bin/env bash
# Follow-up to run_external_tools.sh. Uses ast-grep 0.51.0 and jscpd 5.4.2 from the npm cache (the versions
# measured there); a few minutes at most.
#   bash docs/research/measurements/run_external_followup.sh
#
# 1. ast-grep found no Go Subscribe/Publish calls although grep finds 20 and 51. Print how each pattern
#    parses and retry with call-only forms (the ast-grep Go catalog warns that f(x) parses as a type conversion).
# 2. ast-grep searched <script lang="ts"> blocks in .vue files but missed the 36 watch( calls in lang="tsx"
#    blocks. Retry with --lang tsx, with and without a languageInjections rule.
# 3. jscpd 5 reports only exact clones by default and compares lang="ts" and lang="tsx" blocks in separate
#    pools. Measure its renamed, gap-merged, cross-format (--cross-formats js-ts) and function-similarity
#    modes. Each jscpd run stops itself after 10 minutes; the similarity runs come last.
# Only reads the clones under /tmp/cpf-measure/repos and writes only under /tmp/cpf-measure/external/followup.
# Results: /tmp/cpf-measure/external/followup/results.jsonl
set -u

REPOS=/tmp/cpf-measure/repos
BE=$REPOS/thingspanel-backend-community
FE=$REPOS/thingspanel-frontend-community/src
OUT=/tmp/cpf-measure/external/followup
RES=$OUT/results.jsonl
export npm_config_cache=/tmp/cpf-npm npm_config_prefer_offline=true npm_config_update_notifier=false npm_config_fund=false npm_config_audit=false

command -v npx > /dev/null || { echo "npx not found; open a terminal where node is on PATH"; exit 1; }
[ -d "$BE" ] && [ -d "$FE" ] || { echo "clones missing under $REPOS"; exit 1; }
[ -d /tmp/cpf-measure/scaled ] && { echo "another measurement is running (/tmp/cpf-measure/scaled exists); try later"; exit 1; }
rm -rf "$OUT" && mkdir -p "$OUT"
SG=$(npx -y -p @ast-grep/cli@0.51.0 -c 'command -v ast-grep')
JSCPD=$(npx -y -p jscpd@5.4.2 -c 'command -v jscpd')
[ -x "$SG" ] && [ -x "$JSCPD" ] || { echo "could not resolve tool paths: '$SG' '$JSCPD'"; exit 1; }
echo "$("$SG" --version), $("$JSCPD" --version)"

# measure LABEL OUTFILE CMD...: run CMD with stdout to OUTFILE, append one JSON line to $RES (as in run_external_tools.sh)
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

echo "== 1. ast-grep: Go method calls"
printf 'package x\n' > "$OUT/empty.go"
for p in '$A.Subscribe($$$B)' '$A.Subscribe($B, $C, $D)' 'json.Unmarshal($A, $B)' 'func t() { $A.Subscribe($$$B) }'; do
  echo "--- pattern: $p"
  "$SG" run --lang go --pattern "$p" --debug-query=ast "$OUT/empty.go" 2>&1
done > "$OUT/debug-query.txt"
for m in Subscribe Publish; do
  measure "sg-go-$m-context" "$OUT/sg-go-$m-context.json" "$SG" run --lang go --pattern "func t() { \$A.$m(\$\$\$B) }" --selector call_expression --json=compact "$BE"
done
measure sg-go-Subscribe-3args "$OUT/sg-go-Subscribe-3args.json" "$SG" run --lang go --pattern '$A.Subscribe($B, $C, $D)' --json=compact "$BE"
measure sg-go-Publish-4args "$OUT/sg-go-Publish-4args.json" "$SG" run --lang go --pattern '$A.Publish($B, $C, $D, $E)' --json=compact "$BE"
cat > "$OUT/go-subscribe-rule.yml" <<'YML'
id: go-subscribe-call
language: go
rule:
  kind: call_expression
  has:
    field: function
    regex: '\.Subscribe$'
YML
measure sg-go-Subscribe-rule "$OUT/sg-go-Subscribe-rule.json" "$SG" scan -r "$OUT/go-subscribe-rule.yml" --json=compact "$BE"

echo "== 2. ast-grep: .vue files with <script lang=\"tsx\">"
mkdir -p "$OUT/vue-builtin/rules" "$OUT/vue-inject/rules"
printf 'ruleDirs: [rules]\nlanguageGlobs:\n  html: ["*.vue"]\n' > "$OUT/vue-builtin/sgconfig.yml"
cat > "$OUT/vue-inject/sgconfig.yml" <<'YML'
ruleDirs: [rules]
languageGlobs:
  html: ["*.vue"]
languageInjections:
- hostLanguage: html
  rule:
    kind: raw_text
    pattern: $CONTENT
    inside:
      kind: script_element
      has:
        kind: attribute_value
        regex: '^tsx$'
        stopBy: end
  injected: tsx
YML
for cfg in vue-builtin vue-inject; do
  for lang in ts tsx; do
    measure "sg-$cfg-$lang" "$OUT/sg-$cfg-$lang.json" "$SG" run -c "$OUT/$cfg/sgconfig.yml" --lang "$lang" --pattern 'watch($$$A)' --json=compact "$FE"
  done
done

echo "== 3. jscpd 5: renamed, gap-merged, cross-format and function-similarity clones"
# STOP_AFTER SECONDS CMD...: run CMD in its own process group and kill the group after SECONDS or on Ctrl-C
STOP_AFTER='import os, signal, subprocess, sys
p = subprocess.Popen(sys.argv[2:], start_new_session=True)
try:
    sys.exit(p.wait(timeout=float(sys.argv[1])))
except (subprocess.TimeoutExpired, KeyboardInterrupt) as e:
    os.killpg(p.pid, signal.SIGKILL)
    p.wait()
    sys.exit("stopped: %s" % type(e).__name__)'
# run_jscpd SIDE MODE FLAGS...: one jscpd run on the frontend src or the Go backend, with extra FLAGS
run_jscpd() {
  local side=$1 mode=$2 root=$BE pat='**/*.go'
  shift 2
  if [ "$side" = frontend ]; then root=$FE; pat='**/*.{ts,js,vue}'; fi
  measure "jscpd-$side-$mode" "$OUT/jscpd-$side-$mode.txt" python3 -I -c "$STOP_AFTER" 600 \
    "$JSCPD" "$@" --silent --reporters json --output "$OUT/jscpd-$side-$mode" --pattern "$pat" "$root"
}
for side in frontend backend; do
  run_jscpd "$side" default
  run_jscpd "$side" renamed --ignore-identifiers --ignore-literals
  run_jscpd "$side" gap3 --max-gap-lines 3
  run_jscpd "$side" renamed-gap3 --ignore-identifiers --ignore-literals --max-gap-lines 3
done
run_jscpd frontend cross --cross-formats js-ts
run_jscpd frontend cross-renamed --cross-formats js-ts --ignore-identifiers --ignore-literals
for side in frontend backend; do
  run_jscpd "$side" similarity --similarity=0.8
done
python3 -I - "$OUT" "$RES" <<'PY'
import collections, json, os, sys
out, res = sys.argv[1:3]
for name in sorted(os.listdir(out)):
    path = os.path.join(out, name, 'jscpd-report.json')
    if not os.path.isfile(path):
        continue
    try:
        dups = json.load(open(path, encoding='utf-8'))['duplicates']
        sims = sorted(d['similarity'] for d in dups if isinstance(d.get('similarity'), (int, float)))
        row = {'label': f'{name}-report', 'report_bytes': os.path.getsize(path), 'clones': len(dups),
               'kinds': dict(collections.Counter(d.get('kind') for d in dups)),
               'methods': dict(collections.Counter(d['method'] for d in dups if d.get('method'))),
               'cross_dir': sum(os.path.dirname(d['firstFile']['name']) != os.path.dirname(d['secondFile']['name']) for d in dups),
               'similarity_min_median': [sims[0], sims[len(sims) // 2]] if sims else None}
    except (KeyError, TypeError, ValueError) as e:
        row = {'label': f'{name}-report', 'error': repr(e)}
    with open(res, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row) + '\n')
    print(row)
PY

echo "== done. Results: $RES"
echo "Tell Claude the run has finished; it reads the results from there."
