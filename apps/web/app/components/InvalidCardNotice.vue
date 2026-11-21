<script setup lang="ts">
/**
 * 占位说明卡 —— 收到缺必现字段（或含契约外字段）的证据卡时，
 * 该卡不渲染，改为展示本占位说明（契约注释明确此规则：
 * packages/contracts/evidence-card.schema.json「缺失则前端不得渲染该卡」）。
 */
import type { InvalidEvidenceCard } from "../utils/evidence-schema"

defineProps<{ invalid: InvalidEvidenceCard }>()
</script>

<template>
  <article class="invalid-card">
    <p class="invalid-card__title">该证据卡未通过契约校验，未予渲染</p>
    <ul class="invalid-card__errors">
      <li v-for="err in invalid.errors" :key="err">{{ err }}</li>
    </ul>
    <p class="invalid-card__raw">
      原始数据片段：{{ JSON.stringify(invalid.raw).slice(0, 160) }}
    </p>
    <p class="invalid-card__rule">契约依据：packages/contracts/evidence-card.schema.json（六必现字段，缺一不得渲染）</p>
  </article>
</template>
