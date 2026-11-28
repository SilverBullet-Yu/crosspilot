from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from crosspilot_api.services.validation_round import (
    ValidationRoundError,
    load_validation_rounds_archive,
    load_validation_rounds_archive_data,
    load_validation_rounds_file,
    parse_validation_rounds_document,
    summarize_validation_rounds,
    validation_round_digest,
    write_validation_round,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _round() -> dict[str, object]:
    return {
        "id": "round-test-20261128",
        "createdAt": _now(),
        "scenario": "conflict",
        "query": "旅行收纳包",
        "claimId": "features",
        "hypothesisTitle": "功能越多越好",
        "status": "conflicting",
        "evidenceRefs": "claim_id=features; review-1: https://example.com/review-1",
        "observation": "开放空间首次取物更快，多隔层版找小物更快。",
        "decision": "modify",
        "rationale": "支持和反对来自不同装载场景。",
        "nextAction": "补充 5 位目标用户复测",
        "owner": "德国站运营",
        "confirmation": "confirmed",
    }


def _prototype() -> dict[str, str]:
    return {
        "participantCode": "P01",
        "order": "multi_first",
        "itemsLoaded": "厚衣物放开放空间，充电线放小隔层。",
        "retrieval": "开放空间首次取物成功，多隔层版开合两次。",
        "friction": "厚衣物卡住拉链，参与者要求先取出小物。",
    }


def _document(*rounds: dict[str, object]) -> dict[str, object]:
    return {"schema_version": 1, "source": "crosspilot_validation_rounds", "rounds": list(rounds)}


def test_parse_complete_round_and_summary() -> None:
    records = parse_validation_rounds_document(_document(_round()))
    assert len(records) == 1
    assert records[0].claimId == "features"
    assert records[0].decision == "modify"
    summary = summarize_validation_rounds(records)
    assert "运营确认=1；待确认=0" in summary
    assert "features=1" in summary
    assert "modify=1" in summary
    assert "不生成消费者偏好或市场效果结论" in summary


def test_confirmed_real_round_requires_snapshot_binding() -> None:
    payload = {**_round(), "scenario": "real"}
    with pytest.raises(ValidationRoundError, match="market=de.*l1SnapshotSha256"):
        parse_validation_rounds_document(_document(payload))
    payload.update({"market": "de", "l1SnapshotSha256": "a" * 64})
    record = parse_validation_rounds_document(_document(payload))[0]
    assert record.market == "de"
    assert record.l1SnapshotSha256 == "a" * 64


def test_pending_draft_can_omit_result_fields() -> None:
    draft = _round()
    for field in ("observation", "decision", "rationale", "nextAction", "owner"):
        draft[field] = ""
    draft["confirmation"] = "pending"
    record = parse_validation_rounds_document(_document(draft))[0]
    assert record.confirmation == "pending"
    assert record.decision == ""


def test_prototype_observation_round_trip_and_summary(tmp_path: Path) -> None:
    payload = _round()
    payload["prototype"] = _prototype()
    record = parse_validation_rounds_document(_document(payload))[0]
    assert record.prototype is not None
    assert record.prototype.participantCode == "P01"
    assert record.prototype.order == "multi_first"
    assert "原型测试轮次=1" in summarize_validation_rounds([record])
    path = write_validation_round(record, tmp_path)
    archived = json.loads(path.read_text(encoding="utf-8"))
    assert archived["record"]["prototype"]["itemsLoaded"] == record.prototype.itemsLoaded
    assert archived["record_sha256"] == validation_round_digest(record)


def test_pending_round_can_save_incomplete_prototype() -> None:
    payload = _round()
    payload["confirmation"] = "pending"
    payload["prototype"] = {
        "participantCode": "P01",
        "order": "",
        "itemsLoaded": "",
        "retrieval": "",
        "friction": "",
    }
    record = parse_validation_rounds_document(_document(payload))[0]
    assert record.prototype is not None
    assert record.prototype.order == ""


def test_confirmed_round_requires_complete_prototype() -> None:
    payload = _round()
    payload["prototype"] = {**_prototype(), "friction": ""}
    with pytest.raises(ValidationRoundError, match="prototype 已确认但缺少"):
        parse_validation_rounds_document(_document(payload))


def test_prototype_rejects_invalid_order_and_contact_details() -> None:
    payload = _round()
    payload["prototype"] = {**_prototype(), "order": "random"}
    with pytest.raises(ValidationRoundError, match="prototype.order"):
        parse_validation_rounds_document(_document(payload))
    payload["prototype"] = {**_prototype(), "participantCode": "P01 test@example.com"}
    with pytest.raises(ValidationRoundError, match="prototype.participantCode 含联系方式"):
        parse_validation_rounds_document(_document(payload))


def test_confirmed_round_requires_result_fields() -> None:
    draft = _round()
    draft["rationale"] = ""
    with pytest.raises(ValidationRoundError, match="已确认但缺少"):
        parse_validation_rounds_document(_document(draft))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "bad-id"),
        ("createdAt", "2999-01-01T00:00:00Z"),
        ("createdAt", "2026-11-28T00:00:00"),
        ("scenario", "unknown"),
        ("claimId", "Bad Claim"),
        ("hypothesisTitle", "x" * 201),
        ("status", "unknown"),
        ("decision", "unknown"),
        ("confirmation", "unknown"),
        ("nextAction", "x" * 2001),
        ("owner", "x" * 201),
    ],
)
def test_rejects_invalid_round_fields(field: str, value: object) -> None:
    draft = _round()
    draft[field] = value
    with pytest.raises(ValidationRoundError, match=field):
        parse_validation_rounds_document(_document(draft))


