"""Read-only access to a git repository without the git binary.

Some sandboxes deny the git executable: the Claude Code eval sandbox on macOS masks it, because the
credential helpers under git-core are links to it. The scripts then read the repository directly:
refs, packed-refs, shallow commits, loose objects and v2 pack files with offset and reference
deltas. That covers the HEAD tree, the files each commit changed, and blob contents for the
working-tree diff. Nothing is written. Standard library only.
"""
import difflib
import hashlib
import heapq
import mmap
import os
import struct
import zlib

ERRORS = (OSError, ValueError, KeyError, IndexError, struct.error, zlib.error)   # what a bad repository raises

TYPES = {1: "commit", 2: "tree", 3: "blob", 4: "tag"}
TREE_MODE = b"40000"
LINK_MODE = b"120000"
GITLINK_MODE = b"160000"
CACHE_MAX = 20000           # decoded objects kept per repository
BIG_BLOB = 1 << 20          # blobs larger than this are not cached


_OPEN = {}


def open_repo(path):
    """(top directory, Repo) for the repository that holds `path`, or None. Repo objects are
    cached, so their object caches last for the whole command; call reset() between commands."""
    found = find_repo(path)
    if found is None:
        return None
    key = os.path.realpath(found[1])
    if key not in _OPEN:
        _OPEN[key] = Repo(found[1])
    return found[0], _OPEN[key]


def reset():
    """Forget working-tree state (what differs from HEAD) of the cached repositories."""
    for repo in _OPEN.values():
        repo.dirty = None


def find_repo(path):
    """(top directory, git directory) of the repository that holds `path`, or None."""
    p = os.path.abspath(path)
    while True:
        dot = os.path.join(p, ".git")
        if os.path.isdir(dot):
            return p, dot
        if os.path.isfile(dot):
            try:
                with open(dot, encoding="utf-8") as fh:
                    line = fh.readline().strip()
            except OSError:
                return None
            if line.startswith("gitdir:"):
                return p, os.path.normpath(os.path.join(p, line[len("gitdir:"):].strip()))
            return None
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def _size(buf, pos):
    """Little-endian base-128 number at buf[pos] (delta header sizes)."""
    n = shift = 0
    while True:
        c = buf[pos]
        pos += 1
        n |= (c & 0x7f) << shift
        shift += 7
        if not c & 0x80:
            return n, pos


def apply_delta(base, delta):
    """The object that `delta` (git's copy/insert format) builds from `base`."""
    src, pos = _size(delta, 0)
    dst, pos = _size(delta, pos)
    if src != len(base):
        raise ValueError("delta base has the wrong size")
    out, n = bytearray(), len(delta)
    while pos < n:
        op = delta[pos]
        pos += 1
        if op & 0x80:
            off = size = 0
            for i in range(4):
                if op & (1 << i):
                    off |= delta[pos] << (8 * i)
                    pos += 1
            for i in range(3):
                if op & (0x10 << i):
                    size |= delta[pos] << (8 * i)
                    pos += 1
            out += base[off:off + (size or 0x10000)]
        elif op:
            out += delta[pos:pos + op]
            pos += op
        else:
            raise ValueError("bad delta instruction")
    if len(out) != dst:
        raise ValueError("delta result has the wrong size")
    return bytes(out)


def _inflate(data, pos, size):
    """`size` bytes inflated from the zlib stream at data[pos]."""
    d, out, step = zlib.decompressobj(), [], size + 64
    while not d.eof:
        chunk = data[pos:pos + step]
        if not chunk:
            break
        out.append(d.decompress(chunk))
        pos += len(chunk)
        step *= 2
    res = b"".join(out)
    if len(res) != size:
        raise ValueError("corrupt object in pack")
    return res


