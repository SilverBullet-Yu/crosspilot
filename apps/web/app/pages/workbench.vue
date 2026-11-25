<script setup lang="ts">
import { SCENARIOS, loadEvidenceEnvelope } from "../composables/useEvidence"
import type { ScenarioId, EvidenceEnvelope } from "../composables/useEvidence"
import { HYPOTHESES, groupCardsByHypothesis, STATUS_META } from "../utils/hypotheses"
import type { HypothesisStatus } from "../utils/hypotheses"
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

const productInput = ref("旅行收纳包")
const searchQuery = ref("旅行收纳包")
const activeHypothesisId = ref(HYPOTHESES[0]?.id ?? "")
const mobilePanel = ref<"hypotheses" | "evidence" | "actions">("evidence")
const tourStep = ref<number | null>(null)
const TOUR_KEY = "crosspilot.workbench.tour.v1"
const copyFeedback = ref("")
const checkedActions = reactive<Record<string, boolean>>({})

const scenario = computed<ScenarioId>(() => {
  const value = String(route.query.scenario ?? "real")
  return value === "conflict" || value === "limited" ? value : "real"
})

const { data, pending, error, refresh } = await useAsyncData<EvidenceEnvelope>(
  "evidence",
  () => loadEvidenceEnvelope(scenario.value, searchQuery.value, apiBase),
  { watch: [scenario, searchQuery] },
)

const envelope = computed(() => data.value ?? null)
const grouped = computed(() => (envelope.value ? groupCardsByHypothesis(envelope.value.cards) : null))

const hypothesisViews = computed(() =>
  HYPOTHESES.map((hypothesis, index) => {
    const group = grouped.value?.groups.find((item) => item.hypothesis.id === hypothesis.id)
    const status: HypothesisStatus = group?.status ?? "insufficient"
    return {
      hypothesis,
      index,
      group,
      status,
      statusNote: group?.statusNote ?? "正在读取证据状态",
      supportCount: group?.support.filter((card) => card.level === "L1").length ?? 0,
      opposeCount: group?.oppose.filter((card) => card.level === "L1").length ?? 0,
      missingCount: group?.missing.length ?? 0,
    }
  }),
)

const activeView = computed(() =>
  hypothesisViews.value.find((view) => view.hypothesis.id === activeHypothesisId.value),
)
const activeGroup = computed(() => activeView.value?.group ?? null)

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
  const hashId = window.location.hash.replace(/^#hypo-/, "")
  if (HYPOTHESES.some((hypothesis) => hypothesis.id === hashId)) selectHypothesis(hashId)
  let seen = "1"
  try {
    seen = localStorage.getItem(TOUR_KEY) ?? "0"
  } catch {
    seen = "0"
  }
  if (seen !== "1") startTour()
  window.addEventListener("keydown", onTourKeydown)
})

onBeforeUnmount(() => window.removeEventListener("keydown", onTourKeydown))

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

const activeLabel = (id: ScenarioId) => (scenario.value === id ? "active" : "")

function switchScenario(id: ScenarioId) {
  router.replace({ query: { ...route.query, scenario: id } })
}

function submitSearch() {
  searchQuery.value = productInput.value.trim() || "旅行收纳包"
}

const ACTION_COPY: Record<HypothesisStatus, { title: string; description: string }> = {
  support: {
    title: "扩大样本，复核支持是否稳定。",
    description: "当前假设出现一手支持，但样本仍有限；先复核真实使用场景，再决定是否进入详情页测试。",
  },
  conflict: {
    title: "找到分歧背后的使用场景。",
    description: "支持与反对同时存在，先保留矛盾，再用访谈和原型测试解释分歧。",
  },
  insufficient: {
    title: "先补足一手反馈，再判断。",
    description: "当前假设缺少目标市场 L1 消费者反馈，任何偏好结论都不可用；优先补充样本与来源。",
  },
}

const actionCopy = computed(() => ACTION_COPY[activeView.value?.status ?? "insufficient"])
const actionItems = computed(() => [
  "整理当前假设的支持与反对原文",
  activeView.value?.status === "insufficient"
    ? "补充目标市场 L1 一手消费者反馈"
    : "用访谈验证分歧背后的真实使用场景",
  "将候选文案进入 A/B 测试，并记录选择理由",
])

const actionKey = (index: number) => `${activeHypothesisId.value}:${index}`
const completedActionCount = computed(
  () => actionItems.value.filter((_, index) => checkedActions[actionKey(index)]).length,
)

