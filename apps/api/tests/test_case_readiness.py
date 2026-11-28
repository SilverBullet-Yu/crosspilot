from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crosspilot_api.config import REPO_ROOT
from crosspilot_api.domain.evidence import (
    EvidenceCard,
    EvidenceLevel,
    Stance,
    StanceVotes,
    decide_by_claim,
)
from crosspilot_api.main import app
from crosspilot_api.services.case_readiness import ReadinessLevel, assess_case_readiness
from crosspilot_api.services.claims import select_claim_ids
from crosspilot_api.services.l1_import import L1SnapshotData, write_snapshot
from crosspilot_api.services.validation_round import (
    ValidationRoundRecord,
    ValidationRoundsArchiveData,
    write_validation_round,
)

SCOPE = ("internal_product_validation",)


def _card(
    index: int,
    *,
    claim_id: str | None = "capacity",
    review_required: bool = False,
    demo: bool = False,
) -> EvidenceCard:
    return EvidenceCard(
        excerpt=f"Sehr gut und praktisch. {hashlib.sha256(str(index).encode()).hexdigest()}",
        source_url=f"https://example.com/reviews/{index}",
        language="de",
        published_on=date(2026, 11, 1),
        level=EvidenceLevel.L1,
        sample_size=1,
        stance=Stance.SUPPORT,
        is_demo_data=demo,
        stance_votes=StanceVotes(rule=Stance.SUPPORT),
        classification_method="manual",
        classification_note=None if review_required else "人工复核：支持表述明确。",
        review_required=review_required,
        review_reasons=("待复核",) if review_required else ("人工复核已完成",),
        review_id=f"review-{index}",
        claim_id=claim_id,
        market="de",
        source_id="brand-export",
        authorization="品牌授权导出",
        authorization_ref="brand-2026",
    )


def _round(confirmation: str = "confirmed") -> ValidationRoundRecord:
    return ValidationRoundRecord(
        id="round-readiness-20261128",
        createdAt="2026-11-27T18:00:00Z",
        scenario="real",
        query="旅行收纳包",
        claimId="capacity",
        hypothesisTitle="容量越大越好",
        status="supported",
        evidenceRefs="claim_id=capacity; review-0: https://example.com/reviews/0",
        observation="参与者完成装载与取物任务。",
        decision="keep",
        rationale="样本与访谈一致。",
        nextAction="扩大样本复测",
        owner="德国站运营",
        confirmation=confirmation,
        market="de",
        l1SnapshotSha256="d" * 64,
    )


def _assess(
    cards: list[EvidenceCard],
    rounds: list[ValidationRoundRecord] | None = None,
    snapshot_sha256: str | None = "d" * 64,
    rounds_archive_sha256: str | None = None,
    claim_ids: tuple[str, ...] = ("capacity",),
):
    return assess_case_readiness(
        query="旅行收纳包",
        market="de",
        cards=cards,
        claim_decisions=decide_by_claim(cards, claim_ids),
        rounds=rounds or [],
        snapshot_sha256=snapshot_sha256,
        rounds_archive_sha256=rounds_archive_sha256,
    )


def test_no_real_l1_is_blocked() -> None:
    result = _assess([])
    assert result.level is ReadinessLevel.BLOCKED
    assert result.market_effect_claim_allowed is False
    assert any("品牌授权" in action for action in result.next_actions)


def test_readiness_retains_snapshot_fingerprint() -> None:
    result = _assess(
        [_card(0)],
        snapshot_sha256="d" * 64,
        rounds_archive_sha256="e" * 64,
    )
    assert result.snapshot_sha256 == "d" * 64
    assert result.rounds_archive_sha256 == "e" * 64


def test_pending_review_is_exploratory() -> None:
    result = _assess([_card(0, review_required=True)])
    assert result.level is ReadinessLevel.EXPLORATORY
    assert result.claims[0].review_pending == 1


def test_rule_low_priority_cards_do_not_count_as_human_review() -> None:
    cards = [
        replace(
            _card(index),
            classification_method="rule",
            classification_note=None,
            review_reasons=("强支持低复核优先级",),
        )
        for index in range(30)
    ]
    result = _assess(cards)
    assert result.level is ReadinessLevel.EXPLORATORY
    assert result.claims[0].review_pending == 30
    check = next(item for item in result.checks if item.id == "human_review")
    assert check.status.value == "pending"
    assert "复核说明" in check.detail


def test_manual_classification_without_note_is_not_ready() -> None:
    cards = [replace(_card(index), classification_note=None) for index in range(30)]
    result = _assess(cards)
    assert result.level is ReadinessLevel.EXPLORATORY
    assert result.claims[0].review_pending == 30


