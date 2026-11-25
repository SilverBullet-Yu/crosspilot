# CrossPilot 2.0 数据集采集缺陷、结构与内容审计报告

> 审计日期：2026-11-24  
> 审计范围：`data/sources/`、`data/snapshots/`、`data/licenses/`  
> 数据采集时间：外部来源主要为 2026-11-20～2026-11-21；知乎快照采集于 2026-11-18  
> 审计方式：实际解析 CSV、JSON、JSONL、XML、gzip、tar；核对 manifest、provenance、SHA-256、日期覆盖、重复键、关键字段缺失和关联引用；运行项目数据校验与后端测试。  
> 说明：本报告只读审计，未修改或重抓任何源数据。

> **2026-11-26 复核**：本报告是 2026-11-24 审计快照，正文数字保留审计时点、不随重抓改写。此后 D-04（OpenAlex raw 25/25 页完整、可离线重建）与 D-05 的重复评论（按 `review_id` 去重，重复键 0）已解决；空正文 10 行按 `is_empty_text` 标记保留，`price_usd` 仍全空。当前权威口径为 **67,565**（全部 CSV 行）/ **66,332**（主表口径）/ **42,273**（记录/评论级），OpenAlex **2,454**、Amazon **6,146**；数据状态以 `data/sources/README.md` 与 `status/STATUS.md` 为准。

---

## 1. 执行摘要

### 1.1 总体结论

项目已经形成“**外部语境数据 + 评测基准 + 知乎 L2 快照**”的数据集合，工程结构和大多数原始文件可追溯性良好，但距离“德国市场消费者偏好验证”仍有核心缺口：

1. **德国消费者一手反馈（德国 L1）仍为零样本。**
2. **Amazon Reviews 是美国站、订阅盒子品类试点，不能代表德国或旅行收纳包市场。**
3. **GDELT 时间覆盖严重稀疏且多窗口截断，不能做趋势分析。**
4. **OpenAlex 主表有 2,455 条，但仅保留每主题第 1 页原始响应，第 2～5 页共 20 个响应未落盘。**
5. **Amazon 主表存在重复评论、空正文和价格字段全空等质量问题。**
6. **GERestaurant、MARC、USAGE 均为评测基准，不是目标市场证据；分别存在域不匹配、研究许可和无文本层限制。**

### 1.2 数据规模

| 指标 | 实测值 |
|---|---:|
| 外部数据来源 | 9 个 |
| 知乎真实快照 | 1 个查询、3 条卡片 |
| 来源目录文件总数 | 409 个 |
| 来源目录总大小 | 84,018,120 字节，约 80.13 MiB |
| 原始响应文件 | 368 个，约 66.27 MiB |
| 规范化 CSV | 10 个，约 13.68 MiB |
| 全部 CSV 行数 | 67,627 |
| 项目主表口径 | 66,394 行 |
| 评论/记录级口径 | 42,335 行 |

**行数口径说明：**

- `67,627`：10 个 CSV 的实际行数总和，包含 USAGE 的 25,292 行 span 标注和 1,233 行评论汇总。
- `66,394`：项目文档采用的主表口径，排除 USAGE 的 1,233 行评论汇总表。
- `42,335`：在 `67,627` 基础上排除 25,292 行 span 标注后的评论/记录级口径。

三个数字都正确，但适用场景不同，混用会造成规模误读。

### 1.3 当前可支持与不可支持的结论

| 可支持 | 不可支持 |
|---|---|
| 德国监管风险与品类语境 | 德国消费者喜欢或不喜欢某个卖点 |
| 中德 HS4202 贸易规模与变化 | 具体旅行收纳包品牌的消费者偏好 |
| 德国线上购买宏观行为 | 美国评论外推德国市场 |
| 德语立场抽取方法评测 | 餐厅域基准外推商品域 |
| 中文跨境从业经验生成待验证问题 | 知乎 L2 单独支撑德国偏好结论 |
| 管线演示、数据契约与降级逻辑 | 用当前数据做德国 L1 统计判定 |

---

## 2. 数据区结构

### 2.1 目录结构

