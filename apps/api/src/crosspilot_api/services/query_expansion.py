"""双语检索式扩展：中文查询词 ↔ 英文检索式的透明映射层。

背景（2026-11-21 实测）：中文查询词在英文 Safety Gate 库零命中、英文词在中文知乎
快照零命中——中英文查询各查各的库，对照矩阵另一半永远空白。

本模块提供**人工核校的演示域词表**（非机器翻译，不引入任何模型依赖）：
- 映射目标对齐**库内真实词汇**：2026-11-21 对近邻品类 519 条主表
  （product/product_name/brand/danger/measures）实测词频为 backpack 4、wallet 4、
  rucksack 2、sports bag 2、storage bag 1、handbag 1；复合营销词（packing cube、
  travel organizer 等）在库内零出现，故不作映射目标——检索式必须对齐库内词汇，
  避免想当然的零命中
- wallet 虽有 4 次命中但语义超出收纳包域，不收录
- 只做整词精确匹配（大小写不敏感），不做子串猜测，避免过度扩展
- 局限如实声明：词表只覆盖演示域核心词；命中结果是**候选**证据，语义归属由前端
  「未归属证据」组人工复核（检索管召回，不管相关性判定）；用户输入词表外的词时
  不扩展、原样检索

live 模式知乎检索不使用扩展（配额 10 次/日，扩展会成倍消耗额度）——扩展只用于
本地零成本路径（Safety Gate 检索、知乎快照文件名查找）。此取舍见路由层。
"""

from __future__ import annotations

#: 双语词表：key = 查询词（小写原样），value = 等价/近义检索式（小写）。
#: 映射目标均为近邻品类主表实测出现的产品词（见模块 docstring 词频依据）。
BILINGUAL_GLOSSARY: dict[str, tuple[str, ...]] = {
    "旅行收纳包": ("backpack", "rucksack", "sports bag", "storage bag"),
    "收纳包": ("storage bag", "handbag"),
    "收纳袋": ("storage bag",),
    "双肩包": ("backpack", "rucksack"),
    "背包": ("backpack", "rucksack"),
    "运动包": ("sports bag",),
    "手提包": ("handbag",),
    "backpack": ("双肩包", "背包", "旅行收纳包"),
    "rucksack": ("双肩包", "背包", "旅行收纳包"),
    "sports bag": ("运动包", "旅行收纳包"),
    "storage bag": ("收纳包", "收纳袋", "旅行收纳包"),
    "handbag": ("手提包", "收纳包", "旅行收纳包"),
}


def expand_query(query: str) -> list[str]:
    """查询词 → 原词 + 词表映射的等价检索式（去重、保序，原词永远第一）。

    词表未命中时返回仅含原词的单元素列表（不扩展、不编造）。
    """
    needle = query.strip().lower()
    if not needle:
        return []
    variants = list(dict.fromkeys((needle, *BILINGUAL_GLOSSARY.get(needle, ()))))
    return variants
