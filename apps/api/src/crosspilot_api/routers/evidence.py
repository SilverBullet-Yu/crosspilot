"""证据对照表路由：只做编排，规则一律下沉 domain/ 与 services/。

响应包络（执行者C 按此开发前端，字段名不得偏离）：
query / market / data_mode / scenario / stance / cards / questions / generated_at
+ 2026-11-21 追加可选字段（向后兼容，demo 端点不填即取默认值）：
l2_cards（知乎侧 L2 中文证据卡，含 is_demo_data 标识）/ l2_notice（降级提示）
+ 2026-11-22 追加（ADR-0005 判定链，一次性同步、不向后兼容）：
stance 类型改为 DecisionState 四值（supported/refuted/insufficient/conflicting，
R1 唯一判定枚举；原「冲突→oppose」拆出 conflicting）；
decision（判定全链路可追溯数据：门禁/区间/去重摘要/功效注记）；
卡级可选字段 dedup / stance_votes / annotator_agreement / grade / downgrade_reasons
（对齐 packages/contracts/evidence-card.schema.json）。

L2 语义红线（硬约束 1）：l2_cards 只作为「待验证问题」素材呈现，不进入
decide 的输入——真实端点的判定与此前完全一致，L2 卡永远不改变结论。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..config import settings
from ..domain.evidence import (
    Decision,
    DecisionState,
    EvidenceCard,
    EvidenceGrade,
    EvidenceLevel,
    GateStatus,
    Stance,
    decide,
    decide_by_claim,
)
from ..services.claims import CLAIM_IDS, UNASSIGNED_CLAIM_ID, claim_ids_from_cards
from ..services.cross_source import (
    CrossSourceComparison,
    build_cross_source_comparisons,
    build_evidence_questions,
)
from ..services.datasets import assert_demand_side
from ..services.demo_evidence import (
    DEMO_CONFLICT_CARDS,
    DEMO_L1_SOURCE_KEY,
    DEMO_L2_CARDS,
    DEMO_LIMITED_CARDS,
    DEMO_QUERY,
)
from ..services.l1_import import load_l1_snapshot_data
from ..services.query_expansion import expand_query
from ..services.safety_gate_retrieval import search_safety_gate_multi
from ..services.stats import WilsonInterval
from ..services.zhihu_client import QUOTA_GUIDANCE, QuotaExhaustedError, ZhihuError, search_zhihu
from ..services.zhihu_snapshot import load_zhihu_snapshot, snapshot_path

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

#: 对照表当前只做德国市场。
MARKET = "de"


class Scenario(StrEnum):
    """产品状态：真实快照 / 演示冲突 / 演示有限支持。"""

    REAL = "real"
    DEMO_CONFLICT = "demo_conflict"
    DEMO_LIMITED = "demo_limited"


class DedupOut(BaseModel):
    """卡面去重结果（R2 管道产物，逐卡可审计）。"""

    cluster_id: int
    dup_count: int
    is_canonical: bool


class StanceVotesOut(BaseModel):
    """多标注器立场票（两票制；llm=null 为缺席，R6 显式传播）。"""

    rule: Stance
    llm: Stance | None


class IntervalOut(BaseModel):
    """Wilson 95% 区间（去重后有极性样本分母，对抗审查 C4 口径）。"""

    lo: float
    hi: float
    n: int


class DecisionOut(BaseModel):
    """判定全链路可追溯数据（ADR-0005 决策 3 判定级字段落点：包络，不进卡片 schema）。

    state 与顶层 stance 一致（冗余以自足）；区间 / 样本量 / 去重摘要 /
    功效注记让「证据不足」从口径变公式，评审可逐项追溯。
    """

    state: DecisionState
    gate_status: GateStatus
    support_interval: IntervalOut | None
    oppose_interval: IntervalOut | None
    n_total: int
    n_l1: int
    n_polarized: int
    n_insufficient: int
    dedup_clusters: int
    dedup_duplicated: int
    power_note: str
    inference_note: str

    @classmethod
    def from_decision(cls, decision: Decision) -> DecisionOut:
        return cls(
            state=decision.state,
            gate_status=decision.gate_status,
            support_interval=_interval_out(decision.support_interval),
            oppose_interval=_interval_out(decision.oppose_interval),
            n_total=decision.n_total,
            n_l1=decision.n_l1,
            n_polarized=decision.n_polarized,
            n_insufficient=decision.n_insufficient,
            dedup_clusters=decision.dedup_clusters,
            dedup_duplicated=decision.dedup_duplicated,
            power_note=decision.power_note,
            inference_note=decision.inference_note,
        )


class ClaimDecisionOut(DecisionOut):
    claim_id: str

    @classmethod
    def from_claim(cls, claim_id: str, decision: Decision) -> ClaimDecisionOut:
        base = DecisionOut.from_decision(decision)
        return cls(**base.model_dump(), claim_id=claim_id)


def _interval_out(interval: WilsonInterval | None) -> IntervalOut | None:
    if interval is None:
        return None
    return IntervalOut(lo=interval.lo, hi=interval.hi, n=interval.n)


class EvidenceCardOut(BaseModel):
    """证据卡出参，字段与 packages/contracts/evidence-card.schema.json 对齐。"""

    excerpt: str
    source_url: str
    language: str
    published_on: date
    level: EvidenceLevel
    sample_size: int | None
    stance: Stance
    is_demo_data: bool
    # ---- ADR-0005 卡级扩展字段（全 optional，向后兼容）----
    dedup: DedupOut | None = None
    stance_votes: StanceVotesOut | None = None
    annotator_agreement: bool | None = None
    classification_method: str | None = None
    classification_note: str | None = None
    review_required: bool | None = None
    review_reasons: list[str] = []
    grade: EvidenceGrade | None = None
    downgrade_reasons: list[str] = []
    claim_id: str | None = None
    aspect_terms: list[str] = []
    review_id: str | None = None
    market: str | None = None
    source_id: str | None = None
    authorization: str | None = None
    authorization_ref: str | None = None
    relevance: str = "relevant"

    @classmethod
    def from_card(cls, card: EvidenceCard) -> EvidenceCardOut:
        return cls(
            excerpt=card.excerpt,
            source_url=card.source_url,
            language=card.language,
            published_on=card.published_on,
            level=card.level,
            sample_size=card.sample_size,
            stance=card.stance,
            is_demo_data=card.is_demo_data,
            dedup=(
                DedupOut(
                    cluster_id=card.dedup.cluster_id,
                    dup_count=card.dedup.dup_count,
                    is_canonical=card.dedup.is_canonical,
                )
                if card.dedup is not None
                else None
            ),
            stance_votes=(
                StanceVotesOut(rule=card.stance_votes.rule, llm=card.stance_votes.llm)
                if card.stance_votes is not None
                else None
            ),
            annotator_agreement=card.annotator_agreement,
            classification_method=card.classification_method,
            classification_note=card.classification_note,
            review_required=card.review_required,
            review_reasons=list(card.review_reasons),
            grade=card.grade,
            downgrade_reasons=list(card.downgrade_reasons),
            claim_id=card.claim_id,
            aspect_terms=list(card.aspect_terms),
            review_id=card.review_id,
            market=card.market,
            source_id=card.source_id,
            authorization=card.authorization,
            authorization_ref=card.authorization_ref,
            relevance=card.relevance,
        )


class EvidenceQuestionOut(BaseModel):
    text: str
    source: str


class CrossSourceComparisonOut(BaseModel):
    claim_id: str
    label: str
    status: str
    l1_state: DecisionState
    l1_total: int
    l1_polarized: int
    l1_support: int
    l1_oppose: int
    l1_insufficient: int
    l2_total: int
    l1_refs: list[str]
    l2_refs: list[str]
    question: str

    @classmethod
    def from_comparison(cls, comparison: CrossSourceComparison) -> CrossSourceComparisonOut:
        return cls(
            claim_id=comparison.claim_id,
            label=comparison.label,
            status=comparison.status,
            l1_state=DecisionState(comparison.l1_state),
            l1_total=comparison.l1_total,
            l1_polarized=comparison.l1_polarized,
            l1_support=comparison.l1_support,
            l1_oppose=comparison.l1_oppose,
            l1_insufficient=comparison.l1_insufficient,
            l2_total=comparison.l2_total,
            l1_refs=list(comparison.l1_refs),
            l2_refs=list(comparison.l2_refs),
            question=comparison.question,
        )


class EvidenceResponse(BaseModel):
    """证据对照表统一响应包络。

    stance：判定四值（DecisionState，R1 唯一枚举）——
    supported/refuted/insufficient/conflicting；demo_conflict 场景为 conflicting。
    decision：判定可追溯数据；l2_* 两个可选字段带默认值，旧消费者兼容。
    """

    query: str
    market: str
    data_mode: str
    scenario: Scenario
    stance: DecisionState
    cards: list[EvidenceCardOut]
    questions: list[EvidenceQuestionOut]
    generated_at: datetime
    #: 判定全链路可追溯数据（ADR-0005：区间 / 门禁 / 去重摘要 / 功效注记）。
    decision: DecisionOut
    #: 每条卖点假设的独立判定；跨假设混合情感不得作为单条卖点结论。
    claim_decisions: list[ClaimDecisionOut] = []
    #: 知乎侧 L2 中文证据卡（ADR-0002：snapshot 模式来自快照，live 模式来自实时检索）。
    l2_cards: list[EvidenceCardOut] = []
    #: L2 降级提示：快照缺失/损坏、配额耗尽、凭据缺失、网络故障时非空，禁止静默空结果。
    l2_notice: str | None = None
    #: 德国 L1 授权快照的缺失或损坏提示。
    l1_notice: str | None = None
    #: 真实 L1 快照的授权用途范围；复核导出只能原样沿用，不能扩权。
    l1_authorization_scope: list[str] = []
    #: 当前已验证 L1 快照的 record_sha256；用于隔离不同版本的人工复核草稿。
    l1_snapshot_sha256: str | None = None
    #: 按卖点结构化保存 L1/L2 出处、样本分布与待核对问题；L2 不参与判定。
    comparisons: list[CrossSourceComparisonOut] = []


def _attach_dedup(
    cards: list[EvidenceCard], claim_decisions: dict[str, Decision]
) -> list[EvidenceCard]:
    """把各卖点判定管道的去重结果回填到 L1 卡，未归属卡不参与判定。"""
    positions: dict[str, int] = {}
    out: list[EvidenceCard] = []
    for card in cards:
        info = None
        if card.claim_id in claim_decisions:
            position = positions.get(card.claim_id, 0)
            decision = claim_decisions[card.claim_id]
            info = (
                decision.dedup_by_card[position]
                if position < len(decision.dedup_by_card)
                else None
            )
            positions[card.claim_id] = position + 1
        out.append(replace(card, dedup=info))
    return out


def _collect_l2(query: str) -> tuple[list[EvidenceCard], str | None]:
    """收集知乎 L2 中文证据卡。任何失败都显式降级，返回空列表 + 非空提示。

    live 模式：配额耗尽原样透传 QuotaExhaustedError 消息（自带降级指引）；
    其余适配器错误统一补降级指引。**live 只用原查询词检索**——扩展词表会成倍
    消耗 10 次/日额度，双语扩展仅用于零成本的本地快照路径。
    snapshot 模式：按扩展词表逐个查找快照文件（首个命中即用）；全部缺失时
    返回空列表 + 原查询词的缺失提示（ADR-0002 决策 4）。
    """
    if settings.is_live:
        try:
            return search_zhihu(query), None
        except QuotaExhaustedError as exc:
            return [], str(exc)  # 消息已含「当前为实测 10 次/日，演示请切回 snapshot 模式」
        except ZhihuError as exc:
            return [], f"知乎 L2 live 检索未执行：{exc}；{QUOTA_GUIDANCE}"
    for term in expand_query(query):
        if snapshot_path(term).is_file():
            return load_zhihu_snapshot(term)
    return load_zhihu_snapshot(query)


@router.get("")
def search_evidence(query: str = Query("", max_length=100)) -> EvidenceResponse:
    """真实快照：授权德国 L1 + 知乎 L2 + Safety Gate L3，按卖点分别判定。"""
    terms = expand_query(query)
    l3_cards = search_safety_gate_multi(terms)
    l1_snapshot = load_l1_snapshot_data(query)
    l1_cards = l1_snapshot.cards
    l1_notice = l1_snapshot.notice
    l2_cards, l2_notice = _collect_l2(query)
    cards = l1_cards + l3_cards
    claim_ids = claim_ids_from_cards(l1_cards)
    claim_decisions = decide_by_claim(cards, claim_ids)
    present_claim_ids = sorted(
        {
            card.claim_id
            for card in l1_cards
            if card.relevance == "relevant"
            and card.claim_id in claim_ids
            and card.claim_id != UNASSIGNED_CLAIM_ID
        }
    )
    if len(present_claim_ids) == 1:
        decision = decide(
            [card for card in cards if card.claim_id == present_claim_ids[0]]
        )
    else:
        decision = replace(
            decide([]),
            n_total=len(cards),
            power_note=(
                "当前包络包含多个卖点或未归属评论，不生成跨卖点总体判定；"
                "请查看 claim_decisions。"
            ),
        )
    cards_with_dedup = _attach_dedup(cards, claim_decisions)
    comparisons = build_cross_source_comparisons(
        l1_cards=cards_with_dedup,
        l2_cards=l2_cards,
        claim_decisions=claim_decisions,
        claim_ids=claim_ids,
    )
    questions = build_evidence_questions(
        query=query,
        l1_cards=cards_with_dedup,
        l2_cards=l2_cards,
        l3_cards=l3_cards,
        claim_decisions=claim_decisions,
        claim_ids=claim_ids,
        comparisons=comparisons,
    )
    return EvidenceResponse(
        query=query,
        market=MARKET,
        data_mode=settings.data_mode,
        scenario=Scenario.REAL,
        stance=decision.state,
        cards=[EvidenceCardOut.from_card(card) for card in cards_with_dedup],
        questions=[EvidenceQuestionOut(**question) for question in questions],
        generated_at=datetime.now(UTC),
        decision=DecisionOut.from_decision(decision),
        claim_decisions=[
            ClaimDecisionOut.from_claim(claim_id, claim_decisions[claim_id])
            for claim_id in claim_ids
        ],
        l2_cards=[EvidenceCardOut.from_card(card) for card in l2_cards],
        l2_notice=l2_notice,
        l1_notice=l1_notice,
        l1_authorization_scope=list(l1_snapshot.authorization_scope),
        l1_snapshot_sha256=l1_snapshot.snapshot_sha256,
        comparisons=[
            CrossSourceComparisonOut.from_comparison(comparison)
            for comparison in comparisons
        ],
    )


@router.get("/demo")
def demo_evidence(scenario: Literal["conflict", "limited"]) -> EvidenceResponse:
    """显式标识的模拟 L1 + 模拟 L2，用于演示跨来源对照，不与真实数据混排。"""
    assert_demand_side(DEMO_L1_SOURCE_KEY)
    if scenario == "conflict":
        cards = list(DEMO_CONFLICT_CARDS)
        scenario_label = Scenario.DEMO_CONFLICT
    else:
        cards = list(DEMO_LIMITED_CARDS)
        scenario_label = Scenario.DEMO_LIMITED
    claim_decisions = decide_by_claim(cards, CLAIM_IDS)
    decision = decide(cards)
    cards_with_dedup = _attach_dedup(cards, claim_decisions)
    l2_cards = list(DEMO_L2_CARDS)
    comparisons = build_cross_source_comparisons(
        l1_cards=cards_with_dedup,
        l2_cards=l2_cards,
        claim_decisions=claim_decisions,
    )
    questions = build_evidence_questions(
        query=DEMO_QUERY,
        l1_cards=cards_with_dedup,
        l2_cards=l2_cards,
        l3_cards=[],
        claim_decisions=claim_decisions,
        comparisons=comparisons,
    )
    return EvidenceResponse(
        query=DEMO_QUERY,
        market=MARKET,
        data_mode=settings.data_mode,
        scenario=scenario_label,
        stance=decision.state,
        cards=[EvidenceCardOut.from_card(card) for card in cards_with_dedup],
        questions=[EvidenceQuestionOut(**question) for question in questions],
        generated_at=datetime.now(UTC),
        decision=DecisionOut.from_decision(decision),
        claim_decisions=[
            ClaimDecisionOut.from_claim(claim_id, claim_decisions[claim_id])
            for claim_id in CLAIM_IDS
        ],
        l2_cards=[EvidenceCardOut.from_card(card) for card in l2_cards],
        comparisons=[
            CrossSourceComparisonOut.from_comparison(comparison)
            for comparison in comparisons
        ],
    )