```text
data/
├── sources/
│   ├── _scripts/                 # 抓取、重建、结构校验、覆盖校验脚本
│   ├── _eval_cache/              # LLM 评测缓存
│   ├── amazon_reviews_2023/
│   ├── eu_comext/
│   ├── eu_safety_gate/
│   ├── eurostat_isoc/
│   ├── gdelt/
│   ├── gerestaurant/
│   ├── marc/
│   ├── openalex/
│   └── usage_bielefeld/
├── snapshots/
│   ├── README.md
│   └── zhihu/
│       └── 旅行收纳包.json
└── licenses/                     # 许可原件与 SHA-256 基线
```

### 2.2 单源标准结构

每个来源目录的目标结构为：

```text
<source>/
├── README.md          # 来源、许可、层级、字段、限制、复现方式
├── manifest.json      # 机器可读元数据、覆盖声明、截断声明
├── provenance.csv     # 请求留痕、字节数、SHA-256、UTC 时间
├── <main_table>.csv   # 规范化主表
└── raw/               # 原始响应或下载包
```

实际结构的偏差：

- `usage_bielefeld/` 有 **2 个规范化 CSV**：span 标注主表和评论汇总表。
- `eu_safety_gate/` 额外有 `provenance_resume.csv`，但当前文件只有表头，没有补抓记录。
- `amazon_reviews_2023/raw/` 下有 `review_categories/`、`meta_categories/` 等嵌套目录。
- `openalex/raw/` 只保留每主题第 1 页，不是全部 5 页。
- `marc/` 主表和 raw 当前本地存在，但按研究许可不进入公开 Git 仓库。
- 知乎快照使用独立 schema，不属于 `sources/` 的“四件套”结构。

### 2.3 数据层级

| 层级 | 来源 | 用途 |
|---|---|---|
| L1 数据集类别 | Amazon Reviews 2023 | 仅美国站管线试点；对德国不构成 L1 |
| L2 | 知乎快照 | 中文经验与待验证问题，不建全文库 |
| L3 | Safety Gate、Eurostat ISOC、Comext、GDELT、OpenAlex | 监管、贸易、宏观、媒体、学术语境 |
| BENCHMARK | GERestaurant、MARC、USAGE | 立场抽取与标注结构评测 |

### 2.4 主要证据文件

- [数据区总索引](../../data/sources/README.md)
- [来源结构校验脚本](../../data/sources/_scripts/validate_sources.py)
- [时间覆盖校验脚本](../../data/sources/_scripts/validate_coverage.py)
- [OpenAlex 抓取脚本](../../data/sources/_scripts/fetch_openalex.py)
- [Safety Gate 留痕缺口申报](../../data/sources/eu_safety_gate/manifest.json)（审计时的 `provenance_resume.csv` 空壳已于 2026-11-26 移除，缺口改由 manifest `provenance_gaps` 申报）
- [知乎真实快照](../../data/snapshots/zhihu/旅行收纳包.json)
- [许可原件索引](../../data/licenses/README.md)
- [项目交接状态页](../status/STATUS.md)

---

## 3. 数据规模、覆盖与原始到主表的转换

| 来源 | 主表规模 | 实际时间覆盖 | 原始数据规模 | 转换结果 |
|---|---:|---|---|---|
| Amazon Reviews 2023 | 6,207 行 | 2021-01-01～2023-08-30 | 评论 JSONL 16,216 行；meta JSONL 641 行 | 窗口过滤、PII 清洗、meta 联结、文本截断后 6,207 行 |
| Eurostat ISOC | 13,093 行 | 2021～2025 | 当前数据集 15,957 个 JSON-stat 值；历史数据集 106,294 个值 | 展平并保留窗口内观测 13,093 行 |
| EU Safety Gate | 3,255 行 | 2021-01-08～2026-11-20 | 302 期 XML、19,677 条通知 | 德国相关筛选后 3,255 条，case number 唯一 |
| OpenAlex | 2,455 行 | 2021～2026 | 仅落盘 5 个主题的第 1 页，共 500 条 | 第 1～5 页合并、按 Work ID 去重后 2,455 行 |
| GDELT | 1,090 行 | 2021-06-24～2023-01-01 | 6 个 JSON 响应、1,091 篇文章 | 按 URL 去重后 1,090 行 |
| GERestaurant | 3,078 行 | 静态基准，无逐条日期 | `dataset_filtered.json` 3,078 条 | PII 清洗、aspect 展开、派生 stance |
| MARC | 10,000 行 | 官方采集期 2015-11～2019-11，无逐条日期 | test/validation JSONL 各 5,000 行 | 星级还原、PII 清洗、派生 stance |
| Eurostat Comext | 1,924 行 | 月度 2021-01～2026-09；年度 2021～2025 | 26 个 JSON-stat 响应 | 年度 130 行 + 月度 1,794 行 |
| USAGE | 25,292 标注 + 1,233 评论 | 静态基准，无逐条日期 | 官方 tar.gz，116 个成员、91 个文件 | a1 span 主表 + 评论级汇总表 |
| 知乎快照 | 3 条卡片 | 采集于 2026-11-18；内容发布日 2026-07-29～2026-11-11 | 3 次搜索、30 条返回、5 条相关片段 | 仅保留有发布日的 A/B/D 三条 |

