# MARC（Multilingual Amazon Reviews Corpus）德语商品评论基准（BENCHMARK，research-only）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 论文 | Keung, Lu, Szarvas, Smith: *The Multilingual Amazon Reviews Corpus*, EMNLP 2020（[arXiv:2010.02573](https://arxiv.org/abs/2010.02573)） |
| 官方分发入口 | [AWS Open Data Registry: amazon-reviews-ml](https://registry.opendata.aws/amazon-reviews-ml/)（无独立官方 GitHub 数据仓库） |
| HF 官方仓库 | `amazon/amazon_reviews_multi` —— **已因 Amazon 要求下架**（hf-mirror 实测 404 Repository not found，2026-11-21） |
| 实际数据来源 | hf-mirror.com 镜像的 [mteb/amazon_reviews_multi](https://hf-mirror.com/datasets/mteb/amazon_reviews_multi)（MTEB Classification 任务重构版）：`de/test.jsonl`（5,000 条）+ `de/validation.jsonl`（5,000 条） |
| 许可 | **Amazon 学术研究许可（research-only）**：限学术研究用途，禁转售、禁重发布、禁任何商业使用（含商业研究），禁与个人身份关联；违反即自动终止。**原文见 `raw/upstream_load_script.py` 的 `_LICENSE` 常量** |
| 证据层级 | **BENCHMARK**（`services/datasets.py` Tier.BENCHMARK）——**只作评测基准，不进证据卡，不写消费者证据侧** |
| 硬约束 2 | **商业化路径（¥99—199 定价）启动即下线**（docs/CONSTRAINTS.md；REGISTRY `marc` 条目 commercial_ok=False） |
| 入库日期 | 2026-11-21 |

> **公开仓库不含数据本体（2026-11-21 起）**：Amazon 学术研究许可明文**禁再发布**，
> 公开 Git 仓库构成再发布，故主表 CSV 已从仓库（含全部历史）移除；本目录保留
> README / manifest / provenance / baseline_eval.md（指标与少量 ≤110 字符错误
> 示例引用，属学术合理引用范畴）。本地数据凭 `data/sources/_scripts/fetch_marc.py`
> 复现（mteb 镜像路径，中断可续）。

## 二、下载源证据链（阶梯探测矩阵，2026-11-21 实测）

| 阶梯 | 途径 | 结果 |
|---|---|---|
| ① | hf-mirror `/api/datasets/mteb/amazon_reviews_multi/parquet` | **503 ×3**（持续；脚本加载型数据集本无 parquet 分片） |
| ① | hf-mirror `/api/datasets/mteb/amazon_reviews_multi`（基础 API） | **200**，仓库存在 |
| ① | hf-mirror `/api/.../tree/main/de` | **200**：test/validation/train 三分片 + 加载脚本 |
| ① | hf-mirror `/datasets/.../resolve/main/de/test.jsonl` 等 | **200**（首次探测时 503/502 交替，退避重试后成功；正式下载 validation 分片 503 ×2 后第 3 次 200） |
| ② | hf-mirror `SetFit/amazon_reviews_multi_de` | 200 存在；字段同为 id/label/label_text/text，但 **text 不含评论标题**（标题是立场强信号），弃用 |
| ② | hf-mirror `mrm8488/amazon_reviews_multi_de` | 404 不存在 |
| ③ | `raw.githubusercontent.com`（amazon-reviews-ml README / awslabs registry YAML） | **ERR**（连接级失败，2026-11-21 实测不可达） |
| ③ | `codeload.github.com/amazon-research/amazon-reviews-ml` | **404**（MARC 无独立官方 GitHub 数据仓库，与官方分发入口 AWS Open Data Registry 一致） |

**最终用的是阶梯①**：hf-mirror mteb 镜像。每个 HTTP 调用的 URL/状态码/字节数/耗时/SHA-256/UTC 时间见 `provenance.csv`。

### 为什么用 mteb 镜像而不是别的（取舍）

- 官方 HF 仓库下架后，mteb 版是可达镜像中**字段最完整**的（id/text/label/label_text；text 含评论标题+正文）。
- **代价（如实）**：官方 MARC 的 `product_category`（品类）、`product_id`、`reviewer_id`、独立 `review_title` 字段在 MTEB 重构版中丢失。任务背景里「含星级与品类」的预期只有星级可实现，品类不可得——记录于此，不做替代造数。
- `de/train.jsonl`（61.4MB LFS，201,197 条）**未下载**：规则立场基线零参数不训练，train 无评测用途；URL 与 LFS sha256 已从 API tree 锚定（`manifest.json` 的 `data_origin.train_anchor`），需要时可复现。总下载 ~3MB，远低于 200MB 纪律上限。

## 三、本目录内容

| 文件 | 说明 |
|---|---|
| `marc_reviews_de_10000.csv` | 可追溯主表，**10,000 条**德语商品评论（test 5,000 + validation 5,000）+ 星级 + 金标立场 |
| `provenance.csv` | 一行一次 HTTP 调用（4 次 hf-mirror 下载：URL/状态码/字节数/耗时/SHA-256/UTC，含 503 重试留痕） |
| `manifest.json` | 机器可读元数据；`corpus_type: benchmark`、`time_coverage_applicable: false` |
| `raw/de_test_5000.jsonl` | 上游 test 分片原件（1,534,471 字节，SHA-256 见 provenance） |
| `raw/de_validation_5000.jsonl` | 上游 validation 分片原件（1,528,225 字节） |
| `raw/upstream_load_script.py` | 上游 datasets 加载脚本原件：`_LICENSE`（Amazon 学术研究许可**原文**）、`_DESCRIPTION`（官方规模描述：每语言 train 200,000 / dev 5,000 / test 5,000；采集期 2015-11-01 至 2019-11-01） |
| `raw/hf_api_tree_de.json` | HF API tree 响应原件：`de/train.jsonl` 的 LFS sha256 锚定（train 未下载的证据） |

## 四、字段说明（主表）

| 列 | 含义 |
|---|---|
| `review_id` | 上游 id（如 `de_0784695`，数据原件原序，确定性行序） |
| `text` | 德语评论原文（标题+正文），已清洗 PII（邮箱→`[email-removed]`，电话→`[phone-removed]`）；raw/ 保留未清洗原件（不入库） |
| `stars` | 星级 1-5，由 `label + 1` 还原 |
| `label` | 上游原始标签 0-4（保留上游值便于追溯） |
| `gold_stance` | 金标立场，推导规则见下 |
| `split` | `test` / `validation`（官方 held-out 评测分片） |

### label → 星级映射（证据链）

1. 官方设计：每星级占 20% 均衡（`raw/upstream_load_script.py` 的 `_DESCRIPTION`）。
2. 实测：两分片 label 0-4 各恰好 1,000/5,000（20%），主表 stars 1-5 各 2,000/10,000。
3. 语义内证：label 0 文本为典型一星差评（如首条 `Leider nicht zu empfehlen`）。
4. MTEB Classification 任务口径：stars 1-5 编码为 0-4。
→ **label = stars − 1**。

### 金标立场推导规则（评测口径，唯一实现于 `fetch_marc.py:stars_to_gold_stance`）

星级是消费者对商品的**总体满意度一维信号**（MARC 无 aspect 标注），「推荐倾向」语义与 GERestaurant 金标的整体印象极性一致：

- **4-5 星 → support**：满意、正向推荐倾向；
- **1-2 星 → oppose**：不满意、负向不推荐；
- **3 星 → insufficient**：中评正负证据并存概率最高、方向不可判定，与 GERestaurant「混合评价/证据冲突 → insufficient」口径一致。

分布（每星均衡 20% 的直接推论）：**support 4,000 / oppose 4,000 / insufficient 2,000**。

## 五、时间覆盖校验为何不适用（如实声明，非绿灯造假）

本语料是**静态标注基准**：评论无逐条发布日期字段（官方仅描述采集期为 2015-11-01 至 2019-11-01，**全部早于本项目 2021-01-01 窗口**），不存在「发布节奏」，`validate_coverage.py` 的时间覆盖密度校验在语义上不适用。处理方式按 ADR-0003 的既定机制：本来源未列入其 `TABLES` 配置即为「不适用」的声明方式；manifest 另设 `corpus_type: benchmark` 与 `time_coverage_applicable: false` 显式说明。manifest 的 `window_start/window_end` 保留项目统一窗口口径（校验脚本强制），但**不代表**评论落于此窗口。

## 六、复现方式

```
# 首次抓取（仅访问 hf-mirror.com；4 次下载 + 建主表）
.venv/Scripts/python.exe data/sources/_scripts/fetch_marc.py

# 中断后续传：已落盘且非空的原件自动跳过，可反复运行至完整
# 重建主表：本地 raw 原件存在时，重跑本脚本即为离线重建，不发网络请求
```

校验：`bash scripts/check.sh`（含 validate_sources.py 结构校验）。

## 七、使用约束与已知局限

- **research-only，不进证据卡。** Amazon 学术研究许可禁任何商业使用；`assert_demand_side("marc")` 会拒绝（tier 非 L1）；本目录不产生任何消费者偏好证据。**硬约束 2：商业化路径启动即下线。**
- **金标立场是星级推导值**，不是数据集原生立场标注。3 星→insufficient 的「不可判定」是按映射口径判定，与真中性不完全等同。
- **品类字段缺失**（MTEB 重构版丢失），无法按商品品类做子集分析；「真实德国消费者商品评论」的域定位依据官方描述（de = amazon.de marketplace 检测为德语的评论）。
- 上游已匿名化 reviewer/product ID，主表 text 另做了邮箱/电话清洗；与 raw 原件可能有极少量字符差异（仅替换处）。
- train 分片未下载（201,197 条，61.4MB），见 `manifest.json` 的 `splits_skipped`。
- **已知局限对照**：GERestaurant（餐厅域）的评测结论「不可外推为商品域」正是本语料入库的动机——商品域泛化见 `baseline_eval.md`（规则立场基线在本语料上的表现与两域对照）。
