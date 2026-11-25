/**
 * 证据数据加载：fixtures / 真实 API 双模式。
 *
 * 后端契约（执行者A，字段名不得偏离）：
 *   GET /api/evidence?query=<关键词>       → 真实快照场景（scenario="real"）
 *   GET /api/evidence/demo?scenario=conflict|limited → 演示场景
 * 包络：{ query, market, data_mode, scenario, stance, cards, questions, generated_at,
 *         l2_cards?, l2_notice? }（l2_* 为知乎侧 L2 卡与降级提示，可选、向后兼容）
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
  conflicting: "证据相互冲突",
  supported: "已有有限支持",
}

export const SCENARIOS: Array<{ id: ScenarioId; label: string; demo: boolean }> = [
  { id: "real", label: "真实快照", demo: false },
  { id: "conflict", label: "演示·证据冲突", demo: true },
  { id: "limited", label: "演示·有限支持", demo: true },
]

/** 单条待验证问题：text 为问题内容，source 为来源属性标注 */
export interface EvidenceQuestion {
  text: string
  source: string
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
  generated_at: string
  /** 判定可追溯数据（区间/门禁/去重摘要/功效注记）；旧夹具缺失时为 null */
  decision: DecisionSummary | null
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
  /** 双侧 Wilson 95% 区间；门禁未过时为 null */
  supportInterval: DecisionInterval | null
  opposeInterval: DecisionInterval | null
}

export function decideFromVotes(kSupport: number, kOppose: number, minN = 30): VoteDecision {
  const n = kSupport + kOppose
  if (n < minN) {
    return { state: "insufficient", supportInterval: null, opposeInterval: null }
  }
  const intervals = {
    supportInterval: { lo: wilsonLowerBound(kSupport, n), hi: wilsonUpperBound(kSupport, n), n },
    opposeInterval: { lo: wilsonLowerBound(kOppose, n), hi: wilsonUpperBound(kOppose, n), n },
  }
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

/** 归一化包络：校验证据卡契约、规范问题来源属性、兜底 stance */
function normalizeEnvelope(raw: unknown, dataSource: string): EvidenceEnvelope {
  const obj = (typeof raw === "object" && raw !== null ? raw : {}) as Record<string, unknown>
  const rawCards = Array.isArray(obj.cards) ? obj.cards : []
  const main = splitValidCards(rawCards)

  // 知乎侧 L2 卡：与主卡同一契约校验；缺失字段（旧夹具/旧端点）按空处理
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

  const stanceRaw = obj.stance
  const stance: DecisionState =
    stanceRaw === "supported" ||
    stanceRaw === "refuted" ||
    stanceRaw === "insufficient" ||
    stanceRaw === "conflicting"
      ? stanceRaw
      : fallbackDecision(main.cards)

  // 判定可追溯数据（ADR-0005 DecisionOut）；旧夹具/旧端点缺失时为 null
  const decisionRaw = (typeof obj.decision === "object" && obj.decision !== null ? obj.decision : null) as
    | Record<string, unknown>
    | null
  const decision: DecisionSummary | null = decisionRaw
    ? {
        state:
          decisionRaw.state === "supported" ||
          decisionRaw.state === "refuted" ||
          decisionRaw.state === "conflicting"
            ? decisionRaw.state
            : "insufficient",
        gate_status: typeof decisionRaw.gate_status === "string" ? decisionRaw.gate_status : "",
        support_interval: (decisionRaw.support_interval as DecisionInterval | null) ?? null,
        oppose_interval: (decisionRaw.oppose_interval as DecisionInterval | null) ?? null,
        n_total: Number(decisionRaw.n_total ?? 0),
        n_l1: Number(decisionRaw.n_l1 ?? 0),
        n_polarized: Number(decisionRaw.n_polarized ?? 0),
        n_insufficient: Number(decisionRaw.n_insufficient ?? 0),
        dedup_clusters: Number(decisionRaw.dedup_clusters ?? 0),
        dedup_duplicated: Number(decisionRaw.dedup_duplicated ?? 0),
        power_note: typeof decisionRaw.power_note === "string" ? decisionRaw.power_note : "",
      }
    : null

  return {
    query: typeof obj.query === "string" ? obj.query : "",
    market: typeof obj.market === "string" ? obj.market : "de",
    data_mode: typeof obj.data_mode === "string" ? obj.data_mode : "snapshot",
    scenario: typeof obj.scenario === "string" ? obj.scenario : "real",
    stance,
    cards: main.cards,
    invalidCards: main.invalidCards,
    decision,
    l2Cards: l2.cards,
    l2InvalidCards: l2.invalidCards,
    l2Notice: typeof obj.l2_notice === "string" && obj.l2_notice ? obj.l2_notice : null,
    questions,
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
    return normalizeEnvelope(FIXTURES[scenario], "本地 fixtures")
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
