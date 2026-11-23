<script setup lang="ts">
/**
 * 附录：待验证问题 + 静态「建议访谈问题」区。
 * - questions 逐条渲染并标注来源属性（如「基于 L3 监管信号推断」→ 属「待验证假设」层）；
 *   L2/L3 证据只能产出待验证问题，不得直接写入偏好结论；
 * - 静态区 3 条访谈问题 + 2 条详情页 A/B 测试方向，可直接人工执行。
 */
import type { EvidenceQuestion } from "../composables/useEvidence"

defineProps<{ questions: EvidenceQuestion[] }>()

/** 静态区：建议访谈问题（可直接用于用户访谈） */
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

/** 静态区：详情页信息排序 / 文案 A/B 测试方向（可直接执行） */
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
  <aside class="qcol">
    <section class="qcol__block">
      <h2 class="qcol__heading">待验证问题 <span class="qcol__count">{{ questions.length }}</span></h2>
      <p class="qcol__hint">二手经验与宏观背景只产出待验证问题，不直接写入偏好结论。</p>
      <ol class="qcol__list">
        <li v-for="(q, i) in questions" :key="i" class="qitem">
          <p class="qitem__text">{{ q.text }}</p>
          <p class="qitem__meta">
            <span class="qitem__layer">待验证假设</span>
            <span class="qitem__source">来源属性：{{ q.source }}</span>
          </p>
        </li>
      </ol>
    </section>

    <section class="qcol__block qcol__block--static">
      <h2 class="qcol__heading">建议访谈问题</h2>
      <p class="qcol__hint">可直接用于用户访谈执行。</p>
      <ol class="qcol__list">
        <li v-for="(q, i) in INTERVIEW_QUESTIONS" :key="i" class="qitem">
          <p class="qitem__text">{{ q.text }}</p>
          <p class="qitem__meta"><span class="qitem__source">{{ q.why }}</span></p>
        </li>
      </ol>
    </section>

    <section class="qcol__block qcol__block--static">
      <h2 class="qcol__heading">详情页测试方向（A/B 草稿）</h2>
      <ul class="qcol__list">
        <li v-for="(t, i) in AB_TESTS" :key="i" class="qitem">
          <p class="qitem__text">{{ t.text }}</p>
        </li>
      </ul>
    </section>
  </aside>
</template>
