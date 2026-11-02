"""Prototype checks for a contract-map recipe (stdlib only, Python 3.9)."""
import os, re, sys, time

# ---------- 1. identifier splitting, folding, variants ----------
SPLIT = re.compile(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+')

def words(name):
    return [w.lower() for w in SPLIT.findall(name)]

def fold(name):  # same idea as Go encoding/json/v2 foldName: ignore case, '-' and '_'
    return re.sub(r'[-_\s]', '', name).lower()

def variants(name):
    w = words(name)
    if not w:
        return set()
    cap = [x.capitalize() for x in w]
    out = {w[0] + ''.join(cap[1:]), ''.join(cap), '_'.join(w), '-'.join(w),
           '_'.join(w).upper(), '.'.join(w)}
    # acronym-preserving forms for short all-letter words (AGV, ID, URL)
    acr = [x.upper() if len(x) <= 3 and x.isalpha() else c for x, c in zip(w, cap)]
    out.add(''.join(acr)); out.add(w[0] + ''.join(acr[1:]))
    return out

def seed_regex(name):
    w = words(name)
    return re.compile(r'(?i)' + r'[-_ .]?'.join(map(re.escape, w)))

# ---------- 2. MQTT filter vs code topic template ----------
DYN = '\x00'  # one dynamic level from Sprintf %s / f-string {x} / ${x}

def template_from_code(s):
    s = re.sub(r'%[-+# 0]*\d*(?:\.\d+)?[sdvqxXfg]', DYN, s)        # Go / Python %
    s = re.sub(r'\$\{[^}]*\}', DYN, s)                              # JS template
    s = re.sub(r'\{[^{}]*\}', DYN, s)                               # f-string / str.format
    return s

def filter_matches(flt, topic):
    """MQTT 3.1.1/5.0 section 4.7 semantics. topic may contain DYN levels."""
    f, t = flt.split('/'), topic.split('/')
    if f[0] in ('+', '#') and t[0].startswith('$'):
        return False
    for i, lv in enumerate(f):
        if lv == '#':
            return True                       # also matches parent level
        if i >= len(t):
            return False
        if lv != '+' and t[i] != DYN and lv != t[i]:
            return False
    return len(f) == len(t)

def filters_overlap(a, b):
    """True if some topic matches both filters (co-subscribers)."""
    fa, fb = a.split('/'), b.split('/')
    for i in range(max(len(fa), len(fb))):
        x = fa[i] if i < len(fa) else None
        y = fb[i] if i < len(fb) else None
        if x == '#' or y == '#':
            return True
        if x is None or y is None:
            return False
        if x != '+' and y != '+' and x != y:
            return False
    return True

def strip_share(flt):
    return flt.split('/', 2)[2] if flt.startswith('$share/') else flt

# ---------- tests ----------
def check(label, got, want):
    ok = got == want
    print(('PASS' if ok else 'FAIL'), label, '->', got, '' if ok else '(want %r)' % (want,))
    return ok

def run_tests():
    r = []
    names = ['AGVStatus', 'agvStatus', 'agv_status', 'AGV_STATUS', 'agv-status', 'AgvStatus']
    r.append(check('fold unifies 6 AGV spellings', len({fold(n) for n in names}), 1))
    r.append(check('words(taskID)', words('taskID'), ['task', 'id']))
    r.append(check('words(HTTPServer2Go)', words('HTTPServer2Go'), ['http', 'server', '2', 'go']))
    r.append(check('words(pose2D)==words(pose_2d)', words('pose2D') == words('pose_2d'), True))
    rx = seed_regex('battery_level')
    hits = [s for s in ['batteryLevel', 'BATTERY_LEVEL', 'battery-level', 'BatteryLevel',
                        'battery.level', 'lowBatteryLevelWarn', 'battery'] if rx.search(s)]
    r.append(check('one seed regex covers case variants', len(hits), 6))
    r.append(check('variants(agv_task_id) has AGVTaskID', 'AGVTaskID' in variants('agv_task_id'), True))
    # MQTT spec 4.7 examples (3.1.1 / 5.0)
    r.append(check("'sport/#' matches 'sport'", filter_matches('sport/#', 'sport'), True))
    r.append(check("'+/+' matches '/finance'", filter_matches('+/+', '/finance'), True))
    r.append(check("'/+' matches '/finance'", filter_matches('/+', '/finance'), True))
    r.append(check("'+' does not match '/finance'", filter_matches('+', '/finance'), False))
    r.append(check("'#' does not match '$SYS/x'", filter_matches('#', '$SYS/x'), False))
    r.append(check("'sport/+' does not match 'sport/a/b'", filter_matches('sport/+', 'sport/a/b'), False))
    naive = re.compile('^' + 'agv/+/status'.replace('+', '[^/]+') + '$')
    r.append(check("naive regex misses empty level 'agv//status'", bool(naive.match('agv//status')), False))
    r.append(check("spec matcher accepts 'agv//status'", filter_matches('agv/+/status', 'agv//status'), True))
    # code templates
    go = template_from_code('agv/%s/status')
    py = template_from_code('agv/{agv_id}/status')
    js = template_from_code('agv/${id}/status')
    r.append(check('Go/Python/JS templates normalise equal', go == py == js, True))
    r.append(check("'agv/+/status' may match Sprintf template", filter_matches('agv/+/status', go), True))
    r.append(check("'agv/+/pose' does not match it", filter_matches('agv/+/pose', go), False))
    r.append(check("'agv/#' overlaps 'agv/+/status'", filters_overlap('agv/#', 'agv/+/status'), True))
    r.append(check("'agv/+/status' vs 'task/+/status'", filters_overlap('agv/+/status', 'task/+/status'), False))
    r.append(check('$share prefix stripped', strip_share('$share/g1/agv/+/status'), 'agv/+/status'))
    print('%d/%d passed' % (sum(r), len(r)))

# ---------- timing: one combined seed regex over a corpus ----------
def timing(roots, seeds, exts=('.py', '.js', '.ts', '.mjs', '.cjs', '.vue', '.go')):
    rx = re.compile('|'.join('(?:%s)' % seed_regex(s).pattern[4:] for s in seeds), re.I)
    t0, nfiles, nbytes, nhits, files_hit = time.time(), 0, 0, 0, set()
    for root in roots:
        for d, _, fs in os.walk(root):
            for f in fs:
                if not f.endswith(exts):
                    continue
                p = os.path.join(d, f)
                try:
                    with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                        txt = fh.read()
                except OSError:
                    continue
                nfiles += 1; nbytes += len(txt)
                for i, line in enumerate(txt.splitlines(), 1):
                    if rx.search(line):
                        nhits += 1; files_hit.add(p)
    dt = time.time() - t0
    print('files=%d MB=%.1f secs=%.2f files/s=%.0f MB/s=%.1f hit_lines=%d hit_files=%d'
          % (nfiles, nbytes / 1e6, dt, nfiles / dt, nbytes / 1e6 / dt, nhits, len(files_hit)))

if __name__ == '__main__':
    run_tests()
    if len(sys.argv) > 1:
        timing(sys.argv[1:], ['read_timeout', 'status_code', 'socket_path'])
