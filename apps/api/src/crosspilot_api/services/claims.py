"""卖点假设的稳定 ID 与展示标签。"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from ..domain.evidence import EvidenceCard

CLAIM_LABELS: dict[str, str] = {
    "capacity": "容量越大越好",
    "features": "功能越多越好",
    "price": "低价是核心购买理由",
}
CLAIM_IDS: tuple[str, ...] = tuple(CLAIM_LABELS)
UNASSIGNED_CLAIM_ID = "unassigned"
_CLAIM_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


def is_valid_claim_id(value: str) -> bool:
    return _CLAIM_ID_RE.fullmatch(value) is not None


def claim_ids_from_cards(cards: Iterable[EvidenceCard]) -> tuple[str, ...]:
    custom = sorted(
        {
            card.claim_id
            for card in cards
            if card.claim_id
            and card.claim_id != UNASSIGNED_CLAIM_ID
            and card.claim_id not in CLAIM_IDS
            and card.relevance == "relevant"
        }
    )
    return (*CLAIM_IDS, *custom)


def select_claim_ids(
    cards: Iterable[EvidenceCard],
    requested: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """选择本次案例活跃卖点；未指定时保留内置三项与卡片自定义 ID。"""
    if not requested:
        return claim_ids_from_cards(cards)
    selected: list[str] = []
    for value in requested:
        claim_id = value.strip()
        if not is_valid_claim_id(claim_id):
            raise ValueError(f"claim_id 非法：{value}")
        if claim_id not in selected:
            selected.append(claim_id)
    return tuple(selected)


_CAPACITY_TERMS = (
    "容量", "尺寸", "便携", "手提行李", "装得下", "臃肿",
    "kapazität", "volumen", "liter", "größe", "handgepäck", "carry-on",
    "sperrig", "bulky", "koffer", "platz", "packen", "klein", "groß", "leicht",
    "gewicht", "space", "luggage", "carry on", "packed",
)
_FEATURE_TERMS = (
    "隔层", "分区", "拉链", "功能", "分层", "口袋",
    "fach", "fächer", " compartment", "pocket", "zip", "organizer",
    "reißverschluss", "reissverschluss", "innentasche", "sortiert", "ordnung",
    "verstaut", "hineinschauen", "beschriftung", "mesh", "netz",
    "würfel", "kabel", "kosmetik", "wäsche",
)
_PRICE_TERMS = (
    "价格", "低价", "便宜", "性价比", "耐用", "材质", "退换",
    "preis", "günstig", "billig", "preiswert", "price", "cheap",
    "quality", "qualität", "material", "durable", "warranty", "retoure",
    "nähte", "naht", "abnutzung", "stoff", "form", "verarbeitung", "stabil",
)


def claim_aspect_terms(claim_id: str) -> tuple[str, ...]:
    """返回内置卖点的术语表；自定义卖点没有词典时必须回退整条规则票。"""
    return {
        "capacity": _CAPACITY_TERMS,
        "features": _FEATURE_TERMS,
        "price": _PRICE_TERMS,
    }.get(claim_id, ())


def infer_claim_id(text: str) -> str | None:
    """为旧快照和演示卡补充卖点归属；新数据须显式归属或标记为未归属。"""
    lowered = text.casefold()
    for claim_id in CLAIM_IDS:
        if any(term.casefold() in lowered for term in claim_aspect_terms(claim_id)):
            return claim_id
    return None
