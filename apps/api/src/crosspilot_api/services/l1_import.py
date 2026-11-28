"""授权德国 L1 评论的本地导入、校验与快照加载。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from ..config import settings
from ..domain.evidence import (
    EvidenceCard,
    EvidenceLevel,
    Stance,
    StanceVotes,
    decide_by_claim,
)
from .claims import CLAIM_IDS, UNASSIGNED_CLAIM_ID, claim_ids_from_cards, is_valid_claim_id
from .evidence_dedup import find_stance_conflicts
from .stance_baseline import classify_claim_stance, classify_stance, review_triage
from .zhihu_client import sanitize_excerpt

L1_SNAPSHOT_DIR = settings.snapshot_dir / "l1"
_ILLEGAL_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')
AUTHORIZATION_SCOPES = (
    "internal_product_validation",
    "model_processing",
    "contest_demo",
    "public_display",
)
INTERNAL_AUTHORIZATION_SCOPE = "internal_product_validation"
_SNAPSHOT_HASH_FIELDS = (
    "schema_version",
    "source_api",
    "query",
    "market",
    "source_id",
    "authorization",
    "authorization_ref",
    "authorization_scope",
    "claim_terms",
    "input_sha256",
    "source_snapshot_sha256",
    "is_demo_data",
    "cards",
)
_SNAPSHOT_VERSION_FIELDS = (*_SNAPSHOT_HASH_FIELDS, "generated_at_utc")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_digest(payload: dict[str, object]) -> str:
    stable = {field: payload.get(field) for field in _SNAPSHOT_HASH_FIELDS}
    canonical = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def snapshot_version_digest(payload: dict[str, object]) -> str:
    stable = {field: payload.get(field) for field in _SNAPSHOT_VERSION_FIELDS}
    canonical = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class L1ImportError(ValueError):
    """评论导入不满足来源、市场或契约要求。"""


@dataclass(frozen=True)
class L1SnapshotData:
    cards: list[EvidenceCard]
    authorization_scope: tuple[str, ...]
    notice: str | None = None
    snapshot_sha256: str | None = None


def _parse_authorization_scope(
    raw: object,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    value = raw if raw not in (None, "") else list(default)
    if not isinstance(value, list) or not value:
        raise L1ImportError("authorization_scope 必须为非空数组")
    if not all(isinstance(scope, str) for scope in value):
        raise L1ImportError("authorization_scope 必须全部为字符串")
    scope = tuple(dict.fromkeys(value))
    invalid = [item for item in scope if item not in AUTHORIZATION_SCOPES]
    if invalid:
        raise L1ImportError(f"authorization_scope 非法：{', '.join(invalid)}")
    if INTERNAL_AUTHORIZATION_SCOPE not in scope:
        raise L1ImportError("authorization_scope 未覆盖 internal_product_validation")
    return scope


def _resolve_authorization_scope(
    raw: object,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    if raw in (None, ""):
        return _parse_authorization_scope(None, default)
    document_scope = _parse_authorization_scope(raw, default)
    if default and set(default) != set(document_scope):
        raise L1ImportError("命令行授权范围与文件 authorization_scope 不一致")
    return document_scope


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise L1ImportError(f"{field} 必须为非空字符串")
    return value.strip()


def _parse_claim_terms(raw: object) -> dict[str, tuple[str, ...]]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise L1ImportError("claim_terms 必须为对象")
    parsed: dict[str, tuple[str, ...]] = {}
    for raw_claim_id, raw_terms in raw.items():
        if not isinstance(raw_claim_id, str) or not is_valid_claim_id(raw_claim_id):
            raise L1ImportError("claim_terms 的 claim_id 非法")
        if raw_claim_id in CLAIM_IDS or raw_claim_id == UNASSIGNED_CLAIM_ID:
            raise L1ImportError("claim_terms 只能声明自定义卖点，不能覆盖内置或未归属 ID")
        if not isinstance(raw_terms, list) or not 1 <= len(raw_terms) <= 20:
            raise L1ImportError(f"claim_terms.{raw_claim_id} 必须为 1–20 个术语")
        terms: list[str] = []
        for index, raw_term in enumerate(raw_terms):
            term = _required_text(raw_term, f"claim_terms.{raw_claim_id}[{index}]")
            if len(term) > 80 or any(ord(char) < 32 for char in term):
                raise L1ImportError(
                    f"claim_terms.{raw_claim_id}[{index}] 不超过 80 字符且不得含控制字符"
                )
            terms.append(term)
        parsed[raw_claim_id] = tuple(dict.fromkeys(terms))
    return parsed


def claim_terms_from_cards(cards: list[EvidenceCard]) -> dict[str, tuple[str, ...]]:
    """从卡片还原自定义术语表，并拒绝同一卖点使用不一致范围。"""
    seen: dict[str, tuple[str, ...]] = {}
    for card in cards:
        claim_id = card.claim_id
        if card.aspect_terms and (
            not claim_id or claim_id in CLAIM_IDS or claim_id == UNASSIGNED_CLAIM_ID
        ):
            raise L1ImportError("aspect_terms 只能归属于自定义卖点")
        if not claim_id or claim_id in CLAIM_IDS or claim_id == UNASSIGNED_CLAIM_ID:
            continue
        if not is_valid_claim_id(claim_id):
            raise L1ImportError(f"自定义 claim_id 非法：{claim_id}")
        if claim_id in seen and seen[claim_id] != card.aspect_terms:
            raise L1ImportError(f"同一自定义卖点的 aspect_terms 不一致：{claim_id}")
        seen[claim_id] = card.aspect_terms
    return {claim_id: terms for claim_id, terms in seen.items() if terms}


def _parse_date(value: object, field: str) -> date:
    text = _required_text(value, field)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise L1ImportError(f"{field} 必须为 YYYY-MM-DD") from exc


def _card_from_raw(
    raw: object,
    index: int,
    defaults: dict[str, str],
    *,
    claim_terms: dict[str, tuple[str, ...]],
    preserve_classification: bool = False,
) -> EvidenceCard:
    if not isinstance(raw, dict):
        raise L1ImportError(f"cards[{index}] 不是对象")
    if "aspect_terms" in raw:
        raise L1ImportError(f"cards[{index}].aspect_terms 请通过顶层 claim_terms 声明")
    review_id = _required_text(raw.get("review_id"), f"cards[{index}].review_id")
    relevance = raw.get("relevance", "relevant")
    if relevance not in {"relevant", "irrelevant"}:
        raise L1ImportError(f"cards[{index}].relevance 非法: {relevance}")
    if relevance == "relevant":
        raw_claim_id = raw.get("claim_id")
        if raw_claim_id is None or (
            isinstance(raw_claim_id, str) and not raw_claim_id.strip()
        ):
            claim_id = UNASSIGNED_CLAIM_ID
        else:
            claim_id = _required_text(raw_claim_id, f"cards[{index}].claim_id")
            if not is_valid_claim_id(claim_id):
                raise L1ImportError(
                    f"cards[{index}].claim_id 非法：仅限小写字母、数字、- 和 _，最长 64 位"
                )
    else:
        if raw.get("claim_id") not in (None, ""):
            raise L1ImportError(f"cards[{index}] 不相关评论不得归属到卖点")
        claim_id = None
    aspect_terms = (
        claim_terms.get(claim_id, ())
        if relevance == "relevant" and claim_id
        else ()
    )
    excerpt = sanitize_excerpt(_required_text(raw.get("excerpt"), f"cards[{index}].excerpt"))
    if not excerpt:
        raise L1ImportError(f"cards[{index}].excerpt 清洗后为空")
    source_url = _required_text(raw.get("source_url"), f"cards[{index}].source_url")
    if not source_url.startswith("https://"):
        raise L1ImportError(f"cards[{index}].source_url 必须为 https")
    market = _required_text(raw.get("market", defaults.get("market")), f"cards[{index}].market")
    if market.lower() != "de":
        raise L1ImportError(f"cards[{index}].market 必须为 de")
    source_id = _required_text(
        raw.get("source_id", defaults.get("source_id")), f"cards[{index}].source_id"
    )
    authorization = _required_text(
        raw.get("authorization", defaults.get("authorization")),
        f"cards[{index}].authorization",
    )
    authorization_ref = _required_text(
        raw.get("authorization_ref", defaults.get("authorization_ref")),
        f"cards[{index}].authorization_ref",
    )
    if raw.get("is_demo_data", False) is not False:
        raise L1ImportError(f"cards[{index}] 不得标记为演示数据")
    language = _required_text(raw.get("language", "de"), f"cards[{index}].language")
    published_on = _parse_date(raw.get("published_on"), f"cards[{index}].published_on")
    if published_on > date.today():
        raise L1ImportError(f"cards[{index}].published_on 不得晚于今天")

    rule_result = (
        classify_claim_stance(
            excerpt,
            claim_id or UNASSIGNED_CLAIM_ID,
            aspect_terms or None,
        )
        if relevance == "relevant"
        else classify_stance(excerpt)
    )
    rule_stance = rule_result.stance if relevance == "relevant" else Stance.INSUFFICIENT
    raw_stance = raw.get("stance")
    if raw_stance in (None, ""):
        override_stance = None
    elif not isinstance(raw_stance, str):
        raise L1ImportError(f"cards[{index}].stance 非法")
    else:
        try:
            override_stance = Stance(raw_stance)
        except ValueError as exc:
            raise L1ImportError(f"cards[{index}].stance 非法：{raw_stance}") from exc
    if relevance == "irrelevant" and override_stance not in (None, Stance.INSUFFICIENT):
        raise L1ImportError(f"cards[{index}] 不相关评论不得标注支持/反对")

    if not preserve_classification and any(
        key in raw
        for key in (
            "classification_method",
            "classification_note",
            "stance_votes",
            "annotator_agreement",
            "review_required",
            "review_reasons",
        )
    ):
        raise L1ImportError(f"cards[{index}] 分类方法由导入器生成，不接受外部覆盖")

    method_value = raw.get("classification_method") if preserve_classification else None
    if method_value in (None, ""):
        classification_method = "manual" if override_stance is not None else "rule"
    elif not isinstance(method_value, str) or method_value not in {
        "rule",
        "manual",
        "llm",
        "ensemble",
    }:
        raise L1ImportError(f"cards[{index}].classification_method 非法")
    else:
        classification_method = method_value
    if classification_method == "manual" and override_stance is None:
        raise L1ImportError(f"cards[{index}] 人工分类缺少 stance")

    votes_value = raw.get("stance_votes") if preserve_classification else None
    if votes_value in (None, ""):
        stance_votes = StanceVotes(rule=rule_stance)
    elif not isinstance(votes_value, dict):
        raise L1ImportError(f"cards[{index}].stance_votes 非法")
    else:
        vote_rule = votes_value.get("rule")
        vote_llm = votes_value.get("llm")
        try:
            parsed_rule = Stance(vote_rule) if isinstance(vote_rule, str) else None
        except ValueError as exc:
            raise L1ImportError(f"cards[{index}].stance_votes.rule 非法") from exc
        if parsed_rule is None:
            raise L1ImportError(f"cards[{index}].stance_votes.rule 非法")
        if vote_llm in (None, ""):
            parsed_llm = None
        elif isinstance(vote_llm, str):
            try:
                parsed_llm = Stance(vote_llm)
            except ValueError as exc:
                raise L1ImportError(f"cards[{index}].stance_votes.llm 非法") from exc
        else:
            raise L1ImportError(f"cards[{index}].stance_votes.llm 非法")
        stance_votes = StanceVotes(rule=parsed_rule, llm=parsed_llm)

    agreement_value = raw.get("annotator_agreement") if preserve_classification else None
    if agreement_value not in (None, "") and not isinstance(agreement_value, bool):
        raise L1ImportError(f"cards[{index}].annotator_agreement 非法")
    annotator_agreement = (
        agreement_value
        if isinstance(agreement_value, bool)
        else (override_stance == rule_stance if classification_method == "manual" else None)
    )

    note_field = "classification_note" if preserve_classification else "stance_note"
    note_value = raw.get(note_field)
    if note_value in (None, ""):
        classification_note = None
    elif not isinstance(note_value, str):
        raise L1ImportError(f"cards[{index}] 分类说明必须是字符串")
    else:
        classification_note = sanitize_excerpt(note_value)[:500]
        if not classification_note:
            raise L1ImportError(f"cards[{index}] 分类说明清洗后为空")
        if classification_method != "manual":
            raise L1ImportError(f"cards[{index}] 分类说明仅用于人工复核")
    if classification_method == "manual" and classification_note is None:
        raise L1ImportError(f"cards[{index}] 人工立场覆盖必须提供 {note_field}")

    review_required: bool | None = None
    review_reasons: tuple[str, ...] = ()
    if preserve_classification:
        review_value = raw.get("review_required")
        if review_value not in (None, ""):
            if not isinstance(review_value, bool):
                raise L1ImportError(f"cards[{index}].review_required 非法")
            review_required = review_value
        reasons_value = raw.get("review_reasons")
        if reasons_value not in (None, ""):
            if not isinstance(reasons_value, list) or not all(
                isinstance(reason, str) for reason in reasons_value
            ):
                raise L1ImportError(f"cards[{index}].review_reasons 非法")
            review_reasons = tuple(reason.strip() for reason in reasons_value if reason.strip())
            if review_reasons and review_required is None:
                raise L1ImportError(f"cards[{index}].review_reasons 需要 review_required")
    if review_required is None:
        if classification_method == "manual":
            review_required = False
            review_reasons = ("人工复核已完成",)
        elif relevance == "irrelevant":
            review_required = False
            review_reasons = ("不相关评论由输入方标注",)
        else:
            triage = review_triage(excerpt, rule_result)
            review_required = triage.required
            review_reasons = triage.reasons

    stance = override_stance or rule_stance
    if relevance == "irrelevant":
        stance = Stance.INSUFFICIENT
    return EvidenceCard(
        excerpt=excerpt,
        source_url=source_url,
        language=language,
        published_on=published_on,
        level=EvidenceLevel.L1,
        sample_size=1,
        stance=stance,
        is_demo_data=False,
        stance_votes=stance_votes,
        annotator_agreement=annotator_agreement,
        classification_method=classification_method,
        classification_note=classification_note,
        review_required=review_required,
        review_reasons=review_reasons,
        review_id=review_id,
        claim_id=claim_id,
        aspect_terms=aspect_terms,
        market="de",
        source_id=source_id,
        authorization=authorization,
        authorization_ref=authorization_ref,
        relevance=relevance,
    )


def _flag_stance_conflicts(cards: list[EvidenceCard]) -> list[EvidenceCard]:
    """同卖点重复评论出现不同立场时强制复核，不自动合并或改票。"""
    flagged = list(cards)
    by_claim: dict[str, list[tuple[int, EvidenceCard]]] = {}
    for index, card in enumerate(cards):
        if card.relevance == "relevant" and card.claim_id:
            by_claim.setdefault(card.claim_id, []).append((index, card))
    for _claim_id, indexed_cards in by_claim.items():
        conflicts = find_stance_conflicts(
            [card.excerpt for _, card in indexed_cards],
            [card.stance.value for _, card in indexed_cards],
        )
        for group in conflicts:
            review_ids = [
                indexed_cards[local_index][1].review_id or "unknown"
                for local_index in group
            ]
            reason = (
                f"同卖点重复评论出现不同立场（{', '.join(review_ids)}），"
                "需人工确认后再计入分歧"
            )
            for local_index in group:
                index, card = indexed_cards[local_index]
                reasons = tuple(dict.fromkeys((*card.review_reasons, reason)))
                flagged[index] = replace(
                    card,
                    review_required=True,
                    review_reasons=reasons,
                )
    return flagged


def parse_import_document(
    payload: object,
    *,
    default_query: str = "",
    default_source_id: str = "",
    default_authorization: str = "",
    default_authorization_ref: str = "",
    default_authorization_scope: tuple[str, ...] = (),
    preserve_classification: bool = False,
) -> tuple[str, list[EvidenceCard]]:
    if not isinstance(payload, dict):
        raise L1ImportError("导入文件顶层必须是 JSON 对象")
    if payload.get("is_demo_data", False) is not False:
        raise L1ImportError("真实 L1 导入文件不得标记为演示数据")
    query = _required_text(payload.get("query", default_query), "query")
    defaults = {
        "market": _required_text(payload.get("market", "de"), "market"),
        "source_id": _required_text(payload.get("source_id", default_source_id), "source_id"),
        "authorization": _required_text(
            payload.get("authorization", default_authorization), "authorization"
        ),
        "authorization_ref": _required_text(
            payload.get("authorization_ref", default_authorization_ref),
            "authorization_ref",
        ),
    }
    if defaults["market"].lower() != "de":
        raise L1ImportError("market 必须为 de")
    _resolve_authorization_scope(
        payload.get("authorization_scope"),
        default_authorization_scope,
    )
    source_snapshot_sha256 = payload.get("source_snapshot_sha256")
    if source_snapshot_sha256 not in (None, "") and (
        not isinstance(source_snapshot_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_snapshot_sha256) is None
    ):
        raise L1ImportError("source_snapshot_sha256 必须为 64 位小写十六进制")
    claim_terms = _parse_claim_terms(payload.get("claim_terms"))
    raw_cards = payload.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        raise L1ImportError("cards 必须为非空数组")
    cards = [
        _card_from_raw(
            raw,
            index,
            defaults,
            claim_terms=claim_terms,
            preserve_classification=preserve_classification,
        )
        for index, raw in enumerate(raw_cards)
    ]
    cards = _flag_stance_conflicts(cards)
    used_claim_ids = {
        card.claim_id for card in cards if card.claim_id and card.relevance == "relevant"
    }
    unused_terms = sorted(set(claim_terms) - used_claim_ids)
    if unused_terms:
        raise L1ImportError(f"claim_terms 含未使用卖点：{', '.join(unused_terms)}")
    review_ids = [
        _required_text(raw.get("review_id"), "review_id")
        for raw in raw_cards
        if isinstance(raw, dict)
    ]
    if len(review_ids) != len(set(review_ids)):
        raise L1ImportError("review_id 不得重复")
    return query, cards


def load_import_payload(path: Path) -> object:
    if path.suffix.lower() == ".json":
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise L1ImportError(f"无法读取 JSON: {exc}") from exc
    if path.suffix.lower() != ".csv":
        raise L1ImportError("仅支持 .json 或 .csv")
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise L1ImportError(f"无法读取 CSV: {exc}") from exc
    return {"cards": rows}


def load_import_file(
    path: Path,
    *,
    query: str = "",
    source_id: str = "",
    authorization: str = "",
    authorization_ref: str = "",
    authorization_scope: tuple[str, ...] = (),
) -> tuple[str, list[EvidenceCard]]:
    payload = load_import_payload(path)
    return parse_import_document(
        payload,
        default_query=query,
        default_source_id=source_id,
        default_authorization=authorization,
        default_authorization_ref=authorization_ref,
        default_authorization_scope=authorization_scope,
    )


def _serialize_card(card: EvidenceCard) -> dict[str, object]:
    return {
        "review_id": card.review_id,
        "claim_id": card.claim_id,
        "excerpt": card.excerpt,
        "source_url": card.source_url,
        "published_on": card.published_on.isoformat(),
        "language": card.language,
        "market": card.market,
        "source_id": card.source_id,
        "authorization": card.authorization,
        "authorization_ref": card.authorization_ref,
        "level": card.level.value,
        "sample_size": card.sample_size,
        "stance": card.stance.value,
        "stance_votes": (
            {
                "rule": card.stance_votes.rule.value,
                "llm": card.stance_votes.llm.value if card.stance_votes.llm else None,
            }
            if card.stance_votes is not None
            else None
        ),
        "annotator_agreement": card.annotator_agreement,
        "classification_method": card.classification_method,
        "classification_note": card.classification_note,
        "review_required": card.review_required,
        "review_reasons": list(card.review_reasons),
        "relevance": card.relevance,
        "is_demo_data": False,
    }


def validate_review_lineage(
    cards: list[EvidenceCard],
    *,
    query: str,
    source_snapshot_sha256: str | None,
    authorization_scope: tuple[str, ...],
    snapshot_dir: Path = L1_SNAPSHOT_DIR,
) -> None:
    if source_snapshot_sha256 is None:
        return
    if re.fullmatch(r"[0-9a-f]{64}", source_snapshot_sha256) is None:
        raise L1ImportError("source_snapshot_sha256 必须为 64 位小写十六进制")
    parent_payload: dict[str, object] | None = None
    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise L1ImportError(f"来源快照无法读取：{path}") from exc
        if (
            isinstance(candidate, dict)
            and candidate.get("query") == query
            and candidate.get("record_sha256") == source_snapshot_sha256
            and snapshot_digest(candidate) == source_snapshot_sha256
            and candidate.get("version_sha256") == snapshot_version_digest(candidate)
        ):
            parent_payload = candidate
            break
    if parent_payload is None:
        raise L1ImportError("source_snapshot_sha256 未匹配到已验证来源快照")
    try:
        _, parent_cards = parse_import_document(parent_payload, preserve_classification=True)
        parent_scope = _parse_authorization_scope(parent_payload.get("authorization_scope"), ())
        generated_at = parent_payload.get("generated_at_utc")
        generated_dt = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
    except (L1ImportError, ValueError) as exc:
        raise L1ImportError(f"来源快照校验失败：{exc}") from exc
    if generated_dt.tzinfo is None or generated_dt > datetime.now(UTC) + timedelta(seconds=60):
        raise L1ImportError("来源快照 generated_at_utc 缺少时区或晚于当前时间")
    if set(authorization_scope) != set(parent_scope):
        raise L1ImportError("复核回导不得扩大或改变来源快照的授权范围")
    parent_by_id = {card.review_id: card for card in parent_cards if card.review_id}
    immutable_fields = (
        "excerpt",
        "source_url",
        "published_on",
        "language",
        "market",
        "source_id",
        "authorization",
        "authorization_ref",
    )
    for card in cards:
        if not card.review_id:
            raise L1ImportError("复核评论缺少 review_id")
        parent = parent_by_id.get(card.review_id)
        if parent is None:
            raise L1ImportError(f"复核评论不在来源快照中：{card.review_id or 'unknown'}")
        if any(getattr(card, field) != getattr(parent, field) for field in immutable_fields):
            raise L1ImportError(f"复核评论改动了来源快照的原文或溯源字段：{card.review_id}")


def write_snapshot(
    cards: list[EvidenceCard],
    *,
    query: str,
    source_id: str,
    authorization: str,
    authorization_ref: str,
    authorization_scope: tuple[str, ...],
    input_sha256: str | None = None,
    source_snapshot_sha256: str | None = None,
    output_dir: Path = L1_SNAPSHOT_DIR,
    versioned: bool = False,
) -> Path:
    authorization_scope = _parse_authorization_scope(
        list(authorization_scope),
        (),
    )
    for index, card in enumerate(cards):
        if card.level is not EvidenceLevel.L1 or card.is_demo_data:
            raise L1ImportError(f"cards[{index}] 必须是 is_demo_data=false 的真实 L1 卡")
        if not all(
            (
                card.review_id,
                card.source_url,
                card.published_on,
                card.market,
                card.source_id,
                card.authorization,
                card.authorization_ref,
            )
        ):
            raise L1ImportError(f"cards[{index}] 缺少真实 L1 溯源字段")
    validate_review_lineage(
        cards,
        query=query,
        source_snapshot_sha256=source_snapshot_sha256,
        authorization_scope=authorization_scope,
        snapshot_dir=output_dir,
    )
    claim_terms = claim_terms_from_cards(cards)
    serialized_claim_terms = {
        claim_id: list(terms) for claim_id, terms in claim_terms.items()
    }
    if input_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", input_sha256):
        raise L1ImportError("input_sha256 必须为 64 位小写十六进制")
    query, validated = parse_import_document(
        {
            "query": query,
            "market": "de",
            "source_id": source_id,
            "authorization": authorization,
            "authorization_ref": authorization_ref,
            "authorization_scope": list(authorization_scope),
            "claim_terms": serialized_claim_terms,
            "cards": [_serialize_card(card) for card in cards],
        },
        preserve_classification=True,
    )
    filename = _ILLEGAL_FILENAME_RE.sub("_", query.strip()) or "untitled"
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "schema_version": 1,
        "generated_at_utc": now.isoformat(
            timespec="microseconds" if versioned else "seconds"
        ).replace("+00:00", "Z"),
        "source_api": "local_authorized_import",
        "query": query,
        "market": "de",
        "source_id": source_id,
        "authorization": authorization,
        "authorization_ref": authorization_ref,
        "authorization_scope": list(authorization_scope),
        "claim_terms": serialized_claim_terms,
        "input_sha256": input_sha256,
        "source_snapshot_sha256": source_snapshot_sha256,
        "is_demo_data": False,
        "cards": [_serialize_card(card) for card in validated],
    }
    digest = snapshot_digest(payload)
    payload["record_sha256"] = digest
    payload["version_sha256"] = snapshot_version_digest(payload)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if versioned:
        stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
        path = output_dir / f"{filename}_{stamp}_{digest[:12]}.json"
        for existing_path in sorted(output_dir.glob(f"{filename}_*.json")):
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise L1ImportError(f"已有版本无法读取：{existing_path}") from exc
            if (
                isinstance(existing, dict)
                and existing.get("query") == query
                and existing.get("record_sha256") == payload["record_sha256"]
                and snapshot_digest(existing) == payload["record_sha256"]
            ):
                return existing_path
    else:
        path = output_dir / f"{filename}.json"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except FileExistsError:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise L1ImportError(f"快照已存在但无法读取，禁止覆盖：{path}") from exc
        if (
            not isinstance(existing, dict)
            or existing.get("record_sha256") != payload["record_sha256"]
            or snapshot_digest(existing) != payload["record_sha256"]
        ):
            raise L1ImportError(
                f"快照已存在且内容不同，禁止覆盖：{path}；"
                "请使用 --versioned 写入新版本"
            ) from None
        return path
    return path


def load_l1_snapshot_data(
    query: str, snapshot_dir: Path = L1_SNAPSHOT_DIR
) -> L1SnapshotData:
    if not snapshot_dir.is_dir():
        return L1SnapshotData(
            [],
            (),
            "德国 L1 快照目录不存在；请先用 scripts/import_l1_reviews.py 导入授权评论。",
        )
    filename = _ILLEGAL_FILENAME_RE.sub("_", query.strip()) or "untitled"
    candidates: list[
        tuple[datetime, str, list[EvidenceCard], tuple[str, ...], str]
    ] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            if path.stem == filename or path.stem.startswith(f"{filename}_"):
                return L1SnapshotData(
                    [],
                    (),
                    f"德国 L1 快照损坏（{path}）：无法读取 JSON：{exc}",
                )
            continue
        if not isinstance(payload, dict) or payload.get("query") != query:
            continue
        expected = payload.get("record_sha256")
        expected_version = payload.get("version_sha256")
        if (
            not isinstance(expected, str)
            or expected != snapshot_digest(payload)
            or not isinstance(expected_version, str)
            or expected_version != snapshot_version_digest(payload)
        ):
            return L1SnapshotData(
                [],
                (),
                f"德国 L1 快照损坏（{path}）：record_sha256 或 version_sha256 缺失/不匹配",
            )
        try:
            _, cards = parse_import_document(payload, preserve_classification=True)
            scope = _parse_authorization_scope(payload.get("authorization_scope"), ())
        except L1ImportError as exc:
            return L1SnapshotData([], (), f"德国 L1 快照损坏（{path}）：{exc}")
        generated_at = payload.get("generated_at_utc")
        if not isinstance(generated_at, str) or not generated_at:
            return L1SnapshotData([], (), f"德国 L1 快照损坏（{path}）：缺少 generated_at_utc")
        try:
            generated_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError as exc:
            return L1SnapshotData(
                [],
                (),
                f"德国 L1 快照损坏（{path}）：generated_at_utc 非法：{exc}",
            )
        if generated_dt.tzinfo is None:
            return L1SnapshotData(
                [],
                (),
                f"德国 L1 快照损坏（{path}）：generated_at_utc 缺少时区",
            )
        if generated_dt > datetime.now(UTC) + timedelta(seconds=60):
            return L1SnapshotData(
                [],
                (),
                f"德国 L1 快照损坏（{path}）：generated_at_utc 晚于当前时间",
            )
        candidates.append((generated_dt, path.name, cards, scope, expected))
    if not candidates:
        return L1SnapshotData(
            [],
            (),
            f"未找到「{query}」的德国 L1 授权评论快照；当前结论保持证据不足。",
        )
    _, _, cards, scope, snapshot_sha256 = max(
        candidates, key=lambda item: (item[0], item[1])
    )
    return L1SnapshotData(cards, scope, snapshot_sha256=snapshot_sha256)


def load_l1_snapshot(
    query: str, snapshot_dir: Path = L1_SNAPSHOT_DIR
) -> tuple[list[EvidenceCard], str | None]:
    snapshot = load_l1_snapshot_data(query, snapshot_dir)
    return snapshot.cards, snapshot.notice


def summarize_l1_import(
    query: str,
    cards: list[EvidenceCard],
    *,
    input_sha256: str | None = None,
    authorization_scope: tuple[str, ...] = (),
) -> str:
    """生成不写盘的导入验收摘要，按真实判定口径报告每条卖点样本。"""
    claim_ids = claim_ids_from_cards(cards)
    decisions = decide_by_claim(cards, claim_ids)
    lines = [f"校验通过：{len(cards)} 条评论，query={query}"]
    if input_sha256:
        lines.append(f"- 输入文件 SHA-256：{input_sha256}")
    if authorization_scope:
        lines.append(f"- 授权范围：{', '.join(authorization_scope)}")
    for claim_id in claim_ids:
        claim_cards = [
            card
            for card in cards
            if card.claim_id == claim_id and card.relevance == "relevant"
        ]
        decision = decisions[claim_id]
        support = sum(
            card.stance is Stance.SUPPORT
            and (info is None or info.is_canonical)
            for card, info in zip(claim_cards, decision.dedup_by_card, strict=True)
        )
        oppose = sum(
            card.stance is Stance.OPPOSE
            and (info is None or info.is_canonical)
            for card, info in zip(claim_cards, decision.dedup_by_card, strict=True)
        )
        lines.append(
            f"- {claim_id}: L1={decision.n_l1}，支持={support}，反对={oppose}，"
            f"无极性={decision.n_insufficient}，去重簇={decision.dedup_clusters}，"
            f"重复={decision.dedup_duplicated}，门禁={decision.gate_status.value}，"
            f"判定={decision.state.value}"
        )
    unassigned = sum(
        card.claim_id == UNASSIGNED_CLAIM_ID and card.relevance == "relevant"
        for card in cards
    )
    irrelevant = sum(card.relevance == "irrelevant" for card in cards)
    lines.append(f"- 未归属={unassigned}，不相关={irrelevant}（均不进入卖点判定）")
    relevant_cards = [card for card in cards if card.relevance == "relevant"]
    manual = sum(card.classification_method == "manual" for card in relevant_cards)
    rule = sum(card.classification_method == "rule" for card in relevant_cards)
    disagreements = sum(
        card.classification_method == "manual" and card.annotator_agreement is False
        for card in relevant_cards
    )
    lines.append(
        f"- 分类方法：人工复核={manual}，规则基线={rule}，人工与规则不一致={disagreements}"
    )
    review_required = sum(card.review_required is True for card in relevant_cards)
    lines.append(
        f"- 复核分流：建议人工复核={review_required}，"
        f"低复核优先级={len(relevant_cards) - review_required}"
    )
    if cards:
        dates = [card.published_on.isoformat() for card in cards]
        lines.append(f"- 评论日期范围：{min(dates)} 至 {max(dates)}")
    if any(decision.n_polarized < 30 for decision in decisions.values()):
        lines.append("提示：仍有卖点低于 n≥30 门禁；可导入用于问题生成，但不能形成偏好结论。")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入合法取得的德国消费者评论")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--query", default="")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--authorization", default="")
    parser.add_argument(
        "--authorization-ref",
        default="",
        help="授权合同编号、品牌导出记录或平台书面许可编号（必填）",
    )
    parser.add_argument(
        "--authorization-scope",
        action="append",
        choices=AUTHORIZATION_SCOPES,
        default=[],
        help="可重复声明授权用途；必须包含 internal_product_validation",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--versioned",
        action="store_true",
        help="保留旧快照并写入新版本；加载器使用最新已验证版本",
    )
    args = parser.parse_args()
    authorization_scope = tuple(dict.fromkeys(args.authorization_scope))
    try:
        try:
            input_sha256 = sha256_file(args.input)
        except OSError as exc:
            raise L1ImportError(f"无法读取输入文件：{exc}") from exc
        payload = load_import_payload(args.input)
        query, cards = parse_import_document(
            payload,
            default_query=args.query,
            default_source_id=args.source_id,
            default_authorization=args.authorization,
            default_authorization_ref=args.authorization_ref,
            default_authorization_scope=authorization_scope,
        )
        authorization_scope = _resolve_authorization_scope(
            payload.get("authorization_scope") if isinstance(payload, dict) else None,
            authorization_scope,
        )
        raw_source_snapshot_sha256 = (
            payload.get("source_snapshot_sha256") if isinstance(payload, dict) else None
        )
        source_snapshot_sha256 = (
            raw_source_snapshot_sha256
            if isinstance(raw_source_snapshot_sha256, str)
            else None
        )
        validate_review_lineage(
            cards,
            query=query,
            source_snapshot_sha256=source_snapshot_sha256,
            authorization_scope=authorization_scope,
        )
        if args.dry_run:
            print(
                summarize_l1_import(
                    query,
                    cards,
                    input_sha256=input_sha256,
                    authorization_scope=authorization_scope,
                )
            )
            return
        path = write_snapshot(
            cards,
            query=query,
            source_id=cards[0].source_id or "imported_source",
            authorization=cards[0].authorization or "see_import_record",
            authorization_ref=cards[0].authorization_ref or "missing_authorization_ref",
            authorization_scope=authorization_scope,
            input_sha256=input_sha256,
            source_snapshot_sha256=source_snapshot_sha256,
            versioned=args.versioned,
        )
    except L1ImportError as exc:
        parser.exit(2, f"导入失败：{exc}\n")
    print(
        f"已写入 {path}（{len(cards)} 条，仅本地快照，未上传；"
        f"input_sha256={input_sha256}；scope={','.join(authorization_scope)}）"
    )


if __name__ == "__main__":
    main()
