# Ledger

`.change-propagation/ledger.json` in the workspace that `seed` prints as `工作区`: the repository root, or the current directory when it is outside git or holds repositories one or two levels below it. The other commands look for the ledger from the current directory upwards, so they also work from a subdirectory. The directory holds a `.gitignore` containing `*`, so it never shows in `git status`. `seed --new` moves the previous ledger to `ledger-<time>.json` in the same directory.

## Top level

| Field | Meaning |
|---|---|
| `change`, `invariants` | what you wrote in `seed --change` and `--invariant` |
| `roots` | absolute paths searched |
| `seeds` | `names`, `keys`, `values` (`{value, near}`), `enums`, `layouts`, `like`, `funcs`, `diff`, `files` |
| `scans` | one entry per `scan` or `verify`: files, seconds, hits per channel, `too_broad` seeds, new items |
| `items` | candidates, below |
| `digests`, `lines` | sha1 and line-set checksums of each ledger file when it first appeared, so `verify` can tell lines the edit wrote from lines that were there |
| `untracked` | files untracked in git at the first scan; files untracked later count as written by the agent |
| `dirty` | files that differed from HEAD at the first scan, with sha1 digests; residue does not take them as edits while they are unchanged |

## Item

| Field | Written by | Meaning |
|---|---|---|
| `id` | script | `c1`, `c2`, …; stable across rescans |
| `path`, `line` | script | relative to the workspace; `line` is refreshed on rescans |
| `anchor` | script | the stripped source line, used to find the item again after lines move |
| `layer`, `stack` | script | frontend, backend, locale, config, sql, docs, test, other |
| `channels`, `queries`, `why`, `roles` | script | which channels and seeds hit, a one-line reason, contract roles (producer, consumer, schema, definition, use, publisher, subscriber) |
| `score` | script | 0-100; ordering only, not a tier |
| `mismatch` | script | a field read under a spelling the backend does not write |
| `generated`, `comment` | script | generated file; whole-line comment |
| `tier` | agent | direct, coupled, review, exclude |
| `status` | agent | open, asked, confirmed, declined, edited, listed |
| `note` | agent | evidence or the user's answer |
| `after` | verify | the new text of the line once it was edited |
| `block` | script | `[start, end, checksum]` of the enclosing function or style rule at scan time; `verify` compares it to tell whether the item was edited |
| `bulk` | mark | tiered with `rest`, so its block was not read |
| `moved` | verify | the line is in a file the agent created (a shared helper); not a failure |

## Status flow

- direct: `open` → `edited`. `verify` sets `edited` when the item's block changed, and gives direct/edited to changed lines inside that block and to new lines the edit wrote.
- coupled: `open` → `asked` → `confirmed` → `edited`, or `asked` → `declined`. Without a way to ask, stay at `asked` and list it, or use `listed`.
- review: `listed` (set when tiered); if the user asks for it, `confirmed` → `edited`.
- exclude: `listed` (set automatically), with the reason in `note`. `verify` reports it if the line changed.

`mark` refuses `edited` for coupled and review items that are not `confirmed`.
