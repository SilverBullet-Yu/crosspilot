<script setup lang="ts">
import { loadEvidenceEnvelope } from "../composables/useEvidence"
import type { ValidEvidenceCard } from "../utils/evidence-schema"
import {
  L1_AUTHORIZATION_SCOPES,
  buildL1ReviewDocument,
  defaultL1ReviewDecision,
  filterL1ReviewCards,
  l1ReviewErrors,
  l1ReviewStorageKey,
  normalizeL1ReviewDecision,
} from "../utils/l1-review"
import type { L1AuthorizationScope, L1ReviewDecision } from "../utils/l1-review"

useHead({ title: "L1 人工复核 · CrossPilot 2.0" })

const QUERY = "旅行收纳包"
const config = useRuntimeConfig()
const apiBase = String(config.public.apiBase ?? "fixtures").replace(/\/$/, "")
const apiConfigured = computed(() => Boolean(apiBase) && apiBase !== "fixtures")
const cards = ref<ValidEvidenceCard[]>([])
const decisions = ref<Record<string, L1ReviewDecision>>({})
const scope = ref<L1AuthorizationScope[]>([])
const snapshotSha256 = ref<string | null>(null)
const storageKey = ref<string | null>(null)
const loading = ref(false)
const feedback = ref("")
const error = ref("")
const filter = ref<"pending" | "reviewed" | "all">("all")
const claimFilter = ref("all")
const searchQuery = ref("")

const l1Cards = computed(() => cards.value.filter((card) => card.level === "L1" && !card.is_demo_data))
const claimOptions = computed(() => {
  const custom = l1Cards.value
    .map((card) => card.claim_id)
    .filter((claimId): claimId is string => Boolean(claimId) && claimId !== "unassigned")
  return [...new Set(["capacity", "features", "price", ...custom])].sort()
})

function reviewClaimId(card: ValidEvidenceCard): string {
  return card.relevance === "irrelevant" ? "irrelevant" : card.claim_id || "unassigned"
}

const reviewFilterOptions = computed(() => [
  { id: "all", label: "全部卖点" },
  { id: "unassigned", label: "相关但未归属" },
  { id: "irrelevant", label: "不相关" },
  ...claimOptions.value.map((claimId) => ({ id: claimId, label: claimId })),
])

function decisionFor(card: ValidEvidenceCard): L1ReviewDecision {
  return decisions.value[card.review_id || card.source_url] ?? defaultL1ReviewDecision(card)
}

function errorsFor(card: ValidEvidenceCard): string[] {
  return l1ReviewErrors(decisionFor(card))
}

function needsAttention(card: ValidEvidenceCard): boolean {
  const decision = decisionFor(card)
  return (
    !decision.reviewed ||
    errorsFor(card).length > 0 ||
    (decision.relevance === "relevant" && decision.claim_id === "unassigned")
  )
}

const pendingCount = computed(() => l1Cards.value.filter(needsAttention).length)
const reviewedCount = computed(() => l1Cards.value.length - pendingCount.value)
const reviewProgress = computed(() => {
  const progress: Record<string, string> = {
    all: `${reviewedCount.value}/${l1Cards.value.length}`,
  }
  for (const option of reviewFilterOptions.value) {
    if (option.id === "all") continue
    const cards = l1Cards.value.filter((card) => reviewClaimId(card) === option.id)
    const reviewed = cards.filter((card) => !needsAttention(card)).length
    progress[option.id] = `${reviewed}/${cards.length}`
  }
  return progress
})
const visibleCards = computed(() =>
  filterL1ReviewCards(l1Cards.value, claimFilter.value, searchQuery.value).filter((card) => {
    if (filter.value === "all") return true
    return filter.value === "pending" ? needsAttention(card) : !needsAttention(card)
  }),
)

function clearReviewFilters() {
  filter.value = "all"
  claimFilter.value = "all"
  searchQuery.value = ""
}

