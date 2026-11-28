from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crosspilot_api.domain.evidence import EvidenceLevel, Stance, StanceVotes
from crosspilot_api.main import app
from crosspilot_api.services.l1_import import (
    L1ImportError,
    L1SnapshotData,
    claim_terms_from_cards,
    load_import_file,
    load_l1_snapshot,
    load_l1_snapshot_data,
    parse_import_document,
    sha256_file,
    snapshot_digest,
    snapshot_version_digest,
    summarize_l1_import,
    write_snapshot,
)

SCOPE = ("internal_product_validation",)


def _payload() -> dict[str, object]:
    return {
        "query": "旅行收纳包",
        "market": "de",
        "source_id": "brand_export",
        "authorization": "品牌授权导出，仅内部验证",
        "authorization_ref": "brand-export-2026-11",
        "authorization_scope": list(SCOPE),
        "cards": [
            {
                "review_id": "r1",
                "claim_id": "capacity",
                "excerpt": "Die Tasche ist sehr gut und praktisch.",
                "source_url": "https://example.com/reviews/r1",
                "published_on": "2026-11-01",
                "language": "de",
            }
        ],
    }


def test_import_requires_claim_market_source_and_authorization() -> None:
    query, cards = parse_import_document(_payload())
    assert query == "旅行收纳包"
    assert cards[0].review_id == "r1"
    assert cards[0].claim_id == "capacity"
    assert cards[0].market == "de"
    assert cards[0].source_id == "brand_export"
    assert cards[0].authorization
    assert cards[0].authorization_ref == "brand-export-2026-11"
    assert cards[0].level is EvidenceLevel.L1
    assert cards[0].stance is Stance.SUPPORT
    assert cards[0].classification_method == "rule"
    assert cards[0].review_required is True
    assert cards[0].review_reasons
    assert cards[0].stance_votes is not None
    summary = summarize_l1_import(query, cards)
    assert "capacity: L1=1，支持=1，反对=0" in summary
    assert "门禁=below_minimum，判定=insufficient" in summary
    assert "未归属=0，不相关=0" in summary


@pytest.mark.parametrize("field", ["source_id", "authorization", "authorization_ref"])
def test_import_rejects_missing_provenance(field: str) -> None:
    payload = _payload()
    payload.pop(field)
    with pytest.raises(L1ImportError):
        parse_import_document(payload)


@pytest.mark.parametrize(
    "scope",
    [
        None,
        [],
        ["model_processing"],
        ["public_display"],
        ["internal_product_validation", "unknown"],
    ],
)
def test_import_requires_explicit_internal_authorization_scope(scope: object) -> None:
    payload = _payload()
    if scope is None:
        payload.pop("authorization_scope")
    else:
        payload["authorization_scope"] = scope
    with pytest.raises(L1ImportError, match="authorization_scope"):
        parse_import_document(payload)


def test_import_accepts_multiple_explicit_authorization_scopes() -> None:
    payload = _payload()
    payload["authorization_scope"] = [
        "internal_product_validation",
        "model_processing",
        "contest_demo",
    ]
    parse_import_document(payload)


def test_import_accepts_custom_claim_ids() -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "custom-waterproof"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    assert cards[0].claim_id == "custom-waterproof"
    summary = summarize_l1_import("旅行收纳包", cards)
    assert "custom-waterproof: L1=1" in summary


def test_import_classifies_same_review_separately_for_each_claim() -> None:
    payload = _payload()
    payload["cards"][0]["excerpt"] = (  # type: ignore[index]
        "Der Preis ist überteuert, aber die Fächer sind sehr gut."
    )
    payload["cards"][0]["claim_id"] = "features"  # type: ignore[index]
    _, feature_cards = parse_import_document(payload)
    payload["cards"][0]["claim_id"] = "price"  # type: ignore[index]
    _, price_cards = parse_import_document(payload)
    assert feature_cards[0].stance is Stance.SUPPORT
    assert price_cards[0].stance is Stance.OPPOSE
    assert feature_cards[0].stance_votes is not None
    assert price_cards[0].stance_votes is not None
    assert feature_cards[0].stance_votes.rule is Stance.SUPPORT
    assert price_cards[0].stance_votes.rule is Stance.OPPOSE
    assert any("仅计 1/2 个相关从句" in reason for reason in feature_cards[0].review_reasons)
    assert any("命中术语 faecher" in reason for reason in feature_cards[0].review_reasons)
    assert any("命中术语 preis" in reason for reason in price_cards[0].review_reasons)


