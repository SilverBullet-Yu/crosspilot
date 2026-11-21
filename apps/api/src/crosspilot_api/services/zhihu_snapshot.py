"""知乎检索快照读取（L2 中文侧，ADR-0002 演示默认快照模式）。

快照文件位于 data/snapshots/zhihu/<查询词>.json，由 scripts/capture_zhihu_snapshot.py
以真实凭据预跑落盘（live 模式），或为演示撰写的样例（全部卡 is_demo_data=true）。

快照文件 schema（本模块是唯一校验口径，捕获脚本经 build_snapshot_document 产出）：
- 顶层：generated_at_utc（ISO8601 UTC）/ source_api（端点 URL）/ is_demo_data（顶层
  演示标识）/ cards[]。前三个为任务约定必现，is_demo_data 为本模块扩展，用于强制
  「演示标识文件内一致、不与真实反馈混排」（docs/CONSTRAINTS.md 第四节）。
- 卡字段：对齐 packages/contracts/evidence-card.schema.json 的六个必现字段 + stance +
  is_demo_data，另附快照扩展 title / author_anonymous_id（合规最小集，见
  services/zhihu_client.py）。evidence-card.schema.json 本身 additionalProperties=false，
  title / author_anonymous_id 只存在于快照层，构建 EvidenceCard 时丢弃。

降级语义（ADR-0002 决策 4）：快照缺失或损坏 → 返回空列表 + 非空降级提示字符串，
禁止静默返回空结果；正常命中时提示为 None。
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ..config import settings
from ..domain.evidence import EvidenceCard, EvidenceLevel, resolve_stance
from .zhihu_client import (
    EXCERPT_MAX_CHARS,
    ZHIHU_SEARCH_URL,
    ZhihuExtraction,
    sanitize_excerpt,
)

#: 快照目录：data/snapshots/zhihu/。
SNAPSHOT_DIR: Path = settings.snapshot_dir / "zhihu"

#: 顶层必现字段。
_TOP_LEVEL_KEYS = ("generated_at_utc", "source_api", "cards")

#: 卡必现字段（evidence-card.schema.json 六必现 + stance + is_demo_data）。
_CARD_REQUIRED = (
    "excerpt",
    "source_url",
    "language",
    "published_on",
    "level",
    "sample_size",
    "stance",
    "is_demo_data",
)

#: Windows 文件名非法字符（查询词直接用作文件名，必须清洗）。
_ILLEGAL_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')


class SnapshotValidationError(ValueError):
    """快照文件结构或字段不符合 schema。加载器捕获后转为降级提示。"""


def sanitize_query_filename(query: str) -> str:
    """查询词 → 快照文件名主体。非法字符替换为下划线，避免落盘/读取错位。"""
    cleaned = _ILLEGAL_FILENAME_RE.sub("_", query.strip())
    return cleaned or "untitled"


def snapshot_path(query: str) -> Path:
    """查询词对应的快照文件路径。"""
    return SNAPSHOT_DIR / f"{sanitize_query_filename(query)}.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotValidationError(message)


def _parse_card(raw: Any, index: int) -> EvidenceCard:
    """单张快照卡 → EvidenceCard。字段缺失/类型不符直接抛错，不做部分降级。"""
    _require(isinstance(raw, dict), f"cards[{index}] 不是对象")
    card_map: dict[str, Any] = raw  # type: ignore[assignment]  # isinstance 已收窄
    missing = [key for key in _CARD_REQUIRED if key not in card_map]
    _require(not missing, f"cards[{index}] 缺字段: {missing}")
    excerpt = card_map["excerpt"]
    _require(
        isinstance(excerpt, str) and excerpt != "",
        f"cards[{index}].excerpt 必须为非空字符串",
    )
    _require(
        len(excerpt) <= EXCERPT_MAX_CHARS,
        f"cards[{index}].excerpt 超过 {EXCERPT_MAX_CHARS} 字符（不落全文红线）",
    )
    source_url = card_map["source_url"]
    _require(
        isinstance(source_url, str) and source_url.startswith("https://"),
        f"cards[{index}].source_url 必须为 https URL",
    )
    _require(card_map["level"] == "L2", f"cards[{index}].level 必须为 L2（本目录只存知乎快照）")
    _require(card_map["language"] == "zh-CN", f"cards[{index}].language 必须为 zh-CN")
    published = card_map["published_on"]
    _require(isinstance(published, str), f"cards[{index}].published_on 必须为 ISO 日期字符串")
    try:
        published_on = date.fromisoformat(published)
    except ValueError as exc:
        raise SnapshotValidationError(
            f"cards[{index}].published_on 无法解析: {published!r}"
        ) from exc
    sample_size = card_map["sample_size"]
    _require(
        sample_size is None or isinstance(sample_size, int),
        f"cards[{index}].sample_size 类型非法",
    )
    _require(isinstance(card_map["is_demo_data"], bool), f"cards[{index}].is_demo_data 必须为布尔")
    stance_value = card_map["stance"]
    _require(
        stance_value in {"support", "oppose", "insufficient"},
        f"cards[{index}].stance 非法: {stance_value!r}",
    )
    card = EvidenceCard(
        excerpt=excerpt,
        source_url=source_url,
        language="zh-CN",
        published_on=published_on,
        level=EvidenceLevel.L2,
        sample_size=sample_size,
        stance=stance_value,  # type: ignore[arg-type]  # 枚举值已校验
        is_demo_data=card_map["is_demo_data"],
    )
    # stance 聚合一律走 domain 规则复核，不信任落盘值（L2 必然 insufficient）。
    return replace(card, stance=resolve_stance([card]))


def _load_document(path: Path) -> list[EvidenceCard]:
    """读取并校验快照文件。任何结构问题抛 SnapshotValidationError。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SnapshotValidationError(f"快照文件无法读取或非合法 JSON: {exc}") from exc
    _require(isinstance(payload, dict), "快照顶层不是 JSON 对象")
    doc: dict[str, Any] = payload  # type: ignore[assignment]  # isinstance 已收窄
    missing_top = [key for key in _TOP_LEVEL_KEYS if key not in doc]
    _require(not missing_top, f"快照顶层缺字段: {missing_top}")
    cards_raw = doc["cards"]
    _require(isinstance(cards_raw, list), "cards 必须为数组")
    top_demo = doc.get("is_demo_data", False)
    _require(isinstance(top_demo, bool), "顶层 is_demo_data 必须为布尔")
    cards = [_parse_card(raw, index) for index, raw in enumerate(cards_raw)]
    if top_demo:
        # 演示标识文件内一致：顶层声明演示则全部卡必须为演示（不与真实反馈混排）。
        mixed = [i for i, card in enumerate(cards) if not card.is_demo_data]
        _require(not mixed, f"顶层 is_demo_data=true 但 cards 存在真实标识卡: {mixed}")
    elif any(card.is_demo_data for card in cards):
        raise SnapshotValidationError(
            "顶层 is_demo_data=false 但存在 is_demo_data=true 的卡（混排违规）"
        )
    return cards


