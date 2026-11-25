# 交接状态页

**唯一事实来源。** 接手第一件事读本页，交班最后一件事更新本页。

> 本文件位于仓库内 `docs/status/`；文中 `apps/`、`docs/`、`data/`、`scripts/` 等路径均相对仓库根目录。
>
> 2026-11-25 工作区整理：GitHub 开发区统一为 `crosspilot/`，交接材料移至 `handover/`；本页后续项目状态仍需当值负责人按最新代码复核。
>
> 2026-11-26 托管状态：GitHub public 仓库 <https://github.com/SilverBullet-Yu/crosspilot>，main 已推送，CI 首跑 success。
>
> 2026-11-26 文档归位：交接材料自仓库外 `handover/` 迁入 `docs/`（status / checklists / requirements / research / reports），随仓库分发。

最后更新：2026-11-26（**GitHub 托管完成**：public 仓库创建并推送 main，CI 首跑 success；同日清理 SOTM 第三方参考图 6 张、QA 验收截图 12 张与失效调研过程稿 3 份；同步测试数 181、数据口径 42,273 / 66,332 / 67,565，关闭「创建 GitHub 仓库并推送」；上一轮 2026-11-25 交接区清理：V2.0 旧版 PRD/项目方案移入 `archive/`、设计迭代过程截图清除、许可原件补齐） ｜ 当值：待指派 ｜ 距提交截止（12-07 10:00）**11 天**

---

## 一、一句话现状

**双侧证据链已闭环且 real 场景全真实数据**：L3 监管语境（Safety Gate 519 条）+ **L3 贸易语境（Comext HS4202 中国→德国，2025 年 9.50 亿欧元）** + L2 中文侧（真实采集片段快照 + 双语检索式，中文查询 0→8 命中）+ 三状态判定 + 立场基线**双域评测**（餐厅 0.610 / 商品域 MARC 0.580，域偏置被数据证实）+ **LLM 立场抽取适配层就绪（待凭据实测）**。自检 **181 测试、9 来源合规全绿**。**剩余最高阻塞不变：德国 L1 零样本**；两个凭据型动作：知乎 Access Secret 申请与 LLM 端点配置（开发层均已就绪，凭据到位即实测）。

## 二、当前阶段

| 项 | 状态 |
|---|---|
| 阶段 | 演示就绪（fixtures 模式可完整跑通三场景）；真实数据侧待凭据与预跑 |
| 代码状态 | ✅ 检索、证据 API、演示状态、知乎适配器、立场基线、**前端多页工作台（AppShell 外壳 + 产品概览落地页 + /workbench 证据工作台 + 历史页，合规标识全保留）**、演示文档、LLM 立场抽取适配层（待凭据实测）、**ADR-0005 判定链（Wilson 区间/去重/四值状态机/两票聚合）**均实现并联调；❌ 反馈回填（P1）未实现 |
| 自检 | `bash scripts/check.sh` 五道全绿：ruff + mypy strict + **181 测试** + 结构校验（**9 来源**）+ 时间覆盖校验；前端另有 `bash scripts/check_web.sh`（**56 断言**：工作台三场景 + 落地页，~20s） |
| 数据区 | `data/sources/` **9 来源**：记录/评论级 **42,273** 行（主表口径 66,332；全部 CSV 行 67,565，三种口径见 `data/sources/README.md` §2.0）；`data/snapshots/` 已含真实采集快照 |
| 注册表 | **18 项**（第五轮新增 eu_comext），marc / usage_bielefeld / eu_comext note 已回填实测结论 |
| 开发环境 | 后端 8000 + 前端 3000 联调环境可用；知乎 capture 脚本已备（--dry-run 实测） |
| 版本控制 | **GitHub public 仓库已就绪**：<https://github.com/SilverBullet-Yu/crosspilot>，main 已推送（HEAD `a844366`，4 次提交 / 148 文件），CI 首跑 success；MARC 零跟踪且历史无残留；本仓库配置 `http.version=HTTP/1.1` 适配本机网络 |
| 提交窗口 | 12-05 10:00 开放，12-07 10:00 截止，逾期不可修改 |

## 三、数据区盘点

| 目录 | 层级 | 行数 | 年份覆盖 | 时间密度 | 可用性 |
|---|---|---|---|---|---|
| `eu_safety_gate/` | L3 | **3,255** | 2021–2026 六年 | 97.7% | ✅ 302/302 期完整 |
| `eurostat_isoc/` | L3 | 13,093 | 2021–2025 | 83.3% | ✅ 2026 源端未发布 |
| `openalex/` | L3 | 2,454 | 2021–2026 六年 | 56.2% | ✅ 每主题前 500 条；raw 25/25 页完整，可离线重建 |
| `amazon_reviews_2023/` | L1（美国市场） | 6,146 | 2021–2023-08 | 91.5% | ⚠️ 对德国不构成 L1（见 3.3）；已按稳定 `review_id` 去重 |
| `gerestaurant/` | BENCHMARK | 3,078 | —（语料无日期） | 不适用 | ✅ 已入库；**注意：数据原件取自同期 fork**（上游仓库不含标注数据），证据链见其 README |
| `eu_comext/` | L3 | 1,924 | 2021–2026 | 100%（6/6 年） | ✅ HS4202 中国→德国贸易；CN8 细目 API 不可得（bulk 未取） |
| `marc/` | BENCHMARK | 10,000 | —（语料无日期） | 不适用 | ✅ 德语商品评论金标；**研究许可（硬约束 2）**，不进证据卡 |
| `usage_bielefeld/` | BENCHMARK | 1,233（+25,292 span 标注） | — | 不适用 | ✅ 英德立场标注基准（ODC-By 1.0）；**公开件不含评论原文**，只有标注层 |
| `gdelt/` | L3 | 1,090 | 2021–2022 | **15.1%** | ⚠️ 见 3.1 |

