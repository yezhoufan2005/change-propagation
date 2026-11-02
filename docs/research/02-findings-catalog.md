# 附录：调研发现目录

日期 2026-10-30。本文是调研报告 [01-research-report.md](01-research-report.md) 的附录，按维度逐条列出调研工作流（`docs/research/workflow/research.workflow.js`）语料中的全部 102 条发现。要点、启示和更正保留语料原文（多为英文）。被更正条目的"要点"里仍保留原来的错误，阅读时以"更正"一行为准。

## 发现数量

| 维度 | 已核实 | 已更正 | 自行核验 | 合计 |
|---|---:|---:|---:|---:|
| 1 经典 systematic edits（classic-systematic-edits） | 8 | 2 | 0 | 10 |
| 2 LLM 编辑传播（llm-edit-propagation） | 8 | 2 | 0 | 10 |
| 3 影响分析与 co-change（impact-and-cochange） | 6 | 4 | 0 | 10 |
| 4 克隆与去重合并（clones-and-consolidation） | 8 | 2 | 0 | 10 |
| 5 Agent 漏改原因与意图澄清（agent-failure-and-intent） | 9 | 1 | 0 | 10 |
| 6 工业界工具（industry-tooling） | 8 | 2 | 0 | 10 |
| 7 Claude Code 生态（claude-code-ecosystem） | 9 | 1 | 0 | 10 |
| 8 Skill 规范（skill-spec） | 9 | 1 | 0 | 10 |
| 9 补缺 1：自动触发与 hook（gap-1） | 0 | 0 | 7 | 7 |
| 10 补缺 2：代码中声明的耦合（gap-2） | 0 | 0 | 8 | 8 |
| 11 补缺 3：权限模式与确认关口（gap-3） | 0 | 0 | 7 | 7 |
| **合计** | **65** | **15** | **22** | **102** |

已更正的条目：1.1、1.10、2.8、2.10、3.3、3.7、3.8、3.10、4.3、4.9、5.4、6.3、6.5、7.5、8.4。

## 标注说明

- **核验**：已核实（verified）指核验 agent 打开了来源，来源支持该说法。已更正（corrected）指说法大体正确，但数字、年份、出处或机制有误，"更正"一行给出改法。自行核验（self-verified）是补缺调研（维度 9-11）的发现，只要求调研 agent 引用前自己打开来源，没有经过独立核验。核验判为 refuted 的发现（若有）在合并时已被剔除，语料没有保留，本目录不含。
- **场景**：S1 需求耦合：用户要求改业务逻辑 A，而逻辑 B 须与 A 保持一致（共享不变量或关联需求），agent 只改 prompt 字面点名的部分。S2 散落的同类对象：计划要求给所有 X 类组件加动画，但这类组件各自独立命名、散落在仓库各处，grep 或 agent 的默认做法只召回一部分。S3 重复实现合并：清理任务要求把同类对象提取成共享抽象、移除早期迭代留下的略有偏移的重复实现，agent 漏掉部分副本。通用（general）指不限于某个场景。条目内按 S1、S2、S3、通用排序。
- **类型**：论文 paper、基准 benchmark、工具 tool、文档 doc、实践 practice、讨论 discussion、本地核查 local-check（调研 agent 在本机做的测量或检查）。
- **年份**：不带 † 的取自语料。带 † 的是语料没有给出、本目录按来源推断的年份，依据是条目正文写明的论文年份或会议、arXiv 编号、文件名中的会议标注、URL 中的日期，或已知的出版信息；本地核查记为 2026。没有日期的在线文档、工具页、博客和 issue 不参与推断；所有来源都没有日期时记"—"，内容以 2026 年 10 月调研时的状态为准。
- **置信度**：调研 agent 的自评，高（high）或中（medium）。
- **来源**：语料每条最多保留 3 个来源。`/tmp/` 下的路径是调研时生成的临时文件，重启后可能消失；纯文字的来源是对本地操作的描述。
- **术语**：启示里的 Tier 1/2/3 对应用户决策 (c)：直接命中的位置直接改，推断出的耦合项附证据请用户确认后再改，低置信度项只列出不改。tier 0 指不调用模型的脚本检索（见 [04-scale-measurements.md](04-scale-measurements.md)）。(a)-(d) 是用户已定的四项决策：(a) 以 Claude Code plugin 打包；(b) 覆盖多个技术栈，逐栈推出；(c) 按上述三级处理范围；(d) 既靠 description 自动触发，也可用 /change-propagation 手动触发。
- **格式**：部分代码片段加了反引号，以免 Markdown 误解析，文字本身未改。"局限"一行是语料自带的局限说明，只有 9.3 有。"注"一行是本目录加的，指出某条与另一条经独立核验的更正相冲突，只有 11.5 有。

## 1 经典 systematic edits（classic-systematic-edits）

范围：示例驱动的批量编辑工具（Sydit/LASE、Refazer、Coccinelle、Getafix）、规则例外检测、关联编辑，以及补充补丁和克隆漂移研究。10 条：已核实 8，已更正 2。

### 1.1 Sydit/LASE: learn from 2+ examples

`lase` ｜ 类型：论文 ｜ 年份：2011, 2013† ｜ 场景：S2、S3 ｜ 置信度：高 ｜ 核验：**已更正**

- 要点：Sydit: 1 example, user-named targets, 82% of 56 edits. LASE abstracts only names differing across examples, adds dependence context, scans all methods: P99% R89% on 24 Eclipse fix sets, found 9 sites developers missed. Recall 51->100% from 2 to 5 examples; 1 concrete example R60%, all names abstract P75%.
- 对 skill 的启示：From 2+ confirmed sites build an ast-grep pattern: shared tokens literal, differing ones `$VAR`, one context line. Concrete hits tier 1; abstract-only tier 2, or 3 if from one example.
- 更正：The 51->100% recall gain is a single case (Table II, Index 4), not an average, and extra examples can cut precision (Index 12: 78->31%). Sydit: 82% applied an edit; only 70% (39/56) matched the developer exactly.
- 来源：<http://www.cs.utexas.edu/users/mckinley/papers/lase-icse-2013.pdf>；<http://www.cs.utexas.edu/users/mckinley/papers/sydit-pldi-2011.pdf>

### 1.2 Refazer: extra matches, real omissions

`refazer` ｜ 类型：论文 ｜ 年份：2016† ｜ 场景：S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：C# AST PBE; ranking prefers short context. 59 scenarios (median 5 sites): 83% learned from 2.8 examples. In 11, extra edits were developer omissions (Roslyn: 26 edited, 689 more, confirmed); in 10 (17%), wrong.
- 对 skill 的启示：Matches beyond the user's examples go to tier 2 with snippets; ask first if broadening multiplies hits (say >5x).
- 来源：<https://arxiv.org/abs/1608.09000>

### 1.3 Coccinelle/spdiff/SPINFER

`cocci` ｜ 类型：论文 ｜ 年份：2008, 2020† ｜ 场景：S2、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：SmPL (metavariables, '...' paths, isomorphisms) fully updated >93% of 5,800 files over 62 Linux API changes and fixed >150 files maintainers botched; misses were dataflow cases. spdiff, from 3 files, also fixed overlooked files elsewhere. SPINFER: P86% R69%, missing unseen variants.
- 对 skill 的启示：Keep per-language equivalence lists (`a?.b` vs `a && a.b`; `if let` vs `guard let`); inferred patterns must reproduce the user's edits; search sibling enum values and overloads.
- 来源：<https://homes.cs.aau.dk/~rrh/pubs/eurosys08.pdf>；<https://who.paris.inria.fr/Julia.Lawall/andersen_ase08.pdf>；<https://www.usenix.org/conference/atc20/presentation/serrano>

### 1.4 Getafix: ranked patterns

`getafix` ｜ 类型：论文 ｜ 年份：2019† ｜ 场景：S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Anti-unification builds general-to-specific patterns ranked by prevalence, location, specificity; the analyzer re-checks fixes. Top-1 exact 12-91% by category, top-5 41% of 1,268; 42% of ~250 deployed suggestions accepted.
- 对 skill 的启示：Cluster drifted variants into few patterns; match each site to the most specific; validate with the change's checker (tsc, kotlinc, go vet, mypy, tests).
- 来源：<https://arxiv.org/abs/1902.06111>

### 1.5 LSdiff/Critics: exceptions, residue

`lsdiff-critics` ｜ 类型：论文 ｜ 年份：2009, 2015† ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：LSdiff rules ('all X in subtypes of Y changed, except W'; >=3 matches, >=0.75 accuracy) covered 75% of structural changes; exceptions flag misses. Critics flags code matching the old template, not the new: 11/12 users found all missing updates vs 4/12 with diff; users stopped after 2-3 refinements; keyword search was unstable.
- 对 skill 的启示：Define categories structurally (implements, extends, decorator); report 'N of M updated' and exceptions as tier 2; old-pattern residue must be zero or explained; do >=3 broadening rounds.
- 来源：<https://web.cs.ucla.edu/~miryung/Publications/icse09-lsdiff.pdf>；<http://web.cs.ucla.edu/~miryung/Publications/ICSE2015-Critics.pdf>

### 1.6 LAPIS/Codelink/CloneTracker

`lapis-links` ｜ 类型：论文 ｜ 年份：2001–2007† ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：LAPIS inferred 84% of selections from 1 example, but 8/24 sessions kept uncorrected errors (5/24 manual) as users missed near-miss selections; break-even 3.6-8.4 records. Codelink: linking took 22 s vs 13 min to abstract. CloneTracker anchors (file, class, signature, block) tracked 96% of regions.
- 对 skill 的启示：Show tier-2 outliers first, grouped by shape; rejections become negatives; skip inference under ~4 sites. Keep coupling groups in a repo file keyed by symbol and anchor, for a later hook.
- 来源：<https://www.cs.cmu.edu/~rcm/papers/usenix01/usenix01.html>；<http://harmonia.cs.berkeley.edu/papers/toomim-linked-editing.pdf>；<http://cs.mcgill.ca/~martin/papers/icse2007.pdf>

### 1.7 Supplementary patches

`supp` ｜ 类型：论文 ｜ 年份：2016† ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：23-34% of fixed bugs (Eclipse, Mozilla) needed supplementary patches. Of 200 incomplete ones, 36% missed a port to another component or branch, 20% missed references to or from the change, 15% mishandled conditions; others missed config, sibling subclasses, visitor links. Only 7-17% resembled the first patch.
- 对 skill 的启示：Per change, check: platform/branch twins, references, implementers, sibling subclasses, DI/reflection/string keys, config, tests, else/null branches.
- 来源：<http://web.cs.ucla.edu/~miryung/Publications/emse2016-supplementary.pdf>

### 1.8 Where omitted sites are

`reach` ｜ 类型：论文 ｜ 年份：2012–2017† ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Only 10-20% of supplementary locations are one hop (call, clone, name, co-change) from the first patch; single signals <=9% precision, combined F<=10%. But 42-48% of supplementary files changed within 25 lines of it, and 70-94% of repeated-fix groups stayed in one file.
- 对 skill 的启示：Sweep the same file, then package; a one-hop LSP neighbor is tier 2 only if a second signal agrees. For S1, ask where else the rule lives and save it.
- 来源：<http://web.cs.ucla.edu/~miryung/Publications/ase2014-omissionerror.pdf>；<https://web.cs.ucla.edu/~miryung/Publications/msr2012-supplementarypatch.pdf>；<https://people.cs.vt.edu/nm8247/publications/ruru-icsme-2017-camera-ready.pdf>