---

## 4. 逐源结构与内容

### 4.1 Amazon Reviews 2023

**来源与定位**

- 提供方：McAuley Lab / UCSD。
- 实际渠道：`hf-mirror.com` → 官方 CDN。
- 许可：Apache-2.0。
- 层级：L1 数据集类别，但当前样本为 **Amazon.com 美国站**。
- 试点分片：`Subscription_Boxes`，与旅行收纳包无直接品类关系。

**主表**

`amazon_reviews_2023_pilot_2021_2026.csv`，6,207 行。

```text
shard, category, asin, parent_asin, item_title, price_usd,
rating, title, text, timestamp_ms, review_date,
verified_purchase, helpful_vote
```

**内容特征**

- `title` 截断至 200 字符，`text` 截断至 600 字符。
- 主表不保留 `user_id`，原始 JSONL 保留完整字段。
- `verified_purchase=True` 5,328 行，`False` 879 行。
- 价格字段 `price_usd` **6,207 行全部为空**。
- 565 行正文达到 600 字符截断上限。

**实测质量问题**

- 按 `(asin, timestamp_ms)` 计有 6,146 个唯一键，存在 **61 行重复键**。
- 其中 **60 行为完全重复记录**。
- **10 行正文为空**。
- 主表没有原生 `review_id`，只能使用弱组合键去重。

**使用边界**

只能用于美国站管线试点和方法演练，不得作为德国市场证据；`item_title` 等卖家元数据只能进企业假设侧。

---

### 4.2 Eurostat ISOC

**来源与定位**

- 提供方：Eurostat。
- 格式：JSON-stat 2.0。
- 许可：Eurostat 开放数据复用政策。
- 层级：L3 宏观市场语境。

**主表**

`eurostat_isoc_de_2021_2026.csv`，13,093 行。

```text
dataset, year, geo, indicator_code, indicator_label, unit,
ind_type_code, ind_type_label, value
```

**内容特征**

- 地理固定为 `DE`。
- 实际覆盖 2021～2025；2026 调查年尚未发布。
- `isoc_ec_ibuy` 是 2002～2019 历史数据集，106,294 个观测全部在项目窗口外，未进入主表。
- 业务键 `(dataset, year, geo, indicator_code, unit, ind_type_code)` 无重复。

**使用边界**

描述德国个人线上购买总体行为，不描述具体商品或卖点偏好。

---

### 4.3 EU Safety Gate / RAPEX

**来源与定位**

- 提供方：European Commission。
- 格式：周报索引 XML + 逐期明细 XML。
- 许可：CC0-1.0，须署名。
- 层级：L3 监管信号。

**主表**

`safety_gate_de_alerts_2021_2026.csv`，3,255 行。

```text
case_number, report_reference, publication_date, category,
product, product_name, brand, barcode, risk_type, risk_level,
danger, measures, notifying_country, country_of_origin, de_relation
```

**内容特征**

- 302/302 期周报完整，原始 XML 共 19,677 条通知。
- 德国相关关系：`notifying` 2,806、`origin` 446、`mentioned` 3。
- `case_number` 唯一，无重复。
- `danger` 截断至 600 字符，`measures` 截断至 400 字符。
- 98 行危害描述达到截断上限；329 行措施达到截断上限。