### 3.1 GDELT 的使用禁令（务必先读）

`sort=datedesc` + `maxrecords=250` 使每窗只取末端 250 条，2023–2026 全缺，全表时间覆盖仅 15.1%。**禁止**用于趋势分析、跨时间比较、报道量级统计；**可以**用于验证检索式、取定性示例。详见 `data/sources/gdelt/README.md` §2。

### 3.2 Safety Gate 的使用提醒

Motor vehicles 占 1,504 / 3,255（46%），品类分析前必须先过滤。旅行收纳包近邻品类（Toys / Childcare / Chemical products / Clothing, textiles and fashion items / Hobby/sports equipment）合计 **519 条**（检索服务与测试以此为断言）。

### 3.3 Amazon Reviews 2023：美国市场 L1 试点

hf-mirror.com → 官方 CDN 分片直下路径已打通（SHA-256 逐字节一致），但数据集为 Amazon.com 全站、无 language/marketplace 列，**无法筛德国子集**（manifest `tier_caveat`）。德国 L1 唯一路径 = 品牌授权导出。

### 3.4 知乎快照区（`data/snapshots/`）

**`旅行收纳包.json` 已是真实数据**（`is_demo_data=false`）：转录自 2026-11-18 zhihu-cli v0.6.3 的真实采集（消耗 3/10 次搜索额度），引文/链接/AuthorityLevel/赞同数/时间戳逐字保留，溯源材料见 `../research/CrossPilot_证据_dim04_知乎实查记录.md` §4.1。收录 A/B/D 三条（发布日期 2026-11-11 / 2026-10-10 / 2026-07-29）；**C/E 两条无发布日期元数据暂不收录**（不以捕获日冒充发布日），待凭据重采补齐。演示撰写的样例已迁至 `apps/api/tests/fixtures/zhihu/`（测试专用）。real 场景前端与 API 已全部为真实数据，演示标识只剩 conflict/limited 两个演示场景。

## 四、下一步（按优先级）

| # | 事项 | 负责人 | 为什么是这个顺序 |
|---|---|---|---|
| 1 | **约访 1 位正在做德国站上架/改版的品牌运营** | 待指派 | 德国 L1 唯一路径，无接口可替代；其余一切都在等它或可并行 |
| 2 | **申请知乎 Access Secret → live 首跑核验端点 → 重采 C/E 片段补齐快照** | 待指派（需账号） | 自助生成于 developer.zhihu.com；先 `python scripts/capture_zhihu_snapshot.py --dry-run` 预检再真跑；响应结构若与文档副本不符需修订 `zhihu_client.py` 并回填核验记录；顺带补采缺日期元数据的 C/E 两条片段（真实快照演示已不阻塞于此） |
| 3 | ~~录制演示视频~~（**暂缓**：2026-11-21 用户指示不需要录屏脚本，专注开发；物料保留，提交窗口开启前再按 `docs/demo/录屏脚本.md` 恢复此项） | 暂缓 | 成片一致性要求不变：恢复录制时按演示说明第四节合规清单勾选并重跑两道自检 |
| 4 | **LLM 立场抽取实测**（开发层已就绪，等凭据） | 待指派（需 LLM key） | 适配层已实现（ADR-0004）：`.env` 配 LLM_API_BASE / LLM_API_KEY / LLM_MODEL 三项后 `scripts/eval_stance_baseline.py --classifier llm` 即可双域实测；对照靶 GERestaurant 0.610 / MARC 0.580，启用前提 = oppose recall 超规则基线；缓存可中断续跑，`--limit` 控成本 |
| 5 | 注册 Destatis / Comtrade / OpenAlex key / eBay keyset / DeepL key | 待指派 | 均免费无审批；eBay 补 2023-09 后时效缺口（卖家侧，只进企业假设栏） |
| 6 | 向官方确认知乎配额是否随参赛提升、Token 补贴细则 | 待指派 | 决定 live 模式可行性；实测搜索 10 次/日（手册称 5000） |
| 7 | ~~创建 GitHub 仓库并推送~~ ✅ 2026-11-26 完成：public 仓库已创建，main 已推送 | — | 关闭；CI 首跑 success，后续保持 main 绿即可 |

**算法工程子表（零训练 · 无凭据依赖；设计与六条对齐规则见 ADR-0005。**✅ A0–A6 已于 2026-11-22 第十轮落地，A7 可选项未做）：**

