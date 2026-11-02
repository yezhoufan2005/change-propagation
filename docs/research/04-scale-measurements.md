# 规模测量：tier 0 脚本检索的耗时、输出量和命中质量

## 目的

change-propagation 要帮 coding agent 找全一次改动必须波及的位置。用户的真实项目是 AGV 监控与任务调度平台：约 10 万个文件（含生成代码和静态资源），Go、Python、Node 后端，多个 Vue 前端通过 MQTT 和 WebSocket 通信。典型的漏改是 PR 修好了一个对象，别处长得像的对象还是坏的；按名字搜索找不到它们，Agent 的上下文几轮就满，token 预算也有限。

这次测量只看不调用模型的脚本检索（tier 0），回答四个问题：

1. 在约 2.5k 文件的两个开源仓库上，ripgrep、契约锚点（contract anchors）和 shingle 索引各要多久，输出多大；ast-grep 和 jscpd 的结果和它们有什么不同。
2. 命中质量如何：哪些是真的关联或相似代码，哪些是噪声。
3. 放大到约 10 万文件时，耗时和体积怎么变。
4. 约 2k token 的预算能放下多少候选。

## 环境与仓库

| 项 | 内容 |
|---|---|
| 机器 | Apple M2，8 核（4 性能核 + 4 能效核），16 GB 内存，macOS 27.0.1（26A434），Darwin 27.0.0 arm64 |
| ripgrep | 14.1.1（rev 0ae49f8b6e，+pcre2，NEON，PCRE2 10.45 JIT），即 Claude Code 2.1.312 内置的 rg |
| Python | 3.9.6（`/usr/bin/python3`），脚本只用标准库 |
| git | 2.54.0（Apple Git-157） |
| ast-grep、jscpd | 0.51.0、5.4.2，经 npx 下载到 `/tmp/cpf-npm`，由用户在自己的终端运行（见"ast-grep 与 jscpd"） |

两个仓库是开源 IoT 平台 ThingsPanel 的后端和前端：Go 后端加 Vue 前端，经 MQTT topic 和 WebSocket endpoint 通信。结构上接近目标场景，但规模小，只有一个前端，后端几乎只有 Go。主会话用 `git clone --depth 1` 克隆到 `/tmp/cpf-measure/repos`，文件数和行数由 `measurements/repo_stats.py` 统计（跳过 `.git` 和 `node_modules`）。

| 仓库 | commit | 克隆 | 文件 | 主要内容 |
|---|---|---|---|---|
| thingspanel-backend-community | `7f694779c979702740b15125164ebec2545604a4`（2026-10-29 23:42 +0800） | 7.2 s，35 MB | 1599 | Go 1206 个文件 / 252,647 行；22 个 `.py`；82 个 `.sql` |
| thingspanel-frontend-community | `b911926fd15eb3eee5c3034a91f1dc7592d68dbe`（2026-10-29 17:50 +0800） | 4.8 s，24 MB | 923 | 344 个 `.vue`（81,983 行）、321 个 `.ts`（44,015 行）；Vue 3.4、Pinia、naive-ui、axios |

两个仓库合计 2522 个文件，下文称"2.5k 文件"。其中扩展名属于 `.go .py .vue .ts .js .json .sql .yaml .yml .md` 的源文件有 2310 个、16.8 MB（后端 1522 个，前端 788 个），它们是放大实验的复制单位。

## 方法

**计时和计量。** 耗时用 `time.perf_counter` 记录墙钟时间，含进程启动（rg 启动约 5-9 ms）。每项测量连跑两次，记为"第一次运行"和"重复运行"。macOS 没有管理员权限清不掉文件缓存，所以第一次运行不等于冷缓存；放大实验的文件刚写入，所有运行都在热缓存上。输出量记字符数，token 按字符数 / 4 估算。这会低估 CJK 文本的 token，但本次 rg 输出里 CJK 字符只占 1.7%。

**脚本**（都在 `docs/research/measurements/`，只依赖 Python 标准库和 rg）：

- `rg_bench.py`：9 条查询，每条用两种输出模式各跑两次。full 是 `rg -n --no-heading`（`路径:行号:内容`，即 Agent 实际读到的内容），files 是 `rg -l`（只有路径）。从两个仓库的共同父目录用相对路径搜索，加 `--no-config --color never`。记录行数、文件数、字符数、CJK 字符数和输出最多的文件。
- `contract_map.py`：契约锚点，分三类。① 提取 Go 的 `json:"..."` tag，生成 snake、camel、Pascal、kebab、SCREAMING 和 Go 缩写词形式（pascal_go、camel_go，如 `DeviceConfigID`）的变体，在前端 Vue/TS 里按整词计数，把每个 tag 归为 exact（前端有原名）、variant-only（只有变体）或 none（都没有）。② 提取 MQTT topic 字面量和 Subscribe/Publish 调用点，按规范化后的 topic 分组：`+ # %s {x} :x ${x}` 和结尾的 `/` 都换成 `*`。③ 提取两侧的 WebSocket endpoint 和消息字段。输出一行一项的 `contract_summary.txt` 和明细 `contract_map.json`；`--slice` 按名字切出相关的行。
- `shingle_index.py`：函数级相似代码索引。用正则加括号匹配切分函数：Go 的顶层 func 和方法；TS/JS 的 function 声明、const/let 箭头函数、对象和类方法、Vue hook（watch、computed、onMounted 等）回调；`.vue` 只取 `<script>` 块。分词后做 winnowing（k=5，窗口 4），分两种模式：raw 保留原样 token；norm 把标识符换成 I、字符串换成 S、数字换成 N，保留关键字和运算符。建倒排索引，按 Jaccard 和 containment（查询函数的指纹有多少出现在候选里）排序。`pairs` 子命令用 AllPairs（prefix filter 加 size filter）精确求出 Jaccard ≥ 阈值的函数对，再用 union-find 聚类。
- `scale_copy.py`：把指定扩展名的文件复制 N 份，用于放大实验。
- `repo_stats.py`：统计文件数和行数（未改动）。
- `run_external_tools.sh`、`run_external_followup.sh`：ast-grep 和 jscpd 的测量，给用户在自己的终端运行（auto 模式不允许 Claude 用 npx 下载）。
- `analyze_external.py`：把 ast-grep 的结果和正则计数逐文件对照，并统计 jscpd 报告。
- `compare_clones.py`：把 jscpd 的克隆和 shingle 的函数对对照。

**测试和生成代码。** 测试路径的正则是 `_test\.go$|/(?:test|tests|__tests__|testdata|e2e)/|\.(?:test|spec)\.[jt]sx?$`。生成代码指前 600 个字符内有 `Code generated` 的 Go 文件，以及 `.min.js`。

**命中质量。** 逐条读两侧源码判断，样本是：12 个多词 variant-only tag（`random.Random(0)` 抽样），5 个 shingle 查询的前 5 名，6 对只在 norm 模式出现的前端近似重复函数。

原始输出都在 `/tmp/cpf-measure/out/`，没有放进仓库。

## 结果：ripgrep（2.5k 文件）

查询对象是后端和前端之间的 payload 字段 `device_config_id` 及其各种写法，外加一个 MQTT topic、一个 WebSocket endpoint 和一个日期格式化正则。时间单位 ms，格式为"第一次运行/重复运行"，取自第一轮测量。

| 查询 | 模式 | full 耗时 | 行 | 文件 | 字符 | ≈token | `-l` 耗时 | `-l` 字符 | `-l` ≈token | 后端/前端行 |
|---|---|---|---|---|---|---|---|---|---|---|
| snake | `-F device_config_id` | 96.8/39.7 | 331 | 117 | 50,146 | 12,536 | 37.9/38.4 | 8,171 | 2,042 | 226/105 |
| camel | `-F deviceConfigId` | 38.2/38.6 | 138 | 24 | 18,876 | 4,719 | 39.0/38.4 | 1,640 | 410 | 81/57 |
| pascal | `-F DeviceConfigId` | 32.1/31.0 | 63 | 23 | 8,460 | 2,115 | 31.1/37.0 | 1,487 | 371 | 55/8 |
| pascal_go | `-F DeviceConfigID` | 36.0/32.3 | 435 | 116 | 65,514 | 16,378 | 33.3/37.2 | 7,885 | 1,971 | 435/0 |
| kebab | `-F device-config-id` | 51.4/87.5 | 5 | 5 | 693 | 173 | 34.0/32.4 | 358 | 89 | 0/5 |
| variants_re | `-i device[-_]?config[-_]?id` | 36.6/44.2 | 930 | 196 | 137,666 | 34,416 | 39.3/32.8 | 13,575 | 3,393 | 763/167 |
| mqtt_topic | `-F devices/telemetry/control` | 33.7/33.5 | 42 | 21 | 7,697 | 1,924 | 32.2/31.7 | 1,467 | 366 | 38/4 |
| ws_endpoint | `-F online/status/ws` | 31.4/33.0 | 15 | 13 | 1,967 | 491 | 31.5/35.9 | 831 | 207 | 10/5 |
| date_fmt_re | 正则：`dayjs(...)` 或 `moment(...)` 后接 `.format('YYYY-MM-DD HH:mm:ss')` | 33.8/35.5 | 34 | 21 | 5,610 | 1,402 | 37.3/37.9 | 1,738 | 434 | 0/34 |

