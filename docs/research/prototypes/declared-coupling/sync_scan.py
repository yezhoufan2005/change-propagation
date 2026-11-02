#!/usr/bin/env python3
"""Scan a git repo for declared-coupling comments (sync annotations).

Usage: python3 -I sync_scan.py <repo_root> <out_json>
Counts hits per pattern family, decides whether each hit names a
resolvable target (path or identifier present in another tracked file),
and dumps samples for manual precision review.
"""
import json, os, random, re, subprocess, sys
from collections import Counter, defaultdict

EXCL = re.compile(r'(^|/)(node_modules|vendor|dist|build|\.git|locale|locales|i18n|'
                  r'translations|lang|l10n|Localizations?|testdata|fixtures?|__snapshots__)(/|$)'
                  r'|\.(min\.js|lock|snap|svg|png|jpe?g|gif|ico|webp|pdf|zip|gz|woff2?|ttf|'
                  r'eot|mp3|mp4|jar|so|dylib|a|bin|pbxproj|xcstrings|strings|stringsdict|arb|po|pot)$'
                  r'|(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|go\.sum|uv\.lock)$', re.I)

LANG = {}
for ex, l in [('go', 'go'), ('ts', 'web'), ('tsx', 'web'), ('js', 'web'), ('jsx', 'web'),
              ('mjs', 'web'), ('cjs', 'web'), ('vue', 'web'), ('svelte', 'web'), ('mts', 'web'),
              ('py', 'py'), ('pyi', 'py'), ('kt', 'jvm'), ('kts', 'jvm'), ('java', 'jvm'),
              ('swift', 'apple'), ('m', 'apple'), ('mm', 'apple'), ('h', 'apple'),
              ('dart', 'dart'), ('sql', 'sql'), ('yml', 'cfg'), ('yaml', 'cfg'), ('toml', 'cfg'),
              ('json', 'cfg'), ('ini', 'cfg'), ('md', 'doc'), ('mdx', 'doc'), ('rst', 'doc'),
              ('txt', 'doc'), ('html', 'tpl'), ('tmpl', 'tpl'), ('hbs', 'tpl'), ('jinja', 'tpl'),
              ('sh', 'sh'), ('bash', 'sh'), ('css', 'css'), ('scss', 'css'), ('less', 'css'),
              ('proto', 'proto'), ('xml', 'xml'), ('gradle', 'jvm'), ('rs', 'rs')]:
    LANG[ex] = l

def lang_of(p):
    base = p.rsplit('/', 1)[-1]
    if base in ('Makefile', 'Dockerfile'):
        return 'sh'
    ext = base.rsplit('.', 1)[-1].lower() if '.' in base else ''
    return LANG.get(ext)

F = re.I
PATTERNS = {
    'ifttt': re.compile(r'LINT\.(IfChange|ThenChange)'),
    'sync': re.compile(r'\b(keep|kept|keeps|keeping|stay|stays|staying|remain|remains)\b[^.\n]{0,40}?'
                       r'\bin[\s-]?sync\b|\bin[\s-]sync with\b|\b(must|should|needs? to|has to|have to)'
                       r'\s+(be|stay|remain)\s+(kept\s+)?in[\s-]?sync\b|\bsync(ed|hronized)? (up )?with\b', F),
    'must_match': re.compile(r'\b(must|should|needs? to|has to|have to)\s+(always\s+)?(be\s+)?'
                             r'(match(ed)?|mirror(ed)?|equal|consistent with|aligned with|identical to|'
                             r'the same as|kept consistent)\b', F),
    'update_too': re.compile(r'\b(if|when(ever)?)\s+(you\s+)?(change|update|modify|add|remove|rename|edit|'
                             r'bump)(s|d|ing)?\b[^.\n]{0,60}?\b(also|update|change|must|make sure|remember|'
                             r"don.?t forget)\b|\b(also|please|remember to|don.?t forget to|make sure to|be sure to)"
                             r'\s+(update|change|modify|edit|adjust|bump)\b|\bmust (also )?be (updated|changed|'
                             r'modified|adjusted)\b|\b(update|change) (this|these|it|them) (as well|too|also)\b', F),
    'mirror_of': re.compile(r'\b(mirrors?|mirrored|duplicates?|duplicated|copied|ported|counterpart|'
                            r'equivalent)\s+(of|from|in)\b|\bsame (logic|rules?|values?|list|order|regex|'
                            r'validation|checks?|format|implementation|algorithm|constants?|limits?)\s+(as|in)\b', F),
}
CMT = re.compile(r'(//|#|/\*|<!--|\{\{/\*|--\s|;;|\{#|\*)')
PATH_TOK = re.compile(r'(?:[\w@.\-]+/)+[\w@.\-]+\.\w{1,6}\b|\b[\w\-]+\.(?:go|ts|tsx|js|jsx|mjs|py|kt|java|'
                      r'swift|dart|proto|sql|md|yml|yaml|json|toml|html|tmpl|hbs|css|scss|vue|svelte|rs|cc|'
                      r'h|m|mm|xml|gradle|kts)\b')
IDENT = re.compile(r'\b(?:[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+|[a-z]+(?:[A-Z][a-z0-9]+)+|'
                   r'[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+)\b')
STOP = {'TODO', 'FIXME', 'NOTE', 'IfChange', 'ThenChange', 'JavaScript', 'TypeScript', 'GitHub',
        'GitLab', 'iOS', 'macOS', 'PostgreSQL', 'MySQL', 'JSON', 'YouTube', 'WebSocket', 'OAuth'}
