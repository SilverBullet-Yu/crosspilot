"""领域模型：证据卡与证据层级。

本模块不依赖 FastAPI、不发网络请求，可被测试直接导入。
硬约束 1（L2/L3 不得单独支撑偏好结论）在此实现，不要在路由层重复判断。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class EvidenceLevel(StrEnum):
    """证据层级。见 docs/CONSTRAINTS.md 第二节。"""

    L1 = "L1"  # 目标市场一手消费者反馈
    L2 = "L2"  # 中文从业者经验、二手转述
    L3 = "L3"  # 宏观统计与市场语境


class Stance(StrEnum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    INSUFFICIENT = "insufficient"


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

    def __post_init__(self) -> None:
        missing = [
            name
            for name in ("excerpt", "source_url", "language", "published_on", "level")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"证据卡缺少必现字段: {missing}")


def can_support_preference_claim(cards: list[EvidenceCard]) -> bool:
    """判断一组证据能否支撑「目标市场消费者偏好」结论。

    硬约束 1：仅 L1 证据可以。L2（知乎）与 L3（宏观统计）无论数量多少，
    都只能产出待验证问题，不得直接写入偏好结论。
    """
    return any(card.level is EvidenceLevel.L1 for card in cards)


def resolve_stance(cards: list[EvidenceCard]) -> Stance:
    """汇总对照结论。

    证据不足与证据冲突是两个必须可见的产品状态，不得被合并或降级为灰字。
    """
    if not can_support_preference_claim(cards):
        return Stance.INSUFFICIENT
    l1 = [c for c in cards if c.level is EvidenceLevel.L1]
    has_support = any(c.stance is Stance.SUPPORT for c in l1)
    has_oppose = any(c.stance is Stance.OPPOSE for c in l1)
    if has_support and has_oppose:
        return Stance.OPPOSE  # 冲突：保留矛盾，由前端左右并排呈现原文
    if has_support:
        return Stance.SUPPORT
    if has_oppose:
        return Stance.OPPOSE
    return Stance.INSUFFICIENT
