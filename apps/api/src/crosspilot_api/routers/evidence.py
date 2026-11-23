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

from fastapi import APIRouter
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
)
from ..services.datasets import assert_demand_side
from ..services.demo_evidence import (
    DEMO_CONFLICT_CARDS,
    DEMO_CONFLICT_QUESTIONS,
    DEMO_L1_SOURCE_KEY,
    DEMO_LIMITED_CARDS,
    DEMO_LIMITED_QUESTIONS,
    DEMO_QUERY,
)
from ..services.query_expansion import expand_query
from ..services.safety_gate_retrieval import build_real_questions, search_safety_gate_multi
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
        )


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
    grade: EvidenceGrade | None = None
    downgrade_reasons: list[str] = []

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
            grade=card.grade,
            downgrade_reasons=list(card.downgrade_reasons),
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
    questions: list[str]
    generated_at: datetime
    #: 判定全链路可追溯数据（ADR-0005：区间 / 门禁 / 去重摘要 / 功效注记）。
    decision: DecisionOut
    #: 知乎侧 L2 中文证据卡（ADR-0002：snapshot 模式来自快照，live 模式来自实时检索）。
    l2_cards: list[EvidenceCardOut] = []
    #: L2 降级提示：快照缺失/损坏、配额耗尽、凭据缺失、网络故障时非空，禁止静默空结果。
    l2_notice: str | None = None


def _attach_dedup(cards: list[EvidenceCard], decision: Decision) -> list[EvidenceCard]:
    """把 decide 管道的去重结果回填到 L1 卡（R2 产物进卡面，逐卡可审计）。

    EvidenceCard 为 frozen dataclass，用 dataclasses.replace 生成带 dedup 的副本；
    L2/L3 位为 None 不回填。stance_votes/annotator_agreement 在单标注器模式下
    恒 None（两票制启用见 ADR-0005 决策 7：凭据到位后 --classifier ensemble）。
    """
    out: list[EvidenceCard] = []
    for i, card in enumerate(cards):
        info = decision.dedup_by_card[i] if i < len(decision.dedup_by_card) else None
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
def search_evidence(query: str = "") -> EvidenceResponse:
    """真实快照（scenario=real）：Safety Gate 近邻品类（L3）+ 知乎侧 L2 卡（l2_* 字段）。

    L3 用双语扩展词表做并集检索（中文词与其英文等价式一起命中）；
    判定只由 cards（L3-only → gate=no_l1）计算，维持既有行为：L2 卡不进入
    decide 的输入，硬约束 1（L2 不得单独支撑偏好结论）由 domain 层保证，
    路由层不重复判断。
    """
    terms = expand_query(query)
    cards = search_safety_gate_multi(terms)
    l2_cards, l2_notice = _collect_l2(query)
    decision = decide(cards)
    return EvidenceResponse(
        query=query,
        market=MARKET,
        data_mode=settings.data_mode,
        scenario=Scenario.REAL,
        stance=decision.state,
        cards=[EvidenceCardOut.from_card(card) for card in cards],
        questions=build_real_questions(query, len(cards)),
        generated_at=datetime.now(UTC),
        decision=DecisionOut.from_decision(decision),
        l2_cards=[EvidenceCardOut.from_card(card) for card in l2_cards],
        l2_notice=l2_notice,
    )


@router.get("/demo")
def demo_evidence(scenario: Literal["conflict", "limited"]) -> EvidenceResponse:
    """演示状态：显式标识的演示数据，不与真实反馈同卡混排。

    两个场景分支都先走 assert_demand_side 校验 L1 demo 声明源
    （demo 源不进 REGISTRY 的理由见 services/datasets.py 注释与 services/demo_evidence.py）。
    判定走 ADR-0005 公式：conflict（15:15）→ conflicting；limited（21:9）→ supported。
    """
    assert_demand_side(DEMO_L1_SOURCE_KEY)
    if scenario == "conflict":
        cards = list(DEMO_CONFLICT_CARDS)
        questions = list(DEMO_CONFLICT_QUESTIONS)
        scenario_label = Scenario.DEMO_CONFLICT
    else:
        cards = list(DEMO_LIMITED_CARDS)
        questions = list(DEMO_LIMITED_QUESTIONS)
        scenario_label = Scenario.DEMO_LIMITED
    decision = decide(cards)
    cards_with_dedup = _attach_dedup(cards, decision)
    return EvidenceResponse(
        query=DEMO_QUERY,
        market=MARKET,
        data_mode=settings.data_mode,
        scenario=scenario_label,
        stance=decision.state,  # conflict → conflicting（并排）；limited → supported
        cards=[EvidenceCardOut.from_card(card) for card in cards_with_dedup],
        questions=questions,
        generated_at=datetime.now(UTC),
        decision=DecisionOut.from_decision(decision),
    )
