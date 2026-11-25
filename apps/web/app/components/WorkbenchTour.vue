<script setup lang="ts">
const props = defineProps<{ step: number }>()
const emit = defineEmits<{ next: []; skip: [] }>()

const steps = [
  {
    no: "01",
    title: "先选择一条卖点假设",
    body: "左侧只保留假设、状态与关键计数。选择后，中央证据区和右侧验证建议会同步更新。",
  },
  {
    no: "02",
    title: "用消费者原话检验判断",
    body: "支持与反对并排呈现，点击编号可定位原文；更多证据按需展开，L2 / L3 不参与偏好判定。",
  },
  {
    no: "03",
    title: "把发现变成下一步行动",
    body: "右侧提供待验证问题、访谈与 A/B 草案。勾选行动或复制完整计划，继续下一轮验证。",
  },
]
</script>

<template>
  <aside class="tour" role="dialog" aria-label="工作台使用引导" aria-live="polite">
    <div class="tour__top">
      <span class="tour__badge">首次使用 · {{ props.step + 1 }} / 3</span>
      <button type="button" class="tour__close" aria-label="跳过引导" @click="emit('skip')">×</button>
    </div>
    <div class="tour__progress" aria-hidden="true">
      <span v-for="(_, index) in steps" :key="index" :class="{ active: index <= props.step }"></span>
    </div>
    <p class="tour__no num">{{ steps[props.step]?.no }}</p>
    <h2>{{ steps[props.step]?.title }}</h2>
    <p class="tour__body">{{ steps[props.step]?.body }}</p>
    <div class="tour__actions">
      <button type="button" class="tour__skip" @click="emit('skip')">稍后再说</button>
      <button type="button" class="tour__next" @click="emit('next')">
        {{ props.step === 2 ? "开始验证" : "下一步" }} <span aria-hidden="true">→</span>
      </button>
    </div>
  </aside>
</template>