观察：

- **耗时。** 单条查询 31-97 ms，大多在 32-40 ms，其中进程启动约 5-9 ms。表中 96.8 ms 和 87.5 ms 是偶发抖动，第二轮里同样的查询是 35-41 ms。9 条查询 × 2 种模式 × 2 次，第一轮共 1.41 s，第二轮 1.36 s。把所有写法合成一个正则（variants_re）和搜一个字面量一样快。只遍历不搜内容（`rg --files`，2414 个文件）30-40 ms；搜一个不存在的字符串 30-100 ms（含 bash 启动）。小仓库上 rg 的成本主要是进程启动。
- **输出量。** 同一个字段，只搜 snake 写法就有 12.5k token，所有写法合起来 34.4k token，远超 2k 的预算。`-l` 把输出压到 1/6 到 1/10（variants_re 为 3.4k token），仍然超预算，而且没了行内容，Agent 还得再去读文件。
- **写法分散在两侧。** Go 代码用 `DeviceConfigID`（435 行，全在后端）；JSON 和 SQL 用 `device_config_id`（后端 226 行、前端 105 行）；前端还有 `deviceConfigId`（57 行）和 `device-config-id`（5 行，全在前端）。只搜任何一种写法，都会漏掉另一侧的大部分。
- **噪声来源。** 输出最多的是文档和测试：snake 查询里排前面的是 `docs/demand-community/2025.11.11-主题转换.md` 和 `docs/A02-页面与操作路径对照-2026-10-24.md`，mqtt_topic 查询的前三名都是 `_test.go`。full 输出平均每行 149 字符（约 37 token），最长一行 759 字符。

## 契约锚点命中情况

`contract_map.py` 在 2.5k 文件上一次跑完三类锚点，读取 1206 个 Go 文件（8.75 M 字符）、17 个 YAML 和 671 个前端文件（3.74 M 字符）。总耗时 1.18 s（更早一次的第一次运行为 1.31 s），其中读文件 0.33 s、tag 0.50 s、topic 0.28 s、WebSocket 0.04 s、写出 0.03 s。

### JSON tag

共 1622 个不同的 tag（多词 1129 个），6684 处定义。81 个只出现在测试里，52 个只出现在生成代码里。

| 范围 | exact | variant-only | none |
|---|---|---|---|
| 全部 1622 | 858（52.9%） | 57（3.5%） | 707（43.6%） |
| 多词 1129 | 446（39.5%） | 51（4.5%） | 632（56.0%） |
| 单词 493 | 412（83.6%） | 6（1.2%） | 75（15.2%） |

单词 tag（如 `id`、`name`）在前端几乎都能按原名找到，但这种命中没有区分度。多词 tag 有 56% 在这个前端里完全找不到。57 个 variant-only tag 按匹配上的变体统计（一个 tag 可以匹配多种）：camel 42、camel_go 37、kebab 6、snake 6、pascal 4、pascal_go 5、SCREAMING 5。前端没有统一的大小写转换层，`camelcase`、`humps`、`transformResponse` 都是 0 处。

抽查 12 个多词 variant-only tag，读两侧代码后的结论：

- **真实关联且有偏差（疑似 bug），1 个：`last_visit_time`。** 后端 `internal/dal/users.go:247` 在 `GetUserByIdWithAddress` 返回的 map 里输出 `"last_visit_time"`，列表接口 `GetUserListByPageWithAddress`（319 行、409-416 行）的每一行也用它。前端 `src/views/management/user/index.vue:258-262` 读的却是 `row.lastVisitTime`，`src/typings/api.d.ts:437` 也声明为 `lastVisitTime`，而同一个类型里的 `created_at`、`updated_at` 都是 snake 写法。后端没有任何 `lastVisitTime`，所以 `dayjs(row.lastVisitTime || row.created_at)` 这一列实际显示的是创建时间。
- **同一概念的兄弟字段，4 个。** 前端出现的那个变体，其实是后端另一个结构体里的原名 tag：
  - `true_text`：前端 `src/service/api/thingmodel-native-transport.ts:10` 的 `trueText`，对应 Go `encore-api/thingmodel/transport.go:34` 的 `json:"trueText"`；snake 写法在 `thingmodel/core/types.go:97` 和 `devicemetadata/validation_types.go:55`。
  - `config_version`：前端 `notification-v2.types.d.ts:134` 的 `configVersion`，对应 `notification/contract/business.go:184`；snake 写法在 `plugin_v1.go:29`。
  - `minVersion`：前端 `market-template-list.vue:189` 和 `add-devices-step1.vue:133` 从 `missing_plugins` 读 `p.min_version`，对应 `internal/model/device_templates.http.go:182` 的 `json:"min_version"`（`missing_plugins` 在 230 行）；camel 写法在 `market_bundle.go:89`。
  - `published_at`：前端 `market-bundle.ts:63` 的 `publishedAt`，对应 `market_bundle.go:256`。
- **误报，7 个。** i18n key（`publish_topic`、`message_type`，在 `src/typings/app.d.ts:980`、`:954`）；前端本地算出来的值（`memory_usage`，`useGridPerformance.ts:33`）；CSS class（`item_id` 对应栅格布局 id 和 `.item-id`，`roleKey` 对应 `PublishWizard.vue:346` 的 `.role-key`）；JSON Schema 关键字（`max_items`，`notification-v2.ts:296`）；字典编码（`product_type` 对应 `irrigation.ts:138` 的 `'PRODUCT_TYPE'`，是相关的枚举，不是这个字段）。

合计 1 个直接关联（带 bug）、4 个兄弟字段、7 个误报。全部 57 个 variant-only tag 里有 22 个能找到这样的兄弟 tag，22 个都是多词 tag。6 个单词的 variant-only tag 是 `$env`、`_tp`、`attempts`、`cid`、`cpu`、`iss`。

### MQTT topic 和 WebSocket

- **topic 分组。** 共 262 组，其中 212 组只出现在测试里（全在 Go 测试）。739 处字面量位置里，519 处在测试文件。topic 根段从非测试代码的关键字行和 YAML 的 `*topic*` 键学到 5 个：attributes、command、devices、gateway、ota。50 个非测试组按出现的位置分：Go + 配置 + 前端 18 组，只在 Go 20 组，Go + 前端 6 组，Go + 配置 2 组，只在配置 4 组。
- **调用点。** 53 个 Subscribe/Publish 调用（10 个在测试里），其中 10 个的 topic 参数能就地解析到字面量，其余是变量或函数返回值。
- **近似拼写（near-miss）。** 规则是段数相同、只差一个非通配段、SequenceMatcher 相似度 ≥ 0.75，只在非测试组之间比较。唯一的命中是配置里的拼写错误：`ota/devices/infrom/*`（配置 3 处）对 `ota/devices/inform/*`（0.83）。把测试组也算进来时，这一条淹没在约 40 对测试夹具之间。
- **前缀链接。** 以 `/` 结尾、运行时再拼 id 的字面量，覆盖它下面更长的组，共 10 组。只在配置里出现的 4 组里，有 3 组靠它连到代码：`devices/attributes/response/*` → `.../*/*`，`devices/event/response/*` → `.../*/*`，以及 `gateway/command/*`。
- **WebSocket。** 4 个 endpoint，两侧都有。输出里带两侧的字段差异，例如批量设备状态的 endpoint，Go 侧字段是 `device_id, device_ids, device_status, is_online, token`，前端只发 `device_ids, token`。

### 摘要体积

| 段 | 行 | 字符 | ≈token |
|---|---|---|---|
| tags | 1622 | 75,287 | 18,821 |
| topics（非测试） | 50 | 12,190 | 3,047 |
| topics_test_only | 212 | 23,083 | 5,770 |
| mqtt_calls | 53 | 5,885 | 1,471 |
| ws | 4 | 1,333 | 333 |
| 合计 | 1941 | 117,778 | 29,444 |

