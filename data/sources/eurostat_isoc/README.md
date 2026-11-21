# Eurostat ISOC — 德国线上购买行为（L3 市场语境）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 提供方 | Eurostat（European Commission） |
| 接入方式 | REST / JSON-stat 2.0，`ec.europa.eu/eurostat/api/dissemination` |
| 凭据 | **无需注册、无需 key** |
| 许可 | Eurostat 开放数据政策，可商用，须署名 |
| 证据层级 | **L3** — 仅作市场语境基线，**不得单独支撑消费者偏好结论** |
| 抓取日期 | 2026-11-20 |

## 二、本目录内容

| 文件 | 说明 |
|---|---|
| `eurostat_isoc_de_2021_2026.csv` | 可追溯主表，13,093 行，长表格式 |
| `provenance.csv` | 每次 HTTP 调用的留痕：URL、状态码、字节数、耗时、SHA-256 |
| `manifest.json` | 机器可读元数据：时间窗、数据集元信息、行数 |
| `raw/isoc_ec_ib20_DE.json` | 原始 JSON-stat 响应，未经改动 |

## 三、数据范围

| 项 | 值 |
|---|---|
| 数据集 | `isoc_ec_ib20`（Internet purchases by individuals, 2020 onwards） |
| 地理 | `geo=DE`（德国） |
| 请求时间窗 | 2021-01-01 ~ 2026-12-31 |
| **实际可得年份** | **2021、2022、2023、2024、2025** |
| 源端更新时间 | 2026-04-17T11:00:00+0200 |
| 窗口内行数 | 13,093 |

**2026 年无数据**：Eurostat 的 ICT 家庭调查按年发布，2026 调查年数据在抓取日（2026-11-20）尚未发布。这不是抓取失败。

## 四、字段说明

| 列 | 含义 |
|---|---|
| `dataset` | 源数据集代码 |
| `year` | 调查年 |
| `geo` | 地理代码，固定 `DE` |
| `indicator_code` / `indicator_label` | 指标，如 `I_B3_12` = 最近一次线上购买在 3–12 个月前 |
| `unit` | 单位，如 `PC_IND` = 占全部个人百分比，`PC_IND_ILT12` = 占近 12 个月上网者百分比 |
| `ind_type_code` / `ind_type_label` | 人群细分，如 `CB_EU_FOR` = 出生于另一 EU 成员国的个人 |
| `value` | 观测值 |

## 五、已排除的数据集

| 数据集 | 排除原因 |
|---|---|
| `isoc_ec_ibuy` | 实为 **2002–2019** 历史数据集（源端 `updated=2024-06-16`，标题标注 2002-2019）。106,294 个观测**全部落在 2021-2026 窗口外**，故不纳入。已在抓取脚本中注释说明 |

## 六、复现方式

```
.venv/Scripts/python.exe data/sources/_scripts/fetch_eurostat.py
```

脚本幂等：重跑会覆盖 CSV 与 raw，并重新生成 provenance。时间窗定义在 `_scripts/common.py` 的 `WINDOW_START` / `WINDOW_END` 单点维护。

## 七、使用约束

- 本数据是**宏观统计**，描述"德国人线上购买的总体行为"，不描述任何具体商品的消费者偏好。
- 写入对照矩阵时只能进"市场语境"位，经 `services/datasets.py:assert_demand_side` 拦截，无法误写入消费者证据侧。
- 引用时须署名 Eurostat 并标注数据提取日期。
