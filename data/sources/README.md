# CrossPilot 数据区

本目录是所有外部数据的**唯一落地处**。每个来源一个子目录，结构强制统一。

抓取日期：2026-11-20 / 2026-11-21 ｜ 时间窗：**2021-01-01 ~ 2026-12-31**

## 一、目录约定

每个来源目录必须含以下四件：

| 文件 | 作用 | 强制 |
|---|---|---|
| `README.md` | 来源、许可、层级、字段说明、使用约束、复现命令 | 是 |
| `<source>_<window>.csv` | 可追溯主表，UTF-8-BOM，长表格式 | 是 |
| `provenance.csv` | **一行一次 HTTP 调用**：URL、状态码、字节数、耗时、SHA-256、UTC 时间 | 是 |
| `manifest.json` | 机器可读元数据：时间窗、许可、层级、行数、截断记录 | 是 |
| `raw/` | 原始响应，未经改动，供复核 | 是 |

`_scripts/` 存放抓取脚本，`common.py` 单点定义时间窗与留痕逻辑。

## 二、已入库来源

| 目录 | 来源 | 层级 | 凭据 | 许可 | 主表行数 | 实际覆盖 | 完整性 |
|---|---|---|---|---|---|---|---|
| `eurostat_isoc/` | Eurostat ISOC 德国线上购买 | L3 | 无 | Eurostat 开放数据 | 13,093 | 2021–2025 | 源端 2026 未发布 |
| `eu_safety_gate/` | EU Safety Gate (RAPEX) 德国相关警报 | L3 | 无 | CC0-1.0 | **3,255** | 2021-01 – 2026-11 | **302 份报告，缺 0 份**；299 个发布日，按周更折算 97.7% |
| `openalex/` | OpenAlex 跨境认知与 ABSA 文献 | L3 | 无 | 开放 | 2,454 | 2021–2026 | 每主题前 500 条；raw 25/25 页完整 |
| `gdelt/` | GDELT DOC 2.0 德语媒体语境 | L3 | 无 | 须署名 | 1,090 | **仅 2021H1–2022H2** | ⚠️ **限速致 2023–2026 缺失；且已取回窗口时间覆盖仅 15.1%** |
| `amazon_reviews_2023/` | Amazon Reviews 2023 试点 | L1* | 无 | Apache-2.0 | **6,146** | 2021-01 – 2023-09 | ⚠️ **试点：仅全库最小分片（美国站）；源数据止于 2023-09**；已按稳定 `review_id` 去重 |
| `gerestaurant/` | GERestaurant 德语餐厅评论 ABSA 标注 | BENCHMARK | 无 | CC-BY-4.0 | **3,078** | 静态基准，无时间序列 | 单文件完整下载（3,078/3,078） |
| `marc/` | MARC 德语商品评论（mteb 镜像路径） | BENCHMARK | 无 | 研究许可（**硬约束 2**） | **10,000** | 静态基准，无时间序列 | de test+validation 各 5,000，SHA-256 全留痕 |
| `eu_comext/` | Eurostat Comext DS-045409 HS4202 中国→德国贸易 | L3 | 无 | Eurostat 开放数据 | **1,924** | 2021–2026 | 年度 130 + 月度 1,794；双库交叉互验；CN8 细目 API 不可得 |
| `usage_bielefeld/` | USAGE（Bielefeld）英德评论立场标注基准 | BENCHMARK | 无 | ODC-By 1.0 | **25,292**（另 1,233 条评论汇总表） | 静态基准，无时间序列 | 单包完整下载（gzip CRC + 规模断言 622/611） |

### 2.0 行数口径（三种，不可混用 —— 修复 D-10）

同一批数据按聚合粒度有三个正确但不同的总数，混用会造成规模误读：

| 口径 | 行数 | 定义 | 适用场景 |
|---|---:|---|---|
| 全部 CSV 行 | **67,565** | 10 个主表实际行数之和 | 存储与文件体量描述 |
| 主表口径 | **66,332** | 排除 USAGE 评论汇总表（1,233 行，与 span 表一对多） | 对外描述"数据区规模" |
| 记录/评论级 | **42,273** | 在全部 CSV 行基础上排除 25,292 行 span 标注 | 描述"多少条评论/记录" |

引用规模时必须说明用的是哪个口径。USAGE 的评论表与标注表是**一对多**关系，
直接 join 会把一条评论扩展成多行，**评论数必须先在评论表统计**；Comext 主表
同时含年度行与月度行，**直接对全表求和会重复计算**，须先按 `period_type` 过滤。

