export const meta = {
  name: 'change-propagation-followup',
  description: 'Follow-up research on the user scenario: fix one object, find its unfixed look-alikes in a 100k-scale multi-frontend repo under a token budget',
  phases: [
    { title: 'Research', detail: '4 web-only dimensions tied to the AGV platform scenario' },
    { title: 'Verify', detail: 'adversarial source check per web dimension' },
    { title: 'Synthesize', detail: 'write docs/research/03-scenario-followup.md' },
  ],
}

const ROOT = '/Users/yezhoufan/VScodeProjects/change-propagation'

const CONTEXT = `PROJECT CONTEXT
We are designing "change-propagation", a Claude Code plugin (skill plus optional subagents, hooks and scripts) that makes coding agents recall the full scope of a change.
The user's real scenario (summarized from their words): a personal "multi-instance AGV real-time monitoring and task dispatch platform", about 100k in scale, complex architecture with several separate frontends. It grew from a simple demo through frequent, phase-by-phase AI-generated iterations, so reuse and module boundaries are messy and many look-alike objects drifted apart. Typical prompts are fine-grained detail problems the user found during acceptance testing after bringing up the stack, or bugs found in code review. A PR usually fixes one object, and the agent does not consider look-alike objects (the same logic elsewhere, in another frontend, or a sibling component) that the acceptance notes did not mention. Grep and keyword search do not reach the recall the user expects. Token cost must stay low. The codebase is so large that the agent's context fills within a few turns; even when told to read one whole frontend, it still misses sites.
Pilot evidence: on a 40-file fixture, Opus subagents found every site in 9/9 runs by combining many lexical, structural and API signatures and reading most files; the reproducible failure was unilateral scope decisions on coupled rules. So the recall problem appears at scale, under context and cost limits, and when look-alikes share no vocabulary.
Covered by a parallel research run, so do not survey these broadly: classic systematic edits (LASE, Sydit, Refazer, Coccinelle), LLM edit propagation (CodePlan, CoEdPilot), co-change mining, clone taxonomies, generic agent failure studies, generic tool overviews (ast-grep, Semgrep, OpenRewrite, LSP), the Claude Code skill spec.
Today is 2026-10-30.
USER ANSWERS (2026-10-30): the AGV repo has about 100k files including generated code and static assets. Backends are Go, Python and Node; the several frontends are Vue. Frontends and backends talk through WebSocket real-time push and MQTT/message queues. Cost policy is tiered: by default only cheap checks (scripts search outside the agent context and return a compact candidate list); subagent-level verification only when the user asks or the change is high-risk. The first stack to support and evaluate is Vue + Go/Python/Node with MQTT/WebSocket contracts.`

const RULES = `RULES
- Load WebSearch/WebFetch with ToolSearch ("select:WebSearch,WebFetch") if needed. Run 12+ distinct searches and open primary sources (papers, official docs, repos).
- Cite only URLs you opened or saw in results. Never invent papers, numbers or quotes; mark confidence low when unsure.
- Prefer mechanisms and numbers (recall, precision, tokens, seconds, repo sizes) over adjectives.
- Every finding needs a skill_implication specific to this scenario: what the skill should do, script, check or avoid, and roughly what it costs.
- Do not create or modify files under ${ROOT}. Do not clone repositories or run downloaded packages (npx, uvx, pip install); use web sources only. Temp notes only under /tmp.`

const S = { type: 'string' }
const FINDINGS = { type: 'object', required: ['dimension', 'summary', 'findings', 'open_questions'], properties: {
  dimension: S, summary: { type: 'string', description: '4-8 sentences on what is known, for this scenario' },
  findings: { type: 'array', items: { type: 'object', required: ['id', 'title', 'kind', 'sources', 'claim', 'skill_implication', 'confidence'], properties: {
    id: { type: 'string', description: 'unique short slug' }, title: S, year: S,
    kind: { type: 'string', description: 'paper | tool | doc | dataset | practice | repo | local-check' },
    sources: { type: 'array', items: S }, claim: { type: 'string', description: 'what it is or found, with numbers' },
    mechanism: S, cost: { type: 'string', description: 'runtime, tokens or dependencies' }, limitations: S,
    skill_implication: S, confidence: { type: 'string', enum: ['high', 'medium', 'low'] } } } },
  open_questions: { type: 'array', items: S } } }
const VERIFY = { type: 'object', required: ['checks'], properties: {
  checks: { type: 'array', items: { type: 'object', required: ['id', 'verdict', 'evidence'], properties: { id: S,
    verdict: { type: 'string', enum: ['verified', 'corrected', 'unverifiable', 'refuted'] }, evidence: S, correction: S } } },
  missed_important_work: { type: 'array', items: S } } }

