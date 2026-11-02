---
name: change-propagation
description: Finds every other place a change must reach before and after editing, such as look-alike components with different names, copies that drifted, the other end of a JSON field, MQTT topic or WebSocket event, and other layers that enforce the same rule. Use when a fix, bug report or requirement names one place but the same component, handler, copy or displayed text may live elsewhere and need the same change (修某个组件、页面、处理函数或提示文案的 bug，别处可能有同样的副本；类似的、同类的、统一修改、其他地方也要改), when changing a shared rule such as a validation limit, constant, enum value or i18n text (规则在多处要一致), when changing how one status, level or type is shown, such as its colour, icon or label, because other cards, badges and charts map the same values (提示消息改成蓝色、某个状态换颜色), when asked to change all X-like components (所有弹窗、所有列表), or when extracting or deduplicating repeated logic (抽取公共函数、去重、合并重复实现). Runs offline scripts first, keeps the candidate ledger on disk, edits direct hits, asks before editing inferred couplings, and lists low-confidence sites.
argument-hint: "[change description]"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py *)
---

# change-propagation

A change usually names one place. Your job is to find the other places that must change with it, and handle each by tier. Read the rules first; they apply for the whole task, including after context compaction. The project you change is the current directory; the skill's base directory only holds the scripts, so do not search it.

## Rules

Every candidate gets one tier, decided by what the user asked for and the evidence, not by which search found it. First decide the scope of the request: a single object ("the register form"), or a set ("all popups", "similar lists too", "replace every duplicate implementation").

- **direct**: edit it. Inside the requested scope:
  - The object the user named, its own text (the hint and error message it shows, including locale entries it displays) and its own tests that assert the old value.
  - When the request covers a set: every candidate that reading its block shows to be a member of that set, whatever its name or way of writing. Members you found yourself are what the user asked for; do not ask about them. For duplicates the user asked to merge, this includes copies that drifted inside the same package; say in the report which behaviour changes (padding, an off-by-one month).
  - When the change is how one value of a set looks or behaves (info shown blue, an icon for a status): every other table that renders the same value of the same set for the same thing, such as a summary card coloured by message share, a header badge or a chart legend. A table that lacks the value and falls back to a default is the usual miss. Tables of a different set that only share the value names (log levels, button or tag types) are exclude.
  - Places a type check, compiler or test proves must follow, and places a sync comment in or right above the edited code points to.
- **coupled**: ask first, edit only after the user agrees. Outside the requested scope but probably affected: other layers and other users of the same rule (server validator, other forms, API docs, shared locale text), the other end of a contract the user did not name, look-alikes of a single named object when the user did not say "similar" or "all", and copies across a package or service boundary or whose merge changes stored or grouped data (UTC vs local day).
- **review**: list only. Single weak signal, low-similarity candidates, and anything you rejected (with the reason).
- **exclude**: do not touch. Same name or value with a different meaning.

If a text entry the named object shows is shared with a coupled site (one locale key used by the register and the reset form), give the named object its own entry and leave the shared one as it is, rather than changing it for both.

Hard rules:

1. Never edit a coupled or review item before the user confirmed it in this conversation. `cp.py mark` refuses to mark them edited without a `confirmed` status. If you cannot ask (AskUserQuestion is unavailable or denied, `-p`, dontAsk), leave them unedited and list them in your final message with `path:line` and the question you would ask. Still finish every direct item first: not being able to ask is never a reason to leave direct items undone.
2. Do not edit the docs or tests that belong to an unconfirmed coupled item (the server tests of a server validator).
3. Edit only direct and confirmed items. No renames or refactors on the side.
4. The task is done only when `cp.py verify` shows no unhandled item. "Listed, not edited" is a normal outcome.
5. The ledger is the source of truth: `.change-propagation/ledger.json` in the `工作区` that `seed` prints (the repository root, or the current directory when it is outside git or holds several repositories). Keep only summaries and the blocks you read in context; fetch the rest by ID.

## Commands

Run every command exactly in this form, from the workspace root, without `cd`, pipes or redirection, so the permission rule matches. Output paths are relative to the `工作区` line that `seed` prints.

```
python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py seed --new --scan --change "..." [--invariant "..."] [--name X] [--key K] [--value V --near w1,w2] [--enum CHANGED,SIBLING,...] [--layout header-in-scroll] [--like EXAMPLE] [--func PATH:NAME] [--diff] [--file PATH] [--root DIR]
python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py scan [--top 30]
python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py show c3,c7-c9 [--context 5]
python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py mark c1,c2 direct c3,c5-c9 coupled/asked "same rule on the server" c4 exclude "phone length" [--verify]
python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py add a.vue:42 b.vue:17 --why "same grey header inside the scroll box" [--tier direct]
python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py verify
python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py status [--all]
```

Each tool call re-sends the whole conversation, so keep calls few: tier all candidates in one `mark` call (groups of `IDS TIER[/STATUS] ["note"]`), `add` all positions that share a reason in one call, `show` several IDs at once, seed and scan in one call with `seed --scan`, and skip `status` right after a scan unless it said items were hidden. Do not mark items `edited` yourself: `verify` does it for direct and confirmed items whose block changed, and for lines your edit wrote.

