import type {
  ClaimDecisionSummary,
  EvidenceEnvelope,
} from "../composables/useEvidence"
import type { Hypothesis, HypothesisStatus } from "./hypotheses"
import type { ValidationPlan } from "./validation-plan"
import type { ValidationRound } from "./validation-round"

export interface CaseHypothesisPlan {
  hypothesis: Hypothesis
  status: HypothesisStatus
  statusNote: string
  decision: ClaimDecisionSummary
  plan: ValidationPlan
}

export function buildCasePackage(
  envelope: EvidenceEnvelope,
  hypotheses: CaseHypothesisPlan[],
  rounds: ValidationRound[],
  exportedAt: string = new Date().toISOString(),
) {
  const isDemo =
    envelope.scenario !== "real" ||
    envelope.cards.some((card) => card.is_demo_data) ||
    envelope.l2Cards.some((card) => card.is_demo_data)
  return {
    schema_version: 1,
    source_api: "crosspilot_case_export",
    exported_at_utc: exportedAt,
    query: envelope.query,
    market: envelope.market,
    data_mode: envelope.data_mode,
    scenario: envelope.scenario,
    data_source: envelope.dataSource,
    is_demo_data: isDemo,
    market_effect_claim_allowed: false,
    disclaimer: isDemo
      ? "本案例包包含模拟演示数据，仅用于流程展示，不构成真实消费者证据、偏好或市场效果结论。"
      : "本案例包仅描述当前授权样本与待验证计划；在线评论通常为非随机样本，不可外推总体消费者偏好或市场效果。",
    evidence: {
      generated_at: envelope.generated_at,
      cards: envelope.cards,
      l2_cards: envelope.l2Cards,
      questions: envelope.questions,
      comparisons: envelope.comparisons,
      decision: envelope.decision,
      claim_decisions: envelope.claimDecisions,
      l1_notice: envelope.l1Notice,
      l1_authorization_scope: envelope.l1AuthorizationScope,
      l1_snapshot_sha256: envelope.l1SnapshotSha256,
      l2_notice: envelope.l2Notice,
      invalid_card_count: envelope.invalidCards.length,
      invalid_card_errors: envelope.invalidCards.map((card) => card.errors),
      l2_invalid_card_count: envelope.l2InvalidCards.length,
      l2_invalid_card_errors: envelope.l2InvalidCards.map((card) => card.errors),
    },
    hypotheses: hypotheses.map((item) => ({
      claim_id: item.hypothesis.id,
      title: item.hypothesis.title,
      probe: item.hypothesis.probe,
      keywords: item.hypothesis.keywords,
      custom: item.hypothesis.custom === true,
      status: item.status,
      status_note: item.statusNote,
      decision: item.decision,
      validation_plan: item.plan,
    })),
    validation_rounds: rounds,
  }
}