**字段缺失**

| 字段 | 空值行数 | 占比 |
|---|---:|---:|
| `product_name` | 390 | 12.0% |
| `brand` | 350 | 10.8% |
| `barcode` | 2,309 | 70.9% |

**品类偏差**

- Motor vehicles：1,504 行，占 46.2%。
- 旅行收纳近邻品类合计 519 行：Toys 271、Childcare 94、Chemical products 66、Clothing/textiles/fashion 57、Hobby/sports 31。
- 不先过滤品类会被汽车召回主导。

**采集结构注意**

- 明细 XML 使用重复的 `<notifications>`（复数）元素，不能按单数 `<notification>` 解析。
- 当前 `provenance_resume.csv` 只有表头，README 所述 44 期在线补抓留痕未实际保留。
- README 记录电话清洗 34 处；主表实测为 **36 个 `[phone-removed]` 标记、涉及 35 行**，文档计数已漂移。

**使用边界**

是监管缺陷判定，不是消费者偏好表达。

---

### 4.4 OpenAlex

**来源与定位**

- 提供方：OpenAlex / OurResearch。
- 格式：REST JSON。
- 许可：开放数据。
- 层级：L3 学术方法论引用。

**主表**

`openalex_works_2021_2026.csv`，2,455 行。

```text
topic_key, openalex_id, doi, title, publication_year,
publication_date, type, cited_by_count, language, first_author,
venue, primary_topic, is_oa
```

**内容特征**

- 5 个主题，每主题取相关性前约 500 条。
- API 命中总数合计 1,024,115；实际保留 2,455，属于**方法论样本**，不是文献计量普查。
- 开放获取 2,035 行。
- 英语 2,435 行，占绝对多数。
- `openalex_id` 在当前主表中跨主题无重复。

**字段缺失与截断**

- DOI 空值 127 行，占 5.2%。
- `first_author` 空值 23 行。
- `venue` 空值 41 行；21 行达到 120 字符截断上限。
- `language` 空值 1 行。

**原始响应缺陷**

- `raw/` 仅有 5 个 `*_p1.json`，共 500 条结果。
- 第 2～5 页共 **20 个原始响应未落盘**。
- 主表剩余 **1,955 行不能从当前 raw 完全重建**。
- 抓取脚本只在 `page == 1` 时调用 `save_raw`，这是脚本设计缺陷，不是文件丢失。

**使用边界**

用于方法论引用和背景检索，不可支撑消费者偏好，也不可把 2,455 行当作领域规模。

---

### 4.5 GDELT DOC 2.0

**来源与定位**

- 提供方：The GDELT Project。
- 格式：REST JSON。
- 许可：无限制使用，须署名。
- 层级：L3 媒体二手语境。

**主表**

`gdelt_de_coverage_2021_2026.csv`，1,090 行。

```text
query_key, query, half_year, seen_date_utc, title, domain,
source_country, language, url, citation
```

**内容特征**

- 6 个原始 JSON 响应，共 1,091 篇文章；按 URL 去重后 1,090 行。
- 只有标题、域名、链接和元数据，没有正文。
- `seen_date_utc` 是 GDELT 首次发现时间，不是文章发布时间。
- German 1,066 行，其余为 English、French、Spanish、Russian、Polish、Portuguese。

**采集缺陷**

- 2023～2026 窗口因 429 未取回。
- `en_luggage_de_src` 四个窗口均触及 250 条上限。
- 四窗 1,000 条实际只覆盖 33 天 / 730 天，约 4.5%。
- 全表时间覆盖密度仅 15.1%。
- 高密度查询使用 `sort=datedesc + maxrecords=250`，样本集中在窗口末端。

**使用边界**

只能验证检索式、取定性标题示例；禁止趋势、跨时间比较和报道量级统计。

---

### 4.6 GERestaurant

**来源与定位**

- 数据来源：GitHub fork `kartik-gadhvi/GERestaurant` 的 `dataset_filtered.json`。
- 上游官方仓库不含标注数据，HF 渠道不可达。
- 许可：按 CC-BY-4.0 使用；上游仓库无 LICENSE 文件，正式商用前需再确认。
- 层级：BENCHMARK。

