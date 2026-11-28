<script setup lang="ts">
import { SCENARIOS, loadEvidenceEnvelope } from "../composables/useEvidence"
import type { ScenarioId, EvidenceEnvelope } from "../composables/useEvidence"
import { HYPOTHESES, createCustomHypothesis, groupCardsByHypothesis, STATUS_META } from "../utils/hypotheses"
import type { HypothesisStatus } from "../utils/hypotheses"
import { SAMPLING_BIAS, buildValidationPlan } from "../utils/validation-plan"
import { buildCasePackage } from "../utils/case-export"
import { buildL1ImportTemplate } from "../utils/l1-import-template"
import {
  DECISION_OPTIONS,
  VALIDATION_ROUNDS_KEY,
  canConfirmValidationRound,
  emptyPrototypeObservation,
  emptyValidationRound,
  hasValidationRoundContent,
  missingValidationRoundFields,
  normalizeValidationRound,
  normalizeValidationRounds,
  validationRoundErrors,
} from "../utils/validation-round"
import type { PrototypeObservation, ValidationRound } from "../utils/validation-round"
import AppShell from "../components/AppShell.vue"
import StanceBanner from "../components/StanceBanner.vue"
import HypothesisEvidence from "../components/HypothesisEvidence.vue"
import QuestionsColumn from "../components/QuestionsColumn.vue"
import EvidenceCardView from "../components/EvidenceCardView.vue"
import InvalidCardNotice from "../components/InvalidCardNotice.vue"
import WorkbenchTour from "../components/WorkbenchTour.vue"

const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()
const apiBase = String(config.public.apiBase ?? "fixtures")
const isFixturesMode = apiBase.trim() === "" || apiBase.trim().toLowerCase() === "fixtures"

const productInput = ref("旅行收纳包")
const searchQuery = ref("旅行收纳包")
const activeHypothesisId = ref(HYPOTHESES[0]?.id ?? "")
const hypotheses = ref(HYPOTHESES.map((hypothesis) => ({ ...hypothesis, keywords: [...hypothesis.keywords] })))
const mobilePanel = ref<"hypotheses" | "evidence" | "actions">("evidence")
const tourStep = ref<number | null>(null)
const TOUR_KEY = "crosspilot.workbench.tour.v1"
const copyFeedback = ref("")
const checkedActions = reactive<Record<string, boolean>>({})
const customTitle = ref("")
const customProbe = ref("")
const customKeywords = ref("")
const customError = ref("")
const showCustomForm = ref(false)
const rounds = ref<ValidationRound[]>([])
const roundDraft = ref<ValidationRound>(emptyValidationRound())
const showRoundForm = ref(false)
const roundFeedback = ref("")
const usePrototype = ref(false)
const prototypeDraft = ref<PrototypeObservation>(emptyPrototypeObservation())

const scenario = computed<ScenarioId>(() => {
  const value = String(route.query.scenario ?? "real")
  return value === "conflict" || value === "limited" ? value : "real"
})

watch([scenario, searchQuery, activeHypothesisId], () => {
  if (showRoundForm.value) resetRoundForm("场景或假设已切换，本轮草稿已关闭")
})

const storageReady = ref(false)
const workspaceStorageKey = computed(
  () => `crosspilot.workbench.${scenario.value}.${searchQuery.value}`,
)

function restoreWorkspace() {
  hypotheses.value = HYPOTHESES.map((hypothesis) => ({ ...hypothesis, keywords: [...hypothesis.keywords] }))
  for (const key of Object.keys(checkedActions)) delete checkedActions[key]
  activeHypothesisId.value = HYPOTHESES[0]?.id ?? ""
  try {
    const raw = localStorage.getItem(workspaceStorageKey.value)
    if (!raw) return
    const saved = JSON.parse(raw) as {
      hypotheses?: Array<{
        id?: unknown
        title?: unknown
        probe?: unknown
        keywords?: unknown
        custom?: unknown
      }>
      actions?: Record<string, unknown>
      activeHypothesisId?: unknown
    }
    if (Array.isArray(saved.hypotheses)) {
      for (const item of saved.hypotheses) {
        if (typeof item.id !== "string") continue
        const hypothesis = hypotheses.value.find((candidate) => candidate.id === item.id)
        if (hypothesis) {
          if (typeof item.title === "string") hypothesis.title = item.title.slice(0, 200)
          if (typeof item.probe === "string") hypothesis.probe = item.probe.slice(0, 1000)
          continue
        }
        if (
          !/^custom-[a-z0-9-]{1,72}$/.test(item.id) ||
          typeof item.title !== "string" ||
          !item.title.trim() ||
          hypotheses.value.filter((candidate) => candidate.custom).length >= 20
        ) {
          continue
        }
        hypotheses.value.push({
          id: item.id,
          title: item.title.slice(0, 200),
          probe: typeof item.probe === "string" ? item.probe.slice(0, 1000) : "请找一个会推翻该假设的具体使用场景。",
          keywords: Array.isArray(item.keywords)
            ? item.keywords.filter((keyword): keyword is string => typeof keyword === "string").slice(0, 20)
            : [],
          custom: true,
        })
      }
    }
    if (saved.actions && typeof saved.actions === "object") {
      for (const [key, value] of Object.entries(saved.actions).slice(0, 200)) {
        if (typeof value === "boolean") checkedActions[key] = value
      }
    }
    if (
      typeof saved.activeHypothesisId === "string" &&
      hypotheses.value.some((hypothesis) => hypothesis.id === saved.activeHypothesisId)
    ) {
      activeHypothesisId.value = saved.activeHypothesisId
    }
  } catch {
    // Invalid or unavailable local storage must not block the workbench.
  }
}