const planText = computed(() => {
  const view = activeView.value
  const questions = envelope.value?.questions ?? []
  return [
    "CrossPilot 验证计划草案",
    `假设：${view?.hypothesis.title ?? ""}`,
    `状态：${view ? STATUS_META[view.status].label : ""}`,
    `说明：${view?.statusNote ?? ""}`,
    `这次要验证：${view?.hypothesis.probe ?? ""}`,
    "",
    "待验证问题",
    ...questions.map((question, index) => `${index + 1}. ${question.text}（${question.source}）`),
    "",
    "下一步行动",
    ...actionItems.value.map((item, index) => `${checkedActions[actionKey(index)] ? "[x]" : "[ ]"} ${item}`),
  ].join("\n")
})

async function copyPlan() {
  try {
    await navigator.clipboard.writeText(planText.value)
    copyFeedback.value = "已复制完整验证计划"
  } catch {
    copyFeedback.value = "复制失败，请手动选择计划内容"
  }
  window.setTimeout(() => {
    copyFeedback.value = ""
  }, 2400)
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
              v-for="item in SCENARIOS"
              :key="item.id"
              type="button"
              class="scenario-btn"
              :class="[activeLabel(item.id), { 'scenario-btn--demo': item.demo }]"
              @click="switchScenario(item.id)"
            >
              {{ item.label }}
            </button>
          </nav>
          <form class="wb__search" @submit.prevent="submitSearch">
            <label class="wb__field">
              <span class="wb__label">产品</span>
              <input v-model="productInput" type="text" class="wb__input" />
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
          :scenario="scenario"
          :query="envelope.query || searchQuery"
        />

        <p v-if="hasDemoCards" class="wb__notice">
          <strong>演示模式 · Mock 数据</strong>
          演示数据：模拟回填，非真实德国消费者反馈；所有评论均为模拟示例，仅用于体验证据验证流程。
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
              <button
                v-for="view in hypothesisViews"
                :key="view.hypothesis.id"
                type="button"
                class="wb__hypothesis"
                :class="[
                  `wb__hypothesis--${view.status}`,
                  { 'is-active': activeHypothesisId === view.hypothesis.id },
                ]"
                :aria-pressed="activeHypothesisId === view.hypothesis.id"
                @click="selectHypothesis(view.hypothesis.id, true)"
              >
                <span class="wb__hypothesis-top">
                  <span class="wb__hypothesis-number num">{{ String(view.index + 1).padStart(2, "0") }}</span>
                  <span class="wb__hypothesis-title">{{ view.hypothesis.title }}</span>
                  <span class="wb__hypothesis-arrow" aria-hidden="true">→</span>
                </span>
                <span class="status-pill" :class="STATUS_META[view.status].cls">
                  {{ STATUS_META[view.status].label }}
                </span>
                <span class="wb__hypothesis-counts num">
                  {{ view.supportCount }} 支持 · {{ view.opposeCount }} 反对 · {{ view.missingCount }} 语境
                </span>
              </button>
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

              <details v-if="(grouped?.unmatched.length ?? 0) > 0" class="hypo hypo--unmatched wb__supplement">
                <summary class="hypo__head">
                  <h3 class="hypo__title">未归属证据</h3>
                  <span class="status-pill status--info num">{{ grouped!.unmatched.length }} 张</span>
                  <span class="unmatched__hint">需人工复核，不参与状态判定</span>
                  <span class="unmatched__toggle" aria-hidden="true"></span>
                </summary>
                <p class="hypo__probe">
                  以下证据未命中三条假设的归属关键词，绝不静默丢弃；多为 L3 背景语境，不参与状态判定。
                </p>
                <EvidenceCardView v-for="(card, index) in grouped!.unmatched" :key="index" :card="card" />
              </details>

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

              <QuestionsColumn :questions="envelope.questions" />

              <section class="wb__action-checklist">
                <div class="wb__action-heading">
                  <h3>下一步行动</h3>
                  <span class="num">{{ completedActionCount }} / {{ actionItems.length }}</span>
                </div>
                <label v-for="(item, index) in actionItems" :key="item" class="wb__action-check">
                  <input v-model="checkedActions[actionKey(index)]" type="checkbox" />
                  <span>{{ item }}</span>
                </label>
                <p class="wb__action-hint">勾选仅用于当前页面的执行记录。</p>
              </section>

              <button type="button" class="btn btn--ghost btn--sm wb__copy" @click="copyPlan">
                复制完整验证计划
              </button>
              <p v-if="copyFeedback" class="wb__copy-feedback" role="status">{{ copyFeedback }}</p>
            </div>
          </aside>
        </div>

        <WorkbenchTour v-if="tourStep !== null" :step="tourStep" @next="advanceTour" @skip="finishTour" />

        <div v-if="envelope.l2Cards.length || envelope.l2Notice" class="appendix wb__appendix">
          <details class="l2zone">
            <summary class="wb__l2-summary">
              <span>中文侧经验（L2 · 知乎）</span>
              <span>不参与偏好判定</span>
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