| # | 事项 | 为什么是这个顺序 | 成本 |
|---|---|---|---|
| A0 | **演示夹具扩卡迁移（ADR-0005 验证发现，必做）**：demo conflict/limited 从单卡（n=4/n=2）扩到 n≥30 分层模拟评论（星级/时间分层）；**三状态演示设计（对抗审查修正）**：conflict 15/15→`conflicting`（并排）、limited 21/30→`supported`（Wilson 下界 0.521 刚过线，「有限」=区间宽的量化表达）、real 场景→`insufficient`，三场景各演示一种状态；20/30（下界 0.488）跨阈值作边界测试用例；连带同步 `StanceBanner`（新增 conflicting 分支）/`EvidenceStance` 类型/演示说明/录屏脚本/`check_web.sh` 断言（state 拆分**不是向后兼容变更**，现状冲突→oppose） | R3 门禁（n<30→insufficient）会把两个演示场景全部打成 insufficient，不迁移演示叙事崩塌；三状态设计让判定公式化成果直接变成演示亮点且前端文案改动最小 | 2–4 小时含测试 |
| A1 | 契约先行，**按层级拆两处落点（对抗审查修正：判定级字段不进卡片 schema）**：①卡级字段进 `packages/contracts/evidence-card.schema.json` + `EvidenceCard` dataclass + 前端卡校验（`dedup` / `stance_votes` / `annotator_agreement` / `grade`+`downgrade_reasons`，全 optional，`additionalProperties:false` 拒绝未登记字段，三处同批改）；②判定级字段进包络 `EvidenceResponse` + 前端响应校验（`state` 唯一枚举 / `stance_interval` / `gate_status` / `recommended_tier`） | 判定是卡集合的函数，按 ADR 原文塞进每张卡会产生全卡 `state=null` 脏字段 | 随 A2 |
| A2 | 统计层 `services/stats.py`（新）：判定映射公式（**对抗审查修正后口径**）——门禁（**n=去重后有极性样本数**≥30 且 level=L1；insufficient 比例单独报告）→ Wilson 95% 区间（分母同门禁）→ support 下界>0.5 → `supported` / oppose 下界>0.5 → `refuted` / **support 区间与 oppose 区间重叠 → `conflicting`**（「区间含 0.5」判据在 20:10 主导场景误判，弃用）/ 否则 `insufficient`；公式与边界用例（20:10→insufficient、21:30→supported、15:15→conflicting）写入测试；+ 最小样本量门禁 + 功效分析注记 | 「证据不足从口径变公式」的核心；三项口径歧义已由对抗审查堵死 | 半天+测试 |
| A3 | 信号层 `services/evidence_dedup.py`（新）：近重复去重——L1 规模 ≤数百时用**精确字符 3-gram Jaccard 全对比 + 并查集聚类**（精确相似度值可入 provenance，~30 行；MinHash 近似留作规模化升级路径）；**短文本守卫（对抗审查新增）**：<20 字符不参与聚类 + 相似度阈值取高（0.85+，宁少合并 R6），短通用好评（"Sehr gut!"/"Super gut!"）误聚案例写入测试；**去重先于计数**（R2） | 精确值比 MinHash 估计更可信可追溯、实现减半；无守卫则短模板评论虚增一致性 | ~1 小时 |
| A4 | 证据层 `services/stance_aggregate.py`（新）：固定规则聚合，**两票制（对抗审查修正：原三票引用了不存在的「双语词表」标注器）**——`stance_votes {rule, llm}`，llm 凭据缺省时 `votes.llm=null`（R6 显式传播）；两票一致→该立场，分歧→`annotator_agreement=false` 推向 insufficient（R4），**不学权重** | LLM 与规则融合备胎；标注冲突≠证据冲突的纪律落点；两票制零新增标注器成本 | ~1 小时 |
| A5 | L1 人工小样本分层采样清单（星级/时间/变体分层；采样框入 provenance） | 采样纪律提升 n=30 证据价值，服务待办 #1 的降级路径 | 0.5 小时 |
| A6 | 叙事批（纯文档）：GRADE 定位、AVeriTeC 四标签口径、评级状态机（Watch/NM）、SR 11-7 治理、不对称损失、选择偏差声明、「挖掘管输入 / NLP 管解读 / 金融管决策」三层定位句 → 演示说明 8.2/8.5 | 零成本可信度加分，冻结前文档批一并做 | 2–3 小时 |
| A7 | （可选，时间富余）Apriori 关联挖掘：L3 hazard 共现 → 自动生成右栏待验证问题（**旁路通道，绝不进判定管道**，ADR-0005 R5） | 问题栏从手写变 mined；不依赖凭据 | ~1 天 |

**判定链实数据跑通（2026-11-22 验证补充）**：德国 L1 到位前，A0–A4 判定链用**美国市场 L1 试点**（`amazon_reviews_2023`，去重后 6,146 行已在库）做端到端真实输入（去重→抽取→区间→门禁→四状态），避免判定链沦为只被测试覆盖的死代码；对外叙事遵守 manifest 既有 `tier_caveat`（美国试点≠德国结论，不进德国偏好判定）。

凭据到位后同框架启用（ADR-0005 决策 7）：辩论式 prompt 升级 `stance_llm` → 零样本 NLI 归属替换关键词启发式 → X-Stance 第三域评测 → `--classifier ensemble` 固定聚合档。Roadmap（不实现）：完整 Black-Litterman、conformal 弃权、PSI 漂移监测、启发式异常标记。

