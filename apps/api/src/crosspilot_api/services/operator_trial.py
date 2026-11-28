"""本地运营试用 JSON 的校验、摘要与归档。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from ..config import REPO_ROOT

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "operator_trials"
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+|00)\d[\d\s().-]{7,}\d")
_REQUIRED_FIELDS = (
    "trialDate",
    "operatorRole",
    "productMarket",
    "evidenceRefs",
    "decision",
    "prototypeObservation",
    "nextAction",
)


class OperatorTrialError(ValueError):
    """运营试用记录不满足验收或隐私要求。"""


@dataclass(frozen=True)
class OperatorTrialRecord:
    trialDate: str
    operatorRole: str
    productMarket: str
    evidenceRefs: str
    decision: str
    prototypeObservation: str
    nextAction: str
    confirmation: str


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperatorTrialError(f"{field} 必须为非空字符串")
    return value.strip()


def parse_operator_trial_document(payload: object) -> OperatorTrialRecord:
    if not isinstance(payload, dict):
        raise OperatorTrialError("运营试用文件顶层必须是 JSON 对象")
    values = {field: _required_text(payload.get(field), field) for field in _REQUIRED_FIELDS}
    try:
        trial_date = date.fromisoformat(values["trialDate"])
    except ValueError as exc:
        raise OperatorTrialError("trialDate 必须为 YYYY-MM-DD") from exc
    if trial_date > date.today():
        raise OperatorTrialError("trialDate 不得晚于今天")
    confirmation = _required_text(payload.get("confirmation"), "confirmation")
    if confirmation not in {"pending", "confirmed"}:
        raise OperatorTrialError("confirmation 仅允许 pending 或 confirmed")
    for field, value in values.items():
        if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
            raise OperatorTrialError(f"{field} 含联系方式，请剔除后再导入")
    return OperatorTrialRecord(**values, confirmation=confirmation)


def load_operator_trial_file(path: Path) -> OperatorTrialRecord:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OperatorTrialError(f"无法读取运营试用 JSON: {exc}") from exc
    if isinstance(payload, dict) and isinstance(payload.get("record"), dict):
        record = parse_operator_trial_document(payload["record"])
        expected_digest = payload.get("record_sha256")
        if not isinstance(expected_digest, str) or expected_digest != operator_trial_digest(record):
            raise OperatorTrialError("运营试用归档缺少或 record_sha256 不匹配")
        return record
    return parse_operator_trial_document(payload)


def operator_trial_digest(record: OperatorTrialRecord) -> str:
    canonical = json.dumps(
        asdict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_operator_trial(
    record: OperatorTrialRecord, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> Path:
    digest = operator_trial_digest(record)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", record.operatorRole).strip("_")[:40] or "operator"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.trialDate}_{record.confirmation}_{slug}_{digest[:10]}.json"
    payload = {
        "schema_version": 1,
        "source_api": "local_operator_trial_export",
        "imported_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "record_sha256": digest,
        "record": asdict(record),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OperatorTrialError(f"已有运营试用归档无法读取：{path}") from exc
        if not isinstance(existing, dict) or existing.get("record_sha256") != digest:
            raise OperatorTrialError(f"运营试用归档路径冲突：{path}") from None
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="校验并归档本地运营试用 JSON")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        record = load_operator_trial_file(args.input)
        if args.dry_run:
            print(
                f"校验通过：{record.trialDate} / {record.operatorRole} / "
                f"{record.confirmation} / sha256={operator_trial_digest(record)}"
            )
            return
        path = write_operator_trial(record, output_dir=args.output_dir)
    except OperatorTrialError as exc:
        parser.exit(2, f"试用记录导入失败：{exc}\n")
    print(f"已归档 {path}（仅本地，未上传）")


if __name__ == "__main__":
    main()
