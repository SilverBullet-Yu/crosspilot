# Eurostat Comext — 中国→德国 HS4202 旅行用品进口贸易（L3 市场语境）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 提供方 | Eurostat Comext 参考库（European Commission） |
| 数据集 | `DS-045409` — EU trade since 1988 by HS2-4-6 and CN8 |
| 接入方式 | Comext 专用 API（与主统计 API 不同基址）：`ec.europa.eu/eurostat/api/comext/dissemination`，JSON-stat 2.0 |
| 凭据 | **无需注册、无需 key** |
| 许可 | Eurostat 开放数据复用政策（免费复用，引用须署名 "Source: Eurostat"）；政策出处：ec.europa.eu/eurostat/web/quality-and-transparency/re-use-policy |
| 证据层级 | **L3** — 仅作市场语境基线，**不得单独支撑消费者偏好结论** |
| 抓取日期 | 2026-11-21 |

## 二、探测矩阵（2026-11-21 实测，全部留痕）

| # | 探测 | 路径 | 结果 |
|---|---|---|---|
| 1 | Comext 旧 UI | `ec.europa.eu/eurostat/comext/` | 200，但仅 89 字节 meta 跳转页——旧 UI 已下线，**不是取数入口** |
| 2 | 官方入门文档 | `ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started/comext-database` | 200/191KB/13.2s；确认专用基址 `api/comext/dissemination`，且**明示禁止整库下载，必须带过滤参数** |
| 3 | 数据集列表 | `api/comext/dissemination/sdmx/2.1/dataflow/ESTAT/all` | 200/23KB/2.2s，SDMX-ML，含 DS-045409 等 |
| 4 | JSON-stat 按过滤取数 | `api/comext/dissemination/statistics/1.0/data/DS-045409?freq=A&reporter=DE&partner=CN&product=420211&flow=1&time=2024` | **200/2KB/1.5-3s，路径打通** |
| 5 | 替代数据集 DS-059341（EU 及非 EU 国家 HS2-4-6） | 同过滤 | 200，指标为 VALUE_EUR/VALUE_NAC/QUANTITY_KG；与 DS-045409 同口径数值**完全一致**（4202 总目 2024=977,620,894 EUR / 92,101,845 kg 两库相符），本切片选 DS-045409（Comext 正典、含 SUPPLEMENTARY_QUANTITY 维度） |
| 6 | CN8 八位子目（JSON-stat） | product=42021100 | 200 但 product 维度 size=0——与无效码 99999999 表现相同（API 对无效/缺席码静默返回空，不报错） |
| 7 | CN8 八位子目（SDMX） | `api/comext/dissemination/sdmx/2.1/data/DS-045409/A.DE.CN.42021100.1.VALUE_IN_EUROS` | **400** `INVALID_QUERY_DIMENSION_VALUE: PRODUCT=42021100`——**CN8 细目经 API 不可得**，只能走 bulk 7z |
| 8 | 无 product 过滤（整库试探） | 仅 reporter/partner/flow/time | 响应 >910KB 仍流式传输至超时——整库下载被禁，逐产品过滤是唯一可行姿势 |
| 9 | 2026 年度可得性 | freq=A time=2026 | 200，product 维度存在但 **0 观测**（2026 年度未发布，非抓取失败） |
| 10 | 月度时间格式 | `time=2025M08` / `time=202508` → 400 Invalid value；`time=2025-08` | **200 有值**——月度时间格式为 ISO "YYYY-MM" |
| 11 | 多年区间语法 | `sinceTimePeriod=2021&untilTimePeriod=2026`（年度）、`sinceTimePeriod=2021-01&untilTimePeriod=2026-12`（月度） | 200，一次调用取回全区间 |
| 12 | bulk 目录列表 | `api/dissemination/files/?format=csv&dir=comext` | 200（注意必须 `files/` 带尾斜杠；不带尾斜杠 302 跳内网 IP 不可达）；`comext/COMEXT_DATA/PRODUCTS/` 下为按月分片 7z（full_partxixu_v2_YYYYMM.7z，单个约 2MB，TSV 全产品全伙伴全报告国） |
| 13 | bulk 取 CN8 的量级评估 | 指南 `comext/COMEXT_DATA/PRODUCTS/full202305.7z` | 单月全量文件大且含全部 HS 章；本切片按 200MB 量级纪律与年度聚合优先级，**不取 bulk，CN8 细目未纳入**并在 manifest 声明 |

## 三、本目录内容

| 文件 | 说明 |
|---|---|
| `eu_comext_ds045409_de_cn_hs4202_2021_2026.csv` | 可追溯主表，1,924 行，长表（年度 130 行 + 月度 1,794 行），UTF-8-BOM |
| `provenance.csv` | 一行一次 HTTP 调用：26 次，全部 200，总下载 **111KB**，含 SHA-256 与 UTC |
| `manifest.json` | 机器可读元数据：覆盖声明、截断声明、CN8 声明、逐产品观测数 |
| `raw/` | 26 个 JSON-stat 原始响应，未经改动（不入库，可凭 provenance 复现） |

## 四、数据范围与覆盖声明（如实）

