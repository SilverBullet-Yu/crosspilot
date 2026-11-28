export type OperatorTrialConfirmation = "pending" | "confirmed"

export interface OperatorTrialRecord {
  trialDate: string
  operatorRole: string
  productMarket: string
  decision: string
  evidenceRefs: string
  prototypeObservation: string
  nextAction: string
  confirmation: OperatorTrialConfirmation
  sourceScenario: string
  sourceRoundId: string
  isDemo: boolean
}

export function emptyOperatorTrial(): OperatorTrialRecord {
  return {
    trialDate: "",
    operatorRole: "",
    productMarket: "旅行收纳包 × 德国",
    decision: "",
    evidenceRefs: "",
    prototypeObservation: "",
    nextAction: "",
    confirmation: "pending",
    sourceScenario: "",
    sourceRoundId: "",
    isDemo: false,
  }
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

export function normalizeOperatorTrialRecord(raw: unknown): OperatorTrialRecord {
  const source = typeof raw === "object" && raw !== null ? raw as Record<string, unknown> : {}
  const normalized: OperatorTrialRecord = {
    trialDate: textValue(source.trialDate),
    operatorRole: textValue(source.operatorRole),
    productMarket: textValue(source.productMarket) || emptyOperatorTrial().productMarket,
    decision: textValue(source.decision),
    evidenceRefs: textValue(source.evidenceRefs),
    prototypeObservation: textValue(source.prototypeObservation),
    nextAction: textValue(source.nextAction),
    confirmation: source.confirmation === "confirmed" ? "confirmed" : "pending",
    sourceScenario: textValue(source.sourceScenario).slice(0, 40),
    sourceRoundId: textValue(source.sourceRoundId).slice(0, 100),
    isDemo:
      source.isDemo === true ||
      source.sourceScenario === "conflict" ||
      source.sourceScenario === "limited",
  }
  if (normalized.confirmation === "confirmed" && !canConfirmOperatorTrial(normalized)) {
    normalized.confirmation = "pending"
  }
  return normalized
}

export function missingOperatorTrialFields(record: OperatorTrialRecord): string[] {
  const required: Array<{ key: keyof OperatorTrialRecord; label: string }> = [
    { key: "trialDate", label: "试用日期" },
    { key: "operatorRole", label: "运营角色" },
    { key: "productMarket", label: "真实商品与市场" },
    { key: "evidenceRefs", label: "证据 ID / 链接" },
    { key: "decision", label: "运营决定" },
    { key: "prototypeObservation", label: "原型测试观察" },
    { key: "nextAction", label: "下一步与负责人" },
  ]
  const missing = required
    .filter(({ key }) => !record[key].trim())
    .map(({ label }) => label)
  if (record.trialDate) {
    const parsed = new Date(`${record.trialDate}T00:00:00`)
    const parsedIso = Number.isNaN(parsed.getTime())
      ? ""
      : `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-${String(parsed.getDate()).padStart(2, "0")}`
    const today = new Date()
    const todayIso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`
    if (parsedIso !== record.trialDate || record.trialDate > todayIso) {
      missing.push("试用日期（须为不晚于今天的有效日期）")
    }
  }
  if (!/(?:^|;\s*)(?:review_id=)?[^:;\s]{1,100}:\s*https?:\/\/[^\s;]+/i.test(record.evidenceRefs)) {
    missing.push("证据依据（需至少一组 review_id: source_url）")
  }
  const combined = [
    record.operatorRole,
    record.productMarket,
    record.evidenceRefs,
    record.decision,
    record.prototypeObservation,
    record.nextAction,
  ].join("\n")
  if (/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(combined)) {
    missing.push("记录含邮箱，请剔除")
  }
  if (/(?<!\d)(?:\+|00)\d[\d\s().-]{7,}\d/.test(combined)) {
    missing.push("记录含电话号码，请剔除")
  }
  if (record.isDemo) {
    missing.push("演示轮次不得标记为真人运营确认")
  }
  return missing
}

export function hasOperatorTrialContent(record: OperatorTrialRecord): boolean {
  return Boolean(
    record.trialDate ||
    record.operatorRole ||
    record.evidenceRefs ||
    record.decision ||
    record.prototypeObservation ||
    record.nextAction,
  )
}

export function canConfirmOperatorTrial(record: OperatorTrialRecord): boolean {
  return missingOperatorTrialFields(record).length === 0
}