去掉只在测试里出现的 topic 后是 94,695 字符，约 23.7k token。整份摘要放不进上下文，但按名字切出的切片很小：

| 切片 | 行 | 字符 | ≈token |
|---|---|---|---|
| `device_config_id` | 1 | 120 | 30 |
| `is_online` | 3 | 765 | 191 |
| `devices/telemetry/control` | 6 | 1,118 | 279 |

`device_config_id` 的切片只有一行：`tag device_config_id | go 42x/22f | fe =103x/29f | ~deviceConfigId 62x/12f, device-config-id 5x/5f, deviceConfigID 4x/2f`。它说明 Go 侧在 22 个文件里定义了 42 次，前端用原名引用 103 次（29 个文件），另有 3 种变体及其次数，但不给具体位置。要从 rg 得到这些计数，得先读完 34.4k token 的 full 输出。`is_online` 的切片包含上面那条 WebSocket 字段差异。

## shingle 索引

### 构建和查询耗时（2.5k 文件）

| 项 | 数值 |
|---|---|
| 输入 | 1858 个文件（后端 Go 1206、后端 JS 2、前端 JS/TS/Vue 650），11.4 M 字符 |
| 函数 | 15,476 个（后端 Go 10,913、后端 JS 1、前端 4,562），其中生成代码 3,499 个、测试 2,498 个；函数内 token 共 1.81 M |
| 构建（第一次 / 重复） | 2.13 / 2.76 s，8 进程，user 6.4-6.7 s。读取、切分、分词和 winnowing 1.31 / 2.08 s；建倒排 raw 0.15 / 0.21 s，norm 0.07 / 0.10 s；写 pickle 0.54 / 0.33 s |
| 峰值内存 | 约 214 MB |
| 索引文件 | 25.7 MB（pickle，含两种模式） |
| raw 指纹 | 604,270 个，不同值 322,780 个，平均每个函数 39.0 个，最长 posting list 2,567 |
| norm 指纹 | 452,242 个，不同值 21,354 个，平均每个函数 29.2 个，最长 posting list 6,204 |
| 查询 | 加载索引 0.14-0.17 s，整个查询进程 0.27-0.34 s。单次查询 raw 0.0-4.6 ms（候选 26-4,420 个），norm 1.2-17.4 ms（候选 1,497-13,766 个） |

norm 模式只有约 2.1 万种不同的指纹，同一个指纹会命中大量函数，所以候选数是 raw 的 3-100 倍，单次查询慢 4-50 倍。

### 查询结果和判断

Q1-Q3 是计划内的三类查询，Q4 和 Q5 是补充。每个查询取 Jaccard 排名前 5，排除查询函数自身和与它互相嵌套的函数，逐条读代码判断是不是真的相似实现。

**Q1 状态到等级的映射：`normalizeAlarmLevel`（`ThingsVisAppFrame.vue:1179-1187`，86 token）**

- raw：第 1 名是 `ThingsVisWidget.vue:674-682 normalizeAlarmLevel`，J=0.80，是真副本：函数体相同，只是一个写成 function 声明，一个写成箭头函数。第 2-5 名 J ≤ 0.04，都无关。
- norm：第 1 名同上，J=0.72。第 2-5 名是 `runs-drawer.vue` 和 `explain-drawer.vue` 的 `toneOf`（J=0.41）、`simulate-drawer.vue` 的 `decisionTone`（0.31）、同文件的 `isActiveAlarm`（0.30）。它们和查询函数一样是"值 → 标签"的 if 链，但映射的是别的概念，修告警等级时不需要改。
- 两种模式都没找到 `src/views/alarm/warning-message/components/new-information.vue:157` 的 `render`。它把 `alarm_level` 的 `H`/`M`/`L` 映射成文案，概念相同、写法不同，在 norm 模式的前 400 名里也没有出现。用 rg 搜 `alarm_level` 能直接找到它。
- 附带发现（没有验证下游显示）：后端校验只允许 `H`、`M`、`L` 三个等级（`encore-api/automation/domain/validate.go:443`），而两份 `normalizeAlarmLevel` 只识别 `1`/`2`/`3`、`critical`/`high`/`serious` 这类写法，`'H'` 会变成 `'h'` 原样返回。如果要修，两份都要改，这正是目标场景里"改了一处、漏了另一处"的形态。

**Q2 日期格式化：`formatDateTime`（`src/utils/common/datetime.ts:9-11`，31 token）**

- raw：第 4、5 名是真的同类实现：`time-series-data.vue:71` 的 `render: row => dayjs(row.x).format('YYYY-MM-DD HH:mm:ss')`（J=0.06）和 `associated-devices.vue:245-250` 的 `moment(row.ts).format(...)`（J=0.05）。但它们的分数和前 3 名的无关函数（`getThumbnailUrl` 0.15 等）在同一水平，没法用阈值区分。
- norm：0/5，命中的是 `isWhiteColor`、`getThumbnailUrl`、`getTooltipLines`、一个状态文案的 `render` 和 `isVersionConflict`。
- 原因：查询函数只有 12 个指纹，而同类实现多是 15-30 token 的单行箭头函数，外围不同的 token 占了大部分 k-gram。rg 的 date_fmt_re 在前端找到 34 行、21 个文件（约 1.4k token），全是这种内联格式化；它会漏掉 `new Date(x).toLocaleString()` 一类写法（约 10 处）和 `version-history-modal.vue:70` 的 `formatDate`。

**Q3 WebSocket 连接：`connectDeviceStatusWs`（`ThingsVisViewer.vue:170-254`，432 token）**

- raw：第 1-9 名都是 WebSocket 连接代码。前 5 名只对应 3 个外层函数：`ThingsVisAppFrame.vue:346-416` 的同名函数（J=0.75），两个文件各自的 `connectDeviceWs`（Viewer 0.67，AppFrame 0.46）；另外 2 名是嵌在它们里面的 `openWs`（都是 0.54）。第 6-9 名是 AppFrame 的另一个 `openWs`（0.35），以及 `src/hooks/thingsvis/useRealtimePush.ts` 的 `startStatusWebSocket`（0.15）、`useRealtimePush` 和 `startWebSocket`（都是 0.07）。第 10 名起无关。
- norm：第 1-9 名是同一批函数，分数更高（前 5 名 0.60-0.83，`startStatusWebSocket` 0.33），第 10 名起无关。
- 两种模式都漏了 `src/utils/deviceStatusWebSocket.ts:35-138` 的 `connect`（459 token）。它是类方法，连的是批量 endpoint `/device/online/status/ws/batch`，在 raw 排第 155 名（J=0.01），不在 norm 前 400 名里。`src/views/device/details/index.vue:191` 的 `wsUrl += '/device/online/status/ws'` 写在 `<script setup>` 顶层，不属于任何函数，索引里没有它。用 rg 搜 `status/ws`，前端 5 个文件各 1 行，正好是 AppFrame、Viewer、`deviceStatusWebSocket.ts`、`useRealtimePush.ts` 和 `details/index.vue`。
- 两个 `connectDeviceWs` 已经分叉：Viewer 版的参数是 `deviceId: string`，AppFrame 版是 `{ deviceId, fields }` 对象。

**Q4 后端 WebSocket handler：`ServeCurrentDataByWS`（`be/internal/api/telemetry_data.go:373-576`，1079 token）**

- raw：前 3 名是真的同类实现：同文件的 `ServeCurrentDataByKey`（J=0.81，C=0.93）和 `ServeDeviceStatusByWS`（0.42），以及 `device_status_ws.go:22-249` 的 `ServeDeviceOnlineStatusWS`（0.11）。第 4、5 名是 SSE 的 `HandleSystemEvents`（0.04）和 `UpdateDeviceStatus`（0.03），无关。
- norm：前 3 名相同（0.87、0.55、0.23），第 4、5 名是 `processDirectDeviceMessage` 和一个测试函数（都是 0.17），无关。
- 第 3 名只比噪声高一点（raw 0.11 对 0.04，norm 0.23 对 0.17），固定阈值很难既留下它又去掉噪声。

**Q5 补充：`actionValueChange`（`src/views/automation/linkage-edit/modules/edit-action.vue:350-367`，95 token）**

