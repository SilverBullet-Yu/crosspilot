# CrossPilot 2.0

**出海卖点的上线前尽职调查工作台。**

帮准备进入德国市场的中国消费品牌，在商品详情页上线前回答一个问题：

> 这个卖点有没有真实用户证据支持？下一步该验证什么？

它不生成「德国消费者喜欢什么」的笼统结论，只把证据分层摆清楚，给出可执行的下一步。

## 产品逻辑

| 层级 | 证据 | 用途 |
|---|---|---|
| L1 | 德国消费者一手反馈 | 唯一能支撑「消费者偏好」结论 |
| L2 | 知乎中文从业经验 | 只产出待验证问题 |
| L3 | 监管、贸易、学术语境 | 只提供背景与约束 |

证据先按来源分层，再去重（仅合并相同立场）、按单条卖点假设计数，做 Wilson 区间估计，最后只输出四种状态：

- **缺少有效数据**：样本不足，不给结论
- **已有有限支持**：支持区间刚过决定线
- **多数反馈反对**：反对区间过决定线
- **样本内存在分歧**：支持与反对并存，统计上未形成决定性多数

区间只描述当前样本；在线评论通常不是随机样本，不能直接外推为总体消费者偏好。

每轮输出证据卡、待验证问题、访谈问题与 A/B 测试方向；L1 消费者反馈与 L2 从业经验按卖点结构化对照，分别保留全部出处、样本分布和待核对问题，不把 L2 推断为消费者立场。

## 演示场景

固定场景：旅行收纳包 × 德国市场 × 详情页首屏（容量、功能、低价三个卖点假设）。

| 场景 | 数据 | 判定 |
|---|---|---|
| `real` | 知乎真实快照 + L3 监管/贸易数据；德国 L1 尚未取得授权 | 缺少有效数据（德国 L1 零样本） |
| `limited` | 30 条分层模拟评论，21:9 | 商品级包络兼容字段为 `supported`；工作台按卖点判定，目前三项均证据不足 |
| `conflict` | 30 条分层模拟评论，15:15 + 重复摘录 + 1 条未归属评论 | 商品级包络兼容字段为 `conflicting`；工作台按卖点判定，目前三项均证据不足 |

Amazon.de 公开评论候选因平台使用条件禁止未经书面许可的系统性提取、数据挖掘与商业再利用而否决；自动提取的原文与元数据已删除，未进入仓库。真实 L1 仅接受品牌授权导出或 Amazon 书面许可。

`limited` / `conflict` 场景同时包含模拟 L1 与模拟 L2，用于展示跨来源对照；演示数据均带显式标识，不与真实数据混排。

## 快速使用

要求：Python 3.12+、Node.js 20+、Git Bash（Windows）。

```bash
git clone https://github.com/SilverBullet-Yu/crosspilot.git
cd crosspilot

# 安装后端依赖、前端依赖，并生成 .env 记录模板（脚本不会自动加载）
bash scripts/bootstrap.sh

# 启动前端（默认读本地 fixtures，不需要后端、网络或凭据）
bash scripts/dev.sh web
```

打开 <http://localhost:3000>：

- `/`：产品概览
- `/workbench?scenario=real`：真实数据场景
- `/workbench?scenario=limited`：有限支持场景
- `/workbench?scenario=conflict`：证据冲突场景
- `/review`：授权 L1 的人工复核队列（仅 API 模式），本机保存立场、归属、相关性与复核说明，导出可重新导入的 JSON
- `/history`：本地验证轮次与运营试用记录（无服务端历史）；配置 API 后额外展示真实案例 readiness 检查项与下一步，fixtures 模式明确不伪造审计结果

工作台右栏会按当前假设与判定状态生成访谈问题、原型测试和两版待测试文案，并保留计划引用的 L1 原文出处；假设编辑、自定义假设与行动勾选按场景保存在本机浏览器，不代表已完成真人试用。自定义假设会显示 `claim_id`，授权评论导入时填写该 ID 即可归属并由后端独立判定；每轮观察、决定、理由和下一步可追加保存，在 `/history` 回看并导出。启用同组原型测试后，可按参与者编号、测试顺序、装什么、怎么取、哪里麻烦结构化记录。右栏还可导出 `crosspilot-case-<scenario>.json` 案例证据包，包含全部假设、证据原文、判定、跨来源对照、验证计划与本机轮次，并显式标注演示/真实边界；也可导出 `crosspilot-l1-import-template.json`，把当前 query 与自定义假设关键词转为数据提供方可补齐的 `claim_terms` 模板。

