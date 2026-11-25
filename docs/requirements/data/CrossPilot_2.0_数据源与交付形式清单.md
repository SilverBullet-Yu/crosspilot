# CrossPilot 2.0 — 数据源与交付形式清单

核查日期 2026-11-18；接入优先级与扩展源核验 2026-11-20 ｜ 入库状态回填 2026-11-21 ｜ **2026-11-26 复核：OpenAlex 2,454（重抓漂移）、Amazon 6,146（按 review_id 去重）、许可原件与 GitHub public 仓库已就绪** ｜ 赛事提交规格以官网及实时技术指南为准

---

## 〇、接入优先级（2026-11-20 重排；2026-11-21 回填实测结果与入库状态）

排序原则：**有公开接口 + 有免费额度 + 免人工审批**者优先；需申请、需授权、需人工推进者后置。

### 0.1 实测结果（2026-11-20/21，本机）

| 来源 | 实测 | 入库状态 |
|---|---|---|
| **Eurostat** | 200 / 16s | ✅ 13,093 行（2021–2025） |
| **EU Safety Gate** | 索引 200 → 明细 200 | ✅ **3,255 条，302/302 期完整** |
| **OpenAlex** | 200 / 1.1s（最快） | ✅ 2,454 条（2021–2026） |
| **GDELT** | 200 但限速极严 | ⚠️ 1,090 条，**仅 2021H1–2022H2** |
| **OPUS ParaCrawl** | 206 ×3/3 | 可下载，未入库 |
| **GERestaurant** | GitHub 200（HF 不可达，走 fork 快照） | ✅ **已入库 3,078 条**（CC-BY-4.0） |
| **USAGE（Bielefeld）** | romanklinger.de 200（限速，timeout 300s） | ✅ **已入库**（1,233 评论汇总 + 25,292 span 标注，ODC-By 1.0，公开件无文本层） |
| **MARC** | 官方 HF 已下架（404）→ mteb 镜像 200 | ✅ **已入库 10,000 条**（de test+validation；研究许可，硬约束 2） |
| **Eurostat Comext** | 专用 API 按过滤取数 26 次全 200 | ✅ **已入库 1,924 行**（HS4202 中国→德国，2021–2026） |
| **Destatis** | 307 → 匿名被重定向至注册页 | ❌ **降 P1**，域名改为 `genesis.destatis.de` |
| **Hugging Face** | DNS 可解析，**TCP 443 全程超时 28s**；hf-mirror.com 可用（文件 302 至官方 CDN） | ❌ 官方站不可达 → ✅ **经镜像路径解除** |
| **Amazon Reviews 2023** | 经 hf-mirror→官方 CDN 分片直下（SHA-256 一致） | ✅ **试点入库 6,146 行**（美国市场，**不构成德国 L1**） |
| **eBay / DeepL** | 405 / 403（缺凭据的预期响应） | 连通正常，待注册 |
| **UN Comtrade** | preview 200 | 连通正常，正式取数待注册 |

数据区位置：`../../../data/sources/`，结构与字段见该目录 README。

### 0.2 优先级表

