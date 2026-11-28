"""验证轮次导出的校验、摘要与不可变本地归档。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..config import REPO_ROOT
from ..domain.evidence import DecisionState
from .claims import is_valid_claim_id

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "validation_rounds"
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+|00)\d[\d\s().-]{7,}\d")
_ROUND_ID_RE = re.compile(r"round-[a-z0-9-]{4,90}")
_SNAPSHOT_SHA_RE = re.compile(r"[0-9a-f]{64}")
_DECISIONS = {"", "keep", "modify", "pause", "reject"}
_SCENARIOS = {"real", "conflict", "limited"}
_REQUIRED_FIELDS = (
    "id",
    "createdAt",
    "scenario",
    "query",
    "claimId",
    "hypothesisTitle",
    "status",
    "evidenceRefs",
    "confirmation",
)
_CONFIRMED_FIELDS = ("observation", "decision", "rationale", "nextAction", "owner")


class ValidationRoundError(ValueError):
    """验证轮次不满足归档、隐私或契约要求。"""


@dataclass(frozen=True)
class PrototypeObservationRecord:
    participantCode: str
    order: str
    itemsLoaded: str
    retrieval: str
    friction: str


@dataclass(frozen=True)
class ValidationRoundRecord:
    id: str
    createdAt: str
    scenario: str
    query: str
    claimId: str
    hypothesisTitle: str
    status: str
    evidenceRefs: str
    observation: str
    decision: str
    rationale: str
    nextAction: str
    owner: str
    confirmation: str
    prototype: PrototypeObservationRecord | None = None
    market: str = ""
    l1SnapshotSha256: str | None = None


@dataclass(frozen=True)
class ValidationRoundsArchiveData:
    records: list[ValidationRoundRecord]
    archive_sha256: str | None = None


def _text(value: object, field: str, *, required: bool = True, max_length: int = 4000) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ValidationRoundError(f"{field} 必须是字符串")
    text = value.strip()
    if required and not text:
        raise ValidationRoundError(f"{field} 必须为非空字符串")
    if len(text) > max_length:
        raise ValidationRoundError(f"{field} 超过 {max_length} 字符")
    return text


def _parse_created_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationRoundError("createdAt 必须是 ISO 8601 时间") from exc
    if parsed.tzinfo is None:
        raise ValidationRoundError("createdAt 必须包含时区")
    if parsed.astimezone(UTC) > datetime.now(UTC) + timedelta(seconds=60):
        raise ValidationRoundError("createdAt 不得晚于当前时间")
    return parsed


def _parse_prototype(
    raw: object, prefix: str, *, confirmed: bool
) -> PrototypeObservationRecord | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValidationRoundError(f"{prefix}.prototype 必须是对象")
    values = {
        "participantCode": _text(
            raw.get("participantCode"),
            f"{prefix}.prototype.participantCode",
            required=False,
            max_length=100,
        ),
        "order": _text(
            raw.get("order"), f"{prefix}.prototype.order", required=False, max_length=20
        ),
        "itemsLoaded": _text(
            raw.get("itemsLoaded"),
            f"{prefix}.prototype.itemsLoaded",
            required=False,
            max_length=2000,
        ),
        "retrieval": _text(
            raw.get("retrieval"), f"{prefix}.prototype.retrieval", required=False, max_length=2000
        ),
        "friction": _text(
            raw.get("friction"), f"{prefix}.prototype.friction", required=False, max_length=2000
        ),
    }
    if values["order"] not in {"", "multi_first", "open_first"}:
        raise ValidationRoundError(f"{prefix}.prototype.order 非法")
    if confirmed:
        missing = [field for field, value in values.items() if not value]
        if missing:
            raise ValidationRoundError(f"{prefix}.prototype 已确认但缺少：{', '.join(missing)}")
    for field, value in values.items():
        if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
            raise ValidationRoundError(f"{prefix}.prototype.{field} 含联系方式，请剔除后再归档")
    return PrototypeObservationRecord(**values)


def parse_validation_round(raw: object, index: int = 0) -> ValidationRoundRecord:
    if not isinstance(raw, dict):
        raise ValidationRoundError(f"rounds[{index}] 必须是对象")
    prefix = f"rounds[{index}]"
    values = {
        field: _text(raw.get(field), f"{prefix}.{field}")
        for field in _REQUIRED_FIELDS
    }
    values.update(
        {
            field: _text(raw.get(field), f"{prefix}.{field}", required=False)
            for field in ("observation", "decision", "rationale", "nextAction", "owner")
        }
    )
    if not _ROUND_ID_RE.fullmatch(values["id"]):
        raise ValidationRoundError(f"{prefix}.id 非法")
    _parse_created_at(values["createdAt"])
    if values["scenario"] not in _SCENARIOS:
        raise ValidationRoundError(f"{prefix}.scenario 非法")
    if not is_valid_claim_id(values["claimId"]):
        raise ValidationRoundError(f"{prefix}.claimId 非法")
    if len(values["hypothesisTitle"]) > 200:
        raise ValidationRoundError(f"{prefix}.hypothesisTitle 超过 200 字符")
    if len(values["query"]) > 200:
        raise ValidationRoundError(f"{prefix}.query 超过 200 字符")
    if len(values["nextAction"]) > 2000:
        raise ValidationRoundError(f"{prefix}.nextAction 超过 2000 字符")
    if len(values["owner"]) > 200:
        raise ValidationRoundError(f"{prefix}.owner 超过 200 字符")
    if values["status"] not in {state.value for state in DecisionState}:
        raise ValidationRoundError(f"{prefix}.status 非法")
    if values["decision"] not in _DECISIONS:
        raise ValidationRoundError(f"{prefix}.decision 非法")
    if values["confirmation"] not in {"pending", "confirmed"}:
        raise ValidationRoundError(f"{prefix}.confirmation 非法")
    if values["confirmation"] == "confirmed":
        missing = [field for field in _CONFIRMED_FIELDS if not values[field]]
        if missing:
            raise ValidationRoundError(f"{prefix} 已确认但缺少：{', '.join(missing)}")
    market = _text(raw.get("market"), f"{prefix}.market", required=False, max_length=2)
    snapshot_raw = raw.get("l1SnapshotSha256")
    if snapshot_raw in (None, ""):
        l1_snapshot_sha256 = None
    elif isinstance(snapshot_raw, str) and _SNAPSHOT_SHA_RE.fullmatch(snapshot_raw):
        l1_snapshot_sha256 = snapshot_raw
    else:
        raise ValidationRoundError(f"{prefix}.l1SnapshotSha256 必须为 64 位小写十六进制")
    if values["scenario"] == "real" and values["confirmation"] == "confirmed":
        if market.lower() != "de" or l1_snapshot_sha256 is None:
            raise ValidationRoundError(
                f"{prefix} 已确认 real 轮次必须包含 market=de 与 l1SnapshotSha256"
            )
    for field, value in values.items():
        if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
            raise ValidationRoundError(f"{prefix}.{field} 含联系方式，请剔除后再归档")
    prototype = _parse_prototype(
        raw.get("prototype"), prefix, confirmed=values["confirmation"] == "confirmed"
    )
    return ValidationRoundRecord(
        **values,
        prototype=prototype,
        market=market,
        l1SnapshotSha256=l1_snapshot_sha256,
    )


def parse_validation_rounds_document(payload: object) -> list[ValidationRoundRecord]:
    if not isinstance(payload, dict):
        raise ValidationRoundError("验证轮次文件顶层必须是 JSON 对象")
    if payload.get("schema_version", 1) != 1:
        raise ValidationRoundError("schema_version 仅支持 1")
    rounds = payload.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        raise ValidationRoundError("rounds 必须是非空数组")
    if len(rounds) > 200:
        raise ValidationRoundError("单次最多归档 200 轮")
    records = [parse_validation_round(raw, index) for index, raw in enumerate(rounds)]
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValidationRoundError("同一文件存在重复轮次 ID")
    return records


def load_validation_rounds_file(path: Path) -> list[ValidationRoundRecord]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValidationRoundError(f"无法读取验证轮次 JSON: {exc}") from exc
    return parse_validation_rounds_document(payload)


def load_validation_rounds_archive_data(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> ValidationRoundsArchiveData:
    if not output_dir.is_dir():
        return ValidationRoundsArchiveData([])
    records: list[ValidationRoundRecord] = []
    digests: list[str] = []
    seen_ids: set[str] = set()
    for path in sorted(output_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationRoundError(f"无法读取轮次归档 {path}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("record"), dict):
            raise ValidationRoundError(f"轮次归档缺少 record：{path}")
        record = parse_validation_round(payload["record"])
        digest = validation_round_digest(record)
        expected = payload.get("record_sha256")
        if expected != digest:
            raise ValidationRoundError(f"轮次归档哈希不匹配：{path}")
        if record.id in seen_ids:
            raise ValidationRoundError(f"轮次 ID 跨归档重复：{record.id}（{path}）")
        seen_ids.add(record.id)
        records.append(record)
        digests.append(digest)
    archive_sha256 = (
        hashlib.sha256("\n".join(sorted(digests)).encode("utf-8")).hexdigest()
        if digests
        else None
    )
    return ValidationRoundsArchiveData(records, archive_sha256)


def load_validation_rounds_archive(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[ValidationRoundRecord]:
    return load_validation_rounds_archive_data(output_dir).records


def validation_round_digest(record: ValidationRoundRecord) -> str:
    canonical = json.dumps(
        asdict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_validation_round(
    record: ValidationRoundRecord, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> Path:
    digest = validation_round_digest(record)
    date_part = record.createdAt[:10]
    path = output_dir / f"{date_part}_{record.claimId}_{record.confirmation}_{digest[:12]}.json"
    payload = {
        "schema_version": 1,
        "source_api": "crosspilot_validation_rounds",
        "imported_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "record_sha256": digest,
        "record": asdict(record),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("record_sha256") != digest:
            raise ValidationRoundError(f"归档路径冲突：{path}") from None
    return path


def write_validation_rounds(
    records: list[ValidationRoundRecord], output_dir: Path = DEFAULT_OUTPUT_DIR
) -> list[Path]:
    return [write_validation_round(record, output_dir) for record in records]


def summarize_validation_rounds(records: list[ValidationRoundRecord]) -> str:
    confirmed = sum(record.confirmation == "confirmed" for record in records)
    pending = len(records) - confirmed
    prototype_count = sum(record.prototype is not None for record in records)
    by_claim: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    for record in records:
        by_claim[record.claimId] = by_claim.get(record.claimId, 0) + 1
        decision = record.decision or "undecided"
        by_decision[decision] = by_decision.get(decision, 0) + 1
    dates = sorted(record.createdAt[:10] for record in records)
    lines = [
        f"校验通过：{len(records)} 轮；运营确认={confirmed}；"
        f"待确认={pending}；原型测试轮次={prototype_count}",
        f"记录日期范围：{dates[0]} 至 {dates[-1]}",
        "按假设：" + "，".join(f"{claim}={count}" for claim, count in sorted(by_claim.items())),
        "按决定："
        + "，".join(f"{decision}={count}" for decision, count in sorted(by_decision.items())),
        "归档仅保存人工轮次，不生成消费者偏好或市场效果结论。",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="校验并归档工作台导出的验证轮次 JSON")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        records = load_validation_rounds_file(args.input)
        if args.dry_run:
            print(summarize_validation_rounds(records))
            return
        paths = write_validation_rounds(records, output_dir=args.output_dir)
    except ValidationRoundError as exc:
        parser.exit(2, f"验证轮次归档失败：{exc}\n")
    print(summarize_validation_rounds(records))
    for path in paths:
        print(f"已归档 {path}")


if __name__ == "__main__":
    main()