**主表**

`gerestaurant_reviews_3078.csv`，3,078 行。

```text
review_id, text, aspect_labels, aspect_polarities,
n_aspects, gold_stance
```

**内容特征**

- 德语餐厅评论，5 类 aspect，4,314 条 aspect 标注。
- `gold_stance` 为派生值：support 1,508、oppose 1,323、insufficient 247。
- `review_id` 唯一。
- 主表 text 已清洗 PII，raw JSON 保留未清洗文本。

**采集缺陷**

- 数据来自 fork 快照，无法与作者原始分发件逐字节比对。
- 餐厅域与旅行收纳商品域不匹配。
- `gold_stance` 不是原生标签，而是规则推导值；`insufficient` 混合真中性和混合评价。

**使用边界**

只作德语立场基线评测，不进证据卡，不外推商品域。

---

### 4.7 MARC 德语商品评论

**来源与定位**

- 实际来源：`mteb/amazon_reviews_multi` 镜像。
- 官方 HF 仓库已下架。
- 许可：Amazon 学术研究许可，research-only，禁再发布和商业使用。
- 层级：BENCHMARK。

**主表**

`marc_reviews_de_10000.csv`，10,000 行。

```text
review_id, text, stars, label, gold_stance, split
```

**内容特征**

- test 5,000 + validation 5,000。
- 1～5 星各 2,000 行，是均衡评测设计，不代表自然评分分布。
- `gold_stance` 由星级推导：4～5 星 support，1～2 星 oppose，3 星 insufficient。
- `review_id` 唯一。

**采集缺陷**

- 官方 `product_category`、`product_id`、`reviewer_id`、独立 `review_title` 字段在 MTEB 重构版中丢失。
- 无法按商品品类筛选旅行收纳样本。
- train 分片 201,197 条未下载。
- 数据采集期止于 2019-11，时效性不足。
- 本地 raw 保留未清洗文本，主表为清洗衍生表；两者均受研究许可约束，不能进入公开仓库。

**使用边界**

只作学术评测；商业化路径启动即下线。

---

### 4.8 Eurostat Comext

**来源与定位**

- 数据集：`DS-045409`。
- 口径：reporter=DE，partner=CN，flow=IMPORT。
- 产品：HS4 4202 + 12 个 HS6 子目。
- 许可：Eurostat 开放数据。
- 层级：L3 贸易语境。

**主表**

`eu_comext_ds045409_de_cn_hs4202_2021_2026.csv`，1,924 行。

```text
dataset, period_type, period, year, month, reporter, partner,
flow, flow_label, product, product_label_en, indicator, value
```

**内容特征**

- 年度 130 行，月度 1,794 行。
- 月度 2021-01～2026-09，共 69 个月。
- 年度仅 2021～2025；2026 年度未发布。
- 指标为 `VALUE_IN_EUROS` 和 `QUANTITY_IN_100KG`。
- 业务键 `(period_type, period, reporter, partner, flow, product, indicator)` 无重复。
- 月度求和与年度值对账一致，并与 DS-059341 交叉验证一致。

**结构风险**

- 同一产品、同一指标同时存在年度行和月度行，**直接对全表求和会重复计算**。
- 某月无观测行不等于确认零贸易。
- CN 不含香港、澳门、台湾。
- 2026 只有 9 个月，不能表述为全年。

**采集缺陷**

- CN8 八位细目 API 不可得，bulk 未取，当前最深到 HS6。

**使用边界**

用于品类市场存在性和贸易趋势语境，不构成消费者偏好。

---

### 4.9 USAGE / Bielefeld

**来源与定位**

- 版本：v1.0.2。
- 许可：标注数据 ODC-By 1.0；项目注册表保持保守非商用口径。
- 层级：BENCHMARK。

**主表 1：span 标注**

`usage_annotations_25292.csv`，25,292 行。

```text
annotation_id, review_id, lang, category, span_type, span_text,
char_start, char_end, polarity, target_annotation_ids,
target_span_texts, coref_annotation_ids
```

