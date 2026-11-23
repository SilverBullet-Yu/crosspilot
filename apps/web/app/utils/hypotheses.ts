/**
 * 预置企业假设与证据归属 —— 对应项目方案 4.3「演示输出」三条假设。
 *
 * 归属说明：证据卡契约（evidence-card.schema.json，additionalProperties=false）
 * 不允许卡片携带「假设 ID」字段，因此前端用关键词匹配把卡片归到假设；
 * 未匹配到任何假设的卡进「未归属证据」组，绝不静默丢弃。
 *
 * 每条假设的状态为**组级展示状态**（硬约束 1：仅 L1 计入）——不是判定管道输出。
 * ADR-0005（2026-11-22）：判定唯一出口是包络 stance 的四值 DecisionState
 * （Wilson 区间 + 门禁公式）；假设组内样本量低于判定门禁，套用判定公式会
 * 塌缩为 insufficient，故组级只做布尔并集展示：有支持有反对 → conflict（红），
 * 仅支持 → support（绿），无 L1 → insufficient（黄）。三态禁止灰字弱化。
 */
import type { ValidEvidenceCard } from "./evidence-schema"

export interface Hypothesis {
  id: string
  /** 假设原文（方案 4.3） */
  title: string
  /** 系统应提出的核实问题（方案 4.3） */
  probe: string
  /** 归属关键词：拉丁字母词按「词边界+前缀」匹配，中文按包含匹配（不区分大小写） */
  keywords: string[]
}

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

/**
 * 假设状态：与横幅三态一致（绿/红/黄），禁止灰字弱化。
 * 组级标签描述**组内构成**，不复用判定带结论词——避免 limited 场景
 * （判定=已有有限支持/绿）与组级「证据相互冲突」红字打架：
 * 判定唯一出口是包络 stance（ADR-0005 R1），组级只是展示口径。
 */
export type HypothesisStatus = "support" | "conflict" | "insufficient"

export const STATUS_META: Record<HypothesisStatus, { label: string; cls: string }> = {
  support: { label: "有一手支持", cls: "status--ok" },
  conflict: { label: "支持 / 反对并存", cls: "status--bad" },
  insufficient: { label: "缺 L1 一手反馈", cls: "status--warn" },
}

/** 单条假设下的三组证据（支持/相反/缺失） */
export interface HypothesisGroups {
  hypothesis: Hypothesis
  support: ValidEvidenceCard[]
  oppose: ValidEvidenceCard[]
  /** 缺失证据组：不支撑结论的卡（L2/L3、无立场卡），展示时逐一标注「不支撑结论」 */
  missing: ValidEvidenceCard[]
  /** 组级展示状态（非判定管道输出，见文件头注释） */
  status: HypothesisStatus
  /** 状态细分说明（用于徽标下的小字说明，如「仅存在反对证据」） */
  statusNote: string
}

/**
 * 拉丁字母关键词 → 词边界+前缀正则；中文关键词 → 包含匹配。
 * 注意：不用正则的 i 标志 —— 非 unicode 模式下 V8 会把模式里的 ß 折叠成 ss，
 * 导致 größe / reißverschluss 等含 ß 关键词永远失配。改为两侧先 toLowerCase
 * 再用无标志正则匹配（ß.toLowerCase() 仍为 ß，1:1 无展开）。
 */
function matchesKeyword(text: string, keyword: string): boolean {
  if (/[a-zäöüß]/i.test(keyword)) {
    const lowerKeyword = keyword.toLowerCase()
    const re = new RegExp(`\\b${lowerKeyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`)
    return re.test(text.toLowerCase())
  }
  return text.toLowerCase().includes(keyword.toLowerCase())
}

/** 把一张卡归到假设；未命中任何关键词返回 null */
export function matchHypothesis(card: ValidEvidenceCard): Hypothesis | null {
  const text = `${card.excerpt} ${card.source_url}`
  for (const h of HYPOTHESES) {
    if (h.keywords.some((kw) => matchesKeyword(text, kw))) return h
  }
  return null
}

/** 组级布尔并集展示（仅 L1 计入；不套 Wilson 门禁——组内样本低于判定门禁） */
export function resolveHypothesisStatus(cards: ValidEvidenceCard[]): {
  status: HypothesisStatus
  statusNote: string
} {
  const l1 = cards.filter((c) => c.level === "L1")
  const hasSupport = l1.some((c) => c.stance === "support")
  const hasOppose = l1.some((c) => c.stance === "oppose")
  if (hasSupport && hasOppose) return { status: "conflict", statusNote: "L1 一手反馈同时出现支持与反对" }
  if (hasSupport) {
    const l1Count = l1.length
    return {
      status: "support",
      statusNote: `仅 ${l1Count} 张 L1 卡支持，样本有限`,
    }
  }
  if (hasOppose) return { status: "conflict", statusNote: "仅存在反对证据，缺少支持侧对照" }
  return { status: "insufficient", statusNote: "无 L1 一手消费者反馈（目标市场零样本）" }
}

/** 把合法证据卡按假设分组（支持/相反/缺失三组），未命中的进 unmatched */
export function groupCardsByHypothesis(cards: ValidEvidenceCard[]): {
  groups: HypothesisGroups[]
  unmatched: ValidEvidenceCard[]
} {
  const groups: HypothesisGroups[] = HYPOTHESES.map((h) => ({
    hypothesis: h,
    support: [],
    oppose: [],
    missing: [],
    status: "insufficient",
    statusNote: "",
  }))
  const unmatched: ValidEvidenceCard[] = []

  for (const card of cards) {
    const h = matchHypothesis(card)
    const idx = h ? groups.findIndex((g) => g.hypothesis.id === h.id) : -1
    if (idx === -1) {
      unmatched.push(card)
      continue
    }
    if (card.stance === "support") groups[idx].support.push(card)
    else if (card.stance === "oppose") groups[idx].oppose.push(card)
    else groups[idx].missing.push(card)
  }

  for (const g of groups) {
    const { status, statusNote } = resolveHypothesisStatus([...g.support, ...g.oppose])
    g.status = status
    g.statusNote = statusNote
  }
  return { groups, unmatched }
}