def test_import_custom_claim_terms_scope_rule_vote() -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "custom-waterproof"  # type: ignore[index]
    payload["cards"][0]["excerpt"] = (  # type: ignore[index]
        "Der Preis ist überteuert, aber die wasserdichte Tasche ist sehr gut."
    )
    payload["claim_terms"] = {"custom-waterproof": ["wasserdicht", "waterproof"]}
    _, cards = parse_import_document(payload)
    assert cards[0].aspect_terms == ("wasserdicht", "waterproof")
    assert cards[0].stance is Stance.SUPPORT
    assert cards[0].stance_votes is not None
    assert cards[0].stance_votes.rule is Stance.SUPPORT
    assert any("仅计 1/2 个相关从句" in reason for reason in cards[0].review_reasons)
    assert any("命中术语 wasserdicht" in reason for reason in cards[0].review_reasons)
    assert not any("回退整条评论" in reason for reason in cards[0].review_reasons)


@pytest.mark.parametrize(
    "claim_terms",
    [
        [],
        {"capacity": ["groß"]},
        {"unassigned": ["produkt"]},
        {"custom-waterproof": []},
        {"custom-waterproof": ["x" * 81]},
        {"custom-waterproof": [123]},
        {"custom-waterproof": ["line\nbreak"]},
        {"unused-claim": ["wasser"]},
    ],
)
def test_import_rejects_invalid_claim_terms(claim_terms: object) -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "custom-waterproof"  # type: ignore[index]
    payload["claim_terms"] = claim_terms
    with pytest.raises(L1ImportError, match="claim_terms"):
        parse_import_document(payload)


def test_import_rejects_card_level_aspect_terms() -> None:
    payload = _payload()
    payload["cards"][0]["aspect_terms"] = ["wasserdicht"]  # type: ignore[index]
    with pytest.raises(L1ImportError, match="claim_terms"):
        parse_import_document(payload)


def test_claim_terms_from_cards_rejects_inconsistent_scope() -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "custom-waterproof"  # type: ignore[index]
    payload["claim_terms"] = {"custom-waterproof": ["wasserdicht"]}
    _, cards = parse_import_document(payload)
    changed = replace(cards[0], aspect_terms=("waterproof",))
    with pytest.raises(L1ImportError, match="aspect_terms 不一致"):
        claim_terms_from_cards([cards[0], changed])
    builtin = replace(cards[0], claim_id="features")
    with pytest.raises(L1ImportError, match="只能归属于自定义卖点"):
        claim_terms_from_cards([builtin])


def test_import_custom_claim_fallback_requires_review() -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "custom-waterproof"  # type: ignore[index]
    payload["cards"][0]["excerpt"] = (  # type: ignore[index]
        "Dieses Produkt ist wirklich gut super toll perfekt."
    )
    _, cards = parse_import_document(payload)
    assert cards[0].stance is Stance.SUPPORT
    assert cards[0].review_required is True
    assert any("回退整条评论" in reason for reason in cards[0].review_reasons)


def test_manual_agreement_uses_claim_specific_rule_vote() -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "features"  # type: ignore[index]
    payload["cards"][0]["excerpt"] = (  # type: ignore[index]
        "Der Preis ist überteuert, aber die Fächer sind sehr gut."
    )
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    payload["cards"][0]["stance_note"] = "人工复核：功能表述明确支持。"  # type: ignore[index]
    _, feature_cards = parse_import_document(payload)
    payload["cards"][0]["claim_id"] = "price"  # type: ignore[index]
    _, price_cards = parse_import_document(payload)
    assert feature_cards[0].annotator_agreement is True
    assert price_cards[0].annotator_agreement is False
    assert feature_cards[0].stance_votes is not None
    assert price_cards[0].stance_votes is not None
    assert feature_cards[0].stance_votes.rule is Stance.SUPPORT
    assert price_cards[0].stance_votes.rule is Stance.OPPOSE


@pytest.mark.parametrize("claim_id", ["Capacity", "has space", "x" * 65])
def test_import_rejects_invalid_custom_claim_ids(claim_id: str) -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = claim_id  # type: ignore[index]
    with pytest.raises(L1ImportError, match="claim_id"):
        parse_import_document(payload)


