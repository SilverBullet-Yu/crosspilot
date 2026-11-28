<script setup lang="ts">
import { computed, ref } from "vue"
import type { CrossSourceComparison, EvidenceQuestion } from "../composables/useEvidence"
import type { ValidationPlan } from "../utils/validation-plan"

const props = defineProps<{
  questions: EvidenceQuestion[]
  plan: ValidationPlan | null
  comparison: CrossSourceComparison | null
}>()

const COMPARISON_STATUS_LABELS: Record<CrossSourceComparison["status"], string> = {
  needs_l1: "缺消费者证据",
  needs_l2: "缺从业经验",
  mixed_scenarios: "样本分歧，需按场景核对",
  potential_divergence: "潜在分歧，需核验",
  compare_scenarios: "双方都有线索，需核对场景",
}

type AdviceSection = "questions" | "interview" | "prototype" | "ab"
const activeSection = ref<AdviceSection>("questions")
const sections: Array<{ id: AdviceSection; label: string }> = [
  { id: "questions", label: "待验证问题" },
  { id: "interview", label: "访谈" },
  { id: "prototype", label: "原型测试" },
  { id: "ab", label: "A/B" },
]

interface SourcePart {
  text: string
  url?: string
}

/** 来源字段是字符串契约；按分号拆段并保留其中的 L1/L2/L3 标记。 */
function sourceSegments(source: string): string[] {
  return source.split(/[；;]/).map((item) => item.trim()).filter(Boolean)
}

function segmentLayer(segment: string): "L1" | "L2" | "L3" | null {
  const match = segment.match(/^L([123])\s*[:：]/i)
  return match ? (`L${match[1]}` as "L1" | "L2" | "L3") : null
}

/** 把 URL 与普通文本拆开，来源链接可点击，其他来源说明保持纯文本。 */
function sourceParts(segment: string): SourcePart[] {
  const parts: SourcePart[] = []
  const re = /https?:\/\/[^\s；;]+/gi
  let cursor = 0
  for (const match of segment.matchAll(re)) {
    const index = match.index ?? 0
    const raw = match[0]
    const url = raw.replace(/[),.]+$/, "")
    if (index > cursor) parts.push({ text: segment.slice(cursor, index) })
    parts.push({ text: url, url })
    cursor = index + raw.length
  }
  if (cursor < segment.length) parts.push({ text: segment.slice(cursor) })
  return parts.length ? parts : [{ text: segment }]
}

function comparisonRef(ref: string): { label: string; url: string } {
  const match = ref.match(/^(.*?): (https?:\/\/.*)$/)
  return match ? { label: match[1] || "原文出处", url: match[2] || "" } : { label: ref, url: "" }
}

const comparisonView = computed(() => {
  const comparison = props.comparison
  if (!comparison) return null
  return {
    ...comparison,
    statusLabel: COMPARISON_STATUS_LABELS[comparison.status],
    l1Sources: comparison.l1_refs.map(comparisonRef),
    l2Sources: comparison.l2_refs.map(comparisonRef),
  }
})

const questionViews = computed(() =>
  props.questions.map((question) => {
    const segments = sourceSegments(question.source)
    const layers = [...new Set(segments.map(segmentLayer).filter((layer): layer is "L1" | "L2" | "L3" => Boolean(layer)))]
    return {
      ...question,
      segments,
      layers,
      crossSource: layers.length > 1 || question.text.includes("跨来源"),
    }
  }),
)
</script>