**边界调整（按各轮成果累计修订）：**
- 前端「卡片→假设归属」为关键词启发式：conflict 场景一张卡因含「Platz」归入容量假设（功能组显示空）——口径已写入 `docs/demo/演示说明.md` 第七节，属已知行为非缺陷；契约允许后端加归属字段时可替换。
- 中英文查询互不覆盖：中文词在英文 L3 库零命中、英文词在中文快照零命中——是诚实行为；查询词翻译/双语检索式列为可选增强，不承诺。
- fixtures 与真实 API 存在合理差异（real 场景夹具 3 张 L3 卡 vs API 对中文词 0 张 + l2_notice 降级条）——演示说明已文档化，两种模式都是正确行为。
- 录制成片发布前必须重跑 `check_web.sh` + `check.sh`，确认成片与最终代码一致。
- **叙事层调整（第六轮，纯文档）**：对外定位统一为「出海卖点的上线前尽职调查」（演示说明 8.1）；新增相关工作对比（8.2）、判定→建议动作映射（8.3）、术语约定（8.4，不以 "vibe selling" 指代本项目）与高频质疑预案（8.5）。**L1 零样本对外按 problem statement 口径处理**（8.5），不再作为纯缺陷叙述。闭环下游以验证日志留痕：新增 `docs/demo/validation_log.md`。镜 2 旧旁白「L2 演示数据」表述与真实快照现状矛盾，已修正（成片一致性要求）。代码与数据行为零变更。
- **开发优先级调整（第八轮，2026-11-21 用户指示）**：录屏/演示视频暂缓，工作重心转向代码与数据开发（LLM 立场抽取先行）；演示物料保留不删，提交窗口开启前恢复录制即可。
- **零训练硬约束（2026-11-22 用户确立）**：全链路不训练任何模型参数——规则基线 + LLM 零样本推理 + 纯统计。含拟合成分的方案一律替换或排除：弱监督权重学习 → 固定规则投票；孤立森林 → 零参数启发式；排除 MTAB / 少样本跨语言增强 / 微调 NLI / 完整 Snorkel / 任何 fine-tune。LLM API 调用属推理不属训练。「零训练」本身入叙事（可审计 / 可复现 / 不受 L1 稀缺制约 / 部署轻），见 ADR-0005。
- **方法组合契约（ADR-0005，2026-11-22）**：多领域方法（统计区间 / 去重 / 聚合 / 评级状态机 / 动作分级）统一挂接既有 evidence-card 契约，不新造框架；六条对齐规则（单一枚举 / 去重先于计数 / 置信语义分字段 / 标注冲突≠证据冲突 / 旁路防火墙 / 降级显式传播）约束全部新增字段与阶段顺序。
- **ADR-0005 验证（2026-11-22，代码现状核对）**：方案主体成立——契约挂接已被 l2_cards/l2_notice 包络扩展实证、零训练与代码现状一致、成本估计合理、AVeriTeC/GRADE/Wilson/SR 11-7 引用无误。三项修正回写子表：①演示夹具单卡（n=4/n=2）与 R3 门禁直接冲突，新增 A0 扩卡迁移；②state 映射公式与 insufficient 分母口径留白，A2 描述已补全；③A3 在 L1 小样本下用精确 3-gram Jaccard 替代 MinHash 近似（精确、可追溯、实现减半）。另确认：state 四值拆分**不向后兼容**（现状冲突→oppose），需 schema→dataclass→出参→前端→check_web.sh 一次性同步。
- **判定链行为变更口径（2026-11-22 第十轮）**：判定状态从三值改四值（冲突不再=oppose）；单条 support 卡不再判 support（门禁 n≥30，公式化 insufficient）；demo 夹具扩卡且 fixtures 由脚本同源生成（改 demo 数据后必须重跑 gen_web_fixtures.py）；「样本量未知·有偏差风险」标注在扩卡 demo 中不再出现（全部卡 n=1），相关验收口径已迁移。美国 L1 试点清单仅供方法演练，不得写入德国偏好结论。
- **ADR-0005 对抗性审查（2026-11-22 第二轮，实现前堵漏）**：进度核实 A0–A7 全部未开始（git 仅 v0 提交，工作区纯文档改动），check.sh 实测 117 测试全绿、9 来源合规，STATUS 事实声称属实。四项实质修正回写子表：④A4 三票制引用了不存在的「双语词表」标注器 → 改两票 {rule, llm}（llm 缺省 null，R6）；⑤A1 判定级字段（state/stance_interval/gate_status）层级错位 → 拆分包络落点，不进卡片 schema；⑥A2 conflicting「区间含 0.5」判据在 20:10 主导场景误判 → 改两份额区间重叠判据，边界用例（20:10→insufficient / 21:30→supported / 15:15→conflicting）入测试；⑦A2 门禁 n 口径统一为去重后有极性样本数。A0 目标映射升级为三状态演示设计（conflict→conflicting / limited 21:30→supported / real→insufficient），前端文案改动最小。A3 增短文本守卫（<20 字符不聚类、阈值 0.85+）。
- **前端多页化口径（2026-11-22 第十二轮，用户给定目标设计图）**：场景深链从 `/?scenario=…` 变为 `/workbench?scenario=…`（落地页自动跳转兼容旧链）；check_web.sh 断言 URL 随之修改（断言逻辑未动，42→51 条）；组级假设标签从判定词改构成词「支持 / 反对并存」等（组级仍是布尔并集展示口径，判定唯一出口不变，ADR-0005 R1 不受影响）；产品概览落地页含自撰演示内容（卖点假设/支持/反对观点卡），全部带「模拟示例」标识、不含任何真实数据表述；工作台节头统计瓦片为**卡面计数**（含演示场景未去重卡），判定样本口径仍以横幅可追溯小字行（去重后 n）为准，两者并存不冲突。

