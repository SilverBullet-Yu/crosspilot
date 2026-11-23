<script setup lang="ts">
/**
 * 单条假设的证据节：统计瓦片（支持/反对/语境三格计数）+ 证据组。
 * - 瓦片承担节级计数（总-分口径的唯一计数处），组头不再重复黑块计数；
 * - 空组不渲染整块占位：无证据组直接不出现，缺 L1 时由黄底空状态卡承担全部空态信息
 *   （醒目呈现，非灰字；核实方向并入其中，不与节头重复）；
 * - 证据冲突时支持/反对两组左右并排原文（README 产品级强制项，保留矛盾不调和）；
 * - 组内真实卡在前、演示卡在后并以分隔条隔开，绝不与真实卡混排在同一组内；
 * - 缺失证据组：L2/L3 卡不支撑结论（硬约束 1），逐一说明。
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

/** 该假设是否缺 L1 一手反馈 → 渲染独立空状态卡（并隐藏与卡内重复的核实问题行） */
const lacksL1 = computed(
  () =>
    !props.group.support.some((c) => c.level === "L1") &&
    !props.group.oppose.some((c) => c.level === "L1"),
)
</script>

<template>
  <section class="hypo" :class="`hypo--${props.group.status}`" :id="`hypo-${props.group.hypothesis.id}`">
    <header class="hypo__head">
      <h3 class="hypo__title">{{ props.group.hypothesis.title }}</h3>
      <span class="status-pill" :class="STATUS_META[props.group.status].cls">
        {{ STATUS_META[props.group.status].label }}
      </span>
    </header>
    <p v-if="!lacksL1" class="hypo__probe">核实问题：{{ props.group.hypothesis.probe }}</p>

    <!-- 节级统计瓦片（0 也如实显示：证据结构一眼可见） -->
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

    <!-- 支持/反对证据组（有卡才渲染整组） -->
    <div v-if="props.group.support.length || props.group.oppose.length" class="hypo__groups" :class="{ 'hypo__groups--conflict': isConflict }">
      <!-- 支持证据 -->
      <div v-if="props.group.support.length" class="egroup egroup--support">
        <h4 class="egroup__title">支持证据</h4>
        <EvidenceCardView v-for="(c, i) in support.real" :key="`sr${i}`" :card="c" />
        <template v-if="support.demo.length">
          <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
          <EvidenceCardView v-for="(c, i) in support.demo" :key="`sd${i}`" :card="c" />
        </template>
      </div>

      <!-- 相反证据 -->
      <div v-if="props.group.oppose.length" class="egroup egroup--oppose">
        <h4 class="egroup__title">相反证据</h4>
        <EvidenceCardView v-for="(c, i) in oppose.real" :key="`or${i}`" :card="c" />
        <template v-if="oppose.demo.length">
          <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
          <EvidenceCardView v-for="(c, i) in oppose.demo" :key="`od${i}`" :card="c" />
        </template>
      </div>
    </div>

    <!-- 缺失证据组：有卡才渲染（L2/L3、无立场卡） -->
    <div v-if="props.group.missing.length" class="egroup egroup--missing">
      <h4 class="egroup__title">缺失证据</h4>
      <p class="egroup__missing-note">以下证据不支撑偏好结论——仅 L1 一手反馈可判定，L2/L3 只产出待验证问题。</p>
      <EvidenceCardView v-for="(c, i) in missing.real" :key="`mr${i}`" :card="c" />
      <template v-if="missing.demo.length">
        <p class="egroup__demo-divider">以下为演示数据（模拟回填），不与真实反馈混排 ↓</p>
        <EvidenceCardView v-for="(c, i) in missing.demo" :key="`md${i}`" :card="c" />
      </template>
    </div>

    <!-- 独立空状态卡片：证据不足必须醒目呈现，不得灰字弱化（核实方向并入，不重复节头） -->
    <div v-if="lacksL1" class="empty-state">
      <p class="empty-state__title">缺少有效数据（L1 零样本）</p>
      <p class="empty-state__body">
        该假设下暂无目标市场（德国）一手消费者反馈，任何结论都不可用。
      </p>
      <p class="empty-state__probe">应核实的方向：{{ props.group.hypothesis.probe }}</p>
      <p class="empty-state__next">→ 对应的待验证问题见下方附录</p>
    </div>
  </section>
</template>