- 两种模式的第 1 名都是 `scene-edit/index.vue:311-333` 的同名函数（raw J=0.71、C=0.96；norm J=0.90、C=1.00），第 2 名只有 0.06（raw）和 0.22（norm）。
- 这一对已经分叉：scene-edit 版对 `command`、`c_attribute`、`c_telemetry`、`c_command` 四种 `action_param_type` 都做 JSON 校验，linkage-edit 版只校验 `command`。linkage-edit 也用另外 3 种类型：`edit-action.vue:321-329` 给它们的输入提示都是 JSON 示例，`linkage-edit/index.vue:247-255` 的注释也写明它们的值是 JSON。这很可能是改了一份、漏了另一份。没有运行前端验证。

**小结。** 有副本的函数（Q1、Q5）第 1 名就是副本，而且和第 2 名分差很大（raw 0.80 对 0.04，0.71 对 0.06）。长函数（Q3、Q4）的前几名都是同类实现，但 Q3 前 5 名里有 2 个是嵌套函数，挤占了名额。短函数（Q2）的真命中和噪声分数相同。写法不同的同类实现（Q1 的 `render`、Q3 的类方法 `connect`）两种模式都找不到，按字段名或 endpoint 用 rg 搜能找到。norm 模式让真副本的分数更高，也把形状相同、概念不同的函数排了上来（Q1 第 2-5 名）。

### 近似重复函数对（J ≥ 0.8）

`pairs` 子命令在所有至少 50 token 的函数里（后端 6,591 个，前端 1,715 个）找 Jaccard ≥ 0.8 的函数对，排除互相嵌套的函数。结果里没有跨前后端的函数对。整个进程第一次运行 1.45 s、重复运行 1.26 s，峰值内存约 236 MB；其中求函数对 raw 0.38 s，norm 0.45 s。

下表"全部"一列是所有函数对；其余各列只统计两个函数都不是生成代码或测试的函数对，下称"干净"的函数对。

| 模式 | 范围 | 全部 | 干净 | 干净且 J=1.0 | 干净且跨文件 | 簇 | 簇内函数 | 最大簇 |
|---|---|---|---|---|---|---|---|---|
| raw | 后端 | 710 | 78 | 4 | 32 | 41 | 97 | 10 |
| raw | 前端 | 99 | 84 | 67 | 75 | 46 | 106 | 6 |
| norm | 后端 | 75,812 | 4,277 | 1,430 | 3,149 | 225 | 896 | 149 |
| norm | 前端 | 221 | 191 | 132 | 114 | 90 | 216 | 8 |

- **raw 找到的基本是真副本。** 后端：`encore-api/automation/store/alarm_store.go` 和 `encore-api/northbound/deliveries.go` 各有一份相同的 `itoa`；`internal/service` 的 `telemetry_data.go`、`attribute_data.go`、`command_data.go` 各有一份 `findTopLevelGateway`（后两份名字带 ForAttribute、ForCommand，J=0.97-0.98）；`internal/uplink` 的 attribute、event、telemetry 三个文件各有一份 `refreshHeartbeat`，`processSubGateways` 和 `processSubDevices` 也成对出现；`cli/tpctl-go` 和 `cli/tpctl-mcp` 的 `newClient` 相同。前端：`card-form-with-selector.vue` 和 `card-form.vue` 的 `updateDisabledOptions`（J=1.00），AppFrame 和 Viewer 的 `disconnectAllDeviceWs`（1.00），以及 `add-edit-commands.vue`、`add-edit-events.vue`、`model-definition.vue` 里相同的表格列 `render`。
- **后端的函数对大多来自生成代码和测试。** raw 的 710 对里只有 78 对是干净的，norm 的 75,812 对里只有 4,277 对。
- **norm 在后端被样板代码淹没。** 最大的簇有 149 个函数，全在 `be/internal/api`，65-118 token（中位数 84），都是 gin handler 的"绑定参数、调用 service、写回结果"三段，例如 `internal/api/logo.go:14` 的 `UpdateLogo`。第 2、3 大的簇各有 27 个函数，分别是 `be/internal/api` 的 handler 和 `be/internal/service` 的分页列表函数。这些函数只是形状相同，业务各不相同。
- **norm 在前端多找到一些真副本**，例如 AppFrame 和 Viewer 的 `extractWsFields`（norm 1.00，raw 0.74）。

**只在 norm 里达到 0.8 的前端函数对。** 干净且跨文件的前端函数对，raw 有 75 对，norm 有 114 对，其中 43 对只在 norm 里达到 0.8（反过来只在 raw 里达到的有 4 对）。用 `random.Random(0)` 从 43 对里抽 6 对，逐对读代码：

| 函数对 | J（norm / raw） | 判断 |
|---|---|---|
| `actionValueChange`：`linkage-edit/modules/edit-action.vue` / `scene-edit/index.vue`（即 Q5） | 0.90 / 0.71 | 真副本，已分叉 |
| `password`：`personal-center/components/change-information copy.vue` / `change-information.vue`（都是 91-111 行） | 1.00 / 0.79 | 真副本，文件名就叫 copy |
| `handleCopy`：`rule-engine/components/secret-key-modal.vue:36-47` / `plugin/copy/index.vue:9-20` | 1.00 / 0.43 | 真副本，已分叉：复制的来源不同（`props.secretKey` 对 `source.value`），前者的成功提示还少了 `copySuccess` 文案 |
| `viewerPlatformDevices`：`device/details/modules/telemetry-chart.vue:190-199` / `device-details-app/index.vue:39-48` | 0.87 / 0.32 | 真副本，改了变量名（`props.id` 对 `d_id.value`） |
| `render`：`data-service/rule-engine/index.vue:125-146` / `device/template/components/step/custom-commands.vue:154-173` | 0.85 / 0.69 | 结构样板：编辑、删除按钮列 |
| `createDefaultFormModel`：两个 `table-action-modal.vue`（`data-service/rule-engine` 和 `apply/service`） | 0.90 / 0.06 | 误报：形状相同，字段不同 |

6 对里有 4 对真副本、1 对样板、1 对误报。4 对真副本里有 2 对已经分叉，正是"改了一处、漏了另一处"的形态。把真副本的一侧当查询，另一侧在两种模式下都排第 1 名。raw 的第 1、2 名分数分别是：`password` 0.79 对 0.50（第 2 名是 `personal-center/index copy.vue` 的 `submitPass`，也是改密码的代码），`handleCopy` 0.43 对 0.09，`viewerPlatformDevices` 0.32 对 0.18，`actionValueChange` 0.71 对 0.06。固定的 raw 阈值 J ≥ 0.8 会把这 4 对全部漏掉。

## 扩展到 10 万文件

### 做法

`scale_copy.py` 把两个仓库里属于上述 10 种扩展名的源文件各复制 43 份，放到 `/tmp/cpf-measure/scaled/<仓库名>-NN/`。每份后端 1,522 个文件、前端 788 个，合计 99,330 个文件、724,063,541 字节（691 MiB，`du` 显示 916 MB），复制用了 18.8 s。复制时跳过 `.git` 和 `node_modules`，其他隐藏目录照常复制（不在隐藏目录里的文件有 97,524 个）；`.gitignore` 以及 `.tsx`、`.jsx`、`.mjs`、`.cjs` 文件没有复制。

43 份内容完全相同，所以命中数正好是 43 倍，命中质量没有参考价值，这里只看耗时、输出体积和内存。真实的 10 万文件仓库里不同的内容更多，索引会比这里大。所有运行都在刚写入的热缓存上。

### ripgrep

时间单位 ms，格式为"第一次运行/重复运行"，共两轮。

| 查询 | full 第一轮 | full 第二轮 | 行 | 文件 | 字符 | ≈token | `-l` 第一轮 | `-l` 第二轮 | `-l` 字符 | `-l` ≈token |
|---|---|---|---|---|---|---|---|---|---|---|
| snake | 2946/2171 | 2190/2192 | 14,233 | 5,031 | 2,198,977 | 549,744 | 2337/2535 | 2085/2281 | 366,446 | 91,611 |
| variants_re | 2348/2065 | 2394/3904 | 39,990 | 8,428 | 6,039,608 | 1,509,902 | 3014/2756 | 3185/2946 | 609,009 | 152,252 |
| date_fmt_re | 2259/2121 | 2270/2419 | 1,419 | 860 | 239,424 | 59,856 | 2233/2096 | 2202/2323 | 74,218 | 18,554 |

- 单条查询 2.1-3.9 s，大多在 2.1-2.5 s，约是 2.5k 文件时的 60 倍，而文件数约是 40 倍。两轮分别用了 29.0 s 和 30.5 s。
- 行数和文件数正好是 43 倍。date_fmt_re 每份 33 行而不是 34 行，因为原仓库有 1 处命中在没有复制的 `.tsx` 文件里。字符数略多于 43 倍，因为路径里多了副本编号。
- 只搜一个字段的 snake 写法，full 输出就有 55 万 token；所有写法合起来 151 万 token；`-l` 也有 9-15 万 token。

