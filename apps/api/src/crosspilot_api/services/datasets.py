"""数据源注册表：许可边界的唯一事实来源。

硬约束 2/3/4/5 在此实现。新增数据源必须在此登记，否则适配器拒绝加载。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Tier(StrEnum):
    """证据层级。L1 可单独支撑偏好结论，L2/L3 不可。"""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    BENCHMARK = "benchmark"
    TOOL = "tool"


@dataclass(frozen=True)
class DataSource:
    key: str
    license: str
    commercial_ok: bool
    requires_credential: bool
    note: str
    tier: Tier = Tier.L3
    #: 接入优先级。P0=公开接口零凭据，P1=免费注册无审批，P2=需人工环节。
    priority: str = "P2"
    #: True 表示该源产出的是卖家自撰文案，只能进「企业假设」栏。
    seller_side_only: bool = False
    #: 单次调用返回上限；None 表示无显式截断风险。
    page_limit: int | None = None


# 注（2026-11-21）：演示证据卡（旅行收纳包场景，见 services/demo_evidence.py）不登记进本注册表。
# 理由：REGISTRY 是真实外部数据源的许可与可达性唯一事实来源，虚构的「demo 源」一旦登记，
# 会被真实适配器与闸门误当作可调用源。演示卡以 is_demo_data=True 标识（赛事合规：
# 显式演示标识且不与真实反馈同卡混排），其 L1 声明复用已登记的 amazon_reviews_2023，
# 由 /api/evidence/demo 端点经 assert_demand_side(DEMO_L1_SOURCE_KEY) 走既有闸门校验。
REGISTRY: dict[str, DataSource] = {
    # ---- P0：公开接口 / 公开下载，零凭据零审批 ----
    "amazon_reviews_2023": DataSource(
        "amazon_reviews_2023", "Apache-2.0", True, False,
        "L1 主数据栈，5.71 亿条。2026-11-21 试点已入库（data/sources/"
        "amazon_reviews_2023/，全库最小分片 6207 条）。hf-mirror.com 镜像可达："
        "api/tree 200/1.3s，/resolve/ 分片直下（302 至官方 CDN cas-bridge."
        "xethub.hf.co，本机可达，支持 Range）；/parquet 400（脚本加载型，无 "
        "parquet 分片）；镜像不代理 datasets-server，/rows /filter 不可用。"
        "数据集为 Amazon.com 美国全站，无 marketplace/language 列，无法筛德国"
        "子集——对德国市场不构成 L1，德国侧仍需品牌授权导出",
        Tier.L1, "P1",
    ),
    "hf_dataset_viewer": DataSource(
        "hf_dataset_viewer", "open", True, False,
        "2026-11-20 实测：huggingface.co 与 datasets-server.huggingface.co "
        "DNS 可解析但 TCP 443 全程超时（28s）。2026-11-21 复测：官方站仍超时；"
        "hf-mirror.com 可代理 Hub API（api/tree/resolve 均 200，文件经官方 "
        "CDN 下载成功）但不代理 datasets-server：/rows 307 至 /Rows 网页路由、"
        "/filter 返回网页 HTML，均非 JSON API。100 行分页纪律保留，当前无可用"
        "接入路径，直连分片路径见 amazon_reviews_2023",
        Tier.L1, "P1", page_limit=100,
    ),
    "eurostat": DataSource(
        "eurostat", "open", True, False,
        "L3 市场语境。2026-11-20 实测：200/16s；isoc_ec_ib20 覆盖 2021-2025，"
        "2026 调查年未发布；isoc_ec_ibuy 为 2002-2019 停更集，不纳入",
        Tier.L3, "P0",
    ),
    "eu_comext": DataSource(
        "eu_comext", "open", True, False,
        "L3 中国→德国 HS4202 贸易语境。2026-11-21 入库（data/sources/eu_comext/，"
        "1924 行）。取数路径：Comext 专用 API api/comext/dissemination/statistics/"
        "1.0/data/DS-045409 按过滤取数，26 次调用全 200 共 111KB，零凭据；官方"
        "明示禁止整库下载，无过滤请求会流式超时，必须逐产品过滤。覆盖：年度 "
        "2021-2025 有值，2026 年度未发布；月度至 2026-09，2026 为不完整年。局限："
        "API product 维度上限 HS6，CN8 八位子目经 SDMX 实测 400 "
        "INVALID_QUERY_DIMENSION_VALUE，细目只能走 bulk 7z（未取）；观测缺席≠"
        "确认零贸易；partner=CN 不含港/澳/台",
        Tier.L3, "P0",
    ),
    "destatis": DataSource(
        "destatis", "DL-DE-BY-2.0", True, True,
        "L3 德国官方统计。2026-11-20 实测：域名已迁至 genesis.destatis.de（www- 前缀 307 跳转）；"
        "匿名 GAST/GAST 被重定向到注册公告页，取数需注册，故由 P0 降为 P1",
        Tier.L3, "P1",
    ),
    "eu_safety_gate": DataSource(
        "eu_safety_gate", "CC0-1.0", True, False,
        "L3 德国侧监管端一手信号。2026-11-20 已入库 302/302 期、3255 条德国相关警报。"
        "明细 URL 必须带 search=WEB_REPORT|:|{id} 否则 400；元素名为 notifications（复数）；"
        "danger/measures 已清洗邮箱与电话",
        Tier.L3, "P0",
    ),
    "gdelt_doc": DataSource(
        "gdelt_doc", "unrestricted-with-attribution", True, False,
        "L3 德语媒体语境。2026-11-20 实测限速远严于官方 1 req/5s：9s/15s/20s 间隔均出现 429，"
        "25s+30s 退避+75s 冷却仍每两窗丢一窗；仅取回 2021H1-2022H2 共 4 窗 1090 条，"
        "coverage_complete=false。只返回标题与链接，不含正文。大批量应改用官方 ngrams 数据集",
        Tier.L3, "P0", page_limit=250,
    ),
    "opus_paracrawl": DataSource(
        "opus_paracrawl", "CC0-1.0", True, False, "硬约束 3：仅 ParaCrawl",
        Tier.TOOL, "P0",
    ),
    "usage_bielefeld": DataSource(
        "usage_bielefeld", "community-free", False, False,
        "立场抽取评测基准。2026-11-21 查证并入库（data/sources/usage_bielefeld/）："
        "Klinger & Cimiano LREC 2014 论文官方发布 v1.0.2（romanklinger.de/"
        "usagecorpus），622 英 + 611 德条 Amazon 评论的 aspect/主观短语/极性/"
        "TARG-SUBJ 目标关系标注，三判据全命中。许可页面声明 ODC-By 1.0（署名开放），"
        "登记保持 community-free 保守口径未放宽：作者同时声明勿再分发评论原文、"
        "含文本版不公开。公开语料不含评论文本（版权限制），规则立场基线（全文输入）"
        "无法在其上评测，只作 span 级标注基准；金标立场为派生口径"
        "（insufficient 占 50%）",
        Tier.BENCHMARK, "P0",
    ),
    "gerestaurant": DataSource(
        "gerestaurant", "CC-BY-4.0", True, False,
        "德语 ABSA 基准，3078 条餐厅评论含 aspect 与极性标注；许可可商用，餐厅域不可外推。"
        "2026-11-21 已入库（data/sources/gerestaurant/）：上游仓库 .gitignore 排除数据文件、"
        "HF 不可达，数据原件取自 fork kartik-gadhvi/GERestaurant（提交 2024-09-13）。"
        "规则立场基线全量实测：accuracy 0.610，宏 F1 0.533（baseline_eval.md）",
        Tier.BENCHMARK, "P0",
    ),
    # ---- P1：免费注册，无人工审批 ----
    "un_comtrade": DataSource(
        "un_comtrade", "registered-free", True, True,
        "硬约束 4：禁用 preview 截断结果", Tier.L3, "P1", page_limit=100_000,
    ),
    "deepl_free": DataSource(
        "deepl_free", "free-tier-no-dpa", True, True,
        "硬约束 5：Free 档无 DPA，禁止传入任何含个人数据的文本；50 万字符/月",
        Tier.TOOL, "P1",
    ),
    "openalex": DataSource(
        "openalex", "open", True, False,
        "L3 学术背景。2026-02 起 polite pool 废弃，mailto 参数被忽略；"
        "per_page<=100，基础分页上限 10000 条，超出用 cursor",
        Tier.L3, "P1", page_limit=100,
    ),
    "ebay_browse": DataSource(
        "ebay_browse", "developer-program-free", True, True,
        "德国站在售商品卖点与价格，补 Amazon 2023-09 时效缺口。"
        "5000 次/日按 AppKey+API 名聚合，不按 marketplace 拆分；单次最多 200 条。"
        "返回内容是卖家自撰文案，只进企业假设栏",
        Tier.L1, "P1", seller_side_only=True, page_limit=200,
    ),
    # ---- P2：需人工环节 ----
    "zhihu_open": DataSource(
        "zhihu_open", "platform-terms", True, True,
        "L2，实测 10 次/日，禁批量爬取；适配器已实现（snapshot+live 双路径、配额守卫、"
        "摘录≤300字符不落全文），快照样例为演示撰写待真实预跑替换", Tier.L2, "P2",
    ),
    "marc": DataSource(
        "marc", "research-only", False, False,
        "硬约束 2：商业化启动即下线；研究许可，不进证据卡。2026-11-21 已入库"
        "（data/sources/marc/）：官方 HF 仓库因 Amazon 要求下架，数据取自 "
        "hf-mirror 镜像 mteb/amazon_reviews_multi 的 de test+validation 分片"
        "（各 5000 条，商品域；品类字段在该镜像中丢失，详见其 README）。"
        "规则立场基线全量实测：accuracy 0.580，宏 F1 0.530，较 GERestaurant "
        "餐厅域（0.610/0.533）accuracy 退化 -0.030，词典域偏置证实"
        "（baseline_eval.md）",
        Tier.BENCHMARK, "P2",
    ),
    "datagovhk": DataSource(
        "datagovhk", "open-no-resale", True, False,
        "L3 背景。2026-11-18 核验：十大出口目的地无德国，不得进对照矩阵；禁转售，须署名",
        Tier.L3, "P2",
    ),
    "shenzhen_opendata": DataSource(
        "shenzhen_opendata", "free-no-transfer", True, True,
        "L3。2026-11-18 核验：无德国相关数据，已停用；条款禁有偿无偿转让",
        Tier.L3, "P2",
    ),
}

# 硬约束 3：OpenSubtitles 明确排除，不得加入 REGISTRY。
FORBIDDEN = frozenset({"opus_opensubtitles"})


def assert_usable(key: str, *, commercial: bool, credential: str | None = None) -> DataSource:
    """使用数据源前的统一闸门。违规直接抛错，不做静默降级。"""
    if key in FORBIDDEN:
        raise PermissionError(f"{key} 被硬约束明确排除（许可不明）")
    source = REGISTRY.get(key)
    if source is None:
        raise KeyError(f"{key} 未在数据源注册表登记，先更新 docs/CONSTRAINTS.md")
    if commercial and not source.commercial_ok:
        raise PermissionError(f"{key} 仅限非商业用途，商业化路径下必须下线")
    if source.requires_credential and not credential:
        raise PermissionError(f"{key} 必须提供凭据，禁止匿名或 preview 调用")
    return source


def assert_demand_side(key: str) -> DataSource:
    """写入对照矩阵「消费者证据」侧前的闸门。

    卖家自撰文案（eBay 挂牌、Amazon 商品元数据）只能进「企业假设」栏；
    L2/L3 不得单独支撑偏好结论，只能生成待验证问题。
    """
    source = REGISTRY.get(key)
    if source is None:
        raise KeyError(f"{key} 未在数据源注册表登记，先更新 docs/CONSTRAINTS.md")
    if source.seller_side_only:
        raise PermissionError(
            f"{key} 返回的是卖家自撰文案，只能写入企业假设栏，不得作为消费者证据"
        )
    if source.tier is not Tier.L1:
        raise PermissionError(
            f"{key} 为 {source.tier.value}，不得单独支撑消费者偏好结论，只能生成待验证问题"
        )
    return source