如需调用真实后端（另开终端）：

```bash
bash scripts/dev.sh api
NUXT_PUBLIC_API_BASE=http://localhost:8000 bash scripts/dev.sh web
```

### 导入授权德国评论

真实 L1 只从本地授权快照读取，不提供无鉴权的在线上传。可先在工作台右栏点击“导出 L1 数据导入模板”，生成 `crosspilot-l1-import-template.json`：自动带入当前 query、`market=de`、`internal_product_validation` 和有关键词的自定义 `claim_terms`；`source_id`、`authorization`、`authorization_ref` 留空，`cards=[]`，因此模板不可直接导入，必须由数据提供方补齐真实来源、授权依据与评论。无关键词的自定义假设不写入 `claim_terms`，导入后仍会回退整条并强制复核。准备完整 JSON 或 CSV 后先 dry-run：

```bash
.venv/Scripts/python.exe scripts/import_l1_reviews.py \
  --input reviews.csv --query "旅行收纳包" \
  --source-id "brand-export-2026-11" \
  --authorization "品牌授权导出，仅内部验证" \
  --authorization-ref "brand-export-2026-11" \
  --authorization-scope internal_product_validation --dry-run
```

`--dry-run` 会按真实判定口径输出每条卖点去重后的支持/反对/无极性样本、重复簇、门禁与四态判定，并单列未归属、不相关数量、人工复核/规则基线/人工与规则不一致数量、建议人工复核/低复核优先级数量和评论日期范围；任何卖点低于 n≥30 都会明确提示仍为证据不足。确认无误后去掉 `--dry-run`，快照写入 `data/snapshots/l1/`。正式导入会记录输入文件 `input_sha256` 和快照 `record_sha256`；同内容重复导入幂等，内容冲突时拒绝覆盖旧快照，加载时验证哈希，损坏快照返回明确错误。每条评论必须含 `review_id`、`excerpt`、`source_url`、`published_on`，原始 `review_id` 会原样保留到快照、API 与卡面，不用数组下标重写；相关评论可归属到 `claim_id`（预置 `capacity` / `features` / `price`，或工作台自定义假设显示的小写字母/数字/`-`/`_` ID）；产品相关但尚未归属的评论留空，导入器标记为 `claim_id=unassigned` 并保留原文与立场，但不进入任何卖点判定；不相关评论设 `relevance=irrelevant` 且不填 `claim_id`。市场固定为 `de`，来源、授权说明和 `authorization_ref`（授权合同编号、品牌导出记录或平台书面许可编号）必须非空。公开页面可见不等于获得再使用许可；Amazon.de 公开评论候选已因平台条款否决，不得导入。导入会剔除联系方式，并用规则基线标注立场；预置卖点只统计命中该卖点术语的从句，避免同一句评论的跨卖点极性串票，`review_reasons` 会显示相关从句占比与命中术语。未命中术语、未归属或未声明术语的自定义卖点回退整条规则票并强制人工复核，不得把回退票当作该卖点的精确证据；卖点级规则尚未独立评测。模型分析未完成真实评测前，不把模型输出作为结论。同一卖点下精确或近重复评论若被标成不同立场，系统不合并、不自动改票，而是标记 `review_required=true` 并列出冲突 `review_id`，防止标注冲突被误算成消费者分歧。人工发现规则误判时，可在 CSV/JSON 中填写 `stance` 与 `stance_note`：最终立场采用人工值，`stance_votes.rule` 保留规则票，`annotator_agreement` 记录是否一致，卡面显示「人工复核」；外部文件不能直接伪造 `classification_method`。未人工覆盖的规则结果会按保守阈值分流：仅强支持且无否定/正负混合可标记低复核优先级，反对、短评、弱信号与无明确极性均显示「建议人工复核」。MARC 商品域实测低优先级覆盖 5.9%、准确率 92.4%，但该金标是整体星级而非卖点级标签，因此不构成自动接受或模型准确性证明。

自定义卖点需要在 JSON 顶层用 `claim_terms` 声明术语范围，例如 `"claim_terms": {"custom-waterproof": ["wasserdicht", "waterproof"]}`；每个自定义 ID 可声明 1–20 个术语，单个不超过 80 字符。导入器拒绝内置/未归属 ID、未使用术语表和同一卖点不一致范围；术语进入快照哈希、API 的 `aspect_terms`、卡面与复核回导 JSON。CSV 不携带该映射，未声明术语的自定义卖点仍按整条回退并强制复核。

可直接交给数据提供方的最小 CSV 表头：

```csv
review_id,claim_id,excerpt,source_url,published_on,language,relevance,stance,stance_note
```

