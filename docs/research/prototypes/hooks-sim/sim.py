# Simulate a tier-0 PostToolUse(Edit|Write) hook that uses the edit payload as the query.
# Inputs: pilot subagent transcripts (real first Edit/Write payloads), pilot fixture, gt.json.
import json, glob, os, re, sys
TR = sys.argv[1]; FIX = sys.argv[2]; GT = json.load(open(sys.argv[3]))
STOP = set("const let var return function import export from string number true false null void this class interface type default async await new else case break".split())
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
def subwords(tok):
    parts = re.split(r"_|(?<=[a-z0-9])(?=[A-Z])", tok)
    return {p.lower() for p in parts if len(p) >= 4}
files = {}
for p in glob.glob(FIX + "/**/*", recursive=True):
    if os.path.isfile(p):
        files[os.path.relpath(p, FIX)] = open(p, encoding="utf-8", errors="replace").read()
def query(payloads):
    idents, words, lits_old = set(), set(), set()
    for name, inp in payloads:
        old = inp.get("old_string", "") if name == "Edit" else ""
        new = inp.get("new_string", "") if name == "Edit" else inp.get("content", "")
        for s in (old, new):
            for t in IDENT.findall(s):
                if len(t) >= 4 and t not in STOP:
                    idents.add(t); words |= subwords(t)
        lo = set(re.findall(r"\b\d+\b", old)); ln = set(re.findall(r"\b\d+\b", new))
        lits_old |= (lo - ln)
    hit_ident, hit_lit = set(), set()
    for rel, txt in files.items():
        if any(re.search(r"\b" + re.escape(t) + r"\b", txt) for t in idents):
            hit_ident.add(rel)
        for line in txt.splitlines():
            ll = line.lower()
            if any(re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d.])", line) for n in lits_old) and any(w in ll for w in words):
                hit_lit.add(rel); break
    return idents, lits_old, hit_ident, hit_lit
runs = {}
for p in sorted(glob.glob(TR + "/agent-*.jsonl")):
    try: meta = json.load(open(p.replace(".jsonl", ".meta.json")))
    except Exception: continue
    d = meta.get("description", "")
    m = re.search(r"run (T\d)-c\d", d)
    if not m: continue
    seq = []
    for line in open(p):
        try: o = json.loads(line)
        except Exception: continue
        c = o.get("message", {}).get("content")
        if isinstance(c, list):
            for b in c:
                if b.get("type") == "tool_use" and b.get("name") in ("Edit", "Write"):
                    seq.append((b["name"], b["input"]))
    runs[d.split()[-1]] = (m.group(1), seq)
for run, (task, seq) in sorted(runs.items()):
    sites = [s for s in GT[task]["sites"] if s["tier"] != "exclude"]
    excl = [s for s in GT[task]["sites"] if s["tier"] == "exclude"]
    for k in (1, 2):
        pay = seq[:k]
        edited = {re.sub(r"^.*?/shopfront/", "", inp["file_path"]) for _, inp in pay}
        idents, lits, hi, hl = query(pay)
        hits = (hi | hl) - edited
        target = [s for s in sites if not (set(s["files"]) & edited)]
        found = [s["id"] for s in target if set(s["files"]) & hits]
        fp = [s["id"] for s in excl if set(s["files"]) & hits]
        print(f"{run} first{k} edited={sorted(edited)} idents={len(idents)} oldlits={sorted(lits)} hitfiles={len(hits)}/{len(files)} recall={len(found)}/{len(target)} found={found} exclude_hit={fp}")
