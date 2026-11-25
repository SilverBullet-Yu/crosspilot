# Amazon Reviews 2023 — 试点接入（Amazon.com 美国全站一手评论）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 提供方 | McAuley-Lab（UCSD），`McAuley-Lab/Amazon-Reviews-2023`（HF Hub） |
| 规模 | 5.71 亿条评论，34 个品类，1996-05 ~ 2023-09 |
| 凭据 | 无需注册、无需 key |
| 许可 | **Apache-2.0**（可商用，须保留许可声明） |
| 证据层级 | **L1 数据集类别**，但**对德国市场不可用**，见第二节 |
| 接入日期 | 2026-11-21（经 hf-mirror.com 镜像） |

## 二、证据层级定位（必读：德国市场适配性结论）

**结论：无法筛出德国/德语评论子集，对德国市场不构成 L1 证据。**

实测依据（零假设，全部来自 API 返回）：

1. 评论与商品元数据**均无 `marketplace`、`language` 列**，任何字段都无法标识市场或语言；
2. 官方 README 与 tags 标注 `language:en`，数据为 **Amazon.com（美国站）全站**采集；
3. 34 个品类全部为 Amazon.com 类目（`raw/all_categories.txt`），**无独立
   Luggage / Travel_Accessories 品类**——旅行收纳包散布在
   Clothing_Shoes_and_Jewelry（「Luggage & Travel Gear」部门，meta 仅
   `main_category`，无可靠子类列）、Amazon_Fashion、Sports_and_Outdoors 内；
4. 商品价格为美元。

因此本库只能用于：① 美国市场一手消费者反馈（L1）；② 评审方法学与证据卡
结构的管线试点。**不得**用英文评论冒充德国市场证据；德国侧 L1 仍只能走
品牌授权导出（见 `docs/status/STATUS.md` 第 1 优先事项）。写入消费者证据
侧前的闸门仍是 `services/datasets.py:assert_demand_side`，tier 维持 L1 不变，
但使用时必须知道这是美国市场样本（manifest `tier_caveat` 有同文说明）。

## 三、镜像能力边界（2026-11-21 实测，决定接入路径）

| 端点 | 结果 | 含义 |
|---|---|---|
| `huggingface.co` 官方站 | TCP 443 全程超时（复测） | 不可用 |
| `hf-mirror.com/api/datasets/{repo}` | **200**，1.3s | 元数据可达 |
| `.../parquet` | **400** | 数据集是脚本加载型（runs arbitrary Python code），viewer 不支持，**无 parquet 分片** |
| `.../tree/main`（含子目录） | **200** | 品类分片清单可用（34 个 jsonl 带精确字节数） |
| `/resolve/main/<file>` | **307 → 302 → cas-bridge.xethub.hf.co → 200** | 镜像本体只代理元数据与跳转，文件内容 302 到 HF 官方 CDN（本机可达）；支持 HEAD（`X-Linked-Size`/`X-Linked-Etag` 即字节数/sha256）与 Range（curl 实测 206） |
| datasets-server `/rows` | **不可用** | 307 重定向到 `/Rows` 网页路由，返回 HTML 非 JSON API（另测得一次 503，镜像共享配额抖动） |
| datasets-server `/filter` | **不可用** | 返回网页 HTML（用户页路由） |
| 共享配额 | 10000 次/5 分钟 | 超限返回 429 + `retryAfter` 秒数；脚本固定 2.5s 间隔并按 retryAfter 退避 |

**可用接入路径**：`/resolve/` 直下原始 jsonl 分片 + 本地过滤。
「≤100 行显式分页」路径（CONSTRAINTS 一之二）当前无生效场景；`page_limit=100`
保留在注册表，留作官方站可达后的约束。

## 四、本目录内容

| 文件 | 说明 |
|---|---|
| `amazon_reviews_2023_pilot_2021_2026.csv` | 可追溯主表，**6,146 条**窗口内去重评论 |
| `provenance.csv` | 一次调用一行的留痕（URL、状态码、字节、耗时、SHA-256、UTC），按 URL 去重合并，重跑不丢历史 |
| `manifest.json` | 机器可读元数据，`coverage_complete: false` + 德国适配性结论 + `quality_report` |
| `raw/all_categories.txt` | 34 个品类清单原件 |
| `raw/dataset_readme.md` | 官方 README（字段定义证据） |
| `raw/api_tree_main.json` 等 3 份 | tree API 响应原件（分片清单证据） |
| `raw/probe_summary.json` | 镜像探测结论缓存（重跑复用，不重复探测） |
| `raw/review_categories/Subscription_Boxes.jsonl` | 评论分片原件，8,953,020 字节，sha256 与镜像 Etag 一致 |
| `raw/meta_categories/meta_Subscription_Boxes.jsonl` | 对应商品元数据分片，1,399,864 字节 |

## 四之二、数据质量处置（2026-11-24，修复 D-05）

审计发现主表有重复键、空正文与价格全空三类问题。处置如下，计数全部由
`fetch_amazon_reviews.py` 自动写入 manifest 的 `quality_report`，并由
`data/sources/_scripts/validate_quality.py` 回归校验：

