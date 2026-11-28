from __future__ import annotations

from dataclasses import replace
from datetime import date

from crosspilot_api.domain.evidence import EvidenceCard, EvidenceLevel, Stance, decide_by_claim
from crosspilot_api.services.claims import CLAIM_IDS
from crosspilot_api.services.cross_source import (
    build_cross_source_comparisons,
    build_evidence_questions,
)
from crosspilot_api.services.evidence_dedup import DedupInfo


def _card(excerpt: str, stance: Stance, *, dedup: DedupInfo) -> EvidenceCard:
    return EvidenceCard(
        excerpt=excerpt,
        source_url="https://example.com/review",
        language="de",
        published_on=date(2026, 1, 1),
        level=EvidenceLevel.L1,
        sample_size=1,
        stance=stance,
        claim_id="capacity",
        dedup=dedup,
    )


def test_cross_source_counts_only_canonical_clusters() -> None:
    cards = [
        _card("Sehr gut!", Stance.SUPPORT, dedup=DedupInfo(0, 2, True)),
        _card("Sehr gut!", Stance.SUPPORT, dedup=DedupInfo(0, 2, False)),
    ]
    l2 = EvidenceCard(
        excerpt="模拟从业经验",
        source_url="https://example.com/l2",
        language="zh-CN",
        published_on=date(2026, 1, 2),
        level=EvidenceLevel.L2,
        sample_size=1,
        claim_id="capacity",
    )
    questions = build_evidence_questions(
        query="旅行收纳包",
        l1_cards=cards,
        l2_cards=[l2],
        l3_cards=[],
        claim_decisions=decide_by_claim(cards, CLAIM_IDS),
    )
    question = questions[0]
    assert "支持 1 条、反对 0 条" in question["text"]
    assert "L1:" in question["source"] and "L2:" in question["source"]

    unassigned = replace(cards[0], claim_id="unassigned")
    gap_questions = build_evidence_questions(
        query="旅行收纳包",
        l1_cards=[unassigned],
        l2_cards=[],
        l3_cards=[],
        claim_decisions=decide_by_claim([unassigned], CLAIM_IDS),
    )
    assert any("未归属或零样本" in question["source"] for question in gap_questions)


def test_cross_source_supports_custom_claim_ids() -> None:
    custom = replace(
        _card("Wasserdicht und sehr praktisch.", Stance.SUPPORT, dedup=DedupInfo(0, 1, True)),
        claim_id="custom-waterproof",
    )
    questions = build_evidence_questions(
        query="旅行收纳包",
        l1_cards=[custom],
        l2_cards=[],
        l3_cards=[],
        claim_decisions=decide_by_claim([custom], ("custom-waterproof",)),
        claim_ids=("custom-waterproof",),
    )
    assert any("custom-waterproof" in question["text"] for question in questions)
    assert not any("未归属或零样本" in question["source"] for question in questions)


def test_comparison_preserves_both_source_layers() -> None:
    cards = [
        replace(
            _card("Sehr gut!", Stance.SUPPORT, dedup=DedupInfo(0, 1, True)),
            review_id="review-1",
            source_url="https://example.com/review-1",
        )
    ]
    l2 = EvidenceCard(
        excerpt="模拟从业经验",
        source_url="https://example.com/l2",
        language="zh-CN",
        published_on=date(2026, 1, 2),
        level=EvidenceLevel.L2,
        sample_size=1,
        claim_id="capacity",
    )
    comparisons = build_cross_source_comparisons(
        l1_cards=cards,
        l2_cards=[l2],
        claim_decisions=decide_by_claim(cards, ("capacity",)),
        claim_ids=("capacity",),
    )
    comparison = comparisons[0]
    assert comparison.status == "compare_scenarios"
    assert comparison.l1_support == 1
    assert comparison.l1_oppose == 0
    assert comparison.l1_refs == ("review-1: https://example.com/review-1",)
    assert comparison.l2_refs == ("https://example.com/l2: https://example.com/l2",)
    assert "L2 不增加 L1 样本量" not in comparison.question


def test_mixed_l1_sample_asks_for_scenario_comparison() -> None:
    cards = [
        replace(
            _card(
                f"Review {index}",
                Stance.SUPPORT if index < 15 else Stance.OPPOSE,
                dedup=DedupInfo(index, 1, True),
            ),
            review_id=f"review-{index}",
            source_url=f"https://example.com/review-{index}",
        )
        for index in range(30)
    ]
    l2 = EvidenceCard(
        excerpt="模拟从业经验",
        source_url="https://example.com/l2",
        language="zh-CN",
        published_on=date(2026, 1, 2),
        level=EvidenceLevel.L2,
        sample_size=1,
        claim_id="capacity",
    )
    comparison = build_cross_source_comparisons(
        l1_cards=cards,
        l2_cards=[l2],
        claim_decisions=decide_by_claim(cards, ("capacity",)),
        claim_ids=("capacity",),
    )[0]
    assert comparison.status == "mixed_scenarios"
    assert comparison.l1_state == "conflicting"
    assert comparison.l1_support == 15
    assert comparison.l1_oppose == 15
    assert "按装什么、怎么取" in comparison.question
    assert "不把 L2 当消费者票" in comparison.question


def test_refuted_l1_with_l2_is_potential_divergence_not_conclusion() -> None:
    cards = [
        replace(
            _card(f"Review {index}", Stance.OPPOSE, dedup=DedupInfo(index, 1, True)),
            review_id=f"review-{index}",
            source_url=f"https://example.com/review-{index}",
        )
        for index in range(30)
    ]
    l2 = EvidenceCard(
        excerpt="模拟从业经验",
        source_url="https://example.com/l2",
        language="zh-CN",
        published_on=date(2026, 1, 2),
        level=EvidenceLevel.L2,
        sample_size=1,
        claim_id="capacity",
    )
    comparison = build_cross_source_comparisons(
        l1_cards=cards,
        l2_cards=[l2],
        claim_decisions=decide_by_claim(cards, ("capacity",)),
        claim_ids=("capacity",),
    )[0]
    assert comparison.status == "potential_divergence"
    assert "可能分歧的原因" in comparison.question
    assert "L2 有" in comparison.question


def test_comparison_marks_missing_source_layer() -> None:
    card = _card("Sehr gut!", Stance.SUPPORT, dedup=DedupInfo(0, 1, True))
    only_l1 = build_cross_source_comparisons(
        l1_cards=[card],
        l2_cards=[],
        claim_decisions=decide_by_claim([card], ("capacity",)),
        claim_ids=("capacity",),
    )[0]
    assert only_l1.status == "needs_l2"
    assert only_l1.l2_refs == ()

    only_l2 = build_cross_source_comparisons(
        l1_cards=[],
        l2_cards=[replace(card, level=EvidenceLevel.L2, language="zh-CN")],
        claim_decisions=decide_by_claim([], ("capacity",)),
        claim_ids=("capacity",),
    )[0]
    assert only_l2.status == "needs_l1"
    assert only_l2.l1_refs == ()