function persistWorkspace() {
  if (!storageReady.value) return
  try {
    localStorage.setItem(
      workspaceStorageKey.value,
      JSON.stringify({
        hypotheses: hypotheses.value.map(({ id, title, probe, keywords, custom }) => ({
          id,
          title,
          probe,
          keywords,
          custom: custom === true,
        })),
        actions: checkedActions,
        activeHypothesisId: activeHypothesisId.value,
      }),
    )
  } catch {
    // The current session still works when browser storage is unavailable.
  }
}

watch(workspaceStorageKey, restoreWorkspace)
watch(hypotheses, persistWorkspace, { deep: true })
watch(checkedActions, persistWorkspace, { deep: true })
watch(activeHypothesisId, persistWorkspace)

const { data, pending, error, refresh } = await useAsyncData<EvidenceEnvelope>(
  "evidence",
  () => loadEvidenceEnvelope(scenario.value, searchQuery.value, apiBase),
  { watch: isFixturesMode ? [scenario] : [scenario, searchQuery] },
)

const envelope = computed(() => data.value ?? null)
const grouped = computed(() =>
  envelope.value
    ? groupCardsByHypothesis(
        envelope.value.cards,
        hypotheses.value,
        envelope.value.claimDecisions,
      )
    : null,
)
const bannerClaimDecisions = computed(() => {
  if (!envelope.value) return []
  return hypotheses.value.flatMap((hypothesis) => {
    const decision =
      envelope.value?.claimDecisions.find((item) => item.claim_id === hypothesis.id) ??
      grouped.value?.groups.find((group) => group.hypothesis.id === hypothesis.id)?.decision
    return decision ? [decision] : []
  })
})

const hypothesisViews = computed(() =>
  (grouped.value?.groups ?? []).map((group, index) => ({
    hypothesis: group.hypothesis,
    index,
    group,
    status: group.status,
    statusNote: group.statusNote,
    supportCount: group.support.filter((card) => card.level === "L1").length,
    opposeCount: group.oppose.filter((card) => card.level === "L1").length,
    missingCount: group.missing.length,
  })),
)

const activeView = computed(() =>
  hypothesisViews.value.find((view) => view.hypothesis.id === activeHypothesisId.value),
)
const activeGroup = computed(() => activeView.value?.group ?? null)
const activePlan = computed(() =>
  activeView.value
    ? buildValidationPlan({
        hypothesis: activeView.value.hypothesis,
        status: activeView.value.status,
        product: envelope.value?.query || searchQuery.value,
        decision: activeView.value.group.decision,
        support: activeView.value.group.support,
        oppose: activeView.value.group.oppose,
      })
    : null,
)
const activeComparison = computed(() =>
  envelope.value?.comparisons.find((item) => item.claim_id === activeHypothesisId.value) ?? null,
)
const activeQuestions = computed(() => {
  const activeId = activeView.value?.hypothesis.id
  const title = activeView.value?.hypothesis.title
  const stableTitle = HYPOTHESES.find((hypothesis) => hypothesis.id === activeId)?.title
  return (envelope.value?.questions ?? []).filter(
    (question) =>
      !title ||
      question.text.includes(title) ||
      Boolean(activeId && question.text.includes(activeId)) ||
      Boolean(stableTitle && question.text.includes(stableTitle)) ||
      question.text.includes("当前没有可归属") ||
      question.text.includes(searchQuery.value),
  )
})

const currentRounds = computed(() =>
  rounds.value
    .filter(
      (round) =>
        round.scenario === scenario.value &&
        round.query === (envelope.value?.query || searchQuery.value) &&
        round.claimId === activeHypothesisId.value,
    )
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
)

function decisionLabel(decision: ValidationRound["decision"]): string {
  return DECISION_OPTIONS.find((option) => option.value === decision)?.label ?? "未决定"
}

function resetRoundForm(message = "") {
  roundDraft.value = emptyValidationRound()
  showRoundForm.value = false
  usePrototype.value = false
  prototypeDraft.value = emptyPrototypeObservation()
  roundFeedback.value = message
}

function startValidationRound() {
  if (!activeView.value) return
  const evidenceRefs = [
    `claim_id=${activeView.value.hypothesis.id}`,
    ...(activePlan.value?.basis.cards.map(
      (card) => `${card.review_id || "review"}: ${card.source_url}`,
    ) ?? []),
  ].join("; ")
  roundDraft.value = {
    ...emptyValidationRound(),
    createdAt: new Date().toISOString(),
    scenario: scenario.value,
    query: envelope.value?.query || searchQuery.value,
    claimId: activeView.value.hypothesis.id,
    hypothesisTitle: activeView.value.hypothesis.title,
    status: activeView.value.status,
    evidenceRefs,
    market: envelope.value?.market || "de",
    l1SnapshotSha256: envelope.value?.l1SnapshotSha256 ?? null,
  }
  roundFeedback.value = ""
  usePrototype.value = false
  prototypeDraft.value = emptyPrototypeObservation()
  showRoundForm.value = true
}

