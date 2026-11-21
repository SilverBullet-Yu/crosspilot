"""Eurostat ISOC 德国切片抓取（L3 市场语境）。

数据集：isoc_ec_ib20（线上购买行为，2020 起）、isoc_ec_ibuy（线上购买人群占比）。
时间窗：2021-2026；实际可得年份取决于调查进度，缺失年份在 README 显式标注。
许可：Eurostat 开放数据，免注册。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    WINDOW_YEARS,
    Provenance,
    fetch,
    save_raw,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "eurostat_isoc"
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
DATASETS = {
    "isoc_ec_ib20": "Internet purchases by individuals (2020 onwards)",
    # isoc_ec_ibuy 已核验为 2002-2019 停更数据集（updated 2024-06-16），
    # 全部观测落在 2021-2026 窗口外，故不纳入。详见 README。
}


def flatten(dataset: str, doc: dict) -> tuple[list[list[object]], dict]:
    """JSON-stat 2.0 展平为长表。只保留 2021-2026 年份。"""
    dims = doc["dimension"]
    order: list[str] = doc.get("id") or list(dims)
    sizes: list[int] = doc.get("size") or [len(dims[d]["category"]["index"]) for d in order]

    # 每个维度：序号 -> (code, label)
    decoded: dict[str, dict[int, tuple[str, str]]] = {}
    for d in order:
        cat = dims[d]["category"]
        idx = cat["index"]
        if isinstance(idx, dict):
            pos = {v: k for k, v in idx.items()}
        else:
            pos = dict(enumerate(idx))
        labels = cat.get("label", {})
        decoded[d] = {p: (c, labels.get(c, c)) for p, c in pos.items()}

    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    rows: list[list[object]] = []
    kept_years: set[str] = set()
    for flat_idx, value in doc.get("value", {}).items():
        n = int(flat_idx)
        coords: dict[str, tuple[str, str]] = {}
        for dim, stride in zip(order, strides, strict=True):
            coords[dim] = decoded[dim][(n // stride) % len(decoded[dim])]
        year = coords.get("time", ("", ""))[0]
        if year not in WINDOW_YEARS:
            continue
        kept_years.add(year)
        rows.append([
            dataset, year,
            coords.get("geo", ("", ""))[0],
            coords.get("indic_is", ("", ""))[0],
            coords.get("indic_is", ("", ""))[1],
            coords.get("unit", ("", ""))[0],
            coords.get("ind_type", ("", ""))[0],
            coords.get("ind_type", ("", ""))[1],
            value,
        ])
    meta = {"updated": doc.get("updated"), "label": doc.get("label"),
            "years_kept": sorted(kept_years), "obs_total": len(doc.get("value", {}))}
    return rows, meta


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prov = Provenance("eurostat", OUT)
    all_rows: list[list[object]] = []
    metas: dict[str, dict] = {}

    for ds in DATASETS:
        url = f"{BASE}/{ds}?geo=DE&format=JSON&lang=EN"
        print(f"[eurostat] {ds}")
        body = fetch(url, source="eurostat", prov=prov, timeout=120, note=ds)
        if body is None:
            metas[ds] = {"error": "unreachable"}
            continue
        save_raw(OUT, f"{ds}_DE.json", body)
        rows, meta = flatten(ds, json.loads(body))
        all_rows.extend(rows)
        metas[ds] = meta
        print(f"  -> {len(rows)} 行（窗口内），年份 {meta['years_kept']}")

    write_csv(OUT / "eurostat_isoc_de_2021_2026.csv",
              ["dataset", "year", "geo", "indicator_code", "indicator_label",
               "unit", "ind_type_code", "ind_type_label", "value"],
              sorted(all_rows, key=lambda r: (r[0], r[1], r[3])))
    prov.write()
    write_manifest(OUT, {
        "source": "eurostat", "tier": "L3", "license": "Eurostat open data",
        "requires_credential": False, "datasets": metas,
        "rows_in_window": len(all_rows),
    })
    print(f"[eurostat] 合计 {len(all_rows)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
