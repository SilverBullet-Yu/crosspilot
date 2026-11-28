from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

from crosspilot_api.domain.evidence import EvidenceCard, EvidenceLevel, Stance
from crosspilot_api.services.l1_import import L1SnapshotData

SAMPLE_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "plan_l1_sample.py"


def _load_sample_module():
    spec = importlib.util.spec_from_file_location("crosspilot_plan_l1_sample", SAMPLE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sample_module = _load_sample_module()


def _card(index: int, stance: Stance) -> EvidenceCard:
    return EvidenceCard(
        excerpt=f"Bewertung {index}: {'sehr gut' if stance is Stance.SUPPORT else 'schlecht'}.",
        source_url=f"https://example.com/reviews/{index}",
        language="de",
        published_on=date(2026, 10 if index % 2 else 11, 1),
        level=EvidenceLevel.L1,
        sample_size=1,
        stance=stance,
        is_demo_data=False,
        review_id=f"review-{index}",
        claim_id="capacity",
        market="de",
        source_id="brand-export",
        authorization="品牌授权导出",
        authorization_ref="brand-2026",
    )


def _snapshot() -> L1SnapshotData:
    cards = [_card(index, Stance.SUPPORT) for index in range(35)]
    cards += [_card(index, Stance.OPPOSE) for index in range(35, 40)]
    return L1SnapshotData(
        cards,
        ("internal_product_validation",),
        snapshot_sha256="a" * 64,
    )


def test_sampling_plan_is_deterministic_and_stratified() -> None:
    first = sample_module.build_sampling_plan(
        _snapshot(),
        "旅行收纳包",
        target=30,
        seed=42,
        claim_ids=("capacity",),
    )
    second = sample_module.build_sampling_plan(
        _snapshot(),
        "旅行收纳包",
        target=30,
        seed=42,
        claim_ids=("capacity",),
    )
    assert first == second
    assert first["snapshot_sha256"] == "a" * 64
    assert first["market_effect_claim_allowed"] is False
    assert set(first["unavailable_dimensions"]) == {"star_rating", "variant"}
    claim = first["claims"][0]
    assert claim["sufficient"] is True
    assert claim["selected_count"] == 30
    assert len({item["review_id"] for item in claim["selected_reviews"]}) == 30
    assert {item["stance"] for item in claim["selected_reviews"]} == {"support", "oppose"}


def test_sampling_plan_reports_insufficient_without_padding() -> None:
    plan = sample_module.build_sampling_plan(
        _snapshot(),
        "旅行收纳包",
        target=50,
        claim_ids=("capacity",),
    )
    claim = plan["claims"][0]
    assert claim["sufficient"] is False
    assert claim["canonical_polarized_total"] == 40
    assert claim["selected_count"] == 40


def test_sampling_plan_rejects_invalid_target() -> None:
    with pytest.raises(ValueError, match="target"):
        sample_module.build_sampling_plan(_snapshot(), "旅行收纳包", target=0)
