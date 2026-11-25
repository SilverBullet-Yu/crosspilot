<script setup lang="ts">
import { ref } from "vue"
import type { EvidenceQuestion } from "../composables/useEvidence"

defineProps<{ questions: EvidenceQuestion[] }>()

type AdviceSection = "questions" | "interview" | "ab"
const activeSection = ref<AdviceSection>("questions")
const sections: Array<{ id: AdviceSection; label: string }> = [
  { id: "questions", label: "待验证问题" },
  { id: "interview", label: "访谈" },
  { id: "ab", label: "A/B" },
]

const INTERVIEW_QUESTIONS = [
  {
    text: "您上一次打包行李时，最花时间的是哪一步？容量不够用和找不到东西，哪个更让您头疼？",
    why: "验证「容量 vs 功能」的真实权衡",
  },
  {
    text: "您在德国站买收纳包时，评论里的哪类负面反馈会让您直接放弃下单——尺寸超标、隔层太多，还是面料廉价？",
    why: "核实尺寸限制与便携性负面反馈",
  },
  {
    text: "价格便宜到多少您反而会怀疑质量？您愿意为耐用材料或退换保障多付多少钱？",
    why: "验证「低价是否核心购买理由」",
  },
]

const AB_TESTS = [
  {
    text: "首屏排序 A/B：首图卖点「31L 量化容量 + 机舱尺寸适配标识」vs「多隔层功能九宫格」，对比点击率与转化率。",
  },
  {
    text: "文案 A/B：「超大容量一包搞定」形容性文案 vs「可量化参数 + 退换货保障」文案，对比停留时长与下单率。",
  },
]
</script>

<template>
  <div class="qcol">
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
      <p class="qcol__hint">二手经验与宏观背景只产出待验证问题，不直接写入偏好结论。</p>
      <ol class="qcol__list">
        <li v-for="(question, index) in questions" :key="index" class="qitem">
          <p class="qitem__text">{{ question.text }}</p>
          <p class="qitem__meta">
            <span class="qitem__layer">待验证假设</span>
            <span class="qitem__source">来源属性：{{ question.source }}</span>
          </p>
        </li>
      </ol>
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
      <ol class="qcol__list">
        <li v-for="(question, index) in INTERVIEW_QUESTIONS" :key="index" class="qitem">
          <p class="qitem__text">{{ question.text }}</p>
          <p class="qitem__meta"><span class="qitem__source">{{ question.why }}</span></p>
        </li>
      </ol>
    </section>

    <section
      id="qcol-panel-ab"
      v-show="activeSection === 'ab'"
      class="qcol__block"
      role="tabpanel"
      aria-labelledby="qcol-tab-ab"
    >
      <h2 class="qcol__heading">详情页测试方向（A/B 草稿）</h2>
      <ul class="qcol__list">
        <li v-for="(test, index) in AB_TESTS" :key="index" class="qitem">
          <p class="qitem__text">{{ test.text }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>
