"""演示证据卡：显式标识的演示数据，用于呈现「证据冲突」与「已有有限支持」两个产品状态。

合规依据（docs/CONSTRAINTS.md 第四节）：演示回填必须带显式「演示数据」标识，且不与真实
反馈同卡混排。本模块所有卡 is_demo_data=True，只经 /api/evidence/demo 单独返回，
绝不与 /api/evidence 的真实卡混合。

为什么 demo 源不进 services/datasets.py 的 REGISTRY：
REGISTRY 是真实外部数据源的许可与可达性唯一事实来源，虚构的「demo 源」一旦登记，
会被真实适配器与闸门误当作可调用源。演示卡声明其模拟的数据源为 amazon_reviews_2023
（REGISTRY 中唯一的 L1 主数据栈，尚未接入），端点以 assert_demand_side(DEMO_L1_SOURCE_KEY)
走既有闸门校验该声明。

关于演示卡的 stance：卡面 stance 是单条模拟评论的态度信号（support/oppose），
是 resolve_stance 的**输入**；路由层聚合 stance 一律走 domain.resolve_stance，不绕过。

关于 source_url：指向 amazon_reviews_2023 数据集主页（真实站点），卡面内容为本项目
演示撰写，并非来自该页面的具体评论；受零网络请求约束，该 URL 本机未做 HTTP 核验。
"""

from __future__ import annotations

from datetime import date

from ..domain.evidence import EvidenceCard, EvidenceLevel, Stance

#: 演示卡声明模拟的 L1 数据源（REGISTRY 已登记，闸门可通过）。
DEMO_L1_SOURCE_KEY = "amazon_reviews_2023"
#: 演示场景的检索词。
DEMO_QUERY = "旅行收纳包"
#: 演示卡统一指向声明数据源的数据集主页。
DEMO_SOURCE_URL = "https://amazon-reviews-2023.github.io/"


def _demo_card(excerpt: str, published_on: date, stance: Stance) -> EvidenceCard:
    """构造一张 L1 演示卡。单条模拟评论即单卡，样本量 1。"""
    return EvidenceCard(
        excerpt=excerpt,
        source_url=DEMO_SOURCE_URL,
        language="de",  # 模拟德国市场一手评论
        published_on=published_on,
        level=EvidenceLevel.L1,
        sample_size=1,
        stance=stance,
        is_demo_data=True,
    )


# 场景「证据相互冲突」：support 与 oppose 并存（日期取 Amazon Reviews 2023 窗口内）。
DEMO_CONFLICT_CARDS: tuple[EvidenceCard, ...] = (
    _demo_card(
        "Die Packwürfel passen perfekt in meinen 40-Liter-Koffer, das Material wirkt "
        "robust und die Nähte sind sauber verarbeitet.",
        date(2023, 5, 14),
        Stance.SUPPORT,
    ),
    _demo_card(
        "Die Aufteilung ist durchdacht: Wäsche, Kabel und Kosmetik bleiben getrennt, "
        "ich finde alles sofort.",
        date(2023, 8, 2),
        Stance.SUPPORT,
    ),
    _demo_card(
        "Nach drei Wochen ist der Reißverschluss des größten Würfels schwergängig "
        "und verklemmt sich regelmäßig.",
        date(2023, 4, 21),
        Stance.OPPOSE,
    ),
    _demo_card(
        "Der größte Beutel riecht beim Auspacken stark nach Chemie, auch nach zwei "
        "Tagen Lüften nicht wirklich neutral.",
        date(2023, 9, 30),
        Stance.OPPOSE,
    ),
)

# 场景「已有有限支持」：仅 support 信号，样本极少，故为「有限」而非「成立」。
DEMO_LIMITED_CARDS: tuple[EvidenceCard, ...] = (
    _demo_card(
        "Die Organizer sparen enorm Platz im Rucksack, alles bleibt sortiert und "
        "griffbereit.",
        date(2023, 6, 11),
        Stance.SUPPORT,
    ),
    _demo_card(
        "Gute Qualität für den Preis, die Nähte halten auch bei voller Belastung "
        "problemlos.",
        date(2023, 7, 19),
        Stance.SUPPORT,
    ),
)

DEMO_CONFLICT_QUESTIONS: tuple[str, ...] = (
    "（推断/待验证假设）演示场景：旅行收纳包正负评价并存——待验证：反对证据"
    "（拉链耐用性、化学异味）在真实 L1 评论中是否占多数？",
    "（推断/待验证假设）演示场景：负面反馈是否集中在使用数周之后，即短期开箱评论"
    "覆盖不到的维度？需真实评论时间序列复核。",
)

DEMO_LIMITED_QUESTIONS: tuple[str, ...] = (
    "（推断/待验证假设）演示场景：支持证据仅来自个别评论——待验证：对德国买家整体"
    "是否成立？需扩大 L1 样本后复核。",
    "（推断/待验证假设）演示场景：缺少反对证据可能是样本不足所致，不等于产品无缺陷。",
)
