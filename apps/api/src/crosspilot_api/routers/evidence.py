"""证据对照表路由：只做编排，规则一律下沉 domain/ 与 services/。

响应包络（执行者C 按此开发前端，字段名不得偏离）：
query / market / data_mode / scenario / stance / cards / questions / generated_at
+ 2026-11-21 追加可选字段（向后兼容，demo 端点不填即取默认值）：
l2_cards（知乎侧 L2 中文证据卡，含 is_demo_data 标识）/ l2_notice（降级提示）

L2 语义红线（硬约束 1）：l2_cards 只作为「待验证问题」素材呈现，不进入
resolve_stance 的输入——真实端点的 stance 与此前完全一致，L2 卡永远不改变结论。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings
from ..domain.evidence import EvidenceCard, EvidenceLevel, Stance, resolve_stance
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
        )


class EvidenceResponse(BaseModel):
    """证据对照表统一响应包络。l2_* 两个新增可选字段带默认值，旧消费者兼容。"""

    query: str
    market: str
    data_mode: str
    scenario: Scenario
    stance: Stance
    cards: list[EvidenceCardOut]
    questions: list[str]
    generated_at: datetime
    #: 知乎侧 L2 中文证据卡（ADR-0002：snapshot 模式来自快照，live 模式来自实时检索）。
    l2_cards: list[EvidenceCardOut] = []
    #: L2 降级提示：快照缺失/损坏、配额耗尽、凭据缺失、网络故障时非空，禁止静默空结果。
    l2_notice: str | None = None


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
    stance 只由 cards（L3）计算，维持既有行为：L2 卡不进入 resolve_stance 的输入，
    硬约束 1（L2 不得单独支撑偏好结论）由 domain 层保证，路由层不重复判断。
    """
    terms = expand_query(query)
    cards = search_safety_gate_multi(terms)
    l2_cards, l2_notice = _collect_l2(query)
    return EvidenceResponse(
        query=query,
        market=MARKET,
        data_mode=settings.data_mode,
        scenario=Scenario.REAL,
        stance=resolve_stance(cards),
        cards=[EvidenceCardOut.from_card(card) for card in cards],
        questions=build_real_questions(query, len(cards)),
        generated_at=datetime.now(UTC),
        l2_cards=[EvidenceCardOut.from_card(card) for card in l2_cards],
        l2_notice=l2_notice,
    )


@router.get("/demo")
def demo_evidence(scenario: Literal["conflict", "limited"]) -> EvidenceResponse:
    """演示状态：显式标识的演示数据，不与真实反馈同卡混排。

    两个场景分支都先走 assert_demand_side 校验 L1 demo 声明源
    （demo 源不进 REGISTRY 的理由见 services/datasets.py 注释与 services/demo_evidence.py）。
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
    return EvidenceResponse(
        query=DEMO_QUERY,
        market=MARKET,
        data_mode=settings.data_mode,
        scenario=scenario_label,
        stance=resolve_stance(cards),  # conflict → oppose（冲突）；limited → support
        cards=[EvidenceCardOut.from_card(card) for card in cards],
        questions=questions,
        generated_at=datetime.now(UTC),
    )
