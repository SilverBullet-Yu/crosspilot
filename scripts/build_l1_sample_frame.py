"""L1 分层采样清单生成器（ADR-0005 A5）：美国市场 L1 试点 → n=30 分层样本。

用途：服务「待办 #1 品牌方德国 L1 导出」到来之前，把分层采样纪律落在
已有真实数据上——采样框（层级 × 配额）与逐条样本（含溯源列）写入
data/sources/amazon_reviews_2023/l1_sample_frame.md，样本批次本身可走
ADR-0005 判定链（去重 → 抽取 → 门禁 → 区间）。

分层设计（星级 × 时间，两层交叉）：
- 星级层：1-2 星（负）/ 3 星（中性）/ 4-5 星（正），配额 10/5/15
  （负向配额不低于 1/3——立场判定需要 oppose 侧有足够样本）；
- 时间层：2021 / 2022 / 2023-08 前三段均分（该试点数据止于 2023-08）。
层内按 review_date 系统抽样（等距起点=各层内位次均值，可复现无种子波动）。

硬约束边界（如实入清单）：该数据为 Amazon.com 美国市场（manifest tier_caveat），
仅作 L1 试点与方法演练，不得写入德国市场偏好结论（ADR-0005 实数据跑通纪律）。

用法：.venv/Scripts/python.exe scripts/build_l1_sample_frame.py [--n 30]
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TABLE = REPO_ROOT / "data" / "sources" / "amazon_reviews_2023" / "amazon_reviews_2023_pilot_2021_2026.csv"
OUT = REPO_ROOT / "data" / "sources" / "amazon_reviews_2023" / "l1_sample_frame.md"

#: 星级分层：层名 → (谓词, 配额占比)
RATING_STRATA: tuple[tuple[str, object], ...] = (
    ("neg(1-2星)", lambda r: float(r) <= 2.0),
    ("neu(3星)", lambda r: float(r) == 3.0),
    ("pos(4-5星)", lambda r: float(r) >= 4.0),
)
#: 负向层配额下限（占比）：立场判定需要 oppose 侧样本充足
NEG_QUOTA_SHARE = 1 / 3
#: 时间层（该试点止于 2023-08）
TIME_STRATA = ("2021", "2022", "2023H1")


def _time_layer(review_date: str) -> str:
    year = review_date[:4]
    if year in {"2021", "2022"}:
        return year
    return "2023H1"


def _quota(n: int) -> dict[str, int]:
    """星级配额：负向不低于 1/3，其余按中性 1/6、正向余量分配。"""
    neg = max(1, round(n * NEG_QUOTA_SHARE))
    neu = max(1, round(n / 6))
    pos = max(0, n - neg - neu)
    return {"neg(1-2星)": neg, "neu(3星)": neu, "pos(4-5星)": pos}


def build_frame(n: int) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    """读主表 → 分层 → 层内系统抽样。返回 (样本行, 每层池大小)。"""
    pool: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with TABLE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rating = row.get("rating") or ""
            if not rating:
                continue
            layer_name = next(
                (name for name, pred in RATING_STRATA if pred(rating)), None  # type: ignore[operator]
            )
            if layer_name is None:
                continue
            pool[(layer_name, _time_layer(row.get("review_date") or ""))].append(row)

    quotas = _quota(n)
    samples: list[dict[str, str]] = []
    strata_sizes: dict[str, dict[str, int]] = defaultdict(dict)
    for rating_layer, _ in RATING_STRATA:
        if rating_layer == "pos(4-5星)":
            # 末层用剩余配额（floor 分摊），避免 ceil 累积超采：n=30 → neg 4×3 + neu 2×3 + pos 4×3 = 30
            remaining = max(0, n - len(samples))
            cell_quota = remaining // len(TIME_STRATA)
        else:
            # 非末层按层配额向上分摊（ceil），保证负向层配额足额
            cell_quota = -(-quotas[rating_layer] // len(TIME_STRATA))
        for time_layer in TIME_STRATA:
            cell = pool.get((rating_layer, time_layer)) or []
            strata_sizes[rating_layer][time_layer] = len(cell)
            if not cell:
                continue
            # 系统抽样：等距取点、窗口居中（确定性、无种子、无波动）
            cell_sorted = sorted(cell, key=lambda r: (r.get("review_date") or "", r.get("asin") or ""))
            take = min(cell_quota, len(cell_sorted))
            step = max(1, len(cell_sorted) // take)
            start = max(0, (len(cell_sorted) - take * step) // 2)
            for i in range(take):
                samples.append(cell_sorted[start + i * step])

    # 时间列排序输出（清单可读）
    samples.sort(key=lambda r: (r.get("review_date") or "", r.get("rating") or ""))
    return samples, dict(strata_sizes)


def render(samples: list[dict[str, str]], strata_sizes: dict[str, dict[str, int]], n: int) -> str:
    lines: list[str] = []
    lines.append("# L1 分层采样清单（ADR-0005 A5 · 美国市场试点）")
    lines.append("")
    lines.append(f"> 生成：scripts/build_l1_sample_frame.py --n {n} ｜ 采样框：星级×时间分层，")
    lines.append(f"> 星级配额 neg/neu/pos = {tuple(q for q in _quota(n).values())}（负向 ≥{NEG_QUOTA_SHARE:.0%}），")
    lines.append(f"> 时间层 {'/'.join(TIME_STRATA)}（试点数据止于 2023-08），层内系统抽样（确定性、无种子）。")
    lines.append("")
    lines.append(
        "**硬约束边界（manifest tier_caveat 同源）**：本清单来自 Amazon.com 美国市场，"
        "仅作 L1 判定链方法演练（去重→抽取→门禁→区间），**不得写入德国市场偏好结论**。"
    )
    lines.append("")
    lines.append("## 采样框（层级池大小 → 实采）")
    lines.append("")
    lines.append("| 星级层 | " + " | ".join(TIME_STRATA) + " | 层合计 |")
    lines.append("|---|" + "---|" * (len(TIME_STRATA) + 1))
    picked_by_layer: dict[str, int] = defaultdict(int)
    for row in samples:
        rating = float(row["rating"])
        layer = next(name for name, pred in RATING_STRATA if pred(rating))  # type: ignore[operator]
        picked_by_layer[layer] += 1
    for name, _ in RATING_STRATA:
        cells = [str(strata_sizes.get(name, {}).get(t, 0)) for t in TIME_STRATA]
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {picked_by_layer.get(name, 0)} 实采 |")
    lines.append("")
    lines.append("## 样本清单（逐条可溯源：shard/asin/日期/星级）")
    lines.append("")
    lines.append("| # | review_date | rating | asin | shard | verified | 摘要（前 80 字符） |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, row in enumerate(samples, 1):
        text = (row.get("title") or "") + " " + (row.get("text") or "")
        summary = text.strip()[:80].replace("|", "\\|")
        lines.append(
            f"| {i} | {row.get('review_date')} | {row.get('rating')} | "
            f"{row.get('asin')} | {row.get('shard')} | {row.get('verified_purchase')} | {summary} |"
        )
    lines.append("")
    lines.append("## 下一步（判定链接线）")
    lines.append("")
    lines.append(
        "1. 抽取层：对 30 条摘要跑规则立场基线（eval_stance_baseline.py 口径）或凭据到位后的 LLM 档；"
        "2. 判定层：domain.decide 端到端（去重 → 计数 → 门禁 → Wilson 区间 → 四状态）；"
        "3. 溯源：每条样本含 shard/asin/review_date，逐条可回原始 CSV 验证。"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30, help="目标样本量（默认 30 = 判定门禁）")
    args = parser.parse_args()
    samples, strata_sizes = build_frame(args.n)
    OUT.write_text(render(samples, strata_sizes, args.n), encoding="utf-8", newline="\n")
    picked = {r["rating"] for r in samples}
    print(f"[OK] {OUT.name}: {len(samples)} 条样本（星级覆盖 {sorted(picked)}，目标 n={args.n}）")


if __name__ == "__main__":
    main()
