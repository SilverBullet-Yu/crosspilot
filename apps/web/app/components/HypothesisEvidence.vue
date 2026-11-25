<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from "vue"
import type { HypothesisGroups } from "../utils/hypotheses"
import { STATUS_META } from "../utils/hypotheses"
import type { ValidEvidenceCard } from "../utils/evidence-schema"
import EvidenceCardView from "./EvidenceCardView.vue"

const props = defineProps<{ group: HypothesisGroups }>()

interface NumberedEvidence {
  card: ValidEvidenceCard
  number: number
  anchor: string
}

function splitDemo<T extends { card: ValidEvidenceCard }>(items: T[]): { real: T[]; demo: T[] } {
  return {
    real: items.filter((item) => !item.card.is_demo_data),
    demo: items.filter((item) => item.card.is_demo_data),
  }
}

const numberedSupport = computed<NumberedEvidence[]>(() =>
  props.group.support.map((card, index) => ({
    card,
    number: index + 1,
    anchor: `evidence-${props.group.hypothesis.id}-support-${index}`,
  })),
)
const numberedOppose = computed<NumberedEvidence[]>(() =>
  props.group.oppose.map((card, index) => ({
    card,
    number: props.group.support.length + index + 1,
    anchor: `evidence-${props.group.hypothesis.id}-oppose-${index}`,
  })),
)
const numberedMissing = computed<NumberedEvidence[]>(() =>
  props.group.missing.map((card, index) => ({
    card,
    number: props.group.support.length + props.group.oppose.length + index + 1,
    anchor: `evidence-${props.group.hypothesis.id}-missing-${index}`,
  })),
)

const support = computed(() => splitDemo(numberedSupport.value))
const oppose = computed(() => splitDemo(numberedOppose.value))
const missing = computed(() => splitDemo(numberedMissing.value))
const citationItems = computed(() => [
  ...numberedSupport.value.slice(0, 2),
  ...numberedOppose.value.slice(0, 2),
])

const supportPreviewCount = computed(() =>
  Math.min(1, support.value.real.length) + Math.min(1, support.value.demo.length),
)
const opposePreviewCount = computed(() =>
  Math.min(1, oppose.value.real.length) + Math.min(1, oppose.value.demo.length),
)
const missingPreviewCount = computed(() =>
  Math.min(3, missing.value.real.length) + Math.min(3, missing.value.demo.length),
)

const isConflict = computed(
  () =>
    props.group.support.some((card) => card.level === "L1") &&
    props.group.oppose.some((card) => card.level === "L1"),
)
const lacksL1 = computed(
  () =>
    !props.group.support.some((card) => card.level === "L1") &&
    !props.group.oppose.some((card) => card.level === "L1"),
)

const summary = computed(() => {
  if (props.group.status === "conflict") return "支持与反对的一手反馈同时出现，先保留分歧，不替市场下结论。"
  if (props.group.status === "support") return "当前假设出现一手支持，但样本有限，仍需扩大样本复核。"
  return "当前假设尚缺一手消费者反馈，不能据此判断市场偏好。"
})

const focusedAnchor = ref("")
const expandedSupport = ref(false)
const expandedOppose = ref(false)
const expandedMissing = ref(false)
let focusTimer: ReturnType<typeof setTimeout> | undefined

function focusEvidence(anchor: string) {
  if (anchor.includes("-support-")) expandedSupport.value = true
  if (anchor.includes("-oppose-")) expandedOppose.value = true
  if (anchor.includes("-missing-")) expandedMissing.value = true
  focusedAnchor.value = anchor
  nextTick(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    document.getElementById(anchor)?.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
      block: "center",
    })
  })
  if (focusTimer) clearTimeout(focusTimer)
  focusTimer = setTimeout(() => {
    focusedAnchor.value = ""
  }, 1800)
}

onBeforeUnmount(() => {
  if (focusTimer) clearTimeout(focusTimer)
})
</script>

