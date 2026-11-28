/**
 * 证据数据加载：fixtures / 真实 API 双模式。
 *
 * 后端契约（执行者A，字段名不得偏离）：
 *   GET /api/evidence?query=<关键词>       → 真实快照场景（scenario="real"）
 *   GET /api/evidence/demo?scenario=conflict|limited → 演示场景
 * 包络：{ query, market, data_mode, scenario, stance, cards, questions, generated_at,
 *         decision, claim_decisions, l1_notice?, l2_cards?, l2_notice? }
 * claim_decisions 按 claim_id 独立判定；questions 为 {text, source}[]；
 * l2_* 为知乎侧 L2 卡与降级提示（demo 也返回全部模拟的 L2 卡）。
 *
 * NUXT_PUBLIC_API_BASE 环境变量切换数据源（nuxt.config.ts 注入 runtimeConfig.public.apiBase）：
 *   - 空值或 "fixtures" → 读本地夹具 apps/web/fixtures/（三场景各一份，字段严格按包络）
 *   - URL（如 http://localhost:8000）→ 调真实 FastAPI
 */
import realFixture from "../../fixtures/evidence_real.json"
import conflictFixture from "../../fixtures/evidence_conflict.json"
import limitedFixture from "../../fixtures/evidence_limited.json"
import { validateEvidenceCard } from "../utils/evidence-schema"
import type { DecisionState, ValidEvidenceCard, InvalidEvidenceCard } from "../utils/evidence-schema"

export type ScenarioId = "real" | "conflict" | "limited"

/** 判定结论词（唯一出口：包络 stance 四值 → 展示文案；横幅与侧栏共用） */
export const DECISION_LABEL: Record<DecisionState, string> = {
  insufficient: "缺少有效数据",
  refuted: "多数反馈反对",
  conflicting: "样本内存在分歧",
  supported: "已有有限支持",
}

export const SCENARIOS: Array<{ id: ScenarioId; label: string; demo: boolean }> = [
  { id: "real", label: "真实快照", demo: false },
  { id: "conflict", label: "演示·样本分歧", demo: true },
  { id: "limited", label: "演示·有限支持", demo: true },
]

/** 单条待验证问题：text 为问题内容，source 为来源属性标注 */
export interface EvidenceQuestion {
  text: string
  source: string
}

export type CrossSourceStatus =
  | "needs_l1"
  | "needs_l2"
  | "mixed_scenarios"
  | "potential_divergence"
  | "compare_scenarios"

export interface CrossSourceComparison {
  claim_id: string
  label: string
  status: CrossSourceStatus
  l1_state: DecisionState
  l1_total: number
  l1_polarized: number
  l1_support: number
  l1_oppose: number
  l1_insufficient: number
  l2_total: number
  l1_refs: string[]
  l2_refs: string[]
  question: string
}

/** Wilson 95% 区间（后端 DecisionOut.support_interval / oppose_interval） */
export interface DecisionInterval {
  lo: number
  hi: number
  n: number
}

/** 判定全链路可追溯数据（ADR-0005，routers/evidence.py: DecisionOut） */
export interface DecisionSummary {
  state: DecisionState
  gate_status: string
  support_interval: DecisionInterval | null
  oppose_interval: DecisionInterval | null
  n_total: number
  n_l1: number
  n_polarized: number
  n_insufficient: number
  dedup_clusters: number
  dedup_duplicated: number
  power_note: string
  inference_note: string
}

/** 单条卖点的独立判定；不得用跨假设混合结果替代。 */
export interface ClaimDecisionSummary extends DecisionSummary {
  claim_id: string
}

