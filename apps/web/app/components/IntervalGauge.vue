<script setup lang="ts">
/**
 * Wilson 区间标尺（SVG，零依赖）—— 把判定依据画成可读仪表。
 * 来源：Awwwards SOTM 模式借鉴（Anime.js 刻度盘 + Oryzo 蓝图测量手柄）。
 * 两处用法共用一份几何：工作台判定带（variant="band"，深底亮线）
 * 与产品概览「样本量→判定」演示器（variant="plain"，浅底实色）。
 * 颜色纪律：支持=三态绿、反对=三态红、决定线中性——随 variant 取对应色板。
 * 无区间（门禁未过）时渲染空轨道 + 提示语，不虚构数据。
 */
const props = withDefaults(
  defineProps<{
    /** band=判定带深色底 / plain=浅色面板底 */
    variant?: "band" | "plain"
    /** 支持/反对 Wilson 95% 区间；null 或缺省 → 空态 */
    loS?: number | null
    hiS?: number | null
    loO?: number | null
    hiO?: number | null
    /** 份额点（landing 演示器有真实 k/n 时传入）；工作台横幅无票数明细，不画 */
    shareS?: number | null
    shareO?: number | null
  }>(),
  { variant: "band", loS: null, hiS: null, loO: null, hiO: null, shareS: null, shareO: null },
)

const W = 720
const H = 66
const PAD = 20
/** 份额 → x 坐标 */
const x = (v: number) => PAD + v * (W - 2 * PAD)

const hasIntervals = computed(
  () =>
    props.loS !== null && props.hiS !== null && props.loO !== null && props.hiO !== null &&
    props.loS >= 0 && props.hiS <= 1 && props.loO >= 0 && props.hiO <= 1,
)

const ticks = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]

/* band（深底）/ plain（浅底）色板：轨道 / 刻度 / 标签 / 决定线 / 支持 / 反对 */
const C = computed(() =>
  props.variant === "band"
    ? { track: "rgba(255,255,255,.22)", tick: "rgba(255,255,255,.28)", label: "rgba(255,255,255,.55)", decide: "rgba(255,255,255,.78)", support: "#4ade80", oppose: "#f87171", hint: "rgba(255,255,255,.62)", halo: "#16181b" }
    : { track: "#d0d4da", tick: "#9aa1ab", label: "#9aa1ab", decide: "#16181b", support: "#1a7f4b", oppose: "#b91c1c", hint: "#5c6470", halo: "#ffffff" },
)
</script>

<template>
  <svg
    class="gauge"
    :viewBox="`0 0 ${W} ${H}`"
    role="img"
    :aria-label="
      hasIntervals
        ? `支持份额 95% 置信区间 [${loS!.toFixed(2)}, ${hiS!.toFixed(2)}]，反对 [${loO!.toFixed(2)}, ${hiO!.toFixed(2)}]，决定线 0.5`
        : '无置信区间：样本低于门禁，补样后此处显示支持/反对区间'
    "
  >
    <!-- 轨道 + 刻度 -->
    <line :x1="PAD" y1="34" :x2="W - PAD" y2="34" :stroke="C.track" stroke-width="1" />
    <g :stroke="C.tick">
      <line
        v-for="t in ticks"
        :key="t"
        :x1="x(t)" :y1="t === 0 || t === 1 ? 29 : (t === 0.5 ? 29 : 30)"
        :x2="x(t)" :y2="t === 0 || t === 1 ? 39 : (t === 0.5 ? 39 : 38)"
      />
    </g>
    <text :x="PAD" y="56" font-size="10" :fill="C.label" text-anchor="middle">0%</text>
    <text :x="W / 2" y="56" font-size="10" :fill="C.label" text-anchor="middle">50%</text>
    <text :x="W - PAD" y="56" font-size="10" :fill="C.label" text-anchor="middle">100%</text>

    <!-- 决定线 0.5 -->
    <line :x1="x(0.5)" y1="10" :x2="x(0.5)" y2="46" :stroke="C.decide" stroke-width="1" stroke-dasharray="3 3" />
    <text :x="x(0.5)" y="8" font-size="10" :fill="C.decide" text-anchor="middle">决定线 0.5</text>

    <!-- 空态提示 -->
    <text v-if="!hasIntervals" :x="W / 2" y="31" font-size="11" :fill="C.hint" text-anchor="middle">
      样本过门禁后，此处显示支持/反对置信区间
    </text>

    <!-- 支持 whisker（上） -->
    <g v-if="hasIntervals" :opacity="loS! > 0.06 ? 1 : 0">
      <line :x1="x(loS!)" y1="20" :x2="x(hiS!)" y2="20" :stroke="C.support" stroke-width="3" />
      <rect :x="x(loS!) - 3" y="17" width="6" height="6" :fill="C.support" />
      <rect :x="x(hiS!) - 3" y="17" width="6" height="6" :fill="C.support" />
      <circle
        v-if="shareS !== null"
        :cx="x(shareS)" cy="20" r="4.5" :fill="C.support" :stroke="C.halo" stroke-width="1.5"
      />
    </g>
    <!-- 反对 whisker（下） -->
    <g v-if="hasIntervals" :opacity="loO! > 0.06 ? 1 : 0">
      <line :x1="x(loO!)" y1="44" :x2="x(hiO!)" y2="44" :stroke="C.oppose" stroke-width="3" />
      <rect :x="x(loO!) - 3" y="41" width="6" height="6" :fill="C.oppose" />
      <rect :x="x(hiO!) - 3" y="41" width="6" height="6" :fill="C.oppose" />
      <circle
        v-if="shareO !== null"
        :cx="x(shareO)" cy="44" r="4.5" :fill="C.oppose" :stroke="C.halo" stroke-width="1.5"
      />
    </g>
  </svg>
</template>

<style scoped>
.gauge { width: 100%; display: block; }
.gauge text { font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }
</style>