**主表 2：评论汇总**

`usage_reviews_1233.csv`，1,233 行。

```text
review_id, lang, category, asin, amazon_review_id,
n_aspect, n_subjective, subjective_polarities,
n_relations, gold_stance
```

**内容特征**

- 英语 622 条、德语 611 条。
- aspect 14,885 条，subjective 10,407 条。
- `annotation_id` 和 `review_id` 均唯一。
- 字符偏移与 span 词面长度全量一致，未发现偏移错误。
- 目标关系和共指引用未发现悬空 ID。
- `gold_stance` 为派生值：support 538、oppose 79、insufficient 616。

**采集缺陷**

- 公开包**不含评论原文**，只有 span 词面、偏移和关系。
- 无法执行依赖全文上下文的规则立场评测。
- 主表仅含标注者 a1；a2 保留在 raw，但未做标注者一致性分析。
- `insufficient` 占 50%，是短语极性聚合口径的结构性结果，不能直接与 GERestaurant 比较。

**结构风险**

- 评论表与标注表是一对多关系，直接 join 会把一条评论扩展成多行，评论数必须先在评论表统计。

**使用边界**

只作 span 级标注基准，不进证据卡。

---

### 4.10 知乎真实快照

**文件**

`data/snapshots/zhihu/旅行收纳包.json`

**结构**

```text
generated_at_utc
source_api
is_demo_data
captured_at
captured_via
provenance
notes[]
cards[]
```

每张卡片包含标题、匿名作者 ID、摘录、链接、发布日期、层级、语言、样本量、stance、AuthorityLevel、赞同数、评论数、ContentID。

**内容**

- 3 次搜索，共 30 条返回，识别 5 条相关片段。
- 当前保存 A/B/D 三条，发布日期分别为 2026-11-11、2026-10-10、2026-07-29。
- C/E 因缺少发布日期元数据未收录。
- 摘录最长 113 字符，符合 ≤300 字符要求。
- `is_demo_data=false`，全部为真实采集转录。

**采集缺陷**

- 没有保存 API 原始响应，只有人工转录后的快照。
- `generated_at_utc=2026-11-21` 与 `captured_at=2026-11-18` 语义不同，消费端若只看生成时间会误判新鲜度。
- 5 条相关片段中 2 条因日期缺失被排除，快照不是完整采集结果。
- 知乎搜索实测配额仅 10 次/日，无法支撑大规模实时采集。

**使用边界**

知乎内容属于 L2，只能生成待验证问题，不能作为德国消费者证据。

---

## 5. 采集缺陷清单

### 5.1 P0：阻塞核心业务结论

| ID | 缺陷 | 证据 | 影响 | 建议 |
|---|---|---|---|---|
| D-01 | 德国消费者一手反馈零样本 | 9 个来源中无德国站、旅行收纳包域、带样本框的 L1 数据 | 无法完成德国偏好判定，只能输出证据不足 | 获取品牌方授权的德国站评论/反馈导出 |
| D-02 | Amazon 市场与品类不匹配 | 美国站、无 marketplace/language 列、Subscription_Boxes 分片、价格全空 | 不能作为德国 L1，也不能代表旅行收纳市场 | 保留为管线试点；需求侧另取德国授权数据 |

### 5.2 P1：影响分析可靠性或可复现性

| ID | 缺陷 | 证据 | 影响 | 建议 |
|---|---|---|---|---|
| D-03 | GDELT 稀疏且截断 | 2023～2026 缺失；4 窗触顶 250；密度 15.1% | 趋势、量级、跨时间比较无效 | 改用 ngrams 或按周/月细分并滚动游标 |
| D-04 | OpenAlex 原始响应不完整 | 25 次调用，仅 5 个 p1 raw；缺 20 个 p2～p5 文件 | 1,955 行不能从 raw 离线重建 | 每页均 `save_raw`；重跑或补抓并校验 SHA |
| D-05 | Amazon 主表质量低 | 61 个重复键、60 行完全重复、10 行空正文、6,207 行价格全空、无 review_id | 去重、价格分析、样本量统计失真 | 增加稳定评论 ID；按原始 ID 去重；空正文隔离；修复 meta 价格联结 |
| D-06 | 评测基准适用性和许可受限 | GERestaurant 餐厅域/fork；MARC research-only/品类字段丢失；USAGE 无文本层 | 不能作为目标市场证据，部分基准无法做全文评测 | 保持 tier 闸门；补领域对齐基准；商用前完成许可审查 |
| D-07 | 样本选择偏差与衍生截断 | OpenAlex 每主题前 500；Amazon 最小分片；Safety Gate 德国筛选；多表文本截断 | 行数不能代表总体，细节分析可能丢失上下文 | 明确样本框；保留原文引用；分析前按用途过滤 |

