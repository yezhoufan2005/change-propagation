"""Contract-map prototype (stdlib only): seed variants, alias/callee hops, MQTT pairing, WS events, enum maps."""
import importlib.util, os, re, sys, time
_s = importlib.util.spec_from_file_location('proto', '/tmp/cp-contracts/proto.py')
P = importlib.util.module_from_spec(_s); _s.loader.exec_module(P)
EXTS = ('.go', '.py', '.js', '.ts', '.vue', '.mjs', '.cjs')

def load(roots):
    files = {}
    for root in roots:
        for d, _, fs in os.walk(root):
            for f in fs:
                if f.endswith(EXTS):
                    p = os.path.join(d, f)
                    with open(p, encoding='utf-8', errors='ignore') as fh:
                        files[os.path.relpath(p, root)] = fh.read().splitlines()
    return files

def vue_blocks(lines):  # crude SFC block tracker; real tool: @vue/compiler-sfc descriptor locs
    blk, out = None, []
    for ln in lines:
        m = re.match(r'\s*<(template|script|style)\b', ln)
        if m and blk is None:
            blk = m.group(1)
        out.append(blk or 'outside')
        if blk and '</%s>' % blk in ln:
            blk = None
    return out

def ctx(p, blk, ln):
    if p.endswith('.go'):
        return 'go:json-tag' if 'json:"' in ln else 'go'
    if p.endswith('.py'):
        return 'py:field' if re.match(r'\s*\w+\s*:\s*[\w\[\]|. ]+(=.*)?$', ln) else 'py'
    if p.endswith('.vue'):
        if blk == 'template':
            return 'vue:tpl-filter' if re.search(r'\{\{[^}]*\|\s*\w', ln) else (
                'vue:tpl-bind' if re.search(r'\s:[\w-]+=', ln) else 'vue:tpl')
        if blk == 'style':
            return 'vue:style'
        return 'vue:props' if re.search(r'define(Props|Emits)\s*\(', ln) else 'vue:script'
    return 'js'

def grep(files, blocks, rx, tag):
    return {(p, i): (tag, ctx(p, blocks[p][i - 1], ln), ln.strip())
            for p, ls in files.items() for i, ln in enumerate(ls, 1) if rx.search(ln)}

def alias_hops(hits, seed_rx):  # newKey: obj.oldKey  ->  newKey becomes a derived seed
    out = set()
    for (_, _, ln) in hits.values():
        for m in re.finditer(r'(?<![\w.])([A-Za-z_]\w*)\s*:\s*(\w+(?:\.\w+)+)', ln):
            k, last = m.group(1), m.group(2).split('.')[-1]
            if seed_rx.fullmatch(last) and P.fold(k) != P.fold(last):
                out.add(k)
    return out

def callee_hops(files, hits):  # {{ x | fmt }} or fmt(x.seed) -> definition of fmt
    names = set()
    for (_, c, ln) in hits.values():
        names |= set(re.findall(r'\|\s*([A-Za-z_]\w*)', ln)) if c == 'vue:tpl-filter' else set()
    if not names:
        return {}
    rx = re.compile(r'(?:\bdef |\bfunction |^\s*|[{,]\s*)(%s)\s*\(' % '|'.join(names))
    return {(p, i): ('callee', 'def', ln.strip()) for p, ls in files.items()
            for i, ln in enumerate(ls, 1) if rx.search(ln)}

CALL = re.compile(r'\b(Publish|Subscribe|AddRoute|publish|subscribe|message_callback_add|topic_callback)'
                  r'\s*\(\s*(?:fmt\.Sprintf\(\s*)?f?(["\'`])(.*?)\2')
DISPATCH = re.compile(r'\btopic\.(split|startsWith|endsWith|includes|match)\(|\btopic\s*===?')
EVENT = re.compile(r'\.(emit|on|once)\(\s*["\']([\w:.\-]+)["\']')
RESERVED = {'message', 'connect', 'disconnect', 'error', 'close', 'open', 'connection'}

def topics(files):
    pubs, subs, disp, emits, ons = [], [], [], [], []
    for p, ls in files.items():
        for i, ln in enumerate(ls, 1):
            for m in CALL.finditer(ln):
                t = P.template_from_code(m.group(3))
                (pubs if m.group(1) in ('Publish', 'publish') else subs).append((t, p, i))
            if DISPATCH.search(ln):
                disp.append((p, i))
            for m in EVENT.finditer(ln):
                if m.group(2) not in RESERVED:
                    (emits if m.group(1) == 'emit' else ons).append((m.group(2), p, i))
    return pubs, subs, disp, emits, ons

def enum_sites(files, values, win=3, need=2):
    alt = '|'.join(map(re.escape, values))
    rx = re.compile(r'["\'`](%s)["\'`]|(?<![\w.$-])(%s)\s*:(?!:)' % (alt, alt))
    out = []
    for p, ls in files.items():
        i = 0
        while i < len(ls):
            seen = {a or b for ln in ls[i:i + win] for a, b in rx.findall(ln)}
            if len(seen) >= need:
                out.append((p, i + 1, sorted(seen))); i += win
            else:
                i += 1
    return out

