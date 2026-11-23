<script setup lang="ts">
/**
 * 状态横幅 —— 页面第一眼看到的总体结论。
 * ADR-0005（2026-11-22）：判定为 DecisionState 四值（R1 唯一判定枚举）——
 * supported / conflicting / refuted 用 大色块呈现，insufficient 用黄色块，
 * 禁止灰字弱化；冲突（conflicting）不再与反对共用 oppose 值。
 * 布局（2026-11-23 仪表化）：左=结论块，右=可追溯区（判定小字行 + Wilson 区间标尺
 * + meta pills）。区间标尺把「为什么判冲突/有限支持」画成可视事实（SOTM 模式借鉴，
 * 见 IntervalGauge.vue）；trace 文字行保留（评审逐字可读 + 断言依赖）。
 * 结论词复用 useEvidence.DECISION_LABEL（与侧栏「本次验证」卡共用一份）。
 * 数据模式 / 来源 / 生成时间等 meta 自 2026-11-22 工作台改版起移至侧栏底部。
 */
import type { DecisionState } from "../utils/evidence-schema"
import type { DecisionSummary, ScenarioId } from "../composables/useEvidence"
import { DECISION_LABEL } from "../composables/useEvidence"
import IntervalGauge from "./IntervalGauge.vue"

const props = defineProps<{
  stance: DecisionState
  scenario: ScenarioId
  query: string
  /** 判定可追溯数据（可选：旧夹具缺失时不渲染小字行） */
  decision?: DecisionSummary | null
}>()

const SUBTITLE: Record<DecisionState, string> = {
  insufficient:
    "目标市场一手消费者反馈（L1）为零样本或低于样本量门禁——以下对照仅基于 L3 语境或演示数据，不构成消费者偏好结论。",
  refuted:
    "L1 一手消费者反馈中反对份额的 95% 区间下界过半（决定性多数反对）——支持侧原文仍并排呈现，不删除。",
  conflicting:
    "L1 一手消费者反馈的支持与反对份额区间重叠（95% 置信下难分高下）——保留矛盾，支持/反对原文左右并排呈现，不做调和。",
  supported:
    "支持份额的 95% 区间下界刚过决定线，区间仍宽——结论需扩大样本复核，不宜直接写入详情页卖点。",
}

const bannerCls = computed(() =>
  props.stance === "conflicting" || props.stance === "refuted"
    ? "banner--bad"
    : props.stance === "supported"
      ? "banner--ok"
      : "banner--warn",
)

/** 判定可追溯小字行：区间 + 样本量 + 去重摘要（有 decision 数据时才渲染） */
const traceText = computed(() => {
  const d = props.decision
  if (!d) return ""
  const parts: string[] = []
  if (d.support_interval && d.oppose_interval) {
    const fmt = (v: number) => v.toFixed(2)
    parts.push(
      `支持份额 95% 区间 [${fmt(d.support_interval.lo)}, ${fmt(d.support_interval.hi)}] · 反对 [${fmt(d.oppose_interval.lo)}, ${fmt(d.oppose_interval.hi)}]（n=${d.support_interval.n}）`,
    )
  }
  if (d.dedup_duplicated > 0) {
    parts.push(`去重 ${d.dedup_duplicated} 条 → ${d.dedup_clusters} 簇`)
  } else if (d.dedup_clusters > 0) {
    parts.push(`去重后 ${d.dedup_clusters} 簇`)
  }
  if (d.power_note) parts.push(d.power_note)
  parts.push(`门禁 ${d.gate_status}`)
  return parts.join(" · ")
})

/** 标尺区间数据（无区间/旧夹具 → null，组件渲染空态轨道） */
const gauge = computed(() => {
  const s = props.decision?.support_interval ?? null
  const o = props.decision?.oppose_interval ?? null
  if (!s || !o) return { loS: null, hiS: null, loO: null, hiO: null }
  return { loS: s.lo, hiS: s.hi, loO: o.lo, hiO: o.hi }
})

const isDemoScenario = computed(() => props.scenario !== "real")
</script>

<template>
  <section class="banner" :class="bannerCls" role="status">
    <div class="banner__main">
      <p class="banner__eyebrow">当前场景总体结论</p>
      <h1 class="banner__title">{{ DECISION_LABEL[props.stance] }}</h1>
      <p class="banner__subtitle">{{ SUBTITLE[props.stance] }}</p>
    </div>
    <div class="banner__right">
      <p v-if="traceText" class="banner__trace">{{ traceText }}</p>
      <IntervalGauge variant="band" v-bind="gauge" />
      <div class="banner__meta">
        <span class="banner__meta-item">场景：{{ props.query }} → 德国市场</span>
        <span v-if="isDemoScenario" class="banner__meta-item banner__demo-chip">演示场景 · 模拟回填</span>
      </div>
    </div>
  </section>
</template>
