# ADR-0003 数据区结构与中断恢复机制

状态：已接受 ｜ 日期：2026-11-21

## 背景

2026-11-20/21 接入外部数据时遇到四类问题，任一处理不当都会让数据不可信：

1. **抓取过程会中断。** Safety Gate 302 期抓到 258 期时进程被回收，主表未写出；若重跑整轮，已下载的 258 期会被重复请求。
2. **截断与完整返回外观一致。** GDELT 单查询上限 250 条、OpenAlex `per_page` 上限 100、HF `/rows` 上限 100，触顶时响应仍是 200 且结构正常，不记录就无从分辨。
3. **行数充足不等于时间覆盖充足。** GDELT 用 `sort=datedesc` + `maxrecords=250` 抓取，`en_luggage_de_src` 四窗共 1,000 条，实际只覆盖 33 天 / 730 天（4.5%）。结构校验看不出这类缺陷。
4. **来源可达性是环境相关的事实，不是文档属性。** Hugging Face 在本机 DNS 可解析但 TCP 443 全程超时；Destatis 匿名凭据被重定向到注册页。这些只能靠实测确定，且会变化。

## 决策

### 1. 数据区统一结构

所有外部数据落在 `data/sources/<source>/`，每个来源强制四件套：

| 文件 | 作用 |
|---|---|
| `README.md` | 来源、许可、层级、字段、使用约束、复现命令 |
| `<source>_<window>.csv` | 可追溯主表，UTF-8-BOM 长表 |
| `provenance.csv` | **一行一次 HTTP 调用**：URL、状态码、字节数、耗时、SHA-256、UTC 时间 |
| `manifest.json` | 机器可读元数据：时间窗、许可、层级、行数、截断与覆盖记录 |
| `raw/` | 原始响应，未经改动 |

时间窗（2021-01-01 ~ 2026-12-31）只在 `_scripts/common.py` 的 `WINDOW_START` / `WINDOW_END` 定义，不在各脚本散落硬编码。

### 2. 抓取与重建分离

| 脚本类型 | 职责 | 是否联网 |
|---|---|---|
| `fetch_*.py` | 抓取并落 `raw/`，同时产出主表 | 是 |
| `resume_*.py` | **只抓 `raw/` 中缺失的条目**，可反复运行至完整 | 是 |
| `rebuild_from_raw.py` | 从本地 `raw/` 重建主表与 manifest | **否** |

原始响应一旦落盘即不再重抓。中断后用 `resume` 补缺口、`rebuild` 出表。

### 3. 校验分两层，接入 `scripts/check.sh`

| 脚本 | 检查内容 |
|---|---|
| `validate_sources.py` | 四件套齐全、manifest 必填字段、时间窗一致、provenance 含 SHA-256；**`coverage_complete=false` 或存在截断窗口时，README 必须显式警示** |
| `validate_coverage.py` | 时间覆盖密度。低于 50% 且 manifest 未声明 `time_coverage_sparse=true` 即失败；反之声明了却不稀疏也失败 |

密度按来源**固有发布节奏**折算：年粒度按覆盖年数，周更来源按实际期数 / 应有期数，其余按不同日期数 / 跨度天数。不折算会把周更的 Safety Gate 误判为 14% 稀疏（实为 97.7%）。

### 4. 实测结论回填注册表

`services/datasets.py` 的 `REGISTRY` 是许可与可达性的唯一事实来源。每项的 `note` 记录实测日期与结论，`priority` 随实测调整（HF 与 Destatis 均由 P0 降 P1）。

### 5. raw 不入库

`.gitignore` 排除 `data/sources/*/raw/`（约 47MB）。主表、README、manifest、provenance 入库；raw 可凭 provenance 的 SHA-256 与 URL 复现。

## 后果

**正面**

- 中断可恢复：Safety Gate 补 44 期成功率 44/44，未重复下载任何已有期次。
- 截断与覆盖缺陷无法悄悄溜过：GDELT 的 15.1% 密度被 `check.sh` 挡住，必须在 manifest 显式声明才放行。
- 新增来源若漏 README、漏许可、漏截断说明，CI 直接红灯。

**代价**

- 每个来源的接入成本高于「写个脚本拉一下」：必须同时产出四件套并通过两层校验。
- `validate_coverage.py` 的节奏折算是按来源配置的（`PUBLISH_CADENCE_DAYS`），新增非日更来源需补配置，否则会误报稀疏。

## 备选方案与否决理由

| 方案 | 否决理由 |
|---|---|
| 数据直接落 `data/snapshots/` | 该目录按 ADR-0002 用于演示预跑快照，职责不同；混放会让 Demo 读到未经校验的中间数据 |
| 只保留主表，不留 raw | 解析逻辑改动后无法复核历史结果；Safety Gate 的 `notifications` 复数标签缺陷正是靠重解析 raw 发现并验证的 |
| 覆盖缺陷写在 README 即可 | 文档不会失败。GDELT 的时间覆盖缺陷在首轮就被写进 README，仍差点被当作可用数据；必须有脚本强制 manifest 与实测一致 |