| 字段 | 交付要求 |
|---|---|
| `review_id` | 必填；来源系统中的原始评论 ID，文件内唯一 |
| `claim_id` | 已归属相关评论填 `capacity` / `features` / `price` 或自定义假设 ID；相关但未归属可留空（导入为 `unassigned`）；不相关评论留空 |
| `excerpt` | 必填；评论原文摘录，不填作者姓名、邮箱、电话或地址 |
| `source_url` | 必填；可追溯的 HTTPS 评论页或授权导出记录链接 |
| `published_on` | 必填；`YYYY-MM-DD`，不得晚于导入当天 |
| `language` | 必填；如 `de`，德国市场评论也可为其他语言 |
| `relevance` | 可选；默认 `relevant`，不相关评论填 `irrelevant` |
| `stance` | 可选；人工复核后填 `support` / `oppose` / `insufficient`。填写即标记为 `manual`，必须同时提供 `stance_note`，并保留规则基线票与一致度 |
| `stance_note` | 填写 `stance` 时必填；人工复核说明，最多 500 字符，自动剔除联系方式；缺失或清洗后为空拒绝导入 |

`query`、`source_id`、`authorization`、`authorization_ref` 通过命令行参数或 JSON 顶层字段提供。`authorization_scope` 必须是非空数组，且至少包含 `internal_product_validation`；可选 `model_processing`、`contest_demo`、`public_display`，分别声明模型处理、赛事演示和公开展示权限。授权范围必须明确覆盖内部产品验证；若计划公开展示评论，还必须覆盖该用途。仅有“公开页面可见”或非空授权编号，不等于已取得再使用许可。`data/snapshots/l1/` 默认加入 `.gitignore`，避免仅获内部授权的评论进入公开仓库。

### 授权 L1 分层采样

需要从较大授权导出中选取人工复核样本时，可生成确定性的“卖点 × 立场 × 发布月份”采样清单。脚本使用快照哈希、固定种子与去重后 canonical 评论，逐卖点默认选 30 条；不足时如实标记 `sufficient=false`，不补齐、不生成偏好结论：

```bash
.venv/Scripts/python.exe scripts/plan_l1_sample.py \
  --query "旅行收纳包" --claim-id capacity --target 30 --seed 42 \
  --output data/reports/l1/travel-packing-sample-plan.json
```

`--claim-id` 可重复；当前 EvidenceCard 契约没有星级/变体字段，报告会明确列为 `unavailable_dimensions`，需由数据提供方另附，不得从文本猜测。采样清单只记录 `review_id`、来源、日期与立场，不修改快照；`data/reports/l1/` 默认不入公开仓库。

### 人工复核授权 L1

配置真实 API 后打开 `/review`，可逐条修正规则基线、卖点归属与相关性，并填写复核说明；支持按卖点筛选、原文/评论 ID/来源搜索和逐卖点进度计数。草稿按当前已验证快照的 `record_sha256` 隔离保存到本机浏览器，旧版本人工决定不会套用到新证据；缺少快照指纹时保存与导出不可用。授权用途范围从快照经 API 原样带入，页面不可修改或扩大。导出 `crosspilot-l1-reviewed.json` 会写入 `source_snapshot_sha256`，随后用版本化导入保留旧快照：

```bash
.venv/Scripts/python.exe scripts/import_l1_reviews.py \
  --input crosspilot-l1-reviewed.json --versioned
```

同内容重复导入幂等，不同内容生成新版本；加载器选择最新且验证哈希的版本，损坏最新版本不会静默回退。导出文件保留原始 `review_id`、原文、日期、来源、授权依据与显式 `authorization_scope`，不会把演示卡写入真实案例。使用 JSON 而非 CSV 回导，避免表格公式注入和原文变形；导入器仍会再次清洗联系方式。

快照同时记录内容 `record_sha256` 与包含 `generated_at_utc` 的 `version_sha256`：前者保证同内容幂等，后者保证时间戳篡改无法绕过版本校验。复核回导必须校验 `source_snapshot_sha256` 对应的父快照、原文与溯源字段，且不得改变或扩大授权范围。

### 归档验证轮次

`/history` 导出的 `crosspilot-validation-rounds.json` 可先 dry-run，再归档到 `data/validation_rounds/`：

```bash
.venv/Scripts/python.exe scripts/import_validation_rounds.py \
  --input crosspilot-validation-rounds.json --dry-run
.venv/Scripts/python.exe scripts/import_validation_rounds.py \
  --input crosspilot-validation-rounds.json
```