**耗时花在哪里。** 在放大后的目录里用 `/usr/bin/time -p bash -c "rg ... > /dev/null < /dev/null"` 把几条命令各跑两次（含 bash 启动）：

| 命令 | real（s） | user（s） | sys（s） |
|---|---|---|---|
| `rg --files`（只遍历，不读内容） | 0.28-0.34 | 0.17-0.18 | 1.5-1.6 |
| `rg -l -F device_config_id .` | 2.68-3.54 | 0.36-0.37 | 7.0-7.1 |
| `rg -c -F zzzqqqxxyy .`（搜不存在的字符串） | 2.03-2.25 | 0.35-0.37 | 8.0-8.5 |
| `rg -l -F -j 4 device_config_id .` | 3.30-3.85 | 0.27-0.32 | 5.0-5.9 |
| `rg -l -F --mmap device_config_id .` | 3.23-3.67 | 0.38-0.40 | 7.4 |
| `rg -l -F --no-mmap device_config_id .` | 2.48-3.61 | 0.37-0.39 | 7.2 |

user 时间只有 0.3-0.4 s，sys 时间是 5-8.5 s（各线程合计），耗时主要在内核里打开和读取 9.9 万个文件，匹配本身很便宜。搜不存在的字符串（2.0-2.3 s）只比真实查询快一点，减少线程或切换 mmap 都没有变快。同样的不命中扫描在原始两个仓库上是 0.03-0.10 s。sys 时间为什么这么高，没有继续查。

### 契约锚点

| 项 | 2.5k 文件 | 10 万文件 |
|---|---|---|
| 读取 | Go 1,206 个文件 / 8.75 M 字符，YAML 17，前端 671 / 3.74 M | Go 51,858 / 376 M，YAML 731，前端 28,724 / 160 M |
| 耗时（第一次 / 重复） | 1.18 s（更早一次第一次运行为 1.31 s） | 50.7 / 52.7 s（墙钟 50.95 / 52.87 s，user 35.2 s） |
| 分项（第一次） | 读文件 0.33、tag 0.50、topic 0.28、WebSocket 0.04 s | 读文件 15.4、tag 22.1、topic 11.3、WebSocket 1.8 s |
| 峰值内存 | 没有记录 | RSS 1.08 GB |
| 摘要 | 1,941 行，117,778 字符，约 29.4k token | 4,167 行，383,048 字符，约 95.8k token |

| 段 | 2.5k 文件：行 / 字符 | 10 万文件：行 / 字符 / ≈token |
|---|---|---|
| tags | 1,622 / 75,287 | 1,622 / 83,581 / 20,895 |
| topics（非测试） | 50 / 12,190 | 50 / 13,248 / 3,312 |
| topics_test_only | 212 / 23,083 | 212 / 31,724 / 7,931 |
| mqtt_calls | 53 / 5,885 | 2,279 / 253,055 / 63,263 |
| ws | 4 / 1,333 | 4 / 1,440 / 360 |

- tag 和 topic 是每个名字一行，行数不变，只是行里的计数变大，字符数增加 8-37%。mqtt_calls 是每个调用点一行，跟着变成 43 倍，占了摘要的三分之二。要让摘要的体积不随仓库增长，调用点得按 topic 聚合成计数。
- 切片仍然很小：`device_config_id` 1 行 136 字符（`go 1806x/946f | fe =4429x/1247f | ...`），`is_online` 3 行 833 字符。`devices/telemetry/control` 是 48 行 5,816 字符（约 1.5k token），其中 5 行是 topic，另外 43 行是同一个调用点的 43 份副本，原因同上。
- 去掉只在测试里的 topic 后是 351,324 字符（约 87.8k token）。

### shingle 索引

| 项 | 2.5k 文件 | 10 万文件 |
|---|---|---|
| 输入 | 1,858 个文件，11.4 M 字符 | 79,722 个文件，490 M 字符 |
| 函数 | 15,476 | 664,092 |
| 构建（第一次 / 重复） | 2.13 / 2.76 s | 52.4 / 48.6 s（墙钟 53.0 / 49.6 s，user 196 / 194 s） |
| 峰值内存 | 约 214 MB | 1.82 GB（RSS 1.36 GB） |
| 索引文件 | 25.7 MB | 598 MB |
| raw 指纹：总数 / 不同值 / 最长 posting list | 604,270 / 322,780 / 2,567 | 25.96 M / 322,613 / 110,381 |
| norm 指纹：总数 / 不同值 / 最长 posting list | 452,242 / 21,354 / 6,204 | 19.43 M / 21,337 / 266,514 |
| 加载索引 | 0.14-0.17 s | 1.01 s |
| 查询 `connectDeviceStatusWs`：raw / norm | 1.1/0.9 ms / 17.4/15.9 ms（候选 895 / 13,766） | 65/78 ms / 1,311/1,457 ms（候选 38,569 / 591,549） |
| 查询 `normalizeAlarmLevel`：raw / norm | 0.1/0.0 ms / 4.3/3.8 ms（候选 38 / 3,919） | 2.4/1.6 ms / 286/235 ms（候选 1,718 / 168,558） |
| 整个查询进程 | 0.27-0.34 s | 4.81 s，RSS 980 MB，峰值 1.59 GB |

- 函数数是 43 倍，构建时间是 18-25 倍（user 时间约 30 倍），原仓库上的固定开销占比更高。主要耗时在读取、切分、分词和 winnowing（39.7 s）。
- 索引文件只有 23 倍，因为副本没有带来新的指纹值，不同值的个数几乎不变，变大的只是 posting list。真实仓库的内容各不相同，索引会更接近线性增长。
- 候选数随函数数增长（约 43 倍），norm 查询变成 0.2-1.5 s。整个查询进程的 4.81 s 里跑了 2 个查询，每种模式各跑两次；按各项相加估算，单独启动一个进程做一次查询约需 2.5-3 s，其中约 1 s 是加载索引。
- 放大后的查询结果全是 43 份副本互相命中（J=1.00），没有判断质量。

测完后按主会话的要求删除了 `/tmp/cpf-measure/scaled`（约 916 MB）。放大后的索引 `/tmp/cpf-measure/out/shingle_scaled.pkl`（598 MB）也是本次生成、可以重建的，一并删除了，这一项不在主会话点名的范围里。其余输出保留在 `/tmp/cpf-measure/out/`。

## ast-grep 与 jscpd

### 运行方式

Claude Code 的 auto 模式不允许 Claude 用 npx 下载软件包，所以这两个工具由用户在自己的终端里运行 `measurements/run_external_tools.sh`，时间是 14:03-14:04。版本是 ast-grep 0.51.0 和 jscpd 5.4.2，npm 缓存在 `/tmp/cpf-npm`。这段时间里测量子代理只在编辑 `shingle_index.py`，没有跑计算。每条命令只跑了一次，用 `/usr/bin/time -l` 记墙钟时间和峰值内存，结果在 `/tmp/cpf-measure/external/results.jsonl`。补测脚本 `run_external_followup.sh` 在 15:59-16:00 运行，版本相同，那时测量子代理已经结束，结果在 `/tmp/cpf-measure/external/followup/`。

启动开销：经 `npx -y` 第一次调用（含下载）两个工具各 3.65 s，已缓存后 1.14 s，直接运行解析出的二进制 0.45 s。ast-grep 在原始仓库上的查询本身只要 0.04-0.35 s，经 npx 调用时启动开销比查询还大，所以脚本应先解析出二进制路径，再反复调用。

### ast-grep：和正则计数对照

正则计数用 Python 在同样的文件里统计（`analyze_external.py`），注释和字符串里的调用也会算进去。

| 模式 | 范围 | ast-grep：处 / 文件 | 正则：处 / 文件 | 耗时 | 说明 |
|---|---|---|---|---|---|
| `json.Unmarshal($A, $B)` | 后端 .go | 667 / 255 | 668 / 255 | 0.26 s | 差的 1 处是注释掉的代码（`internal/dal/device_config.go:312`），ast-grep 是对的 |
| `$A.Subscribe($$$B)` | 后端 .go | 0 | 20 / 14 | 0.35 s | 静默漏报 |
| `$A.Publish($$$B)` | 后端 .go | 0 | 51 / 24 | 0.29 s | 静默漏报 |
| `watch($$$A)` | 前端 src 的 .ts | 15 / 11 | 15 / 11 | 0.05 s | 一致 |
| `$A.get($$$B)` | 前端 src 的 .ts | 131 / 50 | 132 / 51 | 0.04 s | 差的 1 处在注释里（`store/modules/tab/index.ts:60`） |