### 5.3 P2：影响治理、聚合或长期维护

| ID | 缺陷 | 证据 | 影响 | 建议 |
|---|---|---|---|---|
| D-08 | 请求留痕不完整 | Safety Gate/GDELT provenance 为 `FROM_RAW`；`provenance_resume.csv` 只有表头 | 原始 URL、状态码、耗时无法完整追溯 | 在线抓取与重建留痕分开保存，禁止覆盖历史 |
| D-09 | 知乎快照缺原始响应 | 只有转录 JSON；5 条相关片段仅保存 3 条 | 无法逐字复核 API 返回，完整性不足 | 保存脱敏 raw payload 与排除原因清单 |
| D-10 | 行数口径和聚合语义不统一 | 66,394 / 67,627 / 42,335 三种口径；Comext 混合年月；USAGE 一对多 | 容易重复计算或误报规模 | 文档统一口径；建模时显式 granularity；先聚合再 join |
| D-11 | 时效与粒度缺口 | Eurostat 2026 未发布；Comext 2026 仅到 9 月且无 CN8；MARC 止于 2019 | 不支持实时或细目结论 | 在卡片和 API 返回中强制展示数据截止与粒度 |
| D-12 | 元数据与原始数据治理不足 | Safety Gate 电话清洗文档写 34，实测 36；多个 raw 保留未清洗 PII | 文档漂移；原始数据误发布风险 | 自动生成计数；raw 访问控制；公开仓库仅保留衍生数据 |

---

## 6. 数据质量与校验结果

### 6.1 已通过的校验

| 校验 | 结果 |
|---|---|
| 来源结构校验 | 9/9 通过 |
| 时间覆盖校验 | 通过；GDELT 正确标记为 SPARSE |
| 后端测试 | 181 passed |
| JSON/JSONL 解析 | 已检查文件无解析错误 |
| Safety Gate XML | 302 个报告全部可解析 |
| USAGE gzip/tar | CRC 与包结构校验通过 |
| 可映射 provenance 哈希 | 359 条全部与实际文件一致 |
| 许可原件哈希 | 8/8 一致 |
| USAGE 偏移与关联引用 | 0 个长度不一致；0 个悬空引用 |
| Comext/Eurostat 业务键 | 0 重复 |

### 6.2 哈希核验分布

| 来源 | provenance 记录 | 已验证 | 缺原始文件 | 未映射探测 |
|---|---:|---:|---:|---:|
| Amazon | 11 | 7 | 0 | 4 |
| Comext | 26 | 26 | 0 | 0 |
| Safety Gate | 303 | 303 | 0 | 0 |
| Eurostat ISOC | 2 | 2 | 0 | 0 |
| GDELT | 6 | 6 | 0 | 0 |
| GERestaurant | 2 | 2 | 0 | 0 |
| MARC | 4 | 4 | 0 | 0 |
| OpenAlex | 25 | 5 | 20 | 0 |
| USAGE | 4 | 4 | 0 | 0 |
| **合计** | **383** | **359** | **20** | **4** |

### 6.3 当前校验器的盲区

`validate_sources.py` 主要检查四件套、主表非空、许可字段和截断声明，但不会自动发现：

- OpenAlex 声明 5 页，raw 实际只有 1 页。
- manifest 行数与实际 CSV 行数不一致。
- provenance 指向的 raw 文件缺失或哈希不匹配。
- Amazon 重复键、空正文、价格全空。
- 知乎快照缺少 raw payload。
- Safety Gate `provenance_resume.csv` 只有表头。
- 静态 benchmark 的统一样本窗字段被误当作真实日期覆盖。

