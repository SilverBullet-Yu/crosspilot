<script setup lang="ts">
/**
 * 右栏：待验证问题 + 静态「建议访谈问题」区。
 * - questions 逐条渲染并标注来源属性（如「基于 L3 监管信号推断」→ 属「待验证假设」层）；
 *   按 domain/evidence.py 硬约束 1，L2/L3 只能产出待验证问题，不得直接写入偏好结论；
 * - 静态区 3 条访谈问题 + 2 条详情页 A/B 测试方向，来自方案 4.2 第 5 条用户故事。
 */
import type { EvidenceQuestion } from "../composables/useEvidence"

defineProps<{ questions: EvidenceQuestion[] }>()

/** 静态区：建议访谈问题（方案 4.2 用户故事 5「给出 3 个真实访谈问题」） */
const INTERVIEW_QUESTIONS = [
  {
    text: "您上一次打包行李时，最花时间的是哪一步？容量不够用和找不到东西，哪个更让您头疼？",
    why: "验证「容量 vs 功能」的真实权衡（对应假设 1 / 假设 2）",
  },
  {
    text: "您在德国站买收纳包时，评论里的哪类负面反馈会让您直接放弃下单——尺寸超标、隔层太多，还是面料廉价？",
    why: "核实尺寸限制与便携性负面反馈（对应假设 1 的核实问题）",
  },
  {
    text: "价格便宜到多少您反而会怀疑质量？您愿意为耐用材料或退换保障多付多少钱？",
    why: "验证「低价是否核心购买理由」（对应假设 3 的核实问题）",
  },
]

/** 静态区：详情页信息排序 / 文案 A/B 测试方向（方案 4.2 用户故事 5） */
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
      <p class="qcol__hint">按硬约束 1，L2/L3 证据只能产出待验证问题，不得直接写入偏好结论。</p>
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
      <p class="qcol__hint">静态区 · 方案 4.2 第 5 条用户故事，可人工执行。</p>
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
