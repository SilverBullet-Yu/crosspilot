import type { DecisionState } from "./evidence-schema"

export const VALIDATION_ROUNDS_KEY = "crosspilot.validation-rounds.v1"

export type ValidationDecision = "keep" | "modify" | "pause" | "reject"
export type ValidationConfirmation = "pending" | "confirmed"
export type PrototypeOrder = "multi_first" | "open_first" | ""

export interface PrototypeObservation {
  participantCode: string
  order: PrototypeOrder
  itemsLoaded: string
  retrieval: string
  friction: string
}

export interface ValidationRound {
  id: string
  createdAt: string
  scenario: string
  query: string
  claimId: string
  hypothesisTitle: string
  status: DecisionState
  evidenceRefs: string
  observation: string
  decision: ValidationDecision | ""
  rationale: string
  nextAction: string
  owner: string
  confirmation: ValidationConfirmation
  prototype?: PrototypeObservation
  market: string
  l1SnapshotSha256: string | null
}

export const DECISION_OPTIONS: Array<{ value: ValidationDecision; label: string }> = [
  { value: "keep", label: "保留假设" },
  { value: "modify", label: "修改假设" },
  { value: "pause", label: "暂停验证" },
  { value: "reject", label: "拒绝假设" },
]

export function emptyValidationRound(): ValidationRound {
  return {
    id: "",
    createdAt: "",
    scenario: "real",
    query: "旅行收纳包",
    claimId: "",
    hypothesisTitle: "",
    status: "insufficient",
    evidenceRefs: "",
    observation: "",
    decision: "",
    rationale: "",
    nextAction: "",
    owner: "",
    confirmation: "pending",
    market: "de",
    l1SnapshotSha256: null,
  }
}