## 五、已知阻塞与解除条件

| 阻塞 | 严重度 | 解除条件 |
|---|---|---|
| **德国消费者一手反馈零样本（L1）** | **最高** | 品牌方提供德国站反馈导出（含站点、时间、样本量字段） |
| 知乎 live 端点响应结构未核验（无凭据） | 中 | 申请 Access Secret 后 export → capture 脚本首跑核验；不符则修订 zhihu_client.py。无凭据报错路径已实测（exit 2 显式指引，不触网不耗额度）；**演示已不依赖此项**（真实快照已就位） |
| LLM Token 补贴细则不明 | 中 | 向官方确认；**开发层已就绪**（ADR-0004：适配器 + 评测 `--classifier llm` + 缓存），凭据到位即可双域实测，期间立场抽取用规则基线（已建） |
| 知乎 API 实测额度 10 次/日 | 中 | 官方确认参赛额度；Demo 默认 snapshot（ADR-0002） |
| GERestaurant 许可书面确认（上游无 LICENSE 文件） | 低 | 正式商用前向作者确认；CC-BY-4.0 依注册表既有登记 |
| GDELT 时间覆盖稀 | 中 | 改用官方 ngrams 数据集或细化窗格（非本阶段阻塞） |
| Destatis 匿名取数被重定向 | 低 | 注册 GENESIS 账号（genesis.destatis.de） |
| ~~HF 本机不可达~~ | 已解除 | hf-mirror→官方 CDN 路径（余限制：datasets-server 不代理） |
| ~~知乎适配器零实现~~ / ~~立场抽取零实现~~ | 已解除 | 双路径适配器 + 规则基线落地 |

## 六、成果清单（第三轮～第七轮）

