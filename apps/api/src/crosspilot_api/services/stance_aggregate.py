"""证据层：多标注器固定规则聚合（ADR-0005 A4、R4）。

两票制（对抗审查 C1 修正：原三票制引用了不存在的「双语词表」标注器——
代码现状只有规则基线与 LLM 适配器两个标注函数）：
- 两票一致 → 该立场，annotator_agreement=True；
- LLM 缺席（凭据缺省 / 运行时回退）→ 用规则票，annotator_agreement=None
  （单标注器无法评估一致度；R6：缺席显式传播，不静默吞掉）；
- 两票分歧 → INSUFFICIENT + annotator_agreement=False（R4：标注冲突
  ≠ 证据冲突——这是标注器不确定性，不产生 conflicting 判定）。

不学权重（零训练硬约束）：固定规则、每票来源可解释；precision 以
GERestaurant / MARC 双域评测为准（eval_stance_baseline.py）。

运行时接线状态（2026-11-25 审计）：本模块按 ADR-0005 A4 实现并由单测覆盖，
但尚未接入 API 运行链路——生产默认仍是规则基线单标注器（卡面 llm=None）；
待 LLM 凭据到位、启用 ensemble 评测档后再接入。当前为**显式预留模块**，
不要在无 LLM 票的路径上调用它来凑两票。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.evidence import Stance, StanceVotes


@dataclass(frozen=True)
class AggregateStance:
    """聚合结果：卡级最终立场 + 标注器一致度（进卡面字段，逐卡可审计）。"""

    stance: Stance
    annotator_agreement: bool | None  # None = 单标注器无法评估（R6 传播）


def aggregate_stance(votes: StanceVotes) -> AggregateStance:
    """按固定规则聚合两票立场。

    - votes.llm is None → 规则票生效，agreement=None（缺席显式传播）；
    - 两票一致 → 该立场，agreement=True；
    - 两票分歧 → insufficient，agreement=False（R4：标注冲突 ≠ 证据冲突）。
    """
    if votes.llm is None:
        return AggregateStance(stance=votes.rule, annotator_agreement=None)
    if votes.llm is votes.rule:
        return AggregateStance(stance=votes.rule, annotator_agreement=True)
    return AggregateStance(stance=Stance.INSUFFICIENT, annotator_agreement=False)
