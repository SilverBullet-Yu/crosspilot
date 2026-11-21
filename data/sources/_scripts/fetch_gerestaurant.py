"""GERestaurant 基准语料入库（BENCHMARK，CC-BY-4.0，德语 ABSA 标注）。

发布渠道实测（2026-11-21，ADR-0003 第 4 条：可达性是环境相关事实）：
- 上游仓库 NilsHellwig/GERestaurant 本身**不携带标注数据**：baseline/load_dataset.py
  期望的 data/train_dataset.json / test_dataset.json 被其 .gitignore 明确排除，
  git 历史仅 1 个提交、无 releases，HF（NilsHellwig/GERestaurant）经 hf-mirror
  实测 Repository not found。作者经 HuggingFace 分发，本机 HF 直连不可达。
- 标注数据取自 fork kartik-gadhvi/GERestaurant：init 提交 2024-09-13（与
  KONVENS 2024 论文发表同期），含 data/dataset_filtered.json（3,078 条，
  即 do_split.ipynb 划分 train/test 的输入原件）。

四件套与中断恢复（ADR-0003）：
- raw/ 保留两份 codeload zip 原始响应 + 解包出的 dataset_filtered.json 原件，
  以及上游 README/.gitignore、annotation_guideline.pdf；
- 已存在且非空的 zip 直接跳过下载（可反复运行至完整，不重复请求）；
- 主表每次从本地 raw 重建，不发网络请求（本脚本兼作 rebuild_from_raw）；
- provenance.csv 按 URL 去重合并（保留最新一次调用），重跑不丢历史留痕。

主表列含义与金标立场（gold_stance）推导规则见 data/sources/gerestaurant/README.md。
餐厅域不可外推为商品域：本来源只作立场基线评测，不进证据卡（tier=BENCHMARK）。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 同一 sys.path 注入模式见 fetch_amazon_reviews.py
from common import (
    Provenance,
    fetch,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "gerestaurant"
RAW_DIR = OUT / "raw"
MAIN_TABLE = "gerestaurant_reviews_3078.csv"

# 仅限 GitHub（任务网络边界）。codeload 是 GitHub 的打包下载端点。
UPSTREAM_REPO = "NilsHellwig/GERestaurant"
DATA_REPO = "kartik-gadhvi/GERestaurant"
UPSTREAM_ZIP_URL = f"https://codeload.github.com/{UPSTREAM_REPO}/zip/refs/heads/main"
DATA_ZIP_URL = f"https://codeload.github.com/{DATA_REPO}/zip/refs/heads/main"
UPSTREAM_ZIP = RAW_DIR / "gerestaurant_upstream_main.zip"
DATA_ZIP = RAW_DIR / "gerestaurant_fork_main.zip"
DATA_JSON = RAW_DIR / "dataset_filtered.json"
UPSTREAM_README = RAW_DIR / "upstream_README.md"
UPSTREAM_GITIGNORE = RAW_DIR / "upstream_gitignore.txt"
GUIDELINE_PDF = RAW_DIR / "annotation_guideline.pdf"

# 金标立场推导：GERestaurant 极性 -> 本项目 Stance（domain/evidence.py）
POLARITY_TO_STANCE = {"POSITIVE": "support", "NEGATIVE": "oppose", "NEUTRAL": "insufficient"}
GENERAL_IMPRESSION = "GENERAL-IMPRESSION"

# 个人数据清洗：与 fetch_safety_gate.py / fetch_amazon_reviews.py 同一正则口径。
# 评论描述用餐体验而非个人，但自由文本可能夹带联系方式；主表入库前剔除。
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){7,14}\d(?!\d)")


def scrub(text: str) -> str:
    """自由文本剔除邮箱与电话（GDPR，公开评论仍受约束）。"""
    text = RE_EMAIL.sub("[email-removed]", text)
    return RE_PHONE.sub("[phone-removed]", text)


def sha256_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def download_zip(url: str, dest: Path, *, prov: Provenance, note: str) -> bool:
    """下载 zip 到 raw/。已存在且非空即跳过（中断恢复核心，ADR-0003 决策 2）。

    common.fetch 自带 3 次退避重试与逐次留痕（URL/状态码/字节/耗时/SHA-256/UTC）。
    """
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.name} 已存在（{dest.stat().st_size} 字节），跳过下载")
        return True
    body = fetch(url, source="gerestaurant", prov=prov, timeout=180, note=note)
    if body is None:
        print(f"  [!] 下载失败 {url}，可重跑续传")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    print(f"  [ok] {dest.name} {len(body)} 字节（sha256 {sha256_of(body)[:16]}…）")
    return True


def extract_member(zip_path: Path, suffix: str, dest: Path, *, label: str) -> bool:
    """从 zip 解包单个原件到 raw/（zipfile 读出即做 CRC 校验）。"""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.name} 已解包，跳过")
        return True
    if not zip_path.exists():
        print(f"  [!] 缺 {zip_path.name}，无法解包 {label}")
        return False
    with zipfile.ZipFile(zip_path) as zf:
        members = [n for n in zf.namelist() if n.endswith(suffix)]
        if not members:
            print(f"  [!] {zip_path.name} 内未找到 *{suffix}")
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zf.read(members[0]))
    print(f"  [ok] 解包 {label} -> {dest.name}")
    return True


def derive_gold_stance(tags: list[dict[str, Any]]) -> str:
    """金标立场推导（评测口径，README 同文说明）。

    1. 有 GENERAL-IMPRESSION 标签：取其极性直接映射（POSITIVE->support，
       NEGATIVE->oppose，NEUTRAL->insufficient）；若多条 GI 极性冲突，按证据
       冲突处理为 insufficient。
    2. 无 GI 但有其他 aspect 标签：全部极性一致则映射该极性；混合极性按
       证据冲突处理为 insufficient。
    3. 无任何标签：insufficient。
    """
    pols_gi = {str(t.get("polarity")) for t in tags if t.get("label") == GENERAL_IMPRESSION}
    if pols_gi:
        if len(pols_gi) == 1:
            return POLARITY_TO_STANCE.get(pols_gi.pop(), "insufficient")
        return "insufficient"
    pols = {str(t.get("polarity")) for t in tags}
    if len(pols) == 1:
        return POLARITY_TO_STANCE.get(pols.pop(), "insufficient")
    return "insufficient"


def build_main_table() -> dict[str, object]:
    """从本地 raw/dataset_filtered.json 重建主表（不联网）。

    行序保持 JSON 原序（确定性，供评测固定子集复现）。返回统计供 manifest。
    """
    records: list[dict[str, Any]] = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    rows: list[list[object]] = []
    aspect_counter: Counter[str] = Counter()
    polarity_counter: Counter[str] = Counter()
    gold_counter: Counter[str] = Counter()
    for rec in records:
        tags: list[dict[str, Any]] = rec.get("tags") or []
        labels = [str(t.get("label")) for t in tags]
        pols = [str(t.get("polarity")) for t in tags]
        gold = derive_gold_stance(tags)
        for lab, pol in zip(labels, pols, strict=True):
            aspect_counter[lab] += 1
            polarity_counter[f"{lab}={pol}"] += 1
        gold_counter[gold] += 1
        rows.append([
            str(rec.get("id")),
            scrub(str(rec.get("text") or "")),
            "|".join(labels),
            "|".join(pols),
            len(tags),
            gold,
        ])
    write_csv(OUT / MAIN_TABLE, [
        "review_id", "text", "aspect_labels", "aspect_polarities", "n_aspects",
        "gold_stance",
    ], rows)
    return {
        "rows": len(rows),
        "aspect_distribution": dict(sorted(aspect_counter.items())),
        "polarity_distribution": dict(sorted(polarity_counter.items())),
        "gold_stance_distribution": dict(sorted(gold_counter.items())),
    }


def write_provenance_merged(prov: Provenance) -> Path:
    """provenance 按 URL 去重合并（保留最新一次调用），重跑不丢历史留痕。"""
    path = OUT / "provenance.csv"
    header = ["source", "url", "http_status", "bytes", "elapsed_s",
              "sha256", "fetched_at_utc", "note"]
    merged: dict[str, list[str]] = {}
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if len(row) >= 8 and row[0] != "source":
                    merged[row[1]] = row
    for c in prov.calls:
        merged[c.url] = [c.source, c.url, str(c.http_status), str(c.bytes_len),
                         f"{c.elapsed_s:.2f}", c.sha256, c.fetched_at, c.note]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(merged.values())
    return path


def main() -> int:
    # Windows 控制台默认 GBK，打印评论原文里的 ä/ö/ü/ß 会 UnicodeEncodeError
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    prov = Provenance("gerestaurant", OUT)

    print("[fetch] 下载整库快照（codeload zip，仅 GitHub）")
    ok_up = download_zip(
        UPSTREAM_ZIP_URL, UPSTREAM_ZIP, prov=prov,
        note="上游整库快照：无数据文件，供 README/标注指引/许可语境引用")
    ok_data = download_zip(
        DATA_ZIP_URL, DATA_ZIP, prov=prov,
        note="数据来源 fork 整库快照：含 data/dataset_filtered.json（init 提交 2024-09-13）")
    if not (ok_up and ok_data):
        write_provenance_merged(prov)
        print("[fetch] 下载未完成，可重跑本脚本续传（已落盘文件自动跳过）")
        return 1

    print("[extract] 解包原件到 raw/")
    ok1 = extract_member(UPSTREAM_ZIP, "/README.md", UPSTREAM_README, label="上游 README")
    ok2 = extract_member(UPSTREAM_ZIP, "/.gitignore", UPSTREAM_GITIGNORE,
                         label="上游 .gitignore（数据文件被排除的证据）")
    ok3 = extract_member(UPSTREAM_ZIP, "/annotation_guideline.pdf", GUIDELINE_PDF,
                         label="标注指引 PDF")
    ok4 = extract_member(DATA_ZIP, "/data/dataset_filtered.json", DATA_JSON,
                         label="标注数据原件")
    if not (ok1 and ok2 and ok3 and ok4):
        write_provenance_merged(prov)
        return 1

    stats = build_main_table()
    write_provenance_merged(prov)
    write_manifest(OUT, {
        "source": "gerestaurant",
        "tier": "benchmark",
        "license": "CC-BY-4.0",
        "requires_credential": False,
        "corpus_type": "benchmark",
        "time_coverage_applicable": False,
        "time_coverage_note": (
            "基准语料是静态标注集（3,078 条餐厅评论，无发布日期字段），不存在"
            "时间发布节奏，时间覆盖密度校验（validate_coverage.py）不适用；"
            "未列入其 TABLES 配置即为本机制的声明方式，非为绿灯造假"),
        "main_table": MAIN_TABLE,
        "rows": stats["rows"],
        "aspect_distribution": stats["aspect_distribution"],
        "polarity_distribution": stats["polarity_distribution"],
        "gold_stance_distribution": stats["gold_stance_distribution"],
        "gold_stance_rule": (
            "GENERAL-IMPRESSION 极性优先且冲突即 insufficient；无 GI 则全体"
            "aspect 极性一致才映射，混合极性 insufficient；无标签 insufficient"),
        "data_origin": {
            "upstream_repo": f"https://github.com/{UPSTREAM_REPO}",
            "data_repo": f"https://github.com/{DATA_REPO}",
            "data_repo_commit_date": "2024-09-13",
            "reason": ("上游 .gitignore 排除 data/*_dataset.json，作者经 HuggingFace "
                       "分发而本机 HF 不可达；fork init 提交与 KONVENS 2024 论文发表同期"),
        },
        "extracted_files": [
            "raw/dataset_filtered.json", "raw/upstream_README.md",
            "raw/upstream_gitignore.txt", "raw/annotation_guideline.pdf",
        ],
        "coverage_complete": True,
        "coverage_note": (
            "指数据文件完整性：上游分发的 dataset_filtered.json 单文件完整下载"
            "（3,078/3,078 条），非时间覆盖声明"),
        "pii_scrubbed": ["email", "phone"],
        "pii_scrub_scope": "主表 text 列；raw/ 保留原文（不入库）",
        "license_note": (
            "上游仓库无 LICENSE 文件；CC-BY-4.0 依 REGISTRY 既有登记与底层"
            "Google Maps 评论内容的 CC BY 4.0 条款，商用须署名（引用论文）"),
        "domain_caveat": "餐厅域，不可外推为商品域；只作基线评测，不进证据卡",
    })
    print(f"[gerestaurant] 主表 {OUT / MAIN_TABLE}：{stats['rows']} 行；"
          f"金标分布 {stats['gold_stance_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
