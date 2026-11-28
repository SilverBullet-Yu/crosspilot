# ADR-0005 多领域方法组合统一于证据卡契约，全链路零训练

状态：已接受（规划态——契约与边界锁定，代码未实现）｜ 日期：2026-11-22

## 背景

为加固三个可信度短板——立场基线 0.610/0.580 的域偏置、「证据不足」缺量化判据、卡片→假设归属为关键词启发式——对三个领域做了可迁移方案调研：NLP（GRADE 证据分级、AVeriTeC 四标签判定、零样本立场抽取与 NLI、论证挖掘）；量化金融（Wilson 区间与样本量门禁、评级状态机、SR 11-7 模型治理、不对称损失与分级下注）；数据挖掘（分层采样、MinHash 去重、弱监督聚合、关联规则、漂移监测）。需回答：这些方法能否放进同一框架，之间如何传递信息、如何对齐。硬约束（用户确立）：**全链路零训练**——不训练任何模型参数，无 GPU、无金标规模数据、距冻结点 12-03 与提交截止 12-07 时间有限。

## 决策

1. **组合骨架 = 既有契约，不新造框架。** 所有方法挂到 `packages/contracts/evidence-card.schema.json` 与既有管道（检索→证据卡→判定→建议）上，形式一律为「加 optional 字段 + 插管道阶段」。学术原型即 AVeriTeC/FEVER 的「声明→证据检索→判定」三段式管道；本项目在首段插数据挖掘纪律、尾段插金融治理。此前 l2_cards/l2_notice 的包络扩展已验证该挂接模式向后兼容。

2. **五段管道 + 两个横切 + 一条旁路：**

```
采集            信号                  证据                        判定                    行动
分层采样 ──► MinHash去重 ──► 立场抽取(规则/LLM/固定聚合) ──► Wilson区间+样本量门禁 ──► AVeriTeC四状态 ──► 动作分级
   │             │                  │                            │                     │
   └采样框──► provenance      仅 L1 进判定管道               冲突检测并排           GRADE 降级理由(静态)   8.3 映射

横切1  NLI 归属：卡片↔假设 的归属字段（写回契约，替换关键词启发式；待 LLM 凭据）
横切2  时间口径：全部卡片统一「发布日期」，缺失显式 unknown（C/E 片段教训入法）
旁路   Apriori 关联挖掘(L3 hazard 共现) ─► 问题对象 ─► 右栏【防火墙：绝不进判定管道】
```

3. **统一数据模型**（证据卡扩展字段，全 optional）：

| 段 | 字段 | 生产者 → 消费者 |
|---|---|---|
| 信号 | `dedup {cluster_id, dup_count, is_canonical}` | MinHash → 计数器 |
| 证据 | `stance_votes {rule, llm, lexicon}`、`annotator_agreement` | 三标注函数 → 聚合器 |
| 判定 | `stance_interval {lo, hi, n}`、`gate_status` | Wilson → 状态机 |
| 判定 | `state ∈ {supported, refuted, insufficient, conflicting}` | 状态机 → 全下游（**唯一枚举**） |
| 行动 | `recommended_tier` | 状态机+区间宽度 → 8.3 映射 |
| 上下文 | `grade`、`downgrade_reasons[]`（仅 L2/L3） | GRADE → 展示层 |

4. **六条对齐规则**（约束全部新增字段与阶段顺序）：
   - **R1 单一枚举**：全系统只有 AVeriTeC 四值一个状态枚举；任何方法输出要么映射进它，要么不进判定管道；聚合层不得发明第五状态。
   - **R2 去重先于计数**：立场计数 k/n 必须基于去重后的独立证据单元；管道顺序固定为采样→去重→抽取→计数，反序则区间有偏。去重只合并相同立场，相同或近似文本下的支持/反对不得互相吞并。
   - **R3 置信语义分字段、不合并**：`stance_interval`（统计）、`annotator_agreement`（投票吻合）、`grade`（GRADE 证据质量）三种「置信」禁止加权成一个数；判定按固定次序消费：门禁（grade=L1 才可判定）→ 区间 → 冲突。
   - **R4 标注冲突 ≠ 证据冲突**：标注器（规则 vs LLM）对同一文本分歧 = 标注器不确定性，进 `annotator_agreement` 并推向 insufficient；两个独立来源相反 = `conflicting`（并排展示）。避免 AVeriTeC 文献中的 Conflicting→NEE 误判模式。
   - **R5 旁路防火墙**：关联挖掘产出的是问题对象不是证据卡；源自 L3，受硬约束 1 管辖，绝不进 `resolve_stance`（与「L2 不进判定输入」同源纪律）。
   - **R6 降级逐层显式传播**：LLM 故障→`votes.llm=null`+回退标记；去重阈值宁少合并（区间变宽=诚实）；任何一段禁止静默吞失败（ADR-0002 决策 4 同源哲学）。

