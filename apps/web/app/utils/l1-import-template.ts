import type { Hypothesis } from "./hypotheses"

const BUILTIN_CLAIM_IDS = new Set(["capacity", "features", "price", "unassigned"])
const CLAIM_ID_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/

export interface L1ImportTemplate {
  schema_version: 1
  query: string
  market: "de"
  source_id: string
  authorization: string
  authorization_ref: string
  authorization_scope: ["internal_product_validation"]
  claim_terms: Record<string, string[]>
  is_demo_data: false
  cards: []
}

export function buildL1ImportTemplate(
  query: string,
  hypotheses: Hypothesis[],
): L1ImportTemplate {
  const cleanQuery = query.trim()
  if (!cleanQuery) throw new Error("产品关键词不能为空")
  if (cleanQuery.length > 100) throw new Error("产品关键词不超过 100 字符")

  const claimTerms: Record<string, string[]> = {}
  for (const hypothesis of hypotheses) {
    if (!hypothesis.custom) continue
    if (!CLAIM_ID_RE.test(hypothesis.id) || BUILTIN_CLAIM_IDS.has(hypothesis.id)) {
      throw new Error(`自定义 claim_id 非法：${hypothesis.id}`)
    }
    const terms = [
      ...new Set(
        hypothesis.keywords
          .map((term) => term.trim().slice(0, 80))
          .filter(Boolean),
      ),
    ].slice(0, 20)
    if (terms.length) claimTerms[hypothesis.id] = terms
  }

  return {
    schema_version: 1,
    query: cleanQuery,
    market: "de",
    source_id: "",
    authorization: "",
    authorization_ref: "",
    authorization_scope: ["internal_product_validation"],
    claim_terms: claimTerms,
    is_demo_data: false,
    cards: [],
  }
}
