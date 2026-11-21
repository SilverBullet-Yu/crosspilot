"""校验主表的时间覆盖密度，识别"行数充足但时间覆盖极稀"的伪完整。

动因：GDELT 用 sort=datedesc + maxrecords=250 抓取时，250 条上限在高密度
查询下只够覆盖窗口末端几天。行数看着充足（1000 条），实际只覆盖 4.5% 的天数。
这类缺陷不会被"四件套齐全"的结构校验发现，必须独立检查。
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

SOURCES = Path(__file__).resolve().parents[1]

# (目录, 主表, 日期列, 解析方式)
TABLES = (
    ("eu_safety_gate", "safety_gate_de_alerts_2021_2026.csv", "publication_date", "dmy"),
    ("eurostat_isoc", "eurostat_isoc_de_2021_2026.csv", "year", "year"),
    # Comext 贸易数据：主表含年度(A)+月度(M)行，year 列由 period 拆出；
    # 年度粒度走 year 解析（覆盖年数/6），无需 PUBLISH_CADENCE_DAYS 折算。
    ("eu_comext", "eu_comext_ds045409_de_cn_hs4202_2021_2026.csv", "year", "year"),
    ("openalex", "openalex_works_2021_2026.csv", "publication_date", "iso"),
    ("gdelt", "gdelt_de_coverage_2021_2026.csv", "seen_date_utc", "gdelt"),
    ("amazon_reviews_2023", "amazon_reviews_2023_pilot_2021_2026.csv", "review_date", "iso"),
)
# 来源的固有发布节奏（天）。周更来源不可能有逐日数据，
# 密度须按"实际期数 / 应有期数"衡量，否则误判为稀疏。
PUBLISH_CADENCE_DAYS = {"eu_safety_gate": 7}
# 低于此覆盖率即判定为时间覆盖稀疏，必须在 manifest 标注
MIN_DENSITY = 0.5


def parse(value: str, kind: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        if kind == "dmy":
            return datetime.strptime(value, "%d/%m/%Y")
        if kind == "iso":
            return datetime.strptime(value[:10], "%Y-%m-%d")
        if kind == "gdelt":
            return datetime.strptime(value[:8], "%Y%m%d")
        if kind == "year":
            return datetime.strptime(f"{value}-07-01", "%Y-%m-%d")
    except ValueError:
        return None
    return None


def main() -> int:
    problems: list[str] = []
    for d, fn, col, kind in TABLES:
        path = SOURCES / d / fn
        if not path.exists():
            problems.append(f"{d}: 缺主表 {fn}")
            continue
        with path.open(encoding="utf-8-sig") as fh:
            dates = [parse(r.get(col, ""), kind) for r in csv.DictReader(fh)]
        got = sorted(x for x in dates if x)
        if not got:
            problems.append(f"{d}: 日期列 {col} 无可解析值")
            continue

        # 年粒度来源按"覆盖年数/窗口年数"；周更来源按"实际期数/应有期数"；
        # 其余按"有数据的不同日期数/跨度天数"
        if kind == "year":
            years = {x.year for x in got}
            density = len(years) / 6
            unit = f"{len(years)}/6 年"
        elif d in PUBLISH_CADENCE_DAYS:
            cadence = PUBLISH_CADENCE_DAYS[d]
            distinct_days = len({x.date() for x in got})
            span = (got[-1] - got[0]).days + 1
            expected = max(1, span // cadence)
            density = min(distinct_days / expected, 1.0)
            unit = f"{distinct_days} 期 / 应有约 {expected} 期（{cadence} 天节奏）"
        else:
            distinct_days = len({x.date() for x in got})
            span = (got[-1] - got[0]).days + 1
            density = distinct_days / span if span else 0.0
            unit = f"{distinct_days} 个日期 / 跨度 {span} 天"

        mf = SOURCES / d / "manifest.json"
        m = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {}
        declared = m.get("time_coverage_sparse")

        flag = density < MIN_DENSITY
        status = "SPARSE" if flag else "OK"
        print(f"[{status:>6s}] {d:16s} {len(got):6d} 行 | {unit} | 密度 {density:.1%}")

        if flag and declared is not True:
            problems.append(
                f"{d}: 时间覆盖密度 {density:.1%} 低于 {MIN_DENSITY:.0%}，"
                f"但 manifest 未声明 time_coverage_sparse=true"
            )
        if not flag and declared is True:
            problems.append(f"{d}: manifest 声明稀疏但实测密度 {density:.1%} 正常")

    if problems:
        print("\n问题：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\n时间覆盖校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
