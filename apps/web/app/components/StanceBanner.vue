<script setup lang="ts">
/**
 * 顶部判定横幅。有 claim_decisions 时只呈现每条卖点的独立判定摘要，
 * 不把跨假设混合情感包装成单条卖点结论；旧响应才回退到总体结论。
 */
import type { DecisionState } from "../utils/evidence-schema"
import type { ClaimDecisionSummary, DecisionSummary, ScenarioId } from "../composables/useEvidence"
import { DECISION_LABEL } from "../composables/useEvidence"
import type { Hypothesis } from "../utils/hypotheses"
import IntervalGauge from "./IntervalGauge.vue"

const props = defineProps<{
  stance: DecisionState
  scenario: ScenarioId
  query: string
  hypotheses: Hypothesis[]
  activeClaimId?: string
  claimDecisions?: ClaimDecisionSummary[]
  /** 判定可追溯数据（可选：旧夹具缺失时不渲染小字行） */
  decision?: DecisionSummary | null
}>()

const SUBTITLE: Record<DecisionState, string> = {
  insufficient:
    "L1 一手反馈为零样本或低于门禁，当前对照不构成消费者偏好结论。",
  refuted:
    "反对份额的 95% 区间下界过半；支持侧原文仍并排保留。",
  conflicting:
    "支持与反对在当前样本中并存，统计上未形成决定性多数；保留分歧，不做调和。",
  supported:
    "支持区间下界刚过决定线但样本仍有限，需扩大样本复核。",
}

const hasClaimDecisions = computed(() => (props.claimDecisions?.length ?? 0) > 0)
const stateCounts = computed(() => {
  const decisions = props.claimDecisions ?? []
  return {
    supported: decisions.filter((item) => item.state === "supported").length,
    refuted: decisions.filter((item) => item.state === "refuted").length,
    conflicting: decisions.filter((item) => item.state === "conflicting").length,
    insufficient: decisions.filter(
      (item) =>
        item.state === "insufficient" ||
        item.n_l1 <= 0 ||
        item.n_polarized < 30 ||
        item.gate_status !== "pass",
    ).length,
  }
})
const countSummary = computed(() => {
  const counts = stateCounts.value
  return `支持 ${counts.supported} · 反对 ${counts.refuted} · 分歧 ${counts.conflicting} · 不足 ${counts.insufficient}`
})
const claimViews = computed(() =>
  (props.claimDecisions ?? []).map((decision) => ({
    decision,
    title: props.hypotheses.find((item) => item.id === decision.claim_id)?.title ?? decision.claim_id,
    insufficient:
      decision.state === "insufficient" ||
      decision.n_l1 <= 0 ||
      decision.n_polarized < 30 ||
      decision.gate_status !== "pass",
  })),
)
const activeClaim = computed<ClaimDecisionSummary | null>(() => {
  if (props.activeClaimId) {
    return props.claimDecisions?.find((item) => item.claim_id === props.activeClaimId) ?? null
  }
  return props.claimDecisions?.[0] ?? null
})
const activeClaimView = computed(() =>
  claimViews.value.find((item) => item.decision.claim_id === activeClaim.value?.claim_id),
)
const currentState = computed<DecisionState>(() =>
  hasClaimDecisions.value
    ? activeClaimView.value?.insufficient
      ? "insufficient"
      : activeClaim.value?.state ?? "insufficient"
    : props.stance,
)
const currentTitle = computed(() =>
  hasClaimDecisions.value
    ? activeClaimView.value?.title ?? "当前假设"
    : "当前场景总体结论",
)
const bannerCls = computed(() =>
  currentState.value === "conflicting" || currentState.value === "refuted"
    ? "banner--bad"
    : currentState.value === "supported"
      ? "banner--ok"
      : "banner--warn",
)
const currentDecision = computed<DecisionSummary | null>(() =>
  hasClaimDecisions.value ? activeClaim.value : props.decision ?? null,
)
const inferenceNote = computed(() => {
  const notes = (props.claimDecisions ?? []).map((item) => item.inference_note).filter(Boolean)
  return notes[0] ?? props.decision?.inference_note ?? ""
})