def test_manual_stance_override_preserves_rule_vote() -> None:
    payload = _payload()
    payload["cards"][0]["excerpt"] = "Ich bin sehr enttäuscht und komme nicht wieder."  # type: ignore[index]
    _, baseline = parse_import_document(payload)
    assert baseline[0].stance is Stance.OPPOSE
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    payload["cards"][0]["stance_note"] = "人工复核：反讽，实际在肯定。"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    assert cards[0].stance is Stance.SUPPORT
    assert cards[0].classification_method == "manual"
    assert cards[0].review_required is False
    assert cards[0].review_reasons == ("人工复核已完成",)
    assert cards[0].stance_votes is not None
    assert cards[0].stance_votes.rule is Stance.OPPOSE
    assert cards[0].annotator_agreement is False
    assert cards[0].classification_note == "人工复核：反讽，实际在肯定。"
    summary = summarize_l1_import("旅行收纳包", cards)
    assert "人工复核=1，规则基线=0，人工与规则不一致=1" in summary


def test_manual_stance_override_can_agree_with_rule() -> None:
    payload = _payload()
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    payload["cards"][0]["stance_note"] = "人工复核：支持表述明确。"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    assert cards[0].classification_method == "manual"
    assert cards[0].annotator_agreement is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stance", "unknown"),
        ("stance_note", "人工复核"),
        ("classification_method", "manual"),
        ("review_required", "true"),
    ],
)
def test_import_rejects_invalid_manual_classification(field: str, value: str) -> None:
    payload = _payload()
    payload["cards"][0][field] = value  # type: ignore[index]
    with pytest.raises(L1ImportError):
        parse_import_document(payload)


def test_irrelevant_comment_cannot_claim_support() -> None:
    payload = _payload()
    payload["cards"][0].pop("claim_id")  # type: ignore[index,union-attr]
    payload["cards"][0]["relevance"] = "irrelevant"  # type: ignore[index]
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    with pytest.raises(L1ImportError, match="不相关评论"):
        parse_import_document(payload)


@pytest.mark.parametrize("note", [None, "", "   "])
def test_manual_stance_override_requires_note(note: str | None) -> None:
    payload = _payload()
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    if note is not None:
        payload["cards"][0]["stance_note"] = note  # type: ignore[index]
    with pytest.raises(L1ImportError, match="stance_note|分类说明"):
        parse_import_document(payload)


def test_preserved_manual_classification_requires_note() -> None:
    payload = _payload()
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    payload["cards"][0]["classification_method"] = "manual"  # type: ignore[index]
    with pytest.raises(L1ImportError, match="classification_note"):
        parse_import_document(payload, preserve_classification=True)


def test_manual_classification_note_is_sanitized() -> None:
    payload = _payload()
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    payload["cards"][0]["stance_note"] = "复核 test@example.com"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    assert "test@example.com" not in (cards[0].classification_note or "")
    assert "[联系方式已剔除]" in (cards[0].classification_note or "")


def test_snapshot_round_trip_preserves_manual_classification(tmp_path: Path) -> None:
    payload = _payload()
    payload["cards"][0]["excerpt"] = "Ich bin sehr enttäuscht und komme nicht wieder."  # type: ignore[index]
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    payload["cards"][0]["stance_note"] = "人工复核：反讽。"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert notice is None
    assert loaded[0].stance is Stance.SUPPORT
    assert loaded[0].classification_method == "manual"
    assert loaded[0].review_required is False
    assert loaded[0].classification_note == "人工复核：反讽。"
    assert loaded[0].stance_votes is not None
    assert loaded[0].stance_votes.rule is Stance.OPPOSE
    assert loaded[0].annotator_agreement is False


def test_snapshot_round_trip_preserves_claim_scope_reasons(tmp_path: Path) -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "features"  # type: ignore[index]
    payload["cards"][0]["excerpt"] = (  # type: ignore[index]
        "Der Preis ist überteuert, aber die Fächer sind sehr gut."
    )
    _, cards = parse_import_document(payload)
    write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert notice is None
    assert loaded[0].stance is Stance.SUPPORT
    assert loaded[0].stance_votes is not None
    assert loaded[0].stance_votes.rule is Stance.SUPPORT
    assert loaded[0].review_reasons == cards[0].review_reasons
    assert any("仅计 1/2 个相关从句" in reason for reason in loaded[0].review_reasons)


