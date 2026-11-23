"""信号层测试：近重复去重（ADR-0005 A3、R2、短文本守卫 C6）。"""

from __future__ import annotations

import pytest

from crosspilot_api.services.evidence_dedup import (
    DEDUP_THRESHOLD,
    MIN_CLUSTER_TEXT_LEN,
    deduplicate,
    jaccard_similarity,
    normalize_text,
)

# 30 条互异长文本的骨架（>20 字符，Jaccard 远低于阈值）
_UNIQUE_TEXTS = [
    f"Der {adjective} Beutel für {item} hat {count} Innentaschen und trägt sich gut."
    for adjective, item, count in (
        ("stabile", "Reisen", "zwei"),
        ("robuste", "Kabel", "drei"),
        ("leichte", "Socken", "vier"),
        ("große", "Pullover", "fünf"),
        ("kleine", "Kosmetik", "sechs"),
    )
]


class TestNormalize:
    def test_folds_sz_and_case(self) -> None:
        """ß→ss 折叠；ö/ü 不做 oe/ue 转写（与 stance_baseline 同源口径）。"""
        assert normalize_text("Größe reißt") == "grössereisst"

    def test_strips_punctuation(self) -> None:
        assert normalize_text("Sehr gut! (Top.)") == "sehrguttop"


class TestSimilarity:
    def test_identical_texts_score_one(self) -> None:
        text = "Nach drei Wochen ist der Reißverschluss schwergängig und verklemmt sich."
        assert jaccard_similarity(text, text) == 1.0

    def test_distinct_texts_score_low(self) -> None:
        a = "Die Nähte der kleinen Beutel sind nach dem ersten Urlaub aufgerissen."
        b = "Die Reißverschluss-Zipper sind so klein, dass kalte Finger sie kaum greifen."
        assert jaccard_similarity(a, b) < 0.5

    def test_threshold_is_conservative(self) -> None:
        """宁少合并（R6）：阈值 0.85，高相似模板才聚簇。"""
        assert DEDUP_THRESHOLD >= 0.8


class TestDeduplicate:
    def test_unique_texts_all_canonical(self) -> None:
        infos = deduplicate(_UNIQUE_TEXTS)
        assert len(infos) == len(_UNIQUE_TEXTS)
        assert all(info.is_canonical for info in infos)
        assert all(info.dup_count == 1 for info in infos)
        assert len({info.cluster_id for info in infos}) == len(_UNIQUE_TEXTS)

    def test_exact_duplicate_joins_cluster(self) -> None:
        texts = [*_UNIQUE_TEXTS, _UNIQUE_TEXTS[2]]
        infos = deduplicate(texts)
        assert infos[2].is_canonical is True
        assert infos[5].is_canonical is False
        assert infos[5].cluster_id == infos[2].cluster_id
        assert infos[2].dup_count == 2
        # 其余仍是单簇代表
        assert sum(1 for info in infos if info.is_canonical) == len(_UNIQUE_TEXTS)

    def test_template_variant_joins_cluster(self) -> None:
        """模板变体（刷评常见形态：逐字复制 + 改 1 词）：3-gram 高相似 ≥ 阈值 → 同簇。"""
        template = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach zwei Tagen Lüften nicht neutral."
        )
        variant = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach 2 Tagen Lüften nicht neutral."
        )
        assert jaccard_similarity(template, variant) >= DEDUP_THRESHOLD
        infos = deduplicate([template, variant])
        assert infos[0].cluster_id == infos[1].cluster_id
        assert infos[0].is_canonical and not infos[1].is_canonical

    def test_short_texts_never_cluster(self) -> None:
        """短文本守卫（C6）：归一化后几乎相同的短好评（无守卫则 Jaccard=1 必聚），
        因长度低于守卫各自单簇。"""
        a, b = "Sehr gut!", "Sehr gut"
        assert len(normalize_text(a)) < MIN_CLUSTER_TEXT_LEN
        assert jaccard_similarity(a, b) == 1.0  # 若无守卫会误聚
        infos = deduplicate([a, b])
        assert infos[0].cluster_id != infos[1].cluster_id
        assert all(info.dup_count == 1 for info in infos)

    def test_transitive_cluster_via_union_find(self) -> None:
        """A≈B、B≈C（A 与 C 低于阈值）→ 并查集传递聚成一簇。"""
        base = (
            "Der Stoff des mittleren Beutels ist nach zwei Wäschen "
            "eingelaufen und passt nicht mehr."
        )
        near = (
            "Der Stoff des mittleren Beutels ist nach zwei Wäschen "
            "eingelaufen und passt nicht mehr hinein."
        )
        far = (
            "Der Stoff des mittleren Beutels ist nach zwei Wäschen "
            "eingelaufen und passt nicht mehr in den Koffer."
        )
        assert jaccard_similarity(base, near) >= DEDUP_THRESHOLD
        assert jaccard_similarity(base, far) >= DEDUP_THRESHOLD
        infos = deduplicate([base, near, far])
        assert len({info.cluster_id for info in infos}) == 1
        assert infos[0].dup_count == 3

    def test_empty_input(self) -> None:
        assert deduplicate([]) == []

    def test_cluster_ids_are_ordered_by_first_occurrence(self) -> None:
        texts = [_UNIQUE_TEXTS[0], _UNIQUE_TEXTS[1], _UNIQUE_TEXTS[0]]
        infos = deduplicate(texts)
        assert [info.cluster_id for info in infos] == [0, 1, 0]

    def test_demo_conflict_dupes_do_not_inflate_count(self) -> None:
        """演示场景的两条重复摘录聚入既有簇：R2 保证计数不被虚增。"""
        from crosspilot_api.services.demo_evidence import DEMO_CONFLICT_CARDS

        infos = deduplicate([card.excerpt for card in DEMO_CONFLICT_CARDS])
        canonical = sum(1 for info in infos if info.is_canonical)
        assert canonical == 30  # 15 support + 15 oppose，重复摘录不新增簇
        assert len(infos) == 32  # 32 张卡 → 30 簇

    @pytest.mark.parametrize("count", [30, 120])
    def test_scales_to_hundreds(self, count: int) -> None:
        """规模 ≤ 数百时全对比在毫秒级完成（ADR-0005 精确 Jaccard 前提）。"""
        texts = [
            f"Karte {i} über die Packwürfel mit eigener Aussage {i * 7}."
            for i in range(count)
        ]
        infos = deduplicate(texts)
        assert len(infos) == count
