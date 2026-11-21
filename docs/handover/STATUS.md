# 交接状态页

**唯一事实来源。** 接手第一件事读本页，交班最后一件事更新本页。

最后更新：2026-11-22（公开上传准备：安全审计 + MARC 出库 + fresh clone 全绿） ｜ 当值：待指派 ｜ 距提交截止（12-07 10:00）**15 天**

---

## 一、一句话现状

**双侧证据链已闭环且 real 场景全真实数据**：L3 监管语境（Safety Gate 519 条）+ **L3 贸易语境（Comext HS4202 中国→德国，2025 年 9.50 亿欧元）** + L2 中文侧（真实采集片段快照 + 双语检索式，中文查询 0→8 命中）+ 三状态判定 + 立场基线**双域评测**（餐厅 0.610 / 商品域 MARC 0.580，域偏置被数据证实）+ **LLM 立场抽取适配层就绪（待凭据实测）**。自检 **117 测试、9 来源合规全绿**。**剩余最高阻塞不变：德国 L1 零样本**；两个凭据型动作：知乎 Access Secret 申请与 LLM 端点配置（开发层均已就绪，凭据到位即实测）。

## 二、当前阶段

| 项 | 状态 |
|---|---|
| 阶段 | 演示就绪（fixtures 模式可完整跑通三场景）；真实数据侧待凭据与预跑 |
| 代码状态 | ✅ 检索、证据 API、演示状态、知乎适配器、立场基线、前端三栏、演示文档、**LLM 立场抽取适配层（待凭据实测）**均实现并联调；❌ 反馈回填（P1）未实现 |
| 自检 | `bash scripts/check.sh` 五道全绿：ruff + mypy strict + **117 测试** + 结构校验（**9 来源**）+ 时间覆盖校验；前端另有 `bash scripts/check_web.sh`（37 断言，~15s） |
| 数据区 | `data/sources/` **9 来源 42,335 行**（第五轮 +Comext 贸易语境 +MARC 德语基准 +USAGE 标注基准）；`data/snapshots/` 已含真实采集快照 |
| 注册表 | **18 项**（第五轮新增 eu_comext），marc / usage_bielefeld / eu_comext note 已回填实测结论 |
| 开发环境 | 后端 8000 + 前端 3000 联调环境可用；知乎 capture 脚本已备（--dry-run 实测） |
| 版本控制 | 工作区清洁，本页与成果同批提交 |
| 提交窗口 | 12-05 10:00 开放，12-07 10:00 截止，逾期不可修改 |

## 三、数据区盘点

| 目录 | 层级 | 行数 | 年份覆盖 | 时间密度 | 可用性 |
|---|---|---|---|---|---|
| `eu_safety_gate/` | L3 | **3,255** | 2021–2026 六年 | 97.7% | ✅ 302/302 期完整 |
| `eurostat_isoc/` | L3 | 13,093 | 2021–2025 | 83.3% | ✅ 2026 源端未发布 |
| `openalex/` | L3 | 2,455 | 2021–2026 六年 | 56.9% | ✅ 每主题前 500 条 |
| `amazon_reviews_2023/` | L1（美国市场） | 6,207 | 2021–2023-08 | 91.5% | ⚠️ 对德国不构成 L1（见 3.3） |
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

**`旅行收纳包.json` 已是真实数据**（`is_demo_data=false`）：转录自 2026-11-18 zhihu-cli v0.6.3 的真实采集（消耗 3/10 次搜索额度），引文/链接/AuthorityLevel/赞同数/时间戳逐字保留，溯源工作区根目录（仓库外）`research/crosspilot-evidence_dim04.md` §4.1。收录 A/B/D 三条（发布日期 2026-11-11 / 2026-10-10 / 2026-07-29）；**C/E 两条无发布日期元数据暂不收录**（不以捕获日冒充发布日），待凭据重采补齐。演示撰写的样例已迁至 `apps/api/tests/fixtures/zhihu/`（测试专用）。real 场景前端与 API 已全部为真实数据，演示标识只剩 conflict/limited 两个演示场景。

## 四、下一步（按优先级）

