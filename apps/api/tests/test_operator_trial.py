from __future__ import annotations

import json
from pathlib import Path

import pytest

from crosspilot_api.services.operator_trial import (
    OperatorTrialError,
    load_operator_trial_file,
    operator_trial_digest,
    parse_operator_trial_document,
    write_operator_trial,
)


def _payload() -> dict[str, object]:
    return {
        "trialDate": "2026-11-27",
        "operatorRole": "德国站品牌运营",
        "productMarket": "旅行收纳包 × 德国",
        "evidenceRefs": "review_id=r1; authorization_ref=brand-2026",
        "decision": "容量卖点改为精确尺寸，功能卖点保留，低价卖点暂停",
        "prototypeObservation": "多隔层版取物更快；开放空间版装载更灵活",
        "nextAction": "德国站运营负责人完成 5 人原型复测",
        "confirmation": "confirmed",
    }


def test_confirmed_record_round_trip_and_digest(tmp_path: Path) -> None:
    record = parse_operator_trial_document(_payload())
    path = write_operator_trial(record, output_dir=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["source_api"] == "local_operator_trial_export"
    assert payload["record_sha256"] == operator_trial_digest(record)
    assert load_operator_trial_file(path) == record
    assert "_confirmed_" in path.name


def test_rejects_incomplete_future_invalid_status_and_contact_details() -> None:
    missing = _payload()
    missing.pop("decision")
    with pytest.raises(OperatorTrialError, match="decision"):
        parse_operator_trial_document(missing)

    future = _payload()
    future["trialDate"] = "2999-01-01"
    with pytest.raises(OperatorTrialError, match="trialDate"):
        parse_operator_trial_document(future)

    invalid_status = _payload()
    invalid_status["confirmation"] = "done"
    with pytest.raises(OperatorTrialError, match="confirmation"):
        parse_operator_trial_document(invalid_status)

    contact = _payload()
    contact["evidenceRefs"] = "review_id=r1; test@example.com"
    with pytest.raises(OperatorTrialError, match="联系方式"):
        parse_operator_trial_document(contact)


def test_wrapped_archive_requires_hash_and_rejects_tampering(tmp_path: Path) -> None:
    record = parse_operator_trial_document(_payload())
    path = write_operator_trial(record, output_dir=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("record_sha256")
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(OperatorTrialError, match="record_sha256"):
        load_operator_trial_file(path)

    payload["record_sha256"] = operator_trial_digest(record)
    payload["record"]["decision"] = "被篡改的决定"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(OperatorTrialError, match="record_sha256"):
        load_operator_trial_file(path)


def test_operator_archive_does_not_overwrite_conflicting_path(tmp_path: Path) -> None:
    record = parse_operator_trial_document(_payload())
    path = write_operator_trial(record, output_dir=tmp_path)
    original = path.read_bytes()
    assert write_operator_trial(record, output_dir=tmp_path) == path
    assert path.read_bytes() == original
    changed = parse_operator_trial_document({**_payload(), "decision": "另一个决定"})
    changed_path = write_operator_trial(changed, output_dir=tmp_path)
    tampered = json.loads(changed_path.read_text(encoding="utf-8"))
    tampered["record_sha256"] = "0" * 64
    changed_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(OperatorTrialError, match="路径冲突"):
        write_operator_trial(changed, output_dir=tmp_path)
    assert path.read_bytes() == original


def test_pending_record_archives_as_draft(tmp_path: Path) -> None:
    payload = _payload()
    payload["confirmation"] = "pending"
    record = parse_operator_trial_document(payload)
    path = write_operator_trial(record, output_dir=tmp_path)
    assert "_pending_" in path.name
    assert json.loads(path.read_text(encoding="utf-8"))["record"]["confirmation"] == "pending"
