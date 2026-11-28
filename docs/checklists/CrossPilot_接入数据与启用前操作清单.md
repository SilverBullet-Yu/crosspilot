# 接入数据与启用前操作清单

适用场景：① 接入一批新爬取/新获取的外部数据；② 从演示态切换到投入使用（live / 提交评审）前做最终核对。

> 最后核对：2026-11-28（GitHub public 仓库 `SilverBullet-Yu/crosspilot` 已推送 `main`，CI 首跑 success）

> 本清单位于仓库内 `docs/checklists/`；文中 `apps/`、`docs/`、`data/`、`scripts/` 等路径均相对仓库根目录。

约定来源：`data/sources/README.md`（四件套）、`services/datasets.py`（注册表）、`docs/CONSTRAINTS.md`（硬约束）、`.env.example`（凭据）、ADR-0002 ~ 0005。任何改动以这几处现行版本为准。

---

## 一、接入新数据源

### 路径 A：批量/结构化来源 → `data/sources/`

**A1. 抓取与落地**
- [ ] 在 `data/sources/_scripts/` 新增 `fetch_<source>.py`；时间窗引用 `common.py` 的 `WINDOW_START / WINDOW_END`，不得另行定义
- [ ] 抓取逻辑带退避重试与留痕 `Provenance`（一行一次 HTTP 调用：URL、状态码、字节数、SHA-256、UTC 时间）
- [ ] 产出四件套 + raw 到 `data/sources/<source>/`：
  - 主表 `<source>_<window>.csv`（UTF-8-BOM、长表）
  - `provenance.csv`
  - `manifest.json`（时间窗、许可、层级、行数、截断记录；静态基准须声明 `time_coverage_applicable: false`）
  - `README.md`（来源、许可、层级、字段、使用约束、复现命令）
  - `raw/` 原始响应（未经改动）
- [ ] 许可原件存入 `data/licenses/`

**A2. 注册与许可边界（不登记即拒绝加载）**
- [ ] 在 `services/datasets.py` 的 REGISTRY 登记：`tier`（L1/L2/L3/BENCHMARK）、`license`、`commercial_ok`、`requires_credential`、`priority`（P0/P1/P2）
- [ ] 卖家自撰文案类来源必须标 `seller_side_only=True`（只能进「企业假设」栏）
- [ ] 受硬约束 2 管辖的来源（Amazon 学术类）确认商业化下线路径
- [ ] manifest 声明的层级与 REGISTRY 登记的 tier **必须一致**（不一致视为数据错标）

**A3. 适配器与契约**
- [ ] 新增 services 适配器把主表转成 EvidenceCard，字段对齐 `packages/contracts/evidence-card.schema.json`（六个必现字段；schema `additionalProperties=false`）
- [ ] 适配器内显式执行层级闸门：L2/L3 只产出待验证问题，不得单独支撑偏好结论（`domain/evidence.py`）
- [ ] 文本进立场抽取前先过 `sanitize_excerpt`（≤300 字符，不含 PII）
- [ ] 有已知缺口/禁令的，写进该源 `README.md` 并在 manifest 声明（参照 gdelt 的 SPARSE 写法）

**A4. 验证**
- [ ] `bash scripts/check.sh` 六道全绿（ruff / mypy strict / 全量测试 / 数据区结构校验 / 时间覆盖校验 / 质量校验）
- [ ] `docs/devlog/` 当日文件追加记录

### 路径 B：知乎演示快照 → `data/snapshots/`

- [ ] 凭据就绪（shell 导出 `ZHIHU_ACCESS_SECRET`——`.env` 只是记录模板，**不会被脚本自动加载**，适配器读进程环境变量），设 `CROSSPILOT_DATA_MODE=live`
- [ ] 跑 `scripts/capture_zhihu_snapshot.py` 落盘到 `data/snapshots/zhihu/<查询词>.json`（额度：搜索 10 次/日、热榜 2 次/日、直答 2 次/日，先规划查询词）
- [ ] 快照由 `build_snapshot_document` 产出，`zhihu_snapshot.py` 校验通过（该模块是 schema 唯一校验口径）
- [ ] 合规最小集：摘录 ≤300 字符、作者匿名化（`author_anonymous_id`）、链接回源；顶层与逐卡 `is_demo_data` 一致，不与真实反馈混排
- [ ] 无发布日期元数据的卡**不收录**（不以捕获日冒充发布日）

### 路径 B2：授权德国 L1 本地导入 → `data/snapshots/l1/`

