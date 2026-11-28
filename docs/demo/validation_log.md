# CrossPilot 2.0 验证日志（Validation Log）

> 闭环留痕：**假设 → 证据检索 → 四值判定 → 建议动作 → 运营决定 → 下一步**。
> 判定口径见 `演示说明.md` 8.3 映射表；本日志同时是商业叙事的交付物样例——流程先于产品，我们自己就是第一个用户。
> 后续每次验证在表末追加一行；运营决定一栏未经人工确认前一律写「待确认」，不以 Agent 推断代替运营意见。
> 历史行保留当时口径：第 2 行的商品级 `conflicting` / `supported` 是包络兼容字段，不是当前工作台的卖点结论；当前验收统一以 `claim_decisions` 为准。

| # | 日期 | 卖点假设 | 假设来源 | 证据检索（摘要） | 判定 | 建议动作 | 运营决定 | 下一步 | 留痕 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-18 | 「大容量应放在德国站详情页首屏」 | 方案 1.1 预设；运营本人确认待 P0-3 访谈（未完成前标注「来源待确认」） | ① 知乎 3 组检索式（旅行收纳包 × 容量 × 德国，2026-11-18 真实采集）：30 条结果中「德国 + 收纳包 + 容量」交集 0 条——中文经验与德国语境零重叠，实证「来源分散、口径不统一」；② L3 Safety Gate 近邻品类 519 条召回警报（2021–2026 六年）；③ L3 Comext HS4202 中国→德国 2025 年 9.50 亿欧元（品类市场存在性成立）；④ 德国 L1：零样本（无授权数据源，唯一路径为品牌授权导出） | **证据不足（黄）**——L1 零样本；L2 仅计问题来源；L3 仅语境，均不构成消费者偏好结论 | 首屏候选从「大容量」形容性卖点转向「精确尺寸/容量参数 + 可核验合规标识」，待 L1 验证后定稿；衍生 3 个核查问题（核心／权衡／框架）转访谈提纲 | 待 P0-3 访谈（未定） | ① 品牌授权导出（STATUS.md 待办 1，最高优先级）；② 知乎 C/E 片段重采补齐（待办 2，随凭据） | `docs/research/CrossPilot_证据调研清单_2026-11-18_回填版.md`（P0 四组结论）、`data/snapshots/zhihu/旅行收纳包.json`、`data/sources/eu_safety_gate/`、`data/sources/eu_comext/`、`docs/status/STATUS.md` §三/§四 |
| 2 | 2026-11-22 | 「判定从口径变公式」（ADR-0005 判定链上线验证） | 对抗性审查（A0–A4 实现前的堵漏清单） | ① demo conflict 场景：15:15 + 2 条重复摘录 → 精确 3-gram Jaccard 去重（重复不进计数）→ 两份额 Wilson 区间重叠 → **conflicting**；② demo limited 场景：21:9 → n=30 过门禁、支持份额 0.7 下界 0.521 刚过决定线 → **supported**；③ 美国市场 L1 试点分层采样清单 30 条（A5，星级×时间分层）就绪待判定链接入；④ 德国 L1：仍零样本（品牌授权导出，待办 #1） | **四值判定全部公式化（演示覆盖三态）**：insufficient（门禁）/ conflicting（区间重叠）/ supported（下界过决定线）/ refuted（反对下界过半）各有量化判据，判定依据进包络 decision 字段可追溯 | 判定链从文案修饰升级为公式输出——「有限支持」「证据冲突」不再依赖措辞，评审可直接读区间 | 待确认（运营侧无变化，本轮为方法论升级） | ① 美国 L1 试点 30 条样本跑规则基线抽取 + 判定链端到端（L1 演练，遵守 tier_caveat）；② 德国 L1 到位后同框架零改动接入 | `apps/api/tests/test_stats.py`、`test_decision.py`（边界用例 20:10→conflicting / 21:9→supported）、`scripts/build_l1_sample_frame.py`、`data/sources/amazon_reviews_2023/l1_sample_frame.md`、ADR-0005 |