峰值内存 13-16 MB。两条 Go 方法调用模式返回 0 时，退出码是 1，和"没有匹配"相同，stderr 也是空的，从输出上看不出出了问题。ast-grep 的 Go 规则目录说明，单独写的 `f(x)` 形式的模式会被 tree-sitter 优先解析成类型转换，而不是函数调用，建议加上下文，再用 `selector: call_expression` 限定。`json.Unmarshal($A, $B)` 有两个参数，不可能是类型转换，所以结果正常。`$A.Subscribe($$$B)` 在模式里只有一个多节点元变量作参数，可能也被当成了类型转换。补测里按目录的建议加上下文和 `--selector call_expression` 后，两条都和正则逐行一致，见下文"补测：ast-grep 的 Go 方法调用"。

### ast-grep：.vue 文件

前端 src 有 337 个 .vue 文件，共 337 个 `<script>` 块：`lang="ts"` 275 个（274 个带 setup），`lang="tsx"` 61 个，其余 1 个是 JavaScript。用正则统计，这些文件里有 152 处 `watch(` 调用。

| 配置 | `--lang` | 命中 | 耗时 |
|---|---|---|---|
| 默认，加 `--globs '*.vue'` | ts | 0 | 0.01 s |
| `sgconfig.yml` 写 `languageGlobs: {html: ["*.vue"]}`，用 `-c` 指定或在配置目录里运行 | ts | 131：.vue 116，.ts 15 | 0.10-0.11 s |
| 同上 | js | 0 | 0.06 s |

默认配置下 `--lang ts` 不搜 .vue 文件，加 `--globs '*.vue'` 也不行。映射到 html 以后，ast-grep 能搜 `lang="ts"` 块里的 TypeScript，116 处全部和正则的结果对得上；漏掉的 36 处（24%）全部在 `lang="tsx"` 块里。用 `-c` 指定配置和在配置目录里运行，结果完全相同。补测里用 `--lang tsx` 再搜一次，正好补上这 36 处，见下文。

### ast-grep：放大到 10 万文件

`run_external_tools.sh` 把两个仓库的 .go、.ts、.js、.vue 文件（1,876 个）复制 54 份，共 101,304 个文件，测完即删除。这份副本和上文 `scale_copy.py` 的不是同一个，扩展名更少，份数也不同。其中 .go 文件 65,124 个、1,364 万行，.ts 文件 17,442 个、240 万行。

| 模式 | 耗时 | user / sys | 峰值内存 | 命中 | JSON 输出 |
|---|---|---|---|---|---|
| Go `$A.Subscribe($$$B)` | 14.27 s | 66.1 / 5.9 s | 19 MB | 0（模式的问题，同上） | 3 字节 |
| TS `watch($$$A)`，不含 .vue | 2.56 s | 8.6 / 2.2 s | 15.5 MB | 810，正好是 15 × 54 | 1.27 MB |

- 两条查询的速度几乎相同，都是每秒约 95 万行。ast-grep 没有索引，每条查询都要解析这种语言的全部文件，所以耗时取决于这种语言的总行数，和命中多少无关。Go 那条虽然 0 命中，也解析了全部 Go 文件。
- `--json=compact` 每处匹配 751-1,566 字节，带匹配的全文、所在的行、元变量和偏移。810 处就是 1.27 MB，约 32 万 token。只留 `文件:行号` 是每处约 112 字节（这份副本用的是较长的绝对路径）。JSON 里的行号从 0 开始。

### jscpd：默认模式

jscpd 5 默认只报 token 完全相同的克隆（exact），最少 50 个 token、5 行。前端扫 src 下的 `**/*.{ts,js,vue}`，后端扫 `**/*.go`。

| 项 | 前端 src | 后端 |
|---|---|---|
| 扫描 | 1,225 个 source（.vue 的块和整个文件分别计数），183,608 行 | 1,168 个文件，252,351 行 |
| 耗时（两次运行）/ 峰值内存 | 0.98、0.25 s / 147-148 MB | 0.34、0.40 s / 352-355 MB |
| 克隆（全是 exact） | 466 处，重复 7,867 行（4.3%） | 1,336 处，重复 14,360 行（5.7%） |
| 克隆行数：最小 / 中位 / p90 / 最大 | 6 / 15 / 35 / 104 | 6 / 9 / 16 / 82 |
| 同文件 / 同目录的不同文件 / 跨目录 | 65 / 138 / 263 | 588 / 654 / 94 |
| 有克隆的文件；与它有克隆的文件数：中位 / p90 / 最大 | 184；2 / 6 / 13 | 474；1 / 4 / 66 |
| 两侧都是生成代码 | 0 | 350 处（26%）；有克隆的生成文件 80 个，其中 67 个在 `internal/query`（gorm.io/gen 生成） |
| 报告 | JSON 655 KB；每处克隆压成一行是 49 KB，约 1.2 万 token | 1.67 MB；131 KB，约 3.3 万 token |

jscpd 把 .vue 文件里的每个块按 lang 算进对应的 format。扫描模式不含 .tsx 文件，所以 tsx format 的 57 个 source 全部来自 .vue 的 `lang="tsx"` 块：61 个 tsx 块里有 57 个至少 50 个 token。typescript 的 459 个 source 也和同样估算的 460 个对得上，看来 jscpd 不计太小、不可能含克隆的 source。整个 .vue 文件另算一个 vue source，共 299 个，0 处克隆；比 337 个 .vue 文件少的原因没有查。.vue 里报出的行号是整个文件的行号：检查了前 200 处 .vue 克隆，片段的第一行都在报出的起始行上。

### jscpd 和 shingle 函数对的对照

`compare_clones.py` 拿上文 `pairs` 找出的干净、跨文件的函数对（J ≥ 0.8），逐对查 jscpd 报告。一处克隆同时和两个函数的行范围重叠，算"直接检出"。jscpd 不一定把多份副本两两列出：后端有 3 份 `findTopLevelGateway`，jscpd 只报了 attribute 对 command、attribute 对 telemetry，没有 command 对 telemetry。所以另算"连通"：两个函数各自重叠的克隆片段，能经由同一处克隆、或同一文件里互相重叠的片段连到一起。

| 函数对 | 对数 | 直接检出 | 覆盖过半 | 连通 |
|---|---|---|---|---|
| 前端 raw | 75 | 50 | 50 | 62 |
| 前端 norm | 113 | 70 | 61 | 89 |
| 前端只在 norm 达到 0.8 | 42 | 23 | 14 | 30 |
| 后端 raw | 32 | 28 | 28 | 32 |
| 后端 norm（3,149 对里 `pairs` 列出的前 1,000 对） | 1,000 | 35 | 35 | 51 |

"覆盖过半"指两侧函数都有一半以上的行落在直接检出的克隆里。前端 norm 的两行各有 1 对含 jscpd 没扫的 .tsx 文件，没有计入。

前端 raw 没有连通的 13 对，原因都能对上：

- **6 对跨 `lang="ts"` 和 `lang="tsx"`。** 它们是 `personal-center` 的 `validator`（3 对）和 `submitPass`，以及 `manage` 下几个 drawer 的 `handleUpdateModelWhenEdit`（2 对）。jscpd 的文档说，默认每种 format 在各自的池里比较，加 `--cross-formats js-ts` 才会把 javascript、jsx、typescript、tsx 放进同一个池。同 format 的 69 对里有 62 对连通，跨这条边界的 6 对一对也没有。补测加上 `--cross-formats js-ts` 后，这 6 对全部连上。
- **6 对是只差缩进的 JSX。** 它们是 `device/template/components/step` 下三个文件里相同的表格操作列 `render`（19 行）。tsx 里含 JSX 的函数对，缩进也相同的 7 对全部连通，只差缩进的 6 对全部没有。可能是 JSX 标签之间的换行和缩进被当成了文本 token，没有核实。补测里 `--similarity` 按语法树比较，连上了这 6 对，和这个解释一致。
- **1 对太短。** 4 行的 `isActiveAlarm` 低于默认的 5 行下限。

上文逐条读过的 8 对前端函数：

