"""Eurostat Comext 中国→德国 HS4202 旅行用品贸易切片抓取（L3 市场语境）。

数据集：DS-045409（EU trade since 1988 by HS2-4-6 and CN8），Eurostat Comext
参考库的专用 API 端点（与主统计 API 不同基址）：
  https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409

取数路径实测（2026-11-21，详见 data/sources/eu_comext/README.md 探测矩阵）：
- JSON-stat 2.0，按 reporter/partner/product/flow/period 过滤，200 OK，无凭据；
- 官方文档明示该端点禁止整库下载（数据集过大），必须带过滤参数；
- product 维度只到 HS2/HS4/HS6，CN8 八位子目经 API 报
  INVALID_QUERY_DIMENSION_VALUE，细目只能走 bulk 7z（本切片不取）；
- 年度（freq=A）2021-2025 有值、2026 尚未发布；月度（freq=M，时间格式
  "2025-08"）持续到抓取日约两个月前，2026 为不完整年。

许可：Eurostat 开放数据复用政策，免注册，引用须署名 "Source: Eurostat"。

四件套与中断恢复（ADR-0003，模式同 fetch_gerestaurant.py）：
- raw/ 保留每次调用的 JSON-stat 原始响应，已存在且非空则跳过下载，
  可反复运行至完整，不重复请求；
- 主表每次从本地 raw 重建，不发网络请求；
- provenance.csv 按 URL 去重合并（保留最新一次调用），重跑不丢历史留痕。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    WINDOW_YEARS,
    Provenance,
    fetch,
    now_utc,
    save_raw,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "eu_comext"
RAW_DIR = OUT / "raw"
SOURCE = "eu_comext"
DATASET = "DS-045409"
DATASET_LABEL = "EU trade since 1988 by HS2-4-6 and CN8"
API_BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data"
LICENSE = "Eurostat open data"

REPORTER = "DE"  # 德国（含 1991 年起的原民主德国）
PARTNER = "CN"   # 中国（不含香港/澳门/台湾，Comext 有独立伙伴代码）
FLOW = "1"       # 1=IMPORT 进口
FREQS: tuple[str, ...] = ("A", "M")
#: 各频率的时间参数（由 common.WINDOW_YEARS 推导，窗口单点维护）：
#: 年度用四位年，月度用 ISO "YYYY-MM"
PERIOD_RANGE: dict[str, tuple[str, str]] = {
    "A": (WINDOW_YEARS[0], WINDOW_YEARS[-1]),
    "M": (f"{WINDOW_YEARS[0]}-01", f"{WINDOW_YEARS[-1]}-12"),
}
MAIN_TABLE = "eu_comext_ds045409_de_cn_hs4202_2021_2026.csv"

#: HS4202 全家族：HS4 总目 + 12 个 HS6 子目（API product 维度实测全部有效，
#: 2021-2025 年度均有观测）。旅行收纳包主要落在 420292。
PRODUCTS: tuple[str, ...] = (
    "4202",     # HS4 总目
    "420211", "420212", "420219",
    "420221", "420222", "420229",
    "420231", "420232", "420239",
    "420291", "420292", "420299",
)

CSV_HEADER = [
    "dataset", "period_type", "period", "year", "month",
    "reporter", "partner", "flow", "flow_label",
    "product", "product_label_en", "indicator", "value",
]


def build_url(freq: str, product: str) -> str:
    """构造一次过滤查询的完整 URL（一个产品 x 一个频率 = 一次调用）。"""
    since, until = PERIOD_RANGE[freq]
    return (
        f"{API_BASE}/{DATASET}?format=JSON&lang=EN"
        f"&freq={freq}&reporter={REPORTER}&partner={PARTNER}"
        f"&product={product}&flow={FLOW}"
        f"&sinceTimePeriod={since}&untilTimePeriod={until}"
    )


def raw_path(freq: str, product: str) -> Path:
    return RAW_DIR / f"{DATASET}_{freq}_{product}.json"


def download_all(prov: Provenance) -> list[str]:
    """逐产品逐频率抓取；已落盘的 raw 跳过（中断恢复）。返回缺失清单。"""
    missing: list[str] = []
    for freq in FREQS:
        for product in PRODUCTS:
            path = raw_path(freq, product)
            if path.exists() and path.stat().st_size > 0:
                print(f"[comext] 跳过已存在 {path.name}")
                continue
            url = build_url(freq, product)
            print(f"[comext] 抓取 {DATASET} freq={freq} product={product}")
            body = fetch(url, source=SOURCE, prov=prov, timeout=120,
                         note=f"{freq}_{product}")
            if body is None:
                missing.append(path.name)
                continue
            save_raw(OUT, path.name, body)
    return missing


def decode_category(dim: dict[str, Any]) -> dict[int, str]:
    """JSON-stat 维度的序号 -> 编码。"""
    cat = dim["category"]
    idx: dict[str, int] = cat["index"]
    return {v: k for k, v in idx.items()}


def flatten_doc(doc: dict[str, Any]) -> list[list[object]]:
    """JSON-stat 2.0 展平为长表行（CSV_HEADER 顺序，不含 dataset 列）。

    纬度顺序以文档 id 为准；flat 下标 = sum(dim_i 的序号 x 该维 stride)。
    """
    dims = doc["dimension"]
    order: list[str] = doc.get("id") or list(dims)
    sizes: list[int] = doc.get("size") or [
        len(dims[d]["category"]["index"]) for d in order
    ]
    codes = {d: decode_category(dims[d]) for d in order}
    labels = {d: dims[d]["category"].get("label", {}) for d in order}

    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    rows: list[list[object]] = []
    for flat_idx, value in doc.get("value", {}).items():
        n = int(flat_idx)
        coords = {
            d: codes[d][(n // stride) % len(codes[d])]
            for d, stride in zip(order, strides, strict=True)
        }
        freq = coords["freq"]
        period = coords["time"]
        year = int(period[:4])
        month = int(period[5:7]) if freq == "M" else ""
        product = coords["product"]
        rows.append([
            freq,                       # period_type
            period,                     # period
            year,                       # year
            month,                      # month
            coords["reporter"],
            coords["partner"],
            coords["flow"],
            labels["flow"].get(coords["flow"], coords["flow"]),
            product,
            labels["product"].get(product, product),
            coords["indicators"],
            value,
        ])
    return rows


def parse_raw_files() -> tuple[list[list[object]], dict[str, Any]]:
    """从本地 raw 重建主表行与覆盖元数据，不发网络请求。"""
    rows: list[list[object]] = []
    annual_years: set[int] = set()
    monthly_periods: set[str] = set()
    indicators: set[str] = set()
    obs_by_product_freq: dict[str, dict[str, int]] = {}
    parsed_files = 0

    for freq in FREQS:
        for product in PRODUCTS:
            path = raw_path(freq, product)
            if not path.exists() or path.stat().st_size == 0:
                continue
            doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            sub = flatten_doc(doc)
            parsed_files += 1
            for r in sub:
                period_type = str(r[0])
                if period_type == "A":
                    annual_years.add(int(str(r[2])))
                else:
                    monthly_periods.add(str(r[1]))
                indicators.add(str(r[10]))  # 未加 dataset 前缀的行，指标在第 10 列
            obs_by_product_freq[f"{product}_{freq}"] = {freq: len(sub)}
            for r in sub:
                rows.append([DATASET] + list(r))
    meta: dict[str, Any] = {
        "parsed_raw_files": parsed_files,
        "annual_years_present": sorted(annual_years),
        "monthly_periods_first": min(monthly_periods) if monthly_periods else None,
        "monthly_periods_last": max(monthly_periods) if monthly_periods else None,
        "monthly_period_count": len(monthly_periods),
        "indicators_present": sorted(indicators),
        "obs_by_product_freq": obs_by_product_freq,
    }
    return rows, meta


def read_existing_provenance(path: Path) -> dict[str, list[str]]:
    """读取既有 provenance.csv，按 URL 建索引（保留最新一次调用）。"""
    merged: dict[str, list[str]] = {}
    if not path.exists():
        return merged
    with path.open(encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if not r or r[0] == "source" or len(r) < 8:
                continue
            merged[r[1]] = r
    return merged


def write_provenance(prov: Provenance, kept: dict[str, list[str]]) -> Path:
    """合并写入：新调用覆盖同 URL 旧记录，跳过下载的保留历史留痕。"""
    for c in prov.calls:
        kept[c.url] = [c.source, c.url, str(c.http_status), str(c.bytes_len),
                       f"{c.elapsed_s:.2f}", c.sha256, c.fetched_at, c.note]
    path = OUT / "provenance.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "url", "http_status", "bytes", "elapsed_s",
                    "sha256", "fetched_at_utc", "note"])
        for r in kept.values():
            w.writerow(r)
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prov = Provenance(SOURCE, OUT)
    missing = download_all(prov)

    kept = read_existing_provenance(OUT / "provenance.csv")
    write_provenance(prov, kept)

    rows, meta = parse_raw_files()
    rows.sort(key=lambda r: (str(r[1]), str(r[9]), str(r[2]), str(r[11])))
    write_csv(OUT / MAIN_TABLE, CSV_HEADER, rows)

    annual_rows = sum(1 for r in rows if str(r[1]) == "A")
    monthly_rows = len(rows) - annual_rows
    write_manifest(OUT, {
        "source": SOURCE,
        "tier": "L3",
        "license": LICENSE,
        "requires_credential": False,
        "dataset": {
            "code": DATASET,
            "label": DATASET_LABEL,
            "updated": "2026-11-13T11:00:00+0100",
            "api_base": API_BASE,
        },
        "reporter": REPORTER,
        "partner": PARTNER,
        "flow": {"code": FLOW, "label": "IMPORT"},
        "products": list(PRODUCTS),
        "rows_total": len(rows),
        "rows_annual": annual_rows,
        "rows_monthly": monthly_rows,
        "coverage": {
            "granularity": "年度为主 + 月度补充",
            "annual_years_present": meta["annual_years_present"],
            "annual_2026_published": False,
            "annual_2026_note": "Comext 年度 2026 在抓取日（2026-11-21）尚未发布，非抓取失败",
            "monthly_first": meta["monthly_periods_first"],
            "monthly_last": meta["monthly_periods_last"],
            "monthly_period_count": meta["monthly_period_count"],
            "monthly_2026_incomplete": True,
            "monthly_2026_note": "Comext 月度约滞后两个月，2026 仅到最新已发布月份，为不完整年",
        },
        "cn8_detail_via_api": False,
        "cn8_detail_note": (
            "API product 维度只到 HS6；CN8 八位子目经 SDMX 端点实测报 "
            "INVALID_QUERY_DIMENSION_VALUE(PRODUCT=42021100)，细目只能走 "
            "comext/COMEXT_DATA/PRODUCTS/ 的 bulk 7z（本切片不取）"
        ),
        "truncation": {
            "truncated_windows": [],
            "note": "API 按过滤条件返回全量观测，无分页上限；观测缺席（如零贸易月）为源端事实，非截断",
        },
        "indicators_present": meta["indicators_present"],
        "obs_by_product_freq": meta["obs_by_product_freq"],
        "raw_files_expected": len(FREQS) * len(PRODUCTS),
        "raw_files_parsed": meta["parsed_raw_files"],
        "raw_missing": missing,
        "coverage_complete": not missing,
        "fetched_at_utc": now_utc(),
    })

    print(f"[comext] 主表 {len(rows)} 行（年度 {annual_rows} / 月度 {monthly_rows}）")
    print(f"[comext] 年度年份 {meta['annual_years_present']}，"
          f"月度 {meta['monthly_periods_first']} ~ {meta['monthly_periods_last']}")
    if missing:
        print(f"[comext] [!] 缺 raw：{missing}，重跑本脚本补齐（已落盘的不会重抓）")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