归档校验轮次 ID、ISO 时间、场景、`claim_id`、判定状态、决定枚举、确认完整性与联系方式；已确认轮次缺少观察、理由、下一步或负责人时拒绝归档。已确认 `real` 轮次还必须包含 `market=de` 与当前 `l1SnapshotSha256`，旧快照轮次不计入新案例。每轮写入独立 JSON 并附 `record_sha256`，重复导入同一轮次不会覆盖原文件；加载归档时同一 `round.id` 跨文件重复会直接拒绝，避免重复轮次灌入 readiness。待确认草稿也会保留，摘要明确区分确认状态与原型测试轮次数，不生成消费者偏好或市场效果结论。原型记录包含参与者编号、测试顺序、装什么、怎么取、哪里麻烦，已确认时缺一不可。

### 真实案例完成审计

导入授权 L1 并归档运营轮次后，用同一口径检查“真实商品案例 + 运营试用”是否完成：

```bash
.venv/Scripts/python.exe scripts/audit_case.py --query "旅行收纳包" --json
# 强制门禁：仅 decision_ready / trial_complete 返回 0，其余返回 1
.venv/Scripts/python.exe scripts/audit_case.py --query "旅行收纳包" --require-ready
# 真实案例 + 运营试用闭环验收：仅 trial_complete 返回 0
.venv/Scripts/python.exe scripts/audit_case.py --query "旅行收纳包" --require-trial-complete
# 注意：decision_ready 只表示样本可决策，不代表真实案例与试用闭环完成
# 只审计当前案例的自定义卖点（可重复 --claim-id）
.venv/Scripts/python.exe scripts/audit_case.py --query "旅行收纳包" --claim-id custom-waterproof --json
```

审计读取本地 L1 快照与 `data/validation_rounds/`，逐项检查商品/市场、授权德国 L1、逐条溯源、真实/模拟隔离、卖点归属、人工复核、逐卖点去重后有极性样本 `n≥30` 和运营确认轮次，并输出四级状态。CLI JSON 与 API 同时返回 `snapshot_sha256` 与 `rounds_archive_sha256`，历史页展示两者，确保就绪结论同时绑定消费者证据和运营轮次版本。人工复核门禁只认可相关 L1 同时满足 `classification_method=manual`、`review_required=false` 和非空 `classification_note`；规则低优先级或 LLM 结果不能冒充人工复核，不相关评论不进入偏好复核门禁：

| 状态 | 含义 |
|---|---|
| `blocked` | 缺少合规德国 L1、关键溯源字段，或演示数据混入真实案例 |
| `exploratory` | 已有 L1，但未归属、待复核或任一卖点样本不足 |
| `decision_ready` | 数据与样本门禁通过，尚缺运营试用确认 |
| `trial_complete` | 每条卖点至少有一轮 `real` 场景已确认运营记录，引用该卖点真实 `review_id: source_url`，且 `market=de`、`l1SnapshotSha256` 与当前快照一致；仍不能声称总体市场效果 |

同一审计也可通过 `GET /api/case/readiness?query=旅行收纳包` 读取；重复 `claim_id` 参数可只审计当前活跃卖点，历史页提供逗号分隔输入并从本机工作台恢复默认假设 ID。未指定时仍检查内置三项与快照自定义卖点；非活跃卖点的待复核评论不阻塞当前案例，但相关未归属评论仍阻塞。L1 快照或归档哈希损坏时返回 HTTP 409，非法 `claim_id` 返回 HTTP 422。当前真实案例状态为 `blocked`，因为尚无授权德国 L1。

凭据可选，仅在接入真实数据时需要。项目没有 dotenv，`.env` 只是记录模板，**不会自动加载**；运行前必须在当前 shell 导出所需变量：

```bash
export ZHIHU_ACCESS_SECRET='YOUR_ZHIHU_ACCESS_SECRET'
export LLM_API_BASE='YOUR_OPENAI_COMPATIBLE_BASE_URL'
export LLM_API_KEY='YOUR_LLM_API_KEY'
export LLM_MODEL='YOUR_MODEL_NAME'
export COMTRADE_SUBSCRIPTION_KEY='YOUR_COMTRADE_KEY'  # 仅 Comtrade 正式取数需要
```

| 变量 | 用途 |
|---|---|
| `ZHIHU_ACCESS_SECRET` | 知乎实时检索（实测 10 次/日） |
| `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` | LLM 立场抽取；缺省回退规则基线 |
| `COMTRADE_SUBSCRIPTION_KEY` | UN Comtrade 正式取数 |