| 函数对 | 上文的判断 | 覆盖比例 | 连通 |
|---|---|---|---|
| `normalizeAlarmLevel` | 真副本 | 1.00 | 是 |
| `actionValueChange` | 真副本，已分叉 | 0.87 | 是 |
| `password`（`change-information copy.vue`） | 真副本 | 1.00 | 是 |
| `handleCopy` | 真副本，已分叉 | 0 | 否 |
| `viewerPlatformDevices` | 真副本，改了变量名 | 0 | 否 |
| `connectDeviceStatusWs` | 同类实现（Q3 第 1 名） | 0.36 | 是 |
| `render`（rule-engine / custom-commands） | 结构样板 | 0.50 | 是 |
| `createDefaultFormModel` | 误报 | 0 | 否 |

覆盖比例取两侧函数里较小的一个。后端 raw 的 32 对全部连通。后端 norm 的函数对大多是 gin handler 一类的样板，jscpd 只连通了其中 51 对：形状相同、业务不同的函数，它不会报成克隆。

### 补测：ast-grep 的 Go 方法调用

| 写法 | Subscribe（正则 20 处） | Publish（正则 51 处） | 耗时 |
|---|---|---|---|
| `$A.M($$$B)`（第一次测量） | 0 | 0 | 0.29-0.35 s |
| 写死参数个数：`$A.Subscribe($B, $C, $D)`、`$A.Publish($B, $C, $D, $E)` | 18 | 30 | 0.21-0.25 s |
| 加上下文：`func t() { $A.M($$$B) }`，再加 `--selector call_expression` | 20 | 51 | 0.23-0.26 s |
| YAML 规则：`kind: call_expression`，`function` 字段匹配正则 `\.Subscribe$` | 20 | 没测 | 0.34 s |

- 加上下文和 YAML 规则两种写法，找到的位置和正则逐行相同，不多也不少。
- 写死参数个数只能找到参数个数相同的调用。Subscribe 漏的 2 处是 `global.REDIS.Subscribe(ctx, channel)` 这类两个参数的 Redis 调用。Publish 漏的 21 处是事件总线（`a.bus`，8 处）、业务 service（7 处）、Redis（3 处）等其他类型的同名方法，其中 8 处在测试里。这相当于按函数签名过滤（paho MQTT 的 `Publish(topic, qos, retained, payload)` 正好 4 个参数），适合已知签名时用，不适合找全同名调用。
- `--debug-query=ast` 打印的解析树里，四种写法都是 `type_conversion_expression` 加 ERROR 节点，`$` 本身是 ERROR，能匹配 667 处的 `json.Unmarshal($A, $B)` 和加了上下文的写法也一样。这份输出区分不了能匹配和不能匹配的写法，没能用它确认原因。

### 补测：ast-grep 与 .vue 的 tsx 块

| 配置 | `--lang ts` | `--lang tsx` |
|---|---|---|
| 只用 `languageGlobs` 把 `*.vue` 映射到 html（内置注入） | 131：.vue 116，.ts 15 | 36，全在 .vue |
| 再加一条自定义 `languageInjections`，把 `lang="tsx"` 的块注入成 tsx | 131 | 72：36 处各报 2 次 |

- 只用内置注入，`--lang ts` 和 `--lang tsx` 各跑一次，.vue 里找到 116 + 36 = 152 处，和正则找到的位置完全相同。内置注入本来就按 `lang` 区分 ts 和 tsx 块，只是一次只搜一种语言。
- 自定义注入规则是多余的，还让 tsx 块里的每处匹配报了两次。
- 每次 0.08-0.11 s，峰值内存 18-20 MB。

### 补测：jscpd 各模式

"连通"的定义同上。前端看 raw 函数对（75 对）和 norm 函数对（113 对）。后端的 32 对 raw 函数对在所有模式下都全部连通，表里只列 norm 的前 1,000 对。"一行约 token"是把每处克隆压成一行后的体积。

| 模式 | 前端克隆 | 前端 raw 连通 | 前端 norm 连通 | 后端克隆 | 后端 norm 连通 | 一行约 token（前端 / 后端） | 耗时（前端 / 后端） |
|---|---|---|---|---|---|---|---|
| 默认 | 466 | 62 | 89 | 1,336 | 51 | 12.4k / 32.7k | 0.25 / 0.40 s |
| `--max-gap-lines 3` | 422 | 62 | 89 | 1,214 | 51 | 11.2k / 29.8k | 0.26 / 0.41 s |
| `--ignore-identifiers --ignore-literals`（改名） | 1,569 | 62 | 98 | 5,157 | 761 | 38.8k / 121.6k | 0.24 / 0.57 s |
| 改名加 `--max-gap-lines 3` | 1,455 | 62 | 98 | 4,821 | 761 | 35.8k / 113.5k | 0.25 / 0.54 s |
| `--cross-formats js-ts` | 455 | 68 | 94 | 没测 | 没测 | 12.0k / - | 0.19 s / - |
| 跨 format 加改名 | 1,486 | 68 | 105 | 没测 | 没测 | 37.9k / - | 0.24 s / - |
| `--similarity=0.8` | 582 | 74 | 107 | 2,757 | 372 | 15.3k / 64.2k | 0.35 / 0.92 s |

峰值内存前端 140-175 MB，后端 352-390 MB。

- **`--similarity=0.8` 在前端效果最好。** 它在 466 处 exact 之外多报了 116 处 similar（按函数的语法树比较）。raw 函数对多连上 12 对，正是默认模式漏的两类：6 对只差缩进的 JSX `render`，6 对跨 ts/tsx 块的（没加 `--cross-formats` 也连上了）。逐条读过的 `handleCopy`（已分叉）也连上了，相似度 0.821。还漏的 1 对是 4 行的 `isActiveAlarm`。
- **在后端，`--similarity` 多出的记录大多是生成代码。** 1,421 处 similar 里有 1,032 处（73%）两侧都是生成代码，其余 389 处两侧都不是，其中 222 处跨文件。
- **改名模式只增加噪声。** raw 函数对一对也没有多连上，克隆数却是默认的 3.4 倍（前端）和 3.9 倍（后端）。后端 norm 函数对的连通数从 51 涨到 761，基本是 gin handler 一类的样板。逐条判过的误报 `createDefaultFormModel` 只在改名模式下被连上。
- **`--max-gap-lines 3`** 只把相邻的克隆合并成一处（前端 466 → 422），没有多连上函数对。
- **`--cross-formats js-ts`** 补上了跨 ts/tsx 块的 6 对。
- **`viewerPlatformDevices` 所有模式都没连上。** 两份各 10 行，一份在 tsx 块、一份在 ts 块，变量改了名（`props.id` 对 `d_id.value`），一份还多了 `|| device_number.value`。shingle 的 norm 模式给它 J=0.87，排第 1。

这次对照只查了 shingle 找到的函数对 jscpd 能不能找到，没有反过来查。jscpd 也报了 shingle 看不到的克隆：默认模式前端 466 处里有 148 处（32%）在 template（html 53 处）和 style（scss 81 处、css 14 处）里，shingle 只索引 script。

### 小结

1. ast-grep 在模式按预期解析时比正则准，不会算进注释里的调用。Go 里 `$A.M($$$B)` 这种写法会静默返回 0，退出码和"没有匹配"一样；改用加上下文和 `--selector call_expression` 的写法后，和正则逐行一致。
2. Vue SFC 要按 script 的 lang 分别处理。ast-grep 用内置注入，`--lang ts` 和 `--lang tsx` 各跑一次就能找全（152/152）。jscpd 默认不比较 ts 和 tsx 块，加 `--cross-formats js-ts` 或 `--similarity` 后能连上。
3. jscpd 各模式都在 1 s 以内。`--similarity=0.8` 在前端连通 74/75 个 raw 函数对，还连上了已分叉的 `handleCopy`，但在后端多出的记录 73% 是生成代码之间的。改名模式只增加噪声。改了名又改了内容的短函数（`viewerPlatformDevices`）各模式都找不到，shingle norm 能找到。反过来，template 和 style 里的克隆只有 jscpd 能找到。
4. jscpd 报告不能整份放进上下文，每处克隆压成一行，按模式不同有 1.1 万到 12 万 token。按文件查就很小：有克隆的文件，与它有克隆的文件数中位是 1-3 个。
5. 10 万文件时 ast-grep 每条查询 2.6-14.3 s，取决于这种语言的总行数。JSON 每处 0.75-1.6 KB，要先压成 `文件:行号`。

## 对分档设计的启示

### 2k token 能放下多少

按 2k token ≈ 8,000 字符估算：

