# Channels and seeds

What `cp.py scan` searches, what each channel is good for, and where it stops. All channels search every root in the ledger (`seed --root`), skip `node_modules`, `dist`, `vendor`, `build`, files ignored by git, binaries, files over 1 MB, and never read `.env` or key files. Generated files (`Code generated ... DO NOT EDIT`) are kept but scored 30 lower.

## name (`--name`)

Every spelling of an identifier: `lastVisitTime`, `LastVisitTime`, `last_visit_time`, `last-visit-time`, `LAST_VISIT_TIME`, and Go initialisms (`AGVTaskID`). Whole tokens only, so `id` does not match `width`.

Good for: functions, constants and types you touch; finding copies that kept the name (`normalizeAlarmLevel` in two components).
Misses: copies that were renamed. Search their body instead (see SKILL.md).

## value and rule (`--value`, `--near`)

- A string value (`--value "至少 8 位"`, `--value "? '在线' : '离线'"`) is matched literally everywhere.
- A number or a value of 1-2 characters needs `--near` context words. A hit counts only when a context word is on the same line or within 2 lines, and scores higher when the line looks like a rule: comparisons (`< 6`, `>= 8`), `min=6` tags, `minLength: 8`, `{8,}`, `8 位`, `at least 8 characters`, `至少6位`, `MAX_LEN = 8`.

Good for S1: one rule written in several layers (frontend validator, backend struct tag and service check, locale text, API docs, config messages, SQL). Pick context words in every language the code uses: `password,pwd,密码`.
Noise: other rules with the same number next to the same words (`form.phone.lenMin6` next to `form.pwd.*`). Mark them exclude.

## contract (`--key`)

The kind is chosen from the key:

| Key looks like | Kind | Finds |
|---|---|---|
| `agv/+/status`, `devices/telemetry/control/+`, `/api/ws/online` | topic or path | literals that can match it, with `+`, `#`, `%s`, `{x}`, `${x}`, `:x` treated as wildcards; role `publisher` or `subscriber` from the call |
| `form.pwd.tip`, `auth.passwordHint` | i18n key | flat definitions in locale files, nested definitions of the last segment in locale files, and uses (`$t('…')`, `t('…')`) |
| anything else | JSON field | Go `json:"…"` and `gorm:"column:…"` tags, pydantic aliases, object keys (producers), property reads and `["…"]` (consumers), type members (schema) |

For a field, a frontend reader whose spelling no backend schema or producer uses is flagged `不一致` and scored 25 higher: `row.lastVisitTime` read while the backend only writes `last_visit_time`.

Misses: keys built at runtime from pieces (`prefix + '/status'`), and frontends or backends outside the roots.

## enum mapping (`--enum`)

`--enum info,warning,error,success`: the first value is the one that changes, the rest are its siblings. A table is a run of lines (gaps up to 6 lines) where two or more of the values appear as a string literal (`'info'`), a key (`info:`), a class or BEM suffix (`.tip--info`), or a member (`LEVEL.INFO`). `console.error(` calls and boolean keys (`success: true`) do not count.

- Table with the changed value: score 60, likely needs the same change.
- Table with siblings but without the changed value, and a `default:`, `??`, `||` or `else` nearby: score 70. The changed value falls through to the fallback, which is how an overview card coloured by message share keeps showing info in the old colour.
- Siblings without the changed value and no fallback: score 40.

Arrays matched by position: an array of two or more of the values as string literals (`['info', 'success', ...]`) and, within 20 lines, another array of the same length with none of the values (`COLORS`, an ECharts `color` list). The item at the changed value's index is reported (score 70). Not covered: colour arrays in another file than the value array, or arrays built in code.

Good for: "make info messages blue", "add a status", "rename a level". Noise: generic component props (`type="error"` on alerts and tags) also match; read the block and mark unrelated tables exclude. On the 800-file ThingsPanel frontend `--enum info,warning,error,success` gives about 90 tables, 10 of them flagged as falling back.

## declared (`--file`, plus `--name` and `--key`)

Comments such as "keep in sync with", "must match", "if you change X also update", `LINT.IfChange`, and Chinese wording (保持一致, 同步修改, 也要改, 与…一致).

- Forward: a sync comment inside a seed file; the file paths and identifiers it names become candidates.
- Reverse: a sync comment anywhere that names a seed file or seed name. A file name that more than 3 files share (`index.vue`) counts only together with its directory (`scene-edit/index`).

