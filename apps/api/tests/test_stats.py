"""统计层测试：Wilson 区间、门禁、决定份额（ADR-0005 A2 边界用例锁定）。

边界用例（n=30，ADR-0005 对抗审查 C3 修正后口径）：
- 21:9 → 支持份额 0.7 的 95% 下界 0.521 > 0.5 → 决定性支持；
- 20:10 → 两份额区间重叠（0.488 ≤ 0.512）→ conflicting（2:1 主导仍难分高下
  是公式的诚实输出——反对侧 95% 上界无法排除过半）；
- 15:15 → 区间重合 → conflicting；
- 30:0 / 0:30 → 决定性 supported / refuted。
"""

from __future__ import annotations

import pytest

from crosspilot_api.services.stats import (
    MIN_POLARIZED_SAMPLE,
    WilsonInterval,
    below_minimum,
    decisive_share,
    intervals_overlap,
    power_note,
    wilson_interval,
)


class TestWilsonInterval:
    def test_21_of_30_lower_bound_crosses_half(self) -> None:
        """21:30（p̂=0.7）：下界 0.521、上界 0.833，刚过决定线。"""
        interval = wilson_interval(21, 30)
        assert interval.n == 30
        assert interval.lo == pytest.approx(0.521, abs=1e-3)
        assert interval.hi == pytest.approx(0.833, abs=1e-3)

    def test_15_of_30_interval(self) -> None:
        interval = wilson_interval(15, 30)
        assert interval.lo == pytest.approx(0.331, abs=1e-3)
        assert interval.hi == pytest.approx(0.669, abs=1e-3)

    def test_9_of_30_interval(self) -> None:
        interval = wilson_interval(9, 30)
        assert interval.lo == pytest.approx(0.167, abs=1e-3)
        assert interval.hi == pytest.approx(0.479, abs=1e-3)

    def test_all_support_lower_bound_far_above_half(self) -> None:
        interval = wilson_interval(30, 30)
        assert interval.lo > 0.85
        assert interval.hi <= 1.0

    def test_zero_hits_lower_bound_is_zero(self) -> None:
        interval = wilson_interval(0, 30)
        assert interval.lo == 0.0
        assert interval.hi < 0.2

    def test_degenerate_zero_denominator(self) -> None:
        interval = wilson_interval(0, 0)
        assert interval == WilsonInterval(lo=0.0, hi=0.0, n=0)

    def test_interval_is_ordered(self) -> None:
        for k in range(0, 31):
            interval = wilson_interval(k, 30)
            assert 0.0 <= interval.lo <= interval.hi <= 1.0


class TestOverlap:
    def test_15_15_intervals_overlap(self) -> None:
        assert intervals_overlap(wilson_interval(15, 30), wilson_interval(15, 30)) is True

    def test_20_10_intervals_overlap(self) -> None:
        """20:10（对抗审查 C3 关键用例）：支持下界 0.488 ≤ 反对上界 0.512 → 重叠。"""
        support = wilson_interval(20, 30)
        oppose = wilson_interval(10, 30)
        assert support.lo == pytest.approx(0.488, abs=1e-3)
        assert oppose.hi == pytest.approx(0.512, abs=1e-3)
        assert intervals_overlap(support, oppose) is True

    def test_21_9_intervals_disjoint(self) -> None:
        """21:9：支持下界 0.521 > 反对上界 0.479 → 分离 → 不冲突。"""
        support = wilson_interval(21, 30)
        oppose = wilson_interval(9, 30)
        assert intervals_overlap(support, oppose) is False


class TestGate:
    def test_below_minimum(self) -> None:
        assert below_minimum(MIN_POLARIZED_SAMPLE - 1) is True
        assert below_minimum(MIN_POLARIZED_SAMPLE) is False

    def test_decisive_share_at_30(self) -> None:
        """n=30 时决定线约 0.68：20/30（0.667）判不了多数，21/30（0.7）能。"""
        share = decisive_share(30)
        assert share == pytest.approx(0.678, abs=0.01)
        assert 20 / 30 < share <= 21 / 30

    def test_decisive_share_falls_as_n_grows(self) -> None:
        assert decisive_share(100) < decisive_share(30)
        assert decisive_share(100) == pytest.approx(0.59, abs=0.02)


class TestPowerNote:
    def test_below_minimum_note_mentions_gate(self) -> None:
        note = power_note(12)
        assert "低于门禁 30" in note
        assert "insufficient" in note

    def test_pass_note_mentions_decisive_line(self) -> None:
        note = power_note(30)
        assert "决定线" in note
        assert "68%" in note
