<script setup lang="ts">
/**
 * 卖点验证工作台 —— 证据对照工作区（产品核心页）。
 * 主题场景：旅行收纳包 → 德国市场。
 *
 * 布局（2026-11-22 工作台改版，见 main.css tokens 注释）：
 *   外壳    AppShell（侧栏导航 + 面包屑顶栏）
 *   工具行  场景切换 + 产品×市场检索
 *   判定带  深色仪表带：总体结论 + 可追溯小字，第一眼可见；数据源/模式/时间进侧栏底部
 *   主体    证据分节面板（节头 + 统计瓦片 + 支持/反对左右对照）+ 未归属（默认收起）
 *   附录    中文侧经验（L2 · 知乎）+ 待验证问题
 *
 * URL 参数 ?scenario=real|conflict|limited 可直达指定场景（便于演示与验收）。
 */
import { SCENARIOS, loadEvidenceEnvelope, DECISION_LABEL } from "../composables/useEvidence"
import type { ScenarioId, EvidenceEnvelope } from "../composables/useEvidence"
import { HYPOTHESES, groupCardsByHypothesis, STATUS_META } from "../utils/hypotheses"
import type { HypothesisStatus } from "../utils/hypotheses"

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

/** 证据卡按假设分组（支持/反对/缺失）+ 未归属组 */
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

/** 假设导航状态点样式 */
const DOT_CLS: Record<HypothesisStatus, string> = {
  support: "side__hypodot--ok",
  conflict: "side__hypodot--bad",
  insufficient: "side__hypodot--warn",
}
const dotCls = (id: string): string => DOT_CLS[leftStatuses.value[id] ?? "insufficient"]

/** 侧栏「本次验证」结论卡的语义类 */
const verdictCls = computed(() => {
  const s = envelope.value?.stance
  if (s === "conflicting" || s === "refuted") return "verdict--bad"
  if (s === "supported") return "verdict--ok"
  return "verdict--warn"
})

/** 生成时间（截到秒） */
const generatedShort = computed(() => {
  const raw = envelope.value?.generated_at ?? ""
  return raw ? raw.split(".")[0].replace("T", " ").replace("Z", " UTC") : ""
})

/** 演示场景下，返回的卡片（含知乎 L2 卡）是否含演示数据（供侧栏页面级合规提示） */
const hasDemoCards = computed(() =>
  [...(envelope.value?.cards ?? []), ...(envelope.value?.l2Cards ?? [])].some(
    (c) => c.is_demo_data,
  ),
)

const activeLabel = (id: ScenarioId) => (scenario.value === id ? "active" : "")

useHead({ title: "卖点验证工作台 · CrossPilot 2.0" })
</script>