Precision on English wording was 60-65% in the research sample; read the target before trusting it.

## layout (`--layout header-in-scroll`)

Reads each `.vue` file's template tree (html.parser) and style blocks (SCSS nesting resolved), plus utility classes (`overflow-y-auto`, `h-300px`, `sticky`, `bg-*`) and inline styles.

- Score 70: a header row (painted background or sticky, 2+ text cells, about as many cells as the rows) is the first child of a vertical scroll container, directly followed by the repeated rows. A header rendered by a child component is followed one import hop; the child is listed at 55.
- Score 50: a library table (`NDataTable`, `el-table`) is a child of a scroll container, so its own header scrolls with it.
- Score 45 and 40: a library table placed in a layout component's slot whose wrapper scrolls, or a few wrappers below a scrolling page box.

Misses: headers built from render functions or TSX, scroll set only by a parent page, tables with their own `max-height` (correct, not reported). On the 800-file ThingsPanel frontend it finds the 4 natural instances; with the 7 planted lists it finds all 7 and no decoy, in under 1 s.

## like (`--like FILE`)

Feature card from the example and the stylesheets it imports: custom and library tags, words from class names and popup-ish APIs (`mask`, `modal`, `createPortal`, `Teleport`, `keydown`), layout declarations (`position: fixed`, `z-index`, `inset`, `animation`). Other frontend files are ranked by shared features weighted by rarity; features in more than a third of files are dropped. Hits point at the first line showing a shared feature.

Good for: "all popups", "all cards". On the 40-file shop fixture with `Modal.tsx` as the example it ranks the 5 other popups (including an imperative DOM layer and an inline layer in a page) and the drawer in the top 6, the toast seventh, and does not list the tooltip.

## func (`--func PATH:NAME`)

Tokenizes Go functions and named TS/JS/Vue-script functions, replaces identifiers, strings and numbers with placeholders, and compares winnowed 5-token fingerprints. Ranked by containment (how much of the query appears in the candidate), scaled down when the candidate is much larger. On ThingsPanel (2.3k files, about 6 s) `actionValueChange` finds its drifted copy in `edit-action.vue` first (90%), and `normalizeAlarmLevel` finds the copy in `ThingsVisWidget.vue` first (87%). Below the first one or two hits the list is noise; read before trusting.

Misses: functions shorter than 25 tokens, arrow functions with expression bodies, copies rewritten with different control flow.

## diff and history (`--diff`, `--file`)

- `--diff`: each line removed by the uncommitted diff (against HEAD) is abstracted (local identifiers wild; member names, literals and operators kept) and searched in every file. A signature that matches more than 20 lines is reported as too broad. Lone CSS declarations are skipped.
- Co-change: for each `--file`, up to 5 files changed in at least 2 of its commits and in at least 30% of them, most frequent first. Commits touching more than 30 files are ignored and renames are not followed. Needs real git history; a shallow or squashed clone gives nothing. Replayed on the last 300 commits of the ThingsPanel frontend and backend, 42% and 41% of these partners changed in the same commit as the seed, and 39% and 26% of seeds got at least one right partner.
- Residue (no seed needed, every scan and verify): each line the uncommitted diff removed (6+ tokens, not an import) is looked for in the edited file and in its top 5 co-change partners. A line counts when its names match except one and it still reads like the old line where the edit changed it: after `… + item.placeholder` was fixed, `… + item.placeholder || '--'` in the copied page is found, and a copy fixed the same way is not. A line that occurs in more than 4 files is skipped as boilerplate. Files that already differed from HEAD at the first scan, and have not changed since, are not taken as edits.
- Git: the scripts never run the macOS `/usr/bin/git` shim; they run the git of the developer directory (Command Line Tools or Xcode) or one from PATH. The eval sandbox masks that binary too (its credential helpers link to it), so where no git runs, `cplib/gitread.py` reads `.git` directly: HEAD tree, history for co-change, the working-tree diff (difflib, so hunks can split differently from git's) and untracked files. Then `.gitignore` is not applied to the file list, and scan prints a note. A root with repositories one or two levels below it is a workspace of those repositories, even when the root itself lies inside another repository (the eval sandbox keeps one in its home directory).

## Not covered yet

Layout structures other than header-in-scroll, render-function and TSX templates, and Python or Node backends beyond the name and contract channels.