const DIMS = [
  { key: 'variant-analysis', web: true, focus: `"Found one bug or fix, find its variants" as a technique family. Cover: security variant analysis (GitHub CodeQL multi-repository variant analysis, Semgrep rules written from a fix, Google Project Zero variant analysis, Big Sleep and other LLM-driven variant hunting 2024-2026), patch-based vulnerable code clone detection (ReDeBug, VUDDY, MVP USENIX Security 2020, MOVERY 2022, V1SCAN 2023 and successors), similar-bug detection seeded by a fix, recurring and supplementary or incomplete fixes (e.g., Park, Kim, Ray and Bae MSR 2012 on supplementary bug fixes; incomplete patch studies; how often a fix needs follow-up fixes elsewhere), and 2024-2026 LLM work on propagating a fix to similar code. Questions: how to turn a fix diff into queries that do not depend on the object's name (before-pattern signatures, AST patterns with holes, normalized token sequences, data-flow signatures); reported precision and recall at large scale; false-positive control; which of these can run as small scripts on Go, Python, Node and Vue code in a 100k-file repo within seconds to minutes.` },
  { key: 'context-and-budget', web: true, focus: `Token-budgeted retrieval for agents in very large repos (about 100k files). Cover: repo maps (Aider's tree-sitter tags plus PageRank under a token budget, and similar outline approaches), code indexes (universal-ctags, SCIP/LSIF, Zoekt), embedding indexes and their costs at 100k files (indexing time, storage, query latency; claude-context MCP by Zilliz, Serena, Cursor or Augment style indexing), evidence on agentic grep vs. index or embedding retrieval for recall (Claude Code and Cline statements, Augment and Sourcegraph arguments, 2025-2026 studies), Anthropic's guidance on context engineering (just-in-time retrieval, subagent isolation, compaction, structured note-taking to files), Claude Code mechanisms that keep heavy work out of the main context (subagents including Explore, skills with context: fork, scripts with compact output, hooks), measured token costs of subagent fan-out, cascaded verification (cheap filter then strong-model check; FrugalGPT-style routing; Haiku as triage), and keeping a scope list alive across compaction and long sessions. Give concrete numbers to size a tiered design: tier 0 scripts only, tier 1 cheap-model triage of top-N candidates, tier 2 strong-model verification.` },
  { key: 'contracts-vue-go-python', web: true, focus: `Contract-anchored tracing across Go, Python and Node backends and several Vue frontends that talk over MQTT and WebSocket. Cover: AsyncAPI (channels, messages, code-first extraction, generators) and lighter options when no spec exists; how MQTT topics, WebSocket event names and payload fields appear in code (Go struct json tags, Python dicts or pydantic models, Node handlers, Vue subscribers, Pinia or Vuex stores, composables); matching MQTT wildcards (+, #) to pair publishers and subscribers; identifier case conversion across layers (snake_case, camelCase, PascalCase, kebab-case, SCREAMING_CASE) and generated name variants; Vue-specific look-alike surfaces (SFC template, script and style blocks, kebab vs Pascal component names, props and emits, Vue 2 mixins and filters, Vue 3 composables, duplicated status-to-color or status-to-label maps); parser and LSP support for structural search and references in .vue files (ast-grep Vue status and languageInjections, @vue/compiler-sfc, vue-eslint-parser, Vue Language Tools/Volar find-references, whether a Claude Code LSP plugin for Vue exists), and Go and Python equivalents (gopls, gogrep, ast-grep, pyright, LibCST). Output a recipe for a 'contract map' script plus name-variant expansion, and say which parsers or LSPs are worth depending on.` },
]

DIMS.push(
  { key: 'eval-construction', web: true, focus: `How to build a scenario-faithful evaluation. (1) Candidate open-source repos that match Go/Python/Node backends + Vue frontends + MQTT/WebSocket + several frontends or several repos + large size. Check at least ThingsPanel (backend and frontend repos), JumpServer (core, lina, luna, koko), 1Panel, Gitea, EMQX dashboard with EMQX, Open-RMF rmf-web, ThingsBoard and GitLab; report languages, file counts, license, activity and how frontends and backends are split. (2) Mining real 'fix one place, later fix the look-alike' commit pairs from history: commit-message heuristics (also, same fix, forgot, missed, another place, similar, 同样, 漏改, 遗漏, 也要), follow-up commits that touch clone pairs, SZZ-style links, and how prior supplementary-patch studies built their datasets. Find 3-5 concrete examples through GitHub web pages or search results (commit or PR links); do not clone repositories. (3) Existing benchmarks for multi-location or incomplete edits that are less widely known (SWE-PolyBench, Multi-SWE-bench, any missed-edit datasets). (4) Metrics and protocol: site recall and precision, scope-decision conformance, tokens and time, with-skill vs. without-skill through 'claude plugin eval'.` },
)