| 模块 | 内容 |
|---|---|
| 知乎 L2 侧（第三轮） | `zhihu_client.py`（Bearer+时间戳鉴权、配额守卫 30001→QuotaExhaustedError、PII 剔除先于截断、摘录≤300 不落全文、作者匿名化）+ `zhihu_snapshot.py`（快照 schema 校验、显式降级）+ capture 脚本（--dry-run 预检）+ 21 测试 |
| 包络扩展 | `/api/evidence` 追加 `l2_cards` / `l2_notice`（向后兼容，/demo 端点零改动）；L2 不进 resolve_stance 输入（含对抗断言） |
| 前端 L2 | 右栏「中文侧经验（L2·知乎）」小节：降级黄条 + 卡渲染 + 契约校验占位，三夹具镜像新包络 |
| 立场基线 | `stance_baseline.py`（~170 词词典、否定窗口翻转、ß/ss 与 ae/oe/ue 折叠、比较级负面规则、RuleHit 可解释）+ GERestaurant 全量评测（accuracy 0.610 / 宏 F1 0.533）+ 固定子集指标下限回归（13 测试） |
| 演示物料 | `docs/demo/`：演示说明（Runbook+合规自查）、录屏脚本（7 镜 170 秒）、三场景截图（目检确认）；`scripts/check_web.sh` 冒烟（37 断言 / 15s，未并入 check.sh） |
| 数据 | gerestaurant 四件套入库（fork 溯源如实记录） |
| 真实快照（第四轮） | 知乎快照换真实数据：11-18 CLI 采集片段 A/B/D 转录入库（引文/链接/时间戳逐字保留、作者匿名化），演示样例迁入测试夹具，real 场景前端/API/截图全部真实化，新增真实快照守护测试 |
| 数据源扩展（第五轮） | eu_comext 1,924 行（HS4202 中国→德国，月度求和与年度逐位互验 + 双数据集交叉校验）；marc 10,000 行（mteb 镜像路径，SHA-256 全留痕，域退化如实入档）；usage_bielefeld 查证入库（LREC 2014 / ODC-By 1.0，三判据精确命中，公开件不含原文如实声明）；双语检索式（中文查询 0→8 命中，词表对齐库内实测词频） |
| 叙事闭环（第六轮，纯文档） | 演示说明第八节：定位句（上线前尽职调查）／相关工作对比（逐行来源性质标注）／判定→建议动作映射／术语与引用规范／高频质疑预案／roadmap 一句话；录屏脚本改 8 镜 ≤180 秒（新增镜 7 验证日志闭环镜，镜 2 旁白按真实快照口径修正）；新增 `docs/demo/validation_log.md`（假设→判定→建议→决定→下一步留痕，首行用 2026-11-18 真实验证过程回填）；代码与数据零变更 |
| 文档统一（第七轮，纯文档） | 全库文档对齐至当前事实：README（硬约束 5 条、目录地图补 data/sources 与 docs/demo、自检含 check_web.sh）；data/sources/README.md（补 marc/eu_comext 来源行、合计 66,394 行及口径注、Motor vehicles 修正 1,504/3,255、补域退化与 CN8 缺口行、脚本表补全、章节重号修复）；CONSTRAINTS 层级表（L1 美国试点标注、L3 补 Comext）；演示说明前置（9 来源）；根目录数据源清单入库状态回填；devlog 补第六轮记录；工作区整理（docx 重命名）。**一致性审计收尾**：演示文档 real 场景「演示卡」旧口径修正（演示说明 §三表与 §七条 3、录屏脚本镜 3——real 夹具实测 6/6 全真实）；仓库外引用修正（STATUS §七 根目录清单路径、research/ 注记、快照 README 同步）；§二/§六 轮次指代明确化；README 自检描述去硬编码测试数。代码与数据零变更，check.sh + check_web.sh 全绿 |
| LLM 立场抽取适配层（第八轮，开发） | `services/stance_llm.py`：OpenAI 兼容 chat/completions 适配器（LLM_API_BASE/KEY/MODEL 三项齐备才可用），JSON 契约强制（stance 三类口径对齐 + reason 必填可解释），运行时故障逐条回退规则基线并显式标记，输入守卫 ≤300 清洗摘录、空文本短路、超长不触网；eval 脚本重构为可插拔 classifier（rule 模式报告逐字节不变，0.610/0.580 复现），新增 `--classifier llm`（磁盘缓存 data/sources/_eval_cache/ 可中断续跑、`--limit` 成本守卫、回退率统计入报告、报告写 llm_baseline_eval.md 不覆盖规则基线报告）；14 个新测试全离线（MockTransport）；ADR-0004；config 增 llm_* 三项 + .env.example 同步。**本机无凭据未做真实调用核验**（如实声明），凭据到位后零改动实测 |
| 公开上传准备（2026-11-22，第九轮） | 安全隐私审计全干净（无密钥/无真实邮箱/无路径泄露）；**MARC 从全部 git 历史移除**（禁再发布，filter-repo 重写，本地凭 raw 离线还原且 0.580/0.530 复现）；MIT LICENSE；多余文件与缓存清理（回收站）；README 公开化（简介配图 + 克隆须知 + 许可与数据节）；**fresh clone 冒烟抓到 L3 URL 隐藏依赖并修复**——克隆后 CI 同款三道全绿（117 测试）；分支统一 main |
| 算法工程规划（2026-11-22，文档） | 三领域（NLP / 量化金融 / 数据挖掘）可迁移方案收敛为统一框架写入 **ADR-0005**：五段管道+两横切+旁路、统一数据模型、六条对齐规则、**零训练硬约束**、代码落点与执行子表（A1–A7）入「下一步」；代码与数据零变更 |
| **判定链全量落地（2026-11-22，第十轮开发）** | **A2** `services/stats.py`（Wilson 95% 区间 + 门禁 + 决定线 decisive_share + 功效注记；对抗审查 C3/C4 修正口径：冲突=两份额区间重叠、门禁 n=有极性样本）；**A3** `services/evidence_dedup.py`（精确 3-gram Jaccard 全对比 + 并查集 + 短文本守卫 <20 字符 + 阈值 0.85 宁少合并）；**domain** `DecisionState` 四值（supported/refuted/insufficient/conflicting）+ `decide()` 管道（L1 过滤→去重→计数→门禁→区间→映射，R2 顺序内嵌不可绕过）+ 卡级字段（dedup/stance_votes/annotator_agreement/grade/downgrade_reasons）+ `stance_of_card` 承接单卡归一；**A4** `services/stance_aggregate.py` 两票制 {rule, llm}（C1 修正；llm 缺席 R6 显式传播，分歧→insufficient R4）；**A1** 契约分层落地（卡级进 schema+dataclass+前端校验；判定级 DecisionOut 进包络——C2 修正）；**A0** demo 扩卡（conflict 15:15+2 重复摘录→conflicting、limited 21:9→supported，30 条手写互异德语评论）；前端四值同步（DecisionState/StanceBanner 四键+判定可追溯小字行/TS 侧 Wilson 镜像 fallback/hypotheses 组级展示口径）；**夹具同源生成** `scripts/gen_web_fixtures.py`（fixtures=后端响应快照，消除漂移）；**A5** `scripts/build_l1_sample_frame.py`（美国试点星级×时间分层 30 条精确达标，tier_caveat 入清单）；**A6** 叙事批（演示说明 8.2.1 三层定位/AVeriTeC 收紧/GRADE 如实定位、8.5 新增 5 条质疑预案、2.2-2.4 验收清单重写、录屏脚本扩卡注记、validation_log 第 2 行闭环留痕）；**测试 117→169**（test_stats/test_dedup/test_aggregate/test_decision 边界用例 20:10→conflicting、21:9→supported、R2 端到端黄金用例「30 条复制→门禁拦下」）；check_web 37→42 断言 |
| **前端统一设计系统（2026-11-22，第十一轮开发）** | 布局四落地：`main.css` 全量重写为 **tokens 化设计系统**（灰阶三层 bg/panel/line、唯一品牌强调色 --accent、统一 6px 圆角、字阶 11/12/13/15/17、tabular 数字、两级间距节奏 8-12/20、全交互元素 hover 态）；**结构**：三栏平铺 → 判定仪表带（深色锚点，三态=左边框+标题色，可追溯小字保留）+ 左假设导航（sticky 紧凑行）+ 证据分节面板（支持/反对中缝线对照，证据卡→32px 行式）+ 附录两列（L2 知乎 + 待验证问题与节同形态）；**合规不动**：三态色系统、演示卡斜纹底+角标、`?scenario=` URL、六必现字段、契约占位——**全部组件 DOM 与类名零变更，check_web.sh 42 断言零修改全绿**；设计依据：Awwwards SOTM 三站气质借鉴（Dropbox 色块分类学/Anime.js 蓝图溯源/Terminal 克制排版）+ 8 灵感站实测（Siteinspire/Mobbin/Refero 等单点缀色·灰阶三层·hover 纪律），预览稿与过程稿已随 2026-11-25 交接区清理移除；SOTM 第三方参考图与 QA 验收截图已于 2026-11-26 清理 |
| **产品级多页工作台改版（2026-11-22，第十二轮开发）** | 用户给定目标设计图（产品工作台 + 左右布局），两轮预览稿后落地：①**多页外壳** `AppShell.vue`（侧栏：teal logo + 2.0 徽标 + 我的工作空间卡（可折叠 64px 图标栏）+ 三项导航 产品概览/卖点验证工作台/历史验证项目 + 底部实验室语块与「极客松演示版本 MVP」徽标；顶栏：面包屑 + 「演示模式 · Mock 数据」chip + 用户位）；②**产品概览落地页** `/`（hero 卖点之问 + 「一次卖点验证，如何发生」模拟示例卡 + 四步方法 + 判定→动作 CTA，品牌色切换 teal `#087f75`，演示内容全带「模拟示例」标识）；③**工作台迁 `/workbench`**（工具行=场景切换+产品×市场检索；判定带 meta 简化，数据模式/来源/生成时间移侧栏底部；节头统计瓦片 支持/反对/语境三格计数，组头黑块计数取消；**空组不再渲染占位**，黄底空状态卡承担空态；未归属证据 `<details>` 默认收起；证据卡来源链接单行域名化+完整 URL 进 href，每卡合规长文案收进侧栏页面级提示条一处）；④**历史验证项目 `/history`** 诚实空态（演示构建不持久化，不虚构数据）；⑤**语义修正**：组级假设标签改构成词「支持 / 反对并存 / 有一手支持 / 缺 L1 一手反馈」（`hypotheses.ts` STATUS_META），与判定带结论词区分，消除 limited 场景红绿打架；结论词统一 `useEvidence.DECISION_LABEL`；⑥**兼容**：旧深链 `/?scenario=…` 在落地页自动跳 `/workbench?scenario=…`；⑦ check_web.sh **42→51 断言**（URL 改 `/workbench` + 9 条落地页断言），51/51 全绿；三场景截图重拍进 `docs/demo/screenshots/`（新增 landing.png），演示说明/录屏脚本 URL、左中右栏措辞、卡底合规说明位置、组级 pill 口径全部同步；**合规不动**：三态色、斜纹+角标、六必现字段、契约占位、深色判定带唯一锚点、`?scenario=` 语义 |
| **全应用统一设计规范 + 判定带仪表化（2026-11-23，第十三轮开发）** | 用户指令「整个应用的样式都要有统一的规范和风格」+ Awwwards SOTM 检索（31 站筛 8 候选，Terminal Industries/Anime.js/Oryzo/Kriss.ai 等模式提炼）后落地：①**统一规范入 tokens**：`main.css` 头注释扩为全应用规范（色彩：teal 只作品牌色、三态语义专用绿/红/黄、模拟示例语境一律橙；圆角两级 12/6；徽标三形态 status-pill/badge/tag 不混用；字阶 11/12/13/15/17/22/42；交互纪律 hover+全局 `:focus-visible`）；修正真实不一致：落地页 tag--ok 原 teal 底 → 统一三态绿（tag--conflict 删除，ACTIONS「证据冲突」改 tag--bad 红）；②**判定带仪表化**（Anime.js 刻度盘 + Oryzo 测量手柄语言）：新组件 `IntervalGauge.vue`（纯 SVG 零依赖，band/plain 两色板一份几何）——判定带 trace 文字行下新增 Wilson 区间标尺（支持绿/反对红 whisker 跨决定线 0.5，冲突=重叠、有限支持=下界刚过线、real=空轨道+门禁提示），trace 文字保留（断言依赖）；③**判定公式唯一出口**：`useEvidence.decideFromVotes` 导出（fallbackDecision 重构为调用它），工作台兜底与落地页演示器共用一份口径；④**落地页「样本量→判定」交互演示器**（Terminal ROI 计算器模式的诚实版）：滑块 n/k 实时跑产品真实公式，三个 `test_decision.py` 同款真实边界用例预设（15:15/21:9/9:21），带「模拟示例 · 公式为产品真实口径」标识、零编造数字；⑤**FAQ 手风琴**（`<details>`，4 条 = 演示说明 8.5 质疑预案）；⑥**四步方法升级编号大卡**；⑦ check_web **51→56 断言**全绿；四张演示截图重拍（landing 新增验收小节 2.0 + 三场景补标尺验收条目）；**合规不动**：三态色/斜纹角标/六必现字段/契约占位/深色判定带唯一锚点 |
| **启用前清单逐项核对 + 许可原件补齐（2026-11-23，第十四轮）** | 按 `../checklists/CrossPilot_接入数据与启用前操作清单.md` 逐项核对（详见 devlog 当日条）：①修复两缺口——`data/licenses/` 由空目录补为 7 份许可原件 + README 索引（CC0/Apache/CC-BY 官方文本直存，ODC-By/Eurostat/GDELT 官方页留痕，Amazon 学术许可从 marc raw `_LICENSE` AST 提取），第十二轮新增的 landing.png 补 git add；②核验通过：manifest↔REGISTRY 层级 9/9 一致、Safety Gate 519 品类过滤、GDELT/BENCHMARK/快照降级/混排/配额/前端强制项/署名/marc 出库全部有结构或断言守护；③阻塞如实标注：B1 四项凭据未配置（.env 不存在），路径 B live 重采、LLM live 首跑核验均待凭据；路径 A 无新源待接、路径 C 第十三轮已合规执行。代码与数据行为零变更，双自检复跑全绿 |
| **GitHub 公开托管（2026-11-26）** | 创建 public 仓库 `SilverBullet-Yu/crosspilot` 并推送 main（4 提交 / 148 文件）；CI 首跑 success；移除 `provenance_resume.csv` 空壳并同步 manifest / README 的缺口申报（`a844366`）；本仓库配置 `http.version=HTTP/1.1` 以适配本机网络 |