5. **零训练硬约束。** 全链路不训练任何模型参数。两处原方案含拟合成分，替换如下：弱监督聚合（Snorkel 式权重学习）→ **固定规则投票 + 分歧降级**（每票来源可解释）；异常检测（孤立森林）→ **零参数启发式**（MinHash 复用找复制粘贴、好评率/长度阈值、重复 n-gram 频次）。排除清单：MTAB 跨语言迁移、少样本跨语言增强（Hardalov）、微调 NLI、完整 Snorkel、任何 fine-tune/LoRA。澄清：LLM API 调用属推理不属训练，ADR-0004 的 `stance_llm` 适配层不受本约束影响。「零训练」同时是叙事资产：可审计（RuleHit+区间可读）、可复现（无种子无波动）、不受 L1 稀缺制约、部署轻。

6. **代码落点与顺序**（合计约 1.5–2 天含测试，冻结点 12-03 前收口）：

| 序 | 落点 | 内容 |
|---|---|---|
| 1 | `packages/contracts/evidence-card.schema.json` | 决策 3 字段全部 optional，随首个 service 落地一并提交 |
| 2 | `services/stats.py`（新） | Wilson 区间 + 最小样本量门禁 + 功效分析注记 |
| 3 | `services/evidence_dedup.py`（新） | MinHash 近重复去重（R2 顺序纪律） |
| 4 | `services/stance_aggregate.py`（新） | 固定规则聚合 + 分歧降级（R4） |
| 5 | `domain/evidence.py` | 状态机消费新字段；黄金用例显式覆盖 R4 区分 |
| 6 | `routers/evidence.py` | 包络扩展（向后兼容） |
| 7 | 测试 | 各段单测 + 一条端到端黄金用例；断言旁路与判定管道隔离（R5） |

7. **凭据到位后同框架启用**：辩论式 prompt 升级 `stance_llm`（目标 oppose recall）；零样本 NLI 归属替换关键词启发式（STATUS 已预留替换口）；X-Stance 第三域评测（域偏置两点→三点）；`--classifier ensemble` 固定聚合档。

8. **Roadmap（明确不实现）**：完整 Black-Litterman 先验更新、conformal 弃权保证、PSI 漂移监测、Apriori 问题生成（可选增强）、启发式异常标记。

## 后果

- 正面：可信度三层各有量化抓手（输入可信：去重+采样纪律；推断可信：区间+门禁+聚合；决策可信：状态机+分级）；每段纯函数可单测，端到端黄金用例守护组合正确性；逐段可向评审讲解，本身即可信度展示。
- 代价：固定规则聚合精度可能低于学权重版本（接受：LLM 达标即主路径，聚合为备胎）；契约字段增多，前端渲染需分批同步（先判定链字段，后 grade 字段）。
- 风险：R4 的标注冲突/证据冲突区分依赖实现纪律，黄金用例必须显式覆盖；关联挖掘若误入判定管道即违反硬约束 1，测试必须断言旁路隔离。

## 验证记录（2026-11-22，代码现状核对，不改决策）

