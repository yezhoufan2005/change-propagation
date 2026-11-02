#!/usr/bin/env python3
"""change-propagation tier 0: find the other places a change must reach, offline.

Commands (run from the workspace; the ledger lives in .change-propagation/ledger.json):
  seed    record the change, invariants and seeds (--name, --key, --value with --near, --file, --root)
  scan    search every channel, write all candidates to the ledger, print a short summary
  show    print the block around candidates: show c3 c7 [--context N]
  mark    record decisions: mark c1,c2 direct c3-c5 coupled/asked "why" [--verify]
  add     track positions found by reading code: add a.vue:42 --why TEXT [--tier direct]
  verify  rerun the queries on the edited code, mark direct items whose block changed as edited,
          and report residue and unresolved items
  status  counts per tier and status, and the items still needing a decision
Standard library only (Python 3.9+). Reads files; writes only .change-propagation/.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cplib import channels, contracts, declared, enums, gitread, history, layout, ledger as L, shingle, show as S  # noqa: E402

TOP = 30
SHOW_ALL = 45          # scan lists every item when the ledger has at most this many
PER_FILE = 3
LAYER_ORDER = ["frontend", "backend", "locale", "config", "sql", "docs", "test", "other"]
LAYER_ZH = {"frontend": "前端", "backend": "后端", "locale": "语言包", "config": "配置", "sql": "SQL",
            "docs": "文档", "test": "测试", "other": "其他"}


def base_dir(new=False):
    """The workspace: the nearest directory up from here that has a ledger, so the commands after
    seed also work from a subdirectory. A new ledger goes in the current directory when it is
    outside git or has repositories below it (a workspace of several, see history.repos), else in
    the root of the repository it is in."""
    here = d = os.getcwd()
    while not new:
        if os.path.isfile(L.path(d)):
            return d
        d, prev = os.path.dirname(d), d
        if d == prev:
            break
    found = gitread.find_repo(here)
    if found is None or history.below(here):
        return here
    return found[0]


def split_list(values):
    out = []
    for v in values or []:
        out.extend(x.strip() for x in v.split(",") if x.strip())
    return out


def resolver(roots, base):
    """Map a path as the agent wrote it to a path relative to base. A path that exists neither from
    the current directory nor from base (as the output prints it) is matched as a suffix of the
    files under the roots (notice-message.vue, notice/notice-message.vue), so the agent can seed
    without locating the file first."""
    listing = []

    def resolve(path):
        for p in (path, os.path.join(base, path)):
            if os.path.exists(p):
                return os.path.relpath(os.path.abspath(p), base)
        if not listing:
            for r in roots:
                listing.extend(os.path.relpath(os.path.join(r, x), base) for x in channels.walk.list_files(r))
        want = "/" + os.path.normpath(path).lstrip("./")
        found = [x for x in listing if ("/" + x).endswith(want)]
        if len(found) == 1:
            return found[0]
        if not found:
            sys.exit("找不到 %s：根目录下没有这个文件" % path)
        sys.exit("%s 有 %d 个同名文件，写长一点的路径：%s" % (path, len(found), "，".join(found[:6])))
    return resolve


def need_ledger(base):
    led = L.load(base)
    if led is None:
        sys.exit("还没有 ledger：先运行 seed")
    return led


def cmd_seed(args, base):
    led = L.load(base)
    if led is not None and args.new:
        L.archive(base)
        led = None
    if led is None:
        if not args.change:
            sys.exit("新的 ledger 需要 --change 写明改动")
        roots = [os.path.abspath(r) for r in (args.root or [base])]
        led = L.new(args.change, [], roots)
    elif args.change:
        led["change"] = args.change
    for r in args.root or []:
        r = os.path.abspath(r)
        if r not in led["roots"]:
            led["roots"].append(r)
    led["invariants"] += [i for i in args.invariant or [] if i not in led["invariants"]]
    seeds = led["seeds"]
    seeds.setdefault("enums", [])
    for e in args.enum or []:
        vals = split_list([e])
        if len(vals) < 2:
            sys.exit("--enum 要写成 改动的值,兄弟值,...，例如 --enum info,warning,error")
        if vals not in seeds["enums"]:
            seeds["enums"].append(vals)
    for key in ("layouts", "like", "funcs"):
        seeds.setdefault(key, [])
    seeds["diff"] = seeds.get("diff") or bool(args.diff)
    resolve = resolver(led["roots"], base)
    for fn in args.func or []:
        path, _, name = fn.rpartition(":")
        if not path or not name:
            sys.exit("--func 要写成 path:函数名")
        spec = "%s:%s" % (resolve(path), name)
        if spec not in seeds["funcs"]:
            seeds["funcs"].append(spec)
    for lay in args.layout or []:
        if lay not in layout.LAYOUTS:
            sys.exit("--layout 可选：%s" % "、".join(layout.LAYOUTS))
        if lay not in seeds["layouts"]:
            seeds["layouts"].append(lay)
    for ex in split_list(args.like):
        rel = resolve(ex)
        if rel not in seeds["like"]:
            seeds["like"].append(rel)
    files = [resolve(f) for f in split_list(args.file)]
    for key, vals in (("names", args.name), ("keys", args.key), ("files", files)):
        seeds[key] += [v for v in vals or [] if v not in seeds[key]]
    near = split_list(args.near)
    for v in args.value or []:
        if channels.needs_near(v) and not near:
            sys.exit("值 %r 是数字或太短，单独搜会淹没结果；用 --near 给出上下文词，例如 --near password,pwd,密码" % v)
        entry = {"value": v, "near": near if channels.needs_near(v) else []}
        if entry not in seeds["values"]:
            seeds["values"].append(entry)
    L.save(base, led)
    print("ledger：%s" % os.path.relpath(L.path(base), os.getcwd()))
    print("改动：%s" % led["change"])
    for inv in led["invariants"]:
        print("不变量：%s" % inv)
    print("工作区：%s（输出里的路径都相对于它）" % base)
    print("根目录：%s" % "，".join(os.path.relpath(r, base) if r != base else "." for r in led["roots"]))
    print("种子：%s" % describe_seeds(seeds))
    if args.scan:
        cmd_scan(args, base)


def describe_seeds(seeds):
    parts = ["name %s" % n for n in seeds["names"]] + ["key %s" % k for k in seeds["keys"]]
    parts += ["value %s%s" % (v["value"], " near " + ",".join(v["near"]) if v["near"] else "") for v in seeds["values"]]
    parts += ["enum %s（改 %s）" % (",".join(e), e[0]) for e in seeds.get("enums", [])]
    parts += ["layout %s" % x for x in seeds.get("layouts", [])] + ["like %s" % x for x in seeds.get("like", [])]
    parts += ["func %s" % x for x in seeds.get("funcs", [])] + (["diff（未提交的改动）"] if seeds.get("diff") else [])
    parts += ["file %s" % f for f in seeds["files"]]
    return "；".join(parts) or "（无）"


def run_queries(led, base):
    t0 = time.time()
    files, unreadable = channels.load_corpus(led["roots"], base)
    seeds, hits, errors = led["seeds"], [], []
    for n in seeds["names"]:
        hits += channels.name_channel(files, n)
    for k in seeds["keys"]:
        hits += contracts.contract_channel(files, k)
    for v in seeds["values"]:
        try:
            hits += channels.value_channel(files, v["value"], v["near"])
        except ValueError as e:
            errors.append(str(e))
    for e in seeds.get("enums", []):
        hits += enums.enum_channel(files, e)
    for lay in seeds.get("layouts", []):
        hits += layout.header_in_scroll(files)
    for fn in seeds.get("funcs", []):
        try:
            hits += shingle.func_channel(files, fn)
        except ValueError as e:
            errors.append(str(e))
    sig_broad = {}
    if seeds.get("diff"):
        sig_hits, sig_broad = history.sig_channel(files, led["roots"], base)
        hits += sig_hits
    if seeds["files"]:
        hits += history.cochange_channel(files, seeds["files"], led["roots"], base)
    # After an edit: the files that usually change with an edited file, searched for its old lines.
    # A file that already differed from HEAD at the first scan and has not changed since is someone's
    # earlier work, not this edit, unless the agent named it with --file.
    named = {os.path.normpath(p) for p in seeds["files"]}
    wip = {p for p, d in led.get("dirty", {}).items() if p not in named and file_digest(base, p) == d}
    hits += history.residue(files, led["roots"], base, skip=wip)
    if seeds.get("like"):
        try:
            hits += layout.like_channel(files, seeds["like"])
        except ValueError as e:
            errors.append(str(e))
    if seeds["files"] or seeds["names"]:
        hits += declared.declared_channel(files, seeds["files"], seeds["names"] + seeds["keys"])
    notes = []
    if channels.walk.git_exe() is None:
        notes.append("git 不能运行，直接读 .git；没有按 .gitignore 过滤")
    per_channel = {}
    for h in hits:
        per_channel[h["channel"]] = per_channel.get(h["channel"], 0) + 1
    hits, broad = L.cap_per_seed(hits)
    broad.update(sig_broad)
    stats = {"at": L.now(), "files": len(files), "unreadable": unreadable, "seconds": round(time.time() - t0, 2),
             "hits": per_channel, "too_broad": broad, "errors": errors, "notes": notes}
    return files, L.merge_hits(hits, seeds["files"]), stats


def pick(items, top):
    """At most `top` items: the best few of every layer first, then by score; at most PER_FILE per file."""
    per_file, chosen = {}, []
    by_layer = {}
    for it in sorted(items, key=lambda i: -i["score"]):
        by_layer.setdefault(it["layer"], []).append(it)

    def take(it):
        if it in chosen or per_file.get(it["path"], 0) >= PER_FILE or len(chosen) >= top:
            return
        per_file[it["path"]] = per_file.get(it["path"], 0) + 1
        chosen.append(it)

    for layer in LAYER_ORDER:
        for it in by_layer.get(layer, [])[:3]:
            take(it)
    for it in sorted(items, key=lambda i: -i["score"]):
        take(it)
    return chosen


def item_line(it):
    flags = "".join([" 不一致" if it.get("mismatch") else "", " 生成" if it.get("generated") else "",
                     " 注释" if it.get("comment") else ""])
    tier = "" if not it.get("tier") else " %s/%s" % (it["tier"], it["status"])
    return "%s %d %s:%d [%s%s]%s %s | %s" % (
        it["id"], it["score"], it["path"], it["line"], ",".join(it["channels"]), flags, tier,
        "；".join(it["why"])[:70], it["anchor"][:60])


def print_items(items, top):
    shown = pick(items, top)
    for layer in LAYER_ORDER:
        group = [i for i in shown if i["layer"] == layer]
        if not group:
            continue
        total = sum(1 for i in items if i["layer"] == layer)
        print("--- %s（%d 个，显示 %d）" % (LAYER_ZH[layer], total, len(group)))
        for it in sorted(group, key=lambda i: (-i["score"], i["path"], i["line"])):
            print(item_line(it))
    return len(shown)


def print_stats(stats, roots):
    print("搜索：%d 个根目录，%d 个文件，%.1f s。跳过 node_modules、dist、vendor、build、被 .gitignore 忽略的、"
          "二进制、超过 1 MB 的文件；.env 和密钥文件不读；生成代码降分" % (len(roots), stats["files"], stats["seconds"]))
    print("通道命中：%s" % ("，".join("%s %d" % kv for kv in sorted(stats["hits"].items())) or "无"))
    if stats["too_broad"]:
        print("太泛（每个种子只保留前 %d 个，换更具体的种子或加 --near）：%s" % (
            L.MAX_PER_SEED, "，".join("%s %d" % kv for kv in stats["too_broad"].items())))
    for e in stats["errors"]:
        print("错误：%s" % e)
    for n in stats.get("notes", []):
        print("注意：%s" % n)


def cmd_scan(args, base):
    led = need_ledger(base)
    s = led["seeds"]
    if not any(s.get(k) for k in ("names", "keys", "values", "files", "enums", "layouts", "like", "funcs", "diff")):
        sys.exit("没有种子：先用 seed 加 --name、--key、--value、--enum、--layout、--like、--func、--diff 或 --file")
    if "dirty" not in led:      # uncommitted changes from before the task
        led["dirty"] = {p: file_digest(base, p) for p in sorted(history.changed_files(led["roots"], base))}
    _, cands, stats = run_queries(led, base)
    added = L.upsert(led, cands, "scan")
    record_digests(led, base)
    if "untracked" not in led:
        led["untracked"] = sorted(history.untracked_files(led["roots"], base))
    stats["added"] = len(added)
    led["scans"].append(stats)
    L.save(base, led)
    print("ledger：%s，共 %d 项，本次新增 %d" % (os.path.relpath(L.path(base), os.getcwd()), len(led["items"]), len(added)))
    print("种子：%s" % describe_seeds(s))
    print_stats(stats, led["roots"])
    layers = {}
    for it in led["items"]:
        layers[it["layer"]] = layers.get(it["layer"], 0) + 1
    print("按层：%s" % "，".join("%s %d" % (LAYER_ZH[k], layers[k]) for k in LAYER_ORDER if k in layers))
    top = len(led["items"]) if len(led["items"]) <= SHOW_ALL else args.top
    shown = print_items(led["items"], top)
    if len(led["items"]) > shown:
        print("另有 %d 项没显示：status --all 列出全部，或用 show 读局部。" % (len(led["items"]) - shown))
    print("结果只覆盖上面的种子和通道，不代表已经找全。下一步：show 读局部，mark 分级。")


def cmd_show(args, base):
    led = need_ledger(base)
    budget = 200
    for item_id in expand_ids(led, args.ids):
        it = L.find(led, item_id)
        full = os.path.join(base, it["path"]) if not os.path.isabs(it["path"]) else it["path"]
        lines = channels.walk.read_lines(full)
        if lines is None:
            print("== %s %s：读不到" % (item_id, it["path"]))
            continue
        line = relocate(lines, it)
        print("== %s %s:%d [%s] %s" % (item_id, it["path"], line, ",".join(it["channels"]), "；".join(it["why"])))
        text = S.render(lines, line, args.context, it["path"])
        n = text.count("\n") + 1
        if n > budget:
            print("（输出已到 200 行上限，其余 ID 请分开 show）")
            break
        budget -= n
        print(text)


def relocate(lines, it):
    """Current line of an item: its anchor near the recorded line, else the recorded line."""
    want = it["anchor"]
    found = [n for n, l in enumerate(lines, 1) if L.anchor(l.strip()) == want]
    if found:
        return min(found, key=lambda n: abs(n - it["line"]))
    return min(it["line"], len(lines))


def expand_ids(led, spec):
    """c1,c4-c7 or 'rest' (open items without a tier)."""
    ids = []
    for part in split_list([spec]):
        if part == "rest":
            ids += [i["id"] for i in led["items"] if i["status"] == "open" and not i.get("tier")]
            continue
        m = re.fullmatch(r"c(\d+)-c?(\d+)", part)
        if m:
            ids += ["c%d" % n for n in range(int(m.group(1)), int(m.group(2)) + 1)]
        else:
            ids.append(part)
    missing = [i for i in ids if L.find(led, i) is None]
    if missing:
        sys.exit("ledger 里没有：%s" % ",".join(missing))
    return list(dict.fromkeys(ids))


ID_SPEC = re.compile(r"^(rest|c\d+(-c?\d+)?)(,(rest|c\d+(-c?\d+)?))*$")


def mark_groups(args):
    """(ids, tier, status, note) groups from `mark IDS TIER[/STATUS] [NOTE] IDS ...` or the flags."""
    tokens, groups = args.spec, []
    if not tokens or not ID_SPEC.match(tokens[0]):
        sys.exit("mark 的第一个参数要是 ID，例如 c3,c5-c9 或 rest")
    i = 0
    while i < len(tokens):
        if not ID_SPEC.match(tokens[i]):
            sys.exit("看不懂 %r：期望 ID，例如 c3,c5-c9" % tokens[i])
        ids, tier, status, note = tokens[i], args.tier, args.status, args.note
        i += 1
        if i < len(tokens) and tokens[i].split("/")[0] in L.TIERS:
            tier, _, st = tokens[i].partition("/")
            status = st or status
            if status and status not in L.STATUSES:
                sys.exit("状态 %r 不对，可选：%s" % (status, "、".join(L.STATUSES)))
            i += 1
        elif i < len(tokens) and tokens[i] in L.STATUSES:
            status = tokens[i]
            i += 1
        if i < len(tokens) and not ID_SPEC.match(tokens[i]):
            note = tokens[i]
            i += 1
        groups.append((ids, tier, status, note))
    return groups


def cmd_mark(args, base):
    led = need_ledger(base)
    groups = mark_groups(args)
    if not any(t or st or n for _, t, st, n in groups):
        sys.exit("mark 需要级别、状态或说明，例如 mark c3 coupled/asked \"理由\"")
    changed, done = [], []
    for spec, tier_arg, status_arg, note in groups:
        ids = expand_ids(led, spec)
        bulk = set(expand_ids(led, "rest")) if "rest" in spec.split(",") else set()
        done.append(ids)
        for item_id in ids:
            it = L.find(led, item_id)
            tier = tier_arg or it.get("tier")
            status = status_arg or it["status"]
            if status != "open" and not tier:
                sys.exit("%s 还没分级：先给级别" % item_id)
            if tier in ("coupled", "review") and status == "edited" and it["status"] != "confirmed":
                sys.exit("%s 是 %s，用户确认前不能标 edited。先提问并标 asked；用户同意后标 confirmed，再修改。"
                         % (item_id, tier))
            if tier in ("exclude", "review") and status == "open":
                status = "listed"
            it["tier"], it["status"] = tier, status
            it["bulk"] = item_id in bulk        # tiered by `rest`, without reading the block
            if note:
                it["note"] = note
            it["updated"] = L.now()
            changed.append(it)
    L.save(base, led)
    for (spec, tier, status, note), ids in zip(groups, done):
        shown = ",".join(ids) if len(ids) <= 12 else "%s 等 %d 项" % (",".join(ids[:6]), len(ids))
        print("%s → %s%s" % (shown, "/".join(x for x in (tier, status) if x) or "说明", " | " + note if note else ""))
    if args.verify:
        cmd_verify(args, base)


def cmd_add(args, base):
    """Track positions found by reading code, so they are tiered and verified like the rest."""
    led = need_ledger(base)
    if args.tier and args.tier.split("/")[0] not in L.TIERS:
        sys.exit("级别 %r 不对，可选：%s" % (args.tier, "、".join(L.TIERS)))
    resolve, guesser, out = resolver(led["roots"], base), channels.walk.StackGuesser(base), []
    for pos in args.positions:
        m = re.fullmatch(r"(.+):(\d+)", pos)
        if not m:
            sys.exit("位置要写成 path:line，%r 不是" % pos)
        rel, line = m.group(1), int(m.group(2))
        full = os.path.normpath(os.path.join(base, resolve(rel)))
        lines = channels.walk.read_lines(full)
        if lines is None or not 1 <= line <= len(lines):
            sys.exit("读不到 %s 第 %d 行" % (rel, line))
        stack = guesser.stack(os.path.relpath(full, base))
        cand = {"path": channels.display_path(full, base), "line": line, "anchor": L.anchor(lines[line - 1].strip()),
                "layer": channels.walk.layer(os.path.relpath(full, base), stack), "stack": stack,
                "channels": ["manual"], "queries": [], "why": [args.why], "score": 50, "generated": False,
                "comment": channels.is_comment(lines[line - 1]), "roles": []}
        added = L.upsert(led, [cand], "manual")
        it = L.find(led, added[0]) if added else next(
            i for i in led["items"] if (i["path"], i["anchor"]) == (cand["path"], cand["anchor"]))
        if args.tier:
            tier, _, status = args.tier.partition("/")
            if status == "edited" and tier in ("coupled", "review"):
                sys.exit("%s 是 %s，用户确认前不能标 edited" % (pos, tier))
            it["tier"], it["status"] = tier, status or ("listed" if tier == "exclude" else it["status"])
            it["note"] = args.why
        out.append(it)
    record_digests(led, base)
    L.save(base, led)
    for it in out:
        print("%s %s:%d%s" % (it["id"], it["path"], it["line"], " %s/%s" % (it["tier"], it["status"]) if it.get("tier") else ""))


def cmd_status(args, base):
    led = need_ledger(base)
    counts = {}
    for it in led["items"]:
        k = "%s/%s" % (it.get("tier") or "未分级", it["status"])
        counts[k] = counts.get(k, 0) + 1
    print("改动：%s" % led["change"])
    print("共 %d 项：%s" % (len(led["items"]), "，".join("%s %d" % kv for kv in sorted(counts.items()))))
    todo = L.unresolved(led)
    if args.all:
        items = led["items"]
    else:
        items = todo
    if not items:
        print("没有待处理的项。")
        return
    print("%s：" % ("全部" if args.all else "待处理（open、asked、confirmed）"))
    for it in sorted(items, key=lambda i: (i.get("tier") or "", -i["score"])):
        print(item_line(it))


def file_digest(base, path):
    full = path if os.path.isabs(path) else os.path.join(base, path)
    try:
        with open(full, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()
    except OSError:
        return None


def read_item_file(base, path):
    return channels.walk.read_lines(path if os.path.isabs(path) else os.path.join(base, path))


def line_key(anchor):
    return zlib.crc32(anchor.encode("utf-8"))


def block_of(lines, it):
    """[start, end, checksum] of the function or style rule holding the item, or None."""
    r = S.enclosing_block(lines, relocate(lines, it), it["path"])
    if r is None:
        return None
    return [r[0], r[1], "%08x" % zlib.crc32("\n".join(lines[r[0] - 1:r[1]]).encode("utf-8"))]


def record_digests(led, base):
    """Remember, the first time a file or item appears, the file's digest and line set and the item's
    block, so verify can tell which items the edit changed and which hits are lines the edit wrote."""
    digests, snap, cache = led.setdefault("digests", {}), led.setdefault("lines", {}), {}
    for it in led["items"]:
        p = it["path"]
        if p not in digests:
            digests[p] = file_digest(base, p)
        if p in snap and "block" in it:
            continue
        if p not in cache:
            cache[p] = read_item_file(base, p)
        lines = cache[p]
        if lines is None:
            continue
        if p not in snap:
            snap[p] = sorted({line_key(L.anchor(l.strip())) for l in lines})
        if "block" not in it:
            it["block"] = block_of(lines, it)


def item_changed(base, it, lines, digests):
    """Whether the edit changed the item: its line is gone, or its block, or (without a block) its file."""
    if lines is None or not any(L.anchor(l.strip()) == it["anchor"] for l in lines):
        return True
    if it.get("block"):
        now = block_of(lines, it)
        return now is None or now[2] != it["block"][2]
    return digests.get(it["path"], "") not in (file_digest(base, it["path"]), "")


CHECK_SCRIPT = re.compile(r"^(typecheck|type-check|tsc|lint|test(:unit)?|check)$")


def project_checks(roots):
    """One line per package: the check scripts it defines and whether it can run them, so the agent
    does not spend a call on `ls node_modules; grep typecheck package.json`. Nothing is run."""
    out = []
    for r in roots:
        dirs = [r] + sorted(os.path.join(r, d) for d in os.listdir(r) if os.path.isdir(os.path.join(r, d))
                            and d not in channels.walk.SKIP_DIRS and not d.startswith("."))
        for d in dirs:
            rel = os.path.relpath(d, os.getcwd())
            pkg = os.path.join(d, "package.json")
            if os.path.isfile(pkg):
                try:
                    with open(pkg, encoding="utf-8") as fh:
                        scripts = json.load(fh).get("scripts") or {}
                except (OSError, ValueError):
                    scripts = {}
                names = [k for k in scripts if CHECK_SCRIPT.match(k)]
                deps = os.path.isdir(os.path.join(d, "node_modules")) or os.path.isdir(os.path.join(r, "node_modules"))
                out.append("%s：%s%s" % (rel, "、".join("npm run " + n for n in names) or "没有检查脚本",
                                       "" if deps else "（没有 node_modules，装依赖前跑不了）"))
            elif os.path.isfile(os.path.join(d, "go.mod")):
                out.append("%s：go build ./...、go vet ./...、go test ./..." % rel)
    return out


OLD_CODE = {"value", "sig", "residue"}   # channels whose hit on a new line means the old code is still there
SAME_LINE = {"sig", "residue"}   # the item's line is a copy of a removed line, so it must not survive the edit
RANKED = {"func", "like", "history"}   # ranked lists: after the edit, lower-ranked files move up


def cmd_verify(args, base):
    led = need_ledger(base)
    _, cands, stats = run_queries(led, base)
    known = {(i["path"], i["anchor"]): i for i in led["items"]}
    problems, digests = [], led.get("digests", {})
    snap = {p: set(v) for p, v in led.get("lines", {}).items()}
    files = {p: read_item_file(base, p) for p in {i["path"] for i in led["items"]}}
    still = {it["id"]: files[it["path"]] is not None and
             any(L.anchor(l.strip()) == it["anchor"] for l in files[it["path"]]) for it in led["items"]}
    changed = {it["id"]: item_changed(base, it, files[it["path"]], digests) for it in led["items"]}
    gone = [i for i in led["items"] if not still[i["id"]]]
    # Direct items, and confirmed ones, whose block changed are edited; no separate mark call needed.
    auto = [i for i in led["items"] if changed[i["id"]] and i["status"] in ("open", "listed", "confirmed")
            and (i.get("tier") == "direct" or i["status"] == "confirmed")]
    for it in auto:
        it["status"], it["updated"] = "edited", L.now()
    # A changed line inside the block of an edited direct item is part of that edit.
    absorbed = []
    for g in gone:
        # An exclude item tiered by `rest` was never read; inside an edited block it is part of the edit.
        if g.get("tier") in ("direct", "coupled") or g["status"] == "edited" or (
                g.get("tier") == "exclude" and not g.get("bulk")):
            continue
        # Without a block (a template line), the edited direct item's whole file counts, but only
        # for items tiered by `rest`: one the agent read and kept out stays reported.
        owner = next((d for d in led["items"] if d["path"] == g["path"] and d.get("tier") == "direct"
                      and d["status"] == "edited" and changed[d["id"]]
                      and (d["block"][0] <= g["line"] <= d["block"][1] if d.get("block") else g.get("bulk"))),
                     None)
        if owner is not None:
            g.update(tier="direct", status="edited", note="在 %s 的块里，随它一起改" % owner["id"], updated=L.now())
            absorbed.append(g)
    edited_but_same = [i for i in led["items"] if i["status"] == "edited" and not changed[i["id"]]
                       and i.get("found_by") != "verify"]
    changed_unmarked = [i for i in gone if i["status"] != "edited" and i.get("tier") != "exclude"]
    exclude_touched = [i for i in gone if i.get("tier") == "exclude"]
    coupled_unconfirmed = [i for i in gone if i.get("tier") in ("coupled", "review")
                           and i["status"] not in ("confirmed", "edited")]
    changed_unmarked = [i for i in changed_unmarked if i not in coupled_unconfirmed]
    # A hit on the line where a changed item used to be is that item after the edit, not a new site.
    rewritten = {(i["path"], i["line"] + d): i for i in gone for d in (-1, 0, 1)}
    # Untracked files that were not there at the first scan: written by the agent.
    created = history.untracked_files(led["roots"], base) - set(led.get("untracked", []))
    fresh, own, moved, ranked = [], [], [], 0
    for c in cands:
        if (c["path"], c["anchor"]) in known:
            continue
        old = rewritten.get((c["path"], c["line"]))
        if old is not None:
            old["after"] = c["anchor"]
            continue
        chans = set(c["channels"])
        # A line the edit wrote: an enum table that now has the value, a new wrapper. Not residue,
        # unless a value or old-code search found it there.
        if c["path"] in snap and line_key(c["anchor"]) not in snap[c["path"]] and not chans & OLD_CODE:
            own.append(c)
        elif os.path.normpath(c["path"]) in created:
            moved.append(c)             # a file the agent wrote, e.g. the shared helper of a dedupe
        elif chans <= RANKED:
            ranked += 1
        else:
            fresh.append(c)
    added = L.upsert(led, fresh, "verify")
    own_ids = L.upsert(led, own, "verify")
    moved_ids = L.upsert(led, moved, "verify")
    for i in own_ids:
        L.find(led, i).update(tier="direct", status="edited", note="改动写进去的新行")
    for i in moved_ids:
        L.find(led, i).update(tier="direct", status="edited", note="新建文件里的行", moved=True)
    record_digests(led, base)
    still.update((i, True) for i in added + own_ids + moved_ids)
    # Just marked edited, but the old line is still there: one of several identical lines was fixed.
    # Reported once; a line the agent leaves on purpose does not block later runs.
    still_old = [i for i in auto if still[i["id"]] and set(i["channels"]) & SAME_LINE]
    unresolved = L.unresolved(led)
    led["scans"].append(dict(stats, verify=True, added=len(added)))
    L.save(base, led)

    print("复查：%d 个文件，%.1f s，ledger 共 %d 项" % (stats["files"], stats["seconds"], len(led["items"])))
    notes = [("块已改，记为 edited", auto), ("在已改 direct 项的块里，记为 direct/edited", absorbed),
             ("改动写进去的新行，记为 direct/edited，不用处理", [L.find(led, i) for i in own_ids])]
    for title, items in notes:
        if items:
            print("%s：%s" % (title, ",".join(i["id"] for i in items)))
    if moved_ids:
        print("--- 新建文件里命中旧值或旧写法（合并时搬过去的就不用处理；不该有的话改掉再 verify）：%d" % len(moved_ids))
        for i in moved_ids[:10]:
            print(item_line(L.find(led, i)))
    if ranked:
        print("func、like、history 在改后代码上排上来的 %d 个新候选没有加入（复查只找旧写法）" % ranked)
    sections = [
        ("exclude 项被改了（应保持原样）", exclude_touched),
        ("coupled/review 项被改了，但没有确认记录", coupled_unconfirmed),
        ("标了 edited，但它的代码块没变（没改到，或改的是别处）", edited_but_same),
        ("标了 edited，但旧写法那一行还在（同样的行有几处，只改了一部分）", still_old),
        ("原行已经变了，但没标 edited", changed_unmarked),
        ("新出现的命中（改动带进来的旧写法，或之前漏掉的）", [L.find(led, i) for i in added]),
        ("还没处理（open 或已确认未改，不含上面的新命中）", [i for i in unresolved if i["status"] != "asked" and i["id"] not in added]),
    ]
    waiting = [i for i in unresolved if i["status"] == "asked"]
    for title, items in sections:
        if not items:
            continue
        problems.append(title)
        print("--- %s：%d" % (title, len(items)))
        for it in items[:25]:
            print(item_line(it))
        if len(items) > 25:
            print("（另有 %d 项，status --all 查看）" % (len(items) - 25))
    stale_docs = [i for i in led["items"] if still[i["id"]] and (i.get("comment") or i["layer"] == "docs")
                  and i["status"] not in ("listed", "declined", "edited", "asked") and i.get("tier") != "exclude"]
    if stale_docs:
        print("--- 还含旧写法的注释和文档行（列为确认项）：%d" % len(stale_docs))
        for it in stale_docs[:15]:
            print(item_line(it))
    if waiting:
        print("--- 等你确认（asked，在最后的消息里列出，不要改）：%d" % len(waiting))
        groups = {}
        for it in waiting:
            groups.setdefault(it.get("note") or "", []).append(it)
        for note, items in groups.items():
            print("%s：%s" % (note[:60] or "（无说明）", "，".join("%s %s:%d" % (i["id"], i["path"], i["line"]) for i in items)))
    if problems:
        print("复查未通过：%s。处理后再运行 verify。" % "；".join(problems))
    else:
        print("复查通过：除了等你确认的项，每一项都有结论，没有新的旧写法。还要跑测试和类型检查。")
        checks = project_checks(led["roots"])
        if checks:
            print("检查命令（脚本没有运行它们）：")
            for c in checks[:8]:
                print("  " + c)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("seed", help="record the change and its seeds")
    p.add_argument("--change", help="what changes, before and after, in one or two sentences")
    p.add_argument("--invariant", action="append", help="A and B must agree on Z")
    p.add_argument("--name", action="append", help="identifier; all spellings are searched")
    p.add_argument("--key", action="append", help="JSON field, MQTT topic or WS path, or i18n key")
    p.add_argument("--value", action="append", help="old literal value, e.g. 8 or 密码至少6位")
    p.add_argument("--near", action="append", help="context words for numeric values: password,pwd,密码")
    p.add_argument("--enum", action="append", help="changed value first, then its siblings: info,warning,error")
    p.add_argument("--layout", action="append", help="structure query: header-in-scroll")
    p.add_argument("--like", action="append", help="example component; rank others by shared features")
    p.add_argument("--func", action="append", help="PATH:NAME; find renamed or drifted copies of that function")
    p.add_argument("--diff", action="store_true", help="search for lines the uncommitted diff removed")
    p.add_argument("--file", action="append", help="file the change touches (sync comments, co-change history)")
    p.add_argument("--root", action="append", help="extra root to search (sibling repo); default: repo root")
    p.add_argument("--new", action="store_true", help="archive the current ledger and start a new one")
    p.add_argument("--scan", action="store_true", help="run scan right after seeding")
    p.add_argument("--top", type=int, default=TOP)
    p = sub.add_parser("scan", help="search all channels and update the ledger")
    p.add_argument("--top", type=int, default=TOP)
    p = sub.add_parser("show", help="print the block around candidates")
    p.add_argument("ids")
    p.add_argument("--context", type=int)
    p = sub.add_parser("mark", help="set tier, status or note: mark c1,c2 direct c3-c5 coupled/asked \"why\"")
    p.add_argument("spec", nargs="+", help="groups of IDS [TIER[/STATUS]] [NOTE]")
    p.add_argument("--tier", choices=L.TIERS)
    p.add_argument("--status", choices=L.STATUSES)
    p.add_argument("--note")
    p.add_argument("--verify", action="store_true", help="run verify right after marking")
    p = sub.add_parser("add", help="track positions found by reading code")
    p.add_argument("positions", nargs="+", help="path:line ...")
    p.add_argument("--why", required=True)
    p.add_argument("--tier", help="TIER[/STATUS] for all of them, e.g. direct or coupled/asked")
    sub.add_parser("verify", help="rerun the queries and check every item has an outcome")
    p = sub.add_parser("status", help="counts and items still needing a decision")
    p.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)
    gitread.reset()             # the working tree may have changed since an earlier call in this process
    base = base_dir(new=args.cmd == "seed" and args.new)
    {"seed": cmd_seed, "scan": cmd_scan, "show": cmd_show, "mark": cmd_mark, "add": cmd_add,
     "verify": cmd_verify, "status": cmd_status}[args.cmd](args, base)


if __name__ == "__main__":
    main()
