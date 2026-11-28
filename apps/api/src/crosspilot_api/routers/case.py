"""真实商品案例就绪度路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..domain.evidence import decide_by_claim
from ..services.case_readiness import (
    CaseReadiness,
    CheckStatus,
    ReadinessLevel,
    assess_case_readiness,
)
from ..services.claims import select_claim_ids
from ..services.l1_import import L1ImportError, load_l1_snapshot_data
from ..services.validation_round import (
    ValidationRoundError,
    load_validation_rounds_archive_data,
)

router = APIRouter(prefix="/api/case", tags=["case"])


class ReadinessCheckOut(BaseModel):
    id: str
    label: str
    status: CheckStatus
    detail: str


class ClaimReadinessOut(BaseModel):
    claim_id: str
    state: str
    n_l1: int
    n_polarized: int
    review_pending: int
    confirmed_rounds: int


class CaseReadinessOut(BaseModel):
    query: str
    market: str
    level: ReadinessLevel
    summary: str
    checks: list[ReadinessCheckOut]
    claims: list[ClaimReadinessOut]
    next_actions: list[str]
    confirmed_rounds: int
    market_effect_claim_allowed: bool
    snapshot_sha256: str | None = None
    rounds_archive_sha256: str | None = None

    @classmethod
    def from_readiness(cls, readiness: CaseReadiness) -> CaseReadinessOut:
        return cls(
            query=readiness.query,
            market=readiness.market,
            level=readiness.level,
            summary=readiness.summary,
            checks=[
                ReadinessCheckOut(
                    id=check.id,
                    label=check.label,
                    status=check.status,
                    detail=check.detail,
                )
                for check in readiness.checks
            ],
            claims=[
                ClaimReadinessOut(
                    claim_id=claim.claim_id,
                    state=claim.state,
                    n_l1=claim.n_l1,
                    n_polarized=claim.n_polarized,
                    review_pending=claim.review_pending,
                    confirmed_rounds=claim.confirmed_rounds,
                )
                for claim in readiness.claims
            ],
            next_actions=list(readiness.next_actions),
            confirmed_rounds=readiness.confirmed_rounds,
            market_effect_claim_allowed=readiness.market_effect_claim_allowed,
            snapshot_sha256=readiness.snapshot_sha256,
            rounds_archive_sha256=readiness.rounds_archive_sha256,
        )


@router.get("/readiness", response_model=CaseReadinessOut)
def case_readiness(
    query: str = Query("", max_length=100),
    claim_id: Annotated[list[str] | None, Query()] = None,
) -> CaseReadinessOut:
    try:
        snapshot = load_l1_snapshot_data(query)
        cards = snapshot.cards
        l1_notice = snapshot.notice
        claim_ids = select_claim_ids(cards, claim_id)
        decisions = decide_by_claim(cards, claim_ids)
        rounds_archive = load_validation_rounds_archive_data()
        rounds = rounds_archive.records
    except (L1ImportError, ValidationRoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    readiness = assess_case_readiness(
        query=query,
        market="de",
        cards=cards,
        claim_decisions=decisions,
        rounds=rounds,
        snapshot_sha256=snapshot.snapshot_sha256,
        rounds_archive_sha256=rounds_archive.archive_sha256,
    )
    if l1_notice and not cards:
        readiness = CaseReadiness(
            query=readiness.query,
            market=readiness.market,
            level=readiness.level,
            summary=f"{readiness.summary} {l1_notice}",
            checks=readiness.checks,
            claims=readiness.claims,
            next_actions=readiness.next_actions,
            confirmed_rounds=readiness.confirmed_rounds,
            market_effect_claim_allowed=False,
            snapshot_sha256=readiness.snapshot_sha256,
            rounds_archive_sha256=readiness.rounds_archive_sha256,
        )
    return CaseReadinessOut.from_readiness(readiness)