- [ ] 授权范围明确覆盖内部产品验证；`authorization_scope` 至少包含 `internal_product_validation`，模型处理/赛事演示/公开展示分别声明；若计划公开展示评论，还需覆盖该用途，并留存可审计的 `authorization_ref`
- [ ] 优先从工作台导出 `crosspilot-l1-import-template.json` 获取 query 与自定义 `claim_terms`；模板不含评论/授权凭据，补齐 `source_id`、`authorization`、`authorization_ref`、`cards` 前不得导入
- [ ] CSV/JSON 每条评论含原始 `review_id`、`excerpt`、`source_url`、`published_on`、`language`；已归属相关评论含 `claim_id`，相关但未归属评论标记 `claim_id=unassigned`，不相关评论设 `relevance=irrelevant` 且不填 `claim_id`
- [ ] 自定义卖点使用 JSON 顶层 `claim_terms` 声明 1–20 个本地语言术语；同一 `claim_id` 范围一致，术语进入快照哈希、API `aspect_terms` 与复核回导 JSON
- [ ] 市场固定 `de`；`source_id`、`authorization`、`authorization_ref` 非空；原始 `review_id` 文件内唯一
- [ ] 使用 `scripts/plan_l1_sample.py` 生成逐卖点确定性分层采样清单，记录 `snapshot_sha256`、种子、立场/月份分层与不足状态；星级/变体缺少契约字段时由数据提供方另附，不猜测
- [ ] 在 `/review` 完成待复核评论的立场、归属、相关性与说明；导出 JSON 后用 `--versioned` 写入新版本，复核草稿不算已完成
- [ ] 使用卖点筛选与原文/评论 ID/来源搜索定位待复核评论，并核对逐卖点进度，避免大体量队列漏审
- [ ] 复核草稿按 API 返回的 `l1_snapshot_sha256` 隔离；更换快照版本后不得继承旧 `review_id` 的人工立场，导出 JSON 保留 `source_snapshot_sha256`
- [ ] CSV/JSON 人工填写 `stance` 时必须同时提供非空 `stance_note`；缺失、纯空白或清洗后为空均拒绝导入
- [ ] 同一卖点下精确或近重复评论若出现不同立场标签，不自动合并；核对 `review_reasons` 中冲突组并人工解决后再计入分歧
- [ ] readiness 的人工复核门禁仅认可相关 L1 同时满足 `classification_method=manual`、`review_required=false` 和非空 `classification_note`；规则低优先级与 LLM 结果不得冒充人工复核
- [ ] 记录输入文件 `input_sha256` 与快照 `record_sha256`；同内容幂等、冲突拒写，加载时验证哈希
- [ ] 先跑 `scripts/import_l1_reviews.py --dry-run`，逐条核对卖点样本、重复簇、门禁/判定、未归属/不相关数量与日期范围；确认无误后再写入快照
- [ ] 导入后复核快照中的 `review_id` 与来源文件一致，未被数组下标重写；API 卡面显示原始评论 ID 与授权依据
- [ ] 联系方式已剔除；真实 L1 与演示卡不混排；规则基线立场未经真实评测不得冒充模型结论
- [ ] `data/reports/l1/` 下的真实采样/评测报告默认不入公开仓库；公开展示前另核授权与脱敏
- [ ] 内置卖点规则票只统计命中该卖点术语的从句；逐条核对 `review_reasons` 中的相关从句占比与命中术语，确认“夸隔层、骂价格”不会串票
- [ ] 未命中卖点术语、`claim_id=unassigned` 或未声明 `claim_terms` 的自定义卖点已回退整条规则票并列入人工复核；不得把回退票当作该卖点的精确证据
- [ ] `real` 场景按 `claim_id` 独立判定；L2/L3 只进入跨来源待验证问题，不改变 L1 偏好判定
- [ ] 导入完成不等于运营试用完成；仍须由真实运营在工作台为每个活跃卖点保存并确认 `real` 轮次，引用同卖点真实 `review_id: source_url`，填写 `market=de` 并绑定当前 `l1SnapshotSha256`，再导出 `crosspilot-validation-rounds.json` 并归档；单独的 `/history` 运营总结表不计入 readiness
- [ ] 保存 readiness CLI JSON/API 结果时一并记录 `snapshot_sha256` 与 `rounds_archive_sha256`，确保审计结论可追溯到具体 L1 快照和运营轮次版本
- [ ] 用 `--claim-id` 或 readiness API 的重复 `claim_id` 参数指定活跃卖点；自定义-only 案例不得被未活跃的内置三项零样本阻塞，活跃零样本仍必须保持证据不足
- [ ] 轮次归档加载时确认 `round.id` 跨文件唯一；同一 ID 的不同内容文件必须清理后再审计，不得重复计入运营试用