### 1.9 Drifted clones

`clones` ｜ 类型：论文 ｜ 年份：2009, 2015† ｜ 场景：S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：52% of 1,427 clone groups were inconsistent, 28% of those unintentionally, yielding 107 confirmed faults. 3.9% of pairs among 89 independent implementations shared a clone. RASE removed clones in 54-67% of edit-scoped cases (30-34% method-scoped); developers refactored 4 of 56.
- 对 skill 的启示：Find copies by syntax and by shared callees, constants, tests; the user marks each tabled difference intended or bug; extract only parameterizable regions, else propagate and register.
- 来源：<https://arxiv.org/abs/1701.05472>；<https://teamscale.com/hubfs/26978363/Publications/2009-clone-detection-beyond-copy-paste.pdf>；<https://web.cs.ucla.edu/~miryung/Publications/ICSE2015-RASE.pdf>

### 1.10 Nguyen: recurring changes are small

`nguyen` ｜ 类型：论文 ｜ 年份：2013† ｜ 场景：S2 ｜ 置信度：高 ｜ 核验：**已更正**

- 要点：In 2,841 Java projects, changes of AST height 1-2 repeat 60-100%, falling exponentially, rare above 6; calls repeat most. FixWizard: 17-45% of fixes recur (via Park'16).
- 对 skill 的启示：Build patterns from the smallest changed subtree (call, argument, guard) plus one parent; larger edits recur only as variants.
- 更正：Calls are the most common change type and the largest count of repeats, but their repeat rate (40%) is mid-range. Arrays (56-82%), postfix/prefix/infix (53-92%) and super-constructor calls (72%) repeat more; if (10%) and loops (<=6%) repeat least.
- 来源：<https://lab-design.github.io/papers/ASE-13/ase13.pdf>

## 2 LLM 编辑传播（llm-edit-propagation）

范围：LLM 时代的改动传播与定位：CodePlan 影响规则、LSP 路由、以首个编辑为查询、相似兄弟函数打分、提交历史、探索策略，以及多文件、多 hunk 编辑的失败分析。10 条：已核实 8，已更正 2。

### 2.1 CodePlan impact rules

`codeplan` ｜ 类型：论文 ｜ 年份：2023† ｜ 场景：S1、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Each edit enqueues obligations by change type: signature->callers+overrides; field->users+ctors+sub/superclasses; body->callers only if caller-visible state changed. Build errors seed the next round. 5/6 repos pass vs 0/6 for build-repair baselines; behavior-only changes raise no error and are missed.
- 对 skill 的启示：Ship a per-stack table change type->relations; run a worklist to fixpoint, typecheck as oracle; flag body/semantic changes as Tier-2 S1 candidates.
- 来源：<https://arxiv.org/html/2309.12499>

### 2.2 LSP for syntactic edits (TRACE)

`trace-lsp` ｜ 类型：论文 ｜ 年份：2026† ｜ 场景：S1、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：TRACE routes rename, def-use, clone and diagnostic edits to IDE tools, the rest to a neural locator: P/R 69.6/67.9 vs CoEdPilot 48.4/61.8; blind invocation of all tools: P 22%. Claude Code's LSP needs a per-language plugin, is off in cloud sessions and lacks an official Dart plugin.
- 对 skill 的启示：Classify each seed edit; take LSP references/call hierarchy as Tier-1 hits for rename/signature/def-use; fall back to tree-sitter scripts; ship .lsp.json for Dart.
- 来源：<https://arxiv.org/html/2604.12220v1>；<https://code.claude.com/docs/en/plugins/code-intelligence>

### 2.3 First edit as the query

`edit-as-query` ｜ 类型：论文 ｜ 年份：2023, 2024† ｜ 场景：S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Related prior edits lift Codex exact match 37.1->67.9 (GrACE). From one edit, CoEdPilot finds co-edited files at P 79.5/R 72.9; relevant vs random prior edits: EMR 41.8 vs 18.9.
- 对 skill 的启示：From the exemplar edit, extract the before-pattern and changed identifiers, search for sites still matching, feed later edits only relevant prior diffs, repeat until no new site.
- 来源：<https://arxiv.org/html/2305.14129v3>；<https://arxiv.org/html/2408.01733v1>

### 2.4 Sibling scoring beats clones

`siblings` ｜ 类型：论文 ｜ 年份：2019, 2026† ｜ 场景：S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Hercules (AST similarity>=0.8, def-use context, co-change history) localizes 84% of 154 bugs vs 26% for Deckard clones. SiblingRepair (TF-IDF, embeddings, LLM pick) covers all sibling methods for 70.1%; 12/48 misses were at candidate generation.
- 对 skill 的启示：Script find_similar: normalized-token and AST n-gram scores per function/component; high score + shared context -> Tier 2 with evidence, low -> Tier 3. Never rely on name grep.
- 来源：<https://arxiv.org/html/1906.08903v1>；<https://arxiv.org/html/2605.06209v1>

### 2.5 Commit history as evidence

`history` ｜ 类型：论文 ｜ 年份：2025† ｜ 场景：S1、S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：RepoMem: BM25 over past commits lifts LocAgent file Acc@5 71.6->76.5 on SWE-bench Verified but loses 13.1 pp on repos under 10K commits.
- 对 skill 的启示：Script cochange: co-change support and git log -S/-G for seed files; cite commits as Tier-2 evidence; down-weight sparse or squashed history.
- 来源：<https://arxiv.org/html/2510.01003>

### 2.6 1-hop expansion, module partitions

`exploration` ｜ 类型：论文 ｜ 年份：2024–2026† ｜ 场景：S1、S2、S3、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：CoSIL Top-1 falls 0.433->0.320 without iterative call-graph search. SWE-Adept (dependency DFS, previews first): Func Acc@5 87.8/63.3 (Lite/Pro) vs Claude Code 85.4/59.5. RepoGraph helps at 1 hop (+2.3 pp), not as a 2-hop dump. On SWE-bench Pro ansible, per-module Haiku agents find all gold files in 6.4/19 cases vs 3.4 for one sequential Sonnet agent.
- 对 skill 的启示：Depth: an explorer subagent expands one hop at a time with evidence and stops when two searches add nothing. Breadth (S2/S3): parallel read-only subagents per module. Never paste multi-hop graphs.
- 来源：<https://arxiv.org/html/2503.22424v2>；<https://arxiv.org/html/2603.01327v3>；<https://arxiv.org/html/2410.14684v2>

### 2.7 Omission dominates wide edits

`omission` ｜ 类型：基准 ｜ 年份：2025, 2026† ｜ 场景：S2、S3、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：ProMax (170 tasks, 11.4 files avg): failed runs edit fewer files than gold, skipping peripheral call sites, docs, config, fixtures. RefactorBench: no baseline solved a task over 6 files; an edit-state summary gave +43.9% relative. RefactorPlatform: 50.9% of failures miss 1-2 trailing files or break imports.
- 对 skill 的启示：Keep a script-managed site ledger (tier, status, evidence); block completion while Tier-1 items are pending or the peripheral sweep (docs, config, tests, fixtures, mocks, i18n) is unchecked.
- 来源：<https://arxiv.org/html/2608.09802v1>；<https://arxiv.org/html/2503.07832v1>；<https://arxiv.org/html/2609.04898v1>

### 2.8 Claude Code on coordinated edits

`multihunk` ｜ 类型：论文 ｜ 年份：2025, 2026† ｜ 场景：S2、通用 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：PolyHunk (404 bugs): Claude Code repairs 92.8% but matches gold files in 66.1%; on a 16-file bug it edited 3; failing runs search more, edit less. RepoRescue: Claude Code passes at most 2 of 14 coordinated whole-codebase fixes (Codex 14). Compile/test feedback lifts o4-mini 26.9->35.8% (Hunk4J); Multi2Fixer hunk ordering 52->89 fixes, yet 11/16 bugs with 10+ hunks loop until budget.
- 对 skill 的启示：Close on the ledger, not green tests; edit definitions before users, typecheck/test each batch; cap search rounds and re-edits per site.
- 更正：(1) PolyHunk 的 66.1% 指 agent 修改的文件集合覆盖开发者补丁的全部文件，允许多改，不是"与 gold 文件一致"。(2) Hunk4J 的 35.75% 配置同时加了方法级上下文、相似历史补丁检索（token+text-embed）和编译/测试反馈，论文没有单独的反馈消融，所以 +8.9 pp 不能只算在反馈头上，而且成本约为基线的 4.4 倍。(3) Multi2Fixer 的 52→89 对比的是"一次生成整体补丁"和"调度加逐 hunk 迭代修复"的完整框架。单看 hunk 排序，相对 Sequential（81）和 Random（79）调度只多出 8 和 10 个修复。11/16 描述的是反复改已修复 hunk、"may exhaust the 20-step budget"，论文没有给出每个 bug 的预算用量。
- 来源：<https://arxiv.org/html/2511.11012>；<https://arxiv.org/abs/2607.01213>；<https://arxiv.org/html/2506.04418v1>

### 2.9 Union then select

`union-select` ｜ 类型：基准 ｜ 年份：2026† ｜ 场景：S1、通用 ｜ 置信度：中 ｜ 核验：已核实

- 要点：RevPropBench (propagation in chat-built JSON): misses are the main error; artifact+conversation beats either alone; intersecting samples loses 13-21 pp, LLM selection gains 3.3-12.5 pp, saturating at 4-5 calls.
- 对 skill 的启示：For S1, read requirement history (prompt, PRD, tickets) with code; union 2-3 independent enumerations, verify each; demote weak candidates to Tier 3.
- 来源：<https://arxiv.org/html/2609.03254>

### 2.10 Next-edit models stay local

`next-edit` ｜ 类型：工具 ｜ 年份：2025, 2026† ｜ 场景：通用 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Copilot's 2026 inline model emits 1.3-1.4 patches per response. Claude 4 Opus predicts next-edit position 80.5%, exact content 45.7%. 51% of Claude Code's follow-up suggestions break developer flow; an order filter raises precision 40.5->50.5, lowers recall 39.5->36.2.
- 对 skill 的启示：Enumerate sites separately from editing them; present Tier-2 items in dependency order; demote filtered items to Tier 3.
- 更正：(1) 1.3–1.4 patches/response 是 v2 SFT 中间模型的数字。博客没有给出 RL 训练后或最终上线模型的平均 patch 数，不能说"2026 上线模型每次输出 1.3–1.4 个 patch"。(2) EditFlow 的 51.23% 是 Break 类，定义为建议内容不在真实 commit 中（"hallucinates content not present in the ground-truth commit"）。如果把 Jump 和 Revert 也算作打断开发流，Claude Code 是 65.84%；摘要里的 68.81% 是 Cursor 与 Claude Code 的平均。precision/recall 数字无误。
- 来源：<https://code.visualstudio.com/blogs/2026/09/16/building-the-github-copilot-inline-suggestions-model-part-one/>；<https://arxiv.org/html/2508.10074>；<https://arxiv.org/html/2602.21697v1>

## 3 影响分析与 co-change（impact-and-cochange）

范围：co-change 挖掘（ROSE、TARMAQ）的阈值与默认值、本机 git 实测、静态影响分析的深度、特征定位、需求追踪和跨制品链接。10 条：已核实 6，已更正 4。

### 3.1 ROSE: loose vs strict thresholds

`rose` ｜ 类型：论文 ｜ 年份：2005 ｜ 场景：S1、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：8 repos. Support 1, conf 0.1: answers 66%, precision 29%, recall 33%. Support 3, conf 0.9: warns on 3% of one-missing-item cases, recall ~75%, precision >66%; ~2% false alarms.
- 对 skill 的启示：Loose: listed tier, top 5 with evidence. Strict: automatic advisory check on the agent's diff.
- 来源：<https://research.cs.queensu.ca/home/ahmed/home/teaching/CISC880/F11/papers/MSRGuideChange_TSE2005.pdf>

### 3.2 Co-change finds cross-language and cloned partners

`ying` ｜ 类型：论文 ｜ 年份：2004 ｜ 场景：S1、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Mozilla precision ~0.5, recall 0.2-0.3; Eclipse ~0.3, 0.1-0.2. Useful Mozilla hits: XUL/JS/XML-schema pairs, parallel Chimera/Camino code, gtk/xlib clones; Eclipse hits were mostly obvious.
- 对 skill 的启示：Show partners not linked by import, reference or test name first; parallel implementations are S3 candidates.
- 来源：<https://cs.ubc.ca/~rng/psdepository/tse2004.pdf>

### 3.3 TARMAQ and mining defaults

`tarmaq-defaults` ｜ 类型：论文 ｜ 年份：2016 ｜ 场景：S1、S2、通用 ｜ 置信度：高 ｜ 核验：**已更正**

- 要点：ROSE answers ~25% of multi-file queries, TARMAQ (largest overlapping subset) all. 39 measures tie (confidence MAP 0.444, best 0.446); learning from <=8-file commits is best (0.463). MAP 0.285/0.312/0.322 at 5k/15k/35k commits; 100-commit-old rules 0.376 to 0.329.
- 对 skill 的启示：Query with the whole planned file list; learn from <=8-file commits, last 15-25k, fresh each run.
- 更正：39 measures do not all tie: 11 of the 39 are statistically tied in the top group (best 0.446, confidence 0.444). The best transaction filter is 6-8 files (6 = 0.464, 8 = 0.463 in the same top group), not 8 alone.
- 来源：<http://www.cs.loyola.edu/~binkley/papers/saner16-tarmaq.pdf>；<http://www.cs.loyola.edu/~binkley/papers/ase16-mining-guidelines.pdf>；<http://www.cs.loyola.edu/~binkley/papers/scam16-history-exploration.pdf>

### 3.4 Local check: stdlib TARMAQ is fast, tiers separate

`local-cochange` ｜ 类型：本地核查 ｜ 年份：2026 ｜ 场景：S1、通用 ｜ 置信度：中 ｜ 核验：已核实

- 要点：flask/vue/django (3.8k/7.2k/34k commits): load 0.1-1.5 s, query <1 ms. Leave-one-out, 300 commits: hit@10 0.65/0.78/0.49; tier hit rates: s>=3,c>=0.5 52-72%; s>=2,c>=0.2 13-19%; rest ~5%. Strict warnings held the file 80-90%, false alarms 2-6%. No size filter (flask): top tier 16%, warning precision 73% to 9%.
- 对 skill 的启示：Ship scripts/cochange.py with these tiers and the size filter; reuse leave-one-out for calibration and evals.
- 来源：`/tmp/cp-scripts/cochange.py`

### 3.5 Local check: partial clones work, shallow clones do not

`git-clone-modes` ｜ 类型：本地核查 ｜ 年份：2026 ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Git 2.54, blobless flask clone: `--name-only --no-renames` read all history in 0.09 s without blobs. Rename detection fetched blobs (21 s/1,000 commits); `--numstat` (code-maat) 262 s/200. actions/checkout defaults to depth 1; `fetch --unshallow --filter=blob:none` took 6.4 s.
- 对 skill 的启示：Use `--no-merges --no-renames --name-only`. If shallow, ask before unshallowing or fall back and say so.
- 来源：`/tmp/cp-scripts/cochange.py`；<https://github.com/actions/checkout>；<https://github.com/adamtornhill/code-maat/blob/master/README.md>

### 3.6 Real forgotten edits: fuse history and commit text

`gitcf` ｜ 类型：论文 ｜ 年份：2026 ｜ 场景：S1、S2 ｜ 置信度：中 ｜ 核验：已核实

- 要点：Preprint, 543 real incomplete changes in 17 OSS projects. Hit@10: TARMAQ 0.147, TAR 0.322, GitCF (co-change + TF-IDF on commit messages and diff identifiers) 0.403-0.416; parameters picked on the test data.
- 对 skill 的启示：Expect far lower recall than leave-one-out; fuse co-change with task-to-commit-text similarity by RRF (K=60).
- 来源：<https://arxiv.org/html/2609.37045v1>

### 3.7 Depth-1 references beat transitive closure

`static-impact` ｜ 类型：论文 ｜ 年份：2001-2017 ｜ 场景：S1、通用 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Hattori (3 Java systems): depth 1 P 84%/R 81%, depth 2 76%/94%, unbounded 73%/100%. Musco (10 Java projects): the most basic call graph has the best trade-off. Rajlich: propagate to referencing classes, stop where nothing changes.
- 对 skill 的启示：Expand by direct references, recurse only from changed nodes, log unchanged ones as the frontier; no dynamic analysis.
- 更正：Depth 1 does not beat transitive closure. It gives up 19 points of recall (81% vs 100%) for about 11 points of precision, and Hattori's best accuracy is at unbounded depth. Musco cannot support a depth limit, because it uses transitive closure throughout. The report summary's 'transitive closure costs recall' is backwards: closure costs precision. The supported stopping rule is Rajlich's (recurse only from nodes that actually changed), which is itself a closure gated on change.
- 来源：<http://www.dsc.ufcg.edu.br/~jarthur/upload/publications/On_the_precision_and_accuracy_of_impact_analysis_techniques.pdf>；<https://arxiv.org/abs/1812.06286>；<http://people.compute.dtu.dk/~huba/xp2001-web/papers/Chapter3-Rajlich.pdf>

### 3.8 Locate lexically, then expand

`locate-expand` ｜ 类型：论文 ｜ 年份：2013 ｜ 场景：S1、S2 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Dit survey (89 articles): feature location finds the start; 'the full extent of the change is then handled by impact analysis'. Kagdi: textual plus evolutionary coupling raised recall up to 20% over textual and 45% over history alone.
- 对 skill 的启示：S2: widen the vocabulary, grep, expand hits by references, naming siblings and co-change; rank multi-signal items higher.
- 更正：The cited EMSE 2013 paper reports F-measure gains of up to 14 points over textual coupling and 21 points over co-change, not recall gains of 20% and 45%. The 20%/45% recall figures probably come from the WCRE 2010 version (Kagdi, Gethers, Poshyvanyk, Collard, 'Blending Conceptual and Evolutionary Couplings to Support Change Impact Analysis in Source Code', <https://doi.org/10.1109/WCRE.2010.21>). That is unconfirmed.
- 来源：<https://www.cs.wm.edu/~denys/pubs/JSME-FL-SurveyCRCV1.pdf>；<https://link.springer.com/article/10.1007/s10664-012-9233-9>

### 3.9 LLM trace filtering cuts recall

`lissa` ｜ 类型：论文 ｜ 年份：2025 ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：LiSSA (ICSE 2025): embedding top-20 then GPT-4o; requirement-to-code F1 0.322 vs LSI 0.285. Retrieval alone had the best recall (eTour 0.815 at precision 0.216); the LLM raised precision, lowered recall.
- 对 skill 的启示：Keep LLM-rejected candidates in the listed tier with a reason; retrieve with several phrasings.
- 来源：<https://publikationen.bibliothek.kit.edu/1000179816/164563088>

### 3.10 Schema, test and API links are name-based

`cross-artifact` ｜ 类型：论文 ｜ 年份：2013-2020 ｜ 场景：S1、S2 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Qiu (10 DB apps, 146 schema commits): ~72% had useful same-commit code co-change, ~27% none. TCTracer: test naming convention P 100%, R 80% for classes, 11% for methods. Wittern: static JS request check against API specs, 96% precise.
- 对 skill 的启示：Per-stack ripgrep extractors (routes, operationIds, i18n/config keys, tables, CSS, test names) give direct evidence; co-change fills gaps.
- 更正：Qiu: about 50% of the sampled schema revisions (S3) had same-commit code that contained the real change, and about 22% needed no code change. The remaining ~27% are not 'none': their co-change evidence was missing or misleading, because the code change was in another commit or the co-committed code was unrelated.
- 来源：<https://people.inf.ethz.ch/suz/publications/fse13-db-study.pdf>；<https://discovery.ucl.ac.uk/id/eprint/10091100/1/icse20.pdf>；<https://arxiv.org/html/1702.03906v2>

## 4 克隆与去重合并（clones-and-consolidation）

范围：克隆检测的召回分层、不一致克隆编辑与缺陷、jscpd/PMD CPD/ICCheck 等工具、LLM 与 embedding 判定、本机归一化实测，以及哪些克隆该合并、合并后如何核对。10 条：已核实 8，已更正 2。

### 4.1 BigCloneBench recall sets the tiers

`bcb-recall-tiers` ｜ 类型：基准 ｜ 年份：2015† ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Recall for T1/T2/VST3/ST3/MT3/WT3-T4: NiCad 100/100/100/95/1/0, SourcererCC 100/98/93/61/5/0. MT3 (0.5-0.7 similarity) is 12% or less and WT3/T4 1% or less for all five tools.
- 对 skill 的启示：Tier 1: Type-1 and rename-only Type-2. Tier 2: Type-2 with changed literals or callees, and Type-3 at 0.7 or more. Tier 3: 0.5-0.7 and any Type-4. S2 needs non-clone signals.
- 来源：<https://arxiv.org/html/1512.06448v1>

### 4.2 Inconsistent clone edits cause faults

`inconsistent-edits-faults` ｜ 类型：论文 ｜ 年份：2009, 2013† ｜ 场景：S1、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Juergens 2009: of 1,427 clone groups, 724 were inconsistent, 203 unintentionally, and 107 contained faults. Barbour 2013: late-propagation genealogies are 8-21% of changed genealogies and more fault-prone.
- 对 skill 的启示：After editing a function, list its clone siblings with diffs, git co-changed ones first. Ask per group if the difference is intentional and if this copy should follow.
- 来源：<https://arxiv.org/html/1701.05472v1>；<http://swat.polymtl.ca/~foutsekh/docs/Barbour-JSME.pdf>

### 4.3 jscpd v5 as primary detector

`jscpd-v5` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Rust engine on npm and PyPI; 5.4.2 is from 2026-10-20. Defaults: exact, 50 tokens, 5 lines. Opt-in: `--ignore-identifiers`, `--similarity` (AST, 0.8), `--semantic` (548 MB model), ai reporter, MCP check_duplication. Dart: token modes only. No published accuracy.
- 对 skill 的启示：Pin the version; use `--reporters json,ai` and `--ignore` for vendored and generated paths; run exact, renamed, then similarity; semantic only with consent. Untested here (npm install denied).
- 更正：The default `--mode` is 'mild'; 'exact' is the default clone kind, not the mode. 'No published accuracy' is too strong: the docs say reviewers judged 93% of CodeRankEmbed semantic pairs to be duplicates (83% for jina), with thresholds calibrated on Rosetta Code. Only the token and AST passes have no figures. Pinning matters: in 5.4.2 a bare `--ignore-identifiers` means consistent renaming (`=blind` gives the old mode), and 5.4.1 changed `--similarity` scores. `--semantic-url` can call an embeddings API instead of the local model.
- 来源：<https://github.com/kucherenko/jscpd/blob/master/README.md>；<https://github.com/kucherenko/jscpd/blob/master/FORMATS.md>

### 4.4 PMD CPD covers every target stack

`pmd-cpd` ｜ 类型：工具 ｜ 年份：2025† ｜ 场景：S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Supports JS/TS, Java, Kotlin, Go, Python, Swift and Dart; needs a JVM. Identifier and literal ignoring is Java/C++ only. Exit code 4 means duplicates found. A 2025 benchmark measured 31% Type-3 recall.
- 对 skill 的启示：Use for Dart and JVM projects; treat exit 4 as results. Outside Java it finds only token-identical copies, so an empty report does not rule out near-duplicates.
- 来源：<https://pmd.github.io/pmd/pmd_userdocs_cpd.html>；<https://arxiv.org/pdf/2509.25754v1>

### 4.5 LLMs and embeddings as verifiers

`llm-embedding-judge` ｜ 类型：论文 ｜ 年份：2024, 2025† ｜ 场景：S2、S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：GPT-4 BCB recall: MT3 0.87, WT3/T4 0.23. Cross-language CodeNet F1: GPT-3.5 0.34-0.79 on clone pairs, embedding+SVM 0.99 average, raw cosine 0.74-0.78. 93.3% of sampled BCB WT3/T4 pairs are not real clones.
- 对 skill 的启示：Judge only short candidate lists: describe A, describe B, list behavior differences, then decide. Model or cosine matches stay in Tier 2 or 3. Calibrate on bundled fixtures, not BCB.
- 来源：<https://arxiv.org/html/2407.02402v1>；<https://arxiv.org/html/2408.04430v3>；<https://arxiv.org/html/2505.04311v1>

### 4.6 Local: normalization and noise floor

`local-normalization` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：TS fixture, blind tokens plus difflib ratio: Type-1 1.00; Type-2 1.00 though tax 0.08 became 0.2; Type-3 0.89 (k=5 Jaccard 0.55); Type-4 0.47-0.50; unrelated 0.28-0.48. 3,000 random stdlib pairs: p99 0.58, p99.9 0.64, 2 at 0.7 or more.
- 对 skill 的启示：Fallback: rank by sequence ratio, 0.8 to confirm, 0.7 to list, Jaccard only as prefilter. Show raw token diffs so changed constants stay visible. Never claim Type-4 from token scores.
- 来源：`/tmp/cp_scripts/neardup2.py`；`/tmp/cp_scripts/verify_after.py`

### 4.7 Local: seed queries scale, all-pairs not

`local-seed-mode` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、S2、S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：Python 3.9 stdlib: 9,486 functions load in 3.3 s, a 1-vs-N query takes 7.2 s, indexed all-pairs 140-160 s. Of 1,355 groups at 0.8, 75% touched site-packages or `_vendor`; 84% of the rest were same-file.
- 对 skill 的启示：Seed from edited or named code; leave whole-repo scans to jscpd. Exclude dependency, vendored and generated paths, and keep only groups touching the task scope.
- 来源：`/tmp/cp_scripts/neardup2.py`

### 4.8 ICCheck flags missed sibling edits

`iccheck` ｜ 类型：工具 ｜ 年份：2025† ｜ 场景：S1、S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：`iccheck --from HEAD --to WORKTREE` lists unchanged code similar to changed hunks (per-line char-bigram Dice 0.7). Median 0.27 s on 9,368 commits; flagged 28.7% of commits; CBCD precision 0.70, recall 0.23. Go binary.
- 对 skill 的启示：Post-edit check for S1/S3: run it if allowed, else replay pre-edit bodies of changed functions as 1-vs-N queries. Hits go to Tier 2; an empty result proves nothing.
- 来源：<https://arxiv.org/html/2504.04537v1>；<https://github.com/salab/iccheck>

### 4.9 Many clone groups should stay

`merge-or-leave` ｜ 类型：论文 ｜ 年份：2005, 2008† ｜ 场景：S3 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Kim 2005: standard refactorings could not easily remove 49-64% of clone genealogies. Kapser 2008: replicate-and-specialize clones were rated good 76% of the time; parameterized-code clones harmful 71-76% (Gnumeric).
- 对 skill 的启示：Classify each difference: values become parameters, callees or types become generics or closures, control-flow or side-effect drift blocks merging. Platform forks go to Tier 3 with a reason.
- 更正：The 76% good figure is from Apache httpd only. In Gnumeric's small-clone sample, nearly 44% of replicate-and-specialize clones were rated harmful. The share rated good ranged 33-71% across the four samples, so this prior depends on the system.
- 来源：<https://plg.uwaterloo.ca/~migod/846/papers/fse06-kim.pdf>；<http://plg.uwaterloo.ca/~migod/papers/2008/emse08-ClonePatterns.pdf>

### 4.10 Agents rarely dedupe; verify removals

`dedupe-verification` ｜ 类型：本地核查 ｜ 年份：2025, 2026† ｜ 场景：S1、S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：Duplication motivates 1.1% of agent refactorings vs 13.7% for humans. CodeTaste: open discovery under 8%, propose-then-implement 15.1%. Local: after a simulated merge the untouched drifted copy scored 0.87 vs the shared code; a canonical-field grep missed it.
- 对 skill 的启示：Start S3 with a tool pass and a user-approved plan. Save member bodies first; afterwards re-query with them and the shared code, require zero reductive matches, run tests.
- 来源：<https://www.arxiv.org/pdf/2511.04824>；<http://arxiv.org/pdf/2603.04177v2.pdf>；`/tmp/cp_scripts/verify_after.py`

## 5 Agent 漏改原因与意图澄清（agent-failure-and-intent）

范围：Agent 漏改的成因（状态丢失、改动分散、词汇不匹配、经共享状态的耦合、需求缺口）和对策（台账、多通道检索、范围控制、澄清提问、删除核对、测试之外的核对）。10 条：已核实 9，已更正 1。

### 5.1 State loss and early 'done' drive misses

`ledger-gated-done` ｜ 类型：基准 ｜ 年份：2025† ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：RefactorBench: no baseline solved a >6-file task (humans 87%); in ~44% of change checks the target file was never edited; state tracking gave +43.9% relative. Anthropic: agents 'declare the job done' on seeing progress.
- 对 skill 的启示：Keep a JSON site ledger (file:line, symbol, tier, status, evidence); agents only flip status; a Stop check blocks finishing while confirmed sites are pending.
- 来源：<https://arxiv.org/abs/2503.07832v1>；<https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>

### 5.2 Recall drops with dispersion and granularity

`dispersion` ｜ 类型：论文 ｜ 年份：2025† ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：44.6% of Defects4J bugs are multi-hunk; o4-mini fixes 49% of the tightest (Nucleus) vs 22% of Sprawl bugs. SWE-bench runs match the file 59-97% of the time but the function only 14-34%.
- 对 skill 的启示：Track sites per symbol/hunk, re-scan edited files for siblings, and enumerate per module when sites span modules.
- 来源：<https://arxiv.org/html/2506.04418>；<https://arxiv.org/html/2511.00197v1>

### 5.3 Vocabulary mismatch defeats one-term grep

`vocabulary` ｜ 类型：论文 ｜ 年份：1987, 2021† ｜ 场景：S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Furnas: two people chose the same term with p<0.20; one word gave 80-90% access failure; unlimited aliasing gave several-fold gains. Developers chose the same name with median p=6.9% (n=334).
- 对 skill 的启示：Define the category by properties: from 2-3 confirmed exemplars harvest identifiers, base types, props, imports, styles, decorators; expand aliases; log the query per hit; stop when queries add nothing.
- 来源：<https://dl.acm.org/doi/10.1145/32206.32212>；<https://arxiv.org/html/2103.07487v1>

### 5.4 Structural, semantic, per-module search add recall

`multichannel` ｜ 类型：论文 ｜ 年份：2026† ｜ 场景：S1、S2 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Call/inheritance anchors: +2.2pp Func@5, half the variance. Cursor (vendor): semantic search +12.5% accuracy, best with grep. Per-subsystem explorers found all gold files 6.4/19 vs 3.3/19; docs were missed 73%.
- 对 skill 的启示：Union alias grep, LSP findReferences/ast-grep and semantic search; fan out read-only subagents per module; always scan docs, config, tests, mocks.
- 更正：Keep +2.2pp Func@5, but attribute the halved variance (and Pass@1 +3.4pp) to structural tags on medium-scale repos. Restate the explorer result: with the same small model (Haiku), per-subsystem fan-out raised all-gold instances from 3.3 to 6.4 of 19, while one stronger single agent (Codex 5.5 High) reached 9.2 of 19. Fan-out helps a weaker model but does not beat a strong single agent. Label Cursor's 12.5% as offline Q&A accuracy; its online coding effect was +0.3% code retention.
- 来源：<https://arxiv.org/abs/2606.26979>；<https://prod.cursor.com/blog/semsearch>；<https://arxiv.org/html/2606.11976>

### 5.5 S1 coupling runs through shared state

`shared-state` ｜ 类型：讨论 ｜ 年份：2021† ｜ 场景：S1 ｜ 置信度：中 ｜ 核验：已核实

- 要点：Claude Code moved a nav item in navigation.ts but left LayoutsNav.tsx, then patched 4 times and renamed it unasked. Feature-interaction work finds coupling where one feature writes state another reads.
- 对 skill 的启示：Seed S1 candidates from shared artifacts (field, store key, API field, event, config/env key, flag) and mirrored logic (client/server validation, docs); tier them inferred, citing the artifact.
- 来源：<https://github.com/anthropics/claude-code/issues/49216>；<https://arxiv.org/html/2104.07844v1>

### 5.6 Requirement gaps outweigh search gaps

`intent-gap` ｜ 类型：基准 ｜ 年份：2026† ｜ 场景：S1、S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：SWE-RPG: 4.53 clarification points per task; requirement failures lead (24.5-46.0% of runs); Claude Code plans cover constraints 41.6%. DevIntent: Sonnet 4.6 intent-violation rate 54.5%, per problem near 0 or 1.
- 对 skill 的启示：Restate the request as invariants ('A and B must agree on Z') before searching, derive candidates per invariant, and have the user confirm invariants, not only sites.
- 来源：<https://arxiv.org/html/2608.09072v1>；<https://arxiv.org/html/2608.07614>

### 5.7 Models under- and over-scope; action bias

`scope-control` ｜ 类型：文档 ｜ 年份：2026† ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Opus 4.8 'does not silently generalize an instruction from one item to another'. FixedBench: agents edited code in 35-65% of tasks needing none; inaction must be framed as success. A preservation instruction cut excess edit distance 0.195->0.131, Pass@1 +2.3pp.
- 对 skill 的启示：Say 'every instance of the category, not just the named one'; edit only confirmed tiers; add a preservation rule (no renames or refactors); count 'listed, not edited' as success.
- 来源：<https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8>；<https://arxiv.org/abs/2605.07769>；<https://arxiv.org/abs/2609.04061>

### 5.8 Ask few answerable questions after exploring

`clarify-policy` ｜ 类型：论文 ｜ 年份：2025, 2026† ｜ 场景：通用 ｜ 置信度：中 ｜ 核验：已核实

- 要点：Models rarely ask unprompted; with answers Sonnet 4 recovers 89% of full-spec results; behavior questions help, code-answerable ones do not. CLARITI's 3.0 questions matched GPT-5's 5.1 (36.8% vs 35.6%). A separate intent agent: 69.4% vs 61.2%.
- 对 skill 的启示：Explore, then ask once before editing via AskUserQuestion: 3-5 impact-ranked questions, each with a recommended option, evidence and a sample diff; batch inferred sites in multiSelect.
- 来源：<https://arxiv.org/html/2502.13069v3>；<https://arxiv.org/html/2604.14624v1>；<https://arxiv.org/html/2603.26233v3>

### 5.9 S3 fails on deletion and fading reuse

`s3-deletion` ｜ 类型：论文 ｜ 年份：2026† ｜ 场景：S3 ｜ 置信度：中 ｜ 核验：已核实

- 要点：Passing patches skip 28.3-34.8% of developer deletions and 29.0% guard old logic instead; exact deletion spans add 6.5-31.5pp. Over 5 turns repo recall fell 83.6%->35.4% and chains with duplicates rose 13.8%->50.8%, pass rates flat.
- 对 skill 的启示：Write a consolidation spec first: each duplicate's file:line span and delete/redirect action, found by behavior (callees, literals, AST shape). Verify old bodies are gone or delegate; reject guards.
- 来源：<https://arxiv.org/html/2607.28887>；<https://arxiv.org/html/2609.35357>

### 5.10 Tests pass with sites still missing

`verify-beyond-tests` ｜ 类型：论文 ｜ 年份：2025† ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Half of 22 incorrect plausible SWE-bench patches passed all developer tests; 27% were partial fixes. Incomplete Repair (ignored explicit/semantic deps) is a failure class; an expert-reviewer loop solved 24/108 failed issues vs 7.
- 对 skill 的启示：After edits, rerun the recall queries and diff hits (each old hit changed, gone or marked intentional), then a read-only reviewer subagent with intent and ledger only, then tests.
- 来源：<https://arxiv.org/html/2503.15223v2>；<https://arxiv.org/html/2509.13941v1>

## 6 工业界工具（industry-tooling）

范围：Google 大规模改动流程、Claude Code 的 LSP 工具、ast-grep、Semgrep、OpenRewrite、codemod 库、索引检索、给 agent 用的 IDE 检索、embedding 检索，以及本机工具探测。10 条：已核实 8，已更正 2。

### 6.1 Google LSC pipeline

`google-lsc` ｜ 类型：实践 ｜ 年份：2020, 2025† ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Kythe gives callers, Rosie shards by owner, TAP tests. LLM migrations (2025) walk references of references up to distance 5, keep a deliberate superset and let the LLM punt unneeded edits: 39 migrations, 93,574 edits, 69.46% LLM-made; discovery recall unreported.
- 对 skill 的启示：Expand 2-3 reference hops, classify each candidate with evidence, then build/test and re-run discovery until no old-pattern hit remains.
- 来源：<https://abseil.io/resources/swe-book/html/ch22.html>；<https://arxiv.org/abs/2504.09691>

### 6.2 Claude Code LSP tool gaps

`cc-lsp` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Offers findReferences, goToImplementation, workspaceSymbol, incomingCalls; no rename or type hierarchy; errors if no server matches the file. Official plugins: TS, pyright (lacks goToImplementation), gopls, jdtls, kotlin-lsp (alpha), sourcekit-lsp; none for Dart.
- 对 skill 的启示：LSP references/implementations are direct hits; without a server or method, fall back to ast-grep/rg (inferred); suggest, never install, plugins.
- 来源：<https://github.com/anthropics/claude-code/issues/40282>；<https://github.com/traviswye/ContextAtlas/blob/main/docs/adr/ADR-13-python-adapter-pyright.md>

### 6.3 ast-grep structural search

`ast-grep` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S2、S3 ｜ 置信度：高 ｜ 核验：**已更正**

- 要点：Built-in TS/JS, Java, Kotlin, Go, Python, Swift; Dart needs a custom grammar. `$X` matches a node, `$$$` a list, a reused name forces equal code; YAML rules combine kind/regex, inside/has, all/any/not. Syntactic only. Comby last released in 2022.
- 对 skill 的启示：Tier-2 default: turn one exemplar into a metavariable pattern for S2 members and S3 copies, test it via `--stdin`, tag matches inferred.
- 更正：Dart 现在是内置语言。ast-grep 0.42.1（2026-04-04 发布）的 CHANGELOG 写有 'feat: Support Dart again'，0.42.2 升级了 tree-sitter-dart；源码 crates/language/src/lib.rs 的 SupportLang 包含 Dart（别名与扩展名均为 dart）；catalog 页使用 `language: dart` / `-l dart`。当前 npm 的 `@ast-grep/cli` 和 PyPI 的 ast-grep-cli 都是 0.51.0。所以 Dart 不需要自定义 grammar。summary 中 'covering all target stacks except Dart' 对 ast-grep 层不成立，Dart 只缺官方 LSP 插件。
- 来源：<https://ast-grep.github.io/reference/languages.html>；<https://github.com/comby-tools/comby/releases>

### 6.4 Semgrep CE typed patterns

`semgrep` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Typed metavariables (`(Logger $L)` in Java, `$X: T` in Go/TS), import-alias equivalence, deep match `<... ...>`, autofix via `fix:`. CE has no cross-file analysis; it lists Kotlin, Swift, Dart. PyPI needs Python >=3.10.
- 对 skill 的启示：Opt-in to narrow shape matches by type or import alias, and for Dart; run with `--metrics off`.
- 来源：<https://docs.semgrep.dev/writing-rules/pattern-syntax>；<https://docs.semgrep.dev/semgrep-pro-vs-oss/>；<https://docs.semgrep.dev/semgrep-ce-languages>

### 6.5 OpenRewrite type-attributed search

`openrewrite` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S1、S2 ｜ 置信度：中 ｜ 核验：**已更正**

- 要点：Lossless Semantic Trees keep types and formatting; FindImplementations/FindMethods recipes mark hits; `rewrite:dryRun` writes target/rewrite/rewrite.patch. Java/Kotlin/Groovy plus JS/TS, Python, C#; the LST must fit in memory.
- 对 skill 的启示：Opt-in for JVM code when types decide membership or code sits in JARs; needs a building Maven/Gradle project.
- 更正：开源 OpenRewrite 只支持 Java、Kotlin、Groovy 三种编程语言（supported-languages 页写 'As of June 2026'），另支持 HCL/JSON/Properties/Protobuf/TOML/XML/YAML 和 Maven/Gradle。JavaScript、C#、Python 被列为 Moderne 提供的支持：'Moderne offers support for many more languages and frameworks (such as JavaScript, C#, Python, Ruby, COBOL, etc.)'，TypeScript 没有被提及。对本 skill 来说，它只是 JVM 栈的可选工具，不能用于前端或 Python 栈。
- 来源：<https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees>；<https://docs.openrewrite.org/reference/rewrite-maven-plugin>

### 6.6 ts-morph, LibCST, fastmod

`codemod-libs` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：已核实

- 要点：ts-morph wraps the TS compiler (findReferencesAsNodes, getImplementations, rename). LibCST FullyQualifiedNameProvider resolves imported names, relative ones too; types need Pyre. fastmod (regex) and jscodeshift are syntactic.
- 对 skill 的启示：Ship small discovery scripts (ts-morph via npx, LibCST) for when no LSP runs.
- 来源：<https://ts-morph.com/navigation/finding-references>；<https://libcst.readthedocs.io/en/latest/metadata.html>；<https://github.com/facebookincubator/fastmod>

### 6.7 SCIP, Zoekt, Batch Changes

`index-search` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S1、通用 ｜ 置信度：中 ｜ 核验：已核实

- 要点：SCIP indexers cover Java/Kotlin, TS, Python, Dart, Rust, C++. Zoekt is a faster trigram index with rg-level lexical recall. Batch Changes: query-selected repos, container steps, draft changesets.
- 对 skill 的启示：Skip for one repo; SCIP is a headless fallback without LSP; reuse search -> steps -> draft review for multi-repo S1.
- 来源：<https://github.com/sourcegraph/scip>；<https://sourcegraph.com/docs/batch-changes/batch-spec-yaml-reference>

### 6.8 IDE search for agents

`ide-search-agents` ｜ 类型：基准 ｜ 年份：2026† ｜ 场景：S1、S2 ｜ 置信度：中 ｜ 核验：已核实

- 要点：JetBrains' first run never called its IDE tools; in a 2,700-run redo GPT-5.5 made zero calls, GPT-5.6 used them in 616-660/675 at +6-7% median cost. Netflix (IntelliJ via LSP, Java/Kotlin): 20-30% more efficient, correctness unchanged; grep misses JAR code; JDT LS failed on Gradle.
- 对 skill 的启示：Prescribe calls: findReferences per changed symbol, goToImplementation per changed interface; merely available tools go unused.
- 来源：<https://blog.jetbrains.com/ai/2026/05/what-happens-when-you-give-agents-ide-native-seach-tools/>；<https://blog.jetbrains.com/ai/2026/10/how-netflix-made-ai-coding-agents-more-efficient/>

### 6.9 Embedding retrieval

`embeddings` ｜ 类型：基准 ｜ 年份：— ｜ 场景：S3、通用 ｜ 置信度：中 ｜ 核验：已核实

- 要点：Cursor: semantic+grep beats grep by 12.5% QA accuracy, +0.3% code retention (+2.6% at 1,000+ files). ContextBench talk: file precision 65->81->87%, recall 49->39->39%; Claude Code did not reliably pick the semantic tool.
- 对 skill 的启示：Use only for low-confidence S3 behavior-alike candidates (listed, never edited), not as the recall layer.
- 来源：<https://cursor.com/blog/semsearch>；<https://ai.engineer/talks/zKk7sDMGDEQ-benchmarking-semantic-code-retrieval-on-claude>

### 6.10 Local tool probe

`local-env` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：rg is a shell function over bundled ripgrep 14.1.1, invisible to Python subprocess; git grep exists. Absent: ast-grep, semgrep, comby, gopls, pyright, brew. Present: node 24, npx, uvx, python 3.9. `npx ast-grep` runs an unrelated 2018 package; working: `npx -y -p @ast-grep/cli ast-grep`, `uvx --from ast-grep-cli ast-grep`.
- 对 skill 的启示：Probe with `command -v`; scripts must not shell out to rg (use git grep); never run `npx ast-grep`; ask before the first npx/uvx download.
- 来源：command -v/npx/uvx probes, macOS, 2026-10-30

## 7 Claude Code 生态（claude-code-ecosystem）

范围：Claude Code 内置的检索方式、LSP 插件、语义 MCP、现有影响分析类 skill/插件、Explore 子代理、Stop hook、确认关口，以及确认后的耦合如何持久化。10 条：已核实 9，已更正 1。

### 7.1 Search runs as grep/find via Bash

`bash-search` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：On macOS/Linux/WSL, Glob and Grep are not default tools; Claude searches with embedded bfs/ugrep via Bash, which hooks see as Bash calls. Pilot round 2 (9 runs, 283 calls): Bash 88, Read 65, zero Grep/Glob/LSP/Agent. No rg binary on PATH here.
- 对 skill 的启示：Script searches with git grep/grep/find, not rg; match search hooks on Bash.
- 来源：<https://code.claude.com/docs/en/tools-reference>；`/Users/yezhoufan/VScodeProjects/change-propagation/docs/research/pilot/results/round2/usage.json`

### 7.2 LSP tool needs a plugin and a server

`lsp-optional` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：The LSP tool (references, call hierarchy) is inactive until a code-intelligence plugin and its server binary are installed, and off in cloud sessions. The marketplace has 13 `*-lsp` plugins, none for Dart; of probed servers only sourcekit-lsp and clangd are on PATH.
- 对 skill 的启示：Probe LSP once; use references when it works, else grep, and log the fallback.
- 来源：<https://code.claude.com/docs/en/tools-reference>；`/Users/yezhoufan/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json`

### 7.3 Semantic MCPs are optional installs

`semantic-addons` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Serena wraps language servers (40+ languages incl. Dart). ast-grep MCP needs the ast-grep CLI (absent here). GitNexus writes CLAUDE.md and hooks on analyze and is PolyForm Noncommercial. Codebase-Memory: 83% answer quality vs 92% for file exploration at ~10x fewer tokens.
- 对 skill 的启示：Use them when present, verify hits by reading code, never require or bundle them.
- 来源：<https://github.com/oraios/serena>；<https://github.com/ast-grep/ast-grep-mcp>；<https://github.com/abhigyanpatwari/GitNexus>

### 7.4 No tool checks scope completeness

`scope-gap` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、S2、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Regex `impact|refactor|duplicat|rename|propagat|blast|symbol|clone|references` over 315 plugin names/descriptions hits 10; none targets scope completeness. /batch splits work into 5 to 30 units; /simplify and /code-review review the diff. Sourcegraph adds cross-repo search but needs an MCP-enabled instance and token.
- 对 skill 的启示：Orchestrate; feed /batch the confirmed list; search listed sibling repos.
- 来源：`/Users/yezhoufan/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json`；<https://code.claude.com/docs/en/commands>；<https://github.com/sourcegraph-community/sourcegraph-claudecode-plugin>

### 7.5 Impact skills analyze breakage, not scope

`impact-skills` ｜ 类型：实践 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：**已更正**

- 要点：cursor blast-radius looks where grep stops (API JSON, DB columns) and grades evidence 1-5. impact-map is a read-only pre-change report covering naming variants, duplicated logic and git co-change. Neither gates edits on confirmation.
- 对 skill 的启示：Reuse their evidence ladder, tiers and co-change signal; add a confirm gate and residual check.
- 更正：Only blast-radius has no gate. impact-map stops on findings that need a decision and needs an explicit yes before planning. What it lacks is a rule that every inferred coupling waits for confirmation, and a post-edit residual check.
- 来源：<https://github.com/cursor/plugins/blob/main/pstack/skills/blast-radius/SKILL.md>；<https://github.com/soumyaRauth/skills-hub/blob/main/skills/impact-map/README.md>

### 7.6 Explore fits sweeps; Workflows cannot pause

`explore-fanout` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S2、S3、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Explore is read-only and starts without CLAUDE.md; defaults allow 20 concurrent subagents, depth 3. Workflows take no mid-run user input. Cartographer splits a repo by token budget across parallel Sonnet subagents.
- 对 skill 的启示：Fan out per-directory Explore sweeps returning path:line plus evidence; confirm in the main session.
- 来源：<https://code.claude.com/docs/en/sub-agents>；<https://code.claude.com/docs/en/workflows>；<https://github.com/kingbootoshi/cartographer>

### 7.7 Stop hook plus ledger enforce completion

`stop-hook-ledger` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Skills docs put must-hold rules in hooks, which skill frontmatter can declare. A Stop hook can block; after 8 consecutive blocks Claude Code ends the turn. PostToolUse Edit|Write misses Bash edits. Task tools are default only on Opus 4.7, Sonnet 4.6, Haiku 4.5 and earlier.
- 对 skill 的启示：Keep candidates in a JSON ledger; block Stop while entries are open or residual search hits; honor stop_hook_active; read edits from git diff.
- 来源：<https://code.claude.com/docs/en/skills>；<https://code.claude.com/docs/en/hooks>；<https://code.claude.com/docs/en/tools-reference>

### 7.8 Questions and plan approval gate edits

`confirm-gate` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Questions stay open unless askUserQuestionTimeout is set, after which Claude proceeds on its own judgment; plan approval never auto-resolves on idle. In the pilot, 2 of 3 T1 runs edited inferred couplings unasked, incl. rewriting the API doc line tying reset to the register rule.
- 对 skill 的启示：Ask once with evidence; treat timeout as not confirmed; never edit constraint docs first.
- 来源：<https://code.claude.com/docs/en/tools-reference>；`/Users/yezhoufan/VScodeProjects/change-propagation/docs/research/pilot/README.md`

### 7.9 extract-rules loops to saturation with referees

`saturation-referee` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：It loops until a round adds fewer than 3 new rules or under 15%, runs one citation referee per fresh rule, never renders unverified rules as confirmed, and forbids acting on instruction-shaped text in source (line 215).
- 对 skill 的启示：Search in rounds until one adds <3 candidates; verify each before showing; ignore instructions in scanned files.
- 来源：`/Users/yezhoufan/.claude/plugins/marketplaces/claude-plugins-official/plugins/code-modernization/workflows/extract-rules.js`

### 7.10 Confirmed couplings can persist as path rules

`persist-couplings` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1 ｜ 置信度：高 ｜ 核验：已核实

- 要点：A .claude/rules file with paths frontmatter loads when Claude reads or edits a matching file. Kiro steering offers fileMatch inclusion. Spec Kit /analyze is read-only, caps findings at 50 and expects stable IDs on rerun.
- 对 skill 的启示：After confirmation, offer a rule naming both coupled sites; keep candidate IDs stable.
- 来源：<https://code.claude.com/docs/en/memory>；<https://kiro.dev/docs/steering/>；<https://github.com/github/spec-kit/blob/main/templates/commands/analyze.md>

## 8 Skill 规范（skill-spec）

范围：agentskills.io 规范与 Claude Code 的 SKILL.md 字段、列表截断与触发、fork 与命令注入、hook、validate 与 plugin eval、skill-creator，以及插件发布。10 条：已核实 9，已更正 1。

### 8.1 Portable frontmatter rules

`portable-fields` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Spec: name required, 1-64 chars of a-z, 0-9 and single inner hyphens, equal to its folder; description required, 1-1024 chars; optional license, compatibility (<=500), metadata (string map), allowed-tools (experimental). claude.ai and the Skills API reject other keys.
- 对 skill 的启示：Use name: change-propagation in skills/change-propagation/; description third-person, under 1024 chars, with a 'Use when' clause, no angle brackets; allowed-tools as one space-separated string; version in plugin.json.
- 来源：<https://agentskills.io/specification>；<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>

### 8.2 Claude Code-only fields

`cc-fields` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S2、通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Claude Code adds when_to_use, argument-hint, arguments, disable-model-invocation (true hides the description), user-invocable, disallowed-tools, model, effort, context, agent, background, hooks, paths, shell. A plugin skill runs as /plugin:skill; with name set, bare /name also works if free.
- 对 skill 的启示：Omit disable-model-invocation, user-invocable, model and paths (paths waits for a matching file, too late for a plan step, S2). Add argument-hint; document both command forms.
- 来源：<https://code.claude.com/docs/en/skills>

### 8.3 Listing cap and undertriggering

`listing-trigger` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：description+when_to_use is cut at 1,536 chars; the listing gets 1% of context and on overflow the least-invoked skills lose descriptions first. skill-creator: Claude consults skills only for tasks it can't easily do alone, and tends to undertrigger.
- 对 skill 的启示：S1-S3 requests look routine, so expect undertriggering. Lead with situations: changing a rule other code must match, 'all X' steps, unify/extract/dedupe, even when one place is named. The name must work alone.
- 来源：<https://code.claude.com/docs/en/skills>；skill-creator SKILL.md

### 8.4 Run the main skill inline

`no-fork` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、通用 ｜ 置信度：高 ｜ 核验：**已更正**

- 要点：context: fork runs the body as a new subagent's task with no conversation history, in the background by default, with fewer tools and edits outside checkpoints. No subagent gets AskUserQuestion.
- 对 skill 的启示：Don't fork: tier-2 confirmation (decision c) needs the original request and AskUserQuestion. Give only the read-only recall sweep to a plugin agent or Explore that returns file:line evidence.
- 更正：Not every subagent: conversation forks (/subtask, or Claude in fork mode, on by default) keep the main session's tools, AskUserQuestion included. Every non-fork subagent, including the one a context: fork skill starts, loses it, so the confirm step still has to run inline.
- 来源：<https://code.claude.com/docs/en/skills>；<https://code.claude.com/docs/en/sub-agents>

### 8.5 Size, compaction, plan files

`size-writing` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：SKILL.md is not re-read; after compaction only its first 5,000 tokens return (25,000 shared). Body under 500 lines, references one level deep, TOC past 100 lines. Batch edits: plan-validate-execute with a script-checked plan file.
- 对 skill 的启示：Put tier rules, ledger format and stop criteria first. Make the ledger the checked plan; re-run its searches after editing. Per-stack recipes go in `references/stacks/<stack>.md` (decision b).
- 来源：<https://code.claude.com/docs/en/skills>；<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>

### 8.6 Injection and hook sharp edges

`inject-hooks` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：`${CLAUDE_SKILL_DIR}` expands in the body and in allowed-tools Bash rules. A `` !`cmd` `` that fails (exit 1 allowed for search/diff) or isn't pre-allowed aborts the invocation. SKILL.md hooks start at invocation and last the session; hooks.json fires from session load; plugin agents ignore hooks.
- 对 skill 的启示：Avoid injection, or allow each command and append `|| true`. Run scripts via `${CLAUDE_SKILL_DIR}/scripts` with a matching Bash() rule. Put a later Stop-hook check in SKILL.md hooks, guarded by stop_hook_active.
- 来源：<https://code.claude.com/docs/en/skills>；<https://code.claude.com/docs/en/hooks>

### 8.7 validate misses SKILL.md errors

`validate-gaps` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：Flagged only YAML errors, a missing description and a bad shell. Passed: unknown keys, uppercase, 65-char and double-hyphen names, name != folder, a 1,600-char description, angle brackets, bad context/effort, broken eval files. Manifest checks are stricter: './' paths, reserved names.
- 对 skill 的启示：CI: validate --strict, a lint script for spec rules (regex, <=64, folder match, <=1024, no `<>`), and a 1-run eval smoke test.
- 来源：local: validate --strict --json, 2.1.309

### 8.8 plugin eval for recall fixtures

`plugin-eval` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：已核实

- 要点：`evals/<case>/prompt.md` + `graders/*.md`; case.yaml adds context.scaffold_script (needs --scaffold, 120 s). Defaults: 3 runs per arm, max_turns 10, 300 s, threshold 1.0, judge haiku. Graders: regex, tool_used, tool_order, file_exists, llm, baseline; no code graders. Skill-used graders are unscored in two-arm runs. This supersedes the platform guide's 'no built-in way' to run evals.
- 对 skill 的启示：Scaffold S1/S2/S3 repos; score recall with a tool_used Edit grader per expected file (file_exists ignores edits). Near misses: Skill min 0 max 0, arm: both. Pass `--scaffold --allow-tools Edit Write`.
- 来源：<https://code.claude.com/docs/en/plugin-evals>

### 8.9 skill-creator trigger tuning

`skill-creator` ｜ 类型：工具 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：20 queries (8-10 near-miss negatives), 5 iterations, 60/40 train/test, 3 runs per query, pick by test score. run_eval.py writes a temp .claude/commands file in the project root and calls claude -p with the user's full setup. evals.json says 'expectations'; agentskills.io says 'assertions'.
- 对 skill 的启示：Tune in a scratch fixture repo, then confirm with plugin eval, which isolates the namespaced skill. Near misses: 'rename this local variable', 'animate this one button'. Use schemas.md keys.
- 来源：skill-creator run_eval.py (local)；<https://agentskills.io/skill-creation/optimizing-descriptions>

### 8.10 Manifest, naming and dev loop

`distribution` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：已核实

- 要点：plugin.json needs only name; claude-, anthropic- or cc-plugin- prefixes fail (verified). version pins users until bumped, else commit SHA. Root CLAUDE.md isn't loaded; `${CLAUDE_PLUGIN_DATA}` survives updates. --plugin-dir outranks installed and skills-dir copies.
- 对 skill 的启示：Name it change-propagation; develop with claude --plugin-dir on the repo; cache in `${CLAUDE_PLUGIN_DATA}`; release via version bump and claude plugin tag; ship README and LICENSE.
- 来源：<https://code.claude.com/docs/en/plugins/manifest-reference>；<https://code.claude.com/docs/en/plugins/loading>

## 9 补缺 1：自动触发与 hook（gap-1）

范围：只靠 description 触发是否可靠、用 UserPromptSubmit/PostToolUse/Stop hook 补足、以编辑内容为查询的本地重放、hook 的时间与输出预算，以及如何评测触发。检索局限：WebSearch 被拦截，来源是直接抓取的一手页面和本地检查。7 条，均为自行核验。

### 9.1 Description-only activation misses simple single-object prompts

`desc-undertrigger` ｜ 类型：基准 ｜ 年份：2026 ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：Spence (Sonnet 4.5, 22 prompts): no-hook control 55%/50%; ~100% when the prompt names the skill keyword, 20-40% generic, ~0% indirect. Vercel: skill never invoked in 56% of cases, pass rate 53%, same as baseline. skill-creator: skills tend to 'undertrigger'; 'Simple, one-step queries... may not trigger a skill'. Skills doc: listing overflow drops least-invoked (new) skills' descriptions first.
- 对 skill 的启示：AGV acceptance-bug prompts are the simple, indirect case. Keep a bilingual description with triggers first for (d), and propose hook-driven tier 0 so candidates arrive as passive context.
- 来源：<https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals>；<https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>；<https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md>

### 9.2 UserPromptSubmit gate: forced-eval vs llm-eval

`ups-gate` ｜ 类型：基准 ｜ 年份：2026 ｜ 场景：通用 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：Forced-eval hook 100%/100% at +2.0 s; llm-eval 100%/100%; type-prompt 55%/41%, like control. On 24 harder prompts: forced-eval 75% with 0/5 false positives, llm-eval 67% with 4/5. Forced-eval text is imperative; the hooks doc asks for factual statements, since command framing can trip prompt-injection defenses.
- 对 skill 的启示：If approved: a command hook with a regex gate under 1 s, no LLM, no blocking; it saves category words to the ledger and injects <=500 chars of facts.
- 来源：<https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals>；<https://scottspence.com/posts/how-to-make-claude-code-skills-activate-reliably>；<https://code.claude.com/docs/en/hooks>

### 9.3 Local replay: edit payload as query finds S1/S3 look-alikes, not S2

`edit-payload-query` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、S2、S3 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：First Edit/Write of 9 pilot runs (40 files) as identifier+subword+removed-literal query: T1 (MIN_PASSWORD_LENGTH 8->12) recall 7/7 from 7 hit files; T3 recall 5/5 plus excluded useCountdown.ts; T2, which first writes a new CSS file, 0/8 in 2 of 3 runs.
- 局限：Tiny fixture; 100k-file precision unmeasured.
- 对 skill 的启示：S1/S3 tier 0 can be pure patch-as-query. S2 needs prompt category words and the edited file's structure (component kind, imports); after a new-file Write, query on the next Edit. Hits stay candidates under (c).
- 来源：`/tmp/cp-gap1/sim.py`；`/Users/yezhoufan/VScodeProjects/change-propagation/docs/research/pilot/gt.json`

### 9.4 Hook budgets force a cached index and short injections

`hook-budgets` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：additionalContext/stdout capped at 10,000 chars; beyond that Claude gets a path and 2,000-char preview. UserPromptSubmit times out at 30 s. At 100k files rg takes 2-4 s, index builds ~50 s. A python3 -I no-op hook: median 63.2 ms. Over this session's 279 Edit/Write calls, rg each time adds 9-19 min.
- 对 skill 的启示：Filter by extension and new identifiers first, query a prebuilt index in `${CLAUDE_PLUGIN_DATA}` with a 2-3 s cap, rebuild detached at SessionStart. Stdlib Python, git grep fallback (rg is only a Claude shell function here). Inject <=2,000 chars; full list in the ledger.
- 来源：<https://code.claude.com/docs/en/hooks>；`/Users/yezhoufan/VScodeProjects/change-propagation/docs/research/04-scale-measurements.md`；`/tmp/cp-gap1/noop_hook.py`

### 9.5 Trigger hooks belong in plugin hooks.json and fire in subagents

`plugin-hooks-scope` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：Skill-frontmatter hooks register only after invocation, so they cannot trigger the skill; plugin hooks/hooks.json is active while the plugin is enabled. Plugin hooks also run inside subagents, with agent_id in the input. `${CLAUDE_PLUGIN_DATA}` survives updates. Command hooks run with full user permissions.
- 对 skill 的启示：Ship tier-0 hooks in hooks/hooks.json; key the ledger by session_id+agent_id. Scripts stay read-only, offline and bounded, with no npx downloads.
- 来源：<https://code.claude.com/docs/en/hooks>；<https://code.claude.com/docs/en/plugins/components>

### 9.6 Stop hook as a scope-disposition gate

`stop-gate` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：Stop input has stop_hook_active; decision block with a reason continues the turn, at most 8 times in a row. Skills doc: 'move the rule into a hook... whether or not Claude is following the skill.'
- 对 skill 的启示：Block once when ledger candidates lack a disposition (edited, user-skipped, listed); exit 0 if stop_hook_active. This enforces (c) across compaction because state is on disk. Effect on recall is unmeasured.
- 来源：<https://code.claude.com/docs/en/hooks>；<https://code.claude.com/docs/en/skills>

### 9.7 Measure hook vs description triggering with claude plugin eval

`trigger-eval` ｜ 类型：工具 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：run_eval.py counts a trigger only if the first tool call is Skill/Read of the skill, and tests a temp command file, not the plugin. plugin eval loads skills and hooks against a no-plugin baseline (3 runs/arm) with tool_used, tool_order, regex and llm graders; async hooks die at -p teardown; history_file resumes a session.
- 对 skill 的启示：Arms: description only; +UserPromptSubmit; +PostToolUse/Stop. Grade Skill use, regex on look-alike paths, llm on (c) disposition. Prebuild the index in scaffold_script; use history_file for late-session cases; add Chinese single-object prompts and near-miss negatives.
- 来源：<https://code.claude.com/docs/en/plugin-evals>；<https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/scripts/run_eval.py>；<https://code.claude.com/docs/en/hooks>

## 10 补缺 2：代码中声明的耦合（gap-2）

范围：代码里显式写出的耦合声明（LINT.IfChange、"keep in sync" 一类注释）在开源仓库中的分布与精度、反向查找、规则载体、指针失效、过时注释检测，以及确认后的耦合如何存放。检索局限：WebSearch 额度在 3 次查询后用完，证据主要来自本地扫描和直接抓取。8 条，均为自行核验。

### 10.1 IFTTT absent; free-text comments dominate

`ifttt-rare` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、通用 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：LINT.IfChange: 0 of 48,447 files; coupling comments: 680 lines in 477 of 34,141 scanned files. GitHub LINT.IfChange files: Java 3,800, Go 1,056, TS 960, Kotlin 815, Swift 87, Dart 67, mostly Google repos; 'keep in sync with': TS 43,776, Go 13,843.
- 对 skill 的启示：Free-text parser by default on all stacks; IFTTT parser only if git grep -c finds directives. Skip tests and generated files.
- 来源：git grep on 6 OSS clones (see search_log)；GitHub code search (MCP)

### 10.2 Phrase precision and target resolution

`freetext-precision` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、S3 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：True couplings: 'keep in sync' 12/20, 'if you change X also update Y' 13/20, 'must match' 5/20, 'mirrors/copied from' 8/20; false positives are runtime sync, test text, generated code. 28-40% of hits name a resolvable path or an identifier in <=5 files. 12 of 25 true sync/update pairs cross languages.
- 对 skill 的启示：Direct hit only for an IFTTT block or a comment in or above the edited hunk whose target resolves. Match/mirror wording and prose-only targets go to the confirm tier, quoted. 'Copied from' seeds S3.
- 来源：manual review, 20 random code hits per family, one rater

### 10.3 Pairs are mostly one-way; reverse lookup is cheap

`reverse-lookup` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S1、S2 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：30 of 68 path-named pairs point back. mattermost TS 'Keep in sync with server/.../integration_action.go MaxDialogFileIds' and 'Mirrors ... model.mmBlocksActionIDRegex' have no Go-side pointer. Grep of edited path and symbol, filtered by coupling verbs: 5 lines incl. both, 1.13 s on 16.5k files (zulip 0.30 s); unscoped phrase grep: 1,649 lines.
- 对 skill 的启示：Bundle a tier-0 script: forward (comments near edited hunks, then targets) and reverse (grep edited path, stem, changed symbols; keep lines with `sync|mirror|same|match|also|update|copied`), max 20 lines, hook-ready.
- 来源：`mattermost@4bf16a6a webapp/platform/types/src/integrations.ts:254`；`zulip@566f98a9 zerver/models/realms.py:436`

### 10.4 Rule carriers tie mirrored validation

`rule-carriers` ｜ 类型：本地核查 ｜ 年份：2011, 2026† ｜ 场景：S1、S2 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：Error-like messages shared across server/web: 1-7 per repo; the action-ID regex literal also matches unrelated PKCE code. zulip password_min_length: 15 files (register, reset, change-password, settings) vs 222 for 'password'; gitea MinPasswordLength/IsComplexEnough: 11 vs 170. WAPTEC (CCS 2011) found parameter-tampering flaws (server checks weaker than client) in all 6 apps tested.
- 对 skill 的启示：Extract carriers at the edit site (config keys, constants, validator names, routes, error/i18n keys), grep them across tiers and docs, and show a per-tier table; one-sided changes are confirm items. This would have kept register and reset together in T1-c2/c3.
- 来源：carrier grep in zulip and gitea clones；<http://www.cs.uic.edu/~venkat/publications.html>

### 10.5 IFTTT semantics and OSS linters

`ifttt-linters` ｜ 类型：工具 ｜ 年份：— ｜ 场景：S1、通用 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：`LINT.IfChange(label) ... LINT.ThenChange(//path:label)`; `NO_IFTTT=<reason>` bypasses. ifttt-lint (Rust, pre-commit/Action) also reports stale targets, Chromium 488k files in 0.9 s. ifchange: ~17 ms per 30k-line diff; source of truth points at derived files. ifttt-lint links files within one repo only.
- 对 skill 的启示：Where directives exist, ThenChange targets of touched blocks are direct hits scoped by label; run the repo's linter after edits. Write-back is opt-in, source to derived.
- 来源：<https://www.chromium.org/chromium-os/developer-library/guides/development/keep-files-in-sync/>；<https://github.com/simonepri/ifttt-lint>；<https://github.com/slnc/ifchange>

### 10.6 Paths survive; pointed-to content drifts

`pointer-rot` ｜ 类型：本地核查 ｜ 年份：2017, 2026† ｜ 场景：S1、S3 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：44 in-repo pointers: 35 exact, 6 suffix-only, 3 basename-only (moved), 0 dead. zulip realms.py:436 says '600 # if changed, also change in admin.ts, settings_org.ts'; neither file holds 600 or 10 * 60. Fraco (ASE 2017): over half of identifiers had fragile comments after renaming.
- 对 skill 的启示：Resolve exact, then suffix, then basename (flag moved). Check the target still holds the value or symbol, else list it as stale for confirmation. On renames, add comments naming the old identifier.
- 来源：path_rot.py on the 6 clones；<https://www.cs.mcgill.ca/~martin/papers/ase2017.pdf>

### 10.7 Just-in-time stale comment detection

`jit-stale-comment` ｜ 类型：论文 ｜ 年份：2021† ｜ 场景：S1 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：Panthaplackel et al. (AAAI 2021): F1 87.1 on 300 cleaned examples; flagging comments sharing a token with deleted or replaced code scores 74.7; post-hoc models 53.9-67.9.
- 对 skill 的启示：After each edit, list comments and doc lines holding tokens the diff deleted or replaced as confirm items. Never silently rewrite a doc line tying two features (T1-c3).
- 来源：<https://arxiv.org/abs/2010.01625>

### 10.8 Anchors, not line numbers, for stored couplings

`sidecar-anchors` ｜ 类型：论文 ｜ 年份：2007† ｜ 场景：S1、S3 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：CloneTracker (ICSE 2007) stores regions outside code as file/class/method-signature/block-nesting descriptors plus a corroboration metric: 96% of 3,275 regions tracked correctly in 5 Java systems; the metric resolved 81% of ambiguous matches.
- 对 skill 的启示：Persist confirmed couplings under .claude/ as path + symbol + short anchor (e.g. 'MaxDialogFileIds = 10'), re-resolved on read. Add in-code pointers only where the repo already uses them.
- 来源：<https://www.cs.mcgill.ca/~martin/papers/icse2007.pdf>

## 11 补缺 3：权限模式与确认关口（gap-3）

范围：auto、plan、dontAsk 和 -p 模式下 skill 的权限规则、台账写在哪里、确认关口（AskUserQuestion、PreToolUse ask）在各模式下是否可用，以及 plugin eval 的运行环境。检索局限：检索额度在 2 次查询后用完，证据来自文档、Anthropic 的 auto mode 文章和 Claude Code 2.1.309 二进制。7 条，均为自行核验。

### 11.1 Pin allow rules to script paths; grant ends at next user message

`auto-rule-shape` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：通用 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：Auto mode drops `Bash(*)`, a bare interpreter, `'<interp> *'`, `'<interp>:*'`, `'<interp>*'` and `'<interp> -..*'` (`python -m pkg.mod` is exempt) for python/python3/node/npx/bash/sh/env/xargs and others. `'python3 /abs/x.py *'` passes, so those calls skip the classifier. The docs example `Bash(python3 *)` is dropped. classifyAllShell (user/managed) suspends all shell rules. The grant 'clears when you send your next message'.
- 对 skill 的启示：allowed-tools: `Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py *)`, one per script. Show the exact unquoted command; no `cd &&`, no `>` redirects. Gate with AskUserQuestion in the same turn, or re-grant in a /change-propagation:apply skill. Never write rules into settings.
- 来源：<https://code.claude.com/docs/en/settings-reference>；<https://code.claude.com/docs/en/skills>；local:claude 2.1.309 binary fn zYn

### 11.2 Plan mode: only the plan file is writable

`plan-mode-ledger` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：S2、S3 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：Other writes return 'Cannot write to X while in plan mode'. The plan prompt forbids non-read-only tools and overrides other instructions. Phase 4 says to 'list a few representative paths'. Subagents stay in plan mode. With clear-context on accept, the plan is the only handoff.
- 对 skill 的启示：Tier-0 scripts only read and print to stdout. In plan mode, add a required ledger appendix to the plan file: the full tier lists, or the tier-0 query plus counts. State that it overrides the sample-paths rule. Write ledger.json after approval.
- 来源：<https://code.claude.com/docs/en/permission-modes>；<https://code.claude.com/docs/en/sub-agents>；<https://code.claude.com/docs/en/settings-reference>

### 11.3 Keep the ledger in the working dir, outside .claude/

`ledger-location` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：.claude (project and ~/.claude) and --plugin-dir are protected: prompt in default, classifier in auto, denied in dontAsk. CLAUDE_PLUGIN_DATA is `~/.claude/plugins/data/<id>/`. Auto approves edits only in the working dir. Eval Bash writes stay in the workspace.
- 对 skill 的启示：Write `<project>/.change-propagation/ledger.json` with its own .gitignore of `*`. Never write under .claude/ or CLAUDE_PLUGIN_DATA from tool calls.
- 来源：<https://code.claude.com/docs/en/permission-modes>；<https://code.claude.com/docs/en/plugins-reference>；<https://code.claude.com/docs/en/plugin-evals>

### 11.4 Auto mode does not limit scope; a PreToolUse ask does

`auto-no-scope-gate` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：Auto mode approves working-dir edits before the classifier runs. FNR on real overeager actions is 17% (n=52), at 0.4% FPR (n=10,000). 3 consecutive or 20 total blocks pause auto mode. A PreToolUse 'ask' goes to the prompt, not the classifier. In -p, Claude reads the deny reason.
- 对 skill 的启示：Ship an optional stdlib PreToolUse hook on Edit|Write. When an edit touches a tier-2-pending or tier-3 span in the active ledger, it returns ask, or deny with a reason in dontAsk/-p. With no ledger it does nothing.
- 来源：<https://code.claude.com/docs/en/permission-modes>；<https://code.claude.com/docs/en/hooks>；<https://www.anthropic.com/engineering/claude-code-auto-mode>

### 11.5 Where AskUserQuestion works, and its limits

`auq-availability` ｜ 类型：文档 ｜ 年份：— ｜ 场景：S1、S2、S3 ｜ 置信度：高 ｜ 核验：自行核验

- 要点：Interactive sessions, including auto and plan: always a real prompt. The auto-mode reminder says to ask when a skill wants it. Removed from all subagents, so a context: fork skill has no gate. In -p it is offered only with a permission host (canUseTool, --permission-prompt-tool, or a hook returning allow + updatedInput.answers). 1-4 questions, 2-4 options each, multiSelect, free-text Other. A timeout submits only the options already picked.
- 对 skill 的启示：Run the gate in the main conversation and mark it mandatory in auto mode. Fit at most 16 items per call and group the rest. A timeout or no selection means not confirmed. If the tool is missing, mark tier-2 pending and do not edit it.
- 注：8.4 的更正（经独立核验）指出 conversation fork 保留 AskUserQuestion，与本条"Removed from all subagents"不一致；"context: fork skill has no gate"与该更正一致。
- 来源：<https://code.claude.com/docs/en/hooks>；<https://code.claude.com/docs/en/sub-agents>；<https://code.claude.com/docs/en/tools-reference>

### 11.6 plugin eval: dontAsk child with no permission host

`eval-runs` ｜ 类型：本地核查 ｜ 年份：2026† ｜ 场景：通用 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：Each run is `claude -p --permission-mode dontAsk --setting-sources user` with a temp home, sandboxed Bash and settings allow rules filtered out. Bash, Write and Edit need the operator's --allow-tools; a skill's allowed-tools cannot widen it. dontAsk denies AskUserQuestion, and the denial tells Claude to STOP and explain. Plugin hooks run. Graders: regex, tool_used (min 0/max 0), file_exists, `{source: file}`, plus history_file.
- 对 skill 的启示：Test the gate in two cases. Pre-gate: tier-2 items in last_message, and `tool_used Edit input_match <tier-2 path> min 0 max 0`. Post-gate: history_file with the gate shown, the user's confirmation as the prompt, and assert the confirmed edits. Grade ledger.json with `{source: file}`.
- 来源：<https://code.claude.com/docs/en/plugin-evals>；local:claude 2.1.309 binary eval runner

### 11.7 Hooks for mode and inventory, Bash for seed scans

`hook-vs-bash` ｜ 类型：文档 ｜ 年份：— ｜ 场景：通用 ｜ 置信度：中 ｜ 核验：自行核验

- 要点：Command hooks run outside the permission system with full user permissions, in every mode. UserPromptExpansion fires on a typed /skill; PreToolUse(Skill) fires when Claude invokes it. additionalContext is capped at 10k chars. PreToolUse input includes permission_mode; not every event has it.
- 对 skill 的启示：On both events, inject detected stacks, a prior-ledger summary and permission_mode where present, in under 10k chars, so the skill picks its path (plan -> appendix, dontAsk/-p -> pending-only). Scans that need the seed stay in Bash scripts.
- 来源：<https://code.claude.com/docs/en/hooks>
