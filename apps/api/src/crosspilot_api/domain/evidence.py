"""领域模型：证据卡、证据层级与判定状态机。

本模块不依赖 FastAPI、不发网络请求，可被测试直接导入。
硬约束 1（L2/L3 不得单独支撑偏好结论）在此实现，不要在路由层重复判断。

判定管道（ADR-0005 决策 2/4，R1–R6 对齐规则）：
    L1 过滤（硬约束 1）→ 去重（R2：先于计数）→ 去重后立场计数 →
    Wilson 95% 区间 + 门禁 → 四值状态映射 → 全下游唯一枚举（R1）。

判定状态语义（AVeriTeC 四标签；R1：全系统唯一判定枚举，不得发明第五值）：
    supported    支持份额 95% 下界 > 0.5（当前样本内决定性多数支持）
    refuted      反对份额 95% 下界 > 0.5（当前样本内决定性多数反对）
    conflicting  双方票数 > 0 且未形成决定性多数（样本内分歧，不等于独立证据冲突）
    insufficient 无 L1 / 样本低于门禁 / 无极性信号
所有区间只描述当前样本，不外推非随机评论样本到总体消费者。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from ..services.evidence_dedup import DedupInfo, deduplicate
from ..services.stats import (
    WilsonInterval,
    below_minimum,
    intervals_overlap,
    power_note,
    wilson_interval,
)


class EvidenceLevel(StrEnum):
    """证据层级。见 docs/CONSTRAINTS.md 第二节。"""

    L1 = "L1"  # 目标市场一手消费者反馈
    L2 = "L2"  # 中文从业者经验、二手转述
    L3 = "L3"  # 宏观统计与市场语境


class Stance(StrEnum):
    """卡级立场信号（单条证据的态度分类，与 stance_baseline / GERestaurant 口径一致）。

    注意：这是判定管道的**输入**，不是判定输出；判定输出是 DecisionState。
    """

    SUPPORT = "support"
    OPPOSE = "oppose"
    INSUFFICIENT = "insufficient"


class DecisionState(StrEnum):
    """判定状态（R1：全系统唯一判定枚举；包络 stance 字段用它，不发明第五值）。"""

    SUPPORTED = "supported"
    REFUTED = "refuted"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"


class GateStatus(StrEnum):
    """判定门禁状态（进包络 decision 字段，判定路径可追溯）。"""

    PASS = "pass"
    NO_L1 = "no_l1"  # 无 L1 卡（硬约束 1）
    BELOW_MINIMUM = "below_minimum"  # 去重后有极性样本低于门禁
    NO_POLARIZED = "no_polarized"  # 过门禁条件不适用：去重后无极性样本


class EvidenceGrade(StrEnum):
    """GRADE 式证据质量分级（仅 L2/L3 卡做静态注记；L1 不参与）。

    当前实现态：字段随契约落地，填充由演示文档静态注记（A6）提供；
    判定门禁消费的是 level 而非 grade（R3），grade 只进展示层。
    """

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very-low"


INFERENCE_NOTE = (
    "当前评论通常为非随机样本，Wilson 区间仅描述样本内不确定性，"
    "不能直接外推为总体消费者偏好。"
)


@dataclass(frozen=True)
class StanceVotes:
    """多标注器立场票（A4 两票制：对抗审查 C1 修正——原三票引用了不存在的词表标注器）。

    llm 为 None 表示 LLM 标注器缺席（凭据缺省 / 运行时回退，R6 显式传播，
    不静默吞掉）。llm 与 rule 分歧 = 标注器不确定性（R4），由
    services.stance_aggregate 聚合，不进证据冲突。
    """

    rule: Stance
    llm: Stance | None = None


@dataclass(frozen=True)
class EvidenceCard:
    """证据卡。六个必现字段缺一不可，否则不得渲染。"""

    excerpt: str
    source_url: str
    language: str
    published_on: date
    level: EvidenceLevel
    sample_size: int | None
    stance: Stance = Stance.INSUFFICIENT
    is_demo_data: bool = False
    # ---- ADR-0005 卡级扩展字段（全 optional；契约与前端校验同批扩展）----
    #: 去重结果（R2 管道产物；L1 卡才有，L2/L3 恒 None）
    dedup: DedupInfo | None = None
    #: 多标注器立场票（A4；单标注器时 llm=None）
    stance_votes: StanceVotes | None = None
    #: 标注器一致度（R4：None=单标注器无法评估；False=标注器分歧）
    annotator_agreement: bool | None = None
    #: 最终立场的分类方法；人工覆盖时保留规则票，不冒充模型已验证。
    classification_method: str | None = None
    #: 人工复核说明，最多 500 字符。
    classification_note: str | None = None
    #: 规则结果是否需要人工复核；人工覆盖后为 false。
    review_required: bool | None = None
    #: 复核分流理由，便于卡面与 dry-run 解释。
    review_reasons: tuple[str, ...] = ()
    #: GRADE 式静态注记（仅 L2/L3；当前实现态恒 None，见 EvidenceGrade）
    grade: EvidenceGrade | None = None
    #: GRADE 降级理由（静态注记；空 = 无降级）
    downgrade_reasons: tuple[str, ...] = ()
    #: 卖点假设 ID；缺失时仅用于旧数据兼容，不进入新的卖点级判定。
    claim_id: str | None = None
    #: 自定义卖点术语；同一 claim_id 的所有 L1 卡必须一致，空值表示回退整条规则票。
    aspect_terms: tuple[str, ...] = ()
    #: 原始评论 ID；真实 L1 导入必须保留，不得用数组下标重写。
    review_id: str | None = None
    #: 来源市场与授权信息；真实 L1 导入必须提供。
    market: str | None = None
    source_id: str | None = None
    authorization: str | None = None
    authorization_ref: str | None = None
    #: 与当前假设是否相关；irrelevant 卡保留但不进入卖点判定。
    relevance: str = "relevant"

    def __post_init__(self) -> None:
        missing = [
            name
            for name in ("excerpt", "source_url", "language", "published_on", "level")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"证据卡缺少必现字段: {missing}")
        if self.relevance not in {"relevant", "irrelevant"}:
            raise ValueError(f"证据卡 relevance 非法: {self.relevance}")
        if self.aspect_terms:
            if self.level is not EvidenceLevel.L1:
                raise ValueError("aspect_terms 仅用于 L1 证据卡")
            if self.relevance != "relevant":
                raise ValueError("不相关评论不得设置 aspect_terms")
            if len(self.aspect_terms) > 20 or any(
                not isinstance(term, str) or not term.strip() or len(term) > 80
                for term in self.aspect_terms
            ):
                raise ValueError("aspect_terms 须为 1–20 个非空术语，每个不超过 80 字符")
        if self.classification_method is not None:
            if self.level is not EvidenceLevel.L1:
                raise ValueError("classification_method 仅用于 L1 证据卡")
            if self.classification_method not in {"rule", "manual", "llm", "ensemble"}:
                raise ValueError(f"classification_method 非法: {self.classification_method}")
        if self.classification_note is not None:
            if not self.classification_method:
                raise ValueError("classification_note 需要 classification_method")
            if len(self.classification_note) > 500:
                raise ValueError("classification_note 超过 500 字符")
        if self.review_required is not None:
            if self.level is not EvidenceLevel.L1:
                raise ValueError("review_required 仅用于 L1 证据卡")
            if not isinstance(self.review_required, bool):
                raise ValueError("review_required 必须是布尔值或 None")
        if self.review_reasons and self.review_required is None:
            raise ValueError("review_reasons 需要 review_required")


@dataclass(frozen=True)
class Decision:
    """判定结果：四值状态 + 全链路可追溯数据（去重摘要、区间、门禁、功效注记）。

    dedup_by_card 与输入 cards 等长对齐（非 L1 位 None），供路由把去重结果
    序列化到卡面 dedup 字段——去重先于计数（R2），且逐卡可审计。
    """

    state: DecisionState
    gate_status: GateStatus
    support_interval: WilsonInterval | None
    oppose_interval: WilsonInterval | None
    n_total: int  # 输入卡数
    n_l1: int  # L1 卡数（去重前）
    n_polarized: int  # 去重后有极性样本数（门禁与区间分母，对抗审查 C4 口径）
    n_insufficient: int  # 去重后无极性信号的簇数（单独报告比例，不进分母）
    dedup_clusters: int  # L1 去重后簇数
    dedup_duplicated: int  # 被并簇的摘录数（n_l1 - dedup_clusters）
    dedup_by_card: tuple[DedupInfo | None, ...] = field(default=())
    power_note: str = ""
    inference_note: str = INFERENCE_NOTE


def can_support_preference_claim(cards: list[EvidenceCard]) -> bool:
    """只有通过门禁并形成样本内决定性多数的 L1 证据才可支撑偏好表述。

    该判断仍受非随机样本限制，不得外推为总体消费者偏好。
    """
    return decide(cards).state in {DecisionState.SUPPORTED, DecisionState.REFUTED}


def stance_of_card(card: EvidenceCard) -> Stance:
    """单卡立场合规化：L1 保留抽取信号，L2/L3 恒 insufficient（硬约束 1 的卡级落点）。

    这是判定管道**输入侧**的卡级 stance 归一规则，不是判定——判定走 decide()。
    卡面 stance 一律经本函数归一，不得手工指定绕过。
    """
    return card.stance if card.level is EvidenceLevel.L1 else Stance.INSUFFICIENT


def decide(cards: list[EvidenceCard]) -> Decision:
    """判定入口：L1 过滤 → 去重（R2）→ 计数 → 门禁 → 区间 → 四值映射（R3 次序）。

    L2/L3 卡绝不进判定（硬约束 1；R5 同源纪律）；insufficient 卡不进区间
    分母（对抗审查 C4 口径），只单独报告簇数。
    """
    l1_positions = [
        i
        for i, c in enumerate(cards)
        if c.level is EvidenceLevel.L1 and c.relevance == "relevant"
    ]
    dedup_by_card: list[DedupInfo | None] = [None] * len(cards)

    if not l1_positions:
        return Decision(
            state=DecisionState.INSUFFICIENT,
            gate_status=GateStatus.NO_L1,
            support_interval=None,
            oppose_interval=None,
            n_total=len(cards),
            n_l1=0,
            n_polarized=0,
            n_insufficient=0,
            dedup_clusters=0,
            dedup_duplicated=0,
            dedup_by_card=tuple(dedup_by_card),
            power_note=power_note(0),
        )

    l1_cards = [cards[i] for i in l1_positions]
    infos = deduplicate(
        [card.excerpt for card in l1_cards],
        [card.stance.value for card in l1_cards],
    )
    for pos, i in enumerate(l1_positions):
        dedup_by_card[i] = infos[pos]

    # R2：只统计簇代表（is_canonical），重复摘录不进计数
    canonical_stances = [
        l1_cards[pos].stance for pos, info in enumerate(infos) if info.is_canonical
    ]
    k_support = sum(1 for s in canonical_stances if s is Stance.SUPPORT)
    k_oppose = sum(1 for s in canonical_stances if s is Stance.OPPOSE)
    n_insufficient = sum(1 for s in canonical_stances if s is Stance.INSUFFICIENT)
    n_polarized = k_support + k_oppose
    clusters = len(canonical_stances)
    duplicated = len(infos) - clusters

    support_interval = wilson_interval(k_support, n_polarized) if n_polarized else None
    oppose_interval = wilson_interval(k_oppose, n_polarized) if n_polarized else None

    # R3 固定消费次序：门禁 → 区间（决定性多数）→ 冲突（区间重叠）→ insufficient
    if n_polarized == 0:
        state, gate = DecisionState.INSUFFICIENT, GateStatus.NO_POLARIZED
    elif below_minimum(n_polarized):
        state, gate = DecisionState.INSUFFICIENT, GateStatus.BELOW_MINIMUM
    elif support_interval is not None and support_interval.lo > 0.5:
        state, gate = DecisionState.SUPPORTED, GateStatus.PASS
    elif oppose_interval is not None and oppose_interval.lo > 0.5:
        state, gate = DecisionState.REFUTED, GateStatus.PASS
    elif (
        k_support > 0
        and k_oppose > 0
        and support_interval is not None
        and oppose_interval is not None
        and intervals_overlap(support_interval, oppose_interval)
    ):
        state, gate = DecisionState.CONFLICTING, GateStatus.PASS
    else:
        # 防御性兜底：n_polarized 过门禁且二项份额互补时不可达
        # （分离当且仅当一侧份额下界 > 0.5，已被上两个分支捕获）
        state, gate = DecisionState.INSUFFICIENT, GateStatus.PASS

    return Decision(
        state=state,
        gate_status=gate,
        support_interval=support_interval,
        oppose_interval=oppose_interval,
        n_total=len(cards),
        n_l1=len(l1_positions),
        n_polarized=n_polarized,
        n_insufficient=n_insufficient,
        dedup_clusters=clusters,
        dedup_duplicated=duplicated,
        dedup_by_card=tuple(dedup_by_card),
        power_note=power_note(n_polarized),
    )


def decide_by_claim(
    cards: list[EvidenceCard], claim_ids: tuple[str, ...]
) -> dict[str, Decision]:
    """按卖点假设分别判定，未归属卡片不进入任何卖点结论。"""
    return {
        claim_id: decide(
            [
                card
                for card in cards
                if card.claim_id == claim_id and card.relevance == "relevant"
            ]
        )
        for claim_id in claim_ids
    }
