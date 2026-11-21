<script setup lang="ts">
/**
 * 状态横幅 —— 页面第一眼看到的总体结论。
 * 证据不足与证据冲突是两个必须可见的产品状态（domain/evidence.py: resolve_stance 注释），
 * 三种状态分别用 黄/红/绿 大色块呈现，禁止灰字弱化。
 */
import type { EvidenceStance } from "../utils/evidence-schema"
import type { ScenarioId } from "../composables/useEvidence"

const props = defineProps<{
  stance: EvidenceStance
  scenario: ScenarioId
  query: string
  market: string
  dataMode: string
  generatedAt: string
  dataSource: string
}>()

const TITLE: Record<EvidenceStance, string> = {
  insufficient: "缺少有效数据",
  oppose: "证据相互冲突",
  support: "已有有限支持",
}

const SUBTITLE: Record<EvidenceStance, string> = {
  insufficient:
    "目标市场一手消费者反馈（L1）为零样本——以下对照仅基于 L3 语境或演示数据，不构成消费者偏好结论。",
  oppose:
    "L1 一手消费者反馈同时出现支持与反对——保留矛盾，支持/反对原文左右并排呈现，不做调和。",
  support:
    "已有 L1 一手反馈支持，但样本有限——结论仍需访谈验证，不宜直接写入详情页卖点。",
}

const bannerCls = computed(() =>
  props.stance === "oppose"
    ? "banner--bad"
    : props.stance === "support"
      ? "banner--ok"
      : "banner--warn",
)

const isDemoScenario = computed(() => props.scenario !== "real")

const generatedText = computed(() => {
  if (!props.generatedAt) return ""
  return `生成时间 ${props.generatedAt.replace("T", " ").replace("Z", " UTC")}`
})
</script>

<template>
  <section class="banner" :class="bannerCls" role="status">
    <div class="banner__main">
      <p class="banner__eyebrow">当前场景总体结论</p>
      <h1 class="banner__title">{{ TITLE[props.stance] }}</h1>
      <p class="banner__subtitle">{{ SUBTITLE[props.stance] }}</p>
    </div>
    <div class="banner__meta">
      <span class="banner__meta-item">场景：{{ props.query }} → 德国市场</span>
      <span class="banner__meta-item">
        数据模式：
        <span class="mode-badge" :class="props.dataMode === 'live' ? 'mode-badge--live' : 'mode-badge--snapshot'">
          {{ props.dataMode === 'live' ? '实时 live' : '快照 snapshot' }}
        </span>
      </span>
      <span v-if="isDemoScenario" class="banner__meta-item banner__demo-chip">演示场景 · 模拟回填</span>
      <span class="banner__meta-item">{{ props.dataSource }}</span>
      <span v-if="generatedText" class="banner__meta-item">{{ generatedText }}</span>
    </div>
  </section>
</template>