Demo 默认快照模式，只读 `data/snapshots/`；实时模式需显式设 `CROSSPILOT_DATA_MODE=live`。

LLM 立场评测需显式配置三项凭据；正式子集推荐固定种子随机抽样，`--limit` 仅用于主表前 N 条的成本冒烟：

```bash
.venv/Scripts/python.exe scripts/eval_stance_baseline.py \
  --classifier llm --dataset marc --sample-size 200 --seed 42
```

评测缓存按模型、端点哈希和提示词指纹隔离，只缓存成功的 LLM 结果；规则回退不落盘。当前无凭据，未完成真实 LLM 实测。

授权 L1 到位后，可单独评测卖点级分类器。`--dataset l1` 只把人工最终立场且满足 `manual + review_required=false + 非空复核说明` 的评论作为金标，按 `claim_id` 与 `aspect_terms` 逐卖点输出 accuracy、precision/recall/F1 与混淆矩阵；没有真实快照或人工金标时返回 1，不生成指标：

```bash
.venv/Scripts/python.exe scripts/eval_stance_baseline.py \
  --dataset l1 --query "旅行收纳包" \
  --output data/reports/l1/travel-packing-stance-eval.json
```

`--output` 可选，报告不含评论原文且不得写入 L1 快照目录；`data/reports/l1/` 默认被 Git 忽略，避免泄露真实商品、查询词与样本结构。该评测只描述当前授权样本内的分类质量，不代表总体消费者偏好或市场效果。默认使用规则基线；加 `--classifier llm` 时，适配器会接收目标卖点与术语，只判断该卖点，缓存键同时包含文本、`claim_id` 与术语范围。自定义卖点缺术语时拒绝调用，运行时故障回退同卖点规则基线且不缓存：

```bash
.venv/Scripts/python.exe scripts/eval_stance_baseline.py \
  --dataset l1 --query "旅行收纳包" --classifier llm \
  --output data/reports/l1/travel-packing-llm-eval.json
```

提交前自检：

```bash
bash scripts/check.sh      # ruff + mypy + 全量测试 + 数据区校验
bash scripts/check_web.sh  # 前端 97 断言
```

> 克隆后若 `check.sh` 的数据区校验红灯，通常是本地没有 MARC 主表：该数据依许可禁再发布，不随仓库分发，属预期。CI 只跑 ruff / mypy / 测试。

## 目录地图

| 路径 | 职责 |
|---|---|
| `apps/api/` | FastAPI 后端：检索、立场抽取、证据分层、判定 |
| `apps/web/` | Nuxt 4 + Vue 3 工作台前端 |
| `packages/contracts/` | 前后端共享证据卡契约 |
| `data/sources/` | 9 个外部数据源，每源四件套 + raw |
| `data/snapshots/` | 演示预跑快照，Demo 只读这里 |
| `data/validation_rounds/` | 工作台导出的验证轮次归档；当前无真人记录 |
| `data/licenses/` | 数据许可原件 |
| `docs/` | 状态、清单、需求、调研、报告、ADR、演示与开发日志 |
| `scripts/` | 初始化、启动与自检脚本 |

## 五条硬约束

1. L2/L3 证据不得单独支撑「消费者偏好」结论
2. MARC 数据集在商业化路径启动即下线
3. OPUS 只取 ParaCrawl，排除 OpenSubtitles
4. Comtrade 必须注册账号，禁用 preview 的截断结果
5. DeepL API Free 档禁止传入含个人数据的文本

另有两条产品级强制项：**证据不足必须渲染为独立空状态卡片**，**证据冲突必须左右并排原文**。真实 L1 必须带卖点归属、市场、来源与授权说明；所有偏好表述必须附带“非随机样本、不可直接外推总体”的限制。

## 数据与许可

- 代码：MIT（见 [LICENSE](LICENSE)）
- 数据：逐源声明许可，汇总见 [data/sources/README.md](data/sources/README.md)
- MARC 依 Amazon 学术研究许可**禁再发布**，不随仓库分发
- 知乎内容只做实时检索 + 摘要引用 + 链接回源，不建全文库

## 文档与协作

- 文档总索引：[docs/README.md](docs/README.md)
- 当前状态与接管：[docs/status/STATUS.md](docs/status/STATUS.md)
- 演示 Runbook：[docs/demo/演示说明.md](docs/demo/演示说明.md)
- 分支：`feat/*`、`fix/*`、`docs/*`；提交信息 `type(scope): summary`
- 合并前 `bash scripts/check.sh` 全绿；每次 AI 辅助开发后在 `docs/devlog/` 追加记录