function updateDecision(card: ValidEvidenceCard, patch: Partial<L1ReviewDecision>) {
  const key = card.review_id || card.source_url
  decisions.value[key] = normalizeL1ReviewDecision(
    { ...decisionFor(card), ...patch },
    card,
  )
}

function loadDrafts() {
  if (!storageKey.value) return
  try {
    const raw = JSON.parse(localStorage.getItem(storageKey.value) ?? "{}")
    if (typeof raw !== "object" || raw === null) return
    decisions.value = Object.fromEntries(
      Object.entries(raw).filter((entry): entry is [string, L1ReviewDecision] => {
        const [key, value] = entry
        return typeof key === "string" && typeof value === "object" && value !== null
      }),
    )
  } catch {
    feedback.value = "本机复核草稿读取失败，可重新填写"
  }
}

onMounted(async () => {
  if (!apiConfigured.value) return
  loading.value = true
  error.value = ""
  try {
    const envelope = await loadEvidenceEnvelope("real", QUERY, apiBase)
    cards.value = envelope.cards.filter((card) => card.level === "L1" && !card.is_demo_data)
    scope.value = envelope.l1AuthorizationScope as L1AuthorizationScope[]
    snapshotSha256.value = envelope.l1SnapshotSha256
    storageKey.value = snapshotSha256.value
      ? l1ReviewStorageKey(QUERY, snapshotSha256.value)
      : null
    loadDrafts()
    const normalized: Record<string, L1ReviewDecision> = {}
    for (const card of cards.value) {
      const key = card.review_id || card.source_url
      normalized[key] = normalizeL1ReviewDecision(decisions.value[key], card)
    }
    decisions.value = normalized
    if (envelope.l1Notice) error.value = envelope.l1Notice
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "真实 L1 复核队列加载失败"
  } finally {
    loading.value = false
  }
})

function saveDrafts() {
  if (!storageKey.value) {
    feedback.value = "未加载已验证快照版本，不能保存复核草稿"
    return
  }
  try {
    localStorage.setItem(storageKey.value, JSON.stringify(decisions.value))
    feedback.value = "复核草稿已按快照版本保存到本机浏览器，未上传"
  } catch {
    feedback.value = "保存失败，请及时导出 JSON"
  }
}

