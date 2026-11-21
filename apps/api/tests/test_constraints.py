"""硬约束回归测试。这些用例失败即表示合规被破坏，不得跳过或标记 xfail。"""

from __future__ import annotations

from datetime import date

import pytest

from crosspilot_api.domain.evidence import (
    EvidenceCard,
    EvidenceLevel,
    Stance,
    can_support_preference_claim,
    resolve_stance,
)
from crosspilot_api.services.datasets import (
    REGISTRY,
    DataSource,
    Tier,
    assert_demand_side,
    assert_usable,
)


def card(level: EvidenceLevel, stance: Stance = Stance.SUPPORT) -> EvidenceCard:
    return EvidenceCard(
        excerpt="示例摘录",
        source_url="https://example.com/x",
        language="de",
        published_on=date(2025, 1, 1),
        level=level,
        sample_size=12,
        stance=stance,
    )


def test_l2_alone_cannot_support_preference_claim() -> None:
    """硬约束 1：知乎（L2）单独不成立。"""
    assert can_support_preference_claim([card(EvidenceLevel.L2)]) is False
    assert resolve_stance([card(EvidenceLevel.L2)]) is Stance.INSUFFICIENT


def test_l3_alone_cannot_support_preference_claim() -> None:
    assert can_support_preference_claim([card(EvidenceLevel.L3)]) is False


def test_l1_supports_claim() -> None:
    assert can_support_preference_claim([card(EvidenceLevel.L1)]) is True


def test_conflict_is_preserved_not_smoothed() -> None:
    """证据冲突必须保留，不得调和成单一结论。"""
    cards = [
        card(EvidenceLevel.L1, Stance.SUPPORT),
        card(EvidenceLevel.L1, Stance.OPPOSE),
    ]
    assert resolve_stance(cards) is Stance.OPPOSE


def test_evidence_card_requires_six_fields() -> None:
    with pytest.raises(ValueError):
        EvidenceCard(
            excerpt="",
            source_url="https://example.com",
            language="de",
            published_on=date(2025, 1, 1),
            level=EvidenceLevel.L1,
            sample_size=None,
        )


def test_marc_blocked_under_commercial_path() -> None:
    """硬约束 2。"""
    with pytest.raises(PermissionError):
        assert_usable("marc", commercial=True)


def test_opensubtitles_forbidden() -> None:
    """硬约束 3。"""
    with pytest.raises(PermissionError):
        assert_usable("opus_opensubtitles", commercial=True)


def test_comtrade_requires_credential() -> None:
    """硬约束 4。"""
    with pytest.raises(PermissionError):
        assert_usable("un_comtrade", commercial=True, credential=None)
    assert assert_usable("un_comtrade", commercial=True, credential="k").key == "un_comtrade"


def test_deepl_free_requires_credential() -> None:
    """硬约束 5：Free 档无 DPA，必须显式持有 key 才能调用。"""
    with pytest.raises(PermissionError):
        assert_usable("deepl_free", commercial=True, credential=None)


def test_ebay_is_seller_side_only() -> None:
    """eBay 返回卖家自撰文案，不得写入消费者证据侧。"""
    assert assert_usable("ebay_browse", commercial=True, credential="k").seller_side_only
    with pytest.raises(PermissionError):
        assert_demand_side("ebay_browse")


def test_l2_l3_sources_rejected_on_demand_side() -> None:
    """知乎（L2）与 GDELT / Safety Gate（L3）不得单独支撑消费者偏好结论。"""
    for key in ("zhihu_open", "gdelt_doc", "eu_safety_gate", "openalex"):
        with pytest.raises(PermissionError):
            assert_demand_side(key)


def test_amazon_reviews_allowed_on_demand_side() -> None:
    assert assert_demand_side("amazon_reviews_2023").tier is Tier.L1


def test_unregistered_source_rejected_on_demand_side() -> None:
    with pytest.raises(KeyError):
        assert_demand_side("some_unregistered_source")


@pytest.mark.parametrize("key", sorted(REGISTRY))
def test_every_source_declares_priority_and_tier(key: str) -> None:
    """注册表是许可边界的唯一事实来源，字段不得留空。"""
    source: DataSource = REGISTRY[key]
    assert source.priority in {"P0", "P1", "P2"}
    assert isinstance(source.tier, Tier)
    assert source.note


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("hf_dataset_viewer", 100),
        ("gdelt_doc", 250),
        ("ebay_browse", 200),
        ("openalex", 100),
    ],
)
def test_truncation_prone_sources_declare_page_limit(key: str, expected: int) -> None:
    """截断与完整返回外观一致，分页上限必须显式登记（同硬约束 4 的失败模式）。"""
    assert REGISTRY[key].page_limit == expected


def test_p0_sources_need_no_credential() -> None:
    """P0 的定义就是零凭据零审批，违反即说明优先级标错。"""
    for key, source in REGISTRY.items():
        if source.priority == "P0":
            assert not source.requires_credential, f"{key} 标为 P0 却需要凭据"
