/**
 * 可编辑卖点假设与证据归属。
 *
 * 归属优先级：card.claim_id → 预设关键词。显式 claim_id 未命中时进入
 * 「未归属证据」，绝不退回关键词猜测。组级结论优先使用后端 claim_decisions；
 * 旧响应才用同一门禁（去重后有极性样本 n≥30）在前端兜底。
 */
import type { DecisionState, ValidEvidenceCard } from "./evidence-schema"
import { DEFAULT_INFERENCE_NOTE, decideFromVotes } from "../composables/useEvidence"
import type { ClaimDecisionSummary } from "../composables/useEvidence"

export interface Hypothesis {
  id: string
  /** 假设原文（方案 4.3），工作台内可编辑。 */
  title: string
  /** 系统应提出的核实问题（方案 4.3），工作台内可编辑。 */
  probe: string
  /** 仅 claim_id 缺失时使用的归属关键词。 */
  keywords: string[]
  /** 本地创建的自定义假设；预置假设不设置此字段。 */
  custom?: boolean
}

export function createCustomHypothesis(
  title: string,
  probe: string,
  keywords: string[],
): Hypothesis {
  const cleanTitle = title.trim().slice(0, 200)
  if (!cleanTitle) throw new Error("假设标题不能为空")
  const cleanKeywords = [...new Set(keywords.map((keyword) => keyword.trim().slice(0, 80)).filter(Boolean))].slice(0, 20)
  return {
    id: `custom-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    title: cleanTitle,
    probe: probe.trim().slice(0, 1000) || "请找一个会推翻该假设的具体使用场景。",
    keywords: cleanKeywords,
    custom: true,
  }
}

/** 默认蓝本；页面会克隆为响应式状态，不直接编辑此数组。 */
export const HYPOTHESES: Hypothesis[] = [
  {
    id: "capacity",
    title: "容量越大越好",
    probe: "是否存在尺寸限制或便携性方面的负面反馈？",
    keywords: [
      "容量", "容积", "尺寸", "便携", "手提行李", "装得下", "太能装",
      "kapazität", "volumen", "liter", "größe", "capacity", "volume",
      "handgepäck", "hand luggage", "carry-on", "sperrig", "bulky",
      "koffer", "platz", "pack", "packen", "gepackt", "vollgepackt", "passt", "hinein",
    ],
  },
  {
    id: "features",
    title: "功能越多越好",
    probe: "更多隔层是否带来更高使用价值，还是增加操作负担？",
    keywords: [
      "功能", "隔层", "分层", "分隔", "夹层", "口袋", "拉链", "分区",
      "fach", "fächer", "innentasche", "unterteilung", "aufteilung", "reißverschluss",
      "compartment", "pocket", "zip", "organizer", "packwürfel", "würfel", "feature",
      "section", "getrennt", "sortiert", "kabel", "kosmetik", "wäsche", "einschub",
    ],
  },
  {
    id: "price",
    title: "低价是核心购买理由",
    probe: "有无证据表明耐用性、材料、退换保障更重要？",
    keywords: [
      "价格", "低价", "便宜", "性价比", "降价", "促销", "耐用", "材料", "材质", "退换", "质保",
      "preis", "günstig", "billig", "preiswert", "teuer", "price", "cheap", "expensive",
      "value for money", "cost", "qualität", "quality", "langlebig", "durable",
      "material", "stoff", "chemie", "riecht", "geruch", "nähte", "naht", "robust",
      "verarbeitet", "haltbar", "warranty", "refund", "retoure", "gewährleistung", "return",
    ],
  },
]

/** 组级状态与独立判定共用四值，避免「有一条支持」绕过门禁。 */
export type HypothesisStatus = DecisionState

export const STATUS_META: Record<HypothesisStatus, { label: string; cls: string }> = {
  supported: { label: "已有有限支持", cls: "status--ok" },
  refuted: { label: "多数反馈反对", cls: "status--bad" },
  conflicting: { label: "样本内存在分歧", cls: "status--bad" },
  insufficient: { label: "证据不足", cls: "status--warn" },
}

export interface HypothesisGroups {
  hypothesis: Hypothesis
  support: ValidEvidenceCard[]
  oppose: ValidEvidenceCard[]
  /** 不支撑结论的卡（L2/L3、无立场卡）。 */
  missing: ValidEvidenceCard[]
  status: HypothesisStatus
  statusNote: string
  /** 后端独立判定，或旧响应下按同一门禁计算的兜底判定。 */
  decision: ClaimDecisionSummary
  /** n_l1=0、去重后样本低于门禁或门禁未通过时必须显示证据不足。 */
  evidenceInsufficient: boolean
}

const MIN_POLARIZED = 30

/**
 * 拉丁字母关键词 → 词边界+前缀正则；中文关键词 → 包含匹配。
 * 不用 i 标志，避免 V8 在非 unicode 模式下把 ß 折叠成 ss。
 */
function matchesKeyword(text: string, keyword: string): boolean {
  if (/[a-zäöüß]/i.test(keyword)) {
    const lowerKeyword = keyword.toLowerCase()
    const re = new RegExp(`\\b${lowerKeyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`)
    return re.test(text.toLowerCase())
  }
  return text.toLowerCase().includes(keyword.toLowerCase())
}

/** 优先按 claim_id 归属；缺失时才关键词回退。显式未知 ID 不做回退。 */
export function matchHypothesis(
  card: ValidEvidenceCard,
  hypotheses: Hypothesis[] = HYPOTHESES,
): Hypothesis | null {
  if (card.claim_id) {
    return hypotheses.find((hypothesis) => hypothesis.id === card.claim_id) ?? null
  }
  const text = `${card.excerpt} ${card.source_url}`
  return hypotheses.find((hypothesis) =>
    hypothesis.keywords.some((keyword) => matchesKeyword(text, keyword)),
  ) ?? null
}

/** 旧响应兜底：仅 L1 簇代表计数，门禁与区间规则复用唯一公式。 */
function fallbackClaimDecision(hypothesisId: string, cards: ValidEvidenceCard[]): ClaimDecisionSummary {
  const l1 = cards.filter((card) => card.level === "L1")
  const canonical = l1.filter((card) => card.dedup?.is_canonical !== false)
  const support = canonical.filter((card) => card.stance === "support").length
  const oppose = canonical.filter((card) => card.stance === "oppose").length
  const nPolarized = support + oppose
  const vote = decideFromVotes(support, oppose, MIN_POLARIZED)
  const gateStatus =
    l1.length === 0
      ? "no_l1"
      : nPolarized === 0
        ? "no_polarized"
        : nPolarized < MIN_POLARIZED
          ? "below_minimum"
          : "pass"
  return {
    claim_id: hypothesisId,
    state: vote.state,
    gate_status: gateStatus,
    support_interval: vote.supportInterval,
    oppose_interval: vote.opposeInterval,
    n_total: cards.length,
    n_l1: l1.length,
    n_polarized: nPolarized,
    n_insufficient: canonical.filter((card) => card.stance === "insufficient").length,
    dedup_clusters: canonical.length,
    dedup_duplicated: Math.max(0, l1.length - canonical.length),
    power_note:
      nPolarized < MIN_POLARIZED
        ? `去重后有极性样本 ${nPolarized} 低于门禁 ${MIN_POLARIZED}，按口径强制 insufficient`
        : `去重后有极性样本 ${nPolarized} 过门禁；决定线：份额 ≥68% 才判决定性多数`,
    inference_note: DEFAULT_INFERENCE_NOTE,
  }
}

function hasInsufficientEvidence(decision: ClaimDecisionSummary): boolean {
  return (
    decision.n_l1 <= 0 ||
    decision.n_polarized < MIN_POLARIZED ||
    decision.gate_status !== "pass" ||
    decision.state === "insufficient"
  )
}

function statusNote(decision: ClaimDecisionSummary, evidenceInsufficient: boolean): string {
  if (evidenceInsufficient) {
    if (decision.n_l1 <= 0) return "证据不足：L1 一手反馈为零样本，不能形成单条卖点结论。"
    if (decision.n_polarized < MIN_POLARIZED) {
      return `证据不足：L1 n=${decision.n_l1}，去重后有极性样本 n=${decision.n_polarized}，低于 n≥${MIN_POLARIZED} 门禁。`
    }
    if (decision.gate_status !== "pass") {
      return `证据不足：门禁状态为 ${decision.gate_status || "未标注"}，当前不形成偏好结论。`
    }
    return "证据不足：当前区间不足以支持单条卖点结论。"
  }
  const support = decision.support_interval
  if (decision.state === "supported" && support) {
    return `独立判定：支持份额 95% 区间 [${support.lo.toFixed(2)}, ${support.hi.toFixed(2)}]（n=${support.n}）；样本仍有限，需扩大样本复核。`
  }
  if (decision.state === "refuted") return "独立判定：反对份额的 95% 区间下界过半；支持侧原文仍保留。"
  return "独立判定：支持与反对区间重叠，保留分歧，不做调和。"
}

/** 按可编辑假设分组；后端 claim_decisions 优先，缺失时按同一门禁兜底。 */
export function groupCardsByHypothesis(
  cards: ValidEvidenceCard[],
  hypotheses: Hypothesis[] = HYPOTHESES,
  claimDecisions: ClaimDecisionSummary[] = [],
): {
  groups: HypothesisGroups[]
  irrelevant: ValidEvidenceCard[]
  unassigned: ValidEvidenceCard[]
} {
  const groups: HypothesisGroups[] = hypotheses.map((hypothesis) => {
    const decision =
      claimDecisions.find((item) => item.claim_id === hypothesis.id) ??
      fallbackClaimDecision(hypothesis.id, [])
    const evidenceInsufficient = hasInsufficientEvidence(decision)
    return {
      hypothesis,
      support: [],
      oppose: [],
      missing: [],
      status: evidenceInsufficient ? "insufficient" : decision.state,
      statusNote: statusNote(decision, evidenceInsufficient),
      decision,
      evidenceInsufficient,
    }
  })
  const irrelevant: ValidEvidenceCard[] = []
  const unassigned: ValidEvidenceCard[] = []

  for (const card of cards) {
    if (card.relevance === "irrelevant") {
      irrelevant.push(card)
      continue
    }
    const hypothesis = matchHypothesis(card, hypotheses)
    const group = hypothesis
      ? groups.find((item) => item.hypothesis.id === hypothesis.id)
      : undefined
    if (!group) {
      unassigned.push(card)
      continue
    }
    if (card.level !== "L1") group.missing.push(card)
    else if (card.stance === "support") group.support.push(card)
    else if (card.stance === "oppose") group.oppose.push(card)
    else group.missing.push(card)
  }

  for (const group of groups) {
    const groupCards = [...group.support, ...group.oppose, ...group.missing]
    group.decision =
      claimDecisions.find((item) => item.claim_id === group.hypothesis.id) ??
      fallbackClaimDecision(group.hypothesis.id, groupCards)
    group.evidenceInsufficient = hasInsufficientEvidence(group.decision)
    group.status = group.evidenceInsufficient ? "insufficient" : group.decision.state
    group.statusNote = statusNote(group.decision, group.evidenceInsufficient)
  }
  return { groups, irrelevant, unassigned }
}
