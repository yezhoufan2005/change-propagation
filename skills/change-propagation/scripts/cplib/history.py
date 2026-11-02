"""Fix-signature and co-change channels, both built from git.

Fix signature (`--diff`): the lines the current uncommitted diff removed are the old code. Each is
abstracted (local identifiers become a wildcard; member names after '.', literals, keywords and
operators are kept, the "L1" level of the research prototype) and searched in every other file.
A place that still has the old line and not the new one probably needs the same fix.

Co-change (`--file` seeds): files that past commits changed together with a seed file. Commits that
touch more than MAX_COMMIT_FILES files are skipped (merges, renames, formatting runs).

Residue (every scan and verify): after an edit, each edited file and its co-change partners are
searched for lines nearly the same as a line the edit removed, so a second copy in the same file,
or a copied page that drifted a little, is still found.

A root may be a repository, a directory inside one, or a workspace whose repositories sit up to
two levels below it. Git commands run with the git binary; where it cannot run (a sandbox that
denies it), cplib/gitread reads the .git directory instead.
"""
import collections
import difflib
import os
import re
import subprocess

from . import gitread, walk
from .channels import hit

TOKEN = re.compile(r"\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|`[^`\n]*`|\d[\w.]*|[A-Za-z_$][\w$]*|===|!==|=>|&&|\|\||\?\?|\?\.|[-+*/%&|^!=<>:]=|\S")
KEYWORDS = set("if else for while return const let var function new typeof await async switch case default break "
               "continue try catch throw import export from class extends this null undefined true false nil func "
               "go defer range map struct interface type package err len append make".split())
MIN_TOKENS = 5
MAX_HITS = 20
MAX_COMMIT_FILES = 30
LOG_COMMITS = 3000
TOP_PARTNERS = 5


def _git(root, args, timeout=60):
    exe = walk.git_exe()
    if exe is None:
        return None
    try:
        # core.quotePath=false: print non-ASCII file names as they are, not as quoted octal escapes.
        return subprocess.run([exe, "-C", root, "-c", "core.quotePath=false"] + args, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, check=True, timeout=timeout).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return None


def _reader(top):
    """gitread Repo for the repository at `top`, or None."""
    try:
        found = gitread.open_repo(top)
    except gitread.ERRORS:
        return None
    return found[1] if found else None


def _fallback(top, what, *args):
    """gitread.<what>(top, repo, *args) with read errors turned into None."""
    repo = _reader(top)
    if repo is None:
        return None
    try:
        return getattr(gitread, what)(top, repo, *args)
    except gitread.ERRORS:
        return None