function saveValidationRound() {
  const draftSource: ValidationRound = { ...roundDraft.value }
  if (usePrototype.value) {
    draftSource.prototype = { ...prototypeDraft.value }
    const hasPrototypeContent = Boolean(
      prototypeDraft.value.itemsLoaded.trim() ||
      prototypeDraft.value.retrieval.trim() ||
      prototypeDraft.value.friction.trim(),
    )
    if (!draftSource.observation.trim() && hasPrototypeContent) {
      draftSource.observation = [
        `装什么：${prototypeDraft.value.itemsLoaded || "待记录"}`,
        `怎么取：${prototypeDraft.value.retrieval || "待记录"}`,
        `哪里麻烦：${prototypeDraft.value.friction || "待记录"}`,
      ].join("；")
    }
  } else {
    delete draftSource.prototype
  }
  const draft = normalizeValidationRound(draftSource)
  const errors = validationRoundErrors(draft)
  if (errors.length) {
    roundFeedback.value = errors.join("；")
    return
  }
  if (!hasValidationRoundContent(draft)) {
    roundFeedback.value = "请先填写本轮观察、决定或下一步"
    return
  }
  if (draft.confirmation === "confirmed" && !canConfirmValidationRound(draft)) {
    roundFeedback.value = `还不能标记运营已确认，缺少：${missingValidationRoundFields(draft).join("、")}`
    return
  }
  const saved = {
    ...draft,
    id: draft.id || `round-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
  }
  const index = rounds.value.findIndex((round) => round.id === saved.id)
  if (index >= 0) rounds.value[index] = saved
  else rounds.value.push(saved)
  try {
    localStorage.setItem(VALIDATION_ROUNDS_KEY, JSON.stringify(rounds.value))
    roundFeedback.value = saved.confirmation === "confirmed" ? "本轮已保存并标记运营确认" : "本轮草稿已保存，未标记运营确认"
    showRoundForm.value = false
  } catch {
    roundFeedback.value = "本地保存失败，请导出历史轮次"
  }
}

watch(
  grouped,
  (groups) => {
    if (!groups?.groups.length) return
    if (!groups.groups.some((group) => group.hypothesis.id === activeHypothesisId.value)) {
      activeHypothesisId.value = groups.groups[0].hypothesis.id
    }
  },
  { immediate: true },
)

function addCustomHypothesis() {
  try {
    const hypothesis = createCustomHypothesis(
      customTitle.value,
      customProbe.value,
      customKeywords.value.split(/[,，\n]/),
    )
    hypotheses.value.push(hypothesis)
    activeHypothesisId.value = hypothesis.id
    customTitle.value = ""
    customProbe.value = ""
    customKeywords.value = ""
    customError.value = ""
    showCustomForm.value = false
    mobilePanel.value = "evidence"
  } catch (error) {
    customError.value = error instanceof Error ? error.message : "无法创建假设"
  }
}

function selectHypothesis(id: string, revealEvidence = false) {
  activeHypothesisId.value = id
  if (!revealEvidence) return
  mobilePanel.value = "evidence"
  nextTick(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    document.getElementById(`hypo-${id}`)?.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
      block: "start",
    })
  })
}

function startTour() {
  tourStep.value = 0
  mobilePanel.value = "hypotheses"
}

function finishTour() {
  tourStep.value = null
  mobilePanel.value = "evidence"
  try {
    localStorage.setItem(TOUR_KEY, "1")
  } catch {
    // Storage can be unavailable in privacy modes; the guide still works for this visit.
  }
}

function advanceTour() {
  if (tourStep.value === null) return
  if (tourStep.value >= 2) {
    finishTour()
    return
  }
  tourStep.value += 1
  mobilePanel.value = tourStep.value === 1 ? "evidence" : "actions"
}

function onTourKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && tourStep.value !== null) finishTour()
}

onMounted(() => {
  restoreWorkspace()
  storageReady.value = true
  try {
    rounds.value = normalizeValidationRounds(JSON.parse(localStorage.getItem(VALIDATION_ROUNDS_KEY) ?? "[]"))
  } catch {
    rounds.value = []
  }
  const hashId = window.location.hash.replace(/^#hypo-/, "")
  if (hypotheses.value.some((hypothesis) => hypothesis.id === hashId)) selectHypothesis(hashId)
  let seen = "1"
  try {
    seen = localStorage.getItem(TOUR_KEY) ?? "0"
  } catch {
    seen = "0"
  }
  if (seen !== "1") startTour()
  window.addEventListener("keydown", onTourKeydown)
})

onBeforeUnmount(() => {
  persistWorkspace()
  window.removeEventListener("keydown", onTourKeydown)
})

const mobileTabs = [
  { id: "hypotheses", label: "产品与假设" },
  { id: "evidence", label: "证据对照" },
  { id: "actions", label: "验证建议" },
] as const

const generatedShort = computed(() => {
  const raw = envelope.value?.generated_at ?? ""
  return raw ? raw.split(".")[0].replace("T", " ").replace("Z", " UTC") : ""
})

const hasDemoCards = computed(() =>
  [...(envelope.value?.cards ?? []), ...(envelope.value?.l2Cards ?? [])].some(
    (card) => card.is_demo_data,
  ),
)
const hasRealCards = computed(() =>
  [...(envelope.value?.cards ?? []), ...(envelope.value?.l2Cards ?? [])].some(
    (card) => !card.is_demo_data,
  ),
)
const hasMixedEvidence = computed(() => hasDemoCards.value && hasRealCards.value)

const activeLabel = (id: ScenarioId) => (scenario.value === id ? "active" : "")
const scenarioOptions = computed(() =>
  SCENARIOS.map((item) =>
    isFixturesMode && item.id === "real" ? { ...item, label: "本地快照（固定）" } : item,
  ),
)
const fixedScenarioLabel = computed(
  () => scenarioOptions.value.find((item) => item.id === scenario.value)?.label ?? "固定演示场景",
)
const showMockNotice = computed(
  () => hasDemoCards.value || (isFixturesMode && scenario.value !== "real"),
)

function switchScenario(id: ScenarioId) {
  router.replace({ query: { ...route.query, scenario: id } })
}

function submitSearch() {
  searchQuery.value = productInput.value.trim() || "旅行收纳包"
}

const ACTION_COPY: Record<HypothesisStatus, { title: string; description: string }> = {
  supported: {
    title: "独立判定为有限支持，继续复核。",
    description: "当前卖点的 L1 独立样本已过门禁，但区间仍宽；先扩大样本，再进入详情页 A/B 测试。",
  },
  refuted: {
    title: "独立判定为多数反对，先修正卖点。",
    description: "当前卖点的反对份额占优；保留支持侧原文，定位反对集中在哪些尺寸、材料或使用场景。",
  },
  conflicting: {
    title: "样本内存在分歧，先定位使用场景。",
    description: "当前卖点的支持与反对并存，统计上尚未形成多数；用访谈和原型测试解释分歧。",
  },
  insufficient: {
    title: "证据不足，先补样本再判断。",
    description: "当前卖点可能为零样本或低于门禁；任何偏好结论都不可用，优先补充目标市场 L1 反馈。",
  },
}

const actionCopy = computed(() => ACTION_COPY[activeView.value?.status ?? "insufficient"])
const actionItems = computed(() => activePlan.value?.nextSteps ?? [])

const actionKey = (index: number) => `${activeHypothesisId.value}:${index}`
const completedActionCount = computed(
  () => actionItems.value.filter((_, index) => checkedActions[actionKey(index)]).length,
)

const planText = computed(() => {
  const view = activeView.value
  const plan = activePlan.value
  const questions = activeQuestions.value
  const claimLines = hypothesisViews.value.flatMap((item) => [
    `${item.index + 1}. ${item.hypothesis.title}`,
    `   claim_id：${item.hypothesis.id}`,
    `   独立判定：${STATUS_META[item.status].label}；${item.statusNote}`,
    `   这次要验证：${item.hypothesis.probe}`,
  ])
  return [
    "CrossPilot 完整验证计划",
    `产品：${envelope.value?.query || searchQuery.value}；市场：德国`,
    `场景：${fixedScenarioLabel.value}；数据模式：${envelope.value?.data_mode ?? "未标注"}`,
    view ? `当前焦点：${view.hypothesis.title}` : "当前焦点：未选择",
    "",
    `一、${hypothesisViews.value.length} 条卖点假设（逐条独立判定）`,
    ...claimLines,
    "",
    "二、当前假设的依据与待验证问题",
    ...(plan ? [plan.basis.summary, plan.notice] : []),
    ...(questions.length
      ? questions.map((question, index) => `${index + 1}. ${question.text}\n   来源：${question.source}`)
      : ["当前暂无待验证问题。"]),
    "",
    "三、访谈问题",
    ...(plan?.interviews.flatMap((question, index) => [
      `${index + 1}. ${question.text}`,
      `   目的：${question.why}`,
    ]) ?? []),
    "",
    "四、A/B 两版待测试文案",
    ...(plan?.copyVariants.map((variant) => `${variant.label} 版：${variant.text}`) ?? []),
    "",
    "五、原型测试方案",
    ...(plan ? [plan.prototypeTitle, ...plan.prototypeSteps.map((item, index) => `${index + 1}. ${item}`)] : []),
    "",
    "六、样本与成功判据",
    ...(plan?.sampleCriteria.map((item) => `- ${item}`) ?? []),
    "",
    "七、采样偏差与推断边界",
    ...SAMPLING_BIAS.map((item) => `- ${item}`),
    ...(bannerClaimDecisions.value[0]?.inference_note
      ? [`- ${bannerClaimDecisions.value[0].inference_note}`]
      : []),
    "",
    "八、下一步行动",
    ...actionItems.value.map((item, index) => `${checkedActions[actionKey(index)] ? "[x]" : "[ ]"} ${item}`),
  ].join("\n")
})

function flashCopyFeedback(message: string) {
  copyFeedback.value = message
  window.setTimeout(() => {
    copyFeedback.value = ""
  }, 2400)
}

async function copyPlan() {
  try {
    await navigator.clipboard.writeText(planText.value)
    flashCopyFeedback("已复制完整验证计划")
  } catch {
    flashCopyFeedback("复制失败，请手动选择计划内容")
  }
}

function exportCasePackage() {
  const current = envelope.value
  if (!current) return
  const plans = hypothesisViews.value.map((item) => ({
    hypothesis: item.hypothesis,
    status: item.status,
    statusNote: item.statusNote,
    decision: item.group.decision,
    plan: buildValidationPlan({
      hypothesis: item.hypothesis,
      status: item.status,
      product: current.query || searchQuery.value,
      decision: item.group.decision,
      support: item.group.support,
      oppose: item.group.oppose,
    }),
  }))
  const currentRounds = rounds.value.filter(
    (round) =>
      round.scenario === scenario.value &&
      round.query === (current.query || searchQuery.value),
  )
  const payload = buildCasePackage(current, plans, currentRounds)
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `crosspilot-case-${scenario.value}.json`
  link.click()
  URL.revokeObjectURL(url)
  flashCopyFeedback("已导出案例证据包；演示与真实边界已写入文件")
}

function exportL1ImportTemplate() {
  try {
    const payload = buildL1ImportTemplate(
      envelope.value?.query || searchQuery.value,
      hypotheses.value,
    )
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = "crosspilot-l1-import-template.json"
    link.click()
    URL.revokeObjectURL(url)
    const omitted = hypotheses.value.filter(
      (hypothesis) =>
        hypothesis.custom && !hypothesis.keywords.some((keyword) => keyword.trim()),
    ).length
    flashCopyFeedback(
      omitted
        ? `已导出 L1 导入模板；${omitted} 条无关键词自定义假设未写入 claim_terms，需人工复核`
        : "已导出 L1 导入模板；请补齐来源、授权与评论后再导入",
    )
  } catch (cause) {
    flashCopyFeedback(cause instanceof Error ? cause.message : "L1 导入模板导出失败")
  }
}

useHead({ title: "卖点验证工作台 · CrossPilot 2.0" })
</script>

<template>
  <AppShell crumb="卖点验证工作台">
    <template #sidebar>
      <div v-if="envelope" class="side__meta">
        <span>
          数据模式
          <span class="mode-badge" :class="envelope.data_mode === 'live' ? 'mode-badge--live' : 'mode-badge--snapshot'">
            {{ envelope.data_mode === 'live' ? '实时 live' : '快照 snapshot' }}
          </span>
        </span>
        <span>来源 {{ envelope.dataSource }}</span>
        <span v-if="generatedShort" class="num">生成 {{ generatedShort }}</span>
      </div>
    </template>

    <div class="wb">
      <header class="wb__header">
        <div class="wb__heading">
          <h1>卖点验证工作台</h1>
        </div>
        <div class="wb__controls">
          <nav class="wb__scenarios" aria-label="场景切换">
            <button
              v-for="item in scenarioOptions"
              :key="item.id"
              type="button"
              class="scenario-btn"
              :class="[activeLabel(item.id), { 'scenario-btn--demo': item.demo }]"
              @click="switchScenario(item.id)"
            >
              {{ item.label }}
            </button>
          </nav>
          <div v-if="isFixturesMode" class="wb__fixed-product" role="note">
            <span class="wb__fixed-label">固定演示场景</span>
            <strong>旅行收纳包 · 德国市场</strong>
            <span>当前：{{ fixedScenarioLabel }}。fixtures 仅切换内置场景，不检索任意商品。</span>
          </div>
          <form v-else class="wb__search" @submit.prevent="submitSearch">
            <label class="wb__field">
              <span class="wb__label">产品</span>
              <input v-model="productInput" type="text" class="wb__input" placeholder="输入检索产品" />
            </label>
            <span class="wb__market">德国市场</span>
            <button type="submit" class="btn btn--primary btn--sm">检索证据</button>
          </form>
        </div>
      </header>

      <div v-if="pending" class="statebox">正在加载证据…</div>
      <div v-else-if="error" class="statebox statebox--error">
        <p>证据加载失败：{{ (error as Error).message }}</p>
        <button type="button" class="btn btn--primary btn--sm" @click="refresh()">重试</button>
      </div>

      <template v-else-if="envelope">
        <StanceBanner
          :stance="envelope.stance"
          :decision="envelope.decision"
          :claim-decisions="bannerClaimDecisions"
          :hypotheses="hypotheses"
          :active-claim-id="activeHypothesisId"
          :scenario="scenario"
          :query="envelope.query || searchQuery"
        />

        <p v-if="envelope.l1Notice" class="wb__notice wb__notice--warning" role="status">
          <strong>L1 数据提示</strong>{{ envelope.l1Notice }}
        </p>
        <p v-if="showMockNotice" class="wb__notice">
          <strong>{{ hasMixedEvidence ? "混合数据 · 含模拟示例" : "演示模式 · Mock 数据" }}</strong>
          {{
            hasMixedEvidence
              ? "同时包含真实与模拟评论；模拟卡不参与真实结论，支持/反对计数分别标注真实与演示。"
              : "演示数据：模拟回填，非真实德国消费者反馈；所有评论均为模拟示例，仅用于体验证据验证流程。"
          }}
        </p>

        <div class="wb__mobile-tabs" role="tablist" aria-label="工作台面板">
          <button
            v-for="tab in mobileTabs"
            :id="`wb-tab-${tab.id}`"
            :key="tab.id"
            type="button"
            role="tab"
            :aria-selected="mobilePanel === tab.id"
            :aria-controls="`wb-panel-${tab.id}`"
            :class="{ active: mobilePanel === tab.id }"
            @click="mobilePanel = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="wb__workbench">
          <aside
            id="wb-panel-hypotheses"
            class="wb__panel wb__hypotheses"
            :class="{ 'is-mobile-active': mobilePanel === 'hypotheses', 'is-tour-active': tourStep === 0 }"
            role="tabpanel"
            aria-labelledby="wb-tab-hypotheses"
          >
            <header class="wb__panel-head">
              <h2>产品与假设</h2>
              <span>{{ hypothesisViews.length }} 条假设</span>
            </header>
            <div class="wb__hypothesis-list">
              <article
                v-for="view in hypothesisViews"
                :key="view.hypothesis.id"
                class="wb__hypothesis"
                :class="[
                  `wb__hypothesis--${view.status}`,
                  { 'is-active': activeHypothesisId === view.hypothesis.id },
                ]"
              >
                <button
                  type="button"
                  class="wb__hypothesis-select"
                  :aria-pressed="activeHypothesisId === view.hypothesis.id"
                  @click="selectHypothesis(view.hypothesis.id, true)"
                >
                  <span class="wb__hypothesis-top">
                    <span class="wb__hypothesis-number num">{{ String(view.index + 1).padStart(2, "0") }}</span>
                    <span class="wb__hypothesis-title">{{ view.hypothesis.title || "未命名假设" }}</span>
                    <span class="wb__hypothesis-arrow" aria-hidden="true">→</span>
                  </span>
                </button>
                <div class="wb__hypothesis-edit">
                  <label>
                    <span>假设标题</span>
                    <input v-model="view.hypothesis.title" type="text" :aria-label="`假设 ${view.index + 1} 标题`" />
                  </label>
                  <label>
                    <span>核实问题</span>
                    <textarea v-model="view.hypothesis.probe" rows="2" :aria-label="`假设 ${view.index + 1} 核实问题`" />
                  </label>
                  <p v-if="view.hypothesis.custom" class="wb__hypothesis-id">
                    导入归属 ID：<code>{{ view.hypothesis.id }}</code>
                  </p>
                </div>
                <span class="status-pill" :class="STATUS_META[view.status].cls">
                  {{ STATUS_META[view.status].label }}
                </span>
                <span class="wb__hypothesis-counts num">
                  {{ view.supportCount }} 支持 · {{ view.opposeCount }} 反对 · {{ view.missingCount }} 语境
                </span>
              </article>
            </div>
            <div class="wb__custom-hypothesis">
              <button type="button" class="wb__custom-toggle" @click="showCustomForm = !showCustomForm">
                {{ showCustomForm ? "取消新增" : "＋ 新增假设" }}
              </button>
              <form v-if="showCustomForm" class="wb__custom-form" @submit.prevent="addCustomHypothesis">
                <label>
                  <span>假设标题</span>
                  <input v-model="customTitle" type="text" maxlength="200" aria-label="自定义假设标题" placeholder="例如：防水比轻量更重要" />
                </label>
                <label>
                  <span>核实问题</span>
                  <textarea v-model="customProbe" rows="2" maxlength="1000" aria-label="自定义假设核实问题" placeholder="什么反例会推翻它？" />
                </label>
                <label>
                  <span>归属关键词（可选）</span>
                  <input v-model="customKeywords" type="text" aria-label="自定义假设归属关键词" placeholder="逗号分隔，中英文均可" />
                </label>
                <p v-if="customError" class="wb__custom-error" role="alert">{{ customError }}</p>
                <button type="submit" class="btn btn--primary btn--sm">创建并验证</button>
                <p class="wb__custom-hint">创建后显示 claim_id；授权评论导入时填写该 ID 即可归属。假设仅保存在本机浏览器。</p>
              </form>
            </div>
            <div class="wb__boundary">
              <span aria-hidden="true">ⓘ</span>
              <p>验证的是卖点假设，<br />不是替市场下结论。</p>
            </div>
            <button type="button" class="wb__tour-replay" @click="startTour">播放使用引导</button>
          </aside>

          <section
            id="wb-panel-evidence"
            class="wb__panel wb__evidence"
            :class="{ 'is-mobile-active': mobilePanel === 'evidence', 'is-tour-active': tourStep === 1 }"
            role="tabpanel"
            aria-labelledby="wb-tab-evidence"
          >
            <header class="wb__panel-head">
              <h2>证据对照</h2>
              <span>{{ envelope.cards.length }} 张 · 原文 → 判断</span>
            </header>
            <div v-if="grouped" class="wb__evidence-body">
              <div
                v-for="group in grouped.groups"
                v-show="activeHypothesisId === group.hypothesis.id"
                :key="group.hypothesis.id"
                class="wb__hypothesis-pane"
              >
                <HypothesisEvidence :key="`${scenario}-${group.hypothesis.id}`" :group="group" />
              </div>

              <section
                v-if="(grouped?.irrelevant.length ?? 0) + (grouped?.unassigned.length ?? 0) > 0"
                class="wb__review wb__supplement"
              >
                <header class="wb__review-head">
                  <h3>不相关 / 未归属证据</h3>
                  <span class="status-pill status--info num">
                    {{ (grouped?.irrelevant.length ?? 0) + (grouped?.unassigned.length ?? 0) }} 张
                  </span>
                </header>
                <p class="wb__review-note">两类证据分开保留，均不参与状态判定；不相关是相关性判断，未归属是卖点归属缺失。</p>
                <details v-if="grouped?.irrelevant.length" class="wb__review-group">
                  <summary>不相关证据 · {{ grouped.irrelevant.length }} 张</summary>
                  <p>与当前产品卖点无关，保留用于复核检索与分类边界。</p>
                  <EvidenceCardView v-for="card in grouped.irrelevant" :key="card.review_id ?? card.source_url" :card="card" />
                </details>
                <details v-if="grouped?.unassigned.length" class="wb__review-group">
                  <summary>相关但未归属 · {{ grouped.unassigned.length }} 张</summary>
                  <p>产品相关但尚未对应到任何假设，需人工指定 claim_id 后再进入判定。</p>
                  <EvidenceCardView v-for="card in grouped.unassigned" :key="card.review_id ?? card.source_url" :card="card" />
                </details>
              </section>

              <section v-if="envelope.invalidCards.length" class="hypo hypo--invalid wb__supplement">
                <header class="hypo__head">
                  <h3 class="hypo__title">契约校验未通过 · 占位说明</h3>
                </header>
                <InvalidCardNotice v-for="(invalid, index) in envelope.invalidCards" :key="index" :invalid="invalid" />
              </section>
            </div>
            <div v-else class="statebox">正在组织当前假设的证据…</div>
            <div class="wb__storage-note">
              <span aria-hidden="true">✓</span>
              仅 L1 一手反馈参与偏好判定 · L2 / L3 只产出待验证问题
            </div>
          </section>

          <aside
            id="wb-panel-actions"
            class="wb__panel wb__actions"
            :class="{ 'is-mobile-active': mobilePanel === 'actions', 'is-tour-active': tourStep === 2 }"
            role="tabpanel"
            aria-labelledby="wb-tab-actions"
          >
            <header class="wb__panel-head">
              <h2>下一步验证建议</h2>
              <span class="wb__draft-badge">草案</span>
            </header>
            <div class="wb__action-body">
              <section class="wb__plan-intro">
                <h3>{{ actionCopy.title }}</h3>
                <p>{{ actionCopy.description }}</p>
                <div class="wb__plan-gap">
                  <span>这次要验证</span>
                  <p>{{ activeGroup?.hypothesis.probe ?? "选择一条卖点假设后生成验证方向。" }}</p>
                </div>
              </section>

              <QuestionsColumn :questions="activeQuestions" :plan="activePlan" :comparison="activeComparison" />

              <section class="wb__action-checklist">
                <div class="wb__action-heading">
                  <h3>下一步行动</h3>
                  <span class="num">{{ completedActionCount }} / {{ actionItems.length }}</span>
                </div>
                <label v-for="(item, index) in actionItems" :key="item" class="wb__action-check">
                  <input v-model="checkedActions[actionKey(index)]" type="checkbox" />
                  <span>{{ item }}</span>
                </label>
                <p class="wb__action-hint">假设编辑与勾选自动保存在本机浏览器；不代表已完成真人试用。</p>
              </section>

              <details class="wb__round">
                <summary>记录本轮验证结果 · {{ currentRounds.length }} 轮</summary>
                <p class="wb__round-note">按假设追加轮次，不覆盖旧观察；可启用同组原型测试，结构化记录参与者、顺序、装什么、怎么取、哪里麻烦。保存到本机浏览器，未确认前不等于真人试用完成。真实案例完成门禁要求引用同卖点的 review_id: source_url，并绑定当前 L1 snapshot_sha256；仅写 claim_id 或旧快照轮次不计入运营闭环。</p>
                <button v-if="!showRoundForm" type="button" class="btn btn--ghost btn--sm" @click="startValidationRound">
                  开始记录本轮
                </button>
                <form v-else class="wb__round-form" @submit.prevent="saveValidationRound">
                  <label>
                    <span>证据 ID / 链接</span>
                    <textarea v-model="roundDraft.evidenceRefs" rows="3" aria-label="本轮证据依据" />
                    <small>真实案例完成门禁要求引用同卖点的 review_id: source_url；仅写 claim_id 不计入运营闭环。</small>
                  </label>
                  <label>
                    <span>本轮观察</span>
                    <textarea v-model="roundDraft.observation" rows="4" aria-label="本轮观察" placeholder="访谈原话、装什么、怎么取、哪里麻烦" />
                  </label>
                  <label class="wb__prototype-toggle">
                    <input v-model="usePrototype" type="checkbox" />
                    <span>本轮为同组原型测试（多隔层 vs 开放空间）</span>
                  </label>
                  <div v-if="usePrototype" class="wb__prototype-fields">
                    <label>
                      <span>参与者编号</span>
                      <input v-model="prototypeDraft.participantCode" type="text" maxlength="100" aria-label="原型参与者编号" placeholder="如 P01，不填姓名或联系方式" />
                    </label>
                    <label>
                      <span>测试顺序</span>
                      <select v-model="prototypeDraft.order" aria-label="原型测试顺序">
                        <option value="">待记录</option>
                        <option value="multi_first">先用多隔层，再用开放空间</option>
                        <option value="open_first">先用开放空间，再用多隔层</option>
                      </select>
                    </label>
                    <label>
                      <span>装什么</span>
                      <textarea v-model="prototypeDraft.itemsLoaded" rows="3" maxlength="2000" aria-label="原型装载观察" placeholder="每类物品放在哪个区域、是否折叠或挤压、是否放不下" />
                    </label>
                    <label>
                      <span>怎么取</span>
                      <textarea v-model="prototypeDraft.retrieval" rows="3" maxlength="2000" aria-label="原型取物观察" placeholder="首次拿取是否成功、开合次数、翻找步数、是否倒空包体" />
                    </label>
                    <label>
                      <span>哪里麻烦</span>
                      <textarea v-model="prototypeDraft.friction" rows="3" maxlength="2000" aria-label="原型麻烦点" placeholder="卡住拉链、物品遮挡、难度评分或参与者原话" />
                    </label>
                  </div>
                  <label>
                    <span>运营决定</span>
                    <select v-model="roundDraft.decision" aria-label="本轮运营决定">
                      <option value="">待决定</option>
                      <option v-for="option in DECISION_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                  </label>
                  <label>
                    <span>决定理由</span>
                    <textarea v-model="roundDraft.rationale" rows="3" aria-label="本轮决定理由" />
                  </label>
                  <label>
                    <span>下一步</span>
                    <textarea v-model="roundDraft.nextAction" rows="2" aria-label="本轮下一步" />
                  </label>
                  <label>
                    <span>负责人</span>
                    <input v-model="roundDraft.owner" type="text" aria-label="本轮负责人" placeholder="角色或姓名，不填联系方式" />
                  </label>
                  <label>
                    <span>确认状态</span>
                    <select v-model="roundDraft.confirmation" aria-label="本轮确认状态">
                      <option value="pending">待确认</option>
                      <option value="confirmed">运营已确认</option>
                    </select>
                  </label>
                  <div class="wb__round-actions">
                    <button type="submit" class="btn btn--primary btn--sm">保存本轮</button>
                    <button type="button" class="btn btn--ghost btn--sm" @click="showRoundForm = false">取消</button>
                  </div>
                </form>
                <p v-if="roundFeedback" class="wb__round-feedback" role="status">{{ roundFeedback }}</p>
                <div v-if="currentRounds.length" class="wb__round-list">
                  <article v-for="round in currentRounds" :key="round.id" class="wb__round-item">
                    <header>
                      <span class="num">{{ round.createdAt.replace("T", " ").slice(0, 16) }}</span>
                      <span class="status-pill" :class="round.confirmation === 'confirmed' ? 'status--ok' : 'status--warn'">
                        {{ round.confirmation === "confirmed" ? "运营已确认" : "待确认" }}
                      </span>
                    </header>
                    <h4>{{ decisionLabel(round.decision) }} · {{ round.hypothesisTitle }}</h4>
                    <p>{{ round.observation || "尚未填写观察" }}</p>
                    <details v-if="round.prototype" class="wb__round-prototype">
                      <summary>原型测试结构化记录</summary>
                      <p>参与者：{{ round.prototype.participantCode }}；顺序：{{ round.prototype.order === "multi_first" ? "多隔层优先" : "开放空间优先" }}</p>
                      <p><strong>装什么：</strong>{{ round.prototype.itemsLoaded }}</p>
                      <p><strong>怎么取：</strong>{{ round.prototype.retrieval }}</p>
                      <p><strong>哪里麻烦：</strong>{{ round.prototype.friction }}</p>
                    </details>
                    <p v-if="round.rationale"><strong>理由：</strong>{{ round.rationale }}</p>
                    <p v-if="round.nextAction"><strong>下一步：</strong>{{ round.nextAction }}{{ round.owner ? `（${round.owner}）` : "" }}</p>
                    <details>
                      <summary>证据依据</summary>
                      <p>{{ round.evidenceRefs }}</p>
                    </details>
                  </article>
                </div>
              </details>

              <button type="button" class="btn btn--primary btn--sm wb__copy" @click="exportCasePackage">
                导出案例证据包
              </button>
              <button type="button" class="btn btn--ghost btn--sm wb__copy" @click="exportL1ImportTemplate">
                导出 L1 数据导入模板
              </button>
              <p class="wb__action-hint">
                模板只含当前 query、自定义 claim_terms 与内部验证用途；不含评论和授权凭据，补齐 source_id、authorization、authorization_ref、cards 后才能导入。
              </p>
              <button type="button" class="btn btn--ghost btn--sm wb__copy" @click="copyPlan">
                复制完整验证计划
              </button>
              <p v-if="copyFeedback" class="wb__copy-feedback" role="status">{{ copyFeedback }}</p>
              <details class="wb__plan-preview">
                <summary>展开完整计划（可手动选择）</summary>
                <pre>{{ planText }}</pre>
              </details>
            </div>
          </aside>
        </div>

        <WorkbenchTour v-if="tourStep !== null" :step="tourStep" @next="advanceTour" @skip="finishTour" />

        <div v-if="envelope.l2Cards.length || envelope.l2Notice" class="appendix wb__appendix">
          <details class="l2zone">
            <summary class="wb__l2-summary">
              <span>跨来源附录（L2 · 知乎）</span>
              <span>
                {{ envelope.l2Cards.length && envelope.l2Cards.every((card) => card.is_demo_data) ? "全部模拟 · 不参与偏好判定" : "不参与偏好判定" }}
              </span>
            </summary>
            <div class="wb__l2-body">
              <p class="qcol__hint">中文从业者经验只产出待验证问题，不构成支持/反对。</p>
              <p v-if="envelope.l2Notice" class="l2zone__notice">{{ envelope.l2Notice }}</p>
              <p v-else-if="envelope.l2InvalidCards.length" class="l2zone__notice">
                知乎侧有 {{ envelope.l2InvalidCards.length }} 张卡缺少必现字段，已按契约拒绝渲染。
              </p>
              <EvidenceCardView v-for="(card, index) in envelope.l2Cards" :key="index" :card="card" />
            </div>
          </details>
        </div>

        <footer class="footer">
          <span>固定演示边界：非电器旅行收纳包 → 德国市场 → 详情页首屏卖点验证（方案 4.1）</span>
          <span class="num">market={{ envelope.market }} · scenario={{ envelope.scenario }} · data_mode={{ envelope.data_mode }}</span>
        </footer>
      </template>
    </div>
  </AppShell>
</template>
