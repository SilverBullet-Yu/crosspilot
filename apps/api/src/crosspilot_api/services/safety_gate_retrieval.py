"""EU Safety Gate 近邻品类检索服务。

数据区：data/sources/eu_safety_gate/（ADR-0003 四件套），主表 3,255 条德国相关警报，
本服务只取近邻品类子集。全部数据本地读取，零网络请求。

关于 source_url 的处理方式（如实声明，宁可不完美也不编造）：
- 首选：raw/report_*.xml 每条 <notifications> 自带官方给定的公开通知页链接字段
  <reference>（形如 https://ec.europa.eu/safety-gate-alerts/screen/webReport/alertDetail/10118675），
  逐字采用，不做任何拼接改写。当前库内近邻品类子集 100% 命中该字段（零缺失、零冲突）。
  受任务「零网络请求」约束，本机未做 HTTP 可达性核验；URL 来源为官方 XML 原文，
  可信度取决于官方数据本身。
- 降级：raw/ 不入库（.gitignore 排除）。若运行环境缺 raw/，退回推导 URL
  https://ec.europa.eu/safety-gate-alerts/public/web-notification/{case_number 百分号编码}，
  该推导格式**未经验证**（无法联网核验），仅在 raw 缺失时占位使用。
"""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

from ..config import REPO_ROOT
from ..domain.evidence import EvidenceCard, EvidenceLevel, stance_of_card

SAFETY_GATE_DIR = REPO_ROOT / "data" / "sources" / "eu_safety_gate"
SAFETY_GATE_CSV = SAFETY_GATE_DIR / "safety_gate_de_alerts_2021_2026.csv"
SAFETY_GATE_RAW_DIR = SAFETY_GATE_DIR / "raw"

# 近邻品类以 CSV category 列的实际字符串为准（README 用的是简称，不是原文）。
NEAR_NEIGHBOR_CATEGORIES: frozenset[str] = frozenset(
    {
        "Toys",
        "Childcare articles and children's equipment",  # README 简称 Childcare
        "Clothing, textiles and fashion items",  # README 简称 Clothing & textiles
        "Hobby/sports equipment",  # README 简称 Sports equipment
        "Chemical products",
    }
)

# 品类过滤结果条数（2026-11-21 实测）：五品类合计 519。
# README 写 488 = Toys 271 + Childcare 94 + Chemical products 66 + Clothing 57，
# 未计入 Hobby/sports equipment 31；按任务指定的五品类过滤，实际为 519。
# 数据区更新导致测试失败时，以实测数字更新此常量并复测。
EXPECTED_NEAR_NEIGHBOR_COUNT: int = 519

# 降级 URL 前缀：仅在 raw/ 缺失时使用，格式未经验证（见模块 docstring）。
_FALLBACK_URL_PREFIX = "https://ec.europa.eu/safety-gate-alerts/public/web-notification/"


@dataclass(frozen=True)
class SafetyGateRecord:
    """单条警报的检索记录：检索原文与已构建的证据卡绑定，避免每次请求重建。"""

    case_number: str
    #: 预拼接转小写的检索原文（product/product_name/brand/danger/measures）。
    search_blob: str
    card: EvidenceCard


def parse_publication_date(value: str) -> date:
    """主表 publication_date 为 DD/MM/YYYY（如 08/01/2021），解析失败直接抛错。"""
    return datetime.strptime(value.strip(), "%d/%m/%Y").date()


def resolve_source_url(case_number: str, url_map: dict[str, str]) -> str:
    """解析警报的公开通知页 URL。

    首选 raw XML <reference> 字段原文（官方给定的通知详情页）；
    raw 缺失时降级为推导 URL，该格式未经验证，如实标注于模块 docstring。
    """
    official = url_map.get(case_number)
    if official:
        return official
    return _FALLBACK_URL_PREFIX + quote(case_number, safe="")


def _load_case_url_map(raw_dir: Path) -> dict[str, str]:
    """解析 raw/report_*.xml，建立 case_number → 官方公开通知页 URL 的映射。

    已实测（2026-11-21）：302 期共 19,677 个 case_number，零冲突、零空 reference。
    raw/ 目录不入库（ADR-0003），缺失时返回空映射并走降级 URL，不崩溃。
    """
    urls: dict[str, str] = {}
    if not raw_dir.is_dir():
        return urls
    for path in sorted(raw_dir.glob("report_*.xml")):
        root = ElementTree.parse(path).getroot()
        for node in root.iter("notifications"):
            case = (node.findtext("caseNumber") or "").strip()
            reference = (node.findtext("reference") or "").strip()
            if case and reference:
                urls[case] = reference
    return urls