| 输出 | 每行平均字符 | 2k token 约能放 |
|---|---|---|
| rg full 行（`路径:行号:内容`） | 148.8 | 54 行 |
| rg `-l` 路径 | 69.3（各查询 64-83） | 115 个文件 |
| 契约摘要，全部段平均 | 60.7 | 132 行 |
| 其中 tag 行 | 46.4 | 172 行 |
| 其中非测试 topic 行 | 244 | 33 行 |
| 其中 MQTT 调用点行 | 111 | 72 行 |
| 其中 WebSocket 行 | 333 | 24 行 |
| shingle 查询的命中行 | 约 97 | 83 行 |

`device_config_id` 的所有写法在 2.5k 文件上有 930 行、196 个文件，54 行只是其中 6%。

### 典型耗时

| 操作 | 2.5k 文件 | 10 万文件 |
|---|---|---|
| rg 单条查询 | 30-40 ms | 2-4 s（只遍历 0.3 s） |
| contract_map 全量 | 约 1.2 s | 51-53 s，RSS 1.1 GB |
| shingle 构建 | 2-3 s，约 214 MB | 49-53 s，峰值 1.8 GB |
| shingle 查询 | 进程约 0.3 s，单次查询多在 20 ms 以内 | 加载 1 s；raw ≤ 78 ms，norm 0.23-1.46 s |
| pairs（两种模式） | 约 1.4 s | 没有测 |
| ast-grep 单条模式（无索引） | 0.04-0.35 s，经 npx 每次另加约 0.7-1.1 s | 2.6-14.3 s（另一份 10.1 万文件的副本） |
| jscpd（各模式） | 前端 0.19-0.98 s，后端 0.34-0.92 s | 没有测 |

### 建议

1. **不要把 rg 原始输出直接交给 Agent。** 一个字段的 full 输出在 2.5k 文件上已是预算的 6-17 倍（12.5k-34.4k token），在 10 万文件上是 275-755 倍（55 万-151 万 token）；只在前端出现的日期格式化正则也有 6 万 token，是预算的 30 倍。tier 0 应先聚合再输出：按写法和前后端给计数（像契约切片那样一行说明一个字段），按文件分组排序，具体证据行控制在 50 行左右。
2. **所有大小写写法合成一个正则搜。** 耗时和搜一个字面量相同；只搜一种写法会漏掉另一侧的大部分。
3. **10 万文件时 rg 可以按需调用**，每条 2-4 s。contract_map 和 shingle 构建各要约 50 s、1-1.8 GB 内存，需要预先建好索引、按改动增量更新，不能每次全量跑。查询端加载 pickle 要 1 s，norm 查询最多 1.5 s，需要更紧凑的索引格式（例如可以 mmap 的数组）或常驻进程；raw 查询本身很快（≤ 78 ms）。
4. **把信号对应到确认档位：**
   - 直接命中，可以直接改：多词字段、topic、endpoint 按原名出现的位置。
   - 推断出的关联，附证据、用户确认后再改，按可信度排序：shingle raw 第 1 名且与第 2 名分差大的副本（Q1、Q5 和抽查里的 4 对真副本）；只靠变体命中的 tag（12 个里 1 个真关联、4 个兄弟字段、7 个误报）；只在 norm 达到阈值的函数对（6 对里 4 对真副本、1 对样板、1 对误报）。
   - 低可信，只列出：norm 的长尾命中、后端样板簇里的函数、只在测试里出现的 topic。
5. **短函数（约 50 token 以下）用正则或名字搜，不用 shingle。** Q2 的 31 token 函数只有 12 个指纹，真命中和噪声分数相同；一条 rg 正则就找到了 34 处内联格式化。
6. **shingle 和名字、契约搜索要一起用。** 写法不同的同类实现 shingle 找不到（Q1 的 `new-information.vue` 里的 `render`，Q3 的 `deviceStatusWebSocket.ts` 里的 `connect`），按字段名 `alarm_level` 或 endpoint `status/ws` 用 rg 能找到。反过来，改了名的副本按名字搜不到，shingle 能找到，例如 `internal/api` 的 `validReaderToken` 和 `internal/service` 的 `validSourceProjectionToken`，函数体完全相同（raw J=1.00）。
7. **按分差或 containment 排序，不用固定阈值。** 抽查的 4 对真副本 raw J 在 0.32-0.79 之间，全都低于 0.8，但都排第 1。嵌套函数要合并到外层函数（Q3 前 5 名只有 3 个外层函数）。
8. **降低常见形状和测试代码的权重。** 后端 norm 最大的簇是 149 个 gin handler 样板；262 个 topic 组里 212 个只在测试里；后端 raw 的 710 对函数里只有 78 对是干净的。
9. **外推时留余量。** 放大语料是相同的副本，不同指纹的个数没有增长；真实的 10 万文件仓库里，索引体积、候选数和查询时间都会更大。
10. **结构化工具的结果要和正则计数对照。** ast-grep 的 Go 方法调用模式静默返回 0，而正则有 20 处和 51 处。命中数明显少于正则，尤其是 0 的时候，要把两个数都报出来，改用正则的候选。脚本生成 Go 的调用模式时，用加上下文和 `--selector call_expression` 的写法，不写死参数个数。
11. **Vue SFC 的 script 块按同一种语言处理。** 这个前端有 61 个 tsx 块和 275 个 ts 块，ast-grep 和 jscpd 都按 lang 分开处理，只按一种语言搜就会漏。skill 自带的脚本应把 script 块抽出来统一处理。调用 ast-grep 时用内置注入，ts、tsx、js 各跑一次，不加自定义注入（会重复计数）；jscpd 加 `--similarity=0.8` 或 `--cross-formats js-ts`。
12. **ast-grep 和 jscpd 只做可选加速。** auto 模式下 Claude 不能用 npx 下载它们，经 npx 调用每次还多约 0.7-1.1 s。默认档位用 skill 自带的标准库脚本，检测到本机已经装了再用它们。jscpd 用 `--similarity=0.8`，不用改名模式；先排除生成代码，再按改动的文件查克隆对象。它能补上 shingle 看不到的 template 和 style 里的克隆。

## 局限与未完成项

- **ast-grep 和 jscpd 由用户运行，每条命令只跑了一次。** auto 模式不允许 Claude 用 npx 下载，所以由用户在自己的终端运行 `run_external_tools.sh`，计时只看量级。ast-grep 的放大实验用的是另一份副本（4 种扩展名、1,876 个文件 × 54 份）。没有在放大语料上跑 jscpd：相同的副本会让每个文件都和自己的 53 份副本互为克隆，结果没有意义。补测脚本 `run_external_followup.sh` 也由用户运行，同样每条一次。jscpd 和 shingle 只做了单向对照：查了 shingle 的函数对 jscpd 能不能找到，没有查 jscpd 的克隆里 shingle 漏了多少。
- **样本小，场景不全。** 只有两个开源仓库：一个前端，后端几乎只有 Go，没有 Python 和 Node 后端。浅克隆没有提交历史，没法用真实的修复提交检验召回率。命中质量靠逐条读代码判断，样本只有 12 个 tag、5 个查询、6 对函数。
- **放大语料是相同的副本。** 只能测耗时、体积和内存。`.tsx`、`.jsx`、`.mjs`、`.cjs` 和 `.gitignore` 没有复制，隐藏目录复制了。放大后没有跑 `pairs`：每个函数都会和自己的 42 份副本配对，结果没有意义。
- **只测了热缓存，只用了一台 M2。** macOS 下没有管理员权限，清不掉文件缓存。rg 在 10 万文件上 sys 时间高的原因没有查。
- **token 按字符数 / 4 估算**，会低估 CJK 文本（rg 输出里 CJK 占 1.7%）。
- **契约锚点在前端按整词计数整个文件**，不区分代码、字符串、注释和 CSS，variant-only 的误报（i18n key、CSS class）大多来自这里。
- **函数切分用正则加括号匹配。** 不理解 JS 正则字面量，不索引 Vue `<template>`；`<script setup>` 顶层的代码不属于任何函数（如 Q3 的 `details/index.vue:191`）；嵌套函数和外层函数分别计分。
- **发现的疑似问题都没有运行验证：** `last_visit_time` 前后端写法不一致；两份 `normalizeAlarmLevel` 不识别后端的 `H`/`M`/`L`；linkage-edit 的 `actionValueChange` 少校验 3 种类型；`secret-key-modal.vue` 的复制成功提示缺文案；配置里的 topic 拼写 `ota/devices/infrom`。
- **执行中的问题。** rg 耗时分解第一次运行时，有的命令没给路径，也没有重定向 stdin，rg 一直在等 stdin，300 s 后超时转入后台，被手动停止。重跑时加了 `.` 和 `< /dev/null`，表里是重跑的数字。