| 优先级 | 来源 | 接口形态 | 免费额度 | 凭据门槛 | 层级 | 对项目的作用 |
|---|---|---|---|---|---|---|
| **P0-A** | ~~HF Dataset Viewer API~~ → **移至 P1-F** | REST `/search` `/filter` `/rows` | 公开数据集免 key | **需镜像或代理** | L1 | ❌ 2026-11-20 实测本机不可达：DNS 可解析但 TCP 443 全程超时 28s |
| **P0-B** | **Eurostat** | REST / SDMX 3.0 / JSON-stat | 免费免注册 | 无 | L3 | ✅ **已入库 13,093 行**（2021–2025，2026 源端未发布） |
| **P0-C** | ~~Destatis GENESIS~~ → **移至 P1-E** | RESTful / JSON | 免费 | **需注册**（匿名 GAST 被重定向） | L3 | 2026-11-20 复核：域名迁至 `genesis.destatis.de`，匿名取数不可行 |
| **P0-D** | **EU Safety Gate（RAPEX）** | 周报 XML 索引 + 逐期明细 XML | 免费无 key | 无 | L3 | ✅ **已入库 3,255 条**。明细须带 `search=WEB_REPORT\|:\|{id}`，元素名为 `notifications`（复数） |
| **P0-E** | **GDELT DOC 2.0** | REST JSON，无 key | 免费；**实测限速远严于官方 1 req/5s**，单查 250 条 | 无 | L3 | ⚠️ **仅入库 2021H1–2022H2**。大批量应改用官方 ngrams 数据集 |
| **P0-F** | **OPUS ParaCrawl** | `opustools` 下载 | 免费 | 无 | 辅助 | 中德英电商术语对照表；分块下载实测 3/3 稳定 |
| **P0-G** | **USAGE（Bielefeld）** | 直接下载 | 免费 | 无 | 评测基准 | ✅ **已入库**（1,233 评论 + 25,292 span 标注，ODC-By 1.0）；公开件不含评论原文，只作 span 级基准 |
| **P0-H** | **GERestaurant** | ~~HF~~ → **GitHub `NilsHellwig/GERestaurant`** | 免费，CC BY 4.0 | 无 | 评测基准 | ✅ **已入库 3,078 条**（数据原件取自同期 fork 快照，HF 不可达）；德语评论含 aspect + 极性标注 |
| **P1-A** | **UN Comtrade** | REST | 注册后 500 次/日、10 万条/次 | 免费注册，无审批 | L3 | 硬约束 4：禁用 preview 截断结果 |
| **P1-B** | **DeepL API Free** | `api-free.deepl.com/v2` | 50 万字符/月 | 免费注册，无需信用卡 | 工具 | 德↔中↔英卖点对照；Free 档无 DPA，**禁止传入任何含个人数据的文本** |
| **P1-C** | **OpenAlex** | REST | 无 key 可用；免费 key 额度 ×10 | 可选 | L3 | ✅ **已入库 2,454 条**（无 key 完成）。`mailto` 自 2026-02 起被忽略 |
| **P1-D** | **eBay Browse API** | REST，`X-EBAY-C-MARKETPLACE-ID: EBAY_DE` | 5,000 次/日/AppKey，单次 200 条 | 免费 keyset，生产 key 自助创建 | L1（卖点侧） | 德国站在售商品标题/卖点/价格，补 Amazon 2023-09 之后的时效缺口；Buy API 名义面向合作伙伴，eBay 可限权 |
| **P1-E** | **Destatis GENESIS** | `genesis.destatis.de`（新域名） | 免费 | 免费注册 | L3 | 由 P0-C 降级；`www-genesis` 前缀会 307 跳转 |
| **P1-F** | **Amazon Reviews 2023** | ~~HF Dataset Viewer~~ → **hf-mirror.com 镜像分片直下** | 免费，Apache 2.0 | 镜像路径已打通（文件 302 至官方 CDN） | L1 | ✅ **试点已入库 6,146 行**（全库最小分片）。**实测为 Amazon.com 美国全站数据，无 marketplace/language 列，无法筛德国子集——不构成德国 L1**；全量 ≈220GB 不做迁移 |
| **P2-A** | **知乎开放平台** | 官方搜索 / 直答 API | 实测 10 次/日 | Access Secret | L2 | 实时检索 + 摘录 + 链接回源，不建库 |
| **P2-B** | **品牌自有授权数据** | 人工导出 | — | 品牌方授权 | L1 | **唯一能解除德国侧零样本阻塞的路径**，无接口可替代 |

**排序变化说明**

| 变化 | 原位置 | 新位置 | 依据 |
|---|---|---|---|
| Amazon Reviews 2023 | 落地检查第 1 项，整包下载 | 升为 P0-A，改走 HF Dataset Viewer API | 同一数据，API 可按关键词检索，先验证可行性再决定是否落整包 |
| 知乎开放平台 | 数据栈 L2 首列 | 降为 P2-A | 10 次/日实测额度 + 需 Access Secret，不满足"免审批高额度" |
| Comtrade | 落地检查第 2 项 | 降为 P1-A | 需注册，但无人工审批，仍排在需授权项之前 |
| 新增 6 项 | — | P0-D/E/H、P1-B/C/D | 均为公开接口或公开下载，免费额度明确，见下 §1.4 |

---

## 一、数据源（11 项基础 + 6 项扩展）

### 1.1 可商用（主数据栈）

