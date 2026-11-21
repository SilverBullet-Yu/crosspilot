# USAGE（Bielefeld）— 英德商品评论立场标注基准（BENCHMARK，span 级标注语料）

## 一、来源与许可

| 项 | 值 |
|---|---|
| 论文 | Klinger, Cimiano: *The USAGE review corpus for fine-grained, multi-lingual opinion analysis*, LREC 2014（[会议 PDF](https://www.lrec-conf.org/proceedings/lrec2014/pdf/85_Paper.pdf)；预印本原件见 `raw/lrec2014_paper_preprint.pdf`） |
| 官方发布页 | [romanklinger.de/usagecorpus](https://www.romanklinger.de/usagecorpus/)（作者 Roman Klinger 维护；语料制作时属比勒费尔德大学，原始托管 toolkit.cit-ec.uni-bielefeld.de） |
| 入库版本 | **v1.0.2**（最新公开版，2015-07 更新 readme；页内另存 v1.0.0/1.0.1 与 IGGSA 共享任务测试集，均未另取） |
| 许可 | **ODC-By 1.0**（发布页原话："The data is available under the Open Data Commons Attribute License (ODB-By) v1.0."，页面快照见 `raw/usagecorpus_release_page.html`）。REGISTRY 登记保持 `community-free`/不可商用的**保守口径未放宽**——见下「版权限制」 |
| 证据层级 | **BENCHMARK**（`services/datasets.py` Tier.BENCHMARK）——只作评测基准，不进证据卡，不写消费者证据侧 |
| 入库日期 | 2026-11-21 |

### 版权限制（决定本来源形态，逐字引用）

> "For copyright reasons we cannot publish the Amazon reviews themselves. Therefore the tarball contains tools to receive the corpus from the original websites. Please do not redistribute these reviews. There is also a version available which includes text, but this cannot be made publicly available."

即：**公开语料不含评论原文**，只有标注（span 词面 + 字符偏移）与重新爬取原文的工具（包内 `crawler/`）。本项目不执行爬取（避免触碰 Amazon 条款），因此本基准只有标注层，没有文本层。

## 二、查证记录（2026-11-21，判据核对表）

登记判据（数据源清单）：622 英 + 611 德条、含 aspect 与主观短语人工标注、来自 Bielefeld。

| 判据 | 结果 | 证据 |
|---|---|---|
| 约 622 英 + 611 德条 | **精确命中**（622/622 + 611/611 唯一评论 ID，fetch 脚本断言） | 语料包 `files/*.txt` 清单 + manifest |
| aspect 与主观短语人工标注 | **命中**（a1: aspect 14,885 + subjective 10,407 span；另有主观短语极性、TARG-SUBJ 目标关系 8,566、COREF 共指 104） | 语料包 `files/*-a1.csv` / `*-a1.rel` |
| 来自 Bielefeld | **命中**（Klinger 时属比勒费尔德大学；原始托管 cit-ec.uni-bielefeld.de；论文为 LREC 2014） | 发布页 + 论文 |

搜索路径留痕：WebSearch「USAGE dataset stance aspect subjective phrases Bielefeld 622 English 611 German」→ IGGSA（Interest Group on German Sentiment Analysis）条目命名 "Bielefeld University Sentiment Analysis Corpus for German and English" → 定位作者发布页。IGGSA 另基于本语料发布过共享任务测试集（`iggsa-star-test-data.tar.gz`，101 条评论，101 条评论同格式）——**不在本次入库范围**（属另一分发件），仅在此留档线索。

## 三、本目录内容

| 文件 | 说明 |
|---|---|
| `usage_annotations_25292.csv` | **主表**：a1 标注 span 级明细，25,292 行（aspect 14,885 + subjective 10,407） |
| `usage_reviews_1233.csv` | 评论级汇总表：1,233 行（英 622 + 德 611），含金标立场推导列 |
| `provenance.csv` | 一行一次 HTTP 调用（4 次下载：URL/状态码/字节数/耗时/SHA-256/UTC） |
| `manifest.json` | 机器可读元数据；`corpus_type: benchmark` |
| `raw/USAGE-corpus-1.0.2.tar.gz` | 官方语料包原件（1,404,183 字节，gzip CRC 校验通过；含完整 a1+a2 双标注与 crawler） |
| `raw/usage-sentiment-lexicon-en.csv.gz` / `-de.csv.gz` | 作者同页分发的短语-极性词典（从本语料抽取，供不用全量标注的场景） |
| `raw/usagecorpus_release_page.html` | 发布页快照（许可声明与版权限制的原文出处） |
| `raw/corpus_readme.pdf` / `annotation_guidelines.pdf` / `lrec2014_paper_preprint.pdf` / `crawler_readme.txt` | 从语料包解包留档：官方 readme（v1.0.1 起含许可声明）、官方标注指引、LREC 论文预印本、原文爬取工具说明 |

发布页服务器实测限速（~15KB/s，语料包下载数分钟）；provenance 记录真实耗时。

## 四、字段说明

### 主表 `usage_annotations_25292.csv`（一行一条标注 span，标注者 a1）

| 列 | 含义 |
|---|---|
| `annotation_id` | 原件标注 ID（如 `2200-aspect0`），可回溯 raw 语料包与关系文件 |
| `review_id` | 语料内部评论 ID（跨语言不重复；文本需经作者渠道获取，见第一节） |
| `lang` / `category` | `en`/`de`；商品类目（coffeemachine/cutlery/microwave/toaster/trashcan/vacuum/washer/dishwasher，德语侧无 dishwasher） |
| `span_type` | `aspect` 或 `subjective` |
| `span_text` | 标注词面（短语原文，来自评论但仅为被标注的短语） |
| `char_start` / `char_end` | 评论原文中的字符偏移（已验证为字符语义：end-start 与词面字符长全量一致 47,354/47,354，含 a2；与 UTF-8 字节长不一致 4,114 处，排除字节偏移） |
| `polarity` | subjective 短语的极性：positive/negative/neutral/unknown；aspect 行恒为 `unknown` |
| `target_annotation_ids` / `target_span_texts` | TARG-SUBJ 关系：该主观短语指向的目标 aspect（多值 `\|` 分隔；503 条主观短语有多个目标） |
| `coref_annotation_ids` | COREF 共指：该 aspect 与其他 aspect 的共指对象（多为指代产品的代词 span；104 对，双向登记） |

### 汇总表 `usage_reviews_1233.csv`（一行一条评论）

| 列 | 含义 |
|---|---|
| `review_id` / `lang` / `category` | 同主表 |
| `asin` / `amazon_review_id` | Amazon 商品与评论 ID（原件字段，供按作者渠道重新获取原文后对齐） |
| `n_aspect` / `n_subjective` | a1 标注计数 |
| `subjective_polarities` | 该评论主观短语极性序列（`\|` 分隔，span 顺序） |
| `n_relations` | TARG-SUBJ 关系数 |
| `gold_stance` | **派生金标**，推导规则见下 |

### 金标立场推导规则（评测口径，唯一实现于 `fetch_usage_bielefeld.py:derive_gold_stance`）

USAGE **没有评论级立场标签**（原生标注止于短语级极性与目标关系），本列是派生口径，与 GERestaurant 的「集合唯一才映射」同型：

1. 取该评论全部 subjective 标注极性集合：恰为 {positive} → `support`；恰为 {negative} → `oppose`。
2. 正负混合 = 证据冲突 → `insufficient`；仅 neutral/unknown 或无标注 → `insufficient`。

分布：**support 538 / oppose 79 / insufficient 616**。insufficient 占 50.0%——USAGE 无 GERestaurant 的 GENERAL-IMPRESSION 总体标签，混合评价（"great machine, but delivery slow"）在短语极性聚合口径下必然冲突，这是**口径的结构性结果**，不是数据缺陷；与 GERestaurant（insufficient 8.0%）数字不可直接比较。

## 五、为何不做规则立场基线评测（如实声明）

`scripts/eval_stance_baseline.py` 的规则基线输入是**评论全文**（否定窗口、从句切分都依赖完整句子上下文），而 USAGE 公开版**没有评论原文**（第一节版权限制），主表只有孤立短语词面。在孤立短语上跑词典不构成立场评测（否定/转折上下文缺失，结果不可解释），故**不做 `--dataset usage` 评测扩展**，也不产 `baseline_eval.md`。本基准的用途是 span 级标注对照（aspect 术语、主观短语词面、目标关系结构），供未来有文本层的方案（如经作者渠道获取文本或 LLM 管线）使用。

## 六、时间覆盖校验为何不适用（如实声明，非绿灯造假）

本语料是**静态标注基准**：1,233 条评论无发布日期字段，不存在「发布节奏」，`validate_coverage.py` 的时间覆盖密度校验在语义上不适用。处理方式按 ADR-0003 既定机制：该脚本按 `TABLES` 配置逐源检查，本来源未列入 `TABLES` 即为「不适用」的声明方式；manifest 另设 `corpus_type: benchmark` 与 `time_coverage_applicable: false` 显式说明。manifest 的 `window_start/window_end` 保留项目统一窗口口径（校验脚本强制），但**不代表**评论落于此窗口——评论采集于 2014 年论文发表前，主表未做任何窗口过滤。

## 七、复现方式

```
# 首次抓取（仅访问 romanklinger.de；4 次下载 + 解包 + 建表；服务器限速需数分钟）
.venv/Scripts/python.exe data/sources/_scripts/fetch_usage_bielefeld.py

# 中断后续传：已落盘且非空的文件自动跳过，可反复运行至完整
# 重建主表：raw/USAGE-corpus-1.0.2.tar.gz 存在时，重跑本脚本即为离线重建（先跑规模断言），不发网络请求
```

校验：`bash scripts/check.sh`（含 validate_sources.py 结构校验）。fetch 脚本内置断言：622/611 评论数、25,292 标注数、8,566+104 关系数、关系引用无悬空、偏移与词面长度全量一致——不一致即拒绝建表。

## 八、使用约束与已知局限

- **无文本层。** 只有标注与短语词面；任何需要全文的用法（含规则立场基线）都不适用。获取原文的唯一合规路径是按包内 crawler 自行向 Amazon 请求（本项目**不执行**，触及平台条款）。
- **不进证据卡。** tier=BENCHMARK；本目录不产生任何消费者偏好证据。
- **金标立场是派生值**（第四节规则），insufficient 占 50.0% 为口径结构性结果。
- **主表只含标注者 a1**（IGGSA 共享任务金标同款口径）；a2 完整保留在 raw 语料包（22,062 标注 / 10,509 关系），未做标注者间一致性计算（超出本次范围，可作为后续工作）。
- **PII 处理与 GERestaurant 不同，如实记录**：语料无自由全文，主表只有 span 词面；email 扫描 0 命中；phone 正则在主表（a1）4 命中、a2 原件另 2 处，均为商品型号/厂商号码词面（如 `WMF 1280236040`、Wesco `175 831-03`）——属标注 span 原文，清洗会破坏基准完整性，判定非个人数据不清洗（manifest `pii_scan`）。
- **许可口径**：标注数据为 ODC-By 1.0（署名即可，引用上述论文）；REGISTRY 保持 `community-free`/`commercial_ok=False` 保守登记未放宽（含文本版不公开、勿再分发评论原文的作者声明是登记背景；是否放宽由管理者决定）。
- 偏移量为字符语义（已验证），但**无法在本机复核**其对原文本的指向（无文本层）。
- 相关资源（未入库）：IGGSA 共享任务测试集、机器翻译质量语料（发布页尾部链接）。
