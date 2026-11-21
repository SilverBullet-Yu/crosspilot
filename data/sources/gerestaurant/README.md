# GERestaurant — 德语餐厅评论 ABSA 基准（BENCHMARK，立场基线评测语料）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 论文 | Hellwig, Fehle, Bink, Wolff: *GERestaurant: A German Dataset of Annotated Restaurant Reviews for Aspect-Based Sentiment Analysis*, KONVENS 2024（[ACL Anthology 2024.konvens-main.14](https://aclanthology.org/2024.konvens-main.14/)） |
| 上游仓库 | [NilsHellwig/GERestaurant](https://github.com/NilsHellwig/GERestaurant)（代码、标注指引、结果；**不含标注数据**，见下） |
| 数据来源 | fork [kartik-gadhvi/GERestaurant](https://github.com/kartik-gadhvi/GERestaurant) 的 `data/dataset_filtered.json`（init 提交 2024-09-13，与论文发表同期） |
| 底层素材 | Google Maps 餐厅评论（Google Maps 用户评论内容本身按 CC BY 4.0 分发） |
| 许可 | **CC-BY-4.0**，可商用，**须署名**（引用上述论文并注明数据来源） |
| 证据层级 | **BENCHMARK**（`services/datasets.py` Tier.BENCHMARK）——**只作评测基准，不进证据卡，不写消费者证据侧** |
| 入库日期 | 2026-11-21 |

### 为什么数据取自 fork 而不是上游（证据链）

上游仓库是论文的官方实现，但 `baseline/load_dataset.py` 期望的 `data/train_dataset.json` / `data/test_dataset.json` **被其 `.gitignore` 明确排除**（原件见 `raw/upstream_gitignore.txt`）：作者经 HuggingFace 分发数据，而本机 HF 直连不可达（2026-11-20/21 两次实测 TCP 443 超时），hf-mirror 查询 `NilsHellwig/GERestaurant` 返回 Repository not found。上游 git 历史仅 1 个提交（Initial commit）、无 releases。

fork `kartik-gadhvi/GERestaurant` 的 init 提交（2024-09-13）恰好保留了作者分发时的 `data/dataset_filtered.json`——即 `data/do_split.ipynb` 划分 train/test 所用的输入原件（3,078 条，与论文摘要一致）。该 fork 无后续实质改动，原件完整性由 provenance.csv 的 SHA-256 锚定。**残留风险**：无法与作者原件逐字节比对（原件渠道在本机不可达），故此来源标注为「fork 快照」而非「上游原件」。

## 二、本目录内容

| 文件 | 说明 |
|---|---|
| `gerestaurant_reviews_3078.csv` | 可追溯主表，**3,078 条**德语评论 + aspect 标注 + 金标立场 |
| `provenance.csv` | 一行一次 HTTP 调用（2 次 codeload zip 下载：URL/状态码/字节数/耗时/SHA-256/UTC） |
| `manifest.json` | 机器可读元数据；`corpus_type: benchmark` |
| `raw/gerestaurant_upstream_main.zip` | 上游整库快照原件（1,050,337 字节） |
| `raw/gerestaurant_fork_main.zip` | 数据来源 fork 整库快照原件（1,310,948 字节） |
| `raw/dataset_filtered.json` | 从 fork zip 解包的数据原件（2,206,491 字节，zipfile 读出即经 CRC 校验） |
| `raw/upstream_README.md` / `raw/upstream_gitignore.txt` / `raw/annotation_guideline.pdf` | 上游 README、.gitignore（数据被排除的证据）、官方标注指引（1,017,910 字节） |

## 三、字段说明（主表）

| 列 | 含义 |
|---|---|
| `review_id` | 评论 UUID（数据原件原序，确定性行序） |
| `text` | 德语评论原文，已清洗 PII（邮箱→`[email-removed]`，电话→`[phone-removed]`）；raw/ 保留未清洗原件（不入库） |
| `aspect_labels` | `\|` 分隔的 aspect 类别：GENERAL-IMPRESSION / FOOD / SERVICE / AMBIENCE / PRICE |
| `aspect_polarities` | 与 labels 逐位对应的极性：POSITIVE / NEUTRAL / NEGATIVE |
| `n_aspects` | 标签条数（1~16） |
| `gold_stance` | 金标立场，推导规则见下 |

### 金标立场推导规则（评测口径，唯一实现于 `fetch_gerestaurant.py:derive_gold_stance`）

1. 含 GENERAL-IMPRESSION 标签：取其极性直接映射（POSITIVE→support，NEGATIVE→oppose，NEUTRAL→insufficient）；多条 GI 极性冲突按证据冲突处理为 insufficient。
2. 无 GI 但有其他 aspect：全部极性一致才映射该极性；混合极性（如「Essen lecker, jedoch überteuert」）= 证据冲突 → insufficient。
3. 无标签 → insufficient。

分布：**support 1,508 / oppose 1,323 / insufficient 247**（insufficient 占 8.0%，其中包含真中性「in Ordnung」与混合评价两类）。aspect 标注共 4,314 条：FOOD 1,712 / SERVICE 1,086 / GENERAL-IMPRESSION 776 / AMBIENCE 485 / PRICE 255。

## 四、时间覆盖校验为何不适用（如实声明，非绿灯造假）

本语料是**静态标注基准**：3,078 条评论无发布日期字段，不存在「发布节奏」，`validate_coverage.py` 的时间覆盖密度校验在语义上不适用。处理方式按 ADR-0003 的既定机制：该脚本按 `TABLES` 配置逐源检查，本来源未列入 `TABLES` 即为「不适用」的声明方式；manifest 另设 `corpus_type: benchmark` 与 `time_coverage_applicable: false` 显式说明，README（本文件）如实记录。manifest 的 `window_start/window_end` 保留项目统一窗口口径（校验脚本强制），但**不代表**评论落于此窗口——评论采集期为论文发表前（约 2023–2024），主表未做任何窗口过滤。

## 五、复现方式

```
# 首次抓取（仅访问 GitHub；两次 codeload zip 下载 + 解包 + 建主表）
.venv/Scripts/python.exe data/sources/_scripts/fetch_gerestaurant.py

# 中断后续传：已落盘且非空的 zip/原件自动跳过，可反复运行至完整
# 重建主表：本地 raw/dataset_filtered.json 存在时，重跑本脚本即为离线重建，不发网络请求
```

校验：`bash scripts/check.sh`（含 validate_sources.py 结构校验）。

## 六、使用约束与已知局限

- **餐厅域，不可外推为商品域。** 偏好结论（行李收纳/旅行用品）不得引用本语料；它只回答「规则基线在德语情感文本上的表现」这一评测问题。
- **不进证据卡。** `assert_demand_side("gerestaurant")` 会拒绝（tier 非 L1）；本目录不产生任何消费者偏好证据。
- **金标立场是推导值**，不是数据集原生字段；insufficient 类混合了「真中性」与「混合评价」，对基线是偏难的类。
- 主表 text 已清洗 PII，与 raw 原件可能有极少量字符差异（仅邮箱/电话替换处）。
- 许可 CC-BY-4.0 依 REGISTRY 既有登记与底层 Google Maps 评论内容条款；上游 GitHub 仓库**无 LICENSE 文件**，正式商用前建议向作者再确认一次。
- 度量：见 `baseline_eval.md`（规则立场基线在本语料上的 accuracy / 宏 F1 / 混淆明细）。