| 来源 | 层级 | 许可 | 费用 / 限额 | 规模与覆盖 | 接入要点 |
|---|---|---|---|---|---|
| **Amazon Reviews 2023**<br>McAuley Lab, UCSD | L1 | Apache 2.0 | 免费，无需申请 | 5.71 亿条，33 品类，1996-05~2023-09，英文 | 评论侧 `rating`/`text`/`helpful_vote`/`verified_purchase`；商品侧 `features`/`description`/`price` |
| **Eurostat** | L3 | 开放 | 免费，免注册 | EU 27 国，年度 ICT 调查 | REST / SDMX 3.0 / JSON-stat；端点 `ec.europa.eu/eurostat/api/dissemination`；集 `isoc_ec_ib20`、`isoc_ec_ibuy`、`tgs00052` |
| **Destatis GENESIS-Online** | L3 | DL-DE-BY 2.0 | 免费，免注册 | 德国官方统计 | RESTful/JSON；WADL `www-genesis.destatis.de/genesisWS/rest/2020/application.wadl`；区域级换域名 `regionalstatistik.de` |
| **OPUS ParaCrawl** | 辅助 | CC0-1.0 | 免费 | 42 语种 / 43 双语对，含中德英 | `pip install opustools` |
| **知乎开放平台** | L2 | — | 1000 次/日/账号 | 站内搜索、全网搜索、热榜、直答 | `developer.zhihu.com` → 个人中心 → Access Secret |

**Amazon Reviews 2023 优先锁定理由与可用品类**

| 项 | 说明 |
|---|---|
| 核心优势 | 商品元数据 `features`/`description` 即卖家自撰卖点，双侧对照可在单一数据集内跑通，无需企业授权 |
| 分层支撑 | `verified_purchase`、`helpful_vote` 天然支撑证据可信度加权 |
| 相关品类 | `Home_and_Kitchen` 6740 万 ｜ `Clothing_Shoes_and_Jewelry` 6600 万 ｜ `Office_Products` 1280 万 |

### 1.2 仅非商业

| 来源 | 内容 | 许可约束 | 项目用途 |
|---|---|---|---|
| **MARC** | 英/日/**德**/法/中/西六语，每语 20 万条，2015~2019，仅 verified purchase | 仅学术研究；禁转售、再发布、商业研究及交付营利组织；HF 版本已 defunct | Demo 期多语种验证 |
| **USAGE**（Bielefeld） | 622 英 + 611 德条，含 aspect 与主观短语人工标注 | 作者声明免费供社区使用 | 立场抽取评测基准，对应 7.3「证据正确率」 |

### 1.3 有条件

| 来源 | 开放条件 | 处置 |
|---|---|---|
| **DATA.GOV.HK** | 商用与非商用均免费，除转售外无限制，提供 API builder | **2026-11-18 复核：许可属实（条款 v1.2，2025-05-26），但十大出口目的地无德国、无任何欧洲国家 → 降级为 L3 背景，不进对照矩阵** |
| **深圳开放平台**<br>`opendata.sz.gov.cn` | 下载免费；API 需提交应用资料并获批准 | **2026-11-18 复核：唯一相关数据集「跨境电商公共海外仓信息」仅 3 条、2022-11 停更、无德国 → 建议移出数据栈** |
| **UN Comtrade** | preview：500 行/次、单期单品、无分页<br>免费注册后：500 次/日、10 万条/次 | 必须注册 |
| **ITC Export Potential Map** | 公开 | 宏观排名，仅作市场背景，不进对照矩阵 |

> 国内侧核验详见 `../../research/CrossPilot_证据_dim05_国内数据源.md`。**结论：国内可用数据源实际仅知乎一家（L2）。**

### 1.4 扩展数据源（2026-11-20 新增，6 项）

全部为公开接口或公开下载，无人工审批环节。

