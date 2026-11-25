# OpenAlex — 跨境消费者认知与 ABSA 学术证据（L3 方法论引用）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 提供方 | OpenAlex（OurResearch） |
| 接入方式 | REST GET，`api.openalex.org/works` |
| 凭据 | **无需 key**（免费 key 可将额度提升 10×，本次未使用） |
| 许可 | 开放数据，可商用 |
| 证据层级 | **L3** — 方法论与背景引用，**不得单独支撑消费者偏好结论** |
| 抓取日期 | 2026-11-24（重抓并补齐全部 25 页原始响应；首次抓取 2026-11-20） |

## 二、本目录内容

| 文件 | 说明 |
|---|---|
| `openalex_works_2021_2026.csv` | 可追溯主表，2,454 条去重文献 |
| `provenance.csv` | 每次 HTTP 调用留痕（25 次成功：5 主题 × 5 页；另含 2 次 504 重试记录） |
| `provenance_from_raw.csv` | 从 raw 重建时的文件哈希留痕，不覆盖在线留痕 |
| `manifest.json` | 机器可读元数据，含每主题命中总数、取回数与**落盘页数** |
| `raw/{topic}_p{1..5}.json` | **每主题每页**原始响应，共 25 个文件 |

**原始响应完整性（修复 D-04）**：早期脚本只在 `page == 1` 时落盘，25 次调用仅存 5 个 `p1`，主表 1,955 行无法离线重建。现已逐页落盘，`manifest.raw_complete=true`，并可用
`rebuild_from_raw.py` 在**无网络**下重建出与在线抓取**逐字节一致**的主表（已实测 `diff` 无差异）。

## 三、检索范围

API 侧用 `filter=publication_year:2021-2026` 精确限定，不在本地事后过滤。

| 主题 key | 检索式 | 窗口内命中 | 取回 | 落盘页 |
|---|---|---|---|---|
| `cross_cultural_consumer_perception` | cross-cultural consumer perception | 251,800 | 500 | 5 |
| `aspect_based_sentiment_analysis` | aspect-based sentiment analysis | 345,935 | 500 | 5 |
| `german_ecommerce_consumer_behaviour` | German e-commerce consumer behaviour | 28,818 | 496 | 5 |
| `cross_border_ecommerce_trust` | cross-border e-commerce consumer trust | 32,937 | 459 | 5 |
| `product_review_helpfulness` | online product review helpfulness | 379,122 | 499 | 5 |

**取回数远小于命中总数是刻意设计**：每主题取相关性最高的前 500 条（5 页 × 100），用途是方法论引用而非文献计量普查。不要把 CSV 行数当作领域规模。

命中总数随上游持续增长（2026-11-20 首抓时为 248,012 / 340,543 / 28,413 / 32,440 / 374,707），
按相关性排序的前 500 条亦随之微调，故总行数由 2,455 变为 2,454；重抓以**同一轮内自洽**为准，
不与历史行数强制对齐。

## 四、年份分布（验证时间窗生效）

| 年 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 条数 | 372 | 382 | 410 | 453 | 460 | 377 |

六年全覆盖，无窗口外数据。开放获取 2,032 / 2,454。

## 五、字段说明

| 列 | 含义 |
|---|---|
| `topic_key` | 对应上表检索主题 |
| `openalex_id` | OpenAlex Work ID（如 `W2741809807`），全表唯一 |
| `doi` | DOI，空值 123 行（5.0%） |
| `title` | 标题，截断至 240 字符 |
| `publication_year` / `publication_date` | 发表年 / 日期 |
| `type` | 文献类型（article、book-chapter 等） |
| `cited_by_count` | 被引数，CSV 内按主题分组降序排列 |
| `language` | 语言代码（en 2,434 条占绝对多数；空值 1 行） |
| `first_author` | 第一作者，空值 22 行 |
| `venue` | 发表载体，空值 41 行；截断至 120 字符 |
| `primary_topic` | OpenAlex 主题分类（非 Concepts，Concepts 已弃用） |
| `is_oa` | 是否开放获取 |

## 六、接口注意事项（已在脚本中处理）

| 事项 | 处置 |
|---|---|
| `mailto` 参数自 2026-02 起被忽略 | **不发送**。原 polite pool 已被 API key 取代 |
| `per_page` 上限 100 | 显式设为 100，并在脚本中断言返回数不超上限 |
| 基础分页上限 10,000 条 | 本次每主题仅取 500 条，未触及；如需更多须改用 cursor 分页 |
| 偶发 `HTTP 504` | 3 次重试 + 退避（2026-11-24 重抓命中 2 次，均在重试后成功，留痕保留） |
| 无 key 额度 | 实测可用，响应约 1.1s；大批量抓取建议申请免费 key |

## 七、复现方式

```
# 在线抓取（每主题每页均落盘 raw）
.venv/Scripts/python.exe data/sources/_scripts/fetch_openalex.py

# 从本地 raw 重建主表，不发任何网络请求（校验离线可复现性）
.venv/Scripts/python.exe data/sources/_scripts/rebuild_from_raw.py
```

## 八、使用约束

- 本数据是**学术文献元数据**，不含任何消费者原始发言，不构成 L1 证据。
- 可用于支撑"方法论选择"与"领域已有结论"的引用，不可用于论证"德国消费者偏好某个卖点"。
- `services/datasets.py:assert_demand_side("openalex")` 会拒绝其写入消费者证据侧。
