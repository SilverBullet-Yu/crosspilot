"""信号层测试：近重复去重（ADR-0005 A3、R2、短文本守卫 C6）。"""

from __future__ import annotations

import pytest

from crosspilot_api.services.evidence_dedup import (
    DEDUP_THRESHOLD,
    deduplicate,
    find_stance_conflicts,
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

    def test_exact_short_duplicates_cluster(self) -> None:
        """规范化后完全相同的短评必须先去重，不能被短文本守卫绕过。"""
        a, b = "Sehr gut!", "Sehr gut"
        assert normalize_text(a) == normalize_text(b)
        infos = deduplicate([a, b])
        assert infos[0].cluster_id == infos[1].cluster_id
        assert infos[0].is_canonical and not infos[1].is_canonical
        assert all(info.dup_count == 2 for info in infos)

    def test_exact_text_with_opposite_stances_stays_separate(self) -> None:
        text = "Die Tasche ist sehr gut und praktisch."
        infos = deduplicate([text, text], ["support", "oppose"])
        assert infos[0].cluster_id != infos[1].cluster_id
        assert all(info.is_canonical for info in infos)
        assert all(info.dup_count == 1 for info in infos)

    def test_stance_conflict_detects_exact_duplicate_labels(self) -> None:
        text = "Die Tasche ist sehr gut und praktisch."
        assert find_stance_conflicts([text, text], ["support", "oppose"]) == ((0, 1),)
        assert find_stance_conflicts([text, text], ["support", "support"]) == ()

    def test_stance_conflict_detects_near_duplicate_labels(self) -> None:
        template = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach zwei Tagen Lüften nicht neutral."
        )
        variant = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach 2 Tagen Lüften nicht neutral."
        )
        assert find_stance_conflicts([template, variant], ["support", "oppose"]) == ((0, 1),)

    def test_stance_conflict_keeps_short_distinct_texts_out(self) -> None:
        assert find_stance_conflicts(["Sehr gut!", "Sehr schlecht!"], ["support", "oppose"]) == ()

    def test_near_duplicate_with_opposite_stances_stays_separate(self) -> None:
        template = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach zwei Tagen Lüften nicht neutral."
        )
        variant = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach 2 Tagen Lüften nicht neutral."
        )
        infos = deduplicate([template, variant], ["support", "oppose"])
        assert infos[0].cluster_id != infos[1].cluster_id
        assert all(info.is_canonical for info in infos)

    def test_same_stance_near_duplicates_still_cluster(self) -> None:
        template = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach zwei Tagen Lüften nicht neutral."
        )
        variant = (
            "Der größte Beutel riecht beim Auspacken stark nach Chemie, "
            "auch nach 2 Tagen Lüften nicht neutral."
        )
        infos = deduplicate([template, variant], ["oppose", "oppose"])
        assert infos[0].cluster_id == infos[1].cluster_id
        assert infos[0].is_canonical and not infos[1].is_canonical

    def test_stance_length_must_match_texts(self) -> None:
        with pytest.raises(ValueError, match="等长"):
            deduplicate(["Sehr gut"], ["support", "oppose"])

    def test_distinct_short_texts_do_not_cluster(self) -> None:
        """语义相近但并非精确重复的短评仍受近重复短文本守卫保护。"""
        infos = deduplicate(["Sehr gut!", "Sehr schön!"])
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
        assert canonical == 32  # 15 support + 15 oppose + 1 未归属 + 1 不相关
        assert len(infos) == 34  # 34 张卡 → 32 簇；判定管道只取 31 个相关簇

    @pytest.mark.parametrize("count", [30, 120])
    def test_scales_to_hundreds(self, count: int) -> None:
        """规模 ≤ 数百时全对比在毫秒级完成（ADR-0005 精确 Jaccard 前提）。"""
        texts = [
            f"Karte {i} über die Packwürfel mit eigener Aussage {i * 7}."
            for i in range(count)
        ]
        infos = deduplicate(texts)
        assert len(infos) == count
