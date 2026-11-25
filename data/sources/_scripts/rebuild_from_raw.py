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
from fetch_openalex import HEADER as OPENALEX_HEADER
from fetch_openalex import MAIN_TABLE as OPENALEX_TABLE
from fetch_openalex import MAX_PAGES as OPENALEX_MAX_PAGES
from fetch_openalex import TOPICS as OPENALEX_TOPICS
from fetch_openalex import raw_name as openalex_raw_name
from fetch_openalex import rows_from_body as openalex_rows_from_body
from fetch_openalex import sort_rows as openalex_sort_rows
from fetch_safety_gate import parse_index, parse_report

SOURCES = Path(__file__).resolve().parents[1]


PII_MARKS = ("[phone-removed]", "[email-removed]")


def pii_counts(rows: list[list[object]], col_indexes: tuple[int, ...]) -> dict[str, int]:
    """自动统计 PII 清洗标记数（修复 D-12 的文档漂移）。

    README 里手写的"全表共 N 处替换"会随重抓漂移（实测曾写 34、实际 36）。
    改由重建流程生成计数并写入 manifest，README 引用 manifest 即可，
    validate_quality.py 回归校验两者一致。
    """
    marks = 0
    hit_rows = 0
    per_mark: dict[str, int] = dict.fromkeys(PII_MARKS, 0)
    for r in rows:
        n = 0
        for i in col_indexes:
            cell = str(r[i]) if i < len(r) else ""
            for mark in PII_MARKS:
                c = cell.count(mark)
                per_mark[mark] += c
                n += c
        if n:
            hit_rows += 1
            marks += n
    out = {"marks_total": marks, "rows_affected": hit_rows}
    out.update({mark.strip("[]"): per_mark[mark] for mark in PII_MARKS})
    return out


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_provenance(out_dir: Path, source: str, files: list[Path]) -> None:
    """按 raw 文件实际内容重建留痕。

    修复 D-08：重建留痕写入独立文件 `provenance_from_raw.csv`，**不覆盖**
    在线抓取的 `provenance.csv`（后者含真实 URL、状态码、耗时，一旦被
    FROM_RAW 覆盖即永久丢失）。仅当 `provenance.csv` 完全缺失时才补写一份，
    避免结构校验因无留痕而失败。
    """
    path = out_dir / "provenance_from_raw.csv"
    header = ["source", "raw_file", "http_status", "bytes", "elapsed_s",
              "sha256", "fetched_at_utc", "note"]
    rows: list[list[object]] = []
    for f in sorted(files):
        stat = f.stat()
        rows.append([
            source, f.name, "FROM_RAW", stat.st_size, "",
            file_sha(f),
            datetime.fromtimestamp(stat.st_mtime, UTC)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "从本地原始响应重建，未重新请求网络",
        ])
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)

    online = out_dir / "provenance.csv"
    if not online.exists():
        with online.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        print(f"  [i] {source}: 无在线留痕，已用 FROM_RAW 补写 provenance.csv")
    else:
        print(f"  [i] {source}: 保留既有 provenance.csv，重建留痕写入 "
              f"{path.name}")