### 路径 C：改造契约（前后端共同，改动需谨慎）

- [ ] 先在 `docs/adr/` 立新决议（ADR 只增不改）
- [ ] `packages/contracts/` 改 schema → 后端 domain/适配器同步 → 前端同步
- [ ] `bash scripts/check.sh` + `bash scripts/check_web.sh` 双绿

---

## 二、投入使用前确认

### B1. 凭据与配置（环境变量；`.env` 是记录模板，已被 git 忽略，**运行前需 shell 导出，不会被脚本自动加载**）

- [ ] `ZHIHU_ACCESS_SECRET` — https://developer.zhihu.com/profile 自助生成
- [ ] `COMTRADE_SUBSCRIPTION_KEY` — 硬约束 4：禁用匿名 preview（500 行截断结果）
- [ ] `LLM_API_BASE / LLM_API_KEY / LLM_MODEL` — OpenAI 兼容端点三项齐备（智谱/DeepSeek/Moonshot 等）
- [ ] `NUXT_PUBLIC_API_BASE` — 留空/`fixtures` 读本地夹具；填 `http://localhost:8000` 走真实后端
- [ ] **LLM live 首跑核验**：响应结构与 `stance_llm.py` 文档不符时，以实际响应修订该文件并回填核验记录（与 zhihu_client 同口径）

### B2. 模式与演示安全线

- [ ] Demo / 评审默认 `CROSSPILOT_DATA_MODE=snapshot`，确认不走实时网络
- [ ] live 切换为**显式**操作，额度耗尽必须出现明确降级提示（不静默返回空结果）
- [ ] 快照缺失/损坏路径验证过：返回空列表 + 非空降级提示字符串
- [ ] 真实卡（`is_demo_data=false`）与演示卡不混排；conflict / limited 两个演示场景的标识仍在

### B3. 数据缺口禁令复核（错用即翻车）

- [ ] **GDELT**：禁止趋势分析、跨时间比较、量级统计；只可验证检索式与取定性示例
- [ ] **Safety Gate**：品类分析前先过滤（Motor vehicles 占 46%）；适配器只取近邻品类 519 条
- [ ] **amazon_reviews_2023**：美国站样本，对德国市场不构成 L1，不得冒充德国证据
- [ ] **gerestaurant / marc / usage_bielefeld**：基准只作立场评测，不进证据卡；gerestaurant 禁止外推商品域；marc 商业化即下线；usage_bielefeld 无文本层
- [ ] **eurostat_isoc / eu_comext**：仅作语境；CN8 八位细目不可得，不做细分贸易结构分析

### B4. 许可与交付合规

- [ ] `marc/` 主表确认未随仓库分发（研究许可禁再发布）；克隆环境凭 `_scripts/fetch_marc.py` 本地复现
- [ ] 各源 README 署名齐全，`data/licenses/` 原件随作品说明提交
- [ ] 知乎内容只作摘录引用（≤300 字符 + 回源链接），未建全文库

### B5. 产品级强制项与最终验证

- [ ] 证据不足渲染为独立空状态卡片；证据冲突左右并排原文（缺一即功能未完成）
- [ ] `bash scripts/check.sh` 六道全绿（fresh clone 时 MARC 结构校验一道红属预期）
- [ ] `bash scripts/check_web.sh` 97 断言全绿；录屏/提交前必跑
- [ ] 演示 Runbook（`docs/demo/演示说明.md`）三场景可达，截图与当前版本一致
- [ ] GitHub public 仓库 `SilverBullet-Yu/crosspilot` 的 `main` 与本地一致，最近一次 push 的 CI 为 success
- [ ] `../status/STATUS.md` 更新为当前状态（唯一事实来源，交班最后一件事）
- [ ] `docs/devlog/` 每日记录齐全（赛事创作真实性佐证）

---

## 三、一次性速查表

| 阶段 | 必做 | 会挂的点 |
|---|---|---|
| 抓取 | fetch 脚本 + 四件套 + raw | 时间窗绕过 common.py、provenance 缺行 |
| 注册 | REGISTRY 登记 | 忘记登记 → 适配器拒绝加载 |
| 适配 | 契约对齐 + 层级闸门 | L2/L3 混入偏好结论、摘录超 300 字符 |
| 启用 | 凭据 + 模式 + 禁令复核 | GDELT 当趋势用、美国站冒充德国 L1 |
| 交付 | 双自检 + STATUS + devlog | 截止 12-07 10:00，逾期不可修改 |