export function emptyPrototypeObservation(): PrototypeObservation {
  return {
    participantCode: "",
    order: "",
    itemsLoaded: "",
    retrieval: "",
    friction: "",
  }
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

function isDecisionState(value: unknown): value is DecisionState {
  return value === "supported" || value === "refuted" || value === "conflicting" || value === "insufficient"
}

function normalizePrototype(raw: unknown): PrototypeObservation | undefined {
  if (typeof raw !== "object" || raw === null) return undefined
  const source = raw as Record<string, unknown>
  return {
    participantCode: textValue(source.participantCode).slice(0, 100),
    order: source.order === "multi_first" || source.order === "open_first" ? source.order : "",
    itemsLoaded: textValue(source.itemsLoaded).slice(0, 2000),
    retrieval: textValue(source.retrieval).slice(0, 2000),
    friction: textValue(source.friction).slice(0, 2000),
  }
}

export function normalizeValidationRound(raw: unknown): ValidationRound {
  const source = typeof raw === "object" && raw !== null ? raw as Record<string, unknown> : {}
  const decision = source.decision
  const normalized: ValidationRound = {
    id: textValue(source.id).slice(0, 100),
    createdAt: textValue(source.createdAt).slice(0, 40),
    scenario: textValue(source.scenario).slice(0, 40),
    query: textValue(source.query).slice(0, 200),
    claimId: textValue(source.claimId).slice(0, 100),
    hypothesisTitle: textValue(source.hypothesisTitle).slice(0, 200),
    status: isDecisionState(source.status) ? source.status : "insufficient",
    evidenceRefs: textValue(source.evidenceRefs).slice(0, 4000),
    observation: textValue(source.observation).slice(0, 4000),
    decision: decision === "keep" || decision === "modify" || decision === "pause" || decision === "reject"
      ? decision
      : "",
    rationale: textValue(source.rationale).slice(0, 4000),
    nextAction: textValue(source.nextAction).slice(0, 2000),
    owner: textValue(source.owner).slice(0, 200),
    confirmation: source.confirmation === "confirmed" ? "confirmed" : "pending",
    prototype: normalizePrototype(source.prototype),
    market: textValue(source.market).slice(0, 2),
    l1SnapshotSha256:
      typeof source.l1SnapshotSha256 === "string" && /^[0-9a-f]{64}$/.test(source.l1SnapshotSha256)
        ? source.l1SnapshotSha256
        : null,
  }
  if (normalized.confirmation === "confirmed" && !canConfirmValidationRound(normalized)) {
    normalized.confirmation = "pending"
  }
  return normalized
}

export function normalizeValidationRounds(raw: unknown): ValidationRound[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map(normalizeValidationRound)
    .filter((round) => round.id && round.claimId)
    .slice(0, 200)
}

export function missingValidationRoundFields(round: ValidationRound): string[] {
  const required: Array<{ key: keyof ValidationRound; label: string }> = [
    { key: "createdAt", label: "记录时间" },
    { key: "scenario", label: "场景" },
    { key: "query", label: "商品" },
    { key: "claimId", label: "claim_id" },
    { key: "hypothesisTitle", label: "假设标题" },
    { key: "evidenceRefs", label: "证据 ID / 链接" },
    { key: "observation", label: "本轮观察" },
    { key: "decision", label: "运营决定" },
    { key: "rationale", label: "决定理由" },
    { key: "nextAction", label: "下一步" },
    { key: "owner", label: "负责人" },
  ]
  const missing = required.filter(({ key }) => !String(round[key]).trim()).map(({ label }) => label)
  if (round.createdAt) {
    const created = new Date(round.createdAt)
    if (Number.isNaN(created.getTime()) || created.getTime() > Date.now() + 60_000) {
      missing.push("记录时间（不得晚于当前时间）")
    }
  }
  if (round.prototype && round.confirmation === "confirmed") {
    const prototypeFields: Array<{ key: keyof PrototypeObservation; label: string }> = [
      { key: "participantCode", label: "原型参与者编号" },
      { key: "order", label: "原型测试顺序" },
      { key: "itemsLoaded", label: "原型装载观察" },
      { key: "retrieval", label: "原型取物观察" },
      { key: "friction", label: "原型麻烦点" },
    ]
    missing.push(
      ...prototypeFields.filter(({ key }) => !round.prototype?.[key]?.trim()).map(({ label }) => label),
    )
  }
  if (round.scenario === "real" && round.confirmation === "confirmed") {
    if (round.market.toLowerCase() !== "de") missing.push("市场（real 轮次须为 de）")
    if (!/^[0-9a-f]{64}$/.test(round.l1SnapshotSha256 ?? "")) {
      missing.push("L1 快照指纹（real 轮次须绑定当前证据版本）")
    }
  }
  return missing
}

export function validationRoundErrors(round: ValidationRound): string[] {
  const errors: string[] = []
  const combined = [
    round.query,
    round.hypothesisTitle,
    round.evidenceRefs,
    round.observation,
    round.rationale,
    round.nextAction,
    round.owner,
    round.prototype?.participantCode,
    round.prototype?.itemsLoaded,
    round.prototype?.retrieval,
    round.prototype?.friction,
  ].join("\n")
  if (/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(combined)) {
    errors.push("记录含邮箱，请剔除后再保存")
  }
  if (/(?<!\d)(?:\+|00)\d[\d\s().-]{7,}\d/.test(combined)) {
    errors.push("记录含电话号码，请剔除后再保存")
  }
  if (round.id && !/^round-[a-z0-9-]{4,90}$/.test(round.id)) {
    errors.push("轮次 ID 非法")
  }
  return errors
}

export function canConfirmValidationRound(round: ValidationRound): boolean {
  return missingValidationRoundFields(round).length === 0 && validationRoundErrors(round).length === 0
}

export function hasValidationRoundContent(round: ValidationRound): boolean {
  return Boolean(
    round.observation ||
    round.decision ||
    round.rationale ||
    round.nextAction ||
    round.owner ||
    round.prototype?.participantCode ||
    round.prototype?.itemsLoaded ||
    round.prototype?.retrieval ||
    round.prototype?.friction,
  )
}