def rebuild_openalex() -> int:
    """从每页 raw 重建 OpenAlex 主表（修复 D-04 的离线可重建性）。

    依赖 fetch_openalex 的同一套解析与排序函数，因此在线抓取与离线重建
    产出完全一致；缺页会如实报出，不静默产出短表。
    """
    out = SOURCES / "openalex"
    raw = out / "raw"
    if not raw.exists():
        print("[openalex] 无 raw 目录，跳过")
        return 0

    rows: list[list[object]] = []
    seen: set[str] = set()
    used: list[Path] = []
    metas: dict[str, dict[str, object]] = {}
    missing: list[str] = []

    for key, query in OPENALEX_TOPICS.items():
        got = 0
        pages = 0
        total: object = None
        for page in range(1, OPENALEX_MAX_PAGES + 1):
            f = raw / openalex_raw_name(key, page)
            if not f.exists():
                missing.append(f.name)
                continue
            body = f.read_bytes()
            if page == 1:
                total = json.loads(body).get("meta", {}).get("count")
            page_rows = openalex_rows_from_body(key, body, seen)
            rows.extend(page_rows)
            got += len(page_rows)
            pages += 1
            used.append(f)
        metas[key] = {"query": query, "api_total_in_window": total,
                      "rows_kept": got, "raw_pages_saved": pages}

    write_csv(out / OPENALEX_TABLE, OPENALEX_HEADER, openalex_sort_rows(rows))
    raw_provenance(out, "openalex", used)
    pages_total = sum(int(m["raw_pages_saved"]) for m in metas.values())  # type: ignore[arg-type]
    expected = len(OPENALEX_TOPICS) * OPENALEX_MAX_PAGES
    write_manifest(out, {
        "source": "openalex", "tier": "L3", "license": "open",
        "requires_credential": False,
        "page_limit": 100, "per_page": 100, "max_pages": OPENALEX_MAX_PAGES,
        "mailto_sent": False,
        "mailto_note": "polite pool 自 2026-02 废弃，mailto 被忽略，故不发送",
        "topics": metas, "rows_total": len(rows),
        "raw_pages_saved_total": pages_total,
        "raw_pages_expected_total": expected,
        "raw_complete": pages_total == expected,
        "rebuildable_from_raw": True,
        "raw_policy": ("每主题每页均落盘 raw/{topic}_p{page}.json；"
                       "主表可由 rebuild_from_raw.py 在无网络下重建"),
        "sampling_note": ("每主题按相关性取前 500 条，属方法论样本，"
                          "不是文献计量普查；api_total_in_window 为命中总数"),
        "rebuilt_from_raw": True,
        "provenance_online_lost": True,
        "provenance_note": (
            "历史上 rebuild_from_raw 曾把 FROM_RAW 留痕写进 provenance.csv，"
            "覆盖了首轮在线抓取的 URL、状态码与耗时（含 429 限速记录），"
            "已不可恢复；当前 provenance.csv 仅保证 raw 文件哈希可核验。"
            "脚本已改为把重建留痕另存 provenance_from_raw.csv，不再覆盖（D-08）"),
    })
    if missing:
        print(f"[openalex] 缺 {len(missing)} 个 raw 页：{missing[:5]}"
              f"{'…' if len(missing) > 5 else ''}")
    print(f"[openalex] {pages_total}/{expected} 页 -> {len(rows)} 条")
    return len(rows)


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
        # danger=10, measures=11（见上方 write_csv 列序）
        "pii_scrub_counts": pii_counts(deduped, (10, 11)),
        "rebuilt_from_raw": True,
        "provenance_online_lost": True,
        "provenance_note": (
            "历史上 rebuild_from_raw 曾把 FROM_RAW 留痕写进 provenance.csv，"
            "覆盖了首轮在线抓取的 URL、状态码与耗时，已不可恢复；"
            "当前 provenance.csv 仅保证 raw 文件哈希可核验。"
            "脚本已改为把重建留痕另存 provenance_from_raw.csv，不再覆盖（D-08）"),
        "provenance_gaps": {
            "provenance_resume.csv": (
                "README 所述 44 期在线补抓的留痕未实际保留，文件只有表头；"
                "该批次 raw 文件本身完整且哈希可核验，但在线调用明细已丢失。"
                "resume_safety_gate.py 已改为无调用时不写空壳文件"),
        },
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
        "provenance_online_lost": True,
        "provenance_note": (
            "历史上 rebuild_from_raw 曾把 FROM_RAW 留痕写进 provenance.csv，"
            "覆盖了首轮在线抓取的 URL、状态码与耗时（含 429 限速记录），"
            "已不可恢复；当前 provenance.csv 仅保证 raw 文件哈希可核验。"
            "脚本已改为把重建留痕另存 provenance_from_raw.csv，不再覆盖（D-08）"),
    })
    print(f"[gdelt] {len(files)} 个窗口 -> {len(rows)} 条；触顶 {len(truncated)} 个")
    return len(rows)


if __name__ == "__main__":
    rebuild_safety_gate()
    rebuild_gdelt()
    rebuild_openalex()