@pytest.mark.parametrize(
    "text",
    ["联系 test@example.com", "电话 +49 170 1234567"],
)
def test_rejects_contact_details(text: str) -> None:
    draft = _round()
    draft["observation"] = text
    with pytest.raises(ValidationRoundError, match="联系方式"):
        parse_validation_rounds_document(_document(draft))


def test_rejects_duplicate_ids_and_wrong_schema() -> None:
    with pytest.raises(ValidationRoundError, match="重复轮次 ID"):
        parse_validation_rounds_document(_document(_round(), _round()))
    payload = _document(_round())
    payload["schema_version"] = 2
    with pytest.raises(ValidationRoundError, match="schema_version"):
        parse_validation_rounds_document(payload)


def test_archive_round_trip_is_hash_stable_and_idempotent(tmp_path: Path) -> None:
    export = tmp_path / "rounds.json"
    export.write_text(json.dumps(_document(_round()), ensure_ascii=False), encoding="utf-8")
    records = load_validation_rounds_file(export)
    path = write_validation_round(records[0], tmp_path / "archive")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["record_sha256"] == validation_round_digest(records[0])
    assert payload["record"]["id"] == "round-test-20261128"
    first_bytes = path.read_bytes()
    second_path = write_validation_round(records[0], tmp_path / "archive")
    assert second_path == path
    assert path.read_bytes() == first_bytes


def test_archive_loader_verifies_hashes(tmp_path: Path) -> None:
    record = parse_validation_rounds_document(_document(_round()))[0]
    path = write_validation_round(record, tmp_path)
    loaded = load_validation_rounds_archive(tmp_path)
    assert loaded == [record]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["record_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationRoundError, match="哈希不匹配"):
        load_validation_rounds_archive(tmp_path)


def test_archive_loader_rejects_duplicate_id_across_files(tmp_path: Path) -> None:
    first = parse_validation_rounds_document(_document(_round()))[0]
    second_payload = _round()
    second_payload["observation"] = "另一份内容 attempted to reuse the same round id."
    second = parse_validation_rounds_document(_document(second_payload))[0]
    write_validation_round(first, tmp_path)
    write_validation_round(second, tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == 2
    with pytest.raises(ValidationRoundError, match="跨归档重复"):
        load_validation_rounds_archive(tmp_path)


def test_archive_aggregate_fingerprint_is_stable_and_content_bound(tmp_path: Path) -> None:
    first = parse_validation_rounds_document(_document(_round()))[0]
    second_payload = _round()
    second_payload["id"] = "round-test-20261129"
    second = parse_validation_rounds_document(_document(second_payload))[0]
    write_validation_round(first, tmp_path)
    write_validation_round(second, tmp_path)
    loaded = load_validation_rounds_archive_data(tmp_path)
    expected = hashlib.sha256(
        "\n".join(sorted((validation_round_digest(first), validation_round_digest(second))))
        .encode("utf-8")
    ).hexdigest()
    assert loaded.archive_sha256 == expected
    assert load_validation_rounds_archive_data(tmp_path).archive_sha256 == expected

    third_payload = _round()
    third_payload["id"] = "round-test-20261130"
    third = parse_validation_rounds_document(_document(third_payload))[0]
    write_validation_round(third, tmp_path)
    assert load_validation_rounds_archive_data(tmp_path).archive_sha256 != expected
    assert load_validation_rounds_archive_data(tmp_path / "empty").archive_sha256 is None


def test_dry_run_summary_does_not_create_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from crosspilot_api.services import validation_round

    export = tmp_path / "rounds.json"
    export.write_text(json.dumps(_document(_round()), ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "archive"
    monkeypatch.setattr(
        "sys.argv",
        [
            "import_validation_rounds.py",
            "--input",
            str(export),
            "--output-dir",
            str(output),
            "--dry-run",
        ],
    )
    validation_round.main()
    assert "校验通过：1 轮" in capsys.readouterr().out
    assert not output.exists()


def test_created_at_allows_small_clock_skew() -> None:
    draft = _round()
    draft["createdAt"] = (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
    assert parse_validation_rounds_document(_document(draft))[0].id == draft["id"]
