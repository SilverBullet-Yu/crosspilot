import type { EvidenceStance, ValidEvidenceCard } from "./evidence-schema"

export const L1_AUTHORIZATION_SCOPES = [
  "internal_product_validation",
  "model_processing",
  "contest_demo",
  "public_display",
] as const

export type L1AuthorizationScope = (typeof L1_AUTHORIZATION_SCOPES)[number]

export interface L1ReviewDecision {
  review_id: string
  reviewed: boolean
  relevance: "relevant" | "irrelevant"
  claim_id: string
  stance: EvidenceStance
  note: string
}

export function defaultL1ReviewDecision(card: ValidEvidenceCard): L1ReviewDecision {
  return {
    review_id: card.review_id || card.source_url,
    reviewed:
      card.classification_method === "manual" &&
      card.review_required === false &&
      Boolean(card.classification_note?.trim()),
    relevance: card.relevance ?? "relevant",
    claim_id: card.claim_id ?? (card.relevance === "irrelevant" ? "" : "unassigned"),
    stance: card.stance,
    note: card.classification_note ?? "",
  }
}

export function normalizeL1ReviewDecision(
  raw: unknown,
  card: ValidEvidenceCard,
): L1ReviewDecision {
  const fallback = defaultL1ReviewDecision(card)
  if (typeof raw !== "object" || raw === null) return fallback
  const value = raw as Record<string, unknown>
  const relevance = value.relevance === "irrelevant" ? "irrelevant" : "relevant"
  const stance: EvidenceStance =
    value.stance === "support" || value.stance === "oppose" || value.stance === "insufficient"
      ? value.stance
      : fallback.stance
  return {
    review_id: fallback.review_id,
    reviewed: value.reviewed === true,
    relevance,
    claim_id:
      relevance === "irrelevant"
        ? ""
        : typeof value.claim_id === "string"
          ? value.claim_id.trim().slice(0, 64)
          : fallback.claim_id,
    stance: relevance === "irrelevant" ? "insufficient" : stance,
    note: typeof value.note === "string" ? value.note.trim().slice(0, 500) : "",
  }
}

export function filterL1ReviewCards(
  cards: ValidEvidenceCard[],
  claimId: string,
  search: string,
): ValidEvidenceCard[] {
  const query = search.trim().toLowerCase()
  return cards.filter((card) => {
    const cardClaim =
      card.relevance === "irrelevant" ? "irrelevant" : card.claim_id || "unassigned"
    if (claimId !== "all" && cardClaim !== claimId) return false
    if (!query) return true
    return [card.excerpt, card.review_id, card.source_url, cardClaim].some(
      (value) => typeof value === "string" && value.toLowerCase().includes(query),
    )
  })
}

export function l1ReviewErrors(decision: L1ReviewDecision): string[] {
  if (!decision.reviewed) return []
  const errors: string[] = []
  if (!decision.note.trim()) errors.push("复核说明")
  if (decision.relevance === "irrelevant") {
    if (decision.claim_id) errors.push("不相关评论不得填写 claim_id")
    if (decision.stance !== "insufficient") errors.push("不相关评论立场必须为 insufficient")
  } else if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(decision.claim_id)) {
    errors.push("claim_id")
  }
  return errors
}

export function l1ReviewStorageKey(query: string, snapshotSha256: string): string {
  if (!query.trim()) throw new Error("产品关键词不能为空")
  if (!/^[0-9a-f]{64}$/.test(snapshotSha256)) {
    throw new Error("复核草稿需要有效的 L1 快照 record_sha256")
  }
  return `crosspilot.l1-review.v2.${query.trim()}.${snapshotSha256}`
}

export function buildL1ReviewDocument(
  cards: ValidEvidenceCard[],
  decisions: Record<string, L1ReviewDecision>,
  query: string,
  authorizationScope: L1AuthorizationScope[],
  snapshotSha256: string | null = null,
): Record<string, unknown> {
  const realCards = cards.filter((card) => card.level === "L1" && !card.is_demo_data)
  if (!realCards.length) throw new Error("没有可导出的真实 L1 评论")
  if (!authorizationScope.includes("internal_product_validation")) {
    throw new Error("授权范围必须包含 internal_product_validation")
  }
  if (snapshotSha256 && !/^[0-9a-f]{64}$/.test(snapshotSha256)) {
    throw new Error("source_snapshot_sha256 必须为 64 位小写十六进制")
  }
  const first = realCards[0]!
  if (!first.source_id || !first.authorization || !first.authorization_ref) {
    throw new Error("真实 L1 缺少 source_id、authorization 或 authorization_ref")
  }
  const claimTerms: Record<string, string[]> = {}
  for (const card of realCards) {
    if (!card.review_id) throw new Error("真实 L1 缺少 review_id")
    const decision = decisions[card.review_id]
    if (decision?.reviewed) {
      const errors = l1ReviewErrors(decision)
      if (errors.length) throw new Error(`${card.review_id} 复核未完成：${errors.join("、")}`)
    }
    const terms = card.aspect_terms ?? []
    const sourceClaimId = card.claim_id
    const effectiveClaimId =
      decision?.relevance === "irrelevant" ? "" : decision?.claim_id ?? sourceClaimId
    if (!terms.length || !sourceClaimId || effectiveClaimId !== sourceClaimId) continue
    if (["capacity", "features", "price", "unassigned"].includes(sourceClaimId)) {
      throw new Error("aspect_terms 只能归属于自定义卖点")
    }
    const previous = claimTerms[sourceClaimId]
    if (previous && previous.join("\u0000") !== terms.join("\u0000")) {
      throw new Error(`同一自定义卖点的 aspect_terms 不一致：${sourceClaimId}`)
    }
    claimTerms[sourceClaimId] = [...terms]
  }
  return {
    query,
    market: "de",
    source_id: first.source_id,
    authorization: first.authorization,
    authorization_ref: first.authorization_ref,
    authorization_scope: authorizationScope,
    source_snapshot_sha256: snapshotSha256,
    claim_terms: claimTerms,
    is_demo_data: false,
    cards: realCards.map((card) => {
      const decision = decisions[card.review_id || card.source_url]
      const reviewed = decision?.reviewed === true
      return {
        review_id: card.review_id,
        claim_id: decision?.relevance === "irrelevant" ? "" : decision?.claim_id ?? card.claim_id,
        excerpt: card.excerpt,
        source_url: card.source_url,
        published_on: card.published_on,
        language: card.language,
        market: card.market ?? "de",
        source_id: card.source_id,
        authorization: card.authorization,
        authorization_ref: card.authorization_ref,
        relevance: decision?.relevance ?? card.relevance ?? "relevant",
        ...(reviewed
          ? { stance: decision?.stance ?? card.stance, stance_note: decision?.note ?? "" }
          : {}),
      }
    }),
  }
}