| 来源 | 接口 | 免费额度 | 许可 | 覆盖与字段 | 纳入理由 |
|---|---|---|---|---|---|
| **EU Safety Gate（RAPEX）** | 周报 XML 列表 + `POST ec.europa.eu/safety-gate-alerts/public/api/search`；详情 `GET /public/api/notification/{id}` | 免费、无 key、无 cookie | 周报 XML 分发在 data.europa.eu 标注 CC0 1.0 | 2005 年至今非食品消费品警报；含 `category` `brand` `barcodes` `riskTypes` `hazardDescription` `measures` `notifyingCountry` `countryOfOrigin` | 德国侧唯一**免授权**的官方一手信号：监管机构对具体商品的缺陷判定，可与企业卖点直接对照 |
| **GDELT DOC 2.0** | `api.gdeltproject.org/api/v2/doc/doc`，JSON/JSONP | 免费无 key；约 1 req/5s，单查询 ≤250 条 | 官方声明可无限制用于学术、商业、政府用途，须署名 | 滚动 3 个月，65 语种机器翻译；返回 `title` `url` `domain` `language` `sourceCountry` `seenDate` `tone` | 补德语媒体语境与 tone 时间线；**只返回元数据与链接，不含正文**，天然规避全文库问题 |
| **GERestaurant** | GitHub 仓库下载（HF 不可达，走同期 fork 快照） | 免费 | CC BY 4.0 | 3,078 条德语评论，含隐式/显式 aspect、aspect 类别、极性人工标注 | 德语立场抽取评测基准，**许可可商用**，不受 MARC 的硬约束 2 与 USAGE 的社区限定约束 |
| **DeepL API Free** | `api-free.deepl.com/v2/translate`、`/v2/document` | 50 万字符/月，免信用卡 | Free 档**不提供 DPA**，文本可能被用于改进服务 | ~36 语种，支持 DOCX/PDF/PPTX | 德↔中↔英卖点对照与术语统一。**新增硬约束 5：禁止向 Free 档传入任何含个人数据的文本** |
| **OpenAlex** | `api.openalex.org`，REST GET | 无 key 可用；免费 key 额度 ×10；硬上限 100 req/s，`per_page` ≤100，基础分页 ≤10,000 条（超出用 cursor） | 开放 | 学术元数据；注意 2026-02 起 `mailto` polite pool 已被 API key 取代，`mailto` 参数被忽略 | 跨境认知差、ABSA 方法论的 L3 学术引用来源 |
| **eBay Browse API** | `api.ebay.com`，REST + OAuth client_credentials | 5,000 次/日/AppKey，单次返回 ≤200 条 | 开发者计划免费；Buy API 需额外 license，eBay 可对 keyset 限权 | 德国站（`EBAY_DE`）在售商品：标题、价格、币种、状态、卖家评分、配送、品类、上架时间 | **唯一能补 Amazon 2023-09 时效缺口的免费官方接口**；注意配额按 AppKey+API 名计，不按站点拆分 |

**扩展源的层级归属**

| 来源 | 层级 | 能否单独支撑偏好结论 | 理由 |
|---|---|---|---|
| EU Safety Gate | L3 | 否 | 是监管判定，不是消费者偏好表达 |
| GDELT | L3 | 否 | 媒体报道属二手叙述，且只有标题 |
| eBay Browse | L1（卖点侧）/ 不入需求侧 | 否 | 返回的是**卖家自撰卖点与价格**，与 Amazon `features`/`description` 同性质，只进对照矩阵的"企业假设"一侧，不得当作消费者反馈 |
| GERestaurant | 评测基准 | 否 | 餐厅域，与旅行收纳包无域重叠，仅用于校准立场抽取 |
| OpenAlex | L3 | 否 | 学术背景 |
| DeepL | 工具 | — | 不产生证据，只做语言转换 |


---

## 二、硬约束（五条）

| # | 约束 | 触发场景 | 不遵守的后果 |
|---|---|---|---|
| 1 | 知乎内容归 **L2**，不得单独支撑「消费者偏好」结论，只能生成待验证问题 | 对照矩阵写入 stance 时 | 二手转述与一手反馈同权，范畴错误 |
| 2 | **MARC 商业化路径启动即下线** | ¥99—199 定价成立时 | 违反 Amazon 学术限定条款 |
| 3 | OPUS **只取 ParaCrawl**，排除 OpenSubtitles | 拉取语料时 | 底层字幕条款不明，商用受限 |
| 4 | Comtrade **必须注册免费账号** | 任何贸易数据调用 | 截断与完整返回外观一致，500 行可掩盖 4 万行 |
| 5 | **DeepL API Free 档禁止传入含个人数据的文本** | 翻译评论原文、用户名、联系方式时 | Free 档无 DPA，文本可能用于改进服务，构成 GDPR 问题；需译评论原文时改用本地模型或付费档 |

### 2.1 扩展源的调用纪律

