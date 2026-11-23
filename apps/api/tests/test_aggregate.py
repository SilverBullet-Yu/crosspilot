"""证据层测试：两票制聚合（ADR-0005 A4、R4 标注冲突≠证据冲突、R6 显式传播）。"""

from __future__ import annotations

import pytest

from crosspilot_api.domain.evidence import Stance, StanceVotes
from crosspilot_api.services.stance_aggregate import aggregate_stance


class TestAggregateStance:
    def test_agreement_produces_stance(self) -> None:
        result = aggregate_stance(StanceVotes(rule=Stance.SUPPORT, llm=Stance.SUPPORT))
        assert result.stance is Stance.SUPPORT
        assert result.annotator_agreement is True

    def test_agreement_on_oppose(self) -> None:
        result = aggregate_stance(StanceVotes(rule=Stance.OPPOSE, llm=Stance.OPPOSE))
        assert result.stance is Stance.OPPOSE
        assert result.annotator_agreement is True

    def test_disagreement_degrades_to_insufficient_not_conflicting(self) -> None:
        """R4 黄金用例：标注器分歧 = 标注不确定性 → insufficient + agreement=False，
        绝不产生证据冲突（conflicting 是 decide 对独立证据的判定，二者不混）。"""
        result = aggregate_stance(StanceVotes(rule=Stance.SUPPORT, llm=Stance.OPPOSE))
        assert result.stance is Stance.INSUFFICIENT
        assert result.annotator_agreement is False

    def test_llm_absent_uses_rule_and_propagates(self) -> None:
        """R6：LLM 缺席（凭据缺省/回退）→ 规则票生效且缺席显式可见（agreement=None）。"""
        result = aggregate_stance(StanceVotes(rule=Stance.OPPOSE, llm=None))
        assert result.stance is Stance.OPPOSE
        assert result.annotator_agreement is None

    def test_no_silent_fallback(self) -> None:
        """缺席与分歧是两种不同状态，禁止合并成同一口径（R6）。"""
        absent = aggregate_stance(StanceVotes(rule=Stance.SUPPORT, llm=None))
        disagree = aggregate_stance(StanceVotes(rule=Stance.SUPPORT, llm=Stance.INSUFFICIENT))
        assert absent.annotator_agreement is None
        assert disagree.annotator_agreement is False
        assert absent.stance is Stance.SUPPORT
        assert disagree.stance is Stance.INSUFFICIENT

    @pytest.mark.parametrize("stance", list(Stance))
    def test_llm_absent_always_returns_rule(self, stance: Stance) -> None:
        assert aggregate_stance(StanceVotes(rule=stance, llm=None)).stance is stance