def below(root):
    """Top directories of the git repositories one or two levels below `root`."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        depth = 0 if dirpath == root else os.path.relpath(dirpath, root).count(os.sep) + 1
        if depth and (".git" in dirnames or ".git" in filenames):
            out.append(dirpath)
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in sorted(dirnames) if d not in walk.SKIP_DIRS and not d.startswith(".")
                       ] if depth < 2 else []
    return out


def repos(roots):
    """Top directories of the git repositories for the roots. A root that is the top of a repository
    gives that repository. A root with repositories up to two levels below it is a workspace and gives
    those, even when it lies inside another repository (the eval sandbox keeps one in its home
    directory). Any other root gives the repository it is in."""
    out = []
    for root in roots:
        found = gitread.find_repo(root)
        if found and os.path.realpath(found[0]) == os.path.realpath(root):
            out.append(found[0])
            continue
        out += below(root) or ([found[0]] if found else [])
    return list(dict.fromkeys(os.path.realpath(p) for p in out))


def short(path):
    """The last two parts of a path: scene-edit/index.vue rather than index.vue."""
    return "/".join(path.replace(os.sep, "/").split("/")[-2:])


def rel_to(path, base):
    return os.path.normpath(os.path.relpath(os.path.realpath(path), os.path.realpath(base)))


def changed_files(roots, base):
    """Tracked files whose working copy differs from HEAD, relative to base."""
    out = set()
    for top in repos(roots):
        names = _git(top, ["diff", "--name-only", "--no-renames", "HEAD"])
        names = names.splitlines() if names is not None else (_fallback(top, "changed_files") or [])
        out |= {rel_to(os.path.join(top, n), base) for n in names if n}
    return out


def untracked_files(roots, base):
    """Files not tracked in git (not ignored), relative to base."""
    out = set()
    for top in repos(roots):
        st = _git(top, ["status", "--porcelain", "--untracked-files=all"])
        if st is not None:
            names = [l[3:].strip('"') for l in st.splitlines() if l.startswith("?? ")]
        else:
            names = _fallback(top, "untracked", walk.list_files(top)) or []
        out |= {rel_to(os.path.join(top, n), base) for n in names}
    return out


def in_repo(top, base, paths):
    """`paths` (relative to base) that lie in the repository at `top`, relative to it."""
    out = [os.path.relpath(os.path.realpath(os.path.join(base, p)), top) for p in paths]
    return [p for p in out if not p.startswith("..")]


HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def diff_hunks(root):
    """[(path, removed lines, added lines)] of the working tree against HEAD, one entry per hunk, lines
    stripped. The hunk header gives the line counts, so a removed line that starts with "--" is not
    taken for a file header. A deleted file has no path."""
    out = _git(root, ["diff", "--no-color", "--no-renames", "-U0", "HEAD"])
    if out is None:
        return _fallback(root, "diff_hunks") or []
    hunks, path, rem, add = [], None, 0, 0
    for line in out.split("\n"):
        if rem and line.startswith("-"):
            hunks[-1][1].append(line[1:].strip())
            rem -= 1
        elif add and line.startswith("+"):
            hunks[-1][2].append(line[1:].strip())
            add -= 1
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            m = HUNK.match(line)
            if m:
                rem, add = int(m.group(1) or 1), int(m.group(2) or 1)
                hunks.append((path, [], []))
    return hunks


def diff_lines(root):
    """(removed, added): removed lines with their file, and the added lines with spaces normalized."""
    removed, added = [], set()
    for path, rem, add in diff_hunks(root):
        removed += [(path, l) for l in rem]
        added |= {" ".join(l.split()) for l in add}
    return removed, added


CSS_DECL = re.compile(r"^[\w-]+\s*:\s*[^;{}()]*;?$")


def signature(line):
    """Regex for the abstracted line, or None when it is too short or generic to search.

    Single CSS declarations (`z-index: 1;`) are skipped: abstracting them matches every rule, and
    the layout channel searches style structure instead."""
    if CSS_DECL.match(line):
        return None
    toks = TOKEN.findall(line)
    if len(toks) < MIN_TOKENS:
        return None
    parts, concrete = [], 0
    for i, t in enumerate(toks):
        after_dot = i > 0 and toks[i - 1] in (".", "?.")
        if re.match(r"[A-Za-z_$]", t) and t not in KEYWORDS and not after_dot:
            parts.append(r"[A-Za-z_$][\w$]*")
        else:
            parts.append(re.escape(t))
            concrete += t not in "(){}[],;" and t not in KEYWORDS
    if concrete < 3:
        return None
    return re.compile(r"\s*".join(parts))


def sig_channel(files, roots, base):
    seen, hits, broad = set(), [], {}
    for top in repos(roots):
        removed, added = diff_lines(top)
        rel_top = rel_to(top, base)
        for path, line in removed:
            if not line or line in seen or " ".join(line.split()) in added:
                continue
            seen.add(line)
            rx = signature(line)
            if rx is None:
                continue
            origin = os.path.normpath(os.path.join(rel_top, path)) if path else None
            found = []
            for f in files:
                for i, l in enumerate(f.lines, 1):
                    if rx.search(l) and not (os.path.normpath(f.path) == origin and l.strip() == line):
                        found.append((f, i))
            if len(found) > MAX_HITS:
                broad["sig:" + line[:40]] = len(found)
                continue
            for f, i in found:
                h = hit(f, i, "sig", 60, "还是修复前的写法：%s" % line[:60], line[:80], "")
                h["role"] = "old-code"
                hits.append(h)
    return hits, broad


def partners(top, seeds, min_support=2, min_conf=0.3):
    """{seed: [(other, n, total)]}: files changed in at least `min_support` of the seed's `total`
    commits and in at least `min_conf` of them, most frequent first. Paths are relative to `top`."""
    if not seeds:
        return {}
    # --no-renames: rename detection reads file contents and is slow on long histories.
    log = _git(top, ["log", "--no-merges", "--no-renames", "--full-diff", "--name-only", "--format=tformat:@@",
                     "-n", str(LOG_COMMITS), "--"] + seeds, timeout=120)
    if log is not None:
        commits = [set(filter(None, c.split("\n"))) for c in log.split("@@")]
    else:
        commits = _fallback(top, "log", seeds, LOG_COMMITS, MAX_COMMIT_FILES) or []
    commits = [c for c in commits if 0 < len(c) <= MAX_COMMIT_FILES]
    out = {}
    for seed in seeds:
        with_seed = [c for c in commits if seed in c]
        if len(with_seed) < min_support:
            continue
        counts = collections.Counter(o for c in with_seed for o in c if o != seed)
        kept = [(o, n, len(with_seed)) for o, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
                if n >= min_support and n / len(with_seed) >= min_conf]
        if kept:
            out[seed] = kept
    return out


def _partner_files(top, base, seeds, by_path, top_n):
    """{seed: [(file, n, total)]} for partners that are in the corpus, at most top_n per seed."""
    rel_top = rel_to(top, base)
    out = {}
    for seed, plist in partners(top, seeds).items():
        found = [(by_path[p], n, t) for p, n, t in
                 ((os.path.normpath(os.path.join(rel_top, o)), n, t) for o, n, t in plist) if p in by_path]
        if found:
            out[seed] = found[:top_n]
    return out


def cochange_channel(files, seed_files, roots, base, top=TOP_PARTNERS):
    """At most `top` partners per seed. Replaying the last 300 commits of the ThingsPanel repositories
    (docs/research/09 section 11), about 40% of the partners kept this way changed in the same
    commit as the seed."""
    by_path = {os.path.normpath(f.path): f for f in files}
    out = []
    for repo in repos(roots):
        for seed, plist in _partner_files(repo, base, in_repo(repo, base, seed_files), by_path, top).items():
            for f, n, total in plist:
                why = "过去 %d 次改 %s 时有 %d 次一起改了它（%.0f%%）" % (total, short(seed), n, 100.0 * n / total)
                h = hit(f, 1, "history", 35 + int(30 * n / total), why, seed, "")
                h["role"] = "co-change"
                out.append(h)
    return out


WORD = re.compile(r"[A-Za-z_$][\w$]*|\d+|[^\s\w]")
MIN_WORDS = 6
SIMILAR = 0.8
MAX_PER_LINE = 10
MAX_FILES_WITH_LINE = 4     # an old line found in more files than this is boilerplate, not a copy
COUNTERPART = 0.5           # an added line less similar than this to a removed one is not its new form
IMPORT = re.compile(r"^\s*(import\b|export\s+(\*|\{[^}]*\})\s*from\b|from\s+\S+\s+import\b|package\s|#include\b|using\s|"
                    r"(const|let|var)\s+\S+\s*=\s*require\()")


def _dice(a, b):
    if not a and not b:
        return 1.0
    ca, cb = collections.Counter(a), collections.Counter(b)
    return 2.0 * sum(min(n, cb[t]) for t, n in ca.items()) / (len(a) + len(b))


def _has_old(cand, old, new):
    """Whether the copy `cand` still has the old form somewhere the edit changed `old` into `new`.

    `cand` is aligned with `old`; at each place the edit changed, the tokens of `cand` between the
    aligned neighbours count as old when they are at least as close to the old tokens as to the new
    ones. So drift right next to the change (`< 6 && x`) is still old, and a copy fixed another way
    (`?? []` for `|| []`) is not. Without a new form (the edit dropped the line) any close copy is
    old code."""
    if new is None:
        return True
    pos = {}
    for a, b, size in difflib.SequenceMatcher(None, old, cand, autojunk=False).get_matching_blocks():
        for k in range(size):
            pos[a + k] = b + k
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        left = max((pos[k] for k in range(i1) if k in pos), default=-1)
        right = min((pos[k] for k in range(i2, len(old)) if k in pos), default=len(cand))
        seg = cand[left + 1:right]
        if _dice(seg, old[i1:i2]) >= _dice(seg, new[j1:j2]):
            return True
    return False


def _names(words):
    return [w for w in words if w[0].isalpha() or w[0] in "_$"]


def residue(files, roots, base, top=TOP_PARTNERS, skip=()):
    """Lines nearly the same as a line the edit removed, in the edited file itself and in the files
    that usually change with it (a copied page): the old line there probably needs the same fix.
    Names must match except one (copies keep them); small drift such as an appended `|| '--'` is
    tolerated. A copy is reported only where it still reads like the old line at a place the edit
    changed (see _has_old), so a copy fixed the same way is not; one fixed another way may be.
    Files in `skip` (relative to base: changes from before the task) are not taken as edits."""
    by_path = {os.path.normpath(f.path): f for f in files}
    out = []
    for repo in repos(roots):
        rel_top = rel_to(repo, base)
        hunks = [h for h in diff_hunks(repo) if h[0] and os.path.normpath(os.path.join(rel_top, h[0])) not in skip]
        added = {" ".join(l.split()) for _, _, add in hunks for l in add}
        old = {}
        for path, rem, add in hunks:
            # The new form of a removed line: the most similar added line of the hunk, or all of
            # them joined (a line the formatter split in three).
            news = [_words_of(a) for a in add] + ([_words_of(" ".join(add))] if len(add) > 1 else [])
            for line in rem:
                words = _words_of(line)
                if len(words) < MIN_WORDS or len(_names(words)) < 3 or " ".join(line.split()) in added \
                        or IMPORT.match(line) or line in [x[0] for x in old.get(path, [])]:
                    continue
                new = max(news, key=lambda w: _dice(words, w), default=None)
                if new is not None and _dice(words, new) < COUNTERPART:
                    new = None
                old.setdefault(path, []).append((line, words, max(_names(words), key=len), new))
        if not old:
            continue
        mates = _partner_files(repo, base, list(old), by_path, top)
        for seed, lines in old.items():
            own = by_path.get(os.path.normpath(os.path.join(rel_top, seed)))
            targets = ([(own, 0, 0)] if own is not None else []) + mates.get(seed, [])
            for line, words, rare, new in lines:
                names, found = collections.Counter(_names(words)), []
                for f, n, total in targets:
                    for i, l in enumerate(f.lines, 1):
                        if rare not in l or " ".join(l.split()) in added:
                            continue
                        cand = _words_of(l)
                        have = collections.Counter(_names(cand))
                        missing = sum(max(0, k - have[w]) for w, k in names.items())
                        if missing > 1 or missing > 0.2 * sum(names.values()):
                            continue
                        if _dice(words, cand) >= SIMILAR and _has_old(cand, words, new):
                            found.append((f, i, n, total))
                if len(found) > MAX_PER_LINE or (found and _common(files, line, rare)):
                    continue        # a generic line, not a copy
                # Identical lines in one file share an anchor and become one ledger item: list them all.
                groups = {}
                for f, i, n, total in found:
                    groups.setdefault((f.path, " ".join(f.lines[i - 1].split())), []).append((f, i, n, total))
                for rows in groups.values():
                    f, i, n, total = rows[0]
                    more = "（这个文件里有 %d 行一样：第 %s 行）" % (len(rows), "、".join(str(r[1]) for r in rows)) \
                        if len(rows) > 1 else ""
                    if f is own:
                        why = "你在这个文件里改掉的一行，这里还是旧写法%s：%s" % (more, line[:60])
                    else:
                        why = "常和 %s 一起改（%d/%d 次），这行和你改掉的一行几乎一样%s：%s" % (
                            short(seed), n, total, more, line[:60])
                    h = hit(f, i, "residue", 65, why, seed, "")
                    h["role"] = "old-code"
                    out.append(h)
    return out


def _words_of(line):
    return WORD.findall(line)


def _common(files, line, rare):
    """Whether the exact line is still in more than MAX_FILES_WITH_LINE files of the corpus."""
    norm, n = " ".join(line.split()), 0
    for f in files:
        if rare in f.text and any(rare in l and " ".join(l.split()) == norm for l in f.lines):
            n += 1
            if n > MAX_FILES_WITH_LINE:
                return True
    return False
