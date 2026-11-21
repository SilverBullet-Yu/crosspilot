"""从已落盘的 raw/ 重建主表与 manifest，不发起任何网络请求。

用途：抓取进程被中断时，用已下载的原始响应补齐 CSV 与 manifest，
避免为了产出表格而重复抓取。provenance.csv 由本脚本按 raw 文件实际内容重建，
http_status 记为 "FROM_RAW"，与在线抓取的留痕区分开。
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import WINDOW_YEARS, write_csv, write_manifest
from fetch_safety_gate import parse_index, parse_report

SOURCES = Path(__file__).resolve().parents[1]


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_provenance(out_dir: Path, source: str, files: list[Path]) -> None:
    """按 raw 文件实际内容重建留痕。"""
    path = out_dir / "provenance.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "raw_file", "http_status", "bytes", "elapsed_s",
                    "sha256", "fetched_at_utc", "note"])
        for f in sorted(files):
            stat = f.stat()
            w.writerow([
                source, f.name, "FROM_RAW", stat.st_size, "",
                file_sha(f),
                datetime.fromtimestamp(stat.st_mtime, UTC)
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "从本地原始响应重建，未重新请求网络",
            ])


def rebuild_safety_gate() -> int:
    out = SOURCES / "eu_safety_gate"
    raw = out / "raw"
    index_file = raw / "weekly_report_index.xml"
    if not index_file.exists():
        print("[safety_gate] 缺少索引，跳过")
        return 0

    reports = parse_index(index_file.read_bytes())
    by_id = {rid: (pub, ref) for rid, pub, _url, ref in reports}

    rows: list[list[object]] = []
    used: list[Path] = [index_file]
    for f in sorted(raw.glob("report_*.xml")):
        rid = f.stem.replace("report_", "")
        pub, ref = by_id.get(rid, ("", rid))
        try:
            rows.extend(parse_report(f.read_bytes(), ref, pub))
        except Exception as exc:  # noqa: BLE001
            print(f"  [!] 解析失败 {f.name}: {type(exc).__name__}")
            continue
        used.append(f)

    # 同一 case 可能在多期周报重复出现，按 case_number 去重，保留最早一期
    seen: set[str] = set()
    deduped: list[list[object]] = []
    for r in sorted(rows, key=lambda r: str(r[1])):
        case = str(r[0])
        if case in seen:
            continue
        seen.add(case)
        deduped.append(r)

    years = sorted({str(r[2])[-4:] for r in deduped if str(r[2])[-4:] in WINDOW_YEARS})
    write_csv(out / "safety_gate_de_alerts_2021_2026.csv",
              ["case_number", "report_reference", "publication_date", "category",
               "product", "product_name", "brand", "barcode", "risk_type",
               "risk_level", "danger", "measures", "notifying_country",
               "country_of_origin", "de_relation"],
              deduped)
    raw_provenance(out, "eu_safety_gate", used)
    reports_fetched = len(used) - 1
    write_manifest(out, {
        "source": "eu_safety_gate", "tier": "L3", "license": "CC0-1.0",
        "requires_credential": False,
        "reports_in_window": len(reports),
        "reports_fetched": reports_fetched,
        "reports_missing": len(reports) - reports_fetched,
        "coverage_complete": reports_fetched == len(reports),
        "rows_before_dedup": len(rows), "de_rows": len(deduped),
        "years_covered": years,
        "pii_scrubbed": ["email", "phone"],
        "rebuilt_from_raw": True,
    })
    print(f"[safety_gate] {reports_fetched}/{len(reports)} 期 -> "
          f"去重后 {len(deduped)} 条（去重前 {len(rows)}），年份 {years}")
    return len(deduped)


def rebuild_gdelt() -> int:
    out = SOURCES / "gdelt"
    raw = out / "raw"
    files = sorted(raw.glob("*.json"))
    if not files:
        print("[gdelt] 无 raw 文件，跳过")
        return 0

    citation = "Source: The GDELT Project (https://www.gdeltproject.org/)"
    queries = {"de_luggage_de_lang": "Koffer sourcelang:german",
               "en_luggage_de_src": "luggage sourcecountry:GM"}

    rows: list[list[object]] = []
    seen: set[str] = set()
    truncated: list[str] = []
    windows_got: dict[str, list[str]] = {}

    for f in files:
        stem = f.stem
        key = next((k for k in queries if stem.startswith(k)), "")
        label = stem.replace(f"{key}_", "") if key else stem
        arts = json.loads(f.read_text(encoding="utf-8", errors="replace")).get("articles", [])
        if len(arts) >= 250:
            truncated.append(f"{key}/{label}")
        windows_got.setdefault(key, []).append(label)
        for a in arts:
            u = a.get("url", "")
            if not u or u in seen:
                continue
            seen.add(u)
            rows.append([key, queries.get(key, ""), label, a.get("seendate", ""),
                         (a.get("title") or "")[:240], a.get("domain", ""),
                         a.get("sourcecountry", ""), a.get("language", ""), u, citation])

    write_csv(out / "gdelt_de_coverage_2021_2026.csv",
              ["query_key", "query", "half_year", "seen_date_utc", "title",
               "domain", "source_country", "language", "url", "citation"],
              sorted(rows, key=lambda r: (r[0], r[3])))
    raw_provenance(out, "gdelt", files)
    write_manifest(out, {
        "source": "gdelt_doc", "tier": "L3",
        "license": "unrestricted use with attribution",
        "requires_credential": False, "citation_required": citation,
        "page_limit": 250, "window_granularity": "half-year",
        "content_scope": "仅标题与链接，不含正文",
        "queries": {k: {"query": v, "windows_retrieved": sorted(windows_got.get(k, []))}
                    for k, v in queries.items()},
        "windows_expected_per_query": 12,
        "rows_total": len(rows), "truncated_windows": sorted(truncated),
        "coverage_complete": False,
        "coverage_note": "GDELT 限速导致多数半年窗未取回，详见 README",
        "time_coverage_sparse": True,
        "time_coverage_note": (
            "sort=datedesc + maxrecords=250 使每窗只取到窗口末端的 250 条。"
            "en_luggage_de_src 四窗共 1000 条，实际仅覆盖 33 天 / 730 天（4.5%）。"
            "行数充足不等于时间覆盖充足，禁止用于任何跨时间比较或趋势结论。"
        ),
        "window_actual_day_spans": {
            "de_luggage_de_lang/2021H2": 84, "de_luggage_de_lang/2022H2": 88,
            "en_luggage_de_src/2021H1": 8, "en_luggage_de_src/2021H2": 11,
            "en_luggage_de_src/2022H1": 3, "en_luggage_de_src/2022H2": 11,
        },
        "rebuilt_from_raw": True,
    })
    print(f"[gdelt] {len(files)} 个窗口 -> {len(rows)} 条；触顶 {len(truncated)} 个")
    return len(rows)


if __name__ == "__main__":
    rebuild_safety_gate()
    rebuild_gdelt()
