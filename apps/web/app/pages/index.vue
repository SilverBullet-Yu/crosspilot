<script setup lang="ts">
/**
 * CrossPilot 2.0 —— 三栏证据对照单页（产品核心一屏）。
 * 主题场景：旅行收纳包 → 德国市场。
 *
 * 布局：
 *   顶栏    产品×市场输入 + 数据模式徽标 + 场景切换（真实快照 / 演示·证据冲突 / 演示·有限支持）
 *   状态横幅 当前场景总体结论（缺少有效数据 / 证据相互冲突 / 已有有限支持），第一眼可见
 *   三栏    左：企业假设（3 条预置，方案 4.3）｜中：证据对照（支持/相反/缺失三组）｜右：待验证问题
 *
 * URL 参数 ?scenario=real|conflict|limited 可直达指定场景（便于演示与验收）。
 */
import { SCENARIOS, loadEvidenceEnvelope } from "../composables/useEvidence"
import type { ScenarioId, EvidenceEnvelope } from "../composables/useEvidence"
import { HYPOTHESES, groupCardsByHypothesis, STATUS_META } from "../utils/hypotheses"
import type { HypothesisStatus } from "../utils/hypotheses"
import type { EvidenceStance } from "../utils/evidence-schema"

const route = useRoute()
const router = useRouter()

const config = useRuntimeConfig()
// NUXT_PUBLIC_API_BASE：空或 "fixtures" → 本地夹具；URL → 真实后端
const apiBase = String(config.public.apiBase ?? "fixtures")

const productInput = ref("旅行收纳包")
const marketInput = ref("德国")
const searchQuery = ref("旅行收纳包")

const scenario = computed<ScenarioId>(() => {
  const s = String(route.query.scenario ?? "real")
  return s === "conflict" || s === "limited" ? s : "real"
})

const { data, pending, error, refresh } = await useAsyncData<EvidenceEnvelope>(
  "evidence",
  () => loadEvidenceEnvelope(scenario.value, searchQuery.value, apiBase),
  { watch: [scenario, searchQuery] },
)

/** 切换场景：写回 URL（可分享、可被 curl 带 SSR 数据验证） */
function switchScenario(id: ScenarioId) {
  router.replace({ query: { ...route.query, scenario: id } })
}

/** 检索按钮：以产品输入词重新拉取真实快照场景 */
function submitSearch() {
  searchQuery.value = productInput.value.trim() || "旅行收纳包"
}

const envelope = computed(() => data.value ?? null)

/** 中栏：合法证据卡按假设分组（支持/相反/缺失）+ 未归属组 */
const grouped = computed(() =>
  envelope.value ? groupCardsByHypothesis(envelope.value.cards) : null,
)

/** 左栏：每条假设的状态（镜像 domain/evidence.py 的 resolve_stance，仅 L1 计入） */
const leftStatuses = computed<Record<string, HypothesisStatus>>(() => {
  const map: Record<string, HypothesisStatus> = {}
  for (const g of grouped.value?.groups ?? []) {
    map[g.hypothesis.id] = g.status
  }
  return map
})

function leftClass(id: string): string {
  const s = leftStatuses.value[id] ?? "insufficient"
  return STATUS_META[s].cls
}

function leftLabel(id: string): string {
  const s = leftStatuses.value[id] ?? "insufficient"
  return STATUS_META[s].label
}

/** 演示场景下，真实 API/夹具返回的卡片（含知乎 L2 卡）是否含演示数据（供顶栏提示） */
const hasDemoCards = computed(() =>
  [...(envelope.value?.cards ?? []), ...(envelope.value?.l2Cards ?? [])].some(
    (c) => c.is_demo_data,
  ),
)

const scenarioMeta = computed(
  () => SCENARIOS.find((s) => s.id === scenario.value) ?? SCENARIOS[0],
)

const activeLabel = (id: ScenarioId) => (scenario.value === id ? "active" : "")
</script>