| 项 | 值 |
|---|---|
| 口径 | reporter=DE（进口报告国=德国）→ partner=CN（中国，不含香港/澳门/台湾——Comext 有独立伙伴代码 HK/MO/TW） |
| 贸易流向 | flow=1 IMPORT（中国→德国进口） |
| 产品 | HS4 总目 4202 + 12 个 HS6 子目（API product 维度上限即 HS6） |
| 年度 | **2021、2022、2023、2024、2025 有值；2026 年度在抓取日尚未发布**（源端发布节奏，非抓取失败） |
| 月度 | **2021-01 ~ 2026-09 共 69 个月**（Comext 月度约滞后两个月）；**2026 为不完整年**，仅 9 个月 |
| 聚合/截断 | **无**：过滤查询返回该口径全量观测，无分页上限（manifest `truncation.truncated_windows=[]`） |

月度求和与年度值对账一致（420292 各年 sum(月度)=年度，逐位相符），可作为数据完整性旁证。

## 五、字段说明

| 列 | 含义 |
|---|---|
| `dataset` | 固定 `DS-045409` |
| `period_type` | `A` 年度 / `M` 月度 |
| `period` | 年度 `"2025"`；月度 `"2026-09"` |
| `year` / `month` | 拆分列，月度行的 `month` 为 1-12，年度行为空 |
| `reporter` / `partner` | `DE` / `CN` |
| `flow` / `flow_label` | `1` / `IMPORT` |
| `product` / `product_label_en` | HS 编码与 Comext 官方英文品名 |
| `indicator` | `VALUE_IN_EUROS`（价值，欧元）/ `QUANTITY_IN_100KG`（净质量，**单位 100kg**，即值×100=公斤） |
| `value` | 观测值 |

本切片 26 次调用中未出现 `SUPPLEMENTARY_QUANTITY`（件数等补充单位）：DE/CN 口径的 HS4202 全部以净质量计量，无逐品目补充单位——这是源端事实，已核对 raw。

**缺席≠零**：某月某子目无观测行表示源端无该观测（未申报或贸易量为零无法区分）；不能把"无行"当作"确认零贸易"用于结论。

## 六、HS 子目 → 中文品名对照（常用译名，便于中文检索；官方口径以 Comext 英文品名为准）

| HS6 | 中文（常用对照） | 与「旅行收纳包」的相关性 |
|---|---|---|
| 4202 | 衣箱、手提包及类似容器（HS4 总目） | 章级总量 |
| 420211 | 衣箱、旅行箱等——外表面皮革/再生皮革/漆皮 | 硬箱（皮革面） |
| 420212 | 衣箱、旅行箱等——外表面塑料薄膜/纺织材料 | 硬箱（主流材质） |
| 420219 | 衣箱、旅行箱等——其他材料 | 硬箱（其他） |
| 420221 | 手提包——外表面皮革/再生皮革/漆皮 | 手袋（对照品类） |
| 420222 | 手提包——外表面塑料薄膜/纺织材料 | 手袋（对照品类） |
| 420229 | 手提包——其他材料 | 手袋（对照品类） |
| 420231 | 钱包、名片盒等通常随身小件——外表面皮革 | 小件（对照品类） |
| 420232 | 同上——外表面塑料薄膜/纺织材料 | 小件（对照品类） |
| 420239 | 同上——其他材料 | 小件（对照品类） |
| 420291 | 旅行包、保温食品/饮料袋、化妆包、背包、购物袋、运动包等——外表面皮革 | 收纳包（皮革面） |
| 420292 | 同上——外表面塑料薄膜/纺织材料 | **旅行收纳包主要落点** |
| 420299 | 同上——其他材料 | 收纳包（其他材质） |

「旅行收纳包」本身无独立 HS 税号，散布于 420291/420292/420299 与部分 420212；做市场规模判断时以 420292 为主、420299/420291 佐证，避免把 4202 全章当作收纳包市场。

## 七、交叉校验

| 校验 | 结果 |
|---|---|
| DS-045409 vs DS-059341 同口径 | 4202 总目 2024 年 = 977,620,894 EUR / 92,101,845 kg，两数据集逐位一致 |
| 月度求和 vs 年度 | 420292 各年 sum(月度)=年度，逐位一致 |
| 校验时间 | 2026-11-21，抓取当日 |

## 八、复现方式

```
.venv/Scripts/python.exe data/sources/_scripts/fetch_eu_comext.py
```

- 幂等 + 中断恢复：raw/ 已存在且非空的响应直接跳过下载，重跑只补缺口并从 raw 重建主表（模式同 fetch_gerestaurant.py）；
- 26 次调用定义在脚本 `PRODUCTS` / `PERIOD_RANGE`，时间窗沿用 `_scripts/common.py` 的 `WINDOW_START` / `WINDOW_END`；
- 重跑成本：全量重抓约 70s / 111KB。

## 九、已知局限

1. **HS6 为 API 上限**：CN8 八位子目经 API 不可得（实测 400，见探测矩阵 #7），如需八位细目必须走 bulk 7z（未纳入，量级纪律）。
2. **2026 不完整**：年度未发布；月度仅到 2026-09（抓取日滞后约 2 个月）。任何"2026 全年"表述都禁止。
3. **香港/澳门/台湾不在 CN 内**：Comext 伙伴代码 HK/MO/TW 独立；本表 CN=中国大陆对德出口口径，与"中国全口径"表述有差异。
4. **月度是终值流**：Comext 会修订历史月度值；月度求和与年度在抓取日一致，但未来重跑可能因修订出现微差，以年度为准。
5. **L3 定位**：只能进对照矩阵"市场语境"位，经 `services/datasets.py:assert_demand_side` 拦截，不得支撑消费者偏好结论。引用须署名 "Source: Eurostat (Comext), DS-045409, 提取日期 2026-11-21"。