class Pack:
    """One pack file and its version 2 index."""

    def __init__(self, idx_path):
        with open(idx_path, "rb") as fh:
            self.idx = fh.read()
        if self.idx[:4] != b"\xfftOc" or struct.unpack(">I", self.idx[4:8])[0] != 2:
            raise ValueError("unsupported pack index %s" % idx_path)
        self.fanout = struct.unpack(">256I", self.idx[8:1032])
        n = self.fanout[255]
        self.sha_at, self.ofs_at = 1032, 1032 + 24 * n
        self.big_at = self.ofs_at + 4 * n
        self.path = idx_path[:-4] + ".pack"
        self._data = None

    @property
    def data(self):
        if self._data is None:
            with open(self.path, "rb") as fh:
                try:
                    self._data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
                except (OSError, ValueError):       # mmap not allowed here: read it instead
                    self._data = fh.read()
        return self._data

    def offset(self, sha):
        """Offset of object `sha` (20 bytes) in the pack, or None."""
        lo = self.fanout[sha[0] - 1] if sha[0] else 0
        hi, idx = self.fanout[sha[0]], self.idx
        while lo < hi:
            mid = (lo + hi) // 2
            cur = idx[self.sha_at + 20 * mid:self.sha_at + 20 * mid + 20]
            if cur < sha:
                lo = mid + 1
            elif cur > sha:
                hi = mid
            else:
                o = struct.unpack(">I", idx[self.ofs_at + 4 * mid:self.ofs_at + 4 * mid + 4])[0]
                if o & 0x80000000:
                    k = self.big_at + 8 * (o & 0x7fffffff)
                    o = struct.unpack(">Q", idx[k:k + 8])[0]
                return o
        return None

    def header(self, offset):
        """(type number, size, position after the header) of the entry at `offset`."""
        data, pos = self.data, offset
        c = data[pos]
        kind, size, shift = (c >> 4) & 7, c & 15, 4
        while c & 0x80:
            pos += 1
            c = data[pos]
            size |= (c & 0x7f) << shift
            shift += 7
        return kind, size, pos + 1


