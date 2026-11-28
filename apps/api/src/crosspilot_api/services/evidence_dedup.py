"""信号层：L1 近重复去重（ADR-0005 A3、R2「去重先于计数」）。

L1 规模 ≤ 数百时用**精确字符 3-gram Jaccard 全对比 + 并查集聚类**；MinHash
近似留作规模化升级路径（ADR-0005 验证记录修正 3）。精确相似度逐对可审计、
可直接入 provenance——比 MinHash 估计值更可信、更可追溯。

纪律：
- 短文本守卫（对抗审查 C6）：归一化后 < 20 字符的摘录不参与聚类（自成单簇），
  防止短通用好评（"Sehr gut!" / "Super gut!"）3-gram 虚高误聚；
- 阈值 0.85 宁少合并（R6：阈值偏保守 → 去重变少 → 区间变宽 = 诚实）；
- 同簇取输入序首条为代表（is_canonical），簇内其余标记重复、不进计数。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

#: 近重复判定阈值：Jaccard ≥ 0.85 视为同簇（宁少合并，R6）。
DEDUP_THRESHOLD = 0.85
#: 短文本守卫：归一化长度低于该值的摘录不参与聚类。
MIN_CLUSTER_TEXT_LEN = 20
#: n-gram 宽度（字符级）。
GRAM_N = 3

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


@dataclass(frozen=True)
class DedupInfo:
    """单卡去重结果：簇号、簇大小、是否簇代表。消费者：计数器与卡面展示。"""

    cluster_id: int
    dup_count: int
    is_canonical: bool


def normalize_text(text: str) -> str:
    """去重归一化：NFKC + 小写 + ß→ss（与 stance_baseline 同源坑）+ 去非字母数字。"""
    folded = unicodedata.normalize("NFKC", text).lower().replace("ß", "ss")
    return _NON_WORD.sub("", folded)


def _grams(text: str, n: int = GRAM_N) -> frozenset[str]:
    if len(text) < n:
        return frozenset({text}) if text else frozenset()
    return frozenset(text[i : i + n] for i in range(len(text) - n + 1))


def jaccard_similarity(a: str, b: str) -> float:
    """归一化后的字符 3-gram Jaccard 相似度（精确值，可逐对审计）。"""
    ga, gb = _grams(normalize_text(a)), _grams(normalize_text(b))
    if not ga and not gb:
        return 1.0
    union = len(ga | gb)
    if union == 0:
        return 0.0
    return len(ga & gb) / union


class _UnionFind:
    """小型并查集（路径压缩 + 按秩合并），用于把近重复对聚成簇。"""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


def deduplicate(
    texts: Sequence[str],
    stances: Sequence[str] | None = None,
) -> list[DedupInfo]:
    """对摘录列表做近重复聚类，返回与输入等长的 DedupInfo 列表。

    提供 stances 时仅合并相同立场，防止相同或近似文本下的支持/反对被静默
    丢弃。cluster_id 按簇代表（输入序首条）的出现次序从 0 递增；短文本守卫内
    的摘录与独特摘录各成单簇（dup_count=1）。规范化后完全相同的摘录先去重，
    不受近重复短文本守卫影响。同簇代表 = 输入序首条。
    """
    size = len(texts)
    if size == 0:
        return []
    if stances is not None and len(stances) != size:
        raise ValueError("stances 必须与 texts 等长")

    normalized = [normalize_text(t) for t in texts]
    uf = _UnionFind(size)
    exact_groups: dict[tuple[str, str], list[int]] = {}
    for index, text in enumerate(normalized):
        if text:
            stance = stances[index] if stances is not None else ""
            exact_groups.setdefault((text, stance), []).append(index)
    for indices in exact_groups.values():
        for index in indices[1:]:
            uf.union(indices[0], index)

    grams = [_grams(t) for t in normalized]
    clusterable = [len(t) >= MIN_CLUSTER_TEXT_LEN for t in normalized]

    for i in range(size):
        if not clusterable[i]:
            continue
        for j in range(i + 1, size):
            if not clusterable[j]:
                continue
            if stances is not None and stances[i] != stances[j]:
                continue
            union_len = len(grams[i] | grams[j])
            if union_len == 0:
                continue
            if len(grams[i] & grams[j]) / union_len >= DEDUP_THRESHOLD:
                uf.union(i, j)

    # 簇号按簇代表（输入序首条）出现次序递增
    root_to_cluster: dict[int, int] = {}
    cluster_of: list[int] = []
    for idx in range(size):
        root = uf.find(idx)
        if root not in root_to_cluster:
            root_to_cluster[root] = len(root_to_cluster)
        cluster_of.append(root_to_cluster[root])

    cluster_sizes = [0] * len(root_to_cluster)
    for cid in cluster_of:
        cluster_sizes[cid] += 1

    representative_seen: set[int] = set()
    infos: list[DedupInfo] = []
    for cid in cluster_of:
        is_canonical = cid not in representative_seen
        representative_seen.add(cid)
        infos.append(
            DedupInfo(
                cluster_id=cid,
                dup_count=cluster_sizes[cid],
                is_canonical=is_canonical,
            )
        )
    return infos


def find_stance_conflicts(
    texts: Sequence[str],
    stances: Sequence[str],
) -> tuple[tuple[int, ...], ...]:
    """返回精确或近重复但立场标签不一致的评论索引组。

    这里刻意忽略立场做聚类，与 deduplicate 的同立场聚类互补：冲突组不合并、
    不自动改票，只用于触发人工复核，避免标注冲突被误当成消费者分歧。
    """
    size = len(texts)
    if len(stances) != size:
        raise ValueError("stances 必须与 texts 等长")
    if size < 2:
        return ()
    normalized = [normalize_text(text) for text in texts]
    union_find = _UnionFind(size)
    exact_groups: dict[str, list[int]] = {}
    for index, text in enumerate(normalized):
        if text:
            exact_groups.setdefault(text, []).append(index)
    for indices in exact_groups.values():
        for index in indices[1:]:
            union_find.union(indices[0], index)

    grams = [_grams(text) for text in normalized]
    clusterable = [len(text) >= MIN_CLUSTER_TEXT_LEN for text in normalized]
    for i in range(size):
        if not clusterable[i]:
            continue
        for j in range(i + 1, size):
            if not clusterable[j]:
                continue
            union_len = len(grams[i] | grams[j])
            if union_len and len(grams[i] & grams[j]) / union_len >= DEDUP_THRESHOLD:
                union_find.union(i, j)

    groups: dict[int, list[int]] = {}
    for index in range(size):
        groups.setdefault(union_find.find(index), []).append(index)
    conflicts = [
        tuple(indices)
        for indices in groups.values()
        if len({stances[index] for index in indices}) > 1
    ]
    return tuple(sorted(conflicts, key=lambda indices: indices[0]))