/** 后端包络（归一化后） */
export interface EvidenceEnvelope {
  query: string
  market: string
  data_mode: string
  scenario: string
  /** 判定状态（DecisionState 四值，ADR-0005 R1 唯一判定枚举） */
  stance: DecisionState
  cards: ValidEvidenceCard[]
  invalidCards: InvalidEvidenceCard[]
  questions: EvidenceQuestion[]
  comparisons: CrossSourceComparison[]
  generated_at: string
  /** 判定可追溯数据（区间/门禁/去重摘要/功效与推断注记）；旧夹具缺失时为 null */
  decision: DecisionSummary | null
  /** 每条卖点独立判定；旧端点缺失时为空数组，由分组逻辑按同一门禁兜底。 */
  claimDecisions: ClaimDecisionSummary[]
  /** 德国 L1 授权快照缺失或损坏提示。 */
  l1Notice: string | null
  /** 快照原始授权用途范围；复核导出只能原样沿用。 */
  l1AuthorizationScope: string[]
  /** 当前已验证 L1 快照的 record_sha256；隔离不同版本的人工复核草稿。 */
  l1SnapshotSha256: string | null
  /** 知乎侧 L2 中文证据卡（ADR-0002 snapshot/live），不参与 stance 判定（硬约束 1） */
  l2Cards: ValidEvidenceCard[]
  /** L2 卡中契约校验未通过的部分，只进占位说明不渲染 */
  l2InvalidCards: InvalidEvidenceCard[]
  /** L2 降级提示（快照缺失/配额耗尽等），null 表示正常；禁止静默空结果（ADR-0002 决策 4） */
  l2Notice: string | null
  /** 本次数据实际来源（展示用）：本地 fixtures 或 API 地址 */
  dataSource: string
}

const FIXTURES: Record<ScenarioId, unknown> = {
  real: realFixture,
  conflict: conflictFixture,
  limited: limitedFixture,
}

export const DEFAULT_INFERENCE_NOTE =
  "当前评论通常为非随机样本，Wilson 区间仅描述样本内不确定性，不能直接外推为总体消费者偏好。"

/** questions 元素未标注来源属性时的默认标注（按「待验证假设」层处理） */
const DEFAULT_QUESTION_SOURCE = "来源属性未标注 · 按「待验证假设」层处理"

/** 95% 置信正态分位（与后端 stats.Z_95 = NormalDist().inv_cdf(0.975) 同值） */
const Z95 = 1.959963984540054

/** Wilson 95% 下界（判定管道与落地页演示器共用） */
function wilsonLowerBound(k: number, n: number): number {
  if (n <= 0) return 0
  const p = k / n
  const z2 = Z95 * Z95
  const denom = 1 + z2 / n
  const center = (p + z2 / (2 * n)) / denom
  const half = (Z95 / denom) * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))
  return Math.max(0, center - half)
}

/** Wilson 95% 上界（1 − 对立侧下界，与后端互补口径一致） */
function wilsonUpperBound(k: number, n: number): number {
  return 1 - wilsonLowerBound(n - k, n)
}

/**
 * 判定公式唯一出口（ADR-0005 口径，与 domain/evidence.py decide() 同规则）：
 * 门禁（去重后有极性样本 n≥30）→ Wilson 95% 区间 → 决定线 / 区间重叠 → 四值状态。
 * 工作台兜底判定与产品概览「样本量→判定」演示器共用，口径不得分叉。
 */
export interface VoteDecision {
  state: DecisionState
  /** 有极性样本时保留描述性 Wilson 区间；门禁只决定能否形成结论。 */
  supportInterval: DecisionInterval | null
  opposeInterval: DecisionInterval | null
}

export function decideFromVotes(kSupport: number, kOppose: number, minN = 30): VoteDecision {
  const n = kSupport + kOppose
  if (n === 0) {
    return { state: "insufficient", supportInterval: null, opposeInterval: null }
  }
  const intervals = {
    supportInterval: { lo: wilsonLowerBound(kSupport, n), hi: wilsonUpperBound(kSupport, n), n },
    opposeInterval: { lo: wilsonLowerBound(kOppose, n), hi: wilsonUpperBound(kOppose, n), n },
  }
  if (n < minN) return { state: "insufficient", ...intervals }
  const loS = intervals.supportInterval.lo
  const loO = intervals.opposeInterval.lo
  if (kSupport > 0 && loS > 0.5) return { state: "supported", ...intervals }
  if (kOppose > 0 && loO > 0.5) return { state: "refuted", ...intervals }
  // 区间重叠判定（与后端 intervals_overlap 同口径；互补份额下 hi_oppose ≈ 1 - lo_support）
  if (kSupport > 0 && kOppose > 0 && loS <= 1 - loO) return { state: "conflicting", ...intervals }
  return { state: "insufficient", supportInterval: null, opposeInterval: null }
}

/**
 * 镜像 domain/evidence.py 的 decide()：包络缺 stance 时兜底计算（仅 L1 计入）。
 * 口径与后端一致：去重（卡面 dedup.is_canonical）先于计数（R2），
 * 判定规则本体在 decideFromVotes（本文件，唯一出口）。
 */