提交署名 Ziyi Shen + Boyu Chen；提交前 `bash scripts/check.sh` 与 `check_web.sh` 必须全绿。

## 七、交接必读

| 文件 | 作用 |
|---|---|
| `README.md` | 环境、目录地图、协作约定 |
| `docs/CONSTRAINTS.md` | **五条硬约束 + 赛事合规红线，改代码前必读** |
| `docs/demo/演示说明.md` | **演示 Runbook 与合规自查清单，路演前必读** |
| `docs/demo/validation_log.md` | 验证闭环留痕：假设→检索→判定→建议→决定→下一步 |
| `data/sources/README.md` | 数据区总索引 |
| `data/sources/<source>/README.md` | 单源字段、许可、约束、复现命令 |
| `data/snapshots/README.md` | 快照区合规状态与预跑替换步骤 |
| `docs/adr/` | 设计决策；ADR-0002 快照模式、ADR-0003 数据区与中断恢复、ADR-0004 LLM 立场抽取适配层、ADR-0005 多领域方法组合与对齐契约（零训练） |
| `docs/devlog/` | 创作真实性佐证，赛事核验用 |
| `../checklists/CrossPilot_接入数据与启用前操作清单.md` | 接入新数据源、从演示态切换到投入使用前的逐项核对 |
| `../research/CrossPilot_证据调研清单_2026-11-18_回填版.md` | P0 取证现状（2026-11-18 快照，P0 结论仍成立） |
| `../requirements/data/CrossPilot_2.0_数据源与交付形式清单.md` | 数据源许可、优先级与交付规格 |

