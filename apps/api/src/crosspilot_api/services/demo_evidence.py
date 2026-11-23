"""演示证据卡：显式标识的演示数据，用于呈现「证据冲突」「已有有限支持」两个产品状态。

合规依据（docs/CONSTRAINTS.md 第四节）：演示回填必须带显式「演示数据」标识，且不与真实
反馈同卡混排。本模块所有卡 is_demo_data=True，只经 /api/evidence/demo 单独返回，
绝不与 /api/evidence 的真实卡混合。

为什么 demo 源不进 services/datasets.py 的 REGISTRY：
REGISTRY 是真实外部数据源的许可与可达性唯一事实来源，虚构的「demo 源」一旦登记，
会被真实适配器与闸门误当作可调用源。演示卡声明其模拟的数据源为 amazon_reviews_2023
（REGISTRY 中唯一的 L1 主数据栈），端点以 assert_demand_side(DEMO_L1_SOURCE_KEY)
走既有闸门校验该声明。

关于演示卡的 stance：卡面 stance 是单条模拟评论的态度信号（support/oppose），
是 domain.decide 判定管道的**输入**；路由层聚合判定一律走 domain.decide，不绕过。

ADR-0005 扩卡设计（2026-11-22 验证记录修正 1 / 对抗审查 C5，三状态演示）：
- conflict 场景 = 15 support + 15 oppose + 2 重复摘录 → 去重后 30 簇、
  两份额区间重叠 → conflicting（并排展示）；重复摘录让 R2「去重先于计数」
  与 dup_count 在演示中可见（计数不变、去重摘要可追溯）。
- limited 场景 = 21 support + 9 oppose → n=30 过门禁，支持份额 0.7 的
  Wilson 95% 下界 0.521 刚过决定线 → supported——「有限支持」的公式化含义
  = 支持占优但区间宽（0.52–0.83），不再是文案修饰。
- 卡文本逐条手写、措辞互异（精确 3-gram Jaccard 全对比下去重不误聚），
  内容覆盖容量 / 功能 / 价格三个假设域（前端关键词归属可命中），
  日期在 Amazon Reviews 2023 窗口内分层分布。

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


# ---------------------------------------------------------------------------
# 支持池（21 条，conflict 取前 15 条，limited 全量）
# ---------------------------------------------------------------------------
_SUPPORT_POOL: tuple[tuple[str, date], ...] = (
    (
        "Die drei Würfel passen exakt in meinen 55-Liter-Trolley, sogar im "
        "Handgepäckfach blieb noch Platz für den kleinen Beutel.",
        date(2023, 3, 14),
    ),
    (
        "Die Aufteilung ist durchdacht: Wäsche, Kabel und Kosmetik bleiben "
        "getrennt, ich finde alles sofort.",
        date(2023, 8, 2),
    ),
    (
        "Gute Qualität für den Preis, die Nähte halten auch bei voller "
        "Belastung problemlos.",
        date(2023, 7, 19),
    ),
    (
        "Wir haben vier Würfel im Familienkoffer verstaut und trotzdem noch "
        "Platz für Schuhe gehabt, die Größenstaffelung ist ideal.",
        date(2023, 5, 2),
    ),
    (
        "Der Zusatzgriff zum Herausnehmen der gefüllten Würfel ist klever "
        "gelöst, nichts rutscht mehr unten aus dem Koffer.",
        date(2023, 4, 11),
    ),
    (
        "Für unter dreißig Euro bekommt man sechs Beutel in stabiler "
        "Verarbeitung, das Preis-Leistungs-Verhältnis ist schwer zu schlagen.",
        date(2023, 3, 28),
    ),
    (
        "Das transparente Sichtfenster der Fächer erspart mir das Öffnen "
        "jedes Beutels, auf einen Blick erkenne ich die Socken.",
        date(2023, 6, 5),
    ),
    (
        "Die Beutel sparen enorm Platz im Rucksack, alles bleibt sortiert "
        "und griffbereit.",
        date(2023, 6, 11),
    ),
    (
        "Zwei der Fächer haben Reißverschluss-Laschen in verschiedenen "
        "Farben, so finde ich Wäsche und Technik ohne Etiketten.",
        date(2023, 7, 2),
    ),
    (
        "Nach vier Wochen Dauereinsatz auf zwei Geschäftsreisen zeigt der "
        "Stoff keine Abnutzung, die Nähte sind doppelt gesäumt.",
        date(2023, 9, 12),
    ),
    (
        "Der größte Würfel fasst meine komplette Fototechnik samt Kabeln, "
        "mit den Trennstege bleibt nichts durcheinander.",
        date(2023, 5, 20),
    ),
    (
        "Der Handgriff auf der Rückseite macht das Ein- und Auspacken im "
        "Hotelzimmer zum Einhandverfahren, sehr praktisch.",
        date(2023, 8, 15),
    ),
    (
        "Bei dem Preis war ich skeptisch, aber Material und Reißverschlüsse "
        "wirken hochwertiger als bei teureren Sets aus dem Kaufhaus.",
        date(2023, 4, 25),
    ),
    (
        "Handgepäck-Check am Flughafen problemlos bestanden, alle Würfel "
        "passten stapelbar in das vorgeschriebene Maß.",
        date(2023, 10, 3),
    ),
    (
        "Die beschriftbaren Fächer sind Gold wert: meine Kinder packen "
        "selbst und finden alles wieder zurück.",
        date(2023, 7, 25),
    ),
    (
        "Die Stoffqualität überzeugt: wasserabweisend, leicht zu reinigen, "
        "nach dem Waschen kein Verziehen.",
        date(2023, 8, 28),
    ),
    (
        "Kompakter als erwartet: geleert fallen die Würfel auf ein Drittel "
        "zusammen, im Schrank kaum Platz nötig.",
        date(2023, 9, 1),
    ),
    (
        "Ich liebe die Innentasche mit Reißverschluss für Wertsachen, Pass "
        "und Geld bleiben bei der Kontrolle griffbereit.",
        date(2023, 6, 18),
    ),
    (
        "Zwei Jahre im Einsatz, nur die weiße Beschriftung ist verblasst – "
        "für den Preis habe ich nichts Besseres gefunden.",
        date(2023, 10, 15),
    ),
    (
        "Die Würfel lassen sich in die vorhandenen Kofferfächer einschieben "
        "wie Schubladen, auspacken ohne Chaos.",
        date(2023, 5, 8),
    ),
    (
        "Auch voll beladen behalten die Beutel ihre Form, der Stoff gibt "
        "nicht nach und die Tragegriffe halten.",
        date(2023, 9, 22),
    ),
)

# ---------------------------------------------------------------------------
# 反对池（15 条，conflict 全量，limited 取第 1–2、4、6–8、10、12–13 条）
# ---------------------------------------------------------------------------
_OPPOSE_POOL: tuple[tuple[str, date], ...] = (
    (
        "Nach drei Wochen ist der Reißverschluss des größten Würfels "
        "schwergängig und verklemmt sich regelmäßig.",
        date(2023, 4, 21),
    ),
    (
        "Der größte Beutel riecht beim Auspacken stark nach Chemie, auch "
        "nach zwei Tagen Lüften nicht wirklich neutral.",
        date(2023, 9, 30),
    ),
    (
        "Für Handgepäck bei Billigairlines sind die Maße knapp: mit "
        "gefüllten Würfeln war mein Koffer über dem Limit.",
        date(2023, 5, 15),
    ),
    (
        "Die Nähte der kleinen Beutel haben nach dem ersten Urlaub "
        "nachgegeben, eine Kante ist bereits aufgerissen.",
        date(2023, 7, 8),
    ),
    (
        "Die Trennstege im größten Würfel sind zu kurz genäht, die Klappe "
        "lässt sich nicht schließen, wenn er voll ist.",
        date(2023, 4, 2),
    ),
    (
        "Qualität entspricht nicht dem Preis: dünner Stoff, der sich beim "
        "Packen sofort falten und knautschen lässt.",
        date(2023, 6, 2),
    ),
    (
        "Der mittlere Beutel fasst weniger als die angegebenen Liter, ein "
        "Paar Schuhe plus Pullover füllt ihn schon komplett.",
        date(2023, 8, 5),
    ),
    (
        "Der Kunststoffgeruch der Netzfächer ist so präsent, dass ich "
        "Kleidung nur noch in den Stoffbeuteln lagern mag.",
        date(2023, 9, 18),
    ),
    (
        "Die Reißverschluss-Zipper sind so klein, dass man sie mit kalten "
        "Fingern kaum greifen kann.",
        date(2023, 5, 30),
    ),
    (
        "Nach zwei Wäschen in der Maschine ist der Stoff eingelaufen, die "
        "Würfel passen nicht mehr ineinander.",
        date(2023, 8, 22),
    ),
    (
        "Leer wiegen die vier großen Würfel fast ein Kilo, bei einem "
        "8-kg-Handgepäck-Limit ist das zu viel Leergewicht.",
        date(2023, 6, 25),
    ),
    (
        "Die Maschen der Fächer sind zu grob gestrickt, feine Strümpfe "
        "ziehen sich an den Maschen fest.",
        date(2023, 7, 15),
    ),
    (
        "Nach dem Preis-Leistungs-Check enttäuschend: für denselben Betrag "
        "gibt es beim Discounter stabilere Sets.",
        date(2023, 9, 5),
    ),
    (
        "Der versprochene Hängehaken an den Würfeln ist so kurz, dass er "
        "an Kleiderstangen nicht über die Stange greift.",
        date(2023, 4, 18),
    ),
    (
        "Die Beschriftungsfelder der Fächer verreiben schon beim ersten "
        "Anfassen, nach einer Woche ist nichts mehr lesbar.",
        date(2023, 10, 8),
    ),
)


def _pool_cards(
    pool: tuple[tuple[str, date], ...], stance: Stance
) -> tuple[EvidenceCard, ...]:
    return tuple(_demo_card(text, day, stance) for text, day in pool)


#: 场景「证据相互冲突」：15:15 + 2 条重复摘录（一条逐字复制、一条措辞微调的
#: 同源变体——两者聚入既有簇、不进计数，R2 与去重摘要在演示中可见）。
_DEMO_CONFLICT_BASE = (
    _pool_cards(_SUPPORT_POOL[:15], Stance.SUPPORT)
    + _pool_cards(_OPPOSE_POOL, Stance.OPPOSE)
)
_DEMO_CONFLICT_DUPES = (
    _demo_card(
        "Nach drei Wochen ist der Reißverschluss des größten Würfels "
        "schwergängig und verklemmt sich regelmäßig.",  # 逐字复制 O1
        date(2023, 5, 19),
        Stance.OPPOSE,
    ),
    _demo_card(
        "Nach drei Wochen ist der Reißverschluss des größten Würfels "
        "schwergängig und verklemmt sich regelmäßig beim Packen.",  # 同源变体（尾部追加，高相似）
        date(2023, 6, 9),
        Stance.OPPOSE,
    ),
)

DEMO_CONFLICT_CARDS: tuple[EvidenceCard, ...] = (
    _DEMO_CONFLICT_BASE + _DEMO_CONFLICT_DUPES
)

#: 场景「已有有限支持」：21:9 → 过门禁、支持份额 0.7 下界 0.521 刚过决定线 → supported。
DEMO_LIMITED_CARDS: tuple[EvidenceCard, ...] = _pool_cards(
    _SUPPORT_POOL, Stance.SUPPORT
) + _pool_cards(
    tuple(
        _OPPOSE_POOL[i]
        for i in (0, 2, 3, 5, 6, 7, 9, 11, 12)
    ),
    Stance.OPPOSE,
)

DEMO_CONFLICT_QUESTIONS: tuple[str, ...] = (
    "（推断/待验证假设）演示场景：旅行收纳包正负评价并存且份额区间重叠——待验证："
    "反对证据（拉链耐用性、化学异味）在真实 L1 评论中是否占多数？",
    "（推断/待验证假设）演示场景：负面反馈是否集中在使用数周之后，即短期开箱评论"
    "覆盖不到的维度？需真实评论时间序列复核。",
)

DEMO_LIMITED_QUESTIONS: tuple[str, ...] = (
    "（推断/待验证假设）演示场景：支持份额 0.7 的 95% 区间下界 0.52 刚过决定线——"
    "待验证：对德国买家整体是否成立？需扩大 L1 样本后复核。",
    "（推断/待验证假设）演示场景：9 条反对证据集中在耐久与气味维度，不等于产品无缺陷。",
)