const researchPrompt = d => `${CONTEXT}\n\nYOUR DIMENSION: ${d.key}\n${d.focus}\n\n${RULES}\n\nReturn 8-15 findings via the schema with dimension="${d.key}".`
const verifyPrompt = (d, r) => `${CONTEXT}\n\nYou are an adversarial fact-checker for research dimension "${d.key}". Pick up to 8 findings that matter most for the design (prefer strong claims and numbers). Open each source with WebFetch (load via ToolSearch "select:WebSearch,WebFetch"), or search for the work if the URL fails. Verdicts: verified = a source supports the claim; corrected = mostly right but a detail is wrong, give the fix; unverifiable = no source you could open supports it; refuted = a source contradicts it. Default to unverifiable when unsure. Use the finding ids. Also list up to 3 clearly important works the report missed (title + URL). Do not modify files under ${ROOT}.\n\nREPORT:\n${JSON.stringify(r)}`

function merge(r, v) {
  const byId = {}
  for (const c of (v && v.checks) || []) byId[c.id] = c
  const all = (r.findings || []).map(f => { const c = byId[f.id]; return { ...f, verdict: c ? c.verdict : (v ? 'unchecked' : 'local-check'), correction: (c && c.correction) || '' } })
  return { dimension: r.dimension, summary: r.summary, findings: all.filter(f => f.verdict !== 'refuted'), refuted: all.filter(f => f.verdict === 'refuted').map(f => f.title), open_questions: r.open_questions || [], missed: (v && v.missed_important_work) || [] }
}

const results = (await pipeline(DIMS,
  d => agent(researchPrompt(d), { label: `research:${d.key}`, phase: 'Research', schema: FINDINGS }),
  (r, d) => !r ? null : d.web
    ? agent(verifyPrompt(d, r), { label: `verify:${d.key}`, phase: 'Verify', schema: VERIFY }).then(v => merge(r, v))
    : Promise.resolve(merge(r, null)),
)).filter(Boolean)
log(`${results.length}/${DIMS.length} dimensions, ${results.reduce((n, r) => n + r.findings.length, 0)} findings kept`)
for (const r of results) if (r.refuted.length) log(`${r.dimension}: dropped refuted findings: ${r.refuted.join('; ')}`)

phase('Synthesize')
const corpus = results.map(r => ({ ...r, findings: r.findings.map(f => ({ ...f, sources: (f.sources || []).slice(0, 3) })) }))
const report = await agent(`${CONTEXT}\n\nTask: write ${ROOT}/docs/research/03-scenario-followup.md in Chinese (keep technical terms in English) for the user who is building the skill. Use only the corpus below. Apply every 'correction'. Mark findings whose verdict is unchecked or unverifiable with （未核验）, and label local measurements as 本机实测. Sections: 1 场景定义：近似对象召回 (a precise definition of 'fix one object, find its unfixed look-alikes', with the user's constraints); 2 为什么 grep 和通读都不够 (mechanisms and evidence); 3 技术手段 (table: technique, how it builds queries from the fix, Go/Python/Node/Vue support, cost with measured numbers where available, best use); 4 契约锚点：MQTT/WebSocket 与多前端 (contract map recipe, name-variant expansion, Vue specifics); 5 成本与分档 (tier 0/1/2 with concrete numbers, what enters the main context, how the scope list survives compaction); 6 评测构建 (candidate repo table, mined commit-pair examples, metrics and protocol); 7 对 skill 架构的启示 (for discussion, not final); 8 未决问题. Cite as [n] with a numbered URL list at the end. Write the file with the Write tool: write the first part with Write, then append with Edit, keeping every tool call under 8 KB. Write only this one file under ${ROOT}. Return a 300-500 word Chinese summary plus the file path.\n\nCORPUS:\n${JSON.stringify(corpus)}`, { label: 'write:followup', phase: 'Synthesize' })
return { report, dimensions: corpus.map(r => ({ dimension: r.dimension, n: r.findings.length, summary: r.summary, open_questions: r.open_questions, missed: r.missed })) }