> 数字随重抓变动：2026-11-24 重抓 OpenAlex（2,455→2,454，上游相关性排序漂移）
> 并对 Amazon 按稳定 `review_id` 去重（6,207→6,146），故本节三个总数相应更新。

> **公开仓库说明（2026-11-21）**：`marc/` 主表 CSV 因 Amazon 学术研究许可**禁再发布**
> 不随仓库分发（本地保留，凭 `_scripts/fetch_marc.py` 复现），见其 README 首节；
> 其余来源许可均允许随仓库分发并已在各源 README 署名。

**L1\* 说明**：`amazon_reviews_2023` 数据集类别是一手消费者反馈（L1），但实测为 **Amazon.com 美国全站数据，无 marketplace/language 列，无法筛出德国子集**（官方 tags 标 language:en）——对德国市场不构成 L1 证据，不得用英文评论冒充德国市场证据，详见其 README 第二节。其余四个来源均为 L3，按 `docs/CONSTRAINTS.md` 硬约束 1，不能单独支撑消费者偏好结论，只能作市场语境、监管信号与方法论引用。`gerestaurant/` 为 BENCHMARK 基准（餐厅域），只作立场基线评测，不进证据卡；`usage_bielefeld/` 为 BENCHMARK 基准（商品域 span 标注，无文本层），只作 span 级评测基准，不进证据卡。

### 2.1 已知缺口（写在显眼处，避免误用）

| 来源 | 缺口 | 影响 |
|---|---|---|
| `gdelt/` | ① 2023–2026 全部半年窗因 429 未取回；② 已取回的 4 窗触顶 250 条，**`en_luggage_de_src` 四窗共 1000 条实际只覆盖 33 天 / 730 天（4.5%）**；③ 全表时间覆盖密度 15.1% | **禁止**用于趋势分析、跨时间比较、量级统计。仅可验证检索式与取定性示例 |
| `eurostat_isoc/` | 2026 调查年数据源端未发布 | 非抓取失败，属正常时滞 |
| `openalex/` | 每主题仅取相关性前 500 条（命中总数达数十万） | 用于方法论引用，不可当作文献计量普查。**原始响应已补齐 25/25 页**（修复 D-04），主表可离线逐字节重建 |
| `eu_safety_gate/` | Motor vehicles 占 **1,504 / 3,255（46%）**（2026-11-21 复核修正，早期记录 1,167 有误） | 品类分析前必须先过滤，否则结论被汽车召回主导 |
| `amazon_reviews_2023/` | **覆盖不完整**：试点仅取全库最小分片 Subscription_Boxes（8.5MB，16,216 条中窗口内去重后 6,146 条）；源数据止于 2023-09，窗口 2023-10–2026-12 源端无数据；品类无关（订阅盒子 vs 旅行收纳）；**`price_usd` 全列为空**（上游 meta 641 条 price 全 null） | 仅作管线试点与美国站样本；不得当作全库覆盖声明；不可做价格分析；品类相关分片（Clothing_Shoes_and_Jewelry 26.5GB 等）超试点预算未下载 |
| `gerestaurant/` | **餐厅域 + fork 来源**：上游仓库 `.gitignore` 排除数据文件，数据原件取自 fork `kartik-gadhvi/GERestaurant`（提交 2024-09-13），无法与作者原件逐字节比对 | **禁止外推为商品域**；只作立场基线评测，不进证据卡；金标立场为推导值（非数据集原生字段） |
| `usage_bielefeld/` | **无文本层**：公开版不含评论原文（版权），只有标注 span 词面 + 字符偏移；金标立场为派生口径（insufficient 占 50%），规则立场基线无法在其上评测 | 只作 span 级标注基准，不进证据卡；不产 baseline_eval.md；获取原文须走作者渠道（本项目不执行 Amazon 爬取） |
| `marc/` | **商品域基线退化**：规则基线在 MARC 商品域 accuracy 0.580，低于 GERestaurant 餐厅域 0.610（域退化 -0.030，商品缺陷词不在餐厅域词表）；数据止于 2019-11 | 只作立场基线双域评测对照，不进证据卡；商业化路径启动即下线（硬约束 2） |
| `eu_comext/` | CN8 八位细目 API 实测 400 不可得，bulk 数据未取，主表仅到 HS4 章级 | 只作品类市场存在性语境；细分到 CN8 的贸易结构分析不可用 |

