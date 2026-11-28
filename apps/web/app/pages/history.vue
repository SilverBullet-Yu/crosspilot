<script setup lang="ts">
import {
  canConfirmOperatorTrial,
  emptyOperatorTrial,
  hasOperatorTrialContent,
  missingOperatorTrialFields,
  normalizeOperatorTrialRecord,
} from "../utils/operator-trial"
import {
  DECISION_OPTIONS,
  VALIDATION_ROUNDS_KEY,
  normalizeValidationRounds,
} from "../utils/validation-round"
import type { ValidationRound } from "../utils/validation-round"

type ReadinessLevel = "blocked" | "exploratory" | "decision_ready" | "trial_complete"
type ReadinessCheckStatus = "pass" | "pending" | "fail"

interface ReadinessCheck {
  id: string
  label: string
  status: ReadinessCheckStatus
  detail: string
}

interface ClaimReadiness {
  claim_id: string
  state: string
  n_l1: number
  n_polarized: number
  review_pending: number
  confirmed_rounds: number
}

interface CaseReadiness {
  query: string
  market: string
  level: ReadinessLevel
  summary: string
  checks: ReadinessCheck[]
  claims: ClaimReadiness[]
  next_actions: string[]
  confirmed_rounds: number
  market_effect_claim_allowed: boolean
  snapshot_sha256: string | null
  rounds_archive_sha256: string | null
}

const READINESS_LABELS: Record<ReadinessLevel, string> = {
  blocked: "真实案例被阻塞",
  exploratory: "探索性样本",
  decision_ready: "样本可决策",
  trial_complete: "真实案例与试用闭环完成",
}

const READINESS_STATUS_LABELS: Record<ReadinessCheckStatus, string> = {
  pass: "通过",
  pending: "待完成",
  fail: "阻塞",
}

useHead({ title: "历史验证项目 · CrossPilot 2.0" })

const STORAGE_KEY = "crosspilot.operator-trial.v1"
const record = ref(emptyOperatorTrial())
const feedback = ref("")
const rounds = ref<ValidationRound[]>([])
const roundFeedback = ref("")
const readiness = ref<CaseReadiness | null>(null)
const readinessLoading = ref(false)
const readinessFeedback = ref("")
const readinessClaimIds = ref("")
const apiBase = String(useRuntimeConfig().public.apiBase ?? "").replace(/\/$/, "")
const apiConfigured = computed(() => Boolean(apiBase) && apiBase !== "fixtures")
const missingFields = computed(() => missingOperatorTrialFields(record.value))
const isConfirmed = computed(
  () => record.value.confirmation === "confirmed" && canConfirmOperatorTrial(record.value),
)

onMounted(async () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) record.value = normalizeOperatorTrialRecord(JSON.parse(saved))
  } catch {
    feedback.value = "本地记录读取失败，可重新填写"
  }
  try {
    rounds.value = normalizeValidationRounds(JSON.parse(localStorage.getItem(VALIDATION_ROUNDS_KEY) ?? "[]"))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  } catch {
    rounds.value = []
  }
  try {
    const workspace = JSON.parse(
      localStorage.getItem("crosspilot.workbench.real.旅行收纳包") ?? "{}",
    ) as { hypotheses?: Array<{ id?: unknown }> }
    if (Array.isArray(workspace.hypotheses)) {
      readinessClaimIds.value = workspace.hypotheses
        .map((item) => item.id)
        .filter((id): id is string => typeof id === "string" && /^[a-z0-9][a-z0-9_-]{0,63}$/.test(id))
        .join(", ")
    }
  } catch {
    readinessClaimIds.value = ""
  }
  await loadReadiness()
})

async function loadReadiness() {
  if (!apiConfigured.value) return
  readinessLoading.value = true
  readinessFeedback.value = ""
  try {
    const params = new URLSearchParams({ query: "旅行收纳包" })
    for (const claimId of readinessClaimIds.value.split(/[,，\n]/)) {
      if (claimId.trim()) params.append("claim_id", claimId.trim())
    }
    const response = await fetch(`${apiBase}/api/case/readiness?${params.toString()}`)
    if (!response.ok) {
      throw new Error(
        response.status === 409
          ? "真实案例审计数据损坏，请检查 L1 快照或轮次归档"
          : `真实案例审计读取失败（HTTP ${response.status}）`,
      )
    }
    const payload = await response.json() as CaseReadiness
    if (
      !["blocked", "exploratory", "decision_ready", "trial_complete"].includes(payload.level) ||
      (payload.snapshot_sha256 !== null && !/^[0-9a-f]{64}$/.test(payload.snapshot_sha256)) ||
      (payload.rounds_archive_sha256 !== null && !/^[0-9a-f]{64}$/.test(payload.rounds_archive_sha256)) ||
      !Array.isArray(payload.checks) ||
      !Array.isArray(payload.claims) ||
      !Array.isArray(payload.next_actions)
    ) {
      throw new Error("真实案例审计响应格式不正确")
    }
    readiness.value = payload
  } catch (error) {
    readiness.value = null
    readinessFeedback.value = error instanceof Error ? error.message : "真实案例审计读取失败"
  } finally {
    readinessLoading.value = false
  }
}