function exportReviewDocument() {
  try {
    const document = buildL1ReviewDocument(
      cards.value,
      decisions.value,
      QUERY,
      scope.value,
      snapshotSha256.value,
    )
    const blob = new Blob([JSON.stringify(document, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement("a")
    link.href = url
    link.download = "crosspilot-l1-reviewed.json"
    link.click()
    URL.revokeObjectURL(url)
    feedback.value = "已导出复核 JSON；使用 --versioned 重新导入并保留旧快照"
  } catch (cause) {
    feedback.value = cause instanceof Error ? cause.message : "导出失败"
  }
}

function clearDrafts() {
  decisions.value = Object.fromEntries(
    l1Cards.value.map((card) => [
      card.review_id || card.source_url,
      defaultL1ReviewDecision(card),
    ]),
  )
  try {
    if (storageKey.value) localStorage.removeItem(storageKey.value)
    feedback.value = storageKey.value
      ? "本机当前快照版本的复核草稿已清空"
      : "本机复核草稿已重置；未加载快照版本，未删除其他版本草稿"
  } catch {
    feedback.value = "本机复核草稿已重置"
  }
}
</script>

<template>
  <AppShell crumb="L1 人工复核">
    <div class="review-page">
      <section class="history__panel">
        <p class="trial__eyebrow">真实 L1 · 本机复核</p>
        <h1 class="history__title">把规则判断变成可追溯的人工决定</h1>
        <p class="history__body">
          逐条确认立场、卖点归属与相关性，并写下复核说明。草稿按当前快照 `record_sha256` 隔离保存在本机浏览器，旧版本人工决定不会套用到新证据；导出 JSON 后用 `--versioned` 写入新版本，旧快照保留。
        </p>
        <NuxtLink to="/workbench?scenario=real" class="btn btn--primary">回到证据工作台 →</NuxtLink>
      </section>

      <section v-if="!apiConfigured" class="trial" aria-labelledby="review-mode-title">
        <h2 id="review-mode-title">当前为 fixtures 演示模式</h2>
        <p class="trial__hint">
          人工复核队列只读取真实 API 的授权 L1，不用演示评论伪造复核数据。配置 NUXT_PUBLIC_API_BASE 后打开本页。
        </p>
      </section>

      <template v-else>
        <section class="trial" aria-label="复核进度与操作">
          <header class="trial__header">
            <div>
              <p class="trial__eyebrow">旅行收纳包 × 德国</p>
              <h2>复核进度</h2>
            </div>
            <span class="trial__badge">{{ reviewedCount }} / {{ l1Cards.length }} 已完成</span>
          </header>
          <p v-if="loading" class="trial__empty" role="status">正在加载授权 L1…</p>
          <p v-else-if="error && !l1Cards.length" class="trial__empty" role="alert">{{ error }}</p>
          <template v-else>
            <p class="trial__hint">
              待处理 {{ pendingCount }} 条；规则回退、相反立场和未归属评论会优先保留。导出前请确认授权范围与原始文件一致。
            </p>
            <p v-if="snapshotSha256" class="trial__hint">
              当前快照版本：<span class="num">{{ snapshotSha256 }}</span>；草稿仅属于该版本。
            </p>
            <p v-else class="trial__hint" role="alert">
              未获取已验证快照的 record_sha256，草稿隔离、保存与导出不可用。
            </p>
            <fieldset class="review-page__scopes">
              <legend>授权范围（来自快照，不可修改或扩大）</legend>
              <label v-for="item in L1_AUTHORIZATION_SCOPES" :key="item">
                <input :checked="scope.includes(item)" type="checkbox" disabled />
                <span>{{ item }}</span>
              </label>
            </fieldset>
            <div class="trial__actions">
              <button type="button" class="btn btn--ghost" :disabled="!storageKey" @click="saveDrafts">保存本机草稿</button>
              <button type="button" class="btn btn--primary" :disabled="!l1Cards.length || !scope.length || !snapshotSha256" @click="exportReviewDocument">
                导出复核 JSON
              </button>
              <button type="button" class="btn btn--ghost" :disabled="!storageKey" @click="clearDrafts">清空本机复核</button>
            </div>
            <p class="review-page__warning">不要填写评论者姓名、邮箱、电话或地址；导入器会再次清洗联系方式。</p>
            <p v-if="feedback" class="trial__feedback" role="status">{{ feedback }}</p>
          </template>
        </section>

        <section class="trial" aria-labelledby="review-queue-title">
          <header class="trial__header">
            <div>
              <p class="trial__eyebrow">按 review_id 留痕</p>
              <h2 id="review-queue-title">复核队列</h2>
            </div>
          </header>
          <div class="review-page__tools">
            <label class="trial__field">
              <span>按卖点筛选</span>
              <select v-model="claimFilter">
                <option v-for="item in reviewFilterOptions" :key="item.id" :value="item.id">
                  {{ item.label }}（{{ reviewProgress[item.id] }}）
                </option>
              </select>
            </label>
            <label class="trial__field review-page__search">
              <span>搜索原文 / 评论 ID / 来源</span>
              <input v-model="searchQuery" type="search" placeholder="输入关键词，支持德语与评论 ID" />
            </label>
            <button type="button" class="btn btn--ghost btn--sm" @click="clearReviewFilters">清除筛选</button>
          </div>
          <p class="trial__hint">当前显示 {{ visibleCards.length }} / {{ l1Cards.length }} 条评论。</p>
          <div class="review-page__filters" role="tablist" aria-label="复核状态筛选">
            <button
              v-for="item in ([
                { id: 'pending', label: `待处理 ${pendingCount}` },
                { id: 'reviewed', label: `已完成 ${reviewedCount}` },
                { id: 'all', label: `全部 ${l1Cards.length}` },
              ] as const)"
              :key="item.id"
              type="button"
              role="tab"
              :aria-selected="filter === item.id"
              :class="{ active: filter === item.id }"
              @click="filter = item.id"
            >
              {{ item.label }}
            </button>
          </div>
          <p v-if="!loading && !visibleCards.length" class="trial__empty">当前筛选下没有评论。</p>
          <div class="review-page__list">
            <article v-for="card in visibleCards" :key="card.review_id || card.source_url" class="review-card">
              <header class="review-card__head">
                <div>
                  <span class="review-card__id">{{ card.review_id || "缺少 review_id" }}</span>
                  <span class="badge" :class="`badge--${card.level}`">{{ card.level }} 一手反馈</span>
                  <span v-if="card.aspect_terms?.length" class="badge">术语：{{ card.aspect_terms.join("、") }}</span>
                  <span v-if="decisionFor(card).reviewed" class="badge">已人工复核</span>
                </div>
                <a :href="card.source_url" target="_blank" rel="noopener noreferrer">原文出处 ↗</a>
              </header>
              <blockquote class="review-card__excerpt">{{ card.excerpt }}</blockquote>
              <p class="review-card__meta">
                规则票：{{ card.stance_votes?.rule ?? card.stance }}；当前归属：{{ card.claim_id || "未归属" }}；日期：{{ card.published_on }}
              </p>
              <ul v-if="card.review_reasons?.length" class="review-card__reasons">
                <li v-for="reason in card.review_reasons" :key="reason">{{ reason }}</li>
              </ul>
              <label class="review-card__confirm">
                <input
                  :checked="decisionFor(card).reviewed"
                  type="checkbox"
                  @change="updateDecision(card, { reviewed: ($event.target as HTMLInputElement).checked })"
                />
                <span>我已人工复核这条评论</span>
              </label>
              <div class="review-card__grid">
                <label class="trial__field">
                  <span>相关性</span>
                  <select :value="decisionFor(card).relevance" @change="updateDecision(card, { relevance: ($event.target as HTMLSelectElement).value as 'relevant' | 'irrelevant' })">
                    <option value="relevant">相关</option>
                    <option value="irrelevant">不相关</option>
                  </select>
                </label>
                <label class="trial__field">
                  <span>卖点归属</span>
                  <select :value="decisionFor(card).claim_id" @change="updateDecision(card, { claim_id: ($event.target as HTMLSelectElement).value })">
                    <option v-if="decisionFor(card).relevance === 'irrelevant'" value="">不填</option>
                    <option v-else value="unassigned">相关但未归属</option>
                    <option v-for="claimId in claimOptions" :key="claimId" :value="claimId">{{ claimId }}</option>
                  </select>
                </label>
                <label class="trial__field">
                  <span>人工立场</span>
                  <select :value="decisionFor(card).stance" @change="updateDecision(card, { stance: ($event.target as HTMLSelectElement).value as 'support' | 'oppose' | 'insufficient' })">
                    <option value="support">支持</option>
                    <option value="oppose">反对</option>
                    <option value="insufficient">无明确极性</option>
                  </select>
                </label>
              </div>
              <label class="trial__field review-card__note">
                <span>复核说明（必填）</span>
                <textarea
                  :value="decisionFor(card).note"
                  rows="3"
                  maxlength="500"
                  placeholder="说明为什么支持、反对、不相关或未归属；不要填写个人信息"
                  @input="updateDecision(card, { note: ($event.target as HTMLTextAreaElement).value })"
                />
              </label>
              <p v-if="errorsFor(card).length" class="review-card__error">
                仍缺：{{ errorsFor(card).join("、") }}
              </p>
            </article>
          </div>
        </section>
      </template>
    </div>
  </AppShell>
</template>
