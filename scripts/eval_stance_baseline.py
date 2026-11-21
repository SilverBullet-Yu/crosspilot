"""在 GERestaurant / MARC 基准上评测立场分类器（scripts/eval_stance_baseline.py）。

数据集（--dataset，默认 gerestaurant）：
- gerestaurant：data/sources/gerestaurant/gerestaurant_reviews_3078.csv（3,078 条，
  PII 已清洗，餐厅域；金标由 fetch_gerestaurant.py:derive_gold_stance 推导）。
- marc：data/sources/marc/marc_reviews_de_10000.csv（10,000 条，PII 已清洗，
  商品域，官方 held-out test+validation 分片；金标为星级映射 stars 4-5 ->
  support、1-2 -> oppose、3 -> insufficient，映射理由见 data/sources/marc/README.md）。

分类器（--classifier，默认 rule）：
- rule：services/stance_baseline.py 透明规则基线，离线零网络，报告写
  baseline_eval.md（保持既有口径不变）。
- llm：services/stance_llm.py OpenAI 兼容端点（需 .env 配 LLM_API_BASE /
  LLM_API_KEY / LLM_MODEL 三项，缺一启动即报错退出，不消耗额度）；运行时故障
  逐条回退规则基线并统计回退率；结果带磁盘缓存（data/sources/_eval_cache/，
  sha256(文本) 为键，可中断续跑，两域共用），报告写 llm_baseline_eval.md，
  不做两域自动重跑（成本守卫；两域对照分别跑，缓存使第二次只需补新增判定）。

输出：accuracy / 各类与宏平均 precision-recall-F1 / 混淆矩阵 / 错误类型小结，
写入对应来源目录的报告并打印到 stdout。--classifier rule 且 --dataset marc 时
额外在离线主表上重跑 GERestaurant 评测，生成「餐厅域 vs 商品域」两域对照段，
回答「餐厅域结论是否外推到商品域（退化）」这一问题。

用法：
    .venv/Scripts/python.exe scripts/eval_stance_baseline.py
    .venv/Scripts/python.exe scripts/eval_stance_baseline.py --dataset marc
    .venv/Scripts/python.exe scripts/eval_stance_baseline.py --classifier llm --limit 200
    # 另支持 --emit-test-sample N SEED：按固定随机种子抽样，输出
    # apps/api/tests/test_stance_baseline.py 内嵌子集的字面量（随测试提交；
    # 该子集固定取自 GERestaurant 主表）

rule 模式只在已入库主表上离线运行，不发网络请求；llm 模式对每条文本发起一次
端点调用（受 --limit 与磁盘缓存约束）。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from crosspilot_api.config import settings
from crosspilot_api.domain.evidence import Stance
from crosspilot_api.services.stance_baseline import classify_stance
from crosspilot_api.services.stance_llm import classify_stance_with_fallback

# 两个基准的主表与报告输出位置（离线读取，均不含网络请求）
DATASETS: dict[str, dict[str, Path | str]] = {
    "gerestaurant": {
        "main_table": REPO_ROOT / "data" / "sources" / "gerestaurant"
        / "gerestaurant_reviews_3078.csv",
        "out_md": REPO_ROOT / "data" / "sources" / "gerestaurant" / "baseline_eval.md",
        "domain": "餐厅域",
        "gold_rule": "GENERAL-IMPRESSION 极性优先、冲突即 insufficient（见该目录 README）",
    },
    "marc": {
        "main_table": REPO_ROOT / "data" / "sources" / "marc"
        / "marc_reviews_de_10000.csv",
        "out_md": REPO_ROOT / "data" / "sources" / "marc" / "baseline_eval.md",
        "domain": "商品域",
        "gold_rule": "星级映射 4-5→support、1-2→oppose、3→insufficient"
        "（星级是总体满意度一维信号，中评方向不可判定；见该目录 README）",
    },
}
STANCES = ("support", "oppose", "insufficient")


def load_rows(main_table: Path) -> list[tuple[str, str]]:
    """读主表，返回 (text, gold_stance) 列表（保持主表确定性行序）。

    两个主表共享 text / gold_stance 列名约定（fetch 脚本落表时对齐）。
    """
    rows: list[tuple[str, str]] = []
    with main_table.open(encoding="utf-8-sig", newline="") as fh:
        for rec in csv.DictReader(fh):
            rows.append((str(rec.get("text") or ""), str(rec.get("gold_stance") or "")))
    return rows


def evaluate(
    rows: list[tuple[str, str]], classify: Callable[[str], Stance]
) -> dict[str, object]:
    """全量评测：逐条调用注入的分类器，计算 accuracy/precision/recall/F1 与混淆矩阵。

    classify 可注入规则基线（离线）或 LLM 适配器（带缓存与回退统计），
    指标计算与报告渲染对两种分类器完全同构。
    """
    confusion: dict[tuple[str, str], int] = Counter()
    gold_counts: Counter = Counter()
    pred_counts: Counter = Counter()
    true_pos: Counter = Counter()
    results: list[tuple[str, str, Stance]] = []
    for text, gold in rows:
        pred = classify(text).value
        confusion[(gold, pred)] += 1
        gold_counts[gold] += 1
        pred_counts[pred] += 1
        if pred == gold:
            true_pos[gold] += 1
        results.append((text, gold, Stance(pred)))

    per_class: dict[str, dict[str, float]] = {}
    f1_sum = 0.0
    for s in STANCES:
        tp = true_pos[s]
        prec = tp / pred_counts[s] if pred_counts[s] else 0.0
        rec = tp / gold_counts[s] if gold_counts[s] else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[s] = {"precision": prec, "recall": rec, "f1": f1,
                        "gold_n": gold_counts[s]}
        f1_sum += f1
    total = len(rows)
    accuracy = sum(true_pos.values()) / total if total else 0.0
    return {
        "total": total,
        "accuracy": accuracy,
        "macro_f1": f1_sum / len(STANCES),
        "per_class": per_class,
        "confusion": confusion,
        "results": results,
    }


def error_buckets(results: list[tuple[str, str, Stance]]) -> dict[str, list[str]]:
    """按错误类型归集示例（每类截取前 6 条，截断至 110 字符）。"""
    buckets: dict[str, list[str]] = {
        "gold_support_pred_oppose": [],
        "gold_oppose_pred_support": [],
        "gold_insufficient_pred_positive": [],
        "gold_positive_pred_insufficient": [],
    }
    for text, gold, stance in results:
        pred = stance.value
        snippet = text[:110].replace("\n", " ")
        if gold == "support" and pred == "oppose":
            buckets["gold_support_pred_oppose"].append(snippet)
        elif gold == "oppose" and pred == "support":
            buckets["gold_oppose_pred_support"].append(snippet)
        elif gold == "insufficient" and pred in ("support", "oppose"):
            buckets["gold_insufficient_pred_positive"].append(snippet)
        elif gold in ("support", "oppose") and pred == "insufficient":
            buckets["gold_positive_pred_insufficient"].append(snippet)
    return buckets


def emit_test_sample(size: int, seed: int) -> None:
    """按固定种子抽样并输出可粘贴进测试文件的字面量（子集随测试提交）。

    测试内嵌子集固定取自 GERestaurant 主表（基线的原始评测集）。
    """
    rows = load_rows(DATASETS["gerestaurant"]["main_table"])
    rng = random.Random(seed)
    sample = rng.sample(rows, size)
    payload = [{"text": t, "gold": g} for t, g in sample]
    print(f"# 固定评测子集（random.Random({seed}).sample，N={size}）")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def make_llm_classifier(
    model: str,
) -> tuple[Callable[[str], Stance], dict[str, int]]:
    """构造带磁盘缓存的 LLM 分类器（成本守卫，ADR-0004）。

    缓存以 sha256(文本) 为键，JSONL 追加式落盘于 data/sources/_eval_cache/
    （下划线目录，validate_sources 不视为来源），可中断续跑；两域评测共用同一
    缓存文件（键只含文本哈希），第二次跑另一域时已判定文本直接命中。运行时
    故障逐条回退规则基线并计入 stats["fallback"]，回退率随报告留痕。
    """
    cache_dir = REPO_ROOT / "data" / "sources" / "_eval_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_model = re.sub(r"[^A-Za-z0-9._-]", "-", model)
    cache_path = cache_dir / f"llm_stance_{safe_model}.jsonl"
    cache: dict[str, str] = {}
    if cache_path.exists():
        with cache_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    cache[str(rec["key"])] = str(rec["stance"])
    stats = {"hit": 0, "fresh": 0, "fallback": 0}

    def classify(text: str) -> Stance:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in cache:
            stats["hit"] += 1
            return Stance(cache[key])
        res = classify_stance_with_fallback(text)
        if res.fallback_used:
            stats["fallback"] += 1
        stats["fresh"] += 1
        cache[key] = res.stance.value
        with cache_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "key": key,
                        "stance": res.stance.value,
                        "reason": res.reason,
                        "model": res.model,
                        "fallback": res.fallback_used,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return res.stance

    return classify, stats


def write_llm_report(
    dataset: dict[str, Path | str],
    dataset_key: str,
    metrics: dict[str, object],
    buckets: dict[str, list[str]],
    model: str,
    stats: dict[str, int],
    n_evaluated: int,
) -> None:
    """LLM 分类器报告（写 llm_baseline_eval.md，不覆盖规则基线报告）。"""
    out_md = dataset["out_md"]
    assert isinstance(out_md, Path)
    out_md = out_md.parent / "llm_baseline_eval.md"
    judged = stats["hit"] + stats["fresh"]
    fallback_rate = stats["fallback"] / judged if judged else 0.0
    lines = [
        f"# {dataset['domain']} LLM 立场抽取评测结果",
        "",
        "- 评测日期：2026-11-21",
        f"- 分类器：`services/stance_llm.py`（OpenAI 兼容 chat/completions，"
        f"model=`{model}`，temperature=0，JSON 契约强制）",
        f"- 判定数：{n_evaluated}（缓存命中 {stats['hit']} / 新调用 {stats['fresh']}；"
        "缓存于 `data/sources/_eval_cache/`，可中断续跑）",
        (f"- 回退规则基线：{stats['fallback']} 条（{fallback_rate:.1%}）——网络/响应"
         "故障逐条回退并留痕，不编造立场"),
        f"- 金标口径：{dataset['gold_rule']}",
        ("- 对照靶：规则基线同域结果见同目录 `baseline_eval.md`（餐厅域 accuracy "
         "0.610 / 商品域 0.580）；**LLM 方案的启用前提（ADR-0004）：至少在 oppose "
         "recall 上超过规则基线**，未达标则继续用规则基线"),
        ("- 两域对照：需分别跑 `--dataset gerestaurant` 与 `--dataset marc`（缓存"
         "共用，第二次只补新增判定）；llm 模式不做两域自动重跑（成本守卫）"),
        "",
    ]
    lines += metrics_table_lines("## 指标", metrics)
    confusion: dict[tuple[str, str], int] = metrics["confusion"]  # type: ignore[assignment]
    lines += confusion_lines(confusion)
    lines += error_bucket_lines(buckets, domain=str(dataset["domain"]))
    lines += [
        "## 复现",
        "",
        "```",
        "# 先在 shell 导出 LLM_API_BASE / LLM_API_KEY / LLM_MODEL（.env 不会被脚本自动加载）",
        f".venv/Scripts/python.exe scripts/eval_stance_baseline.py --classifier llm --dataset {dataset_key}",
        "```",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[eval] 报告已写入 {out_md}")


def metrics_table_lines(header_note: str, metrics: dict[str, object]) -> list[str]:
    """指标表 + accuracy 的公共渲染。"""
    per_class: dict[str, dict[str, float]] = metrics["per_class"]  # type: ignore[assignment]
    lines = [
        header_note,
        "",
        "| 类别 | precision | recall | F1 | 金标数 |",
        "|---|---|---|---|---|",
    ]
    for s in STANCES:
        c = per_class[s]
        lines.append(
            f"| {s} | {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} "
            f"| {c['gold_n']} |")
    lines.append(
        f"| **宏平均** | — | — | **{metrics['macro_f1']:.3f}** | {metrics['total']} |")
    lines.append("")
    lines.append(f"**Accuracy：{metrics['accuracy']:.3f}"
                 f"（{round(metrics['accuracy'] * metrics['total'])}/{metrics['total']}）**")
    lines.append("")
    return lines


def confusion_lines(confusion: dict[tuple[str, str], int]) -> list[str]:
    """混淆矩阵（行=金标，列=预测）的公共渲染。

    列头顺序必须与 STANCES 一致（support/oppose/insufficient）。旧版列头
    （oppose/insufficient/support）与数据列序错位，2026-11-21 发现并修复。
    """
    lines = ["## 混淆矩阵（行=金标，列=预测）", ""]
    lines.append("| gold \\ pred | support | oppose | insufficient |")
    lines.append("|---|---|---|---|")
    for g in STANCES:
        cells = [confusion.get((g, p), 0) for p in STANCES]
        lines.append(f"| {g} | " + " | ".join(str(c) for c in cells) + " |")
    lines.append("")
    return lines


def error_bucket_lines(buckets: dict[str, list[str]], domain: str) -> list[str]:
    """错误类型小结（数字驱动句式 + 每类前 6 条示例）。

    主因文案按域定制：错误形态与金标构成方式有关——餐厅域的 insufficient
    多为「混合评价」，商品域（MARC）的 insufficient 多为 3 星中评（文本常
    仍是温和负面抱怨）；商品域常见缺陷词（undicht/klemmt/beschädigt 等）
    不在餐厅域词表中。
    """
    n_ins_pos = len(buckets["gold_insufficient_pred_positive"])
    n_pos_ins = len(buckets["gold_positive_pred_insufficient"])
    n_s_o = len(buckets["gold_support_pred_oppose"])
    n_o_s = len(buckets["gold_oppose_pred_support"])
    if domain == "商品域":
        causes = [
            (f"- 金标 insufficient（3 星中评）被判 support/oppose：{n_ins_pos} 条。"
             "主因：中评文本常仍是温和负面抱怨（用户用 3 星表达不满），且常见"
             "\"功能可用但不满意\"的混合表达；正面词多于负面词时被强判 support，"
             "反之判 oppose——按口径不可判定，但基线倾向强行表态。"),
            (f"- 金标 support/oppose 被判 insufficient：{n_pos_ins} 条。主因：商品"
             "评论偏短、不含任何词典词（商品域典型缺陷词 undicht/klemmt/zu klein/"
             "beschädigt/Reinfall/Fake 等不在餐厅域词表中），或正负各一命中相抵。"),
            (f"- support/oppose 互混：{n_s_o + n_o_s} 条（support→oppose {n_s_o}，"
             f"oppose→support {n_o_s}）。主因：否定窗口误翻转、个别词的领域歧义"
             "（同一形容词在商品域可正可负），以及短评里单一信号被放大。"),
        ]
    else:
        causes = [
            (f"- 金标 insufficient 被判 support/oppose：{n_ins_pos} 条。主因：混合评价里"
             "正面词多于负面词（词典覆盖不均）、元否定（\"kann ich nicht bestätigen\"）"
             "不处理，基线倾向强行表态。这是 insufficient 类召回低的结构性原因。"),
            (f"- 金标 support/oppose 被判 insufficient：{n_pos_ins} 条。主因：评论不含任何"
             "词典词（如 \"Wir werden dieses Restaurant sicher nicht noch einmal "
             "besuchen\"），或正负各一命中相抵。"),
            (f"- support/oppose 互混：{n_s_o + n_o_s} 条（support→oppose {n_s_o}，"
             f"oppose→support {n_o_s}）。主因：否定窗口误翻转与个别词的领域歧义。"),
        ]
    lines = ["## 错误类型小结", "", *causes]
    for key, title in (
        ("gold_support_pred_oppose", "support→oppose 示例"),
        ("gold_oppose_pred_support", "oppose→support 示例"),
        ("gold_insufficient_pred_positive", "insufficient→表态 示例"),
        ("gold_positive_pred_insufficient", "表态→insufficient 示例"),
    ):
        lines.append("")
        lines.append(f"### {title}")
        lines.append("")
        for snippet in buckets[key][:6]:
            lines.append(f"> {snippet}")
        if not buckets[key]:
            lines.append("（无）")
    lines.append("")
    return lines


def write_gerestaurant_report(dataset: dict[str, Path | str], metrics: dict[str, object],
                              buckets: dict[str, list[str]]) -> None:
    """GERestaurant 报告（原版结构，--dataset gerestaurant 或默认）。"""
    out_md = dataset["out_md"]
    assert isinstance(out_md, Path)
    lines = [
        "# GERestaurant 规则立场基线评测结果",
        "",
        "- 评测日期：2026-11-21",
        (f"- 语料：`data/sources/gerestaurant/gerestaurant_reviews_3078.csv`"
         f"（{metrics['total']} 条，PII 已清洗，餐厅域）"),
        ("- 基线：`apps/api/src/crosspilot_api/services/stance_baseline.py`"
         "（透明规则：德语极性词典 + 否定窗口翻转 + 从句切分；零 ML 依赖）"),
        "- 金标口径：GENERAL-IMPRESSION 极性优先、冲突即 insufficient（见该目录 README）",
        ("- 结论定位：给后续 LLM 立场抽取方案提供对照基准；餐厅域结论不可外推为商品域"
         "——商品域表现见 `data/sources/marc/baseline_eval.md`（--dataset marc）"),
        "",
    ]
    lines += metrics_table_lines("## 指标", metrics)
    confusion: dict[tuple[str, str], int] = metrics["confusion"]  # type: ignore[assignment]
    lines += confusion_lines(confusion)
    lines += error_bucket_lines(buckets, domain="餐厅域")
    lines += [
        "## 复现",
        "",
        "```",
        ".venv/Scripts/python.exe scripts/eval_stance_baseline.py",
        "```",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[eval] 报告已写入 {out_md}")


def cross_domain_lines(ger: dict[str, object], marc: dict[str, object]) -> list[str]:
    """「餐厅域 vs 商品域」两域对照段（数字驱动，退化就写退化）。"""
    ger_cls: dict[str, dict[str, float]] = ger["per_class"]  # type: ignore[assignment]
    marc_cls: dict[str, dict[str, float]] = marc["per_class"]  # type: ignore[assignment]
    lines = [
        "## 与 GERestaurant（餐厅域）对照",
        "",
        ("- 对照口径：GERestaurant 3,078 条（同一基线、同一 STANCES 三类口径，"
         "离线重跑主表得出，与 data/sources/gerestaurant/baseline_eval.md 同源）"),
        ("- 规则基线的词典是**手写餐厅/服务/价格域**德语词表（见 stance_baseline.py "
         "模块 docstring），本对照回答「餐厅域 → 商品域是否退化」"),
        "",
        "### 两域指标对照表",
        "",
        "| 指标 | GERestaurant（餐厅域） | MARC de（商品域） | 差值（商品-餐厅） |",
        "|---|---|---|---|",
    ]
    acc_delta = marc["accuracy"] - ger["accuracy"]
    macro_delta = marc["macro_f1"] - ger["macro_f1"]
    lines.append(
        f"| accuracy | {ger['accuracy']:.3f} | {marc['accuracy']:.3f} "
        f"| {acc_delta:+.3f} |")
    lines.append(
        f"| 宏 F1 | {ger['macro_f1']:.3f} | {marc['macro_f1']:.3f} "
        f"| {macro_delta:+.3f} |")
    for s in STANCES:
        lines.append(
            f"| {s} F1 | {ger_cls[s]['f1']:.3f} | {marc_cls[s]['f1']:.3f} "
            f"| {marc_cls[s]['f1'] - ger_cls[s]['f1']:+.3f} |")
        lines.append(
            f"| {s} recall | {ger_cls[s]['recall']:.3f} | {marc_cls[s]['recall']:.3f} "
            f"| {marc_cls[s]['recall'] - ger_cls[s]['recall']:+.3f} |")
    lines.append("")
    lines.append("### 结论：餐厅域 → 商品域是否退化")
    lines.append("")
    degraded = marc["accuracy"] < ger["accuracy"] or marc["macro_f1"] < ger["macro_f1"]
    if degraded:
        lines.append(
            f"**是，出现退化。** accuracy {ger['accuracy']:.3f}→{marc['accuracy']:.3f}"
            f"（{acc_delta:+.3f}），宏 F1 {ger['macro_f1']:.3f}→{marc['macro_f1']:.3f}"
            f"（{macro_delta:+.3f}）。GERestaurant 评测报告中「餐厅域结论不可外推为"
            "商品域」的判断得到证实：基线词典以餐饮体验词为主（lecker/knusprig/"
            "gemütlich 等），商品评论的典型缺陷表达（材质/功能/物流类词）覆盖不足，"
            "泛化下降是词典域偏置的直接后果。")
    else:
        lines.append(
            f"**未出现整体退化**（accuracy {ger['accuracy']:.3f}→{marc['accuracy']:.3f}"
            f"（{acc_delta:+.3f}），宏 F1 {ger['macro_f1']:.3f}→{marc['macro_f1']:.3f}"
            f"（{macro_delta:+.3f}））。但逐类差异仍可能存在域偏置（见对照表），"
            "GERestaurant「餐厅域结论不可外推为商品域」的提醒依然成立——本次未退化"
            "可能是两域共用大量通用极性词的巧合，不构成可外推的证据。")
    lines.append("")
    return lines


def write_marc_report(dataset: dict[str, Path | str], metrics: dict[str, object],
                      buckets: dict[str, list[str]],
                      ger_metrics: dict[str, object]) -> None:
    """MARC 报告（含与 GERestaurant 的两域对照段）。"""
    out_md = dataset["out_md"]
    assert isinstance(out_md, Path)
    lines = [
        "# MARC 德语商品评论规则立场基线评测结果",
        "",
        "- 评测日期：2026-11-21",
        (f"- 语料：`data/sources/marc/marc_reviews_de_10000.csv`"
         f"（{metrics['total']:,} 条，PII 已清洗，商品域，官方 held-out "
         "test+validation 分片）"),
        ("- 基线：`apps/api/src/crosspilot_api/services/stance_baseline.py`"
         "（透明规则：德语极性词典 + 否定窗口翻转 + 从句切分；零 ML 依赖）"),
        ("- 金标口径：星级映射 4-5→support、1-2→oppose、3→insufficient"
         "（星级是消费者总体满意度的一维信号，无 aspect 标注；中评正负证据并存、"
         "方向不可判定，与 GERestaurant 混合评价→insufficient 口径一致；"
         "映射理由见该目录 README）"),
        ("- 结论定位：补 GERestaurant（餐厅域）缺失的商品域基准，回答「餐厅域结论"
         "是否外推到商品域」；research-only，不进证据卡（硬约束 2：商业化启动即下线）"),
        "",
    ]
    lines += metrics_table_lines("## 指标", metrics)
    confusion: dict[tuple[str, str], int] = metrics["confusion"]  # type: ignore[assignment]
    lines += confusion_lines(confusion)
    lines += error_bucket_lines(buckets, domain="商品域")
    lines += cross_domain_lines(ger_metrics, metrics)
    lines += [
        "## 复现",
        "",
        "```",
        ".venv/Scripts/python.exe scripts/eval_stance_baseline.py --dataset marc",
        "```",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[eval] 报告已写入 {out_md}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="立场分类器评测（GERestaurant / MARC）")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="gerestaurant",
                        help="评测哪个基准（默认 gerestaurant；marc 报告含两域对照）")
    parser.add_argument("--classifier", choices=("rule", "llm"), default="rule",
                        help="rule=透明规则基线（离线）；llm=OpenAI 兼容端点"
                        "（需 .env 三项配置，带磁盘缓存与回退统计，报告写"
                        " llm_baseline_eval.md）")
    parser.add_argument("--limit", type=int, default=0,
                        help="只评测主表前 N 条（确定性行序，成本守卫）；0=全量")
    parser.add_argument("--emit-test-sample", nargs=2, metavar=("N", "SEED"),
                        default=None,
                        help="按固定种子抽 N 条，输出测试内嵌子集字面量后退出"
                        "（固定取自 GERestaurant 主表）")
    args = parser.parse_args()
    if args.emit_test_sample:
        size, seed = int(args.emit_test_sample[0]), int(args.emit_test_sample[1])
        emit_test_sample(size, seed)
        return 0

    dataset = DATASETS[args.dataset]
    main_table = dataset["main_table"]
    assert isinstance(main_table, Path)
    rows = load_rows(main_table)
    if not rows:
        print(f"[eval] 主表为空或缺失：{main_table}；先跑对应 fetch_*.py")
        return 1
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    if args.classifier == "llm":
        if not (settings.llm_api_base and settings.llm_api_key and settings.llm_model):
            print("[eval] LLM 未配置：--classifier llm 需要先在 shell 导出 "
                  "LLM_API_BASE / LLM_API_KEY / LLM_MODEL 三项（缺一不启动，不消耗额度）")
            return 1
        model = settings.llm_model
        classify, llm_stats = make_llm_classifier(model)
        metrics = evaluate(rows, classify)
        buckets = error_buckets(metrics["results"])  # type: ignore[arg-type]
        write_llm_report(dataset, args.dataset, metrics, buckets, model,
                         llm_stats, len(rows))
    else:
        metrics = evaluate(rows, lambda text: classify_stance(text).stance)
        buckets = error_buckets(metrics["results"])  # type: ignore[arg-type]
        if args.dataset == "marc":
            # 两域对照：离线重跑 GERestaurant 主表（不发网络请求），保证对照数字
            # 与餐厅域主表同源，不依赖解析 markdown 报告
            ger_rows = load_rows(DATASETS["gerestaurant"]["main_table"])  # type: ignore[arg-type]
            ger_metrics = evaluate(ger_rows, lambda text: classify_stance(text).stance)
            write_marc_report(dataset, metrics, buckets, ger_metrics)
        else:
            write_gerestaurant_report(dataset, metrics, buckets)

    per_class: dict[str, dict[str, float]] = metrics["per_class"]  # type: ignore[assignment]
    print(f"[eval] dataset={args.dataset}  classifier={args.classifier}  N={metrics['total']}  "
          f"accuracy={metrics['accuracy']:.3f}  macro_f1={metrics['macro_f1']:.3f}")
    for s in STANCES:
        c = per_class[s]
        print(f"  {s:12s} P={c['precision']:.3f} R={c['recall']:.3f} F1={c['f1']:.3f} "
              f"(gold={c['gold_n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