function saveRecord() {
  if (record.value.confirmation === "confirmed" && !canConfirmOperatorTrial(record.value)) {
    feedback.value = `还不能标记运营已确认，缺少：${missingFields.value.join("、")}`
    return
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(record.value))
    feedback.value = "已保存到本地浏览器，未上传"
  } catch {
    feedback.value = "保存失败，请使用导出 JSON"
  }
}

function exportRecord() {
  if (!hasOperatorTrialContent(record.value)) {
    feedback.value = "请先填写试用记录，再导出 JSON"
    return
  }
  if (record.value.confirmation === "confirmed" && !canConfirmOperatorTrial(record.value)) {
    feedback.value = `不完整记录不能导出为已确认，缺少：${missingFields.value.join("、")}`
    return
  }
  const blob = new Blob([JSON.stringify(record.value, null, 2)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = isConfirmed.value
    ? "crosspilot-operator-trial.json"
    : record.value.isDemo
      ? "crosspilot-operator-trial-demo-draft.json"
      : "crosspilot-operator-trial-draft.json"
  link.click()
  URL.revokeObjectURL(url)
  feedback.value = isConfirmed.value
    ? "已导出运营已确认记录"
    : `已导出待确认草稿；仍缺：${missingFields.value.join("、") || "运营确认"}`
}

function decisionLabel(round: ValidationRound): string {
  return DECISION_OPTIONS.find((option) => option.value === round.decision)?.label ?? "待决定"
}

function useRound(round: ValidationRound) {
  record.value = {
    trialDate: round.createdAt.slice(0, 10),
    operatorRole: round.owner || "待填写",
    productMarket: `${round.query} × 德国`,
    evidenceRefs: round.evidenceRefs.startsWith(`claim_id=${round.claimId}`)
      ? round.evidenceRefs
      : `claim_id=${round.claimId}; ${round.evidenceRefs}`,
    decision: `${decisionLabel(round)}：${round.rationale || "待补充理由"}`,
    prototypeObservation: round.observation || "待补充观察",
    nextAction: `${round.nextAction || "待补充下一步"}${round.owner ? `（${round.owner}）` : ""}`,
    confirmation: "pending",
    sourceScenario: round.scenario,
    sourceRoundId: round.id,
    isDemo: round.scenario !== "real",
  }
  feedback.value = record.value.isDemo
    ? "已填入演示轮次草稿；演示来源不得标记为真人运营确认"
    : "已填入上方试用总结；请补齐运营角色并重新确认"
  document.getElementById("trial-title")?.scrollIntoView({ behavior: "smooth", block: "start" })
}

function exportRounds() {
  if (!rounds.value.length) {
    roundFeedback.value = "当前没有可导出的验证轮次"
    return
  }
  const blob = new Blob([
    JSON.stringify({ schema_version: 1, source: "crosspilot_validation_rounds", rounds: rounds.value }, null, 2),
  ], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "crosspilot-validation-rounds.json"
  link.click()
  URL.revokeObjectURL(url)
  roundFeedback.value = `已导出 ${rounds.value.length} 轮验证记录`
}

function clearRecord() {
  record.value = emptyOperatorTrial()
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    feedback.value = "本地记录已清空"
    return
  }
  feedback.value = "本地记录已清空"
}
</script>

<template>
  <AppShell crumb="历史验证项目">
    <div class="history">
      <section class="history__panel">
        <h1 class="history__title">服务端历史项目尚未启用</h1>
        <p class="history__body">
          演示构建不做服务端持久化。下方保留本机验证轮次与运营试用总结，不虚构服务端历史项目。
        </p>
        <NuxtLink to="/workbench" class="btn btn--primary">去发起一次验证 →</NuxtLink>
      </section>

      <section class="trial trial--readiness" aria-labelledby="readiness-title">
        <header class="trial__header">
          <div>
            <p class="trial__eyebrow">真实案例 · 服务端门禁</p>
            <h2 id="readiness-title">完成状态审计</h2>
          </div>
          <span
            v-if="readiness"
            class="trial__badge"
            :class="readiness.level === 'trial_complete' ? 'status--ok' : 'status--warn'"
          >
            {{ READINESS_LABELS[readiness.level] }}
          </span>
        </header>
        <p class="trial__hint">
          只审计授权德国 L1、逐条出处、人工复核、样本门禁与 real 场景运营轮次；轮次须引用同卖点真实 review_id + source_url，并绑定当前 L1 snapshot_sha256。审计结果同时绑定 L1 snapshot_sha256 与轮次归档 rounds_archive_sha256，演示评论和演示轮次不计入真实案例完成。
        </p>
        <label class="trial__field readiness__scope">
          <span>审计卖点（逗号分隔，留空=全部）</span>
          <input v-model="readinessClaimIds" placeholder="capacity, features, price 或自定义 claim_id" />
        </label>
        <p v-if="!apiConfigured" class="trial__empty">
          当前为 fixtures 演示模式，未读取服务端真实案例门禁。配置 NUXT_PUBLIC_API_BASE 后可查看真实审计结果。
        </p>
        <p v-else-if="readinessLoading" class="trial__empty" role="status">正在读取真实案例审计…</p>
        <p v-else-if="readinessFeedback" class="trial__feedback" role="alert">{{ readinessFeedback }}</p>
        <template v-else-if="readiness">
          <p class="readiness__summary">{{ readiness.summary }}</p>
          <p v-if="readiness.snapshot_sha256" class="trial__hint">
            审计依据快照：<span class="num">{{ readiness.snapshot_sha256 }}</span>
          </p>
          <p v-else class="trial__hint">当前未加载已验证 L1 快照，审计结论不绑定具体证据版本。</p>
          <p v-if="readiness.rounds_archive_sha256" class="trial__hint">
            运营轮次归档：<span class="num">{{ readiness.rounds_archive_sha256 }}</span>
          </p>
          <p v-else class="trial__hint">当前无已验证运营轮次归档。</p>
          <ul class="readiness__checks">
            <li
              v-for="check in readiness.checks"
              :key="check.id"
              class="readiness__check"
              :class="`readiness__check--${check.status}`"
            >
              <strong>{{ READINESS_STATUS_LABELS[check.status] }} · {{ check.label }}</strong>
              <span>{{ check.detail }}</span>
            </li>
          </ul>
          <div class="readiness__claims" aria-label="逐卖点审计">
            <article v-for="claim in readiness.claims" :key="claim.claim_id">
              <strong>{{ claim.claim_id }}</strong>
              <span>L1 {{ claim.n_l1 }} · 极性 n={{ claim.n_polarized }} · 待复核 {{ claim.review_pending }} · 已确认 {{ claim.confirmed_rounds }}</span>
            </article>
          </div>
          <h3 class="readiness__subtitle">下一步</h3>
          <ol class="readiness__actions">
            <li v-for="action in readiness.next_actions" :key="action">{{ action }}</li>
          </ol>
          <p class="readiness__boundary">即使达到 trial_complete，也不得把当前样本外推为总体消费者偏好或市场效果。</p>
        </template>
        <div v-if="apiConfigured" class="trial__actions">
          <button type="button" class="btn btn--ghost btn--sm" :disabled="readinessLoading" @click="loadReadiness">
            重新读取审计
          </button>
        </div>
      </section>

      <section class="trial trial--rounds" aria-labelledby="rounds-title">
        <header class="trial__header">
          <div>
            <p class="trial__eyebrow">本地轮次 · 不覆盖旧记录</p>
            <h2 id="rounds-title">验证轮次</h2>
          </div>
          <span class="trial__badge">{{ rounds.length }} 轮</span>
        </header>
        <p class="trial__hint">
          从工作台按假设追加的观察、决定与下一步。轮次可回看和导出；填入下方总结后仍需人工确认，未确认轮次不代表真人试用完成。
        </p>
        <div v-if="rounds.length" class="trial__round-list">
          <article v-for="round in rounds" :key="round.id" class="trial__round">
            <header>
              <span class="num">{{ round.createdAt.replace("T", " ").slice(0, 16) }} · {{ round.scenario }}</span>
              <span class="status-pill" :class="round.confirmation === 'confirmed' ? 'status--ok' : 'status--warn'">
                {{ round.confirmation === "confirmed" ? "运营已确认" : "待确认" }}
              </span>
            </header>
            <h3>{{ round.hypothesisTitle }} <small>{{ round.claimId }}</small></h3>
            <p><strong>{{ decisionLabel(round) }}</strong> · {{ round.rationale || "待补充理由" }}</p>
            <p>{{ round.observation || "待补充观察" }}</p>
            <details v-if="round.prototype" class="trial__prototype">
              <summary>原型测试结构化记录</summary>
              <p>参与者：{{ round.prototype.participantCode }}；顺序：{{ round.prototype.order === "multi_first" ? "多隔层优先" : "开放空间优先" }}</p>
              <p><strong>装什么：</strong>{{ round.prototype.itemsLoaded }}</p>
              <p><strong>怎么取：</strong>{{ round.prototype.retrieval }}</p>
              <p><strong>哪里麻烦：</strong>{{ round.prototype.friction }}</p>
            </details>
            <p v-if="round.nextAction"><strong>下一步：</strong>{{ round.nextAction }}{{ round.owner ? `（${round.owner}）` : "" }}</p>
            <details>
              <summary>证据依据</summary>
              <p>{{ round.evidenceRefs }}</p>
            </details>
            <button type="button" class="btn btn--ghost btn--sm" @click="useRound(round)">填入下方试用总结</button>
          </article>
        </div>
        <p v-else class="trial__empty">暂无验证轮次；请先在工作台记录一次假设验证。</p>
        <div class="trial__actions">
          <button type="button" class="btn btn--ghost btn--sm" @click="exportRounds">导出全部轮次 JSON</button>
        </div>
        <p v-if="roundFeedback" class="trial__feedback" role="status">{{ roundFeedback }}</p>
      </section>

      <section class="trial" aria-labelledby="trial-title">
        <header class="trial__header">
          <div>
            <p class="trial__eyebrow">本地记录 · 不上传</p>
            <h2 id="trial-title">运营试用记录</h2>
          </div>
          <span class="trial__badge">{{ isConfirmed ? "运营已确认" : "待人工确认" }}</span>
        </header>
        <p class="trial__hint">
          记录运营角色、证据依据与最终决定。不要填写评论作者姓名、邮箱或其他个人信息；本地保存不等于已完成真人试用。完整填写后方可标记「运营已确认」，不完整记录只能导出为待确认草稿。
        </p>
        <p v-if="record.sourceRoundId" class="trial__hint">
          来源轮次：<span class="num">{{ record.sourceRoundId }}</span> · 场景 {{ record.sourceScenario || "未记录" }}
        </p>
        <p v-if="record.isDemo" class="trial__feedback" role="alert">
          当前记录来自演示轮次，只能导出为演示草稿，不得标记为真人运营确认。
        </p>
        <div class="trial__grid">
          <label class="trial__field">
            <span>试用日期</span>
            <input v-model="record.trialDate" type="date" />
          </label>
          <label class="trial__field">
            <span>运营角色</span>
            <input v-model="record.operatorRole" type="text" placeholder="如：德国站品牌运营" />
          </label>
          <label class="trial__field trial__field--wide">
            <span>真实商品与市场</span>
            <input v-model="record.productMarket" type="text" />
          </label>
          <label class="trial__field trial__field--wide">
            <span>依据哪些证据 ID / 链接</span>
            <textarea v-model="record.evidenceRefs" rows="3" placeholder="填写工作台中的 claim_id、review_id 或来源链接" />
          </label>
          <label class="trial__field trial__field--wide">
            <span>运营决定</span>
            <textarea v-model="record.decision" rows="3" placeholder="保留、修改或暂停哪个卖点？为什么？" />
          </label>
          <label class="trial__field trial__field--wide">
            <span>原型测试观察</span>
            <textarea v-model="record.prototypeObservation" rows="4" placeholder="记录装什么、怎么取、哪里麻烦，以及两种原型的差异" />
          </label>
          <label class="trial__field trial__field--wide">
            <span>下一步与负责人</span>
            <textarea v-model="record.nextAction" rows="3" />
          </label>
          <label class="trial__field">
            <span>确认状态</span>
            <select v-model="record.confirmation">
              <option value="pending">待确认</option>
              <option value="confirmed">运营已确认</option>
            </select>
          </label>
        </div>
        <div class="trial__actions">
          <button type="button" class="btn btn--primary" @click="saveRecord">保存本地记录</button>
          <button type="button" class="btn btn--ghost" @click="exportRecord">导出 JSON</button>
          <button type="button" class="btn btn--ghost" @click="clearRecord">清空</button>
        </div>
        <p v-if="feedback" class="trial__feedback" role="status">{{ feedback }}</p>
      </section>
    </div>
  </AppShell>
</template>