**时间覆盖密度**（`validate_coverage.py` 实测，按来源固有发布节奏折算）：

| 来源 | 密度 | 判定 |
|---|---|---|
| `eu_safety_gate/` | 97.7%（299 期 / 应有 306 期，周更） | OK |
| `amazon_reviews_2023/` | 91.5%（889 个日期 / 跨度 972 天） | OK |
| `eurostat_isoc/` | 83.3%（5/6 年） | OK |
| `openalex/` | 56.2%（1,208 个日期 / 跨度 2,148 天） | OK |
| `gdelt/` | **15.1%**（84 个日期 / 跨度 557 天） | **SPARSE，已在 manifest 声明** |
| `eu_comext/` | 100%（6/6 年，月度序列 2021–2026） | OK |
| `gerestaurant/` | —（静态标注基准，无发布日期节奏） | 校验不适用（未列入 TABLES，manifest 已声明 `time_coverage_applicable: false`） |
| `usage_bielefeld/` | —（静态标注基准，无发布日期节奏） | 校验不适用（未列入 TABLES，manifest 已声明 `time_coverage_applicable: false`） |

## 三、脚本

| 脚本 | 作用 |
|---|---|
| `_scripts/common.py` | **时间窗单点定义**（`WINDOW_START` / `WINDOW_END`）、带退避的 `fetch`、留痕 `Provenance` |
| `_scripts/fetch_eurostat.py` | Eurostat 抓取 + JSON-stat 展平 |
| `_scripts/fetch_safety_gate.py` | Safety Gate 周报索引 → 逐期明细 |
| `_scripts/resume_safety_gate.py` | **仅补缺失期次**，可反复运行直至完整 |
| `_scripts/fetch_openalex.py` | OpenAlex 多主题分页抓取（**每主题每页均落盘 raw**，修复 D-04） |
| `_scripts/fetch_gdelt.py` | GDELT 按半年窗抓取（强节流） |
| `_scripts/fetch_amazon_reviews.py` | Amazon Reviews 2023 经 hf-mirror.com 镜像试点接入（探测 + 分片下载 + 建表一体，429 按 retryAfter 退避，分片按字节数续传） |
| `_scripts/fetch_gerestaurant.py` | GERestaurant 经 GitHub codeload zip 接入（上游 + 数据 fork 各一次调用；zip 已落盘自动跳过，主表从本地 raw 重建即离线 rebuild） |
| `_scripts/fetch_marc.py` | MARC 经 mteb/amazon_reviews_multi 镜像 resolve 路径接入（503 抖动退避重试；SHA-256 全留痕；主表从本地 raw 重建即离线 rebuild） |
| `_scripts/fetch_eu_comext.py` | Comext DS-045409 专用 API 按过滤取数（官方明示禁止整库下载，无过滤请求会流式超时；月度求和与年度逐位互验 + DS-059341 双库交叉） |
| `_scripts/fetch_usage_bielefeld.py` | USAGE（Bielefeld）经官方发布页 romanklinger.de 接入（4 次下载：语料包/双语词典/发布页快照；服务器限速 timeout 300s；规模断言 622/611 不过即拒绝建表，主表从本地 raw 重建即离线 rebuild） |
| `_scripts/rebuild_from_raw.py` | **从本地 raw 重建主表，不发网络请求**，用于中断恢复与离线可复现性校验（Safety Gate / GDELT / OpenAlex）。重建留痕写入 `provenance_from_raw.csv`，**不覆盖**在线 `provenance.csv`（修复 D-08） |
| `_scripts/validate_sources.py` | **结构回归校验**（四件套齐全、许可声明、截断记录），已接入 `scripts/check.sh` |
| `_scripts/validate_coverage.py` | **时间覆盖密度校验**，识别"行数充足但时间覆盖极稀"的伪完整，已接入 `scripts/check.sh` |
| `_scripts/validate_quality.py` | **质量回归校验**（主表主键唯一、raw 逐页完整、manifest 行数与实表一致、留痕哈希、在线留痕未被覆盖、空正文标记、全空字段声明、PII 计数无漂移、快照原始响应引用），补齐前两个校验器的盲区，已接入 `scripts/check.sh` |