def test_snapshot_round_trip_preserves_custom_claim_terms(tmp_path: Path) -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "custom-waterproof"  # type: ignore[index]
    payload["cards"][0]["excerpt"] = (  # type: ignore[index]
        "Der Preis ist überteuert, aber die wasserdichte Tasche ist sehr gut."
    )
    payload["claim_terms"] = {"custom-waterproof": ["wasserdicht", "waterproof"]}
    _, cards = parse_import_document(payload)
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["claim_terms"] == {
        "custom-waterproof": ["wasserdicht", "waterproof"]
    }
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert notice is None
    assert loaded[0].aspect_terms == ("wasserdicht", "waterproof")
    assert loaded[0].stance is Stance.SUPPORT
    assert loaded[0].review_reasons == cards[0].review_reasons


def test_api_exposes_custom_claim_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    payload["cards"][0]["claim_id"] = "custom-waterproof"  # type: ignore[index]
    payload["cards"][0]["excerpt"] = (  # type: ignore[index]
        "Der Preis ist überteuert, aber die wasserdichte Tasche ist sehr gut."
    )
    payload["claim_terms"] = {"custom-waterproof": ["wasserdicht"]}
    _, cards = parse_import_document(payload)
    monkeypatch.setattr(
        "crosspilot_api.routers.evidence.load_l1_snapshot_data",
        lambda query: L1SnapshotData(cards, SCOPE, snapshot_sha256="a" * 64),
    )
    with TestClient(app) as client:
        response = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert response.status_code == 200
    assert response.json()["l1_snapshot_sha256"] == "a" * 64
    card = next(item for item in response.json()["cards"] if item.get("review_id") == "r1")
    assert card["aspect_terms"] == ["wasserdicht"]
    assert card["stance"] == "support"
    assert any("命中术语 wasserdicht" in reason for reason in card["review_reasons"])


def test_api_exposes_manual_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    payload["cards"][0]["excerpt"] = "Ich bin sehr enttäuscht und komme nicht wieder."  # type: ignore[index]
    payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    payload["cards"][0]["stance_note"] = "人工复核：反讽。"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    monkeypatch.setattr(
        "crosspilot_api.routers.evidence.load_l1_snapshot_data",
        lambda query: L1SnapshotData(cards, SCOPE),
    )
    with TestClient(app) as client:
        response = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert response.status_code == 200
    card = next(item for item in response.json()["cards"] if item.get("review_id") == "r1")
    assert card["stance"] == "support"
    assert card["classification_method"] == "manual"
    assert card["classification_note"] == "人工复核：反讽。"
    assert card["review_required"] is False
    assert card["review_reasons"] == ["人工复核已完成"]
    assert card["stance_votes"]["rule"] == "oppose"
    assert card["annotator_agreement"] is False
    assert response.json()["l1_authorization_scope"] == list(SCOPE)


def test_import_allows_explicit_irrelevant_comments() -> None:
    payload = _payload()
    payload["cards"][0].pop("claim_id")  # type: ignore[index,union-attr]
    payload["cards"][0]["relevance"] = "irrelevant"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    assert cards[0].claim_id is None
    assert cards[0].relevance == "irrelevant"
    assert cards[0].stance is Stance.INSUFFICIENT


def test_import_preserves_relevant_but_unassigned_comments() -> None:
    payload = _payload()
    payload["cards"][0].pop("claim_id")  # type: ignore[index,union-attr]
    _, cards = parse_import_document(payload)
    assert cards[0].claim_id == "unassigned"
    assert cards[0].relevance == "relevant"
    assert cards[0].stance is Stance.SUPPORT
    assert "未归属=1，不相关=0" in summarize_l1_import("旅行收纳包", cards)


def test_import_rejects_top_level_demo_data() -> None:
    payload = _payload()
    payload["is_demo_data"] = True
    with pytest.raises(L1ImportError, match="演示数据"):
        parse_import_document(payload)


