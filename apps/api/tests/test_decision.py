"""判定状态机黄金用例（ADR-0005 决策 6 落点 5：R4 区分显式覆盖）。

覆盖四值映射边界、R2 去重先于计数的端到端效果、R4 标注冲突≠证据冲突、
硬约束 1（L2/L3 不进判定）与「L2 不改变结论」的对抗断言。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from itertools import count

import pytest

from crosspilot_api.domain.evidence import (
    DecisionState,
    EvidenceCard,
    EvidenceLevel,
    GateStatus,
    Stance,
    decide,
    decide_by_claim,
)

#: 卡文本全局序号：批量构造时每卡措辞唯一，避免被去重管道聚簇（R2 生效的证据）
_CARD_SEQ = count()
_ADJ = (
    "robust", "schön", "praktisch", "leicht", "schwer", "teuer", "günstig", "groß",
    "klein", "neu", "stabil", "eng", "dicht", "weich", "hart", "alt", "frisch",
    "schlank", "breit", "fest", "matt", "glatt", "bunt", "hell", "dunkel", "warm",
    "kühl", "trocken", "feucht", "klar", "dauerhaft", "kaputt", "kompakt", "voluminös",
    "schlau", "einfach", "doppelt", "lässig", "edel", "schlicht", "bunt", "krause",
    "widerstandsfähig", "flexibel", "steif", "faltbar", "reißfest", "wasserabweisend",
    "leichtgängig", "freundlich", "preiswert", "hochwertig", "unauffällig", "dezent",
    "großzügig", "knapp", "geräumig", "solide", "zierlich", "praizise", "schmiegsam",
)


def _unique_excerpt(seq: int) -> str:
    """词组合互异的占位摘录（骨架模板会被精确 Jaccard 聚簇——R2 对测试同样生效）。

    60 词表 × 4 个互质大步长伪随机组合：相邻文本 4 个词位全变、骨架 gram 占比低，
    任意两条 Jaccard 远低于 0.85；组合空间 60⁴，200 条内无碰撞。
    """
    a = _ADJ[(seq * 31 + 7) % len(_ADJ)]
    b = _ADJ[(seq * 17 + 11) % len(_ADJ)]
    c = _ADJ[(seq * 23 + 19) % len(_ADJ)]
    d = _ADJ[(seq * 29 + 41) % len(_ADJ)]
    return f"{a} Beutel für {b} und {c}, {d} im Detail, im Praxistest {seq}."


def _card(
    stance: Stance,
    level: EvidenceLevel = EvidenceLevel.L1,
    excerpt: str | None = None,
) -> EvidenceCard:
    return EvidenceCard(
        excerpt=excerpt or _unique_excerpt(next(_CARD_SEQ)),
        source_url="https://example.com/review",
        language="de",
        published_on=date(2023, 6, 1),
        level=level,
        sample_size=1,
        stance=stance,
        is_demo_data=True,
    )


def _l1_batch(k_support: int, k_oppose: int, k_insufficient: int = 0) -> list[EvidenceCard]:
    cards = [_card(Stance.SUPPORT) for _ in range(k_support)]
    cards += [_card(Stance.OPPOSE) for _ in range(k_oppose)]
    cards += [_card(Stance.INSUFFICIENT) for _ in range(k_insufficient)]
    return cards


class TestDecisionStates:
    def test_no_l1_is_insufficient(self) -> None:
        """硬约束 1：仅 L2/L3 → gate=no_l1（无论数量多少）。"""
        cards = [_card(Stance.SUPPORT, EvidenceLevel.L3) for _ in range(100)]
        cards += [_card(Stance.OPPOSE, EvidenceLevel.L2) for _ in range(100)]
        decision = decide(cards)
        assert decision.state is DecisionState.INSUFFICIENT
        assert decision.gate_status is GateStatus.NO_L1
        assert decision.support_interval is None

    def test_below_minimum_forces_insufficient(self) -> None:
        """门禁：n=1 的单条 support 卡不再判 support（ADR-0005 行为变更核心）。"""
        decision = decide([_card(Stance.SUPPORT)])
        assert decision.state is DecisionState.INSUFFICIENT
        assert decision.gate_status is GateStatus.BELOW_MINIMUM
        assert decision.n_polarized == 1

    def test_opposite_stances_are_not_deduplicated(self) -> None:
        text = "Die Tasche ist sehr gut und praktisch."
        decision = decide([
            _card(Stance.SUPPORT, excerpt=text),
            _card(Stance.OPPOSE, excerpt=text),
        ])
        assert decision.n_polarized == 2
        assert decision.dedup_clusters == 2
        assert decision.dedup_duplicated == 0
        assert all(info is not None and info.is_canonical for info in decision.dedup_by_card)

    def test_21_9_is_supported(self) -> None:
        decision = decide(_l1_batch(21, 9))
        assert decision.state is DecisionState.SUPPORTED
        assert decision.gate_status is GateStatus.PASS
        assert decision.support_interval is not None
        assert decision.support_interval is not None
        assert decision.support_interval.lo == pytest.approx(0.521, abs=1e-3)

    def test_20_10_is_conflicting(self) -> None:
        """对抗审查 C3 关键用例：2:1 主导仍判 conflicting（反对侧上界 0.512 无法排除过半）。"""
        decision = decide(_l1_batch(20, 10))
        assert decision.state is DecisionState.CONFLICTING

    def test_15_15_is_conflicting(self) -> None:
        decision = decide(_l1_batch(15, 15))
        assert decision.state is DecisionState.CONFLICTING

    def test_0_30_is_refuted(self) -> None:
        decision = decide(_l1_batch(0, 30))
        assert decision.state is DecisionState.REFUTED

    def test_30_0_is_supported(self) -> None:
        decision = decide(_l1_batch(30, 0))
        assert decision.state is DecisionState.SUPPORTED

    def test_all_insufficient_cards(self) -> None:
        """全部无极性信号：gate=no_polarized、区间 None。"""
        decision = decide(_l1_batch(0, 0, 40))
        assert decision.state is DecisionState.INSUFFICIENT
        assert decision.gate_status is GateStatus.NO_POLARIZED
        assert decision.support_interval is None
        assert decision.n_insufficient == 40


class TestDedupBeforeCount:
    def test_duplicates_do_not_inflate_evidence(self) -> None:
        """R2 端到端黄金用例：同一条评论复制 30 次 ≠ 30 条独立证据。

        去重后 1 簇 → n_polarized=1 → 门禁拦下 → insufficient（不是 supported）。
        """
        text = "Der Reißverschluss des größten Würfels ist nach drei Wochen schwergängig."
        cards = [
            _card(Stance.SUPPORT, excerpt=text) for _ in range(30)
        ]
        decision = decide(cards)
        assert decision.dedup_clusters == 1
        assert decision.dedup_duplicated == 29
        assert decision.n_polarized == 1
        assert decision.state is DecisionState.INSUFFICIENT
        assert decision.gate_status is GateStatus.BELOW_MINIMUM

    def test_template_variants_do_not_inflate_evidence(self) -> None:
        """模板变体（刷评常见形态：逐字复制 + 改 1 词）同样被聚簇。"""
        base = (
            "Der Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach zwei Tagen Lüften nicht neutral."
        )
        variant = (
            "Der Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach 2 Tagen Lüften nicht neutral."
        )
        cards = [
            _card(Stance.SUPPORT, excerpt=base),
            _card(Stance.SUPPORT, excerpt=variant),
            *[_card(Stance.SUPPORT) for _ in range(28)],
        ]
        decision = decide(cards)
        assert decision.dedup_duplicated == 1
        assert decision.n_polarized == 29  # 变体并入 base 簇，不计双份

    def test_dedup_by_card_aligned_with_input(self) -> None:
        """dedup_by_card 与输入等长对齐：L1 位有值、L2/L3 位 None（卡面回填依据）。"""
        cards = [
            _card(Stance.SUPPORT, EvidenceLevel.L3),
            _card(Stance.SUPPORT),
            _card(Stance.OPPOSE),
        ]
        decision = decide(cards)
        assert decision.dedup_by_card[0] is None
        assert decision.dedup_by_card[1] is not None
        assert decision.dedup_by_card[2] is not None
        assert decision.dedup_by_card[1].is_canonical is True  # type: ignore[union-attr]
        assert decision.dedup_by_card[2].is_canonical is True  # type: ignore[union-attr]


class TestHardConstraintOne:
    def test_l2_cards_never_change_conclusion(self) -> None:
        """对抗断言（STATUS 包络纪律同源）：追加任意数量 L2/L3 卡，判定逐字段不变。"""
        base = _l1_batch(21, 9)
        polluted = [
            *base,
            *[_card(Stance.SUPPORT, EvidenceLevel.L2) for _ in range(50)],
            *[_card(Stance.OPPOSE, EvidenceLevel.L3) for _ in range(50)],
        ]
        clean = decide(base)
        dirty = decide(polluted)
        assert dirty.state is clean.state
        assert dirty.gate_status is clean.gate_status
        assert dirty.n_polarized == clean.n_polarized
        assert dirty.support_interval == clean.support_interval

    def test_insufficient_cards_do_not_enter_interval_denominator(self) -> None:
        """对抗审查 C4 口径：insufficient 卡单独报告，不进分母。"""
        decision = decide(_l1_batch(21, 9, k_insufficient=10))
        assert decision.n_polarized == 30  # 分母只含 support+oppose
        assert decision.n_insufficient == 10
        assert decision.state is DecisionState.SUPPORTED  # 21:9 判定不受影响


class TestTraceability:
    def test_decision_carries_audit_data(self) -> None:
        """判定全链路可追溯：区间/样本量/去重摘要/功效注记齐备。"""
        decision = decide(_l1_batch(21, 9))
        assert decision.support_interval is not None
        assert decision.oppose_interval is not None
        assert decision.power_note
        assert decision.n_total == 30
        assert decision.n_l1 == 30
        assert decision.dedup_clusters == 30


class TestClaimDecisions:
    def test_decisions_are_isolated_by_claim(self) -> None:
        capacity = [replace(_card(Stance.SUPPORT), claim_id="capacity") for _ in range(30)]
        price = [replace(_card(Stance.OPPOSE), claim_id="price") for _ in range(30)]
        decisions = decide_by_claim(capacity + price, ("capacity", "features", "price"))
        assert decisions["capacity"].state is DecisionState.SUPPORTED
        assert decisions["price"].state is DecisionState.REFUTED
        assert decisions["features"].gate_status is GateStatus.NO_L1

    def test_unassigned_cards_do_not_enter_claim_decision(self) -> None:
        cards = [replace(_card(Stance.SUPPORT), claim_id="capacity") for _ in range(30)]
        cards += [_card(Stance.OPPOSE) for _ in range(30)]
        decisions = decide_by_claim(cards, ("capacity",))
        assert decisions["capacity"].state is DecisionState.SUPPORTED
        assert decisions["capacity"].n_total == 30

    def test_repeated_short_comments_do_not_pass_gate(self) -> None:
        cards = [
            replace(_card(Stance.SUPPORT, excerpt="Sehr gut!"), claim_id="capacity")
            for _ in range(30)
        ]
        decision = decide_by_claim(cards, ("capacity",))["capacity"]
        assert decision.state is DecisionState.INSUFFICIENT
        assert decision.n_polarized == 1
        assert decision.dedup_duplicated == 29
