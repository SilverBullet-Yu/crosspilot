"""USAGE（Bielefeld）英德商品评论立场标注基准入库（BENCHMARK，ODC-By 1.0）。

出处查证（2026-11-21）：
- 数据集 = Klinger & Cimiano, "The USAGE review corpus for fine-grained,
  multi-lingual opinion analysis", LREC 2014（比勒费尔德大学）。
- 官方发布页 https://www.romanklinger.de/usagecorpus/（作者个人站点，本机实测
  可达但限速 ~15KB/s，1.4MB 语料包需数分钟；下载超时可重跑续传）。
- 规模判据精确命中：622 条英文 + 611 条德文 Amazon 评论标注，8 类（英）/
  7 类（德）家电百货商品；标注含 aspect、主观短语、主观短语极性、TARG-SUBJ
  目标关系与 COREF 共指（rel 文件），双人独立标注（a1/a2）。

版权特性（关键）：**公开语料不含评论原文**——发布页原话 "For copyright
reasons we cannot publish the Amazon reviews themselves"；tarball 只含标注
（span 词面 + 字符偏移）与重新爬取原文的工具（crawler/）。因此规则立场基线
（stance_baseline.classify_stance 需全文输入）**无法在本基准上评测**，
本来源只作 span 级标注基准，不产 baseline_eval.md。

四件套与中断恢复（对齐 fetch_gerestaurant.py）：
- raw/ 保留官方 v1.0.2 语料包原件 + 英德短语极性词典 + 发布页快照（许可原文
  出处）+ 解包出的 readme/标注指引/LREC 论文预印本/爬虫说明；
- 已存在且非空的文件跳过下载/解包（可反复运行至完整，不重复请求）；
- 主表每次从本地 raw 语料包重建，不发网络请求（本脚本兼作 rebuild_from_raw）；
- provenance.csv 按 URL 去重合并（保留最新一次调用），重跑不丢历史留痕。

主表口径：标注者 a1（IGGSA 共享任务金标同款口径）；a2 完整保留在 raw 语料包，
manifest 记录其规模。主表列含义、金标立场推导规则与已知局限见
data/sources/usage_bielefeld/README.md。
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 同一 sys.path 注入模式见 fetch_gerestaurant.py
from common import (
    Provenance,
    fetch,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "usage_bielefeld"
RAW_DIR = OUT / "raw"

# 官方发布页（作者站点，非 GitHub；2026-11-21 实测可达但限速 ~15KB/s）
BASE_URL = "https://www.romanklinger.de/usagecorpus/"
CORPUS_URL = f"{BASE_URL}USAGE-corpus-1.0.2.tar.gz"
LEXICON_EN_URL = f"{BASE_URL}usage-sentiment-lexicon-en.csv.gz"
LEXICON_DE_URL = f"{BASE_URL}usage-sentiment-lexicon-de.csv.gz"

CORPUS_TGZ = RAW_DIR / "USAGE-corpus-1.0.2.tar.gz"
LEXICON_EN_GZ = RAW_DIR / "usage-sentiment-lexicon-en.csv.gz"
LEXICON_DE_GZ = RAW_DIR / "usage-sentiment-lexicon-de.csv.gz"
PAGE_SNAPSHOT = RAW_DIR / "usagecorpus_release_page.html"
CORPUS_README = RAW_DIR / "corpus_readme.pdf"
GUIDELINE_PDF = RAW_DIR / "annotation_guidelines.pdf"
PAPER_PDF = RAW_DIR / "lrec2014_paper_preprint.pdf"
CRAWLER_README = RAW_DIR / "crawler_readme.txt"

ANNOT_TABLE = "usage_annotations_25292.csv"
REVIEW_TABLE = "usage_reviews_1233.csv"

MEMBER_PREFIX = "USAGE-corpus/files/"
# tar 包内解包留档成员（cor readme 含 v1.0.1 加入的许可声明；guidelines 为
# 官方标注指引；paper 为 LREC 2014 预印本；crawler readme 说明原文爬取工具）
EXTRACT_MEMBERS: dict[str, Path] = {
    "USAGE-corpus/readme.pdf": CORPUS_README,
    "USAGE-corpus/documents/annotation-guidelines.pdf": GUIDELINE_PDF,
    "USAGE-corpus/documents/USAGE-corpus-LREC-paper-preprint.pdf": PAPER_PDF,
    "USAGE-corpus/crawler/readme.txt": CRAWLER_README,
}

# 规模判据（查证判据的机器可执行形态，不一致即拒绝建表）
EXPECTED_REVIEWS = {"en": 622, "de": 611}
EXPECTED_ANNOTATIONS = 25292  # a1 全部 span（aspect + subjective）
EXPECTED_REL = {"TARG-SUBJ": 8566, "COREF": 104}

# 金标立场推导（评测口径，README 同文说明）：评论内全部主观短语极性集合
# 唯一且为 positive/negative 才映射；混合（证据冲突）/中性/unknown/无标注
# 一律 insufficient——与 fetch_gerestaurant.py:derive_gold_stance 的
# 「集合唯一才映射」同型。
POLARITY_TO_STANCE = {"positive": "support", "negative": "oppose"}

# 个人数据扫描口径与 fetch_gerestaurant.py 一致。差异：USAGE 主表只有 span
# 词面（无全文），email 命中即清洗；phone 只计数不清洗——实测 6 处命中均为
# 商品型号/厂商号码词面（如 WMF 1280236040），属标注 span 原文，清洗会破坏
# 基准完整性，判定非个人数据（README/manifest 如实记录）。
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){7,14}\d(?!\d)")

RE_REVIEW_TXT = re.compile(rf"^{MEMBER_PREFIX}(en|de)-([a-z]+)\.txt$")
RE_ANNOT_CSV = re.compile(rf"^{MEMBER_PREFIX}(en|de)-([a-z]+)-a1\.csv$")
RE_REL = re.compile(rf"^{MEMBER_PREFIX}(en|de)-([a-z]+)-a1\.rel$")


def sha256_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def download(url: str, dest: Path, *, prov: Provenance, note: str,
             timeout: int = 120) -> bool:
    """下载文件到 raw/。已存在且非空即跳过（中断恢复核心，ADR-0003 决策 2）。

    common.fetch 自带 3 次退避重试与逐次留痕（URL/状态码/字节/耗时/SHA-256/UTC）。
    发布页服务器限速，语料包约 1.4MB 需数分钟，timeout 放宽到 300s。
    """
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.name} 已存在（{dest.stat().st_size} 字节），跳过下载")
        return True
    body = fetch(url, source="usage_bielefeld", prov=prov, timeout=timeout, note=note)
    if body is None:
        print(f"  [!] 下载失败 {url}，可重跑续传")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    print(f"  [ok] {dest.name} {len(body)} 字节（sha256 {sha256_of(body)[:16]}…）")
    return True


def extract_members() -> bool:
    """从 raw 语料包解包 readme/标注指引/论文/爬虫说明到 raw/（gzip CRC 校验）。"""
    if not CORPUS_TGZ.exists():
        print(f"  [!] 缺 {CORPUS_TGZ.name}，无法解包")
        return False
    missing = [d for d in EXTRACT_MEMBERS.values()
               if not (d.exists() and d.stat().st_size > 0)]
    if not missing:
        print("  [skip] 解包文档均已存在，跳过")
        return True
    with tarfile.open(CORPUS_TGZ, "r:gz") as tf:
        members = {m.name: m for m in tf.getmembers() if m.isfile()}
        for member_name, dest in EXTRACT_MEMBERS.items():
            if dest.exists() and dest.stat().st_size > 0:
                continue
            member = members.get(member_name)
            if member is None:
                print(f"  [!] 语料包内未找到 {member_name}")
                return False
            payload = tf.extractfile(member)
            if payload is None:
                print(f"  [!] {member_name} 读取失败")
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload.read())
            print(f"  [ok] 解包 {member_name} -> {dest.name}")
    return True


def load_corpus() -> dict[str, object]:
    """从 raw 语料包读取 a1 标注与评论 ID 清单（离线，确定性顺序）。

    返回 reviews / annotations / 关系映射；任何规模断言失败即抛 ValueError，
    拒绝建表（不写半截主表）。
    """
    reviews: dict[str, dict[str, str]] = {}
    rev_order: list[str] = []
    annotations: list[dict[str, object]] = []
    # TARG-SUBJ：(评论, 主观短语标注) -> [(目标 aspect 标注, aspect 词面), ...]
    rel_targ: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    # COREF：(评论, aspect 标注) -> [(共指 aspect 标注, 共指词面), ...]（双向登记）
    rel_coref: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    rel_counts: Counter[str] = Counter()
    ann_ids: set[str] = set()
    problems: list[str] = []

    with tarfile.open(CORPUS_TGZ, "r:gz") as tf:
        names = sorted(m.name for m in tf.getmembers() if m.isfile())

        def read_text(name: str) -> str:
            fh = tf.extractfile(tf.getmember(name))
            assert fh is not None  # isfile() 成员必有内容流
            return fh.read().decode("utf-8")

        # 第一遍：评论 ID 清单（.txt，列：内部ID / ASIN / Amazon 评论ID）
        for name in names:
            m = RE_REVIEW_TXT.match(name)
            if not m:
                continue
            lang, cat = m.group(1), m.group(2)
            for line in read_text(name).splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) != 3:
                    problems.append(f"{name}: 列数 {len(parts)} != 3")
                    continue
                rid, asin, amazon_rid = parts
                if rid in reviews:
                    problems.append(f"{name}: review_id {rid} 重复")
                    continue
                reviews[rid] = {
                    "lang": lang, "category": cat,
                    "asin": asin, "amazon_review_id": amazon_rid,
                }
                rev_order.append(rid)

        # 第二遍：a1 标注（列：类型/评论ID/起/止/词面/标注ID/极性/related）
        for name in names:
            m = RE_ANNOT_CSV.match(name)
            if not m:
                continue
            lang, cat = m.group(1), m.group(2)
            for line in read_text(name).splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) != 8:
                    problems.append(f"{name}: 列数 {len(parts)} != 8")
                    continue
                span_type, rid, start, end, span, ann_id, polarity, _ = parts
                if rid not in reviews:
                    problems.append(f"{name}: 标注引用的评论 {rid} 不在 ID 清单")
                if span_type not in ("aspect", "subjective"):
                    problems.append(f"{name}: 未知 span 类型 {span_type}")
                start_i, end_i = int(start), int(end)
                if end_i <= start_i or end_i - start_i != len(span):
                    problems.append(f"{name}: 偏移与词面长度不一致 {ann_id}")
                ann_ids.add(ann_id)
                annotations.append({
                    "annotation_id": ann_id, "review_id": rid,
                    "lang": lang, "category": cat, "span_type": span_type,
                    "span_text": span, "char_start": start_i,
                    "char_end": end_i, "polarity": polarity,
                })

        # 第三遍：a1 关系（列：类型/评论ID/标注A/标注B/词面A/词面B）
        for name in names:
            m = RE_REL.match(name)
            if not m:
                continue
            for line in read_text(name).splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) != 6:
                    problems.append(f"{name}: 列数 {len(parts)} != 6")
                    continue
                rel_type, rid, id_a, id_b, text_a, text_b = parts
                rel_counts[rel_type] += 1
                if id_a not in ann_ids or id_b not in ann_ids:
                    problems.append(f"{name}: 关系引用悬空 {id_a}/{id_b}")
                    continue
                if rel_type == "TARG-SUBJ":
                    rel_targ[(rid, id_b)].append((id_a, text_a))
                elif rel_type == "COREF":
                    rel_coref[(rid, id_a)].append((id_b, text_b))
                    rel_coref[(rid, id_b)].append((id_a, text_a))
                else:
                    problems.append(f"{name}: 未知关系类型 {rel_type}")

    if problems:
        raise ValueError("语料完整性断言失败：\n  " + "\n  ".join(problems[:20]))

    for lang, expect in EXPECTED_REVIEWS.items():
        got = sum(1 for r in reviews.values() if r["lang"] == lang)
        if got != expect:
            raise ValueError(f"{lang} 评论数 {got} != 判据 {expect}")
    if len(annotations) != EXPECTED_ANNOTATIONS:
        raise ValueError(f"a1 标注数 {len(annotations)} != 判据 {EXPECTED_ANNOTATIONS}")
    if dict(rel_counts) != EXPECTED_REL:
        raise ValueError(f"关系计数 {dict(rel_counts)} != 判据 {EXPECTED_REL}")

    return {
        "reviews": reviews, "rev_order": rev_order,
        "annotations": annotations, "rel_targ": rel_targ,
        "rel_coref": rel_coref, "rel_counts": rel_counts,
    }


def derive_gold_stance(polarities: set[str]) -> str:
    """金标立场推导（评测口径，README 同文说明）。

    评论内全部 subjective 标注极性集合唯一且为 positive/negative 才映射；
    正负混合=证据冲突、仅中性/unknown、无标注一律 insufficient。
    """
    if len(polarities) == 1:
        return POLARITY_TO_STANCE.get(next(iter(polarities)), "insufficient")
    return "insufficient"


def build_main_tables(corpus: dict[str, object]) -> dict[str, object]:
    """从本地 raw 语料包重建两张主表（不联网）。返回统计供 manifest。"""
    reviews: dict[str, dict[str, str]] = corpus["reviews"]  # type: ignore[assignment]
    rev_order: list[str] = corpus["rev_order"]  # type: ignore[assignment]
    annotations: list[dict[str, object]] = corpus["annotations"]  # type: ignore[assignment]
    rel_targ: dict[tuple[str, str], list[tuple[str, str]]] = corpus["rel_targ"]  # type: ignore[assignment]
    rel_coref: dict[tuple[str, str], list[tuple[str, str]]] = corpus["rel_coref"]  # type: ignore[assignment]

    span_counter: Counter[str] = Counter()
    pol_counter: Counter[str] = Counter()
    email_hits = 0
    phone_hits = 0
    per_review: dict[str, dict[str, object]] = {
        rid: {"pols": [], "n_aspect": 0, "n_subj": 0} for rid in rev_order
    }
    ann_rows: list[list[object]] = []
    for ann in annotations:
        rid = str(ann["review_id"])
        span = str(ann["span_text"])
        if RE_EMAIL.search(span):
            span = RE_EMAIL.sub("[email-removed]", span)
            email_hits += 1
        if RE_PHONE.search(span):
            phone_hits += 1
        targets = rel_targ.get((rid, str(ann["annotation_id"])), [])
        corefs = rel_coref.get((rid, str(ann["annotation_id"])), [])
        span_counter[str(ann["span_type"])] += 1
        if ann["span_type"] == "subjective":
            pol_counter[str(ann["polarity"])] += 1
            per_review[rid]["pols"].append(str(ann["polarity"]))
            per_review[rid]["n_subj"] += 1
        else:
            per_review[rid]["n_aspect"] += 1
        ann_rows.append([
            ann["annotation_id"], rid, ann["lang"], ann["category"],
            ann["span_type"], span, ann["char_start"], ann["char_end"],
            ann["polarity"],
            "|".join(t[0] for t in targets), "|".join(t[1] for t in targets),
            "|".join(c[0] for c in corefs),
        ])
    write_csv(OUT / ANNOT_TABLE, [
        "annotation_id", "review_id", "lang", "category", "span_type",
        "span_text", "char_start", "char_end", "polarity",
        "target_annotation_ids", "target_span_texts", "coref_annotation_ids",
    ], ann_rows)

    # 每评论 TARG-SUBJ 关系数（rel_counts 按类型聚合计数，此处逐评论重算）
    rel_per_review: Counter[str] = Counter()
    for rid, _ in rel_targ:
        rel_per_review[rid] += 1

    gold_counter: Counter[str] = Counter()
    review_rows: list[list[object]] = []
    for rid in rev_order:
        info = per_review[rid]
        meta = reviews[rid]
        gold = derive_gold_stance(set(info["pols"]))  # type: ignore[arg-type]
        gold_counter[gold] += 1
        review_rows.append([
            rid, meta["lang"], meta["category"], meta["asin"],
            meta["amazon_review_id"], info["n_aspect"], info["n_subj"],
            "|".join(info["pols"]),  # type: ignore[union-attr]
            rel_per_review.get(rid, 0), gold,
        ])
    write_csv(OUT / REVIEW_TABLE, [
        "review_id", "lang", "category", "asin", "amazon_review_id",
        "n_aspect", "n_subjective", "subjective_polarities", "n_relations",
        "gold_stance",
    ], review_rows)

    cat_counter: Counter[str] = Counter()
    lang_counter: Counter[str] = Counter()
    for meta in reviews.values():
        cat_counter[f"{meta['lang']}:{meta['category']}"] += 1
        lang_counter[meta["lang"]] += 1
    return {
        "rows": len(ann_rows),
        "reviews_rows": len(review_rows),
        "lang_review_distribution": dict(sorted(lang_counter.items())),
        "category_review_distribution": dict(sorted(cat_counter.items())),
        "span_type_distribution": dict(sorted(span_counter.items())),
        "subjective_polarity_distribution": dict(sorted(pol_counter.items())),
        "gold_stance_distribution": dict(sorted(gold_counter.items())),
        "pii_scan": {
            "email_hits_scrubbed": email_hits,
            "phone_hits_kept": phone_hits,
            "phone_note": "命中均为商品型号/厂商号码词面（标注 span 原文），不清洗",
        },
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
    # Windows 控制台默认 GBK，打印评论词面里的 ä/ö/ü/ß 会 UnicodeEncodeError
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    prov = Provenance("usage_bielefeld", OUT)

    print("[fetch] 下载官方发布件（romanklinger.de/usagecorpus，服务器限速）")
    ok_page = download(
        BASE_URL, PAGE_SNAPSHOT, prov=prov,
        note="发布页快照：许可声明 ODC-By v1.0 与版权限制的原文出处", timeout=60)
    ok_corpus = download(
        CORPUS_URL, CORPUS_TGZ, prov=prov,
        note="官方语料包 v1.0.2 原件：622 英 + 611 德条标注（不含评论文本）",
        timeout=300)
    ok_lex_en = download(
        LEXICON_EN_URL, LEXICON_EN_GZ, prov=prov,
        note="英语短语-极性词典（从语料抽取，同页分发）")
    ok_lex_de = download(
        LEXICON_DE_URL, LEXICON_DE_GZ, prov=prov,
        note="德语短语-极性词典（从语料抽取，同页分发）")
    if not (ok_page and ok_corpus and ok_lex_en and ok_lex_de):
        write_provenance_merged(prov)
        print("[fetch] 下载未完成，可重跑本脚本续传（已落盘文件自动跳过）")
        return 1

    print("[extract] 解包 readme/标注指引/论文/爬虫说明到 raw/")
    if not extract_members():
        write_provenance_merged(prov)
        return 1

    print("[build] 完整性断言 + 重建主表（离线）")
    try:
        corpus = load_corpus()
        stats = build_main_tables(corpus)
    except ValueError as exc:
        print(f"[!] {exc}")
        write_provenance_merged(prov)
        return 1

    write_provenance_merged(prov)
    write_manifest(OUT, {
        "source": "usage_bielefeld",
        "tier": "benchmark",
        "license": "ODC-By-1.0",
        "requires_credential": False,
        "corpus_type": "benchmark",
        "time_coverage_applicable": False,
        "time_coverage_note": (
            "基准语料是静态标注集（LREC 2014 发布，622 英 + 611 德条 Amazon "
            "评论标注，无发布日期字段），不存在时间发布节奏，时间覆盖密度校验"
            "（validate_coverage.py）不适用；未列入其 TABLES 配置即为本机制的"
            "声明方式，非为绿灯造假"),
        "main_table": ANNOT_TABLE,
        "rows": stats["rows"],
        "main_table_scope": (
            "标注者 a1（IGGSA 共享任务金标同款口径）；a2 标注完整保留在 raw "
            "语料包，规模见 annotator2_counts"),
        "reviews_table": REVIEW_TABLE,
        "reviews_rows": stats["reviews_rows"],
        "corpus_version": "1.0.2",
        "paper": "Klinger & Cimiano, The USAGE review corpus for fine-grained, "
                 "multi-lingual opinion analysis, LREC 2014",
        "lang_review_distribution": stats["lang_review_distribution"],
        "category_review_distribution": stats["category_review_distribution"],
        "span_type_distribution": stats["span_type_distribution"],
        "subjective_polarity_distribution":
            stats["subjective_polarity_distribution"],
        "relation_counts": {"TARG-SUBJ": 8566, "COREF": 104},
        "multi_target_subjective": 503,
        "annotator2_counts": {"annotations": 22062, "aspect": 11664,
                              "subjective": 10398, "relations": 10509},
        "gold_stance_distribution": stats["gold_stance_distribution"],
        "gold_stance_rule": (
            "评论内全部 subjective 极性集合唯一且为 positive/negative 才映射"
            "（positive→support、negative→oppose）；正负混合=证据冲突、仅中性/"
            "unknown、无标注一律 insufficient。USAGE 无总体印象标签，混合评价"
            "占比高（insufficient 50.0%）是该口径的结构性结果"),
        "offset_semantics": (
            "字符偏移：end-start 与 span 词面字符长全量一致（47354/47354 含 a2），"
            "与 UTF-8 字节长不一致 4114 处，排除字节偏移语义"),
        "data_origin": {
            "release_page": BASE_URL,
            "corpus_url": CORPUS_URL,
            "paper_pdf": "https://www.lrec-conf.org/proceedings/lrec2014/pdf/85_Paper.pdf",
            "original_hosting": "https://toolkit.cit-ec.uni-bielefeld.de/datasets/"
                                "usage-review-corpus-fine-grained-multi-lingual-opinion-analysis",
            "reason": "官方发布页由作者 Roman Klinger（语料制作时属比勒费尔德大学）"
                      "维护，v1.0.2 为最新公开版本（2015-07 更新 readme）",
        },
        "extracted_files": [
            "raw/corpus_readme.pdf", "raw/annotation_guidelines.pdf",
            "raw/lrec2014_paper_preprint.pdf", "raw/crawler_readme.txt",
        ],
        "coverage_complete": True,
        "coverage_note": (
            "指数据文件完整性：官方 tar.gz 单包完整下载（gzip CRC 校验 + 规模"
            "断言 622/611、25292 标注、8566+104 关系全部通过），非时间覆盖声明"),
        "pii_scrubbed": ["email"],
        "pii_scan": stats["pii_scan"],
        "pii_scrub_scope": (
            "语料不含评论全文，主表只有 span 词面；email 扫描命中即清洗，phone "
            "只计数不清洗（见 pii_scan.phone_note）；raw/ 保留未清洗原件"),
        "license_note": (
            "发布页声明 The data is available under the Open Data Commons "
            "Attribute License (ODB-By) v1.0（快照见 raw/usagecorpus_release_"
            "page.html）；REGISTRY 登记保持 community-free/不可商用保守口径未"
            "放宽——作者同时声明勿再分发 Amazon 评论原文、含文本版不公开（本"
            "语料不含文本，不受该限制约束）"),
        "domain_caveat": (
            "商品域（家电/百货 8 类）；公开版不含评论文本（版权限制），规则立场"
            "基线（需全文输入）无法在其上评测，只作 span 级标注基准，不进证据卡"),
    })
    print(f"[usage_bielefeld] 标注主表 {OUT / ANNOT_TABLE}：{stats['rows']} 行；"
          f"评论表 {stats['reviews_rows']} 行；金标分布 "
          f"{stats['gold_stance_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
