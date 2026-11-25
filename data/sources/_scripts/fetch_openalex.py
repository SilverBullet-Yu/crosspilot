"""OpenAlex 学术证据抓取（L3 方法论引用）。

主题：跨境/跨文化消费者认知差、aspect-based sentiment、德国电商消费者行为。
时间窗：publication_year 2021-2026（用 API 侧 filter 精确限定）。
许可：开放。无 key 可用；2026-02 起 polite pool 废弃，mailto 参数被忽略，故不发送。
分页：per_page 上限 100，基础分页上限 10000 条——必须显式分页并记录截断。

原始响应落盘纪律（修复 D-04）：
- 历史缺陷：早期版本只在 `page == 1` 时 `save_raw`，25 次调用仅落盘 5 个 p1，
  主表 1,955 行无法从 raw 离线重建，哈希核验出现 20 个「缺原始文件」。
- 现纪律：**每一页都 save_raw**，文件名 `{topic}_p{page}.json`；
  manifest 记录每主题实际落盘页数，`raw_pages_saved` 与 provenance 的 200
  响应数必须一致，由 validate_quality.py 回归校验。
- 主表构建与 raw 解析共用 `rows_from_body`，使 rebuild_from_raw.py 能在
  不发网络请求的前提下重建出逐字节一致的 CSV。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    Provenance,
    fetch,
    save_raw,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "openalex"
BASE = "https://api.openalex.org/works"
PER_PAGE = 100
PAGE_LIMIT = 100  # 来源声明的单次上限，用于截断自检
MAX_PAGES = 5     # 每个主题最多取 500 条，够做方法论引用

TOPICS = {
    "cross_cultural_consumer_perception": "cross-cultural consumer perception",
    "aspect_based_sentiment_analysis": "aspect-based sentiment analysis",
    "german_ecommerce_consumer_behaviour": "German e-commerce consumer behaviour",
    "cross_border_ecommerce_trust": "cross-border e-commerce consumer trust",
    "product_review_helpfulness": "online product review helpfulness",
}

SELECT_FIELDS = (
    "id", "doi", "display_name", "publication_year", "publication_date",
    "type", "cited_by_count", "language", "primary_location", "topics",
    "open_access", "authorships",
)
SELECT = ",".join(SELECT_FIELDS)

MAIN_TABLE = "openalex_works_2021_2026.csv"
HEADER = [
    "topic_key", "openalex_id", "doi", "title", "publication_year",
    "publication_date", "type", "cited_by_count", "language",
    "first_author", "venue", "primary_topic", "is_oa",
]


def raw_name(topic_key: str, page: int) -> str:
    """原始响应文件名：每主题每页一个文件。"""
    return f"{topic_key}_p{page}.json"


def first_author(work: dict) -> str:
    auth = work.get("authorships") or []
    if not auth:
        return ""
    return (auth[0].get("author") or {}).get("display_name", "")


def venue(work: dict) -> str:
    loc = work.get("primary_location") or {}
    return ((loc.get("source") or {}).get("display_name")) or ""


def row_from_work(topic_key: str, work: dict) -> list[object] | None:
    """单条 work -> 主表行；窗口外或无 ID 返回 None。"""
    wid = work.get("id", "")
    year = work.get("publication_year")
    if not wid or year is None or not 2021 <= year <= 2026:
        return None
    topic = (work.get("topics") or [{}])[0].get("display_name", "")
    return [
        topic_key, wid.rsplit("/", 1)[-1], work.get("doi") or "",
        (work.get("display_name") or "")[:240], year,
        work.get("publication_date") or "", work.get("type") or "",
        work.get("cited_by_count", 0), work.get("language") or "",
        first_author(work)[:80], venue(work)[:120], topic[:90],
        bool((work.get("open_access") or {}).get("is_oa")),
    ]


def rows_from_body(topic_key: str, body: bytes, seen: set[str]) -> list[list[object]]:
    """解析一页响应为主表行，并就地更新全局去重集合。

    在线抓取与 raw 重建共用本函数，保证两条路径产出完全一致。
    """
    doc = json.loads(body)
    results = doc.get("results", [])
    if len(results) > PAGE_LIMIT:
        raise AssertionError(f"返回 {len(results)} 条超过声明上限 {PAGE_LIMIT}")
    out: list[list[object]] = []
    for work in results:
        row = row_from_work(topic_key, work)
        if row is None:
            continue
        wid = str(row[1])
        if wid in seen:
            continue
        seen.add(wid)
        out.append(row)
    return out


def sort_rows(rows: list[list[object]]) -> list[list[object]]:
    """主表排序：主题内按被引数降序。稳定排序保留页内原始顺序。"""
    return sorted(rows, key=lambda r: (str(r[0]), -int(r[7])))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prov = Provenance("openalex", OUT)
    rows: list[list[object]] = []
    metas: dict[str, dict] = {}
    seen: set[str] = set()

    for key, query in TOPICS.items():
        print(f"[openalex] {key}")
        total = None
        got = 0
        pages_saved = 0
        for page in range(1, MAX_PAGES + 1):
            url = (f"{BASE}?search={quote(query)}"
                   f"&filter=publication_year:2021-2026"
                   f"&per_page={PER_PAGE}&page={page}&select={SELECT}")
            body = fetch(url, source="openalex", prov=prov, timeout=90,
                         backoff_s=3.0, note=f"{key} page={page}")
            if body is None:
                break
            # 每页都落盘：主表任意一行都可从 raw 离线重建（修复 D-04）
            save_raw(OUT, raw_name(key, page), body)
            pages_saved += 1
            if page == 1:
                total = json.loads(body)["meta"]["count"]
            page_rows = rows_from_body(key, body, seen)
            rows.extend(page_rows)
            got += len(page_rows)
            if len(json.loads(body).get("results", [])) < PER_PAGE:
                break
            time.sleep(1.0)
        metas[key] = {"query": query, "api_total_in_window": total,
                      "rows_kept": got, "raw_pages_saved": pages_saved}
        print(f"  -> 窗口内命中 {total}，取回 {got} 条，落盘 {pages_saved} 页")

    write_csv(OUT / MAIN_TABLE, HEADER, sort_rows(rows))
    prov.write()
    pages_total = sum(int(m["raw_pages_saved"]) for m in metas.values())
    write_manifest(OUT, {
        "source": "openalex", "tier": "L3", "license": "open",
        "requires_credential": False,
        "page_limit": PAGE_LIMIT, "per_page": PER_PAGE, "max_pages": MAX_PAGES,
        "mailto_sent": False,
        "mailto_note": "polite pool 自 2026-02 废弃，mailto 被忽略，故不发送",
        "topics": metas, "rows_total": len(rows),
        "raw_pages_saved_total": pages_total,
        "raw_pages_expected_total": len(TOPICS) * MAX_PAGES,
        "raw_complete": pages_total == len(TOPICS) * MAX_PAGES,
        "rebuildable_from_raw": True,
        "raw_policy": ("每主题每页均落盘 raw/{topic}_p{page}.json；"
                       "主表可由 rebuild_from_raw.py 在无网络下重建"),
        "sampling_note": ("每主题按相关性取前 500 条，属方法论样本，"
                          "不是文献计量普查；api_total_in_window 为命中总数"),
    })
    print(f"[openalex] 合计 {len(rows)} 条，落盘 {pages_total}/"
          f"{len(TOPICS) * MAX_PAGES} 页")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