class Repo:
    """Objects and refs of one repository (`gitdir` is its .git directory)."""

    def __init__(self, gitdir):
        self.gitdir = self.common = gitdir
        common = os.path.join(gitdir, "commondir")
        if os.path.isfile(common):          # a linked worktree keeps objects in the main .git
            with open(common, encoding="utf-8") as fh:
                self.common = os.path.normpath(os.path.join(gitdir, fh.read().strip()))
        self.objdirs = [os.path.join(self.common, "objects")]
        alt = os.path.join(self.objdirs[0], "info", "alternates")
        if os.path.isfile(alt):
            with open(alt, encoding="utf-8") as fh:
                self.objdirs += [os.path.normpath(os.path.join(self.objdirs[0], l.strip()))
                                 for l in fh if l.strip() and not l.startswith("#")]
        self.shallow = set()
        try:
            with open(os.path.join(self.common, "shallow"), encoding="utf-8") as fh:
                self.shallow = {l.strip() for l in fh if l.strip()}
        except OSError:
            pass
        self.packs, self.objects, self.commits, self.trees = None, {}, {}, {}
        self.dirty = None

    def _remember(self, key, obj):
        if len(self.objects) > CACHE_MAX:
            self.objects.clear()
        if obj[0] != "blob" or len(obj[1]) <= BIG_BLOB:
            self.objects[key] = obj

    def _at(self, pack, offset):
        """(type, content) of the pack entry at `offset`, resolving delta chains."""
        deltas = []                         # (cache key, delta), outermost first
        while True:
            key = (pack.path, offset)
            base = self.objects.get(key)
            if base is not None:
                break
            kind, size, pos = pack.header(offset)
            if kind == 6:                   # offset delta: base is earlier in the same pack
                data = pack.data
                c = data[pos]
                rel, pos = c & 0x7f, pos + 1
                while c & 0x80:
                    c = data[pos]
                    rel, pos = ((rel + 1) << 7) | (c & 0x7f), pos + 1
                deltas.append((key, _inflate(data, pos, size)))
                offset -= rel
            elif kind == 7:                 # reference delta: base named by id
                base_id = bytes(pack.data[pos:pos + 20])
                deltas.append((key, _inflate(pack.data, pos + 20, size)))
                base = self.read(base_id)
                if base is None:
                    raise KeyError("missing delta base %s" % base_id.hex())
                break
            elif kind in TYPES:
                base = (TYPES[kind], _inflate(pack.data, pos, size))
                self._remember(key, base)
                break
            else:
                raise ValueError("bad object type %d in %s" % (kind, pack.path))
        for key, delta in reversed(deltas):
            base = (base[0], apply_delta(base[1], delta))
            self._remember(key, base)
        return base

    def read(self, sha):
        """(type, content) of object `sha` (hex or 20 bytes), or None when it is not here
        (a partial clone leaves old blobs out)."""
        if isinstance(sha, str):
            sha = bytes.fromhex(sha)
        obj = self.objects.get(sha)
        if obj is not None:
            return obj
        obj = self._packed(sha) or self._loose(sha)
        if obj is None and self.packs is not None:
            self.packs = None               # a pack written since the list was read
            obj = self._packed(sha)
        if obj is not None:
            self._remember(sha, obj)
        return obj

    def _packed(self, sha):
        if self.packs is None:
            self.packs = []
            for od in self.objdirs:
                pd = os.path.join(od, "pack")
                names = sorted(os.listdir(pd)) if os.path.isdir(pd) else []
                self.packs += [Pack(os.path.join(pd, n)) for n in names if n.endswith(".idx")]
        for pack in self.packs:
            off = pack.offset(sha)
            if off is not None:
                return self._at(pack, off)
        return None

    def _loose(self, sha):
        h = sha.hex()
        for od in self.objdirs:
            try:
                with open(os.path.join(od, h[:2], h[2:]), "rb") as fh:
                    raw = zlib.decompress(fh.read())
            except OSError:
                continue
            head, _, body = raw.partition(b"\0")
            return head.split(b" ")[0].decode("ascii"), body
        return None


    def _ref(self, name):
        for d in (self.gitdir, self.common):
            try:
                with open(os.path.join(d, name), encoding="utf-8") as fh:
                    return fh.read().strip()
            except OSError:
                pass
        try:
            with open(os.path.join(self.common, "packed-refs"), encoding="utf-8") as fh:
                for line in fh:
                    sha, _, ref = line.strip().partition(" ")
                    if ref == name and not line.startswith(("#", "^")):
                        return sha
        except OSError:
            pass
        return None

    def resolve(self, ref="HEAD"):
        """Commit id (hex) that `ref` points to, or None."""
        for _ in range(10):
            val = self._ref(ref)
            if not val:
                return None
            if not val.startswith("ref:"):
                return val[:40]
            ref = val[4:].strip()
        return None

    def commit(self, sha):
        """(tree, parents, commit time) of commit `sha` (hex), or None."""
        if sha in self.commits:
            return self.commits[sha]
        obj = self.read(sha)
        if obj is None or obj[0] != "commit":
            return None
        tree, parents, when = None, [], 0
        for line in obj[1].split(b"\n"):
            if not line:
                break
            if line.startswith(b"tree "):
                tree = line[5:].decode("ascii")
            elif line.startswith(b"parent "):
                parents.append(line[7:].decode("ascii"))
            elif line.startswith(b"committer "):
                try:
                    when = int(line.rsplit(b" ", 2)[1])
                except (IndexError, ValueError):
                    pass
        if sha in self.shallow:
            parents = []
        self.commits[sha] = (tree, parents, when)
        return self.commits[sha]

    def tree(self, sha):
        """{name: (mode, id hex)} of tree `sha`; submodule entries are left out."""
        if sha in self.trees:
            return self.trees[sha]
        obj = self.read(sha)
        out = {}
        if obj is not None and obj[0] == "tree":
            data, i = obj[1], 0
            while i < len(data):
                sp = data.index(b" ", i)
                nul = data.index(b"\0", sp)
                mode = data[i:sp].lstrip(b"0") or b"0"
                if mode != GITLINK_MODE:
                    out[data[sp + 1:nul].decode("utf-8", "replace")] = (mode, data[nul + 1:nul + 21].hex())
                i = nul + 21
        if len(self.trees) > CACHE_MAX:
            self.trees.clear()
        self.trees[sha] = out
        return out

    def changed(self, a, b, limit=None, prefix="", out=None):
        """Paths whose entries differ between trees `a` and `b` (either may be None), like
        `git diff --name-only --no-renames`. Stops once more than `limit` are found."""
        out = set() if out is None else out
        ta, tb = (self.tree(a) if a else {}), (self.tree(b) if b else {})
        for name in sorted(set(ta) | set(tb)):
            ea, eb = ta.get(name), tb.get(name)
            if ea == eb:
                continue
            sub_a = ea[1] if ea and ea[0] == TREE_MODE else None
            sub_b = eb[1] if eb and eb[0] == TREE_MODE else None
            if sub_a or sub_b:
                self.changed(sub_a, sub_b, limit, prefix + name + "/", out)
            if (ea and ea[0] != TREE_MODE) or (eb and eb[0] != TREE_MODE):
                out.add(prefix + name)
            if limit is not None and len(out) > limit:
                break
        return out

    def touches(self, a, b, parts):
        """Whether the file at path `parts` differs between trees `a` and `b`."""
        for i, name in enumerate(parts):
            if a == b:
                return False
            ea = self.tree(a).get(name) if a else None
            eb = self.tree(b).get(name) if b else None
            if i == len(parts) - 1:
                return ea != eb and any(e and e[0] != TREE_MODE for e in (ea, eb))
            a = ea[1] if ea and ea[0] == TREE_MODE else None
            b = eb[1] if eb and eb[0] == TREE_MODE else None
        return False


