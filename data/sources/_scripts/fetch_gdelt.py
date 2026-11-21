"""GDELT DOC 2.0 德语媒体语境抓取（L3，仅标题与链接，无正文）。

实测约束（2026-11-20，本机）：
- TLS 握手慢（9-13s），HTTP 超时须放宽到 90s+。
- 官方说 1 req/5s，实测连续请求仍返回 429；本脚本固定 >=9s 间隔 + 退避重试。
- 单查询上限 250 条；超过须切分时间窗，否则静默截断。
- 长尾德语词（如 Reisetasche）近一月可能零命中，故按季度窗 + 宽品类词检索。
时间窗：2021-2026，按季度切分（DOC 2.0 支持 startdatetime/enddatetime 回溯）。
许可：官方声明可无限制用于学术、商业、政府用途，须署名 The GDELT Project。
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

OUT = Path(__file__).resolve().parents[1] / "gdelt"
BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
PAGE_LIMIT = 250          # 官方单查询上限
# 实测 2026-11-20：官方文档称 1 req/5s，但本机实测 9s、15s、20s 间隔均仍出现 429。
# GDELT 按客户端 IP 做滑动窗口限速，且与同 IP 其他请求共享配额。
# 采用 25s 基础间隔 + 指数退避 + 429 后长休眠；宁慢不丢数据。
SLEEP_S = 25.0
BACKOFF_S = 30.0
COOLDOWN_AFTER_429_S = 75.0
CITATION = "Source: The GDELT Project (https://www.gdeltproject.org/)"

# 宽品类词：长尾德语词零命中，故用品类级德语词 + 德国来源限定。
# 请求数 = QUERIES × 窗口数，受限速约束须节制：2 × 12 = 24 次。
QUERIES = {
    "de_luggage_de_lang": 'Koffer sourcelang:german',
    "en_luggage_de_src": 'luggage sourcecountry:GM',
}


def half_years(start_year: int = 2021, end_year: int = 2026) -> list[tuple[str, str, str]]:
    """生成 (label, startdatetime, enddatetime)，按半年切。

    半年窗而非季度窗：GDELT 限速极严（实测需 25s 间隔），请求数必须压缩。
    长尾德语品类词单季度命中稀疏（实测 Reisetasche 近一月为 0），
    半年窗触及 250 条上限的概率低；一旦触顶会记入 manifest.truncated_windows。
    """
    out: list[tuple[str, str, str]] = []
    for y in range(start_year, end_year + 1):
        out.append((f"{y}H1", f"{y}0101000000", f"{y}0630235959"))
        if y == 2026:
            out.append((f"{y}H2", f"{y}0701000000", f"{y}1120235959"))
        else:
            out.append((f"{y}H2", f"{y}0701000000", f"{y}1231235959"))
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prov = Provenance("gdelt", OUT)
    rows: list[list[object]] = []
    seen: set[str] = set()
    metas: dict[str, dict] = {}
    windows = half_years()
    truncated: list[str] = []
    rate_limited: list[str] = []

    for key, query in QUERIES.items():
        kept = 0
        empty_windows = 0
        print(f"[gdelt] {key}: {query}")
        for label, start, end in windows:
            url = (f"{BASE}?query={quote(query)}&mode=artlist"
                   f"&maxrecords={PAGE_LIMIT}&format=json"
                   f"&startdatetime={start}&enddatetime={end}&sort=datedesc")
            body = fetch(url, source="gdelt", prov=prov, timeout=120,
                         retries=3, backoff_s=BACKOFF_S, note=f"{key} {label}")
            if body is None:
                rate_limited.append(f"{key}/{label}")
                print(f"  [429] {label} 放弃，冷却 {COOLDOWN_AFTER_429_S}s")
                time.sleep(COOLDOWN_AFTER_429_S)
                continue
            text = body.decode("utf-8", "replace").strip()
            if not text.startswith("{"):
                # 限速提示页返回 200 但正文是纯文本告警
                rate_limited.append(f"{key}/{label}")
                time.sleep(COOLDOWN_AFTER_429_S)
                continue
            try:
                arts = json.loads(text).get("articles", [])
            except json.JSONDecodeError:
                continue
            if len(arts) >= PAGE_LIMIT:
                truncated.append(f"{key}/{label}")
            if not arts:
                empty_windows += 1
            else:
                save_raw(OUT, f"{key}_{label}.json", body)
            for a in arts:
                u = a.get("url", "")
                if not u or u in seen:
                    continue
                seen.add(u)
                rows.append([
                    key, query, label, a.get("seendate", ""),
                    (a.get("title") or "")[:240], a.get("domain", ""),
                    a.get("sourcecountry", ""), a.get("language", ""), u, CITATION,
                ])
                kept += 1
            print(f"  {label}: {len(arts)} 条 (累计 {kept})")
            time.sleep(SLEEP_S)
        metas[key] = {"query": query, "rows_kept": kept,
                      "empty_windows": empty_windows, "windows": len(windows)}
        print(f"  -> 取回 {kept} 条（{empty_windows}/{len(windows)} 个半年窗零命中）")

    write_csv(OUT / "gdelt_de_coverage_2021_2026.csv",
              ["query_key", "query", "quarter", "seen_date_utc", "title",
               "domain", "source_country", "language", "url", "citation"],
              sorted(rows, key=lambda r: (r[0], r[3])))
    prov.write()
    write_manifest(OUT, {
        "source": "gdelt_doc", "tier": "L3",
        "license": "unrestricted use with attribution",
        "requires_credential": False, "citation_required": CITATION,
        "page_limit": PAGE_LIMIT, "request_interval_s": SLEEP_S,
        "backoff_s": BACKOFF_S, "cooldown_after_429_s": COOLDOWN_AFTER_429_S,
        "content_scope": "仅标题与链接，不含正文",
        "window_granularity": "half-year",
        "queries": metas, "rows_total": len(rows),
        "truncated_windows": truncated,
        "rate_limited_windows": rate_limited,
    })
    print(f"[gdelt] 合计 {len(rows)} 条；触顶 {len(truncated)} 个；限速丢失 {len(rate_limited)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
