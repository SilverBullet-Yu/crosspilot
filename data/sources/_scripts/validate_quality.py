"""数据区质量校验：补齐 validate_sources.py 的盲区（审计报告 §6.3）。

validate_sources.py 只看"四件套齐全 + 主表非空 + 许可字段 + 截断声明"，
以下缺陷它一律发现不了，必须独立校验（对应审计报告缺陷 ID）：

| 检查 | 缺陷 ID |
|---|---|
| raw 声明页数与实际落盘页数不一致 | D-04 |
| provenance 指向的 raw 文件缺失或哈希不匹配 | D-04 / D-08 |
| manifest 行数与实际 CSV 行数不一致 | D-10 |
| 主表主键重复 | D-05 |
| 空正文未显式标记 | D-05 |
| 声明为空的字段是否仍被当作可用 | D-05 |
| 重建留痕覆盖在线留痕 | D-08 |
| 只有表头的留痕文件被当作有效补抓记录 | D-08 |
| 快照缺原始响应引用 | D-09 |
| PII 清洗计数文档漂移 | D-12 |

退出码：0 全通过；1 存在不合规项。纳入 scripts/check.sh 作为回归门禁。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

SOURCES = Path(__file__).resolve().parents[1]
DATA = SOURCES.parent
SNAPSHOTS = DATA / "snapshots"

#: 主表主键唯一性约束：目录 -> (主表文件, 主键列)
PRIMARY_KEYS: tuple[tuple[str, str, str], ...] = (
    ("amazon_reviews_2023", "amazon_reviews_2023_pilot_2021_2026.csv", "review_id"),
    ("eu_safety_gate", "safety_gate_de_alerts_2021_2026.csv", "case_number"),
    ("openalex", "openalex_works_2021_2026.csv", "openalex_id"),
    ("gerestaurant", "gerestaurant_reviews_3078.csv", "review_id"),
    ("marc", "marc_reviews_de_10000.csv", "review_id"),
    ("usage_bielefeld", "usage_annotations_25292.csv", "annotation_id"),
    ("usage_bielefeld", "usage_reviews_1233.csv", "review_id"),
)

#: manifest 声明行数与主表实际行数必须一致：目录 -> (主表, manifest 键)
ROW_COUNT_CLAIMS: tuple[tuple[str, str, str], ...] = (
    ("openalex", "openalex_works_2021_2026.csv", "rows_total"),
    ("gdelt", "gdelt_de_coverage_2021_2026.csv", "rows_total"),
    ("eu_comext", "eu_comext_ds045409_de_cn_hs4202_2021_2026.csv", "rows_total"),
)

#: 自由文本含 PII 占位符的主表：目录 -> (主表, 待检列, manifest 计数键)
PII_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("eu_safety_gate", "safety_gate_de_alerts_2021_2026.csv",
     ("danger", "measures")),
    ("amazon_reviews_2023", "amazon_reviews_2023_pilot_2021_2026.csv",
     ("title", "text")),
)

PII_MARKS = ("[phone-removed]", "[email-removed]")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def manifest_of(dir_: Path) -> dict[str, object]:
    mf = dir_ / "manifest.json"
    if not mf.exists():
        return {}
    return json.loads(mf.read_text(encoding="utf-8"))


def check_primary_keys() -> list[str]:
    """主表主键必须唯一（D-05）。"""
    errs: list[str] = []
    for name, table, key in PRIMARY_KEYS:
        path = SOURCES / name / table
        if not path.exists():
            continue  # 许可受限来源（如 MARC）可能不在本地
        rows = read_rows(path)
        if not rows:
            errs.append(f"{name}/{table}: 无数据行")
            continue
        if key not in rows[0]:
            errs.append(f"{name}/{table}: 缺主键列 {key}")
            continue
        values = [r[key] for r in rows]
        blank = sum(1 for v in values if not v.strip())
        dupes = len(values) - len(set(values))
        if blank:
            errs.append(f"{name}/{table}: 主键 {key} 有 {blank} 个空值")
        if dupes:
            errs.append(f"{name}/{table}: 主键 {key} 有 {dupes} 个重复值")
    return errs


def check_openalex_raw_pages() -> list[str]:
    """OpenAlex 声明 max_pages × 主题数，raw 必须逐页落盘（D-04）。"""
    errs: list[str] = []
    dir_ = SOURCES / "openalex"
    m = manifest_of(dir_)
    if not m:
        return ["openalex: 缺 manifest"]
    topics = m.get("topics") or {}
    max_pages = int(m.get("max_pages") or 0)
    raw = dir_ / "raw"
    if not isinstance(topics, dict) or not max_pages:
        return ["openalex: manifest 缺 topics / max_pages"]

    missing: list[str] = []
    for key, meta in topics.items():
        declared = int((meta or {}).get("raw_pages_saved") or 0)
        actual = sum(1 for p in range(1, max_pages + 1)
                     if (raw / f"{key}_p{p}.json").exists())
        if declared != actual:
            errs.append(f"openalex/{key}: manifest 声明落盘 {declared} 页，"
                        f"实际 {actual} 页")
        for p in range(1, max_pages + 1):
            if not (raw / f"{key}_p{p}.json").exists():
                missing.append(f"{key}_p{p}.json")

    expected = len(topics) * max_pages
    saved = int(m.get("raw_pages_saved_total") or 0)
    if saved != expected and m.get("raw_complete") is not False:
        errs.append(f"openalex: 落盘 {saved}/{expected} 页但未声明 "
                    f"raw_complete=false")
    if missing:
        errs.append(f"openalex: 缺 {len(missing)} 个 raw 页（{missing[:4]}"
                    f"{'…' if len(missing) > 4 else ''}），"
                    f"主表无法从 raw 完全重建")
    return errs


def check_row_count_claims() -> list[str]:
    """manifest 声明行数必须等于主表实际行数（D-10）。"""
    errs: list[str] = []
    for name, table, key in ROW_COUNT_CLAIMS:
        path = SOURCES / name / table
        if not path.exists():
            continue
        m = manifest_of(SOURCES / name)
        if key not in m:
            errs.append(f"{name}: manifest 缺行数声明 {key}")
            continue
        actual = len(read_rows(path))
        declared = int(m[key] or 0)
        if actual != declared:
            errs.append(f"{name}: manifest {key}={declared} 与主表实际 "
                        f"{actual} 行不一致")
    return errs


def check_provenance_hashes() -> list[str]:
    """FROM_RAW 留痕引用的 raw 文件必须存在且哈希一致（D-04 / D-08）。

    只有表头的留痕文件不得冒充"补抓已留痕"：要么有记录，要么在 manifest
    的 `provenance_gaps` 中按文件名显式申报留痕缺口与原因（D-08）。
    """
    errs: list[str] = []
    for dir_ in sorted(d for d in SOURCES.iterdir()
                       if d.is_dir() and not d.name.startswith("_")):
        gaps = manifest_of(dir_).get("provenance_gaps") or {}
        declared_gaps = set(gaps) if isinstance(gaps, dict) else set()
        for prov in sorted(dir_.glob("provenance*.csv")):
            rows = read_rows(prov)
            if not rows:
                if prov.name in declared_gaps:
                    continue  # 已在 manifest 显式申报缺口
                errs.append(f"{dir_.name}/{prov.name}: 只有表头，无留痕记录；"
                            f"须在 manifest.provenance_gaps 申报缺口与原因")
                continue
            if "raw_file" not in rows[0]:
                continue  # 在线留痕记 URL，不指向本地文件
            for r in rows:
                fname = (r.get("raw_file") or "").strip()
                declared = (r.get("sha256") or "").strip()
                if not fname or not declared:
                    continue
                f = dir_ / "raw" / fname
                if not f.exists():
                    errs.append(f"{dir_.name}/{prov.name}: 引用的 raw 文件 "
                                f"{fname} 不存在")
                    continue
                actual = hashlib.sha256(f.read_bytes()).hexdigest()
                if actual != declared:
                    errs.append(f"{dir_.name}/{prov.name}: {fname} 哈希不匹配")
    return errs


def check_online_provenance_preserved() -> list[str]:
    """在线留痕不得被 FROM_RAW 重建覆盖（D-08）。

    rebuild_from_raw.py 一旦把 FROM_RAW 写进 provenance.csv，真实 URL、
    状态码与耗时就永久丢失。新策略下重建留痕另存为
    provenance_from_raw.csv；对历史上已被覆盖、确实无法恢复的来源，
    必须在 manifest 以 `provenance_online_lost` 显式申报，不得静默
    让 FROM_RAW 冒充在线留痕。
    """
    errs: list[str] = []
    for dir_ in sorted(d for d in SOURCES.iterdir()
                       if d.is_dir() and not d.name.startswith("_")):
        m = manifest_of(dir_)
        if not m.get("rebuilt_from_raw"):
            continue
        prov = dir_ / "provenance.csv"
        if not prov.exists():
            errs.append(f"{dir_.name}: 缺 provenance.csv")
            continue
        rows = read_rows(prov)
        if not (rows and "raw_file" in rows[0]):
            continue  # provenance.csv 是在线留痕，正常
        # provenance.csv 形如 FROM_RAW：要么另有在线留痕，要么显式申报丢失
        if m.get("provenance_online_lost") is True:
            continue
        errs.append(f"{dir_.name}: provenance.csv 为 FROM_RAW 重建留痕，"
                    f"在线 URL/状态码缺失；须在 manifest 申报 "
                    f"provenance_online_lost=true 并说明原因")
    return errs


def check_empty_text_flagged() -> list[str]:
    """主表空正文必须显式标记，不得静默混入（D-05）。"""
    errs: list[str] = []
    name, table = "amazon_reviews_2023", "amazon_reviews_2023_pilot_2021_2026.csv"
    path = SOURCES / name / table
    if not path.exists():
        return errs
    rows = read_rows(path)
    if not rows or "is_empty_text" not in rows[0]:
        return [f"{name}/{table}: 缺 is_empty_text 标记列，空正文无法识别"]
    mismatch = sum(1 for r in rows
                   if (not r["text"].strip()) != (r["is_empty_text"] == "True"))
    if mismatch:
        errs.append(f"{name}/{table}: {mismatch} 行 is_empty_text 与实际"
                    f"正文是否为空不一致")
    declared = int((manifest_of(SOURCES / name).get("quality_report") or {})
                   .get("empty_text_rows") or 0)
    actual = sum(1 for r in rows if r["is_empty_text"] == "True")
    if declared != actual:
        errs.append(f"{name}: manifest empty_text_rows={declared} 与实际 "
                    f"{actual} 不一致")
    return errs


def check_all_blank_columns_declared() -> list[str]:
    """全空字段必须在 manifest 显式声明，避免被当作可用列（D-05 价格全空）。"""
    errs: list[str] = []
    name, table = "amazon_reviews_2023", "amazon_reviews_2023_pilot_2021_2026.csv"
    path = SOURCES / name / table
    if not path.exists():
        return errs
    rows = read_rows(path)
    if not rows:
        return errs
    m = manifest_of(SOURCES / name)
    quality = m.get("quality_report") or {}
    for col in rows[0]:
        if any(r[col].strip() for r in rows):
            continue
        # 该列全空：必须有同名 *_note 声明
        if not any(str(k).startswith(col) and "note" in str(k)
                   for k in (quality if isinstance(quality, dict) else {})):
            errs.append(f"{name}/{table}: 列 {col} 全部为空，"
                        f"但 manifest quality_report 未声明 {col}_note")
    return errs


def check_pii_counts() -> list[str]:
    """PII 清洗计数必须自动核对，禁止文档手写漂移（D-12）。"""
    errs: list[str] = []
    for name, table, cols in PII_TABLES:
        path = SOURCES / name / table
        if not path.exists():
            continue
        rows = read_rows(path)
        marks = 0
        hit_rows = 0
        for r in rows:
            n = sum(r.get(c, "").count(mark) for c in cols for mark in PII_MARKS)
            if n:
                hit_rows += 1
                marks += n
        readme = SOURCES / name / "README.md"
        if not readme.exists():
            continue
        text = readme.read_text(encoding="utf-8")
        # README 若写出"共 N 处替换"，N 必须等于实测标记数
        for claim in re.findall(r"全表共\s*([\d,]+)\s*处替换", text):
            declared = int(claim.replace(",", ""))
            if declared != marks:
                errs.append(f"{name}/README.md: 声明 PII 替换 {declared} 处，"
                            f"实测 {marks} 处（涉及 {hit_rows} 行）")
    return errs


def check_snapshot_raw_reference() -> list[str]:
    """知乎快照须声明原始响应引用与排除清单（D-09）。"""
    errs: list[str] = []
    zhihu = SNAPSHOTS / "zhihu"
    if not zhihu.exists():
        return errs
    for f in sorted(zhihu.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("is_demo_data") is True:
            continue
        if not d.get("raw_payload_ref"):
            errs.append(f"snapshots/zhihu/{f.name}: 缺 raw_payload_ref，"
                        f"无法逐字复核 API 返回")
        if not d.get("excluded_cards"):
            errs.append(f"snapshots/zhihu/{f.name}: 缺 excluded_cards，"
                        f"排除原因不可审计")
        if d.get("captured_at") and d.get("generated_at_utc") and not d.get(
                "freshness_note"):
            errs.append(f"snapshots/zhihu/{f.name}: captured_at 与 "
                        f"generated_at_utc 语义不同，须有 freshness_note")
    return errs


CHECKS = (
    ("主表主键唯一性", check_primary_keys),
    ("OpenAlex raw 逐页落盘", check_openalex_raw_pages),
    ("manifest 行数与主表一致", check_row_count_claims),
    ("留痕哈希与 raw 文件一致", check_provenance_hashes),
    ("在线留痕未被重建覆盖", check_online_provenance_preserved),
    ("空正文显式标记", check_empty_text_flagged),
    ("全空字段已声明", check_all_blank_columns_declared),
    ("PII 清洗计数无漂移", check_pii_counts),
    ("快照原始响应引用", check_snapshot_raw_reference),
)


def main() -> int:
    all_errs: list[str] = []
    for label, fn in CHECKS:
        errs = fn()
        status = "OK" if not errs else f"{len(errs)} 项问题"
        print(f"[{status:>9s}] {label}")
        all_errs.extend(errs)

    if all_errs:
        print("\n不合规项：")
        for e in all_errs:
            print(f"  - {e}")
        return 1
    print(f"\n{len(CHECKS)} 项质量校验全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