function fallbackDecision(cards: ValidEvidenceCard[]): DecisionState {
  const l1 = cards.filter((c) => c.level === "L1")
  const canonical = l1.filter((c) => c.dedup?.is_canonical !== false)
  const kSupport = canonical.filter((c) => c.stance === "support").length
  const kOppose = canonical.filter((c) => c.stance === "oppose").length
  return decideFromVotes(kSupport, kOppose).state
}

/** 契约校验一组原始卡：合法卡与占位说明分列（主证据卡与 L2 卡共用） */
function splitValidCards(
  rawList: unknown[],
): { cards: ValidEvidenceCard[]; invalidCards: InvalidEvidenceCard[] } {
  const cards: ValidEvidenceCard[] = []
  const invalidCards: InvalidEvidenceCard[] = []
  for (const rawCard of rawList) {
    const result = validateEvidenceCard(rawCard)
    if (result.ok) cards.push(result.card)
    else invalidCards.push(result.invalid)
  }
  return { cards, invalidCards }
}

function normalizeDecisionState(value: unknown, fallback: DecisionState = "insufficient"): DecisionState {
  return value === "supported" ||
    value === "refuted" ||
    value === "conflicting" ||
    value === "insufficient"
    ? value
    : fallback
}

function normalizeDecision(raw: unknown): DecisionSummary | null {
  if (typeof raw !== "object" || raw === null) return null
  const value = raw as Record<string, unknown>
  const interval = (input: unknown): DecisionInterval | null => {
    if (typeof input !== "object" || input === null) return null
    const item = input as Record<string, unknown>
    const lo = Number(item.lo)
    const hi = Number(item.hi)
    const n = Number(item.n)
    if (![lo, hi, n].every(Number.isFinite)) return null
    return { lo, hi, n }
  }
  return {
    state: normalizeDecisionState(value.state),
    gate_status: typeof value.gate_status === "string" ? value.gate_status : "",
    support_interval: interval(value.support_interval),
    oppose_interval: interval(value.oppose_interval),
    n_total: Number(value.n_total ?? 0),
    n_l1: Number(value.n_l1 ?? 0),
    n_polarized: Number(value.n_polarized ?? 0),
    n_insufficient: Number(value.n_insufficient ?? 0),
    dedup_clusters: Number(value.dedup_clusters ?? 0),
    dedup_duplicated: Number(value.dedup_duplicated ?? 0),
    power_note: typeof value.power_note === "string" ? value.power_note : "",
    inference_note:
      typeof value.inference_note === "string" ? value.inference_note : DEFAULT_INFERENCE_NOTE,
  }
}

function normalizeComparison(raw: unknown): CrossSourceComparison | null {
  if (typeof raw !== "object" || raw === null) return null
  const item = raw as Record<string, unknown>
  const claimId = typeof item.claim_id === "string" ? item.claim_id : ""
  const question = typeof item.question === "string" ? item.question : ""
  const statuses: CrossSourceStatus[] = [
    "needs_l1",
    "needs_l2",
    "mixed_scenarios",
    "potential_divergence",
    "compare_scenarios",
  ]
  const status = statuses.find((candidate) => candidate === item.status)
  if (!claimId || !question || !status) return null
  const counts = [
    Number(item.l1_total ?? 0),
    Number(item.l1_polarized ?? 0),
    Number(item.l1_support ?? 0),
    Number(item.l1_oppose ?? 0),
    Number(item.l1_insufficient ?? 0),
    Number(item.l2_total ?? 0),
  ]
  if (!counts.every((value) => Number.isFinite(value) && value >= 0)) return null
  const refs = (value: unknown): string[] =>
    Array.isArray(value) ? value.filter((ref): ref is string => typeof ref === "string") : []
  return {
    claim_id: claimId,
    label: typeof item.label === "string" && item.label ? item.label : claimId,
    status,
    l1_state: normalizeDecisionState(item.l1_state),
    l1_total: counts[0]!,
    l1_polarized: counts[1]!,
    l1_support: counts[2]!,
    l1_oppose: counts[3]!,
    l1_insufficient: counts[4]!,
    l2_total: counts[5]!,
    l1_refs: refs(item.l1_refs),
    l2_refs: refs(item.l2_refs),
    question,
  }
}

