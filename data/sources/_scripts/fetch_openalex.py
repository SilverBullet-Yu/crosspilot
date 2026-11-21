"""OpenAlex 学术证据抓取（L3 方法论引用）。

主题：跨境/跨文化消费者认知差、aspect-based sentiment、德国电商消费者行为。
时间窗：publication_year 2021-2026（用 API 侧 filter 精确限定）。
许可：开放。无 key 可用；2026-02 起 polite pool 废弃，mailto 参数被忽略，故不发送。
分页：per_page 上限 100，基础分页上限 10000 条——必须显式分页并记录截断。
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


def first_author(work: dict) -> str:
    auth = work.get("authorships") or []
    if not auth:
        return ""
    return (auth[0].get("author") or {}).get("display_name", "")


def venue(work: dict) -> str:
    loc = work.get("primary_location") or {}
    return ((loc.get("source") or {}).get("display_name")) or ""


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
        for page in range(1, MAX_PAGES + 1):
            url = (f"{BASE}?search={quote(query)}"
                   f"&filter=publication_year:2021-2026"
                   f"&per_page={PER_PAGE}&page={page}&select={SELECT}")
            body = fetch(url, source="openalex", prov=prov, timeout=90,
                         backoff_s=3.0, note=f"{key} page={page}")
            if body is None:
                break
            doc = json.loads(body)
            if page == 1:
                save_raw(OUT, f"{key}_p1.json", body)
                total = doc["meta"]["count"]
            results = doc.get("results", [])
            if len(results) > PAGE_LIMIT:
                raise AssertionError(f"返回 {len(results)} 条超过声明上限 {PAGE_LIMIT}")
            for w in results:
                wid = w.get("id", "")
                year = w.get("publication_year")
                if not wid or wid in seen or year is None or not 2021 <= year <= 2026:
                    continue
                seen.add(wid)
                topic = (w.get("topics") or [{}])[0].get("display_name", "")
                rows.append([
                    key, wid.rsplit("/", 1)[-1], w.get("doi") or "",
                    (w.get("display_name") or "")[:240], year,
                    w.get("publication_date") or "", w.get("type") or "",
                    w.get("cited_by_count", 0), w.get("language") or "",
                    first_author(w)[:80], venue(w)[:120], topic[:90],
                    bool((w.get("open_access") or {}).get("is_oa")),
                ])
                got += 1
            if len(results) < PER_PAGE:
                break
            time.sleep(1.0)
        metas[key] = {"query": query, "api_total_in_window": total, "rows_kept": got}
        print(f"  -> 窗口内命中 {total}，取回 {got} 条")

    write_csv(OUT / "openalex_works_2021_2026.csv",
              ["topic_key", "openalex_id", "doi", "title", "publication_year",
               "publication_date", "type", "cited_by_count", "language",
               "first_author", "venue", "primary_topic", "is_oa"],
              sorted(rows, key=lambda r: (r[0], -int(r[7]))))
    prov.write()
    write_manifest(OUT, {
        "source": "openalex", "tier": "L3", "license": "open",
        "requires_credential": False,
        "page_limit": PAGE_LIMIT, "per_page": PER_PAGE, "max_pages": MAX_PAGES,
        "mailto_sent": False,
        "mailto_note": "polite pool 自 2026-02 废弃，mailto 被忽略，故不发送",
        "topics": metas, "rows_total": len(rows),
    })
    print(f"[openalex] 合计 {len(rows)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