function traceText(decision: DecisionSummary | null): string {
  if (!decision) return ""
  const parts: string[] = []
  if (decision.support_interval && decision.oppose_interval) {
    const fmt = (value: number) => value.toFixed(2)
    parts.push(
      `支持份额 95% 区间 [${fmt(decision.support_interval.lo)}, ${fmt(decision.support_interval.hi)}] · 反对 [${fmt(decision.oppose_interval.lo)}, ${fmt(decision.oppose_interval.hi)}]（n=${decision.support_interval.n}）`,
    )
  }
  if (decision.dedup_duplicated > 0) {
    parts.push(`去重 ${decision.dedup_duplicated} 条 → ${decision.dedup_clusters} 簇`)
  } else if (decision.dedup_clusters > 0) {
    parts.push(`去重后 ${decision.dedup_clusters} 簇`)
  }
  if (decision.power_note) parts.push(decision.power_note)
  parts.push(`门禁 ${decision.gate_status || "未标注"}`)
  return parts.join(" · ")
}

const gauge = computed(() => {
  const support = currentDecision.value?.support_interval ?? null
  const oppose = currentDecision.value?.oppose_interval ?? null
  if (!support || !oppose) return { loS: null, hiS: null, loO: null, hiO: null }
  return { loS: support.lo, hiS: support.hi, loO: oppose.lo, hiO: oppose.hi }
})

const isDemoScenario = computed(() => props.scenario !== "real")
</script>

<template>
  <section class="banner" :class="bannerCls" role="status" aria-live="polite">
    <div class="banner__main">
      <p class="banner__eyebrow">{{ hasClaimDecisions ? "每条卖点独立判定" : "当前场景总体结论" }}</p>
      <h2 class="banner__title">
        {{ hasClaimDecisions ? countSummary : DECISION_LABEL[props.stance] }}
      </h2>
      <p class="banner__subtitle">
        <template v-if="hasClaimDecisions">
          当前假设「{{ currentTitle }}」：{{ DECISION_LABEL[currentState] }}。{{ SUBTITLE[currentState] }}
        </template>
        <template v-else>{{ SUBTITLE[props.stance] }}</template>
      </p>
    </div>
    <div class="banner__right">
      <div class="banner__summary">
        <span v-if="currentDecision" class="banner__stat num">
          n={{ currentDecision.n_total }} · L1={{ currentDecision.n_l1 }} · 门禁 {{ currentDecision.gate_status || "未标注" }}
        </span>
        <span v-if="isDemoScenario" class="banner__meta-item banner__demo-chip">演示场景 · 模拟回填</span>
        <details class="banner__details">
          <summary>判定依据</summary>
          <div class="banner__detail-body">
            <p class="banner__detail-subtitle">
              {{ hasClaimDecisions ? `当前假设：${currentTitle}` : SUBTITLE[props.stance] }}
            </p>
            <p v-if="traceText(currentDecision)" class="banner__trace">{{ traceText(currentDecision) }}</p>
            <IntervalGauge variant="band" v-bind="gauge" />
            <div class="banner__meta">
              <span class="banner__meta-item">场景：{{ props.query || "未标注" }} → 德国市场</span>
            </div>
          </div>
        </details>
      </div>
      <p v-if="inferenceNote" class="banner__inference"><strong>推断边界：</strong>{{ inferenceNote }}</p>
    </div>
    <ul v-if="hasClaimDecisions" class="banner__claims" aria-label="各卖点独立判定">
      <li v-for="item in claimViews" :key="item.decision.claim_id" class="banner__claim">
        <span class="banner__claim-title">{{ item.title }}</span>
        <span
          class="banner__claim-state"
          :class="item.insufficient ? 'is-insufficient' : `is-${item.decision.state}`"
        >{{ item.insufficient ? "证据不足" : DECISION_LABEL[item.decision.state] }}</span>
        <span class="banner__claim-n num">L1={{ item.decision.n_l1 }} · 极性 n={{ item.decision.n_polarized }}</span>
      </li>
    </ul>
  </section>
</template>