Statuses: `open` → `asked` → `confirmed` or `declined`; then `edited`. Review and exclude items become `listed` when tiered. Use `listed` for coupled items you report without asking, `declined` when the user said no. `mark rest` addresses all open items without a tier. Fields and the full status flow: [references/ledger.md](references/ledger.md).

## Workflow

1. **Write down the change and its invariant**: what changes, before and after, and "A and B must agree on Z" if a rule is shared. They go in `seed --change` and `--invariant`.
2. **Seed first, before exploring.** Take seeds from the prompt and from the diff you made or plan to make (see [references/channels.md](references/channels.md)). `--file`, `--like` and `--func` accept a bare file name or a path suffix (`notice-message.vue`); the script finds it under the roots, so do not run `ls`, `find` or Glob to locate it:
   - `--name`: identifiers you touch (all spellings are searched: camel, snake, Pascal, kebab, SCREAMING).
   - `--key`: JSON fields, MQTT topics or WS paths, i18n keys. A field read and written under different spellings is flagged `不一致`.
   - `--value`: the old literal and old text, e.g. `--value 8 --near password,pwd,密码` and `--value "至少 8 位"`. Numbers need `--near`; the scan finds the rule in validators, struct tags, locale files, docs, SQL and config.
   - `--enum`: when one value of a set changes (info shown blue, a new status): changed value first, then its siblings, `--enum info,warning,error,success`, plus the old look as a value (`--value transparent`). Tables that map the siblings but not the changed value and fall back to a default are flagged, and so are arrays matched by position to an array of the values (`COLORS[LEVELS.indexOf(level)]`, a chart `color` list).
   - `--layout header-in-scroll`: layout changes to lists and tables. Finds every component whose column-title row is the first child of a vertical scroll container (style block, nested SCSS, utility classes, inline style or `n-scrollbar`), follows a header rendered by a child component, and lists library tables (`NDataTable`) inside scroll boxes or scrolling layout slots.
   - `--like EXAMPLE`: "all X" requests (all popups, all cards). Builds a feature card from the example file and its stylesheets (tags, class words, `position: fixed`, `z-index`, `createPortal`, `mask`) and ranks other frontend files by rare shared features. Give 2-3 examples when you know them.
   - `--func PATH:NAME`: duplicates and drifted copies. Finds functions whose body is similar after renaming variables, including renamed copies.
   - `--diff`: after you edit, finds other places that still contain a line your uncommitted diff removed (the old code), abstracted over local names.
   - `--file`: every file you will edit. Finds "keep in sync" comments pointing at it and from it, and the files past commits usually changed with it (needs git history; co-change alone is a weak signal, read the block before tiering).
   - `--root`: sibling repositories (other frontends, backends). Search every frontend and backend root you know of.
3. **Scan.** `seed --scan` (or `scan`) writes all candidates to the ledger and prints a short summary grouped by layer. "太泛" means a seed is too broad: make it more specific instead of reading everything.
4. **Read only the blocks.** `show <IDs>` prints the enclosing function or style rule. Do not open whole files to triage.
5. **Tier.** Give every candidate a tier and a short note on the evidence, in one `mark` call. Positions you find by reading code go in with `add`, then `mark`.
6. **Ask once.** Group coupled items by rule ("Should reset-password use the same 12-character minimum?"), not by file, and ask with one AskUserQuestion call: at most 4 questions with up to 4 options each, a recommended option first, evidence in the description. Mark them `asked` before asking; then `confirmed` or `declined` from the answer. A timeout or no answer counts as not confirmed.
7. **Edit** direct and confirmed items.
8. **Verify.** `verify` marks the edited items, reruns all queries on the edited code and lists only what is still wrong, including copies of the lines you removed that are left in the edited file or in a file that usually changes with it (`residue`). Edit the new hits that are direct, then tier all of them in one `mark ... --verify` call. Old values inside files you created (a shared helper) are listed, not failures. On a pass it prints each package's check commands and whether dependencies are installed; run those, do not search for them.

## Choosing seeds by change type

- Rule or limit (S1): `--value` with `--near`, `--name` of the constant, `--key` of the i18n text.
- Contract: `--key` for the field, topic or WS path; add `--root` for every other end.
- One value of a set shown differently: `--enum` plus `--value` of the old look.
- Layout of similar lists: `--layout header-in-scroll`, plus `--diff` after fixing the named one.
- "All X" components (S2): `--like` with the named example; read each candidate's block before tiering, a shared feature is not proof.
- Duplicates (S3): `--func` for each known copy; record for each copy how it differs and whether it is deleted or turned into a call.

The scripts do not cover structures other than header-in-scroll yet. For other layout changes, write a feature card yourself (class names, library wrappers, the structure the fix changes), search each feature in each way it can be written, and `add` what you find.

## Permission modes

- **auto / default:** commands as above; ask with AskUserQuestion in the same turn. If the user answers in a new message, run `status` and continue from the open ledger.
- **plan:** only the plan file is writable. Use `scan` output, put the full tier list in a "Ledger" appendix of the plan (it overrides "list a few representative paths"), and write the ledger after the plan is approved.
- **`-p` / dontAsk:** no questions possible; see hard rule 1.

## Final report

In the user's language, state: what you edited (`path:line`), what you asked and the answers, what you listed without editing and why (`path:line` for each), what you excluded, which seeds and roots you searched, and what you did not search. Do not claim the list is complete; say which channels it covers.
