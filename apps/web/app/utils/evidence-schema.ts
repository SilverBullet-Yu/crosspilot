/**
 * 证据卡契约校验 —— 对应 packages/contracts/evidence-card.schema.json。
 *
 * 契约规则（docs/CONSTRAINTS.md 第三节）：
 *   六必现字段 excerpt / source_url / language / published_on / level / sample_size，
 *   缺任一字段的证据卡不得渲染 —— 前端渲染占位说明，绝不静默丢弃或降级为灰字。
 * 补充规则（同 schema）：
 *   - additionalProperties: false，出现契约外字段同样视为校验不通过；
 *   - level 仅允许 L1/L2/L3；stance 仅允许 support/oppose/insufficient；
 *   - stance 与 is_demo_data 在 schema/领域模型中带默认值，缺失时分别按
 *     "insufficient" 与 false 处理（domain/evidence.py 的 EvidenceCard 默认值）；
 *   - sample_size 键必须存在（可为 null），null 时卡面必须标注「样本量未知·有偏差风险」。
 */

/** 证据层级（domain/evidence.py: EvidenceLevel） */
export type EvidenceLevel = "L1" | "L2" | "L3"

/** 立场（domain/evidence.py: Stance） */
export type EvidenceStance = "support" | "oppose" | "insufficient"

/** 校验通过的证据卡（六必现字段齐备，可渲染） */
export interface ValidEvidenceCard {
  excerpt: string
  source_url: string
  language: string
  published_on: string
  level: EvidenceLevel
  sample_size: number | null
  stance: EvidenceStance
  is_demo_data: boolean
}

/** 校验不通过的卡：保存原因与原始数据，供占位说明展示 */
export interface InvalidEvidenceCard {
  errors: string[]
  raw: Record<string, unknown>
}

export type CardValidation =
  | { ok: true; card: ValidEvidenceCard }
  | { ok: false; invalid: InvalidEvidenceCard }

/** schema 允许的全部键（additionalProperties: false） */
const ALLOWED_KEYS = new Set([
  "excerpt",
  "source_url",
  "language",
  "published_on",
  "level",
  "sample_size",
  "stance",
  "is_demo_data",
])

/** 判定日期字符串是否为 YYYY-MM-DD 且真实存在（防止 V8 把 2026-02-30 滚动解析为 03-02） */
function isIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [y, m, d] = value.split("-").map(Number)
  const parsed = new Date(Date.UTC(y, m - 1, d))
  return (
    parsed.getUTCFullYear() === y &&
    parsed.getUTCMonth() === m - 1 &&
    parsed.getUTCDate() === d
  )
}

/** 判定来源链接是否可直接打开（schema: format=uri，仅接受 http/https） */
function isHttpUrl(value: unknown): value is string {
  return typeof value === "string" && /^https?:\/\/\S+$/i.test(value)
}

/** 判定非空字符串（schema: excerpt minLength=1） */
function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

/**
 * 按 schema 校验单张证据卡。
 * 返回 { ok: true, card } 或 { ok: false, invalid }，调用方据此渲染或渲染占位说明。
 */
export function validateEvidenceCard(raw: unknown): CardValidation {
  const errors: string[] = []
  const rawObj =
    typeof raw === "object" && raw !== null
      ? (raw as Record<string, unknown>)
      : null

  if (!rawObj) {
    return { ok: false, invalid: { errors: ["非对象类型，无法作为证据卡"], raw: {} } }
  }

  // additionalProperties: false —— 契约外字段一律拒绝，防止后端漂移
  const unknownKeys = Object.keys(rawObj).filter((k) => !ALLOWED_KEYS.has(k))
  if (unknownKeys.length > 0) {
    errors.push(`含契约外字段: ${unknownKeys.join(", ")}`)
  }

  // 六必现字段逐一校验（CONSTRAINTS 第三节）
  if (!isNonEmptyString(rawObj.excerpt)) errors.push("缺少必现字段 excerpt（原文摘录）")
  if (!isHttpUrl(rawObj.source_url)) errors.push("缺少或非法必现字段 source_url（须为可打开的 http/https 链接）")
  if (!isNonEmptyString(rawObj.language)) errors.push("缺少必现字段 language（语言，BCP-47）")
  if (!isIsoDate(rawObj.published_on)) errors.push("缺少或非法必现字段 published_on（须为 YYYY-MM-DD）")
  if (rawObj.level !== "L1" && rawObj.level !== "L2" && rawObj.level !== "L3") {
    errors.push("缺少或非法必现字段 level（仅允许 L1/L2/L3）")
  }
  // sample_size 键必须存在，值可为 null 或非负整数
  if (!("sample_size" in rawObj)) {
    errors.push("缺少必现字段 sample_size（键必须存在，可为 null）")
  } else {
    const v = rawObj.sample_size
    if (v !== null && !(typeof v === "number" && Number.isInteger(v) && v >= 0)) {
      errors.push("sample_size 非法（须为非负整数或 null）")
    }
  }

  if (errors.length > 0) {
    return { ok: false, invalid: { errors, raw: rawObj } }
  }

  // 带默认值的两个可选字段：缺失时按 schema/领域模型默认值处理
  const stance = rawObj.stance ?? "insufficient"
  if (stance !== "support" && stance !== "oppose" && stance !== "insufficient") {
    return {
      ok: false,
      invalid: { errors: [`stance 非法（仅允许 support/oppose/insufficient），实际: ${String(stance)}`], raw: rawObj },
    }
  }
  const isDemo = rawObj.is_demo_data ?? false
  if (typeof isDemo !== "boolean") {
    return {
      ok: false,
      invalid: { errors: ["is_demo_data 非法（须为布尔值）"], raw: rawObj },
    }
  }

  return {
    ok: true,
    card: {
      excerpt: rawObj.excerpt as string,
      source_url: rawObj.source_url as string,
      language: rawObj.language as string,
      published_on: rawObj.published_on as string,
      level: rawObj.level as EvidenceLevel,
      sample_size: rawObj.sample_size as number | null,
      stance,
      is_demo_data: isDemo,
    },
  }
}