def test_irrelevant_rule_card_does_not_block_preference_review_gate() -> None:
    cards = [_card(index) for index in range(30)] + [
        replace(
            _card(30),
            claim_id=None,
            relevance="irrelevant",
            stance=Stance.INSUFFICIENT,
            classification_method="rule",
            classification_note=None,
            review_required=False,
            review_reasons=("不相关评论由输入方标注",),
        )
    ]
    result = _assess(cards)
    assert result.level is ReadinessLevel.DECISION_READY
    assert result.claims[0].review_pending == 0


def test_sample_ready_without_operator_is_decision_ready() -> None:
    result = _assess([_card(index) for index in range(30)])
    assert result.level is ReadinessLevel.DECISION_READY
    assert result.claims[0].n_polarized == 30


def test_custom_only_active_claim_can_reach_decision_ready() -> None:
    cards = [_card(index, claim_id="custom-waterproof") for index in range(30)]
    result = _assess(cards, claim_ids=("custom-waterproof",))
    assert result.level is ReadinessLevel.DECISION_READY
    assert [claim.claim_id for claim in result.claims] == ["custom-waterproof"]


def test_inactive_pending_claim_does_not_block_active_case() -> None:
    cards = [_card(index, claim_id="custom-waterproof") for index in range(30)]
    cards.append(_card(30, claim_id="capacity", review_required=True))
    result = _assess(cards, claim_ids=("custom-waterproof",))
    assert result.level is ReadinessLevel.DECISION_READY
    assert result.claims[0].review_pending == 0


def test_unassigned_comment_still_blocks_custom_only_case() -> None:
    cards = [_card(index, claim_id="custom-waterproof") for index in range(30)]
    cards.append(_card(30, claim_id="unassigned"))
    result = _assess(cards, claim_ids=("custom-waterproof",))
    assert result.level is ReadinessLevel.EXPLORATORY


def test_select_claim_ids_deduplicates_and_validates() -> None:
    cards = [_card(0, claim_id="custom-waterproof")]
    assert select_claim_ids(cards, [" custom-waterproof ", "custom-waterproof"]) == (
        "custom-waterproof",
    )
    with pytest.raises(ValueError, match="claim_id 非法"):
        select_claim_ids(cards, ["Invalid Claim"])


def test_confirmed_operator_round_completes_trial() -> None:
    result = _assess([_card(index) for index in range(30)], [_round()])
    assert result.level is ReadinessLevel.TRIAL_COMPLETE
    assert result.confirmed_rounds == 1
    assert result.market_effect_claim_allowed is False


def test_round_bound_to_different_snapshot_does_not_complete_trial() -> None:
    result = _assess(
        [_card(index) for index in range(30)],
        [replace(_round(), l1SnapshotSha256="a" * 64)],
        snapshot_sha256="b" * 64,
    )
    assert result.level is ReadinessLevel.DECISION_READY
    assert result.confirmed_rounds == 0


def test_round_without_consumer_reference_does_not_complete_trial() -> None:
    result = _assess(
        [_card(index) for index in range(30)],
        [replace(_round(), evidenceRefs="claim_id=capacity")],
    )
    assert result.level is ReadinessLevel.DECISION_READY
    assert result.confirmed_rounds == 0
    assert any("review_id: source_url" in action for action in result.next_actions)


def test_round_reference_must_match_real_review_and_source() -> None:
    result = _assess(
        [_card(index) for index in range(30)],
        [
            replace(
                _round(),
                evidenceRefs=(
                    "claim_id=capacity; review-0: https://example.com/reviews/999"
                ),
            )
        ],
    )
    assert result.level is ReadinessLevel.DECISION_READY
    assert result.confirmed_rounds == 0


def test_demo_round_does_not_complete_real_trial() -> None:
    for scenario in ("conflict", "limited"):
        result = _assess(
            [_card(index) for index in range(30)],
            [replace(_round(), scenario=scenario)],
        )
        assert result.level is ReadinessLevel.DECISION_READY
        assert result.confirmed_rounds == 0


def test_pending_operator_round_does_not_complete_trial() -> None:
    result = _assess([_card(index) for index in range(30)], [_round("pending")])
    assert result.level is ReadinessLevel.DECISION_READY


def test_unassigned_comment_blocks_decision_readiness() -> None:
    cards = [_card(index) for index in range(30)] + [_card(30, claim_id="unassigned")]
    assert _assess(cards).level is ReadinessLevel.EXPLORATORY