WORD = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def tracked(root):
    out = subprocess.run(['git', '-C', root, 'ls-files', '-z'], capture_output=True, check=True).stdout
    files = []
    for p in out.decode('utf-8', 'replace').split('\0'):
        if not p or EXCL.search(p):
            continue
        if lang_of(p) is None:
            continue
        fp = os.path.join(root, p)
        try:
            if os.path.getsize(fp) > 1_000_000:
                continue
        except OSError:
            continue
        files.append(p)
    return files


def read(root, p):
    try:
        with open(os.path.join(root, p), 'rb') as fh:
            b = fh.read()
        if b'\0' in b[:4096]:
            return None
        return b.decode('utf-8', 'replace')
    except OSError:
        return None


def is_comment(line, start, lang, in_doc):
    if lang == 'doc':
        return True
    if in_doc:
        return True
    pre = line[:start]
    if CMT.search(pre):
        return True
    s = line.lstrip()
    return s.startswith(('*', '#', '//', '<!--', '--', '"""', "'''"))


def context(lines, i):
    """Current line plus up to 3 following comment-ish lines (targets often follow)."""
    out = [lines[i].strip()]
    for j in range(i + 1, min(i + 4, len(lines))):
        s = lines[j].strip()
        if s.startswith(('//', '#', '*', '<!--', '--')) or (s and not re.search(r'[;{}=()]', s) and len(s) < 120):
            out.append(s)
        else:
            break
    return ' '.join(out)[:400]


def scan(root):
    files = tracked(root)
    langs = Counter(lang_of(p) for p in files)
    hits = []
    for p in files:
        txt = read(root, p)
        if txt is None:
            continue
        lang = lang_of(p)
        lines = txt.split('\n')
        in_doc = False
        for i, line in enumerate(lines):
            if lang == 'py':
                n = line.count('"""') + line.count("'''")
                if n % 2 == 1:
                    in_doc = not in_doc
            for fam, rx in PATTERNS.items():
                m = rx.search(line)
                if m and is_comment(line, m.start(), lang, in_doc):
                    hits.append({'file': p, 'line': i + 1, 'lang': lang, 'fam': fam,
                                 'text': context(lines, i)})
    return files, langs, hits


def all_tracked(root):
    out = subprocess.run(['git', '-C', root, 'ls-files', '-z'], capture_output=True, check=True).stdout
    return [p for p in out.decode('utf-8', 'replace').split('\0') if p]


def resolve(root, files, hits):
    every = all_tracked(root)
    by_base = defaultdict(list)
    for p in every:
        by_base[p.rsplit('/', 1)[-1]].append(p)
    cands = set()
    for h in hits:
        h['paths'] = []
        for t in PATH_TOK.findall(h['text']):
            t = t.strip('./')
            base = t.rsplit('/', 1)[-1]
            ms = [p for p in by_base.get(base, []) if p.endswith(t)] if '/' in t else by_base.get(base, [])
            if ms:
                h['paths'].append([t, ms[:3], len(ms)])
        h['idents'] = [w for w in set(IDENT.findall(h['text'])) if w not in STOP and len(w) >= 5]
        cands.update(h['idents'])
    occ = defaultdict(list)
    for p in files:
        txt = read(root, p)
        if txt is None:
            continue
        for w in set(WORD.findall(txt)) & cands:
            occ[w].append(p)
    for h in hits:
        best = None
        for w in h['idents']:
            others = [p for p in occ.get(w, []) if p != h['file']]
            if others and (best is None or len(others) < best[1]):
                best = (w, len(others), others[:5])
        h['best_ident'] = best
        tgt_langs = set()
        for t, ms, n in h['paths']:
            if n <= 3:
                tgt_langs.update(lang_of(p) for p in ms)
        if best and best[1] <= 5:
            tgt_langs.update(lang_of(p) for p in best[2])
        tgt_langs.discard(None)
        if h['paths']:
            h['res'] = 'path'
        elif best and best[1] <= 5:
            h['res'] = 'ident_specific'
        elif best:
            h['res'] = 'ident_ambiguous'
        elif any(w in occ for w in h['idents']):
            h['res'] = 'same_file_only'
        else:
            h['res'] = 'none'
        h['cross_lang'] = bool(tgt_langs - {h['lang']})


def summarize(files, langs, hits):
    s = {'files': len(files), 'langs': dict(langs.most_common()), 'fam': {}}
    for fam in PATTERNS:
        hs = [h for h in hits if h['fam'] == fam]
        code = [h for h in hs if h['lang'] != 'doc']
        res = Counter(h['res'] for h in hs)
        s['fam'][fam] = {
            'hits': len(hs), 'code_hits': len(code), 'doc_hits': len(hs) - len(code),
            'files_with_hit': len({h['file'] for h in hs}),
            'per_1k_files': round(1000 * len(hs) / max(1, len(files)), 2),
            'res': dict(res),
            'pct_named_target': round(100 * (res['path'] + res['ident_specific']) / max(1, len(hs)), 1),
            'cross_lang_specific': sum(1 for h in hs if h['cross_lang']),
        }
    return s


def main():
    root, out = sys.argv[1], sys.argv[2]
    files, langs, hits = scan(root)
    resolve(root, files, hits)
    summ = summarize(files, langs, hits)
    random.seed(7)
    samples = {}
    for fam in PATTERNS:
        hs = [h for h in hits if h['fam'] == fam]
        samples[fam] = random.sample(hs, min(25, len(hs)))
    with open(out, 'w') as fh:
        json.dump({'summary': summ, 'samples': samples, 'hits': hits}, fh, indent=1, default=list)
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