def load_zhihu_snapshot(query: str) -> tuple[list[EvidenceCard], str | None]:
    """读取查询词对应的知乎快照。

    返回（证据卡列表, 降级提示）。快照缺失或损坏时返回空列表 + 非空提示
    （ADR-0002 决策 4：禁止静默返回空结果）；正常命中时提示为 None。
    """
    path = snapshot_path(query)
    if not path.is_file():
        return (
            [],
            f"知乎快照缺失：{path} 不存在，中文侧 L2 证据暂缺。"
            "正式演示前请用 scripts/capture_zhihu_snapshot.py 以真实凭据预跑替换"
            "（演示标识规则见 docs/CONSTRAINTS.md 第四节）。",
        )
    try:
        return _load_document(path), None
    except SnapshotValidationError as exc:
        return (
            [],
            f"知乎快照损坏（{path}）：{exc}。已按降级处理返回空结果，请重新捕获快照。",
        )


def build_snapshot_document(
    extractions: list[ZhihuExtraction],
    *,
    is_demo_data: bool = False,
    source_api: str = ZHIHU_SEARCH_URL,
) -> dict[str, Any]:
    """合规最小集 → 快照文件文档。捕获脚本与演示样例共用，保证与加载器 schema 同源。

    excerpt 再过一遍 sanitize_excerpt（截断上限 300，双重保险），作者匿名化 ID 由
    adapt 侧传入或由昵称/ContentID 派生。
    """
    cards: list[dict[str, Any]] = [
        {
            "title": extraction.title,
            "author_anonymous_id": extraction.author_anonymous_id,
            "excerpt": sanitize_excerpt(extraction.excerpt),
            "source_url": extraction.source_url,
            "published_on": extraction.published_on.isoformat(),
            "level": "L2",
            "language": "zh-CN",
            "sample_size": 1,
            "stance": "insufficient",
            "is_demo_data": is_demo_data,
        }
        for extraction in extractions
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_api": source_api,
        "is_demo_data": is_demo_data,
        "cards": cards,
    }