中断恢复的设计意图：原始响应一旦落盘就不再重抓。Safety Gate 首轮抓到 258 期被中断，用 `resume` 补 44 期（成功率 44/44），再 `rebuild` 得到完整主表，全程未重复下载已有期次。
（留痕注意：该批补抓的**在线调用明细未保留**，缺口已在
`eu_safety_gate/manifest.json` 的 `provenance_gaps` 显式申报；早期误留的空壳 `provenance_resume.csv` 已移除，`resume` 脚本无调用时不写空壳文件。）

## 四、未入库及原因

| 来源 | 原计划 | 未入库原因 |
|---|---|---|
| **Amazon Reviews 2023 全量** | L1 主数据栈，5.71 亿条 | 2026-11-21 起**试点已入库**（见上表）。全量 ≈220GB，且镜像共享配额 10000 次/5 分钟、无 parquet 分片（脚本加载型，/parquet 400）、datasets-server /rows /filter 在镜像上不可用——只能经 /resolve/ 整片下载，须分品类分批另立计划 |
| **GERestaurant（HF 原件）** | P0，HF 下载 | 2026-11-21 起**已入库**（见上表，经 GitHub fork 快照）。HF 原件渠道本机不可达（官方站 TCP 443 超时、hf-mirror 查无此库）；若 HF 恢复可达，可用作者原件复核 fork 快照的 SHA-256 |
| **Destatis GENESIS** | P0，匿名取表 | 域名已从 `www-genesis` 迁至 `genesis.destatis.de`（307 跳转）。匿名凭据 `GAST/GAST` 被重定向到注册公告页，**实际取数需注册**，故降级为 P1 |
| **GDELT 2023–2026** | P0，与 2021–2022 同批 | 限速。见 `gdelt/README.md` 第二节的间隔实测记录；官方建议大批量改用 ngrams 数据集 |
| **UN Comtrade** | P1 | preview 端点可调（200），但受硬约束 4 限制，正式取数须注册取 key |
| **eBay Browse / DeepL** | P1 | 端点连通正常（405 / 403 均为缺凭据的预期响应），需 keyset 与 API key |
| **知乎开放平台** | P2 | 需 Access Secret，实测额度 10 次/日 |
| **品牌自有授权数据** | P2 | 需品牌方授权，**无任何公开接口可替代** |

## 五、关键缺口（勿被数据量掩盖）

已入库 9 个来源（主表口径 66,332 行，三种口径见 2.0 节），但**德国消费者一手反馈（L1）仍为零样本**：

| 已有 | 性质 | 为何不能替代德国 L1 |
|---|---|---|
| `amazon_reviews_2023/` | 美国站一手消费者评论（试点） | **美国市场数据**，无 marketplace/language 列无法筛德国子集；对德国市场不构成 L1 |
| Safety Gate | 监管机构的缺陷判定 | 是合规结论，不是消费者偏好表达 |
| GDELT | 媒体报道标题 | 二手叙述，且不含正文 |
| Eurostat | 宏观统计百分比 | 描述总体行为，不针对具体商品卖点 |
| OpenAlex | 学术文献元数据 | 不含消费者原始发言 |
| `eu_comext/` | 中德贸易额官方统计 | 宏观贸易量，不构成任何消费者偏好表达 |
| `gerestaurant/` | 德语餐厅评论标注基准 | **餐厅域非商品域**，且金标为标注者判断，只用于基线评测 |
| `usage_bielefeld/` | 英德商品评论标注基准（Bielefeld USAGE） | **无文本层**（公开版不含评论原文，版权），只有 span 标注与短语词面，不构成一手反馈文本 |

解除该缺口的唯一路径是品牌方授权的德国站反馈导出，详见仓库外交接区 `handover/status/STATUS.md` 第 1 优先事项。Amazon Reviews 2023 的接入价值在于：管线验证（镜像路径打通、四件套与两层校验跑通）+ 美国市场对照样本。

## 六、入库纪律

- 新增来源必须同时在 `services/datasets.py:REGISTRY` 登记，否则适配器拒绝加载。
- 时间窗只在 `_scripts/common.py` 改，不在各脚本内散落硬编码。
- 分页上限类来源（GDELT 250、OpenAlex 100）触顶必须记入 `manifest.json` 的 `truncated_windows`；**截断与完整返回外观一致**，不记录等于埋坑（硬约束 4 的失败模式）。
- 自由文本来源须清洗邮箱与电话（Safety Gate 已做）。
- `raw/` 体积较大，受 `.gitignore` 的 `data/raw/` 规则影响时须显式确认是否入库。