/** 归一化包络：校验证据卡契约、规范问题来源属性、兜底 stance */
function normalizeEnvelope(
  raw: unknown,
  dataSource: string,
): EvidenceEnvelope {
  const obj = (typeof raw === "object" && raw !== null ? raw : {}) as Record<string, unknown>
  const rawCards = Array.isArray(obj.cards) ? obj.cards : []
  const main = splitValidCards(rawCards)

  // 知乎侧 L2 卡：与主卡同一契约校验。
  const rawL2Cards = Array.isArray(obj.l2_cards) ? obj.l2_cards : []
  const l2 = splitValidCards(rawL2Cards)

  // questions 兼容字符串与对象两种形态
  const rawQuestions = Array.isArray(obj.questions) ? obj.questions : []
  const questions: EvidenceQuestion[] = rawQuestions.map((q) => {
    if (typeof q === "string") return { text: q, source: DEFAULT_QUESTION_SOURCE }
    const o = (q ?? {}) as Record<string, unknown>
    const text = typeof o.text === "string" ? o.text : String(o.text ?? o.question ?? o.content ?? "")
    const source = typeof o.source === "string" && o.source ? o.source : DEFAULT_QUESTION_SOURCE
    return { text, source }
  })

  const stance = normalizeDecisionState(obj.stance, fallbackDecision(main.cards))

  // 判定可追溯数据（ADR-0005 DecisionOut）；旧夹具/旧端点缺失时为 null。
  const decision = normalizeDecision(obj.decision)
  const claimDecisions: ClaimDecisionSummary[] = Array.isArray(obj.claim_decisions)
    ? obj.claim_decisions.flatMap((item) => {
        if (typeof item !== "object" || item === null) return []
        const claimId = (item as Record<string, unknown>).claim_id
        const summary = normalizeDecision(item)
        return summary && typeof claimId === "string" && claimId
          ? [{ ...summary, claim_id: claimId }]
          : []
      })
    : []
  const comparisons: CrossSourceComparison[] = Array.isArray(obj.comparisons)
    ? obj.comparisons.flatMap((item) => {
        const comparison = normalizeComparison(item)
        return comparison ? [comparison] : []
      })
    : []
  return {
    query: typeof obj.query === "string" ? obj.query : "",
    market: typeof obj.market === "string" ? obj.market : "de",
    data_mode: typeof obj.data_mode === "string" ? obj.data_mode : "snapshot",
    scenario: typeof obj.scenario === "string" ? obj.scenario : "real",
    stance,
    cards: main.cards,
    invalidCards: main.invalidCards,
    decision,
    claimDecisions,
    l1Notice: typeof obj.l1_notice === "string" && obj.l1_notice ? obj.l1_notice : null,
    l1AuthorizationScope: Array.isArray(obj.l1_authorization_scope)
      ? obj.l1_authorization_scope.filter((scope): scope is string => typeof scope === "string")
      : [],
    l1SnapshotSha256:
      typeof obj.l1_snapshot_sha256 === "string" && /^[0-9a-f]{64}$/.test(obj.l1_snapshot_sha256)
        ? obj.l1_snapshot_sha256
        : null,
    l2Cards: l2.cards,
    l2InvalidCards: l2.invalidCards,
    l2Notice: typeof obj.l2_notice === "string" && obj.l2_notice ? obj.l2_notice : null,
    questions,
    comparisons,
    generated_at: typeof obj.generated_at === "string" ? obj.generated_at : "",
    dataSource,
  }
}

/**
 * 按场景加载证据包络。
 * @param scenario 场景 id（real / conflict / limited）
 * @param query    检索关键词（仅真实快照场景传给后端）
 * @param apiBase  NUXT_PUBLIC_API_BASE 的取值
 */
export async function loadEvidenceEnvelope(
  scenario: ScenarioId,
  query: string,
  apiBase: string,
): Promise<EvidenceEnvelope> {
  const useFixtures = apiBase.trim() === "" || apiBase.trim().toLowerCase() === "fixtures"

  if (useFixtures) {
    // 本地夹具模式：后端不可用时仍可完整演示三种状态
    return normalizeEnvelope(FIXTURES[scenario], "本地 fixtures · 固定演示")
  }

  // 真实 API 模式：字段名与包络不得偏离后端契约
  const base = apiBase.replace(/\/+$/, "")
  const url =
    scenario === "real"
      ? `${base}/api/evidence?query=${encodeURIComponent(query)}`
      : `${base}/api/evidence/demo?scenario=${scenario}`
  const raw = await $fetch<unknown>(url, { method: "GET" })
  return normalizeEnvelope(raw, `真实 API（${base}）`)
}
