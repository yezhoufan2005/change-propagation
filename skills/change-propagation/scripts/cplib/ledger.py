"""The candidate ledger: one JSON file per workspace, one item per position.

Items keep their ID across rescans: they are keyed by path and anchor (the stripped source line),
so a line that moves keeps its ID. Scripts write items; the agent only sets tier, status and note.
"""
import json
import os
import time

DIR = ".change-propagation"
FILE = "ledger.json"
TIERS = ("direct", "coupled", "review", "exclude")
STATUSES = ("open", "asked", "confirmed", "declined", "edited", "listed")
MAX_PER_SEED = 300
ANCHOR = 160


def path(base):
    return os.path.join(base, DIR, FILE)


def new(change, invariants, roots):
    return {"version": 1, "change": change, "invariants": invariants, "roots": roots,
            "seeds": {"names": [], "keys": [], "values": [], "enums": [], "layouts": [], "like": [], "funcs": [], "diff": False, "files": []},
            "scans": [], "items": [], "next_id": 1, "created": now()}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def load(base):
    p = path(base)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(base, ledger):
    d = os.path.join(base, DIR)
    os.makedirs(d, exist_ok=True)
    ignore = os.path.join(d, ".gitignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as fh:
            fh.write("*\n")
    tmp = path(base) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path(base))


def archive(base):
    """Move the current ledger aside so a new change can start."""
    p = path(base)
    if os.path.exists(p):
        os.replace(p, os.path.join(base, DIR, "ledger-%s.json" % time.strftime("%Y%m%d-%H%M%S")))


def anchor(text):
    return " ".join(text.split())[:ANCHOR]


def merge_hits(hits, seed_files):
    """Collapse hits on the same line into one candidate and score it."""
    seed_files = {os.path.normpath(p) for p in seed_files}
    by_pos = {}
    for h in hits:
        c = by_pos.get((h["path"], h["line"]))
        if c is None:
            c = by_pos[(h["path"], h["line"])] = {
                "path": h["path"], "line": h["line"], "anchor": anchor(h["text"]), "layer": h["layer"],
                "stack": h["stack"], "channels": [], "queries": [], "why": [], "score": 0,
                "generated": h["generated"], "comment": h["comment"], "roles": []}
        if h["channel"] not in c["channels"]:
            c["channels"].append(h["channel"])
        q = "%s:%s" % (h["channel"], h["seed"])
        if q not in c["queries"]:
            c["queries"].append(q)
        if h["why"] not in c["why"] and len(c["why"]) < 3:
            c["why"].append(h["why"])
        if h.get("role") and h["role"] not in c["roles"]:
            c["roles"].append(h["role"])
        if h.get("mismatch"):
            c["mismatch"] = True
        c["score"] = max(c["score"], h["score"])
    out = []
    for c in by_pos.values():
        score = c["score"] + 10 * (len(c["channels"]) - 1)
        if os.path.normpath(c["path"]) in seed_files:
            score += 10
        if c["generated"]:
            score -= 30
        c["score"] = max(0, min(100, score))
        out.append(c)
    out.sort(key=lambda c: (-c["score"], c["path"], c["line"]))
    return out


def cap_per_seed(hits):
    """Keep the best MAX_PER_SEED hits of each seed; return (kept, {seed: total}) for broad seeds."""
    by_seed, broad = {}, {}
    for h in hits:
        by_seed.setdefault((h["channel"], h["seed"]), []).append(h)
    kept = []
    for (channel, seed), hs in by_seed.items():
        if len(hs) > MAX_PER_SEED:
            broad["%s:%s" % (channel, seed)] = len(hs)
            hs = sorted(hs, key=lambda h: -h["score"])[:MAX_PER_SEED]
        kept.extend(hs)
    return kept, broad


def upsert(ledger, candidates, found_by):
    """Add new candidates, refresh known ones. Returns the list of new item IDs."""
    index = {(i["path"], i["anchor"]): i for i in ledger["items"]}
    added = []
    for c in candidates:
        item = index.get((c["path"], c["anchor"]))
        if item is None:
            item = dict(c, id="c%d" % ledger["next_id"], tier=None, status="open", note="", found_by=found_by)
            ledger["next_id"] += 1
            ledger["items"].append(item)
            index[(c["path"], c["anchor"])] = item
            added.append(item["id"])
            continue
        item["line"] = c["line"]
        for key in ("channels", "queries", "roles"):
            item[key] = item.get(key, []) + [x for x in c[key] if x not in item.get(key, [])]
        item["why"] = (item["why"] + [w for w in c["why"] if w not in item["why"]])[:3]
        item["score"] = max(item["score"], c["score"])
        if c.get("mismatch"):
            item["mismatch"] = True
    return added


def find(ledger, item_id):
    for item in ledger["items"]:
        if item["id"] == item_id:
            return item
    return None


def unresolved(ledger):
    """Items still needing a decision: open, or asked and unanswered, or confirmed but not yet edited."""
    return [i for i in ledger["items"] if i["status"] in ("open", "asked", "confirmed")
            and i.get("tier") != "exclude"]