| 3 | 2026-11-27 | 「容量越大越好 / 功能越多越好 / 低价是核心购买理由」 | CrossPilot 工作台预置假设 | 核验 Amazon.de 旅行收纳商品公开评论候选；官方使用条件 §3/§5 禁止未经书面许可的系统性提取、数据挖掘、自动化收集及商业再利用。自动提取的原文与元数据已删除，未进入快照、fixtures 或 API | **候选否决，不构成可用 L1**；real 场景仍为德国 L1 零样本 | 只接受品牌授权评论导出或 Amazon 书面许可；在授权到位前继续用模拟场景展示方法 | 待确认（运营试用未执行） | ① 获取品牌授权评论；② 邀请跨境运营试用；③ 商用前由合规模块复核 | Amazon.de 使用条件 <https://www.amazon.de/gp/help/customer/display.html?nodeId=201909000>、`docs/status/STATUS.md` |

| 4 | 2026-11-27 | 公开德国 L1 候选二次核验 | 用户选择“使用公开数据” | ① USAGE 官方页明确不发布 Amazon 评论原文、不得再分发，且无发布日期；② Mendeley v2 为 CC BY 4.0，但官方元数据未证明德语/德国市场、日期、逐条来源 URL 或 review_id，文件端点返回 HTML 而非 XLSX，无法做字段级核验；③ Allegro Reviews 为波兰语，Ciao 许可证与德国子集未核实 | **0 个候选准入**；不把许可不明、市场不明或缺日期的数据冒充真实 L1 | 保持 real 场景零样本；只接受品牌授权导出或 Amazon 书面许可，并保留原始 `review_id` 与 `authorization_ref` | 待确认（运营试用未执行） | ① 获取品牌授权评论；② 邀请跨境运营试用；③ 对取得的数据重跑许可、市场、日期与来源字段审计 | [USAGE 官方页](https://www.romanklinger.de/usagecorpus/)、[Mendeley v2](https://data.mendeley.com/datasets/vwdmctbkr9/2)、[Allegro 官方仓库](https://github.com/allegro/klejbenchmark-allegroreviews)、[Ciao 官方页](https://www.cse.msu.edu/~tangjili/datasetcode/truststudy.htm) |

| 5 | 2026-11-27 | Apple 德国区 App Store 评论 RSS 能否作为公开 L1 | 公开数据候选二次核验 | 官方德国区 RSS 实际返回评论，含 `updated` 日期、评论 `id`、原文与 `de` 店铺链接；但 Apple Media Services Terms §F 明确仅限个人非商业用途、不授予商业或推广权利，并禁止用自动或等效手动流程抓取、复制、测量、分析或监控服务/内容 | **候选否决**；官方可访问不等于可商业再利用，未下载评论入仓 | 只接受品牌/开发者授权导出、App Store Connect 本人应用数据或 Apple 书面许可；不得把公开 RSS 评论用于 CrossPilot 商业案例或公开展示 | 待确认（运营试用未执行） | ① 获取品牌授权评论；② 邀请跨境运营试用；③ 如需应用案例，由应用所有者通过 App Store Connect 导出并确认授权范围 | [Apple Media Services Terms §F](https://www.apple.com/legal/internet-services/itunes/)、[德国区 RSS 端点](https://itunes.apple.com/de/rss/customerreviews/id=284882215/sortBy=mostRecent/json) |

| 6 | 2026-11-27 | Hugging Face 德语评论命名检索 | 公开数据候选二次核验 | `GermanSentimentBank` 明确为 AI 合成数据；`sepidmnorozy/German_sentiment` 无许可且只有 `text/label`；书评集只有 26 条混合记录、其中 Amazon 评论不足 30 条且声明限研究教育、缺逐条来源 URL/review_id；`amazon-reviews-de-filtered` 无卡片/许可且只有 `review_body/class`；`german_products` 实际为商品描述 `input/output` | **候选全部否决**；合成、许可不明、字段不足或样本不足均不构成真实 L1 | 保持 real 场景零样本；不下载或展示候选评论 | 待确认（运营试用未执行） | ① 获取品牌授权评论；② 邀请跨境运营试用；③ 对新来源继续按许可、市场、日期、逐条出处与原始 ID 四项准入 | [GermanSentimentBank](https://huggingface.co/datasets/infinite-dataset-hub/GermanSentimentBank)、[German_sentiment](https://huggingface.co/datasets/sepidmnorozy/German_sentiment)、[书评集](https://huggingface.co/datasets/Susannevoemel/selbstwahrnehmung-buch-rezensionen-pressestimmen-2025)、[Amazon DE filtered](https://huggingface.co/datasets/maaaaxxx/amazon-reviews-de-filtered) |

| 7 | 2026-11-28 | 公开德国 L1 候选第三次核验 | ① Amazon Reviews’23 官方数据字段有原文、ASIN、时间戳，但 Hugging Face 官方元数据标签为 `language:en`、`region:us`，没有德国/德语子集；② Trustpilot Business Reviews Dataset 为 AWS Marketplace 产品，未核验开放再使用许可；③ 搜索未发现同时具备德国市场、日期、商品 ID、逐条出处和可商用许可的旅行收纳包评论集 | **0 个候选准入**；字段完整不等于市场与许可合规 | 保持 real 场景德国 L1 零样本；只接受品牌授权导出或平台书面许可。新增假设级验证轮次，先让真人试用观察按轮次留痕，数据到位后同框架接入 | 待确认（真人运营试用未执行） | ① 获取品牌授权评论；② 邀请跨境运营按轮次记录；③ 对新来源继续执行许可、市场、日期、逐条出处与原始 ID 准入 | [Amazon Reviews’23 官方](https://amazon-reviews-2023.github.io/)、[Hugging Face 元数据](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023)、[Trustpilot AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-ogq7zgb7kxi3e) |

| 8 | 2026-11-28 | 真实商品案例完成门禁 | 原始 idea 的“先完成真实商品案例，再请运营试用”验收 | 新增 readiness 服务、CLI 与 API，覆盖授权 L1、溯源、模拟隔离、归属、人工复核、逐卖点 n≥30 和运营确认；12 项定向测试通过。当前 CLI 实测返回 blocked，真实 L1 0 条 | **真实案例未完成**；代码门禁已就绪，不把测试夹具、模拟评论或待确认草稿计为完成 | 保持 real 场景证据不足；取得品牌授权导出或 Amazon 书面许可并完成运营轮次归档后再跑 `--require-trial-complete` | 待确认（真人运营试用未执行） | ① 获取授权德国 L1；② 完成复核与逐卖点样本；③ 运营按假设确认轮次并归档 | `apps/api/tests/test_case_readiness.py`、`scripts/audit_case.py`、`apps/api/src/crosspilot_api/routers/case.py` |

| 9 | 2026-11-28 | L1/L2 跨来源结构化对照 | 原始 idea 的“保留出处、把不一致变成问题” | 新增 comparisons 契约与工作台分列面板；按卖点保存 L1 分布、L2 线索和双方完整出处，生成场景核对/潜在分歧问题；4 项后端测试、88 项前端断言与浏览器验证通过 | **方法链已验证，真实对照仍未完成**；德国 L1 为零，L2 不被推断为消费者立场 | 授权 L1 到位后按同一框架生成真实对照，保留市场与场景差异 | 待确认（真人运营试用未执行） | ① 获取授权德国 L1；② 回看双方原文；③ 由运营确认分歧是否改变卖点决策 | `apps/api/src/crosspilot_api/services/cross_source.py`、`apps/web/app/components/QuestionsColumn.vue`、`apps/api/tests/test_cross_source.py` |
| 10 | 2026-11-28 | 严格真实案例完成门禁 | 避免把“样本可决策”误报为“真实案例 + 运营试用完成” | 新增 `--require-trial-complete`；集成测试构造 30 条 L1，验证 `decision_ready` 被拒绝，归档绑定当前快照的确认轮次后才返回 0。当前无真实数据，命令实测返回 1 | **严格门禁行为正确，真实案例仍 blocked** | 最终验收只接受 `trial_complete`，不再用 `--require-ready` 代替闭环证明 | 待确认（真人运营试用未执行） | ① 授权 L1；② 逐卖点复核与采样；③ 真人轮次归档后重跑严格门禁 | `scripts/audit_case.py`、`apps/api/tests/test_case_readiness.py` |
| 11 | 2026-11-28 | 授权 L1 卖点级分类评测 | 原始 idea 的“模型分析仍在验证中” | 新增 `--dataset l1`，只把 manual + review_required=false + 非空说明的评论作为金标，按 claim_id/aspect_terms 输出逐卖点指标；无真实快照时实测返回 1 | **评测入口已验证，真实准确率未产生** | 授权 L1 与人工复核完成后先跑 rule，再按 ADR-0004 门槛评估 LLM | 待确认（模型实测未执行） | ① 导入授权 L1；② 完成人工金标；③ 生成绑定 snapshot_sha256 的评测报告 | `scripts/eval_stance_baseline.py`、`apps/api/tests/test_stance_eval.py` |
| 12 | 2026-11-28 | 授权 L1 确定性分层采样 | 路线图 A5：提升 n≥30 样本的审计性 | 新增 `plan_l1_sample.py`，按卖点 × 立场 × 发布月份、固定种子与 canonical 卡生成清单；不足时不补齐，星级/变体明确列为契约缺失 | **采样方法已验证，真实采样未执行** | 数据提供方另附星级/变体，运营按清单复核并保留种子与快照指纹 | 待确认（真人采样未执行） | ① 授权 L1 快照；② 生成采样清单；③ 按清单复核并回导 | `scripts/plan_l1_sample.py`、`apps/api/tests/test_l1_sampling.py` |
| 13 | 2026-11-28 | Claim-aware LLM 卖点评测 | 防止整条商品极性冒充卖点证据 | 新增 claim 上下文适配器、专用提示词指纹与缓存键；故障回退同卖点规则基线。Mock 测试覆盖上下文、缺术语拒绝、缓存隔离与回退不缓存；完整后端 361 测试通过 | **工程链路已验证，真实 LLM 调用未执行** | 凭据与授权 L1 到位后运行 `--dataset l1 --classifier llm`，对照 rule 并记录回退率 | 待确认（真实模型评测未执行） | ① 配置 LLM 三项环境变量；② 跑人工金标子集；③ 达标后再进生产判定链 | `apps/api/src/crosspilot_api/services/stance_llm.py`、`apps/api/tests/test_stance_llm.py`、`apps/api/tests/test_stance_eval.py` |

| 14 | 2026-11-28 | 开发进度、文档同步与原始 idea 对齐审计 | 用户要求先清点进度/改动/必要文件，再评估是否围绕原始 idea 开发 | 双自检实测 367 测试、9 来源校验、97 前端断言全绿；61 改 + 27 新增未提交；真实 L1/轮次/评测报告均为 0；严格完成门禁返回 1；浏览器结构检查确认真实/演示边界与门禁提示 | **工程与方法链已验证，真实案例与模型实测未完成**；文档旧口径已同步，不把商品级演示字段当卖点结论 | 保持当前实现，不新增偏离 idea 的功能；提交前再跑双自检，真实数据到位后执行采样、复核、运营轮次与模型评测 | 待确认（真人运营试用未执行） | ① 获取授权德国 L1；② 逐卖点复核并达到 n≥30；③ 真人运营/原型试用并归档；④ 生成规则/LLM 卖点评测报告 | `docs/status/STATUS.md`「二·补二」、`docs/devlog/2026-11.md` 第五十三轮 |

## 运营试用记录（待执行，不得视为已完成）

- [ ] 取得品牌授权评论导出或 Amazon 书面许可，按每个活跃卖点分别导入至少 30 条去重后、有明确支持或反对极性的德国 L1 评论；每条必须带可审计的 `authorization_ref`。
- [x] 公开页面候选因平台条款否决；自动提取原文与元数据已删除，未入库。
- [x] 本地运营试用表单已提供（`/history`），支持本地保存与 JSON 导出；填写、刷新恢复、清空已实测。新增完整性校验：空记录禁止导出，不完整记录禁止标记「运营已确认」，不完整草稿使用独立文件名；非法本地存储会自动降级为待确认。
- [x] 假设级验证轮次已提供：工作台按当前假设追加观察、决定、理由、下一步与负责人，历史页回看、导出并填入运营试用总结；第二轮追加不覆盖第一轮，未确认轮次不冒充真人试用。
- [x] 同组原型测试可结构化记录：参与者编号、多隔层/开放空间测试顺序、装什么、怎么取、哪里麻烦；工作台、历史页、JSON 导出与 SHA-256 归档同源，已确认时缺一不可。当前无真人原型记录。
- [x] 验证轮次可归档：`scripts/import_validation_rounds.py` 支持 dry-run、契约/隐私/确认完整性校验、按假设汇总与 SHA-256 不可变归档；重复导入不覆盖旧文件。归档加载额外拒绝跨文件重复 `round.id`，防止重复轮次计入 readiness。当前 `data/validation_rounds/` 无真人记录。
- [ ] 真实运营按每个活跃卖点保存并确认 `real` 轮次，引用同卖点真实 `review_id: source_url`，填写 `market=de` 并绑定当前 `l1SnapshotSha256`，导出 `crosspilot-validation-rounds.json` 后先 dry-run 再归档；单独的 `/history` 运营总结表不计入 readiness。
- [x] 真实案例完成审计已提供：`scripts/audit_case.py`、`/api/case/readiness` 与 `/history` 门禁面板统一检查授权德国 L1、溯源、模拟隔离、归属、人工复核、逐卖点 `n≥30` 和 `real` 场景运营确认；运营轮次必须引用同卖点真实 `review_id: source_url`，仅写 `claim_id` 不计入闭环。fixtures 模式不伪造结果，当前实测为 `blocked`，不得标记真实案例完成。
- [x] readiness 支持活跃卖点范围：CLI `--claim-id`、API 重复 `claim_id` 与历史页输入可只审计当前假设；自定义-only 案例不再被未活跃内置三项阻塞，活跃零样本与未归属评论仍阻止完成。
- [x] readiness 结论绑定证据版本：CLI JSON、API 与历史页返回/展示 `snapshot_sha256`；无已验证快照时为 `null`，避免审计状态与 L1 版本错配。
- [x] readiness 同时绑定运营轮次版本：对已校验轮次 `record_sha256` 排序聚合生成 `rounds_archive_sha256`，归档内容变化即指纹变化；无归档时为 `null`。
- [x] readiness 人工复核门禁已收紧：相关 L1 必须 `classification_method=manual`、`review_required=false` 且复核说明非空；规则低优先级、LLM 和缺说明的人工分类均保持探索性，不相关评论不进入偏好复核门禁。
- [x] 工作台可导出案例证据包 JSON：打包全部假设、证据原文、判定、跨来源对照、验证计划与本机轮次；演示包 `is_demo_data=true`，所有包 `market_effect_claim_allowed=false`。浏览器实测演示包含 3 假设、34 卡、3 组对照。
- [x] `/review` 提供本机 L1 人工复核队列：逐条修正立场、归属、相关性并填写说明，保存草稿、刷新恢复、导出可回导 JSON；`--versioned` 保留旧快照并加载最新已验证版本。授权范围从快照原样带入且不可修改，导出不得扩权。fixtures 模式不伪造复核卡。当前无真实授权 L1 可复核。
- [x] 复核队列支持按卖点筛选、原文/评论 ID/来源搜索与逐卖点进度计数；纯函数回归覆盖内置卖点、不相关评论、大小写关键词与来源链接搜索。
- [x] 复核草稿按 `l1_snapshot_sha256` 隔离：API 暴露最新已验证快照的 `record_sha256`，工作台案例包与复核 JSON 保留来源指纹；旧 query 级草稿不再加载，缺少指纹时保存/导出禁用。
- [x] 授权范围结构化：`authorization_scope` 至少包含 `internal_product_validation`，模型处理/赛事演示/公开展示分别声明；缺失或未知用途拒绝导入，范围纳入快照哈希。`data/snapshots/l1/` 默认不入公开仓库。
- [x] 授权 L1 快照记录输入文件 `input_sha256` 与稳定 `record_sha256`；同内容重复导入幂等，冲突覆盖拒绝，加载验哈希。当前无真实授权 L1 快照。
- [x] 授权 L1 支持人工立场覆盖：`stance` / `stance_note` 可纠正规则基线，保留规则票、一致度、分类方法与说明；快照、API 与卡面同源，外部文件不能伪造分类方法。填写 `stance` 时 `stance_note` 必填，缺失或清洗后为空拒绝导入。当前无已授权德国 L1 可复核。
- [x] 同卖点精确/近重复评论出现不同立场标签时不合并、不自动改票，导入器标记 `review_required=true` 并列出冲突 `review_id`；复核页在冲突解决前不默认视为已复核，避免假分歧。
- [x] 规则结果支持保守复核分流：仅强支持且无否定/正负混合可低优先级，其他结果建议人工复核；MARC 实测低优先级覆盖 5.9%、准确率 92.4%，但金标为整体星级而非卖点级标签，不构成自动接受或模型准确性证明。
- [x] 授权 L1 规则票按卖点术语选择相关从句：同一句“价格贵、隔层好”对 price/features 分别产生反对/支持票，相关从句占比与命中术语进入 `review_reasons`。未命中、未归属或未声明术语的自定义卖点回退整条并强制复核；卖点级规则未做真实金标评测，不声称准确性。
- [x] 自定义卖点可在 JSON 顶层用 `claim_terms` 声明术语范围；术语贯通快照哈希、API `aspect_terms`、卡面与复核回导 JSON。内置/未归属 ID、未使用术语、超长/空术语及同卖点不一致范围均拒绝导入。
- [x] 工作台可导出 `crosspilot-l1-import-template.json`，自动带入当前 query、`market=de`、内部验证用途和自定义关键词；模板 `cards=[]` 且授权字段留空，明确不可直接导入，补齐真实来源与评论后才可 dry-run。
- [ ] 使用 `scripts/plan_l1_sample.py` 生成逐卖点确定性分层采样清单，保留 `snapshot_sha256`、种子与不足状态；星级/变体由数据提供方另附。
- [ ] 使用 `scripts/eval_stance_baseline.py --dataset l1` 生成人工金标逐卖点评测报告；如启用 LLM，再运行 `--classifier llm` 并记录模型、提示词指纹与回退率。当前无真实报告。
- [x] 品牌数据请求包与运营试用执行包已准备（`docs/research/CrossPilot_证据_dim03_德国反馈获取路径.md` §3.6–3.8）；仅完成外包协作准备，不等于已取得数据或已执行试用。
- [ ] 邀请 1 位跨境运营或品牌负责人试用，记录日期、角色、试用场景与决定。
- [ ] 运营只看证据与出处，独立写下一个会改变上下架决策的卖点判断。
- [ ] 对存在分歧的卖点执行同组原型测试：多隔层版 vs 开放空间版；记录装什么、怎么取、哪里麻烦。
- [ ] 记录访谈原话、A/B 文案选择理由、样本偏差与仍未回答的问题。
- [ ] 由运营确认最终决定；未确认前一律写「待确认」，不以 Agent 推断代替。

| 字段 | 待填写 |
|---|---|
| 试用日期 / 运营角色 | 待执行 |
| 真实商品与市场 | 待授权：旅行收纳包 × 德国 |
| L1 来源与授权编号 | 待提供品牌授权导出或 Amazon 书面许可 |
| 改动过的卖点决策 | 待执行 |
| 原型测试观察 | 待执行 |
| 运营最终决定 | 待确认 |
| 下一步与负责人 | 待执行 |
