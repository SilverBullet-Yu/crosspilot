"""补齐 Safety Gate 缺失周报：只抓 raw/ 里尚未存在的期次。

与 fetch_safety_gate.py 的区别：跳过已下载期次，可反复运行直至 coverage_complete。
完成后调用 rebuild_from_raw 重建主表。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Provenance, fetch, save_raw
from fetch_safety_gate import INDEX, parse_index

OUT = Path(__file__).resolve().parents[1] / "eu_safety_gate"


def main() -> int:
    raw = OUT / "raw"
    index_file = raw / "weekly_report_index.xml"
    prov = Provenance("eu_safety_gate_resume", OUT)

    if index_file.exists():
        body = index_file.read_bytes()
        print("[resume] 复用本地索引")
    else:
        body = fetch(INDEX, source="eu_safety_gate", prov=prov, timeout=180)
        if body is None:
            return 1
        save_raw(OUT, "weekly_report_index.xml", body)

    reports = parse_index(body)
    missing = [(rid, pub, url, ref) for rid, pub, url, ref in reports
               if not (raw / f"report_{rid}.xml").exists()]
    print(f"[resume] 窗口内 {len(reports)} 期，缺 {len(missing)} 期")

    ok = fail = 0
    for i, (rid, _pub, url, ref) in enumerate(missing, 1):
        rb = fetch(url, source="eu_safety_gate", prov=prov, timeout=180,
                   retries=3, backoff_s=6.0, note=f"resume {ref}")
        if rb is None:
            fail += 1
        else:
            save_raw(OUT, f"report_{rid}.xml", rb)
            ok += 1
        if i % 10 == 0 or i == len(missing):
            print(f"  {i}/{len(missing)} | 成功 {ok} 失败 {fail}")
        time.sleep(1.5)

    # 单独写 resume 留痕，避免覆盖首轮抓取的 provenance.csv
    import csv as _csv

    prov_path = OUT / "provenance_resume.csv"
    with prov_path.open("w", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh)
        w.writerow(["source", "url", "http_status", "bytes", "elapsed_s",
                    "sha256", "fetched_at_utc", "note"])
        for c in prov.calls:
            w.writerow([c.source, c.url, c.http_status, c.bytes_len,
                        f"{c.elapsed_s:.2f}", c.sha256, c.fetched_at, c.note])
    print(f"[resume] 补齐完成：成功 {ok}，失败 {fail}；留痕 {prov_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