def _build_record(row: dict[str, str], url_map: dict[str, str]) -> SafetyGateRecord:
    """把一行主表记录转成检索记录。字段缺失直接抛错，不做静默降级。"""
    case_number = (row.get("case_number") or "").strip()
    danger = (row.get("danger") or "").strip()
    measures = (row.get("measures") or "").strip()
    # excerpt：danger 优先，为空则用 measures，保留原文不翻译。
    excerpt = danger or measures
    if not case_number or not excerpt:
        raise ValueError(f"警报记录缺少 case_number 或摘录字段: {row.get('case_number')!r}")
    card = EvidenceCard(
        excerpt=excerpt,
        source_url=resolve_source_url(case_number, url_map),
        language="en",  # danger/measures 为英文
        published_on=parse_publication_date(row.get("publication_date") or ""),
        level=EvidenceLevel.L3,
        sample_size=1,  # 单条警报即单卡
    )
    # stance 一律走 stance_of_card 归一，不得手工指定绕过（L3 必然得到 insufficient）。
    card = replace(card, stance=stance_of_card(card))
    # 检索字段 = product + product_name + brand + danger + measures，预拼接转小写。
    blob = " ".join(
        (
            row.get("product") or "",
            row.get("product_name") or "",
            row.get("brand") or "",
            danger,
            measures,
        )
    ).lower()
    return SafetyGateRecord(case_number=case_number, search_blob=blob, card=card)


def _load_snapshot() -> tuple[SafetyGateRecord, ...]:
    """加载主表 → 先过滤近邻品类 → 逐条构建证据卡。主表自带 UTF-8 BOM。"""
    url_map = _load_case_url_map(SAFETY_GATE_RAW_DIR)
    records: list[SafetyGateRecord] = []
    with SAFETY_GATE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader[str](handle)
        for row in reader:
            if (row.get("category") or "") not in NEAR_NEIGHBOR_CATEGORIES:
                continue
            records.append(_build_record(row, url_map))
    return tuple(records)


_snapshot: tuple[SafetyGateRecord, ...] | None = None
_snapshot_lock = threading.Lock()


def get_snapshot() -> tuple[SafetyGateRecord, ...]:
    """取近邻品类快照。服务启动经 warm_cache 预热，请求期直接命中缓存，不重读数据区。"""
    global _snapshot
    if _snapshot is None:
        with _snapshot_lock:
            if _snapshot is None:
                _snapshot = _load_snapshot()
    return _snapshot


def warm_cache() -> None:
    """服务启动时预热缓存。数据区文件缺失时不在启动期崩溃：查询期会再次尝试并显式报错。"""
    try:
        get_snapshot()
    except OSError:
        return


def search_safety_gate(query: str) -> list[EvidenceCard]:
    """关键词检索：大小写不敏感，匹配 product/product_name/brand/danger/measures。

    空查询或零命中返回空列表，不报错。
    """
    needle = query.strip().lower()
    if not needle:
        return []
    return [record.card for record in get_snapshot() if needle in record.search_blob]


def search_safety_gate_multi(queries: list[str]) -> list[EvidenceCard]:
    """多检索式并集检索：逐词跑子串匹配，按 case_number 去重、保序。

    服务双语检索式扩展（services/query_expansion.py）：中文词与其英文等价式
    一起命中，对照矩阵不再因查询语言而缺一侧。空列表返回空。
    """
    needles = [q.strip().lower() for q in queries if q.strip()]
    if not needles:
        return []
    seen: set[str] = set()
    cards: list[EvidenceCard] = []
    for record in get_snapshot():
        if record.case_number in seen:
            continue
        if any(needle in record.search_blob for needle in needles):
            seen.add(record.case_number)
            cards.append(record.card)
    return cards


def build_real_questions(query: str, hits: int) -> list[str]:
    """L3 信号 → 待验证问题模板。

    只生成「推断/待验证假设」层的提示，不编造统计数字；
    hits 为本次命中的真实条数，用于如实描述信号量。
    """
    topic = query.strip() or "当前查询"
    if hits:
        return [
            f"（推断/待验证假设）近邻品类 L3 监管信号中「{topic}」命中 {hits} 条警报——"
            "待验证：监管判定的危害属性是否同样是德国买家的实际顾虑？需 L1 一手评论复核。",
            "（推断/待验证假设）L3 监管记录不是消费者偏好表达，不得据此声称德国市场喜欢或排斥"
            "该产品——待接入 Amazon Reviews 后再下判断。",
        ]
    return [
        f"（推断/待验证假设）近邻品类 L3 信号未命中「{topic}」——待验证：该产品在德国是否"
        "本就少有监管记录？需官方门户复核并接入 L1 评论补证。",
        "（推断/待验证假设）缺少有效数据不等于无风险——待验证：是否因品牌/品类关键词差异漏检？",
    ]