| 来源 | 纪律 | 原因 |
|---|---|---|
| GDELT | 请求间隔 ≥5s；单查询结果视为"该窗口上限 250 条"，不得当作全量 | 官方限速；250 条截断与完整返回外观一致，同硬约束 4 的失败模式 |
| eBay Browse | 配额按 **AppKey + API 名**聚合，不按 marketplace 拆分；调用前先读剩余配额 | DE 与 US 共用同一 5,000 次/日额度 |
| eBay Browse | 返回内容只进"企业假设"栏，**不得写入消费者证据侧** | 是卖家自撰文案，非消费者反馈 |
| OpenAlex | 不要再使用 `mailto` 参数 | 2026-02 起 polite pool 已废弃，该参数被忽略 |
| HF Dataset Viewer | `/rows` `/filter` 单次 ≤100 行，必须显式分页 | 与 Comtrade 同类截断风险 |
| EU Safety Gate | 产品级字段可用；文本中的邮箱、电话、私人挂牌链接须剔除 | 警报描述产品而非个人，但自由文本可能夹带个人数据 |

---

## 三、时效缺口

| 来源 | 数据截止 | 可支撑 | 不可支撑 |
|---|---|---|---|
| Amazon Reviews 2023 | 2023-09 | 卖点假设检验方法论 | 实时市场洞察 |
| MARC | 2019-11 | 多语种结构验证 | 当下偏好判断 |
| GermEval 2017 | 2017-01 | 德语 ABSA 结构 | 当下偏好判断 |
| GERestaurant | 2023-10 | 德语立场抽取校准 | 旅行收纳包域结论 |
| Eurostat / Destatis | 2025 调查年 | 市场语境基线 | — |
| **eBay Browse（DE）** | **实时在售** | **当前卖点与价格带** | 消费者反馈 |
| **Eurostat Comext** | **月度，2021–2026** | **贸易规模与趋势语境** | 消费者偏好；CN8 细目不可得 |
| **GDELT** | **滚动 3 个月，15 分钟更新** | **德语媒体语境与 tone** | 消费者个体反馈；无正文 |
| **EU Safety Gate** | **每周五更新** | **监管端缺陷信号** | 偏好与满意度 |

扩展源把"实时性"缺口从卖点侧与语境侧补上了；**需求侧（德国消费者真实反馈）仍为零样本**，无任何公开接口可替代品牌授权数据。路演主动说明，优于被评委问出。

---

## 四、交付形式

### 4.1 核心产物

| 项 | 规格 |
|---|---|
| 形态 | 多页 Web 工作台（产品概览 / 卖点验证工作台 / 历史验证项目），非报告生成器 |
| 左栏 | 企业假设（3 条，用户输入） |
| 中栏 | 证据对照（支持 / 反对 / 证据不足） |
| 右栏 | 验证动作（访谈问题 + A/B 文案） |

### 4.2 证据卡必现字段

| # | 字段 | 作用 |
|---|---|---|
| 1 | 原文摘录 | 可追溯 |
| 2 | 来源链接 | 可真实打开 |
| 3 | 语言 | 跨语言对照 |
| 4 | 日期 | 时效判断 |
| 5 | **证据层级 L1/L2/L3** | 可信度加权 |
| 6 | **样本量** | 偏差标注 |

### 4.3 两个必须可见的状态

| 状态 | 呈现要求 | 目的 |
|---|---|---|
| 证据不足 | 独立空状态卡片，非灰字，附待验证问题 | 把拒答做成产品特性 |
| 证据冲突 | 支持 / 反对原文左右并排 | 保留矛盾，不调和 |

### 4.4 演示与路演

| 项 | 做法 | 原因 |
|---|---|---|
| 数据获取 | 预跑「旅行收纳包 → 德国」落盘，读本地快照 | 规避网络、配额、限流 |
| 来源链接 | 仍保留可点开真实页面 | 保持可追溯感 |
| 关键一屏 | 左：通用大模型流畅无源回答<br>右：本系统「证据不足 + 3 个待验证问题」 | 十秒呈现差异化，无需额外开发 |

### 4.5 文档

| 文件 | 定位 | 结构 |
|---|---|---|
| 作品说明 | 提交物，压缩到一页 | 问题 → 一句话方案 → 架构图 → **数据来源与许可表** → 可验收清单 |
| 现有 docx | 转内部工作文档，不直接提交 | 队内对齐、访谈提纲、风险清单 |

