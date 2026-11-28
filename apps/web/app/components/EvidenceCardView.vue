<script setup lang="ts">
/**
 * 证据卡 —— 行式渲染六必现字段（packages/contracts/evidence-card.schema.json）：
 *   excerpt 原文摘录 / source_url 来源链接（新窗口打开）/ language 语言徽标 /
 *   published_on 发布日期 / level 证据层级徽标（L1/L2/L3 不同底色）/ sample_size 样本量。
 * sample_size 为 null 时必须显示「样本量未知·有偏差风险」标注。
 * is_demo_data=true 时整卡加「演示数据」斜纹底 + 右上角标（CONSTRAINTS 第四节 合规标识）；
 * 页面级合规说明在侧栏提示条一处（工作台页），不在每卡重复。
 * 来源链接单行化：域名作链接文字（完整 URL 在 href，悬停可见），不再单列 URL 文本行。
 */
import type { ValidEvidenceCard } from "../utils/evidence-schema"

const props = defineProps<{
  card: ValidEvidenceCard
  anchor?: string
  number?: number
  highlighted?: boolean
}>()

const levelLabel: Record<string, string> = {
  L1: "L1 一手反馈",
  L2: "L2 二手转述",
  L3: "L3 宏观语境",
}

const classificationLabels: Record<string, string> = {
  rule: "规则基线",
  manual: "人工复核",
  llm: "LLM 分类",
  ensemble: "聚合分类",
}

const classificationLabel = computed(() =>
  props.card.classification_method ? classificationLabels[props.card.classification_method] : "",
)

/** 来源域名（链接文字）；非标准 URL 时原样回退 */
const host = computed(() => {
  try {
    return new URL(props.card.source_url).host
  } catch {
    return props.card.source_url
  }
})

const provenanceItems = computed(() => {
  const card = props.card
  return [
    { key: "claim", label: "卖点", value: card.claim_id === "unassigned" ? "未归属" : card.claim_id },
    { key: "aspectTerms", label: "卖点术语", value: card.aspect_terms?.join("、") },
    { key: "review", label: "评论 ID", value: card.review_id },
    { key: "market", label: "市场", value: card.market?.toUpperCase() },
    { key: "source", label: "来源 ID", value: card.source_id },
    { key: "authorization", label: "授权", value: card.authorization },
    { key: "authorizationRef", label: "授权依据", value: card.authorization_ref },
    { key: "classification", label: "分类方法", value: classificationLabel.value },
    { key: "classificationNote", label: "复核说明", value: card.classification_note },
    { key: "reviewReasons", label: "复核分流", value: card.review_reasons?.join("；") },
  ].filter((item): item is { key: string; label: string; value: string } =>
    Boolean(item.value?.trim()),
  )
})
</script>

<template>
  <article
    :id="anchor"
    class="card"
    :class="{ 'card--demo': card.is_demo_data, 'card--focused': highlighted }"
  >
    <span v-if="number !== undefined" class="card__number num">{{ String(number).padStart(2, "0") }}</span>
    <span v-if="card.is_demo_data" class="card__ribbon">演示数据</span>
    <p class="card__excerpt">{{ card.excerpt }}</p>
    <div class="card__meta">
      <span v-if="card.relevance === 'irrelevant'" class="badge badge--irrelevant">不相关 · 不参与判定</span>
      <span v-if="classificationLabel" class="badge" :class="`badge--method-${card.classification_method}`">{{ classificationLabel }}</span>
      <span v-if="card.classification_method === 'manual' && card.annotator_agreement === false" class="badge badge--sizewarn">人工覆盖规则基线</span>
      <span v-if="card.review_required" class="badge badge--review">建议人工复核</span>
      <span class="badge badge--level" :class="`badge--${card.level}`" :title="`证据层级 ${card.level}`">
        {{ levelLabel[card.level] || card.level }}
      </span>
      <span class="badge badge--lang">{{ card.language }}</span>
      <span class="badge badge--date num">{{ card.published_on }}</span>
      <span class="badge num" :class="card.sample_size === null ? 'badge--sizewarn' : 'badge--num'">
        {{ card.sample_size === null ? "样本量未知·有偏差风险" : `样本量 n=${card.sample_size}` }}
      </span>
      <a
        class="card__source"
        :href="card.source_url"
        target="_blank"
        rel="noopener noreferrer"
        :title="card.source_url"
      >
        {{ host }} ↗
      </a>
    </div>
    <dl v-if="provenanceItems.length" class="card__provenance" aria-label="来源与授权信息">
      <div v-for="item in provenanceItems" :key="item.key" class="card__provenance-item">
        <dt>{{ item.label }}</dt>
        <dd :title="item.value">{{ item.value }}</dd>
      </div>
    </dl>
  </article>
</template>