<template>
  <div class="qcol">
    <section v-if="plan" class="qcol__plan-context" aria-label="当前假设的验证依据">
      <p class="qcol__plan-title">当前假设：{{ plan.hypothesisTitle }}</p>
      <p class="qcol__plan-summary">{{ plan.summary }}</p>
      <p class="qcol__plan-basis num">{{ plan.basis.summary }}</p>
      <p class="qcol__plan-notice">{{ plan.notice }}</p>
      <details v-if="plan.basis.cards.length" class="qcol__basis">
        <summary>回看本计划引用的 {{ plan.basis.cards.length }} 条 L1 原文</summary>
        <ul class="qcol__basis-list">
          <li v-for="card in plan.basis.cards" :key="`${card.review_id ?? card.source_url}-${card.published_on}`">
            <blockquote>{{ card.excerpt }}</blockquote>
            <p>
              <span class="badge" :class="`badge--${card.level}`">{{ card.level }} 一手反馈</span>
              <span v-if="card.is_demo_data" class="badge badge--demo">模拟示例</span>
              <a :href="card.source_url" target="_blank" rel="noopener noreferrer">{{ card.review_id || "原文出处" }} ↗</a>
            </p>
          </li>
        </ul>
      </details>
    </section>

    <section v-if="comparisonView" class="qcol__comparison" aria-label="当前卖点的跨来源对照">
      <header class="qcol__comparison-head">
        <div>
          <p class="qcol__comparison-kicker">L1 消费者 × L2 从业经验</p>
          <h2>{{ comparisonView.label }}</h2>
        </div>
        <span class="qcol__comparison-status">{{ comparisonView.statusLabel }}</span>
      </header>
      <div class="qcol__comparison-grid">
        <article class="qcol__source qcol__source--l1">
          <h3>L1 消费者反馈</h3>
          <p class="num">{{ comparisonView.l1_support }} 支持 · {{ comparisonView.l1_oppose }} 反对 · n={{ comparisonView.l1_polarized }}</p>
          <p>样本状态：{{ comparisonView.l1_state }}；L2 不计入样本量。</p>
          <details v-if="comparisonView.l1Sources.length">
            <summary>查看 {{ comparisonView.l1Sources.length }} 条 L1 出处</summary>
            <ul>
              <li v-for="source in comparisonView.l1Sources" :key="`${source.label}-${source.url}`">
                <a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.label }} ↗</a>
                <span v-else>{{ source.label }}</span>
              </li>
            </ul>
          </details>
          <p v-else class="qcol__comparison-empty">暂无目标市场 L1 评论。</p>
        </article>
        <article class="qcol__source qcol__source--l2">
          <h3>L2 从业经验</h3>
          <p class="num">{{ comparisonView.l2_total }} 条线索 · 只用于提问</p>
          <p>不推断消费者立场，不与 L1 票数合并。</p>
          <details v-if="comparisonView.l2Sources.length">
            <summary>查看 {{ comparisonView.l2Sources.length }} 条 L2 出处</summary>
            <ul>
              <li v-for="source in comparisonView.l2Sources" :key="`${source.label}-${source.url}`">
                <a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.label }} ↗</a>
                <span v-else>{{ source.label }}</span>
              </li>
            </ul>
          </details>
          <p v-else class="qcol__comparison-empty">暂无可对照的从业经验。</p>
        </article>
      </div>
      <p class="qcol__comparison-question"><strong>要追问：</strong>{{ comparisonView.question }}</p>
    </section>

    <div class="qcol__tabs" role="tablist" aria-label="验证建议类型">
      <button
        v-for="section in sections"
        :id="`qcol-tab-${section.id}`"
        :key="section.id"
        type="button"
        role="tab"
        :aria-selected="activeSection === section.id"
        :aria-controls="`qcol-panel-${section.id}`"
        :class="{ active: activeSection === section.id }"
        @click="activeSection = section.id"
      >
        {{ section.label }}
      </button>
    </div>

    <section
      id="qcol-panel-questions"
      v-show="activeSection === 'questions'"
      class="qcol__block"
      role="tabpanel"
      aria-labelledby="qcol-tab-questions"
    >
      <h2 class="qcol__heading">待验证问题 <span class="qcol__count">{{ questions.length }}</span></h2>
      <p class="qcol__hint">L2 二手经验与 L3 宏观背景只产出待验证问题；跨来源问题突出 L1 / L2 标识，不直接写入偏好结论。</p>
      <ol v-if="questionViews.length" class="qcol__list">
        <li v-for="(question, index) in questionViews" :key="index" class="qitem">
          <p class="qitem__text">{{ question.text }}</p>
          <p class="qitem__meta">
            <span v-if="question.crossSource" class="qitem__layer qitem__layer--cross">跨来源</span>
            <span
              v-for="layer in question.layers"
              :key="layer"
              class="qitem__layer"
              :class="`qitem__layer--${layer}`"
            >{{ layer }}</span>
            <span v-if="!question.layers.length" class="qitem__layer">待验证假设</span>
          </p>
          <p class="qitem__source-list">
            <span v-for="(segment, segmentIndex) in question.segments" :key="segmentIndex" class="qitem__source-segment">
              <span
                v-if="segmentLayer(segment)"
                class="qitem__source-layer"
                :class="`qitem__source-layer--${segmentLayer(segment)}`"
              >{{ segmentLayer(segment) }}</span>
              <template v-for="(part, partIndex) in sourceParts(segment)" :key="partIndex">
                <a
                  v-if="part.url"
                  :href="part.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="qitem__url"
                  :title="part.url"
                >{{ part.text }} ↗</a>
                <span v-else>{{ part.text }}</span>
              </template>
            </span>
          </p>
        </li>
      </ol>
      <p v-else class="qcol__empty">当前没有待验证问题；先补充证据或切换演示场景。</p>
    </section>

    <section
      id="qcol-panel-interview"
      v-show="activeSection === 'interview'"
      class="qcol__block"
      role="tabpanel"
      aria-labelledby="qcol-tab-interview"
    >
      <h2 class="qcol__heading">建议访谈问题</h2>
      <p class="qcol__hint">可直接用于用户访谈执行。</p>
      <ol v-if="plan" class="qcol__list">
        <li v-for="(question, index) in plan.interviews" :key="index" class="qitem">
          <p class="qitem__text">{{ question.text }}</p>
          <p class="qitem__meta"><span class="qitem__source">{{ question.why }}</span></p>
        </li>
      </ol>
    </section>

    <section
      id="qcol-panel-prototype"
      v-show="activeSection === 'prototype'"
      class="qcol__block"
      role="tabpanel"
      aria-labelledby="qcol-tab-prototype"
    >
      <h2 class="qcol__heading">{{ plan?.prototypeTitle ?? "原型测试方案" }}</h2>
      <p class="qcol__hint">同组受试者内对照，先验证行为与麻烦来源，不直接外推市场偏好。</p>
      <ol v-if="plan" class="qcol__list">
        <li v-for="(item, index) in plan.prototypeSteps" :key="index" class="qitem">
          <p class="qitem__text">{{ item }}</p>
        </li>
      </ol>
      <h3 class="qcol__subheading">样本与成功判据</h3>
      <ul v-if="plan" class="qcol__list">
        <li v-for="(item, index) in plan.sampleCriteria" :key="index" class="qitem">
          <p class="qitem__text">{{ item }}</p>
        </li>
      </ul>
    </section>

    <section
      id="qcol-panel-ab"
      v-show="activeSection === 'ab'"
      class="qcol__block"
      role="tabpanel"
      aria-labelledby="qcol-tab-ab"
    >
      <h2 class="qcol__heading">两版待测试文案（A/B 草稿）</h2>
      <p class="qcol__hint">仅用于下一步概念或页面测试；不代表已验证转化提升。</p>
      <ul v-if="plan" class="qcol__list">
        <li v-for="variant in plan.copyVariants" :key="variant.label" class="qitem">
          <p class="qitem__test-name">{{ variant.label }} 版</p>
          <p class="qitem__text">{{ variant.text }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>