def test_import_rejects_wrong_market_and_demo_data() -> None:
    payload = _payload()
    payload["market"] = "us"
    with pytest.raises(L1ImportError):
        parse_import_document(payload)
    payload = _payload()
    payload["cards"][0]["is_demo_data"] = True  # type: ignore[index]
    with pytest.raises(L1ImportError):
        parse_import_document(payload)


def test_import_sanitizes_contact_details() -> None:
    payload = _payload()
    payload["cards"][0]["excerpt"] = "Sehr gut. Kontakt: test@example.com"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    assert "test@example.com" not in cards[0].excerpt
    assert "[联系方式已剔除]" in cards[0].excerpt


def test_import_accepts_non_german_language_for_german_market() -> None:
    payload = _payload()
    payload["cards"][0]["language"] = "en"  # type: ignore[index]
    _, cards = parse_import_document(payload)
    assert cards[0].market == "de"
    assert cards[0].language == "en"


def test_import_rejects_future_publication_date() -> None:
    payload = _payload()
    payload["cards"][0]["published_on"] = "2999-01-01"  # type: ignore[index]
    with pytest.raises(L1ImportError, match="published_on"):
        parse_import_document(payload)


def test_import_flags_exact_duplicate_with_opposite_stances() -> None:
    payload = _payload()
    first = payload["cards"][0]
    second = dict(first)
    first["stance"] = "support"
    first["stance_note"] = "人工复核：支持。"
    second["review_id"] = "r2"
    second["source_url"] = "https://example.com/reviews/r2"
    second["stance"] = "oppose"
    second["stance_note"] = "人工复核：反对。"
    payload["cards"] = [first, second]
    _, cards = parse_import_document(payload)
    assert [card.review_id for card in cards] == ["r1", "r2"]
    assert all(card.review_required for card in cards)
    assert all(
        any("重复评论出现不同立场" in reason for reason in card.review_reasons)
        for card in cards
    )


def test_import_flags_near_duplicate_with_opposite_stances() -> None:
    payload = _payload()
    first = payload["cards"][0]
    second = dict(first)
    first["stance"] = "support"
    first["stance_note"] = "人工复核：支持。"
    second["review_id"] = "r2"
    second["source_url"] = "https://example.com/reviews/r2"
    second["excerpt"] = "Die Tasche ist sehr gut und praktisch!"
    second["stance"] = "oppose"
    second["stance_note"] = "人工复核：反对。"
    payload["cards"] = [first, second]
    _, cards = parse_import_document(payload)
    assert all(card.review_required for card in cards)
    assert all(
        any("重复评论出现不同立场" in reason for reason in card.review_reasons)
        for card in cards
    )


def test_import_does_not_flag_same_stance_or_different_claim_duplicates() -> None:
    payload = _payload()
    first = payload["cards"][0]
    second = dict(first)
    first["stance"] = "support"
    first["stance_note"] = "人工复核：支持。"
    second["review_id"] = "r2"
    second["source_url"] = "https://example.com/reviews/r2"
    second["stance"] = "support"
    second["stance_note"] = "人工复核：支持。"
    payload["cards"] = [first, second]
    _, same_stance = parse_import_document(payload)
    assert all(not card.review_required for card in same_stance)

    second["claim_id"] = "price"
    second["stance"] = "oppose"
    second["stance_note"] = "人工复核：价格反对。"
    _, different_claim = parse_import_document(payload)
    assert all(not card.review_required for card in different_claim)


def test_import_rejects_duplicate_review_ids() -> None:
    payload = _payload()
    payload["cards"].append(dict(payload["cards"][0]))  # type: ignore[index,union-attr]
    with pytest.raises(L1ImportError, match="review_id"):
        parse_import_document(payload)