<template>
  <AppShell crumb="卖点验证工作台">
    <!-- 侧栏扩展：本次验证结论 + 假设锚点导航 + 页面级合规提示 + 数据源 meta -->
    <template #sidebar>
      <div v-if="envelope" class="side__block">
        <p class="side__label side__label--flush">本次验证</p>
        <div class="verdict" :class="verdictCls">
          <span class="verdict__dot" aria-hidden="true"></span>
          <p class="verdict__label">{{ DECISION_LABEL[envelope.stance] }}</p>
        </div>
        <p class="verdict__trace num">
          极性样本 {{ envelope.decision?.n_polarized ?? "—" }} · 门禁 {{ envelope.decision?.gate_status || "—" }}
        </p>
        <nav class="side__hypnav" aria-label="假设导航">
          <a
            v-for="h in HYPOTHESES"
            :key="h.id"
            class="side__hypitem"
            :href="`#hypo-${h.id}`"
          >
            <span class="side__hypodot" :class="dotCls(h.id)" aria-hidden="true"></span>
            <span class="side__hyptext">
              <span class="side__hypotitle">{{ h.title }}</span>
              <span class="side__hypoprobe">{{ h.probe }}</span>
            </span>
          </a>
        </nav>
      </div>

      <p v-if="hasDemoCards" class="side__demo-hint">
        本页含演示数据卡（斜纹底 + 角标）：演示数据：模拟回填，非真实德国消费者反馈；与真实反馈分组呈现，绝不混排。
      </p>

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
      <!-- 工具行：场景切换 + 检索 -->
      <div class="wb__toolbar">
        <nav class="wb__scenarios" aria-label="场景切换">
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
        <form class="wb__search" @submit.prevent="submitSearch">
          <label class="wb__field">
            <span class="wb__label">产品</span>
            <input v-model="productInput" type="text" class="wb__input" />
          </label>
          <span class="wb__x" aria-hidden="true">×</span>
          <label class="wb__field">
            <span class="wb__label">市场</span>
            <input v-model="marketInput" type="text" class="wb__input wb__input--market" />
          </label>
          <button type="submit" class="btn btn--primary btn--sm">检索证据</button>
        </form>
      </div>

      <!-- 加载/错误状态 -->
      <div v-if="pending" class="statebox">正在加载证据…</div>
      <div v-else-if="error" class="statebox statebox--error">
        <p>证据加载失败：{{ (error as Error).message }}</p>
        <button type="button" class="btn btn--primary btn--sm" @click="refresh()">重试</button>
      </div>

      <template v-else-if="envelope">
        <!-- 状态横幅：当前场景总体结论，第一眼可见（数据模式/来源/时间在侧栏 meta） -->
        <StanceBanner
          :stance="envelope.stance"
          :decision="envelope.decision"
          :scenario="scenario"
          :query="envelope.query || searchQuery"
        />

        <p v-if="envelope.invalidCards.length" class="invalid-banner">
          契约提示：本次返回有 {{ envelope.invalidCards.length }} 张证据卡缺少必现字段，已按契约拒绝渲染（见下方占位说明）。
        </p>

        <!-- 证据分节 -->
        <HypothesisEvidence
          v-for="g in grouped?.groups ?? []"
          :key="g.hypothesis.id"
          :group="g"
        />

        <!-- 未归属证据：关键词未命中任何假设的卡，人工复核，绝不静默丢弃（默认收起） -->
        <details v-if="(grouped?.unmatched.length ?? 0) > 0" class="hypo hypo--unmatched">
          <summary class="hypo__head">
            <h3 class="hypo__title">未归属证据</h3>
            <span class="status-pill status--info num">{{ grouped!.unmatched.length }} 张</span>
            <span class="unmatched__hint">多为 L3 背景语境，不参与状态判定，需人工复核</span>
            <span class="unmatched__toggle" aria-hidden="true"></span>
          </summary>
          <p class="hypo__probe">
            以下证据未命中三条假设的归属关键词（多为 L3 背景语境），不参与状态判定，需人工复核。
          </p>
          <EvidenceCardView v-for="(c, i) in grouped!.unmatched" :key="i" :card="c" />
        </details>

        <!-- 契约校验占位说明：缺字段卡不渲染 -->
        <section v-if="envelope.invalidCards.length" class="hypo hypo--invalid">
          <header class="hypo__head">
            <h3 class="hypo__title">契约校验未通过 · 占位说明</h3>
          </header>
          <InvalidCardNotice v-for="(inv, i) in envelope.invalidCards" :key="i" :invalid="inv" />
        </section>

        <!-- 附录：中文侧经验（L2）+ 待验证问题与测试建议 -->
        <div class="appendix" :class="{ 'appendix--solo': !(envelope.l2Cards.length || envelope.l2Notice) }">
          <section v-if="envelope.l2Cards.length || envelope.l2Notice" class="l2zone">
            <h2 class="qcol__heading">中文侧经验（L2 · 知乎）</h2>
            <p class="qcol__hint">
              中文从业者经验只产出待验证问题，不构成支持/反对。
            </p>
            <p v-if="envelope.l2Notice" class="l2zone__notice">{{ envelope.l2Notice }}</p>
            <p v-else-if="envelope.l2InvalidCards.length" class="l2zone__notice">
              知乎侧有 {{ envelope.l2InvalidCards.length }} 张卡缺少必现字段，已按契约拒绝渲染。
            </p>
            <EvidenceCardView v-for="(c, i) in envelope.l2Cards" :key="i" :card="c" />
          </section>
          <QuestionsColumn :questions="envelope.questions" />
        </div>

        <footer class="footer">
          <span>固定演示边界：非电器旅行收纳包 → 德国市场 → 详情页首屏卖点验证（方案 4.1）</span>
          <span class="num">market={{ envelope.market }} · scenario={{ envelope.scenario }} · data_mode={{ envelope.data_mode }}</span>
        </footer>
      </template>
    </div>
  </AppShell>
</template>
