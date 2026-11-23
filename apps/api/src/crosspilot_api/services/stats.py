"""统计层：Wilson 95% 区间、最小样本量门禁与决定份额（ADR-0005 A2）。

纯公式零第三方依赖（statistics.NormalDist 为标准库），不训练、不拟合，
可被 domain 层与测试直接导入（无循环：本模块不 import domain）。

口径（2026-11-22 验证 + 对抗审查 C3/C4 修正后锁定，见 ADR-0005 验证记录）：
- 门禁与区间分母统一为「去重后有极性样本数」（support+oppose 的去重簇数），
  insufficient 卡单独报告比例、不进分母（对抗审查 C4）；
- Wilson 95% 区间对 support / oppose 份额分别计算；
- 决定性多数优先，冲突 = 双方票数 > 0 且两份额区间重叠（重叠 = 95% 置信下
  双方都不能排除过半；20:10 与 15:15 同判 conflicting 是公式的诚实输出）。
  「区间含 0.5」旧判据在 20:10 主导场景误判，已弃用（对抗审查 C3）。

边界用例（n=30，写入 test_stats.py）：21:9 → supported（下界 0.521）；
20:10 → conflicting（重叠 0.488 ≤ 0.512）；15:15 → conflicting；
30:0 → supported；0:30 → refuted。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

#: 95% 置信对应的正态分位（NormalDist().inv_cdf(0.975)）。
Z_95: float = NormalDist().inv_cdf(0.975)

#: 最小样本量门禁：去重后有极性样本低于该值 → 判定强制 insufficient。
MIN_POLARIZED_SAMPLE = 30


@dataclass(frozen=True)
class WilsonInterval:
    """Wilson 95% 比例区间。n 为分母（去重后有极性样本数）。"""

    lo: float
    hi: float
    n: int


def wilson_from_share(p: float, n: int, z: float = Z_95) -> WilsonInterval:
    """按已知份额 p 计算 Wilson 95% 区间（decisive_share 二分求解的内核）。"""
    if n <= 0:
        return WilsonInterval(0.0, 0.0, n)
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4 * n * n))
    return WilsonInterval(max(0.0, center - half), min(1.0, center + half), n)


def wilson_interval(k: int, n: int, z: float = Z_95) -> WilsonInterval:
    """Wilson 95% 区间（Wilson 1927）。k 为命中数，n 为分母。

    n <= 0 时返回退化区间（lo=hi=0）；调用方应先过样本量门禁。
    """
    if n <= 0:
        return WilsonInterval(0.0, 0.0, n)
    return wilson_from_share(k / n, n, z)


def intervals_overlap(a: WilsonInterval, b: WilsonInterval) -> bool:
    """两个区间是否重叠（闭区间相交）。冲突判据（对抗审查 C3 修正后）。"""
    return max(a.lo, b.lo) <= min(a.hi, b.hi)


def below_minimum(n_polarized: int, min_n: int = MIN_POLARIZED_SAMPLE) -> bool:
    """最小样本量门禁：低于阈值 → 判定强制 insufficient（R3 消费次序第一步）。"""
    return n_polarized < min_n


def decisive_share(n: int, z: float = Z_95) -> float:
    """使 Wilson 95% 下界超过 0.5 所需的最小支持份额（决定线）。

    二分求解 lo(p, n) = 0.5；n=30 时约 0.68，n=100 时约 0.59。
    低于决定线的份额在 95% 置信下无法判定为多数——这正是「证据不足」的
    公式化含义（ADR-0005：证据不足从口径变公式）。
    """
    lo_bound, hi_bound = 0.5, 1.0
    for _ in range(60):
        mid = (lo_bound + hi_bound) / 2.0
        if wilson_from_share(mid, n, z).lo > 0.5:
            hi_bound = mid
        else:
            lo_bound = mid
    return hi_bound


def power_note(n: int, z: float = Z_95) -> str:
    """功效分析注记（进包络 decision 字段，向评审解释判定线，可追溯）。"""
    if below_minimum(n):
        reference = decisive_share(MIN_POLARIZED_SAMPLE, z)
        return (
            f"去重后有极性样本 {n} 低于门禁 {MIN_POLARIZED_SAMPLE}，按口径强制 insufficient；"
            f"补样至 {MIN_POLARIZED_SAMPLE} 后决定线为份额 ≥{reference:.0%}"
        )
    share = decisive_share(n, z)
    return f"去重后有极性样本 {n} 过门禁；决定线：份额 ≥{share:.0%} 才判决定性多数"
