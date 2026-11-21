"""EU Safety Gate (RAPEX) 德国相关警报抓取（L3 监管端信号）。

链路：周报索引 XML -> 按 publicationDate 过滤 2021-2026 -> 逐期明细 XML。
实测要点：
- 明细 URL 必须带索引给出的 search=WEB_REPORT|:|{id} 参数，否则 400。
- 索引里的链接是 HTML 转义的（&amp;），取用前须 unescape，且尾部带逗号。
许可：周报 XML 分发在 data.europa.eu 标注 CC0 1.0。无需 key。
"""

from __future__ import annotations

import html
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    WINDOW_YEARS,
    Provenance,
    fetch,
    save_raw,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "eu_safety_gate"
INDEX = "https://ec.europa.eu/safety-gate-alerts/api/download/weeklyReport/list/xml/en"
# 德国相关：通报国为德国，或原产国为德国，或德国在措施/描述中出现
DE_KEYS = ("Germany",)
# 目标品类（旅行收纳包场景的近邻品类）
FOCUS_CATEGORIES = (
    "Childcare articles and children's equipment",
    "Clothing, textiles and fashion items",
    "Sports equipment",
    "Toys",
    "Chemical products",
)
# 个人数据清洗：剔除邮箱、电话
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){7,14}\d(?!\d)")


def scrub(text: str) -> str:
    text = RE_EMAIL.sub("[email-removed]", text)
    return RE_PHONE.sub("[phone-removed]", text)


def txt(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return " ".join(node.text.split())


def parse_index(body: bytes) -> list[tuple[str, str, str, str]]:
    """返回 (report_id, publication_date, url, reference)，仅 2021-2026。"""
    root = ET.fromstring(body)
    out: list[tuple[str, str, str, str]] = []
    for rep in root.iter():
        if not rep.tag.endswith("weeklyReport"):
            continue
        year = txt(rep.find("year"))
        if year not in WINDOW_YEARS:
            continue
        url = html.unescape(txt(rep.find("URL"))).rstrip(",")
        ref = txt(rep.find("reference"))
        pub = txt(rep.find("publicationDate")) or f"{year}-W{txt(rep.find('week'))}"
        rid = re.search(r"/(\d+)\?", url)
        out.append((rid.group(1) if rid else ref, pub, url, ref))
    return out


def parse_report(body: bytes, ref: str, pub: str) -> list[list[object]]:
    """解析单期周报。注意元素名是 <notifications>（复数），每个代表一条警报。"""
    root = ET.fromstring(body)
    rows: list[list[object]] = []
    for note in root.iter("notifications"):

        def get(tag: str, _n: ET.Element = note) -> str:
            # 默认参数绑定当前 note，避免闭包捕获循环变量（ruff B023）
            return txt(_n.find(tag))

        notifying = get("notifyingCountry")
        origin = get("countryOfOrigin")
        blob = ET.tostring(note, encoding="unicode")
        if not any(k in blob for k in DE_KEYS):
            continue
        rows.append([
            get("caseNumber") or get("reference"), ref, pub,
            get("category"), get("product"), get("name"), get("brand"),
            get("barcode"), get("riskType"), get("level"),
            scrub(get("danger"))[:600], scrub(get("measures"))[:400],
            notifying, origin,
            "notifying" if notifying == "Germany" else ("origin" if origin == "Germany" else "mentioned"),
        ])
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prov = Provenance("eu_safety_gate", OUT)

    print("[safety_gate] 取周报索引")
    body = fetch(INDEX, source="eu_safety_gate", prov=prov, timeout=180, note="index")
    if body is None:
        print("[safety_gate] 索引不可达，中止")
        return 1
    save_raw(OUT, "weekly_report_index.xml", body)

    reports = parse_index(body)
    print(f"[safety_gate] 窗口内周报 {len(reports)} 期")

    rows: list[list[object]] = []
    fetched = failed = 0
    for i, (rid, pub, url, ref) in enumerate(reports, 1):
        rb = fetch(url, source="eu_safety_gate", prov=prov, timeout=180,
                   retries=2, backoff_s=5.0, note=f"report {ref}")
        if rb is None:
            failed += 1
            continue
        fetched += 1
        save_raw(OUT, f"report_{rid}.xml", rb)
        got = parse_report(rb, ref, pub)
        rows.extend(got)
        if i % 20 == 0 or i == len(reports):
            print(f"  {i}/{len(reports)} 期 | 德国相关累计 {len(rows)} 条")
        time.sleep(1.2)

    write_csv(OUT / "safety_gate_de_alerts_2021_2026.csv",
              ["case_number", "report_reference", "publication_date", "category",
               "product", "product_name", "brand", "barcode", "risk_type",
               "risk_level", "danger", "measures", "notifying_country",
               "country_of_origin", "de_relation"],
              rows)
    prov.write()
    write_manifest(OUT, {
        "source": "eu_safety_gate", "tier": "L3", "license": "CC0-1.0",
        "requires_credential": False,
        "reports_in_window": len(reports), "reports_fetched": fetched,
        "reports_failed": failed, "de_rows": len(rows),
        "focus_categories_reference": list(FOCUS_CATEGORIES),
        "pii_scrubbed": ["email", "phone"],
    })
    print(f"[safety_gate] 完成：{fetched} 期，德国相关 {len(rows)} 条，失败 {failed} 期")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