> 注：上表所列清单与调研文档均位于 `docs/` 内；§3.4 的取证材料位于 `../research/`。

## 八、数据区操作速查

```
# 五道自检（提交前必跑）
bash scripts/check.sh

# 前端冒烟（录屏/提交前必跑，56 断言约 20s：工作台三场景 + 产品概览落地页）
bash scripts/check_web.sh

# 从本地 raw 重建主表，零网络请求
.venv/Scripts/python.exe data/sources/_scripts/rebuild_from_raw.py

# 抓取中断后只补缺失期次，可反复运行
.venv/Scripts/python.exe data/sources/_scripts/resume_safety_gate.py

# Amazon Reviews 试点（镜像路径，中断可续）
.venv/Scripts/python.exe data/sources/_scripts/fetch_amazon_reviews.py

# 知乎快照预跑（凭据经 shell 导出——.env 只是记录模板，脚本不自动加载；无凭据真跑 exit 2 显式报错；先预检再真跑）
export ZHIHU_ACCESS_SECRET=<secret>
.venv/Scripts/python.exe scripts/capture_zhihu_snapshot.py --dry-run
.venv/Scripts/python.exe scripts/capture_zhihu_snapshot.py

# 立场基线评测（全量 GERestaurant；--dataset marc 含两域对照）
.venv/Scripts/python.exe scripts/eval_stance_baseline.py

# LLM 立场抽取双域实测（需先导出 LLM_API_BASE / LLM_API_KEY / LLM_MODEL；--limit 控成本）
.venv/Scripts/python.exe scripts/eval_stance_baseline.py --classifier llm --limit 200

# 联调：后端 8000 + 前端 3000
.venv/Scripts/python.exe -m uvicorn crosspilot_api.main:app --app-dir apps/api/src --port 8000
cd apps/web && npm run dev
```

新增数据源时必须同时做三件事，缺一则 `check.sh` 红灯：在 `services/datasets.py:REGISTRY` 登记；产出四件套（README / 主表 / provenance / manifest）；覆盖不完整或存在截断时在 manifest 与 README 双向声明（基准语料用 `corpus_type: benchmark` + `time_coverage_applicable: false` 声明）。