建议把这些检查加入 `scripts/check.sh`。

---

## 7. 修复优先级与验收标准

### P0：解除德国 L1 阻塞

**动作**

- 获取品牌方授权的德国站评论或反馈导出。
- 数据至少包含：marketplace、language、product_id、category、review_id、review_date、rating、verified_purchase、text、sample_frame、export_batch。
- 保留授权范围、样本框、导出时间和许可说明。

**验收标准**

- 能识别德国市场与语言。
- 能筛选旅行收纳相关商品。
- 有稳定评论 ID 和可审计样本量。
- 原始导出、清洗日志、衍生表三级留痕。
- 授权允许预期使用场景。

### P1：修复数据可靠性与可复现性

1. **OpenAlex**
   - 每页保存 raw。
   - 校验 `len(raw pages) == provenance pages == manifest.max_pages`。
   - 从 raw 重建主表结果与当前 CSV 一致。

2. **Amazon**
   - 使用原始稳定评论 ID 去重。
   - 空正文单独标记，不静默删除。
   - 修复 `price_usd` meta 联结。
   - 输出去重前后行数报告。

3. **GDELT**
   - 若只需定性示例，维持当前禁用趋势声明。
   - 若需趋势，改用 ngrams 或按周/月窗口采集，并记录每窗是否触顶。

4. **评测基准**
   - GERestaurant 保留 fork 来源声明，商用前确认许可。
   - MARC 继续禁止公开数据本体和商业使用。
   - USAGE 保持无文本层声明，不伪装成全文基准。

### P2：完善治理与文档

- 在线 provenance 与 `FROM_RAW` 重建 provenance 分文件保存。
- 知乎快照增加脱敏 raw payload 引用。
- 统一“主表行 / 评论行 / 标注行”口径。
- 为 Comext 增加 `granularity` 建模约束，禁止年月混算。
- 为 USAGE join 增加先聚合说明或物化评论特征表。
- 自动生成 PII 清洗计数、缺失率、重复率和文件哈希报告。
- 在 API 响应和前端卡片强制展示数据截止时间与样本限制。

---

## 8. 数据使用边界矩阵

| 数据 | 可做的分析 | 禁止的用法 |
|---|---|---|
| Safety Gate | 德国监管风险、品类缺陷、合规问题 | 消费者偏好、满意度 |
| Eurostat ISOC | 德国线上购买宏观基线 | 具体商品卖点偏好 |
| Comext | 中德贸易规模、HS 品类趋势 | 消费者需求、品牌偏好 |
| GDELT | 检索式验证、定性媒体示例 | 趋势、量级、跨时间比较 |
| OpenAlex | 方法论引用、学术背景 | 文献计量普查、消费者证据 |
| Amazon 美国试点 | 管线测试、美国样本方法演练 | 德国 L1、旅行收纳市场结论 |
| GERestaurant | 德语餐厅域立场基线 | 商品域外推、证据卡 |
| MARC | 德语商品域学术评测 | 商用、公开再发布、证据卡 |
| USAGE | span 标注与关系结构评测 | 全文立场评测、证据卡 |
| 知乎快照 | 中文经验、待验证问题 | 德国消费者证据、全文建库 |

---

## 9. 结论

当前数据集已经能够支撑：

- 数据接入、清洗、留痕、校验和降级管线；
- 德国监管与贸易语境展示；
- 德语立场抽取的双域基线评测；
- 知乎 L2 经验生成待验证问题；
- 证据不足状态的诚实呈现。

当前数据集仍然不能支撑：

- 德国消费者对旅行收纳包具体卖点的偏好判定；
- 基于德国一手反馈的统计显著性结论；
- 2023 年以后完整的德国媒体趋势；
- CN8 级贸易结构分析；
- 将美国、餐厅域或研究许可数据外推为德国商品域证据。

**最高优先级不是继续扩大数据行数，而是获取一个市场正确、品类相关、授权清晰、带样本框的德国 L1 数据集。** 在其到位前，应继续保留“证据不足”作为核心产品状态，而不是用现有 L2/L3/benchmark 数据填补需求侧空白。