TRUTH = [('backend-go/publisher.go', 'json:"battery_level"'), ('backend-py/models.py', 'battery_level: float'),
         ('backend-py/models.py', 'data.battery_level < 20'), ('backend-node/ws.js', 'battery: s.battery_level'),
         ('web-a/src/stores/agv.js', 'battery: msg.battery'), ('web-a/src/components/AgvCard.vue', 'agv.battery }}'),
         ('web-b/src/views/Monitor.vue', 'battery_level | batteryText'), ('web-b/src/views/Monitor.vue', 'batteryText(v)'),
         ('web-b/src/views/Monitor.vue', 'battery_level: d.battery_level'),
         ('web-c/src/composables/useAgvWs.js', 'batteryLevel: s.batteryLevel'),
         ('web-c/src/components/BatteryBar.vue', '{{ batteryLevel }}'),
         ('web-c/src/components/BatteryBar.vue', 'defineProps({ batteryLevel'),
         ('web-c/src/components/AgvRow.vue', ':battery-level=')]

def score(files, found):
    truth = {(p, i) for p, s in TRUTH for i, ln in enumerate(files[p], 1) if s in ln}
    return len(truth & set(found)), len(truth), len(set(found) - truth)

def fixture(root, seed='battery_level'):
    files = load([root])
    blocks = {p: (vue_blocks(ls) if p.endswith('.vue') else ['code'] * len(ls)) for p, ls in files.items()}
    naive = grep(files, blocks, re.compile(re.escape(seed)), 'naive')
    srx = P.seed_regex(seed)
    folded = grep(files, blocks, srx, 'variant')
    derived = alias_hops(folded, re.compile(srx.pattern[4:], re.I))
    hop = {}
    for k in derived:
        hop.update(grep(files, blocks, re.compile(r'\.%s\b|(?<![\w.])%s\s*:' % (k, k)), 'alias:' + k))
    allh = dict(hop); allh.update(folded)
    callee = callee_hops(files, allh)
    full = dict(callee); full.update(allh)
    for name, h in [('naive literal', naive), ('folded variants', folded),
                    ('+alias hop', allh), ('+callee hop', full)]:
        tp, n, fp = score(files, h)
        print('%-16s recall %d/%d  extra(non-truth) %d' % (name, tp, n, fp))
    print('derived seeds:', sorted(derived))
    lines = ['%s:%d [%s|%s] %s' % (p, i, t, c, s[:70]) for (p, i), (t, c, s) in sorted(full.items())]
    pubs, subs, disp, emits, ons = topics(files)
    for t, p, i in pubs:
        m = [('%s:%d %s' % (q, j, P.strip_share(f))) for f, q, j in subs if P.filter_matches(P.strip_share(f), t)]
        lines.append('PUB %s @%s:%d -> %s' % (t.replace(P.DYN, '{}'), p, i, m or 'NO SUBSCRIBER IN REPO'))
    for f, p, i in subs:
        co = ['%s:%d' % (q, j) for g, q, j in subs if (q, j) != (p, i) and P.filters_overlap(f, g)]
        lines.append('SUB %s @%s:%d co-subscribers %s' % (f, p, i, co))
    lines += ['DISPATCH %s:%d (topic string ops)' % d for d in disp]
    for e, p, i in emits:
        lines.append('EMIT %s @%s:%d -> %s' % (e, p, i, ['%s:%d' % (q, j) for o, q, j in ons if o == e]
                                                 or [('FOLD-ONLY ' + o) for o, q, j in ons if P.fold(o) == P.fold(e)]))
    for p, i, v in enum_sites(files, ['idle', 'charging', 'error']):
        lines.append('ENUM-MAP %s:%d %s' % (p, i, v))
    out = '\n'.join(lines)
    print(out)
    print('contract map: %d lines, %d bytes (~%d tokens at 4 B/token)' % (len(lines), len(out), len(out) // 4))

def corpus_enum(roots, values, lone):
    t0 = time.time(); files = load(roots)
    lit = re.compile(r'["\'`]%s["\'`]' % re.escape(lone))
    n_lone = sum(1 for ls in files.values() for ln in ls if lit.search(ln))
    sites = enum_sites(files, values)
    print('corpus files=%d  lines with literal %r=%d  windows with >=2 of %s=%d  files=%d  secs=%.1f'
          % (len(files), lone, n_lone, values, len(sites), len({p for p, _, _ in sites}), time.time() - t0))

if __name__ == '__main__':
    if sys.argv[1] == 'fixture':
        fixture(sys.argv[2])
    else:
        corpus_enum(sys.argv[2:], ['debug', 'info', 'warn', 'error'], 'error')