MAX_WALK = 50000     # commits visited at most per log call


def log(top, repo, paths, limit, max_files):
    """Changed paths of the newest `limit` non-merge commits reachable from HEAD that change one
    of `paths`, newest first by commit time, like git log --no-merges --no-renames --full-diff
    --name-only -n LIMIT -- PATHS. As in git's default history simplification, a merge that leaves
    the paths as one parent had them is followed only through that parent. A commit that changes
    more than `max_files` files comes back with `max_files` + 1 of them."""
    head = repo.resolve("HEAD")
    first = repo.commit(head) if head else None
    if first is None:
        return []
    parts = [p.split("/") for p in paths]
    heap, seen, out = [(-first[2], head)], {head}, []
    walked = 0
    while heap and len(out) < limit and walked < MAX_WALK:
        walked += 1
        _, sha = heapq.heappop(heap)
        tree, parents, _ = repo.commit(sha)
        follow = parents
        if len(parents) > 1:
            same = [p for p in parents if repo.commit(p) is not None
                    and not any(repo.touches(repo.commit(p)[0], tree, pt) for pt in parts)]
            follow = same[:1] or parents
        for p in follow:
            pc = repo.commit(p) if p not in seen else None
            if pc is not None:
                seen.add(p)
                heapq.heappush(heap, (-pc[2], p))
        if len(parents) > 1:
            continue
        base = repo.commit(parents[0]) if parents else None
        base_tree = base[0] if base else None
        if any(repo.touches(base_tree, tree, pt) for pt in parts):
            out.append(repo.changed(base_tree, tree, max_files))
    return out


def head_files(repo):
    """{path: (mode, blob id)} of every file in the HEAD tree."""
    head = repo.resolve("HEAD")
    c = repo.commit(head) if head else None
    out, stack = {}, [(c[0], "")] if c else []
    while stack:
        sha, prefix = stack.pop()
        for name, (mode, ident) in repo.tree(sha).items():
            if mode == TREE_MODE:
                stack.append((ident, prefix + name + "/"))
            else:
                out[prefix + name] = (mode, ident)
    return out


def blob_id(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _working(top, path, mode):
    """Bytes git would hash for the working copy of `path`, or None if it is gone."""
    full = os.path.join(top, path)
    try:
        if mode == LINK_MODE:
            return os.readlink(full).encode("utf-8")
        with open(full, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _dirty(top, repo):
    """{path: (mode, HEAD blob id, working bytes or None)} for tracked files that differ from HEAD.
    Computed once per repository: the scripts do not change the working tree while they run."""
    if repo.dirty is None:
        repo.dirty = {}
        for path, (mode, ident) in head_files(repo).items():
            now = _working(top, path, mode)
            if now is None or blob_id(now) != ident:
                repo.dirty[path] = (mode, ident, now)
    return repo.dirty


def changed_files(top, repo):
    """Tracked paths whose working copy differs from HEAD or is gone (git diff --name-only HEAD)."""
    return sorted(_dirty(top, repo))


def _text(data):
    """Lines as git counts them: a final newline does not start another line."""
    if data is None or b"\0" in data[:8000]:
        return None
    lines = data.decode("utf-8", "replace").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def diff_hunks(top, repo):
    """[(path, removed lines, added lines)] per hunk of the working tree against HEAD, lines
    stripped, like `git diff -U0 HEAD`; a deleted file has path None, binary files are skipped.
    The hunks come from difflib, so they can be split differently from git's."""
    out = []
    for path, (mode, ident, now) in sorted(_dirty(top, repo).items()):
        old = repo.read(ident)
        a, b = _text(old[1] if old else None), _text(now) if now is not None else []
        if a is None or b is None:
            continue
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                out.append((path if now is not None else None, [l.strip() for l in a[i1:i2]],
                            [l.strip() for l in b[j1:j2]]))
    return out


def untracked(top, repo, listing):
    """Paths in `listing` (relative to `top`) that are not in the HEAD tree."""
    tracked = head_files(repo)
    return sorted(p for p in listing if p not in tracked)
