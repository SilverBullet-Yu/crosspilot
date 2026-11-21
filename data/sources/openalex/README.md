# OpenAlex — 跨境消费者认知与 ABSA 学术证据（L3 方法论引用）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 提供方 | OpenAlex（OurResearch） |
| 接入方式 | REST GET，`api.openalex.org/works` |
| 凭据 | **无需 key**（免费 key 可将额度提升 10×，本次未使用） |
| 许可 | 开放数据，可商用 |
| 证据层级 | **L3** — 方法论与背景引用，**不得单独支撑消费者偏好结论** |
| 抓取日期 | 2026-11-20 |

## 二、本目录内容

| 文件 | 说明 |
|---|---|
| `openalex_works_2021_2026.csv` | 可追溯主表，2,455 条去重文献 |
| `provenance.csv` | 每次 HTTP 调用留痕（25 次：5 主题 × 5 页） |
| `manifest.json` | 机器可读元数据，含每主题命中总数与取回数 |
| `raw/{topic}_p1.json` | 每个主题第 1 页原始响应 |

## 三、检索范围

API 侧用 `filter=publication_year:2021-2026` 精确限定，不在本地事后过滤。

| 主题 key | 检索式 | 窗口内命中 | 取回 |
|---|---|---|---|
| `cross_cultural_consumer_perception` | cross-cultural consumer perception | 248,012 | 500 |
| `aspect_based_sentiment_analysis` | aspect-based sentiment analysis | 340,543 | 500 |
| `german_ecommerce_consumer_behaviour` | German e-commerce consumer behaviour | 28,413 | 496 |
| `cross_border_ecommerce_trust` | cross-border e-commerce consumer trust | 32,440 | 460 |
| `product_review_helpfulness` | online product review helpfulness | 374,707 | 499 |

**取回数远小于命中总数是刻意设计**：每主题取相关性最高的前 500 条（5 页 × 100），用途是方法论引用而非文献计量普查。不要把 CSV 行数当作领域规模。

## 四、年份分布（验证时间窗生效）

| 年 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 条数 | 372 | 385 | 420 | 441 | 458 | 379 |

六年全覆盖，无窗口外数据。开放获取 2,035 / 2,455。

## 五、字段说明

| 列 | 含义 |
|---|---|
| `topic_key` | 对应上表检索主题 |
| `openalex_id` | OpenAlex Work ID（如 `W2741809807`） |
| `doi` | DOI，可能为空 |
| `title` | 标题，截断至 240 字符 |
| `publication_year` / `publication_date` | 发表年 / 日期 |
| `type` | 文献类型（article、book-chapter 等） |
| `cited_by_count` | 被引数，CSV 内按主题分组降序排列 |
| `language` | 语言代码（en 2,435 条占绝对多数） |
| `first_author` | 第一作者 |
| `venue` | 发表载体 |
| `primary_topic` | OpenAlex 主题分类（非 Concepts，Concepts 已弃用） |
| `is_oa` | 是否开放获取 |

## 六、接口注意事项（已在脚本中处理）

| 事项 | 处置 |
|---|---|
| `mailto` 参数自 2026-02 起被忽略 | **不发送**。原 polite pool 已被 API key 取代 |
| `per_page` 上限 100 | 显式设为 100，并在脚本中断言返回数不超上限 |
| 基础分页上限 10,000 条 | 本次每主题仅取 500 条，未触及；如需更多须改用 cursor 分页 |
| 无 key 额度 | 实测可用，响应约 1.1s；大批量抓取建议申请免费 key |

## 七、复现方式

```
.venv/Scripts/python.exe data/sources/_scripts/fetch_openalex.py
```

## 八、使用约束

- 本数据是**学术文献元数据**，不含任何消费者原始发言，不构成 L1 证据。
- 可用于支撑"方法论选择"与"领域已有结论"的引用，不可用于论证"德国消费者偏好某个卖点"。
- `services/datasets.py:assert_demand_side("openalex")` 会拒绝其写入消费者证据侧。