- **成立**：决策 1 挂接模式已被 `l2_cards`/`l2_notice` 包络扩展实证（`routers/evidence.py`）；决策 5 与代码现状一致（`stance_baseline.py` 零 ML 依赖零新包、`stance_llm.py` 属推理）；决策 6 成本估计合理（Wilson ~5 行公式、聚合器输入 `StanceResult`+`RuleHit` 已就绪）；引用核实无误（AVeriTeC EMNLP 2024 四标签、GRADE、Wilson 1927、SR 11-7）。
- **修正 1（A0，必做）**：现有演示夹具为单卡——conflict n=4、limited n=2（`demo_evidence.py`）。R3 门禁将把两个演示场景全部打成 insufficient，演示叙事崩塌。必做迁移：扩卡至 n≥30（星级/时间分层），扩卡后 conflict→`conflicting`（并排）、limited→`insufficient`（区间跨 0.5），两场景精确演示新判定状态；连带同步 StanceBanner / EvidenceStance / 演示说明 / 录屏脚本 / check_web.sh 断言。
- **修正 2（A2 前置）**：决策 3 留白了 state 映射公式。随 A2 锁定：门禁（n≥30 且 level=L1）→ Wilson 95% 区间（**分母=去重后有极性样本，insufficient 计数单独报告**）→ support 下界>0.5 → supported；oppose 下界>0.5 → refuted；双方票数均>0 且两份额区间重叠 → conflicting；否则 insufficient。公式随实现写入测试。
- **修正 3（A3 实现）**：L1 样本量 ≤数百时用精确字符 3-gram Jaccard 全对比 + 并查集聚类替代 MinHash 近似——精确值可入 provenance、实现减半（~30 行）、阈值语义直白；MinHash 留作规模化升级路径（R2 顺序纪律不变）。2026-11-28 补充：聚类键加入立场，只有同立场评论可合并，避免相反标注被静默丢弃。
- **澄清**：`state` 四值拆分**不是向后兼容变更**——现状冲突→oppose（`domain/evidence.py`），前端 `StanceBanner` 以 oppose 渲染「证据相互冲突」。需 schema→frozen dataclass→出参模型→前端类型/组件→check_web.sh 断言一次性同步，无中间态。
- **实数据跑通**：德国 L1 到位前，判定链以美国市场 L1 试点（`amazon_reviews_2023`，已在库）做端到端真实输入，避免沦为死代码；对外遵守 manifest `tier_caveat`（美国试点≠德国结论）。

## 对抗性审查（2026-11-22 第二轮，实现前堵漏）

进度核实：A0–A7 全部未开始（git 仅 v0 提交，工作区纯文档改动），check.sh 实测 117 测试全绿、9 来源合规——本 ADR「代码未实现」状态行与事实一致。以下四项为对抗性推演发现的实现级漏洞，均已回写 STATUS 子表：

- **C1（决策 3，A4）三票制引用不存在的标注器**：`stance_votes {rule, llm, lexicon}` 中「双语词表」票无代码对应物（`stance_baseline` 的词典是 rule 票的内部组件）。修正：两票 `{rule, llm}`，llm 凭据缺省时 `votes.llm=null`（R6）；一致取一致，分歧 → `annotator_agreement=false` 推向 insufficient（R4）。
- **C2（决策 3，A1）判定级字段层级错位**：`state` / `stance_interval` / `gate_status` / `recommended_tier` 是卡集合的函数，落点是包络（`EvidenceResponse`）不是每张卡；按「证据卡扩展字段」字面执行会产生全卡 `state=null` 脏字段。修正：卡级（`dedup`/`stance_votes`/`annotator_agreement`/`grade`/`downgrade_reasons`）进 evidence-card.schema.json；判定级进包络与前端响应校验。
- **C3（A2）conflicting 判据数学错误**：「区间含 0.5 → conflicting」在 20:10（2:1 明显主导，support Wilson CI [0.49,0.81]）时误判 conflicting。修正：conflicting = support 份额区间与 oppose 份额区间**重叠**（15:15 → 重叠 ✓；20:10 → 不重叠，落 insufficient，即 95% 置信下无法排除接近 50% 的诚实输出）。边界用例锁定：20:10→conflicting、21:30→supported（下界 0.521）、15:15→conflicting。
- **C4（A2）门禁 n 口径歧义**：验证记录中「门禁 n≥30」未定义 n。修正：门禁 n 与区间分母统一为**去重后有极性样本数**（insufficient 比例单独报告）——否则 30 条中 28 条 insufficient 时门禁虚过、区间极宽。
- **C5（A0）演示映射升级**：limited 场景从 insufficient（验证记录原设计）改为 21/30→`supported`（「有限」=区间宽 [0.52,0.83] 的量化表达）；三场景各演示一状态（conflicting/supported/insufficient），前端「已有有限支持」文案无需改动，跨层同步面最小。
- **C6（A3）短文本膨胀守卫**：短通用好评 3-gram Jaccard 虚高误聚（"Sehr gut!"/"Super gut!" 类）。守卫：<20 字符不参与聚类 + 阈值 0.85+（宁少合并，R6），误聚案例入测试。

## 实现状态补充（2026-11-25 审计，不改决策）

- A0–A6 已于 2026-11-22 第十轮落地（见 `docs/devlog/2026-11.md`；check.sh 实测 **181 测试**全绿），A7 未做。
- A4 两票聚合 `services/stance_aggregate.py` 已实现并有单测覆盖，但尚未接入 API 运行链路（见该模块「运行时接线状态」注释）；生产默认仍是规则基线单标注器。
- 本 ADR 顶部状态行「代码未实现」及「对抗性审查」中的 117 测试 / A0–A7 未开始，均为 2026-11-22 决策时点记录，不再代表当前实现状态。