<template>
  <div class="page">
    <!-- 顶栏 -->
    <header class="topbar">
      <div class="topbar__brand">
        <span class="topbar__logo">CrossPilot 2.0</span>
        <span class="topbar__tagline">跨境消费者认知差验证</span>
      </div>
      <form class="topbar__form" @submit.prevent="submitSearch">
        <label class="topbar__field">
          <span class="topbar__label">产品</span>
          <input v-model="productInput" type="text" class="topbar__input" />
        </label>
        <span class="topbar__x">×</span>
        <label class="topbar__field">
          <span class="topbar__label">市场</span>
          <input v-model="marketInput" type="text" class="topbar__input topbar__input--market" />
        </label>
        <button type="submit" class="topbar__search">检索证据</button>
        <span class="topbar__source">
          数据源：{{ envelope?.dataSource ?? (apiBase === 'fixtures' || apiBase === '' ? '本地 fixtures' : `真实 API（${apiBase}）`) }}
        </span>
      </form>
      <nav class="topbar__scenarios" aria-label="场景切换">
        <button
          v-for="s in SCENARIOS"
          :key="s.id"
          type="button"
          class="scenario-btn"
          :class="[activeLabel(s.id), { 'scenario-btn--demo': s.demo }]"
          @click="switchScenario(s.id)"
        >
          {{ s.label }}
        </button>
      </nav>
    </header>

    <!-- 加载/错误状态 -->
    <div v-if="pending" class="statebox">正在加载证据…</div>
    <div v-else-if="error" class="statebox statebox--error">
      <p>证据加载失败：{{ (error as Error).message }}</p>
      <button type="button" class="topbar__search" @click="refresh()">重试</button>
    </div>

    <template v-else-if="envelope">
      <!-- 状态横幅：当前场景总体结论，第一眼可见 -->
      <StanceBanner
        :stance="envelope.stance as EvidenceStance"
        :scenario="scenario"
        :query="envelope.query || searchQuery"
        :market="marketInput"
        :data-mode="envelope.data_mode"
        :generated-at="envelope.generated_at"
        :data-source="envelope.dataSource"
      />

      <p v-if="envelope.invalidCards.length" class="invalid-banner">
        契约提示：本次返回有 {{ envelope.invalidCards.length }} 张证据卡缺少必现字段，已按契约拒绝渲染（见中栏底部占位说明）。
      </p>

      <!-- 三栏主体 -->
      <main class="columns">
        <!-- 左栏：企业假设 -->
        <section class="col col--left">
          <h2 class="col__heading">企业假设</h2>
          <p class="col__hint">预置 3 条（方案 4.3）· 状态由对照结果实时判定</p>
          <article
            v-for="h in HYPOTHESES"
            :key="h.id"
            class="hypocard"
            :class="leftClass(h.id)"
          >
            <p class="hypocard__title">{{ h.title }}</p>
            <span class="status-pill" :class="leftClass(h.id)">{{ leftLabel(h.id) }}</span>
            <p class="hypocard__probe">{{ h.probe }}</p>
          </article>
          <p v-if="hasDemoCards" class="hypocard__demo-hint">
            本页含「演示数据」卡片：整卡斜纹边框 + 角标，与真实反馈分组呈现，绝不混排。
          </p>
        </section>

        <!-- 中栏：证据对照 -->
        <section class="col col--mid">
          <h2 class="col__heading">证据对照</h2>
          <p class="col__hint">
            每条假设按 支持证据 / 相反证据 / 缺失证据 三组对照；证据卡渲染契约六必现字段。
          </p>
          <HypothesisEvidence
            v-for="g in grouped?.groups ?? []"
            :key="g.hypothesis.id"
            :group="g"
          />

          <!-- 未归属证据：关键词未命中任何假设的卡，人工复核，绝不静默丢弃 -->
          <section v-if="(grouped?.unmatched.length ?? 0) > 0" class="hypo hypo--unmatched">
            <header class="hypo__head">
              <h3 class="hypo__title">未归属证据</h3>
              <span class="status-pill status--info">{{ grouped!.unmatched.length }} 张</span>
            </header>
            <p class="hypo__probe">
              以下证据未命中三条假设的归属关键词（多为 L3 背景语境），不参与状态判定，需人工复核。
            </p>
            <EvidenceCardView v-for="(c, i) in grouped!.unmatched" :key="i" :card="c" />
          </section>

          <!-- 契约校验占位说明：缺字段卡不渲染 -->
          <section v-if="envelope.invalidCards.length" class="hypo hypo--invalid">
            <header class="hypo__head">
              <h3 class="hypo__title">契约校验未通过 · 占位说明</h3>
            </header>
            <InvalidCardNotice v-for="(inv, i) in envelope.invalidCards" :key="i" :invalid="inv" />
          </section>
        </section>

        <!-- 右栏：中文侧经验（L2）+ 待验证问题与测试建议 -->
        <div class="col col--right">
          <section v-if="envelope.l2Cards.length || envelope.l2Notice" class="l2zone">
            <h2 class="col__heading">中文侧经验（L2 · 知乎）</h2>
            <p class="col__hint">
              中文从业者经验只产出待验证问题，不构成支持/反对（硬约束 1）。
            </p>
            <p v-if="envelope.l2Notice" class="l2zone__notice">{{ envelope.l2Notice }}</p>
            <p v-else-if="envelope.l2InvalidCards.length" class="l2zone__notice">
              知乎侧有 {{ envelope.l2InvalidCards.length }} 张卡缺少必现字段，已按契约拒绝渲染。
            </p>
            <EvidenceCardView v-for="(c, i) in envelope.l2Cards" :key="i" :card="c" />
          </section>
          <QuestionsColumn :questions="envelope.questions" />
        </div>
      </main>

      <footer class="footer">
        <span>固定演示边界：非电器旅行收纳包 → 德国市场 → 详情页首屏卖点验证（方案 4.1）</span>
        <span>market={{ envelope.market }} · scenario={{ envelope.scenario }} · data_mode={{ envelope.data_mode }}</span>
      </footer>
    </template>
  </div>
</template>