---

## 五、落地检查（按接入优先级重排）

### 5.1 P0 — 零凭据零审批（2026-11-26 复核）

| # | 事项 | 来源 | 类别 | 完成 |
|---|---|---|---|---|
| 1 | ~~用 HF Dataset Viewer 检索 Amazon Reviews 2023~~ | HF API | 数据 | ☑ **已解除**：hf-mirror→官方 CDN 路径打通，试点入库 6,146 行（美国市场） |
| 2 | Eurostat 取 `isoc_ec_ib20` 德国切片 | Eurostat | 数据 | ☑ **13,093 行，2021–2025** |
| 3 | ~~Destatis GENESIS 匿名取数~~ | Destatis | 数据 | ❌ 匿名被重定向，移至 P1 |
| 4 | Safety Gate 按德国相关取警报，落 `data/sources/` | EU Safety Gate | 数据 | ☑ **3,255 条，302/302 期完整** |
| 5 | GDELT 建德语品类报道时间线，验证 250 条截断 | GDELT | 数据 | ◐ **部分**：1,090 条，仅 2021H1–2022H2；4 窗触顶已记录 |
| 6 | `opustools` 拉 zh-de / zh-en / de-en | OPUS ParaCrawl | 数据 | ☐ 端点已验证可达（206 ×3/3） |
| 7 | 下载 USAGE + GERestaurant，建德语立场抽取双基准 | USAGE / GERestaurant | 数据 | ☑ **均已入库**（GERestaurant 3,078 / USAGE 1,233+25,292 span） |
| 8 | 留存各源许可原件至 `data/licenses/` | 全部 | 合规 | ☑ **9 份许可原件 + README 索引已入库**（2026-11-23） |
| 9 | 数据区结构校验接入 `scripts/check.sh` | — | 工程 | ☑ **9/9 来源合规**（含时间覆盖校验） |

说明：OpenAlex 原列 P1（第 11 项），**实际用无 key 方式已完成入库 2,454 条**。

**2026-11-21 追加入库**（均过四件套 + 两层校验，详见 `../../../data/sources/README.md`）：Amazon Reviews 2023 试点 6,146 行（美国市场）、GERestaurant 3,078、USAGE 1,233 + 25,292 span、MARC 10,000（mteb 镜像）、EU Comext 1,924（HS4202 中国→德国）。

### 5.2 P1 — 需免费注册，无人工审批

| # | 事项 | 来源 | 类别 | 完成 |
|---|---|---|---|---|
| 9 | 注册 Comtrade 免费账号，取 subscription key | Comtrade | 数据 | ☐ |
| 10 | 申请 DeepL API Free key（`:fx` 结尾，走 `api-free` 域名） | DeepL | 工具 | ☐ |
| 11 | 注册 OpenAlex 免费 key（额度 ×10），代码中移除 `mailto` 参数 | OpenAlex | 数据 | ☐ |
| 12 | 创建 eBay 生产 keyset，用 client_credentials 取 token，跑一次 `EBAY_DE` 搜索并读剩余配额 | eBay | 数据 | ☐ |

### 5.3 P2 — 有人工环节，不阻塞 P0/P1

| # | 事项 | 来源 | 类别 | 完成 |
|---|---|---|---|---|
| 13 | 申请知乎 Access Secret，`quota` 实测全网搜索额度 | 知乎 | 数据 | ☐ |
| 14 | 约访做德国站上架/改版的品牌运营，取授权反馈导出 | 品牌方 | 数据 | ☐ |

### 5.4 合规与交付（不随数据进度推迟）

| # | 事项 | 类别 | 完成 |
|---|---|---|---|
| 15 | 系统规则写死：L2/L3 不得单独支撑偏好结论 | 合规 | ☐ |
| 16 | 文档写死：MARC 非商业边界 | 合规 | ☐ |
| 17 | 代码写死：eBay 返回只进企业假设栏，不进消费者证据侧 | 合规 | ☐ |
| 18 | 代码写死：DeepL Free 档调用前做个人数据检查 | 合规 | ☐ |
| 19 | 作品说明附数据来源与许可表（含 6 项扩展源） | 交付 | ☐ |
| 20 | 路演脚本加入分屏对比一屏 | 交付 | ☐ |