<template>
  <section class="hypo" :class="`hypo--${props.group.status}`" :id="`hypo-${props.group.hypothesis.id}`">
    <header class="hypo__head">
      <div class="hypo__heading">
        <h3 class="hypo__title">{{ props.group.hypothesis.title }}</h3>
      </div>
      <span class="status-pill" :class="STATUS_META[props.group.status].cls">
        {{ STATUS_META[props.group.status].label }}
      </span>
    </header>

    <p class="hypo__summary">{{ summary }}</p>
    <p v-if="!lacksL1" class="hypo__probe">核实问题：{{ props.group.hypothesis.probe }}</p>
    <div v-if="citationItems.length" class="hypo__citations" aria-label="证据定位">
      <button
        v-for="item in citationItems"
        :key="item.anchor"
        type="button"
        class="num"
        :aria-label="`定位到证据 ${item.number}`"
        @click="focusEvidence(item.anchor)"
      >
        {{ item.number }}
      </button>
    </div>

    <div class="statrow">
      <div class="stat stat--support">
        <div class="stat__num num">{{ props.group.support.length }}</div>
        <div class="stat__label">支持（L1）</div>
      </div>
      <div class="stat stat--oppose">
        <div class="stat__num num">{{ props.group.oppose.length }}</div>
        <div class="stat__label">反对（L1）</div>
      </div>
      <div class="stat stat--missing">
        <div class="stat__num num">{{ props.group.missing.length }}</div>
        <div class="stat__label">语境 / 缺失</div>
      </div>
    </div>

    <div v-if="props.group.support.length || props.group.oppose.length" class="hypo__groups" :class="{ 'hypo__groups--conflict': isConflict }">
      <div v-if="props.group.support.length" class="egroup egroup--support">
        <h4 class="egroup__title">支持证据</h4>
        <EvidenceCardView
          v-for="item in support.real.slice(0, 1)"
          :key="item.anchor"
          :card="item.card"
          :anchor="item.anchor"
          :number="item.number"
          :highlighted="focusedAnchor === item.anchor"
        />
        <template v-if="support.demo.length">
          <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
          <EvidenceCardView
            v-for="item in support.demo.slice(0, 1)"
            :key="item.anchor"
            :card="item.card"
            :anchor="item.anchor"
            :number="item.number"
            :highlighted="focusedAnchor === item.anchor"
          />
        </template>
        <div v-show="expandedSupport" class="egroup__extra">
          <EvidenceCardView
            v-for="item in support.real.slice(1)"
            :key="item.anchor"
            :card="item.card"
            :anchor="item.anchor"
            :number="item.number"
            :highlighted="focusedAnchor === item.anchor"
          />
          <template v-if="support.demo.slice(1).length">
            <p class="egroup__demo-divider">更多演示数据（模拟回填），不与真实反馈混排 ↓</p>
            <EvidenceCardView
              v-for="item in support.demo.slice(1)"
              :key="item.anchor"
              :card="item.card"
              :anchor="item.anchor"
              :number="item.number"
              :highlighted="focusedAnchor === item.anchor"
            />
          </template>
        </div>
        <button
          v-if="numberedSupport.length > supportPreviewCount"
          type="button"
          class="hypo__expand"
          @click="expandedSupport = !expandedSupport"
        >
          {{ expandedSupport ? "收起额外证据" : `展开全部 ${numberedSupport.length} 条支持证据` }}
        </button>
      </div>

      <div v-if="props.group.oppose.length" class="egroup egroup--oppose">
        <h4 class="egroup__title">相反证据</h4>
        <EvidenceCardView
          v-for="item in oppose.real.slice(0, 1)"
          :key="item.anchor"
          :card="item.card"
          :anchor="item.anchor"
          :number="item.number"
          :highlighted="focusedAnchor === item.anchor"
        />
        <template v-if="oppose.demo.length">
          <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
          <EvidenceCardView
            v-for="item in oppose.demo.slice(0, 1)"
            :key="item.anchor"
            :card="item.card"
            :anchor="item.anchor"
            :number="item.number"
            :highlighted="focusedAnchor === item.anchor"
          />
        </template>
        <div v-show="expandedOppose" class="egroup__extra">
          <EvidenceCardView
            v-for="item in oppose.real.slice(1)"
            :key="item.anchor"
            :card="item.card"
            :anchor="item.anchor"
            :number="item.number"
            :highlighted="focusedAnchor === item.anchor"
          />
          <template v-if="oppose.demo.slice(1).length">
            <p class="egroup__demo-divider">更多演示数据（模拟回填），不与真实反馈混排 ↓</p>
            <EvidenceCardView
              v-for="item in oppose.demo.slice(1)"
              :key="item.anchor"
              :card="item.card"
              :anchor="item.anchor"
              :number="item.number"
              :highlighted="focusedAnchor === item.anchor"
            />
          </template>
        </div>
        <button
          v-if="numberedOppose.length > opposePreviewCount"
          type="button"
          class="hypo__expand"
          @click="expandedOppose = !expandedOppose"
        >
          {{ expandedOppose ? "收起额外证据" : `展开全部 ${numberedOppose.length} 条反对证据` }}
        </button>
      </div>
    </div>

    <div v-if="props.group.missing.length" class="egroup egroup--missing">
      <h4 class="egroup__title">缺失证据</h4>
      <p class="egroup__missing-note">以下证据不支撑偏好结论——仅 L1 一手反馈可判定，L2/L3 只产出待验证问题。</p>
      <EvidenceCardView
        v-for="item in missing.real.slice(0, 3)"
        :key="item.anchor"
        :card="item.card"
        :anchor="item.anchor"
        :number="item.number"
        :highlighted="focusedAnchor === item.anchor"
      />
      <template v-if="missing.demo.length">
        <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
        <EvidenceCardView
          v-for="item in missing.demo.slice(0, 3)"
          :key="item.anchor"
          :card="item.card"
          :anchor="item.anchor"
          :number="item.number"
          :highlighted="focusedAnchor === item.anchor"
        />
      </template>
      <div v-show="expandedMissing" class="egroup__extra">
        <EvidenceCardView
          v-for="item in missing.real.slice(3)"
          :key="item.anchor"
          :card="item.card"
          :anchor="item.anchor"
          :number="item.number"
          :highlighted="focusedAnchor === item.anchor"
        />
        <template v-if="missing.demo.slice(3).length">
          <p class="egroup__demo-divider">更多演示数据（模拟回填），不与真实反馈混排 ↓</p>
          <EvidenceCardView
            v-for="item in missing.demo.slice(3)"
            :key="item.anchor"
            :card="item.card"
            :anchor="item.anchor"
            :number="item.number"
            :highlighted="focusedAnchor === item.anchor"
          />
        </template>
      </div>
      <button
        v-if="numberedMissing.length > missingPreviewCount"
        type="button"
        class="hypo__expand"
        @click="expandedMissing = !expandedMissing"
      >
        {{ expandedMissing ? "收起额外证据" : `展开全部 ${numberedMissing.length} 条语境证据` }}
      </button>
    </div>

    <div v-if="lacksL1" class="empty-state">
      <p class="empty-state__title">缺少有效数据（L1 零样本）</p>
      <p class="empty-state__body">
        该假设下暂无目标市场（德国）一手消费者反馈，任何结论都不可用。
      </p>
      <p class="empty-state__probe">应核实的方向：{{ props.group.hypothesis.probe }}</p>
      <p class="empty-state__next">→ 对应的待验证问题见右侧验证建议</p>
    </div>
  </section>
</template>