def test_snapshot_round_trip_and_missing_notice(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出，仅内部验证",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    assert path.is_file()
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert notice is None
    assert loaded[0].review_id == "r1"
    assert loaded[0].excerpt == cards[0].excerpt
    assert loaded[0].claim_id == "capacity"
    missing, notice = load_l1_snapshot("保温杯", tmp_path)
    assert missing == []
    assert notice


def test_import_rejects_cli_scope_expansion() -> None:
    with pytest.raises(L1ImportError, match="授权范围.*不一致"):
        parse_import_document(
            _payload(),
            default_authorization_scope=(*SCOPE, "public_display"),
        )


def test_snapshot_records_input_and_record_hashes(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    input_sha256 = "a" * 64
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        input_sha256=input_sha256,
        output_dir=tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["input_sha256"] == input_sha256
    assert payload["authorization_scope"] == list(SCOPE)
    assert payload["record_sha256"] == snapshot_digest(payload)
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert notice is None
    assert loaded == cards
    assert input_sha256 in summarize_l1_import(
        "旅行收纳包", cards, input_sha256=input_sha256
    )


def test_snapshot_loader_rejects_timestamp_tampering(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["generated_at_utc"] = "2999-01-01T00:00:00Z"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert loaded == []
    assert notice and "version_sha256" in notice


def test_write_snapshot_rejects_demo_card_laundering(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    demo = replace(
        cards[0],
        is_demo_data=True,
        classification_method="manual",
        classification_note="人工复核：支持。",
        review_required=False,
    )
    with pytest.raises(L1ImportError, match="真实 L1"):
        write_snapshot(
            [demo],
            query="旅行收纳包",
            source_id="brand_export",
            authorization="品牌授权导出",
            authorization_ref="brand-export-2026-11",
            authorization_scope=SCOPE,
            output_dir=tmp_path,
        )


def test_reviewed_snapshot_requires_matching_parent_and_scope(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    kwargs = {
        "query": "旅行收纳包",
        "source_id": "brand_export",
        "authorization": "品牌授权导出",
        "authorization_ref": "brand-export-2026-11",
        "authorization_scope": SCOPE,
        "output_dir": tmp_path,
    }
    parent = write_snapshot(cards, **kwargs)
    parent_payload = json.loads(parent.read_text(encoding="utf-8"))
    parent_digest = parent_payload["record_sha256"]
    reviewed_payload = _payload()
    reviewed_payload["source_snapshot_sha256"] = parent_digest
    reviewed_payload["cards"][0]["stance"] = "support"  # type: ignore[index]
    reviewed_payload["cards"][0]["stance_note"] = "人工复核：支持明确。"  # type: ignore[index]
    _, reviewed = parse_import_document(reviewed_payload)
    child = write_snapshot(
        reviewed,
        **kwargs,
        source_snapshot_sha256=parent_digest,
        versioned=True,
    )
    child_payload = json.loads(child.read_text(encoding="utf-8"))
    assert child_payload["source_snapshot_sha256"] == parent_digest
    assert child_payload["record_sha256"] == snapshot_digest(child_payload)
    assert child_payload["version_sha256"] == snapshot_version_digest(child_payload)

    with pytest.raises(L1ImportError, match="未匹配"):
        write_snapshot(
            reviewed,
            **kwargs,
            source_snapshot_sha256="a" * 64,
            versioned=True,
        )
    with pytest.raises(L1ImportError, match="授权范围"):
        write_snapshot(
            reviewed,
            **{**kwargs, "authorization_scope": (*SCOPE, "public_display")},
            source_snapshot_sha256=parent_digest,
            versioned=True,
        )
    with pytest.raises(L1ImportError, match="原文或溯源字段"):
        write_snapshot(
            [replace(reviewed[0], excerpt="Die Tasche ist ganz anders.")],
            **kwargs,
            source_snapshot_sha256=parent_digest,
            versioned=True,
        )


def test_snapshot_loader_rejects_tampering(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cards"][0]["excerpt"] = "Manipulierte Bewertung"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert loaded == []
    assert notice and "record_sha256" in notice


def test_snapshot_loader_rejects_authorization_scope_tampering(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["authorization_scope"] = ["model_processing"]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert loaded == []
    assert notice and "record_sha256" in notice


def test_snapshot_rewrite_is_idempotent_and_conflict_is_rejected(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    kwargs = {
        "query": "旅行收纳包",
        "source_id": "brand_export",
        "authorization": "品牌授权导出",
        "authorization_ref": "brand-export-2026-11",
        "authorization_scope": SCOPE,
        "input_sha256": "b" * 64,
        "output_dir": tmp_path,
    }
    first = write_snapshot(cards, **kwargs)
    first_bytes = first.read_bytes()
    second = write_snapshot(cards, **kwargs)
    assert second == first
    assert first.read_bytes() == first_bytes
    with pytest.raises(L1ImportError, match="禁止覆盖"):
        write_snapshot(cards, **{**kwargs, "input_sha256": "c" * 64})


def test_versioned_snapshot_rewrite_is_idempotent(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    kwargs = {
        "query": "旅行收纳包",
        "source_id": "brand_export",
        "authorization": "品牌授权导出",
        "authorization_ref": "brand-export-2026-11",
        "authorization_scope": SCOPE,
        "input_sha256": "b" * 64,
        "output_dir": tmp_path,
        "versioned": True,
    }
    first = write_snapshot(cards, **kwargs)
    second = write_snapshot(cards, **kwargs)
    assert second == first
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_versioned_snapshot_loader_uses_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cards = parse_import_document(_payload())
    base = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)
    times = iter((base, base + timedelta(seconds=1)))

    class Clock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            try:
                return next(times)
            except StopIteration:
                return base + timedelta(seconds=2)

    monkeypatch.setattr("crosspilot_api.services.l1_import.datetime", Clock)
    kwargs = {
        "query": "旅行收纳包",
        "source_id": "brand_export",
        "authorization": "品牌授权导出",
        "authorization_ref": "brand-export-2026-11",
        "authorization_scope": SCOPE,
        "output_dir": tmp_path,
        "versioned": True,
    }
    write_snapshot(cards, **{**kwargs, "input_sha256": "a" * 64})
    latest = write_snapshot(
        [replace(cards[0], excerpt="Die Tasche ist schlecht verarbeitet.")],
        **{**kwargs, "input_sha256": "b" * 64},
    )
    assert len(list(tmp_path.glob("*.json"))) == 2
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert notice is None
    assert loaded[0].excerpt == "Die Tasche ist schlecht verarbeitet."
    snapshot = load_l1_snapshot_data("旅行收纳包", tmp_path)
    assert snapshot.authorization_scope == SCOPE
    assert snapshot.snapshot_sha256 == json.loads(
        latest.read_text(encoding="utf-8")
    )["record_sha256"]
    assert latest.exists()


def test_corrupt_latest_version_does_not_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cards = parse_import_document(_payload())
    base = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)
    times = iter((base, base + timedelta(seconds=1)))

    class Clock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            try:
                return next(times)
            except StopIteration:
                return base + timedelta(seconds=2)

    monkeypatch.setattr("crosspilot_api.services.l1_import.datetime", Clock)
    kwargs = {
        "query": "旅行收纳包",
        "source_id": "brand_export",
        "authorization": "品牌授权导出",
        "authorization_ref": "brand-export-2026-11",
        "authorization_scope": SCOPE,
        "output_dir": tmp_path,
        "versioned": True,
    }
    write_snapshot(cards, **{**kwargs, "input_sha256": "a" * 64})
    latest = write_snapshot(
        [replace(cards[0], excerpt="Die Tasche ist schlecht verarbeitet.")],
        **{**kwargs, "input_sha256": "b" * 64},
    )
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload["record_sha256"] = "0" * 64
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert loaded == []
    assert notice and "record_sha256" in notice


def test_versioned_snapshot_wins_over_legacy_path(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    kwargs = {
        "query": "旅行收纳包",
        "source_id": "brand_export",
        "authorization": "品牌授权导出",
        "authorization_ref": "brand-export-2026-11",
        "authorization_scope": SCOPE,
        "output_dir": tmp_path,
    }
    write_snapshot(cards, **kwargs)
    write_snapshot(
        [replace(cards[0], excerpt="Die Tasche ist schlecht verarbeitet.")],
        **{**kwargs, "input_sha256": "b" * 64, "versioned": True},
    )
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert notice is None
    assert loaded[0].excerpt == "Die Tasche ist schlecht verarbeitet."


def test_snapshot_loader_rejects_missing_hash(tmp_path: Path) -> None:
    _, cards = parse_import_document(_payload())
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("record_sha256")
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    loaded, notice = load_l1_snapshot("旅行收纳包", tmp_path)
    assert loaded == []
    assert notice and "record_sha256" in notice


def test_sha256_file_matches_raw_bytes(tmp_path: Path) -> None:
    path = tmp_path / "reviews.csv"
    content = b"review_id,excerpt\nr1,Sehr gut\n"
    path.write_bytes(content)
    assert sha256_file(path) == hashlib.sha256(content).hexdigest()


def test_csv_import_uses_cli_metadata(tmp_path: Path) -> None:
    path = tmp_path / "reviews.csv"
    path.write_text(
        "review_id,claim_id,excerpt,source_url,published_on,language\n"
        "r1,features,Die Fächer sind sehr praktisch.,https://example.com/r1,2026-11-01,de\n",
        encoding="utf-8",
    )
    query, cards = load_import_file(
        path,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="品牌授权导出",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
    )
    assert query == "旅行收纳包"
    assert cards[0].claim_id == "features"


def test_snapshot_document_is_valid_json(tmp_path: Path) -> None:
    source = _payload()
    source["cards"][0].pop("claim_id")  # type: ignore[index,union-attr]
    _, cards = parse_import_document(source)
    path = write_snapshot(
        cards,
        query="旅行收纳包",
        source_id="brand_export",
        authorization="授权",
        authorization_ref="brand-export-2026-11",
        authorization_scope=SCOPE,
        output_dir=tmp_path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["is_demo_data"] is False
    assert payload["market"] == "de"
    assert payload["authorization_ref"] == "brand-export-2026-11"
    assert payload["cards"][0]["review_id"] == "r1"
    assert payload["cards"][0]["claim_id"] == "unassigned"


def test_real_endpoint_uses_imported_claim_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _, cards = parse_import_document(_payload())
    imported = [
        replace(
            cards[0],
            review_id=f"r{index}",
            excerpt=(
                "Die Tasche ist sehr gut und praktisch. "
                f"{hashlib.sha256(str(index).encode()).hexdigest()[:16]}"
            ),
            stance=Stance.SUPPORT,
            stance_votes=StanceVotes(rule=Stance.SUPPORT),
        )
        for index in range(30)
    ]
    imported.append(
        replace(
            cards[0],
            review_id="r-unassigned",
            claim_id="unassigned",
            relevance="relevant",
            stance=Stance.OPPOSE,
            stance_votes=StanceVotes(rule=Stance.OPPOSE),
        )
    )
    imported.append(
        replace(
            cards[0],
            review_id="r-irrelevant",
            claim_id=None,
            relevance="irrelevant",
            stance=Stance.INSUFFICIENT,
            stance_votes=StanceVotes(rule=Stance.INSUFFICIENT),
        )
    )
    monkeypatch.setattr(
        "crosspilot_api.routers.evidence.load_l1_snapshot_data",
        lambda query: L1SnapshotData(imported, SCOPE),
    )
    with TestClient(app) as client:
        response = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert response.status_code == 200
    body = response.json()
    capacity = next(item for item in body["claim_decisions"] if item["claim_id"] == "capacity")
    assert capacity["state"] == "supported"
    assert capacity["n_l1"] == 30
    l1_review_ids = {card["review_id"] for card in body["cards"] if card["level"] == "L1"}
    assert l1_review_ids == {f"r{index}" for index in range(30)} | {"r-unassigned", "r-irrelevant"}
    assert any(card["claim_id"] == "unassigned" for card in body["cards"])
    assert any(card["relevance"] == "irrelevant" for card in body["cards"])
    assert body["l1_notice"] is None
    assert any("跨来源待验证" in question["text"] for question in body["questions"])


def test_real_endpoint_returns_custom_claim_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    _, cards = parse_import_document(_payload())
    imported = [
        replace(
            cards[0],
            review_id=f"custom-{index}",
            claim_id="custom-waterproof",
            excerpt=(
                "Die Tasche ist sehr gut und praktisch. "
                f"{hashlib.sha256(str(index).encode()).hexdigest()[:16]}"
            ),
            stance=Stance.SUPPORT,
            stance_votes=StanceVotes(rule=Stance.SUPPORT),
        )
        for index in range(30)
    ]
    monkeypatch.setattr(
        "crosspilot_api.routers.evidence.load_l1_snapshot_data",
        lambda query: L1SnapshotData(imported, SCOPE),
    )
    with TestClient(app) as client:
        response = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert response.status_code == 200
    body = response.json()
    custom = next(
        item for item in body["claim_decisions"] if item["claim_id"] == "custom-waterproof"
    )
    assert custom["state"] == "supported"
    assert custom["n_l1"] == 30
    assert len(body["claim_decisions"]) == 4
    assert any("custom-waterproof" in question["text"] for question in body["questions"])
