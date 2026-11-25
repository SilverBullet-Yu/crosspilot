"""MARC（Multilingual Amazon Reviews Corpus）德语基准语料入库（BENCHMARK，research-only）。

许可与硬约束 2：MARC 是 Amazon 学术研究许可（禁商用/转售/重发布，原文见
raw/upstream_load_script.py 的 _LICENSE），只作立场基线评测，不进证据卡；
商业化路径（¥99—199 定价）启动即下线（docs/CONSTRAINTS.md 硬约束 2，
REGISTRY marc 条目 commercial_ok=False）。

分发渠道实测（2026-11-21，ADR-0003 第 4 条：可达性是环境相关事实）：
- HF 官方 amazon_reviews_multi 仓库已因 Amazon 要求下架（hf-mirror 实测
  404 Repository not found，管理者 2026-11-21 实测）；GitHub 无独立官方数据
  仓库（官方分发入口是 registry.opendata.aws/amazon-reviews-ml）；
  raw.githubusercontent.com / codeload.github.com（amazon-research/
  amazon-reviews-ml）实测不可达（ERR / 404）。
- 最终可用源：hf-mirror.com 镜像的 mteb/amazon_reviews_multi（阶梯②备选
  SetFit/amazon_reviews_multi_de 也存在，但 text 字段不含评论标题，弃用）。
  /api/datasets 200 可用；/parquet 503（脚本加载型数据集本无 parquet 分片，
  且镜像抖动持续）；/resolve 偶发 503/502，退避重试后 200。
- mteb 镜像是分类任务重构版：字段 id/text/label/label_text，官方 MARC 的
  product_category / product_id / reviewer_id / review_title 独立字段丢失
  （text 含标题+正文），如实记录于 README/manifest。

下载范围（量级纪律：总下载 <=200MB，实际 ~3MB）：
- 只下载官方 held-out 评测分片 de/test.jsonl（5,000 条）与
  de/validation.jsonl（5,000 条）；de/train.jsonl（61.4MB LFS，201,197 条）
  不下载——规则基线零参数不训练，train 无评测用途；其 URL 与 LFS sha256
  从 API tree 锚定后如实写入 manifest（splits_skipped），可凭 provenance 复现。

星级映射（gold_stance 推导，README 同文说明）：
- label 0-4 = 星级 1-5（label = stars - 1）。证据链：官方每星级 20% 均衡设计
  （加载脚本 _DESCRIPTION）；实测两分片 label 0-4 各恰好 20%；label 0 文本
  为典型一星差评（语义内证）；MTEB Classification 任务口径 stars 1-5 -> 0-4。
- stars 4-5 -> support：满意、正向推荐倾向；stars 1-2 -> oppose：不满意、
  负向不推荐；stars 3 -> insufficient：中评方向不可判定（正负证据并存概率
  最高），与 GERestaurant「混合评价/证据冲突 -> insufficient」口径一致。

四件套与中断恢复（ADR-0003，同 fetch_gerestaurant.py）：
- raw/ 保留三个 jsonl/脚本原件 + HF API tree 响应（train 的 LFS sha256 锚定）；
- 已存在且非空的文件直接跳过下载（可反复运行至完整，不重复请求）；
- 主表每次从本地 raw 重建，不发网络请求（本脚本兼作 rebuild_from_raw）；
- provenance.csv 按 URL 去重合并（保留最新一次调用），重跑不丢历史留痕。
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 同一 sys.path 注入模式见 fetch_gerestaurant.py
from common import (
    Provenance,
    fetch,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "marc"
RAW_DIR = OUT / "raw"
MAIN_TABLE = "marc_reviews_de_10000.csv"

# 仅限 hf-mirror（任务网络边界；HF 官方站本机不可达，GitHub 上无官方数据仓库）。
HF_MIRROR = "https://hf-mirror.com"
DATASET_ID = "mteb/amazon_reviews_multi"
DE_TEST_URL = f"{HF_MIRROR}/datasets/{DATASET_ID}/resolve/main/de/test.jsonl"
DE_VALIDATION_URL = f"{HF_MIRROR}/datasets/{DATASET_ID}/resolve/main/de/validation.jsonl"
LOAD_SCRIPT_URL = f"{HF_MIRROR}/datasets/{DATASET_ID}/resolve/main/amazon_reviews_multi.py"
DE_TREE_API_URL = f"{HF_MIRROR}/api/datasets/{DATASET_ID}/tree/main/de"

DE_TEST = RAW_DIR / "de_test_5000.jsonl"
DE_VALIDATION = RAW_DIR / "de_validation_5000.jsonl"
LOAD_SCRIPT = RAW_DIR / "upstream_load_script.py"
DE_TREE_JSON = RAW_DIR / "hf_api_tree_de.json"

# 个人数据清洗：与 fetch_safety_gate.py / fetch_gerestaurant.py 同一正则口径。
# MARC 上游已匿名化 reviewer/product ID，但评论自由文本仍可能夹带联系方式；
# 主表入库前剔除，raw/ 保留上游原件。
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){7,14}\d(?!\d)")


def scrub(text: str) -> str:
    """自由文本剔除邮箱与电话（GDPR，公开评论仍受约束）。"""
    text = RE_EMAIL.sub("[email-removed]", text)
    return RE_PHONE.sub("[phone-removed]", text)


def download_file(url: str, dest: Path, *, prov: Provenance, note: str,
                  retries: int = 5) -> bool:
    """下载原件到 raw/。已存在且非空即跳过（中断恢复核心，ADR-0003 决策 2）。

    common.fetch 自带逐次退避留痕（URL/状态码/字节/耗时/SHA-256/UTC）；
    hf-mirror /resolve 实测偶发 503/502（镜像抖动），默认重试提高到 5 次。
    """
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.name} 已存在（{dest.stat().st_size} 字节），跳过下载")
        return True
    body = fetch(url, source="marc", prov=prov, timeout=180,
                 retries=retries, note=note)
    if body is None:
        print(f"  [!] 下载失败 {url}，可重跑续传")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    print(f"  [ok] {dest.name} {len(body)} 字节")
    return True


def label_to_stars(label: int) -> int:
    """MTEB label 0-4 -> 官方星级 1-5（label = stars - 1，证据链见模块 docstring）。"""
    return label + 1


def stars_to_gold_stance(stars: int) -> str:
    """星级 -> 金标立场（评测口径，README 同文说明）。

    星级是消费者对商品的总体满意度一维信号（MARC 无 aspect 标注），
    「推荐倾向」语义与 GERestaurant 金标的整体印象极性一致：
    - 4-5 星：满意、正向推荐倾向 -> support
    - 1-2 星：不满意、负向不推荐 -> oppose
    - 3 星：中评，正负证据并存概率最高、方向不可判定 -> insufficient
    """
    if stars >= 4:
        return "support"
    if stars <= 2:
        return "oppose"
    return "insufficient"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """逐行解析 jsonl（UTF-8）。"""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_main_table() -> dict[str, object]:
    """从本地 raw 的 test/validation jsonl 重建主表（不联网）。

    行序固定：先 test 全部、再 validation 全部，各分片内保持 jsonl 原序
    （确定性，供评测固定子集复现）。返回统计供 manifest。
    """
    rows: list[list[object]] = []
    gold_counter: Counter[str] = Counter()
    stars_counter: Counter[str] = Counter()
    split_counter: Counter[str] = Counter()
    for split, path in (("test", DE_TEST), ("validation", DE_VALIDATION)):
        for rec in read_jsonl(path):
            # 直接下标访问：jsonl 每行必有 label 键，缺失时 fail fast（KeyError）
            label = int(rec["label"])
            stars = label_to_stars(label)
            gold = stars_to_gold_stance(stars)
            gold_counter[gold] += 1
            stars_counter[str(stars)] += 1
            split_counter[split] += 1
            rows.append([
                str(rec.get("id")),
                scrub(str(rec.get("text") or "")),
                stars,
                label,
                gold,
                split,
            ])
    write_csv(OUT / MAIN_TABLE, [
        "review_id", "text", "stars", "label", "gold_stance", "split",
    ], rows)
    return {
        "rows": len(rows),
        "gold_stance_distribution": dict(sorted(gold_counter.items())),
        "stars_distribution": dict(sorted(stars_counter.items())),
        "per_split": dict(sorted(split_counter.items())),
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


def extract_train_anchor(tree_path: Path) -> str:
    """从 HF API tree 响应提取 train.jsonl 的 LFS sha256（未下载分片的锚定信息）。"""
    payload: list[dict[str, Any]] = json.loads(tree_path.read_text(encoding="utf-8"))
    for entry in payload:
        if entry.get("path") == "de/train.jsonl" and isinstance(entry.get("lfs"), dict):
            lfs: dict[str, Any] = entry["lfs"]
            return f"{lfs.get('oid')} ({lfs.get('size')} bytes)"
    return "tree 响应中未找到 train.jsonl 的 LFS 信息"


def main() -> int:
    # Windows 控制台默认 GBK，打印评论原文里的 ä/ö/ü/ß 会 UnicodeEncodeError
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    prov = Provenance("marc", OUT)

    print("[fetch] 下载 MARC 德语评测分片与许可原件（仅 hf-mirror）")
    ok1 = download_file(
        DE_TEST_URL, DE_TEST, prov=prov,
        note="MARC 官方 test 分片镜像（held-out 评测集，5,000 条）")
    ok2 = download_file(
        DE_VALIDATION_URL, DE_VALIDATION, prov=prov,
        note="MARC 官方 validation 分片镜像（held-out 评测集，5,000 条）")
    ok3 = download_file(
        LOAD_SCRIPT_URL, LOAD_SCRIPT, prov=prov,
        note="上游 datasets 加载脚本：_LICENSE 含 Amazon 学术研究许可原文")
    ok4 = download_file(
        DE_TREE_API_URL, DE_TREE_JSON, prov=prov,
        note="HF API tree 响应：train.jsonl 的 LFS sha256 锚定（train 未下载）")
    if not (ok1 and ok2 and ok3 and ok4):
        write_provenance_merged(prov)
        print("[fetch] 下载未完成，可重跑本脚本续传（已落盘文件自动跳过）")
        return 1

    stats = build_main_table()
    write_provenance_merged(prov)
    write_manifest(OUT, {
        "source": "marc",
        "tier": "benchmark",
        "license": "research-only",
        "requires_credential": False,
        "corpus_type": "benchmark",
        "time_coverage_applicable": False,
        "time_coverage_note": (
            "基准语料是静态标注集（官方描述采集期 2015-11-01 至 2019-11-01，"
            "无逐条日期字段），不存在时间发布节奏，时间覆盖密度校验"
            "（validate_coverage.py）不适用；未列入其 TABLES 配置即为"
            "本机制的声明方式，非为绿灯造假"),
        "main_table": MAIN_TABLE,
        "rows": stats["rows"],
        "per_split": stats["per_split"],
        "stars_distribution": stats["stars_distribution"],
        "gold_stance_distribution": stats["gold_stance_distribution"],
        "gold_stance_rule": (
            "label 0-4 = 星级 1-5（官方每星级 20% 均衡设计与实测分布内证）；"
            "stars 4-5 -> support、1-2 -> oppose、3 -> insufficient"
            "（中评方向不可判定，与 GERestaurant 混合评价口径一致）"),
        "data_origin": {
            "hf_mirror_dataset": f"{HF_MIRROR}/datasets/{DATASET_ID}",
            "hf_official_dataset": "https://huggingface.co/datasets/amazon/amazon_reviews_multi（已下架，hf-mirror 实测 404）",
            "official_homepage": "https://registry.opendata.aws/amazon-reviews-ml/",
            "mirror_note": (
                "官方 HF 仓库因 Amazon 要求下架；GitHub 无独立官方数据仓库；"
                "raw.githubusercontent.com / codeload.github.com 实测不可达；"
                "mteb/amazon_reviews_multi 是 MTEB Classification 任务重构镜像"
                "（字段 id/text/label/label_text，product_category/product_id/"
                "reviewer_id 独立字段丢失，text 含标题+正文）"),
            "train_anchor": extract_train_anchor(DE_TREE_JSON),
        },
        "splits_downloaded": ["test", "validation"],
        "splits_skipped": {
            "train": (
                "de/train.jsonl（61.4MB LFS，201,197 条）未下载：规则立场基线"
                "零参数不训练，train 无评测用途；URL 与 LFS sha256 已锚定"
                "（data_origin.train_anchor），需要时可凭 provenance 复现"),
        },
        "extracted_files": [
            "raw/de_test_5000.jsonl", "raw/de_validation_5000.jsonl",
            "raw/upstream_load_script.py", "raw/hf_api_tree_de.json",
        ],
        "coverage_complete": True,
        "coverage_note": (
            "指数据文件完整性：test 与 validation 两分片完整下载（各 5,000 条，"
            "与官方每语言 dev/test 5,000 条的设计一致）；train 分片未下载"
            "（见 splits_skipped），非时间覆盖声明"),
        "pii_scrubbed": ["email", "phone"],
        "pii_scrub_scope": "主表 text 列；raw/ 保留上游原件（不入库）",
        "license_note": (
            "Amazon 学术研究许可：禁转售/重发布/商用（含商业研究），禁与个人"
            "身份关联；原文见 raw/upstream_load_script.py 的 _LICENSE；"
            "硬约束 2：商业化路径启动即下线，基准语料不进证据卡"),
        "domain_caveat": (
            "商品域（Amazon.de 等 marketplace 的德语商品评论），只作立场基线"
            "评测，不进证据卡；research-only，商业化启动即下线"),
    })
    print(f"[marc] 主表 {OUT / MAIN_TABLE}：{stats['rows']} 行；"
          f"金标分布 {stats['gold_stance_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
