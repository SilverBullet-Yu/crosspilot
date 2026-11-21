<script setup lang="ts">
/**
 * 中栏单条假设的「支持证据 / 相反证据 / 缺失证据」三组对照。
 * - 证据冲突时支持/反对两组左右并排原文（README 产品级强制项，保留矛盾不调和）；
 * - 组内真实卡在前、演示卡在后并以分隔条隔开，绝不与真实卡混排在同一组内；
 * - 缺失证据组：无 L1 一手反馈时渲染独立空状态卡片（黄底醒目，非灰字），
 *   并给出方案 4.3 的核实问题；L2/L3 卡也落入本组并标注「不支撑结论」（硬约束 1）。
 */
import type { HypothesisGroups } from "../utils/hypotheses"
import { STATUS_META } from "../utils/hypotheses"
import type { ValidEvidenceCard } from "../utils/evidence-schema"

const props = defineProps<{ group: HypothesisGroups }>()

/** 组内按真实/演示拆分，真实卡在前、演示卡在后，避免同组混排 */
function splitDemo(cards: ValidEvidenceCard[]): {
  real: ValidEvidenceCard[]
  demo: ValidEvidenceCard[]
} {
  return {
    real: cards.filter((c) => !c.is_demo_data),
    demo: cards.filter((c) => c.is_demo_data),
  }
}

const support = computed(() => splitDemo(props.group.support))
const oppose = computed(() => splitDemo(props.group.oppose))
const missing = computed(() => splitDemo(props.group.missing))

/** 是否证据冲突（支持与反对同时有 L1）→ 两组左右并排 */
const isConflict = computed(
  () =>
    props.group.support.some((c) => c.level === "L1") &&
    props.group.oppose.some((c) => c.level === "L1"),
)

/** 该假设是否缺 L1 一手反馈 → 渲染独立空状态卡 */
const lacksL1 = computed(
  () =>
    !props.group.support.some((c) => c.level === "L1") &&
    !props.group.oppose.some((c) => c.level === "L1"),
)
</script>

<template>
  <section class="hypo" :class="`hypo--${props.group.status}`">
    <header class="hypo__head">
      <h3 class="hypo__title">{{ props.group.hypothesis.title }}</h3>
      <span class="status-pill" :class="STATUS_META[props.group.status].cls">
        {{ STATUS_META[props.group.status].label }}
      </span>
    </header>
    <p class="hypo__probe">核实问题：{{ props.group.hypothesis.probe }}</p>
    <p class="hypo__note">{{ props.group.statusNote }}。</p>

    <!-- 冲突时支持/反对左右并排呈现原文 -->
    <div class="hypo__groups" :class="{ 'hypo__groups--conflict': isConflict }">
      <!-- 支持证据 -->
      <div class="egroup egroup--support">
        <h4 class="egroup__title">支持证据 <span class="egroup__count">{{ props.group.support.length }}</span></h4>
        <template v-if="props.group.support.length">
          <EvidenceCardView v-for="(c, i) in support.real" :key="`sr${i}`" :card="c" />
          <template v-if="support.demo.length">
            <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
            <EvidenceCardView v-for="(c, i) in support.demo" :key="`sd${i}`" :card="c" />
          </template>
        </template>
        <p v-else class="egroup__empty">本组暂无证据</p>
      </div>

      <!-- 相反证据 -->
      <div class="egroup egroup--oppose">
        <h4 class="egroup__title">相反证据 <span class="egroup__count">{{ props.group.oppose.length }}</span></h4>
        <template v-if="props.group.oppose.length">
          <EvidenceCardView v-for="(c, i) in oppose.real" :key="`or${i}`" :card="c" />
          <template v-if="oppose.demo.length">
            <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
            <EvidenceCardView v-for="(c, i) in oppose.demo" :key="`od${i}`" :card="c" />
          </template>
        </template>
        <p v-else class="egroup__empty">本组暂无证据</p>
      </div>
    </div>

    <!-- 缺失证据 -->
    <div class="egroup egroup--missing">
      <h4 class="egroup__title">缺失证据 <span class="egroup__count">{{ props.group.missing.length }}</span></h4>
      <template v-if="props.group.missing.length">
        <p class="egroup__missing-note">本组证据不支撑偏好结论（硬约束 1：仅 L1 可单独支撑；L2/L3 只产出待验证问题）</p>
        <EvidenceCardView v-for="(c, i) in missing.real" :key="`mr${i}`" :card="c" />
        <template v-if="missing.demo.length">
          <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
          <EvidenceCardView v-for="(c, i) in missing.demo" :key="`md${i}`" :card="c" />
        </template>
      </template>
      <!-- 独立空状态卡片：证据不足必须醒目呈现，不得灰字弱化 -->
      <div v-if="lacksL1" class="empty-state">
        <p class="empty-state__title">缺少有效数据（L1 零样本）</p>
        <p class="empty-state__body">
          该假设下暂无目标市场（德国）一手消费者反馈，任何结论都不可用。
        </p>
        <p class="empty-state__probe">应核实的方向：{{ props.group.hypothesis.probe }}</p>
        <p class="empty-state__next">→ 对应的待验证问题见右栏</p>
      </div>
    </div>
  </section>
</template>