| # | 事项 | 负责人 | 为什么是这个顺序 |
|---|---|---|---|
| 1 | **约访 1 位正在做德国站上架/改版的品牌运营** | 待指派 | 德国 L1 唯一路径，无接口可替代；其余一切都在等它或可并行 |
| 2 | **申请知乎 Access Secret → live 首跑核验端点 → 重采 C/E 片段补齐快照** | 待指派（需账号） | 自助生成于 developer.zhihu.com；先 `python scripts/capture_zhihu_snapshot.py --dry-run` 预检再真跑；响应结构若与文档副本不符需修订 `zhihu_client.py` 并回填核验记录；顺带补采缺日期元数据的 C/E 两条片段（真实快照演示已不阻塞于此） |
| 3 | ~~录制演示视频~~（**暂缓**：2026-11-21 用户指示不需要录屏脚本，专注开发；物料保留，提交窗口开启前再按 `docs/demo/录屏脚本.md` 恢复此项） | 暂缓 | 成片一致性要求不变：恢复录制时按演示说明第四节合规清单勾选并重跑两道自检 |
| 4 | **LLM 立场抽取实测**（开发层已就绪，等凭据） | 待指派（需 LLM key） | 适配层已实现（ADR-0004）：`.env` 配 LLM_API_BASE / LLM_API_KEY / LLM_MODEL 三项后 `scripts/eval_stance_baseline.py --classifier llm` 即可双域实测；对照靶 GERestaurant 0.610 / MARC 0.580，启用前提 = oppose recall 超规则基线；缓存可中断续跑，`--limit` 控成本 |
| 5 | 注册 Destatis / Comtrade / OpenAlex key / eBay keyset / DeepL key | 待指派 | 均免费无审批；eBay 补 2023-09 后时效缺口（卖家侧，只进企业假设栏） |
| 6 | 向官方确认知乎配额是否随参赛提升、Token 补贴细则 | 待指派 | 决定 live 模式可行性；实测搜索 10 次/日（手册称 5000） |
| 7 | **创建 GitHub 仓库并推送**（结构已就绪：fresh clone 三道全绿，MARC 已出库） | 待指派（需账号） | 公开仓库；推送后确认 CI 在 main 上跑绿 |

**边界调整（按各轮成果累计修订）：**
- 前端「卡片→假设归属」为关键词启发式：conflict 场景一张卡因含「Platz」归入容量假设（功能组显示空）——口径已写入 `docs/demo/演示说明.md` 第七节，属已知行为非缺陷；契约允许后端加归属字段时可替换。
- 中英文查询互不覆盖：中文词在英文 L3 库零命中、英文词在中文快照零命中——是诚实行为；查询词翻译/双语检索式列为可选增强，不承诺。
- fixtures 与真实 API 存在合理差异（real 场景夹具 3 张 L3 卡 vs API 对中文词 0 张 + l2_notice 降级条）——演示说明已文档化，两种模式都是正确行为。
- 录制成片发布前必须重跑 `check_web.sh` + `check.sh`，确认成片与最终代码一致。
- **叙事层调整（第六轮，纯文档）**：对外定位统一为「出海卖点的上线前尽职调查」（演示说明 8.1）；新增相关工作对比（8.2）、判定→建议动作映射（8.3）、术语约定（8.4，不以 "vibe selling" 指代本项目）与高频质疑预案（8.5）。**L1 零样本对外按 problem statement 口径处理**（8.5），不再作为纯缺陷叙述。闭环下游以验证日志留痕：新增 `docs/demo/validation_log.md`。镜 2 旧旁白「L2 演示数据」表述与真实快照现状矛盾，已修正（成片一致性要求）。代码与数据行为零变更。
- **开发优先级调整（第八轮，2026-11-21 用户指示）**：录屏/演示视频暂缓，工作重心转向代码与数据开发（LLM 立场抽取先行）；演示物料保留不删，提交窗口开启前恢复录制即可。

## 五、已知阻塞与解除条件

| 阻塞 | 严重度 | 解除条件 |
|---|---|---|
| **德国消费者一手反馈零样本（L1）** | **最高** | 品牌方提供德国站反馈导出（含站点、时间、样本量字段） |
| 知乎 live 端点响应结构未核验（无凭据） | 中 | 申请 Access Secret 后 capture 脚本首跑核验；不符则修订 zhihu_client.py。**演示已不依赖此项**（真实快照已就位） |
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
| `docs/adr/` | 设计决策；ADR-0002 快照模式、ADR-0003 数据区与中断恢复 |
| `docs/devlog/` | 创作真实性佐证，赛事核验用 |
| `../../../CrossPilot_证据调研清单_回填版.md` | P0 取证现状（2026-11-18 快照，P0 结论仍成立） |
| `../../../CrossPilot_数据源与交付形式清单.md` | 数据源许可、优先级与交付规格 |

> 注：上表末两份清单与 §3.4 提到的 `research/` 取证目录均位于**工作区根目录（本仓库之外）**。

## 八、数据区操作速查

```
# 五道自检（提交前必跑）
bash scripts/check.sh

# 前端冒烟（录屏/提交前必跑，37 断言约 15s）
bash scripts/check_web.sh

# 从本地 raw 重建主表，零网络请求
.venv/Scripts/python.exe data/sources/_scripts/rebuild_from_raw.py

# 抓取中断后只补缺失期次，可反复运行
.venv/Scripts/python.exe data/sources/_scripts/resume_safety_gate.py

# Amazon Reviews 试点（镜像路径，中断可续）
.venv/Scripts/python.exe data/sources/_scripts/fetch_amazon_reviews.py

# 知乎快照预跑（需先在 .env 配 ZHIHU_ACCESS_SECRET；先预检再真跑）
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