| 问题 | 旧状态 | 处置 | 现状 |
|---|---|---|---|
| 无原生评论 ID | 只能用弱组合键 `(asin, timestamp_ms)` 去重，窗口内 **61 个重复键** | 新增 `review_id` = `sha1(user_id\|asin\|timestamp)[:16]`，稳定可复现且不泄露 `user_id` | 主键唯一，重复键 **0** |
| 重复记录 | 60 行完全重复混在表内 | 按 `review_id` 去重，保留首条并统计丢弃数 | 丢弃 **61** 条（其中逐字段相同 59 条，字段有差异 2 条），主表 6,207 → **6,146** 行 |
| 空正文 | **10 行**空正文静默混入 | 新增 `is_empty_text` 标记列，**保留不删**，由下游按用途过滤 | 10 行已标记，标记与实际一致 |
| `price_usd` 全空 | 疑为 meta 联结缺陷 | 核查 meta 分片：641 条记录的 `price` 字段**上游全为 JSON null** | **非本地缺陷**；已在 manifest `price_usd_note` 声明，该列不可用于价格分析 |

**口径提醒**：主表行数由 6,207 变为 6,146 是去重结果，不是数据丢失；引用样本量
须以去重后的 6,146 为准。`quality_report.rows_in_window_before_dedup` 保留去重前
行数以便对账。

## 五、试点范围与覆盖情况（**覆盖不完整，勿当全量**）

| 项 | 值 |
|---|---|
| 分片选择 | **全库最小评论分片** Subscription_Boxes（8.5MB），管线试点而非全量迁移 |
| 分片总行数 | 16,216 |
| 窗口内（2021-01-01 ~ 2023-09） | 去重前 6,207 条 → **去重后 6,146 条**（2021: 3,643 / 2022: 2,045 / 2023: 458） |
| 实际日期范围 | 2021-01-01 ~ 2023-08-30，889 个不同日期，密度 91.5% |
| 源数据终点 | **2023-09**，窗口 2023-10 ~ 2026-12 源端无数据 |
| 总下载量 | ≈10.5MB（上限 200MB） |

覆盖局限（manifest 已声明，`validate_sources` 强制 README 警示）：

1. **覆盖不完整**：仅 1 个最小分片，行数不代表全库；且源数据止于 2023-09；
2. **品类无关**：Subscription_Boxes 与旅行收纳场景无直接关系，仅验证
   「下载 → 窗口过滤 → PII 清洗 → meta 联结 → 四件套落盘」管线；
3. 品类相关分片超预算：Clothing_Shoes_and_Jewelry 26.5GB、
   Sports_and_Outdoors 8.8GB、Amazon_Fashion 1.0GB，如需行李收纳相关样本
   须另立计划（可考虑 meta 分片的标题关键词切片检索，商品元数据属卖家
   文案，只能进企业假设栏）。

## 六、字段说明（主表）

| 列 | 含义 |
|---|---|
| `review_id` | **稳定评论 ID**：`sha1(user_id\|asin\|timestamp)` 前 16 位。源数据无原生 ID，此列为主表主键，去重与溯源均以它为准；哈希不可逆，不泄露 `user_id` |
| `shard` / `category` | 来源分片与品类（本试点均为 Subscription_Boxes） |
| `asin` / `parent_asin` | 商品 ID / 父品 ID（联结 meta 的键） |
| `item_title` / `price_usd` | 商品名与价格（来自 meta 分片；**卖家自撰文案**，仅作标注）。`price_usd` **全列为空**——上游 meta 分片 641 条 price 全为 null，不可用于价格分析 |
| `rating` | 1.0 ~ 5.0 |
| `title` / `text` | 评论标题 / 正文，**截断至 200 / 600 字符**，已清洗 PII（raw/ 保留全文）；560 行正文达到截断上限 |
| `timestamp_ms` / `review_date` | 毫秒时间戳与 UTC 日期 |
| `verified_purchase` / `helpful_vote` | 验证购买（True 5,276 / False 870）/ 有用票数 |
| `is_empty_text` | **空正文标记**：正文清洗后为空时为 True（10 行）。空正文不删除，由下游按用途过滤 |

评论字段全集还包括 `images`、`user_id`；主表**不写入 `user_id`**
（数据最小化，GDPR），原始分片保留在 `.gitignore` 的 `raw/` 内。
`review_id` 虽由 `user_id` 派生，但为单向哈希截断，不可还原原值。

## 七、个人数据处理

评论描述购物体验而非个人，但自由文本可能夹带联系方式，`title`/`text`
与 Safety Gate 同口径清洗：

| 类型 | 替换为 | 本试点 |
|---|---|---|
| 邮箱 | `[email-removed]` | 清洗后残留 0 处 |
| 电话 | `[phone-removed]` | 共 13 行命中清洗标记 |

## 八、复现方式

```
# 首次抓取（探测 + 分片下载 + 建表一体）
.venv/Scripts/python.exe data/sources/_scripts/fetch_amazon_reviews.py

# 中断后重跑：已下载分片按字节数跳过、探测结论缓存复用，只补缺口
.venv/Scripts/python.exe data/sources/_scripts/fetch_amazon_reviews.py
```

无需新增 Python 依赖（纯标准库：urllib/json/csv/hashlib）。
扩展到其他品类分片：改脚本内 `REVIEW_SHARD` / `META_SHARD` 两个常量即可，
但先评估分片体积（tree API 清单有精确字节数）。

## 九、使用约束

- 本试点主表是**美国市场**一手评论；任何引用须注明「Amazon.com 美国站样本，
  2023-09 截止」，不得表述为德国市场证据。
- `item_title`/`price_usd` 来自卖家自撰元数据，引用时只进企业假设栏。
- 每条评论的权威版本是 Amazon 页面，CSV 为衍生品；Apache-2.0 声明须保留。
- 全量库 5.71 亿条 ≈ 220GB，本机接入受镜像共享配额（10000 次/5 分钟）与
  CDN 抖动（一次 URLError 由续传恢复）约束，大批量取数须分品类分批进行。
