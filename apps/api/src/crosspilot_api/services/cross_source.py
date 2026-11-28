"""把 L1 消费者反馈、L2 从业经验与 L3 语境转成可追溯的待验证问题。"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.evidence import Decision, EvidenceCard
from .claims import CLAIM_IDS, CLAIM_LABELS


@dataclass(frozen=True)
class CrossSourceComparison:
    claim_id: str
    label: str
    status: str
    l1_state: str
    l1_total: int
    l1_polarized: int
    l1_support: int
    l1_oppose: int
    l1_insufficient: int
    l2_total: int
    l1_refs: tuple[str, ...]
    l2_refs: tuple[str, ...]
    question: str


def _sources(cards: list[EvidenceCard]) -> str:
    urls = list(dict.fromkeys(card.source_url for card in cards))
    return "；".join(urls[:2]) or "未提供"


def _refs(cards: list[EvidenceCard]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        f"{card.review_id or card.source_url}: {card.source_url}"
        for card in cards
    ))


def _refs_source(label: str, refs: tuple[str, ...]) -> str:
    return f"{label}: {'；'.join(refs[:2]) or '未提供'}"


def build_cross_source_comparisons(
    *,
    l1_cards: list[EvidenceCard],
    l2_cards: list[EvidenceCard],
    claim_decisions: dict[str, Decision],
    claim_ids: tuple[str, ...] = CLAIM_IDS,
) -> list[CrossSourceComparison]:
    """按卖点分别保存 L1/L2 出处与样本分布，不自动推断 L2 的消费者立场。"""
    comparisons: list[CrossSourceComparison] = []
    for claim_id in claim_ids:
        claim_l1 = [
            card
            for card in l1_cards
            if card.claim_id == claim_id
            and card.relevance == "relevant"
            and (card.dedup is None or card.dedup.is_canonical)
        ]
        claim_l2 = [card for card in l2_cards if card.claim_id == claim_id]
        decision = claim_decisions.get(claim_id)
        if decision is None or not claim_l1 and not claim_l2:
            continue
        label = CLAIM_LABELS.get(claim_id, claim_id)
        support = sum(card.stance == "support" for card in claim_l1)
        oppose = sum(card.stance == "oppose" for card in claim_l1)
        insufficient = sum(card.stance == "insufficient" for card in claim_l1)
        state = decision.state.value
        l1_refs = _refs(claim_l1)
        l2_refs = _refs(claim_l2)

        if claim_l1 and claim_l2:
            counts = f"支持 {support} 条、反对 {oppose} 条"
            if state == "conflicting":
                status = "mixed_scenarios"
                question = (
                    f"（跨来源待验证）「{label}」当前消费者样本{counts}，判定为 "
                    f"conflicting；L2 有 {len(claim_l2)} 条从业经验。请按装什么、怎么取、"
                    "尺寸与使用场景分组回看双方原文，找出分歧条件，不把 L2 当消费者票。"
                )
            elif state == "refuted":
                status = "potential_divergence"
                question = (
                    f"（跨来源待验证）「{label}」当前消费者样本{counts}，多数反馈反对；"
                    f"L2 有 {len(claim_l2)} 条相关从业经验。请核对市场、商品形态、使用场景"
                    "与样本偏差，找出两类来源可能分歧的原因。"
                )
            elif state == "supported":
                status = "compare_scenarios"
                question = (
                    f"（跨来源待验证）「{label}」当前消费者样本{counts}，仅为样本内有限支持；"
                    f"L2 有 {len(claim_l2)} 条相关从业经验。请核对双方是否描述同一使用场景，"
                    "并主动寻找反例；L2 不增加 L1 样本量。"
                )
            else:
                status = "compare_scenarios"
                question = (
                    f"（跨来源待验证）「{label}」当前消费者样本{counts}，但尚未过样本门禁；"
                    f"L2 有 {len(claim_l2)} 条从业经验。请先补样，并按使用场景核对两类来源，"
                    "不把从业经验当作消费者偏好证据。"
                )
        elif claim_l2:
            status = "needs_l1"
            question = (
                f"（跨来源待验证）知乎经验涉及「{label}」，但目标市场消费者样本不足。"
                "请访谈确认该经验是否适用于本站买家，再用真实评论复核。"
            )
        else:
            status = "needs_l2"
            question = (
                f"（待验证假设）「{label}」已有消费者评论，但缺少可对照的从业经验。"
                "请补充卖家或用户研究访谈，检查样本是否遗漏关键使用场景。"
            )

        comparisons.append(
            CrossSourceComparison(
                claim_id=claim_id,
                label=label,
                status=status,
                l1_state=state,
                l1_total=len(claim_l1),
                l1_polarized=support + oppose,
                l1_support=support,
                l1_oppose=oppose,
                l1_insufficient=insufficient,
                l2_total=len(claim_l2),
                l1_refs=l1_refs,
                l2_refs=l2_refs,
                question=question,
            )
        )
    return comparisons


def build_evidence_questions(
    *,
    query: str,
    l1_cards: list[EvidenceCard],
    l2_cards: list[EvidenceCard],
    l3_cards: list[EvidenceCard],
    claim_decisions: dict[str, Decision],
    claim_ids: tuple[str, ...] = CLAIM_IDS,
    comparisons: list[CrossSourceComparison] | None = None,
) -> list[dict[str, str]]:
    """跨来源问题只提出待验证假设，不把 L2/L3 混入偏好判定。"""
    if comparisons is None:
        comparisons = build_cross_source_comparisons(
            l1_cards=l1_cards,
            l2_cards=l2_cards,
            claim_decisions=claim_decisions,
            claim_ids=claim_ids,
        )
    questions: list[dict[str, str]] = []
    for comparison in comparisons:
        source_parts = []
        if comparison.l1_refs:
            source_parts.append(_refs_source("L1", comparison.l1_refs))
        if comparison.l2_refs:
            source_parts.append(_refs_source("L2", comparison.l2_refs))
        questions.append(
            {
                "text": comparison.question,
                "source": "; ".join(source_parts) or "数据状态：来源缺失",
            }
        )

    if l3_cards:
        questions.append(
            {
                "text": (
                    f"（推断/待验证假设）「{query or '当前产品'}」命中 {len(l3_cards)} 条 L3 "
                    "监管语境。请验证这些风险是否也是德国买家的实际购买顾虑；L3 不参与偏好判定。"
                ),
                "source": f"L3: {_sources(l3_cards)}",
            }
        )
    if not any(
        card.claim_id in claim_ids and card.relevance == "relevant" for card in l1_cards
    ):
        questions.append(
            {
                "text": (
                    "（待验证/证据缺口）当前没有可归属到卖点假设的德国 L1 评论。"
                    "请先完成卖点归属或导入品牌授权评论，再解释消费者偏好。"
                ),
                "source": "数据状态：德国 L1 未归属或零样本",
            }
        )
    return questions
