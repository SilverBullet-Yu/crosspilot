# EU Safety Gate (RAPEX) — 德国相关产品安全警报（L3 监管端信号）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 提供方 | European Commission，Safety Gate（原 RAPEX） |
| 接入方式 | 周报索引 XML → 逐期明细 XML，`ec.europa.eu/safety-gate-alerts/api` |
| 凭据 | **无需注册、无需 key** |
| 许可 | 周报 XML 分发在 data.europa.eu 标注 **CC0 1.0**（公共领域），须署名 © European Union |
| 证据层级 | **L3** — 监管判定，**不得单独支撑消费者偏好结论** |
| 抓取日期 | 2026-11-20 |

## 二、本目录内容

| 文件 | 说明 |
|---|---|
| `safety_gate_de_alerts_2021_2026.csv` | 可追溯主表，**3,255 条**德国相关警报 |
| `provenance.csv` | 按 raw 实际内容重建的留痕（303 个文件的 SHA-256） |
| `provenance_resume.csv` | 补抓 44 期的在线调用留痕（URL、状态码、耗时） |
| `manifest.json` | 机器可读元数据，`coverage_complete: true` |
| `raw/weekly_report_index.xml` | 周报索引原件 |
| `raw/report_*.xml` | 302 期明细原件，共约 46MB |

## 三、覆盖情况

| 项 | 值 |
|---|---|
| 窗口内周报期数 | **302 期**（2021-01-08 ~ 2026-11-20，每周五发布一期） |
| 已抓取 | **302 期，缺 0 期** |
| 德国相关警报 | 3,255 条 |

**年份分布**

| 年 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 条数 | 578 | 453 | 506 | 593 | 621 | 504 |

2026 年截至 11-20（Report-2026-46）。

## 四、德国关系三类

筛选逻辑：整条警报的 XML 中出现 `Germany` 即纳入，再按位置细分。

| `de_relation` | 含义 | 条数 |
|---|---|---|
| `notifying` | **德国监管机构发出的通报** | 2,806 |
| `origin` | 原产国为德国，由他国通报 | 446 |
| `mentioned` | 仅在措施或描述文本中提及德国 | 3 |

做"德国市场对中国商品的监管判定"分析时，应取 `notifying` 子集。

## 五、品类分布（前 8）

| 品类 | 条数 |
|---|---|
| Motor vehicles | 1,504 |
| Cosmetics | 423 |
| Toys | 271 |
| Jewellery | 230 |
| Protective equipment | 150 |
| Electrical appliances and equipment | 144 |
| Childcare articles and children's equipment | 94 |
| Machinery | 82 |

**旅行收纳包无独立品类**。近邻品类（以主表 category 列原文为准：Toys 271 / Childcare articles and children's equipment 94 / Chemical products 66 / Clothing, textiles and fashion items 57 / Hobby/sports equipment 31）合计 **519 条**，是本场景的可用子集。检索服务与测试以 519 为准（`apps/api/.../safety_gate_retrieval.py:EXPECTED_NEAR_NEIGHBOR_COUNT`）。注意 Motor vehicles 占近半（1,504 / 3,255 ≈ 46%），做品类分析前必须先过滤，否则结论被汽车召回主导。
（2026-11-21 修正：本节此前版本数字与主表不符——前8表基于早期统计，且近邻子集漏计 Hobby/sports equipment 31 条，写为 488；现按主表实测更正。）

## 六、字段说明

| 列 | 含义 |
|---|---|
| `case_number` | 警报编号，如 `SR/03270/26`，**主表已按此去重** |
| `report_reference` / `publication_date` | 所属周报与发布日 |
| `category` | 产品品类 |
| `product` / `product_name` / `brand` | 产品类型 / 名称 / 品牌（品牌常为空） |
| `barcode` | EAN/GTIN，可能多码连写 |
| `risk_type` | 风险类型，如 `Choking`、`Chemical`、`Burns, Fire` |
| `risk_level` | 风险等级，如 `Serious risk` |
| `danger` | 危害描述，**截断至 600 字符**，已清洗 PII |
| `measures` | 采取的措施，**截断至 400 字符**，已清洗 PII |
| `notifying_country` / `country_of_origin` | 通报国 / 原产国 |
| `de_relation` | 德国关系分类，见上表 |

## 七、接口注意事项（实测，已在脚本处理）

| 事项 | 处置 |
|---|---|
| 明细 URL 直接拼 `/detail/xml/{id}?language=en` 返回 **400** | 必须带索引给出的 `search=WEB_REPORT%7C:%7C{id}` 参数 |
| 索引中的链接是 HTML 转义的（`&amp;`）且尾部带逗号 | 取用前 `html.unescape()` 并 `rstrip(",")` |
| 明细元素名是 `<notifications>`（**复数**） | 早期版本按单数匹配导致 0 条，已修正 |
| 偶发 `URLError` | 3 次重试 + 退避；44 期中断后由 `resume_safety_gate.py` 补齐，成功率 44/44 |

## 八、个人数据处理

警报描述产品而非个人，但自由文本可能夹带联系方式。`danger` 与 `measures` 已做清洗：

| 类型 | 替换为 | 校验结果 |
|---|---|---|
| 邮箱 | `[email-removed]` | 残留 0 处 |
| 电话 | `[phone-removed]` | — |

全表共 34 处替换。

## 九、复现方式

```
# 首次抓取
.venv/Scripts/python.exe data/sources/_scripts/fetch_safety_gate.py

# 中断后补齐缺失期次（可反复运行）
.venv/Scripts/python.exe data/sources/_scripts/resume_safety_gate.py

# 从本地 raw 重建主表，不发网络请求
.venv/Scripts/python.exe data/sources/_scripts/rebuild_from_raw.py
```

## 十、使用约束

- 本数据是**监管机构的缺陷判定**，不是消费者偏好表达。可用于论证"某品类在德国存在哪些合规风险"，**不可**用于论证"德国消费者喜欢什么"。
- `services/datasets.py:assert_demand_side("eu_safety_gate")` 会拒绝其写入消费者证据侧。
- 每条警报的权威版本是 Safety Gate 门户页面，CSV 为衍生品。
- 署名要求：© European Union，并注明数据提取日期。