def test_demo_card_blocks_real_case() -> None:
    cards = [_card(index) for index in range(30)] + [_card(30, demo=True)]
    assert _assess(cards).level is ReadinessLevel.BLOCKED


def test_missing_provenance_blocks_real_case() -> None:
    cards = [replace(_card(0), review_id=None)]
    assert _assess(cards).level is ReadinessLevel.BLOCKED


def test_below_sample_gate_is_exploratory() -> None:
    assert _assess([_card(index) for index in range(29)]).level is ReadinessLevel.EXPLORATORY


def test_readiness_api_returns_checks_and_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [_card(index) for index in range(30)]
    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_l1_snapshot_data",
        lambda query: L1SnapshotData(cards, SCOPE, snapshot_sha256="d" * 64),
    )
    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_validation_rounds_archive_data",
        lambda: ValidationRoundsArchiveData([_round()], "e" * 64),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/case/readiness",
            params={"query": "旅行收纳包", "claim_id": "capacity"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "trial_complete"
    assert body["market_effect_claim_allowed"] is False
    assert body["snapshot_sha256"] == "d" * 64
    assert body["rounds_archive_sha256"] == "e" * 64
    assert {check["id"] for check in body["checks"]} >= {
        "authorized_l1",
        "human_review",
        "sample_gate",
        "operator_trial",
    }
    assert body["claims"][0]["confirmed_rounds"] == 1


def test_readiness_api_accepts_custom_only_claim_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [_card(index, claim_id="custom-waterproof") for index in range(30)]
    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_l1_snapshot_data",
        lambda query: L1SnapshotData(cards, SCOPE),
    )
    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_validation_rounds_archive_data",
        lambda: ValidationRoundsArchiveData([]),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/case/readiness",
            params={"query": "旅行收纳包", "claim_id": "custom-waterproof"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "decision_ready"
    assert [claim["claim_id"] for claim in body["claims"]] == ["custom-waterproof"]


def test_readiness_api_rejects_invalid_claim_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_l1_snapshot_data",
        lambda query: L1SnapshotData([], ()),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/case/readiness",
            params={"query": "旅行收纳包", "claim_id": "Invalid Claim"},
        )
    assert response.status_code == 422


def test_cli_require_trial_complete_rejects_decision_ready(tmp_path: Path) -> None:
    cards = [_card(index) for index in range(30)]
    snapshot_dir = tmp_path / "snapshots"
    snapshot_path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand-export",
        authorization="品牌授权导出",
        authorization_ref="brand-2026",
        authorization_scope=SCOPE,
        output_dir=snapshot_dir,
    )
    snapshot_sha256 = json.loads(snapshot_path.read_text(encoding="utf-8"))["record_sha256"]
    rounds_dir = tmp_path / "rounds"
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "audit_case.py"),
        "--query",
        "旅行收纳包",
        "--snapshot-dir",
        str(snapshot_dir),
        "--rounds-dir",
        str(rounds_dir),
        "--claim-id",
        "capacity",
        "--json",
    ]

    ready = subprocess.run(
        [*command, "--require-ready"], capture_output=True, text=True, check=False
    )
    assert ready.returncode == 0
    incomplete = subprocess.run(
        [*command, "--require-trial-complete"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert incomplete.returncode == 1

    write_validation_round(
        replace(_round(), l1SnapshotSha256=snapshot_sha256),
        rounds_dir,
    )
    complete = subprocess.run(
        [*command, "--require-trial-complete"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert complete.returncode == 0


def test_readiness_api_rejects_corrupt_round_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    from crosspilot_api.services.validation_round import ValidationRoundError

    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_l1_snapshot_data",
        lambda query: L1SnapshotData([], (), "missing"),
    )
    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_validation_rounds_archive_data",
        lambda: (_ for _ in ()).throw(ValidationRoundError("hash mismatch")),
    )
    with TestClient(app) as client:
        response = client.get("/api/case/readiness", params={"query": "旅行收纳包"})
    assert response.status_code == 409


def test_readiness_api_rejects_corrupt_l1_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    from crosspilot_api.services.l1_import import L1ImportError

    monkeypatch.setattr(
        "crosspilot_api.routers.case.load_l1_snapshot_data",
        lambda query: (_ for _ in ()).throw(L1ImportError("invalid snapshot")),
    )
    with TestClient(app) as client:
        response = client.get("/api/case/readiness", params={"query": "旅行收纳包"})
    assert response.status_code == 409
    assert "invalid snapshot" in response.json()["detail"]
