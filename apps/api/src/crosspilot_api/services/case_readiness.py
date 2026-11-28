"""真实商品案例的就绪度审计：防止把模拟、待复核或探索性样本误报为完成。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain.evidence import Decision, EvidenceCard, EvidenceLevel
from .claims import claim_ids_from_cards
from .validation_round import ValidationRoundRecord


class ReadinessLevel(StrEnum):
    BLOCKED = "blocked"
    EXPLORATORY = "exploratory"
    DECISION_READY = "decision_ready"
    TRIAL_COMPLETE = "trial_complete"


class CheckStatus(StrEnum):
    PASS = "pass"
    PENDING = "pending"
    FAIL = "fail"


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    label: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class ClaimReadiness:
    claim_id: str
    state: str
    n_l1: int
    n_polarized: int
    review_pending: int
    confirmed_rounds: int


@dataclass(frozen=True)
class CaseReadiness:
    query: str
    market: str
    level: ReadinessLevel
    summary: str
    checks: tuple[ReadinessCheck, ...]
    claims: tuple[ClaimReadiness, ...]
    next_actions: tuple[str, ...]
    confirmed_rounds: int
    market_effect_claim_allowed: bool = False
    snapshot_sha256: str | None = None
    rounds_archive_sha256: str | None = None


def _round_references_card(
    round_record: ValidationRoundRecord,
    card: EvidenceCard,
) -> bool:
    if (
        card.level is not EvidenceLevel.L1
        or card.is_demo_data
        or card.claim_id != round_record.claimId
        or not card.review_id
        or not card.source_url
    ):
        return False
    references = {part.strip() for part in round_record.evidenceRefs.split(";")}
    return f"{card.review_id}: {card.source_url}" in references


def _needs_human_review(card: EvidenceCard) -> bool:
    if card.relevance != "relevant":
        return False
    return not (
        card.classification_method == "manual"
        and card.review_required is False
        and bool((card.classification_note or "").strip())
    )


def assess_case_readiness(
    *,
    query: str,
    market: str,
    cards: list[EvidenceCard],
    claim_decisions: dict[str, Decision],
    rounds: list[ValidationRoundRecord],
    snapshot_sha256: str | None = None,
    rounds_archive_sha256: str | None = None,
) -> CaseReadiness:
    l1_cards = [card for card in cards if card.level is EvidenceLevel.L1]
    real_l1 = [card for card in l1_cards if not card.is_demo_data]
    demo_count = len(l1_cards) - len(real_l1)
    known_claims = set(claim_decisions)
    available_claims = set(claim_ids_from_cards(cards))
    provenance_missing = [
        card.review_id or "unknown"
        for card in real_l1
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
        )
    ]
    unassigned = [
        card
        for card in real_l1
        if card.relevance == "relevant" and card.claim_id not in available_claims
    ]
    review_pending = [
        card
        for card in real_l1
        if card.claim_id in known_claims and _needs_human_review(card)
    ]
    sample_ready = bool(claim_decisions) and all(
        decision.n_polarized >= 30 for decision in claim_decisions.values()
    )
    real_confirmed_rounds = [
        round_record
        for round_record in rounds
        if round_record.query == query
        and round_record.scenario == "real"
        and round_record.claimId in known_claims
        and round_record.confirmation == "confirmed"
        and round_record.market.lower() == "de"
        and snapshot_sha256 is not None
        and round_record.l1SnapshotSha256 == snapshot_sha256
    ]
    confirmed_rounds = [
        round_record
        for round_record in real_confirmed_rounds
        if any(_round_references_card(round_record, card) for card in real_l1)
    ]
    invalid_reference_rounds = len(real_confirmed_rounds) - len(confirmed_rounds)
    confirmed_by_claim = {
        claim_id: sum(round_record.claimId == claim_id for round_record in confirmed_rounds)
        for claim_id in known_claims
    }
    trial_complete = bool(known_claims) and all(
        confirmed_by_claim[claim_id] > 0 for claim_id in known_claims
    )
    valid_market = market.lower() == "de"
    base_ready = (
        bool(query.strip())
        and valid_market
        and bool(real_l1)
        and not provenance_missing
        and demo_count == 0
    )

    if not base_ready:
        level = ReadinessLevel.BLOCKED
    elif unassigned or review_pending or not sample_ready:
        level = ReadinessLevel.EXPLORATORY
    elif trial_complete:
        level = ReadinessLevel.TRIAL_COMPLETE
    else:
        level = ReadinessLevel.DECISION_READY

    checks = [
        ReadinessCheck(
            "query_market",
            "商品与目标市场",
            CheckStatus.PASS if query.strip() and valid_market else CheckStatus.FAIL,
            f"query={query or '空'}；market={market or '空'}（当前真实案例固定 de）",
        ),
        ReadinessCheck(
            "authorized_l1",
            "授权德国 L1",
            CheckStatus.PASS if real_l1 else CheckStatus.FAIL,
            f"真实 L1 {len(real_l1)} 条；演示 L1 {demo_count} 条",
        ),
        ReadinessCheck(
            "provenance",
            "逐条溯源字段",
            CheckStatus.PASS if real_l1 and not provenance_missing else CheckStatus.FAIL,
            "缺少字段：" + ("、".join(provenance_missing[:5]) if provenance_missing else "无"),
        ),
        ReadinessCheck(
            "demo_isolation",
            "真实/模拟隔离",
            CheckStatus.PASS if demo_count == 0 else CheckStatus.FAIL,
            f"演示卡混入 {demo_count} 条",
        ),
        ReadinessCheck(
            "claim_assignment",
            "卖点归属完整",
            CheckStatus.PASS if real_l1 and not unassigned else CheckStatus.PENDING,
            f"相关但未归属 {len(unassigned)} 条",
        ),
        ReadinessCheck(
            "human_review",
            "人工复核完成",
            CheckStatus.PASS if real_l1 and not review_pending else CheckStatus.PENDING,
            f"待人工复核 {len(review_pending)} 条"
            "（相关评论须 manual + review_required=false + 复核说明）",
        ),
        ReadinessCheck(
            "sample_gate",
            "逐卖点样本门禁",
            CheckStatus.PASS if sample_ready else CheckStatus.PENDING,
            "每条卖点去重后有极性样本均需 n≥30",
        ),
        ReadinessCheck(
            "operator_trial",
            "运营试用确认",
            CheckStatus.PASS if trial_complete else CheckStatus.PENDING,
            f"有效证据引用轮次 {len(confirmed_rounds)}/{len(real_confirmed_rounds)}；"
            "每条卖点均需至少 1 轮引用真实 review_id + source_url",
        ),
    ]

    next_actions: list[str] = []
    if not query.strip() or not valid_market:
        next_actions.append("先确定商品查询词与德国市场。")
    if not real_l1:
        next_actions.append("取得品牌授权评论导出或 Amazon 书面许可，再导入真实德国 L1。")
    if provenance_missing:
        next_actions.append("补齐缺失的 review_id、来源、日期、市场与授权依据。")
    if demo_count:
        next_actions.append("移除真实案例中的演示卡，模拟数据只能进入独立演示端点。")
    if unassigned:
        next_actions.append("为相关但未归属评论指定 claim_id，不进入任何卖点判定前保持证据不足。")
    if review_pending:
        next_actions.append(
            "完成相关评论的人工立场确认；classification_method=manual、"
            "review_required=false 且复核说明非空才通过 readiness。"
        )
    if not sample_ready:
        next_actions.append("补充样本，使每条卖点去重后有极性样本达到 n≥30；不足时保持探索性状态。")
    if invalid_reference_rounds:
        next_actions.append(
            "为运营轮次补充该卖点真实评论的 review_id: source_url 引用；"
            "仅写 claim_id 不能证明消费者依据。"
        )
    if not trial_complete:
        next_actions.append("邀请跨境运营按假设完成试用并导出至少 1 轮已确认记录。")
    if level is ReadinessLevel.TRIAL_COMPLETE:
        next_actions.append("归档授权证据、判定与运营轮次；对外仍限定为当前样本，不声称总体市场效果。")

    summaries = {
        ReadinessLevel.BLOCKED: "真实案例被阻塞：缺少合规德国 L1 或关键溯源字段。",
        ReadinessLevel.EXPLORATORY: (
            "真实案例为探索性状态：已有 L1，但归属、复核或样本门禁尚未完成。"
        ),
        ReadinessLevel.DECISION_READY: (
            "真实案例可决策：L1、溯源、复核与样本门禁通过，尚缺运营试用确认。"
        ),
        ReadinessLevel.TRIAL_COMPLETE: (
            "真实案例与运营试用闭环完成；仍不得外推为总体消费者偏好或市场效果。"
        ),
    }
    claims = tuple(
        ClaimReadiness(
            claim_id=claim_id,
            state=decision.state.value,
            n_l1=decision.n_l1,
            n_polarized=decision.n_polarized,
            review_pending=sum(
                card.claim_id == claim_id and _needs_human_review(card)
                for card in real_l1
            ),
            confirmed_rounds=confirmed_by_claim[claim_id],
        )
        for claim_id, decision in sorted(claim_decisions.items())
    )
    return CaseReadiness(
        query=query,
        market=market,
        level=level,
        summary=summaries[level],
        checks=tuple(checks),
        claims=claims,
        next_actions=tuple(next_actions),
        confirmed_rounds=len(confirmed_rounds),
        snapshot_sha256=snapshot_sha256,
        rounds_archive_sha256=rounds_archive_sha256,
    )
