import type { ClaimDecisionSummary } from "../composables/useEvidence"
import type { ValidEvidenceCard } from "./evidence-schema"
import type { Hypothesis, HypothesisStatus } from "./hypotheses"

export interface InterviewQuestion {
  text: string
  why: string
}

export interface CopyVariant {
  label: "A" | "B"
  text: string
}

export interface EvidenceBasis {
  mode: "empty" | "demo" | "real" | "mixed"
  summary: string
  cards: ValidEvidenceCard[]
}

export interface ValidationPlan {
  hypothesisTitle: string
  status: HypothesisStatus
  summary: string
  notice: string
  basis: EvidenceBasis
  interviews: InterviewQuestion[]
  prototypeTitle: string
  prototypeSteps: string[]
  copyVariants: CopyVariant[]
  sampleCriteria: string[]
  nextSteps: string[]
}

export const SAMPLING_BIAS = [
  "评论与访谈均为非随机、自选择样本；可能存在激励评价、幸存者偏差、极端体验更容易被表达的问题。",
  "按语言、日期、关键词、是否已验证购买与来源去重；重复摘录不重复计数，并检查是否遗漏差评、不同尺寸与使用周期。",
  "知乎 L2 是从业者二手经验，不等于德国消费者；跨来源问题只能形成待验证假设，不能进入 L1 偏好判定。",
  "演示数据全部为模拟示例，仅验证流程，不构成真实市场证据；结论限定为当前样本、当前场景与当前时间窗口。",
]

type PlanDomain = "capacity" | "features" | "price" | "generic"

function inferDomain(hypothesis: Hypothesis): PlanDomain {
  if (hypothesis.id === "capacity" || /容量|尺寸|便携|承重|volume|capacity|size/i.test(hypothesis.title)) {
    return "capacity"
  }
  if (hypothesis.id === "features" || /隔层|功能|分区|口袋|拉链|feature|compartment|pocket/i.test(hypothesis.title)) {
    return "features"
  }
  if (hypothesis.id === "price" || /价格|低价|性价比|便宜|price|cheap|value/i.test(hypothesis.title)) {
    return "price"
  }
  return "generic"
}

function buildInterviews(domain: PlanDomain, hypothesis: Hypothesis, product: string): InterviewQuestion[] {
  if (domain === "features") {
    return [
      {
        text: "请回忆最近一次收纳或打包：哪些物品必须分开，哪些物品反而被隔层卡住？",
        why: "定位「功能越多越好」的支持场景与操作负担",
      },
      {
        text: "如果只能选多隔层或开放空间，您会先放什么、先取什么？为什么？",
        why: "把分歧转成可观察的装载与取物任务",
      },
      {
        text: hypothesis.probe || `使用${product}时，更多功能在什么情况下会帮倒忙？`,
        why: "追问当前假设的反例与边界条件",
      },
    ]
  }
  if (domain === "capacity") {
    return [
      {
        text: `您最近一次使用${product}实际带了什么？哪件物品最占空间？`,
        why: "用真实物品清单校准容量需求，不依赖笼统的「越大越好」",
      },
      {
        text: "容量大到什么程度会让您放弃携带？请描述一次装不下或太笨重的经历。",
        why: "寻找容量收益与便携性损失之间的边界",
      },
      {
        text: hypothesis.probe || "如果只能保留一个尺寸或容量参数，您最需要哪一个？",
        why: "把偏好转成可核实的产品参数",
      },
    ]
  }
  if (domain === "price") {
    return [
      {
        text: "价格、耐用性和退换保障，哪个最影响您的决定？请按重要性排序。",
        why: "检验低价是否真的是核心购买理由",
      },
      {
        text: "便宜到什么程度会让您怀疑质量？您愿意为什么多付？",
        why: "识别价格阈值与质量联想，不预设消费者行为",
      },
      {
        text: hypothesis.probe || "请回忆一次因为价格放弃购买的经历，当时替代品是什么？",
        why: "用真实选择解释价格权衡",
      },
    ]
  }
  return [
    {
      text: `请回忆一次与${product}有关的真实使用或购买经历，当时发生了什么？`,
      why: "先取得具体行为与场景，避免复述营销卖点",
    },
    {
      text: `什么情况下「${hypothesis.title}」会帮倒忙？请给出一个具体例子。`,
      why: "主动寻找反例与适用边界",
    },
    {
      text: hypothesis.probe || "如果只能改变一个地方，您最希望改变什么？",
      why: "把模糊偏好转成下一步可验证问题",
    },
  ]
}

function buildPrototype(domain: PlanDomain): { title: string; steps: string[] } {
  if (domain === "features") {
    return {
      title: "原型测试：多隔层 vs 开放空间",
      steps: [
        "采用同组受试者内对照：每位参与者分别使用「多隔层」与「开放空间」两个原型，随机或交叉平衡先后顺序，避免顺序效应。",
        "两个原型使用同一包体、同一组物品（换洗衣物、电子产品、线材、洗护用品）与同一任务卡；只改变内部结构。",
        "记录装什么：每类物品放入哪个区域、是否折叠或挤压、是否有物品放不下；以物品清单和放置照片编码记录。",
        "记录怎么取：请参与者取回袜子、充电线和洗护用品，记录首次拿取是否成功、开合次数、翻找步数、是否倒空包体、取物耗时。",
        "记录麻烦程度：每次任务后记录 1–7 分操作难度、1–7 分满意度，并追问「哪里麻烦、为什么」；同时观察是否卡住拉链、物品互相遮挡。",
      ],
    }
  }
  if (domain === "capacity") {
    return {
      title: "概念 / 原型测试：大容量 vs 轻便尺寸",
      steps: [
        "同一组参与者分别查看「大容量」与「轻便尺寸」两版概念，顺序随机或交叉平衡。",
        "给出同一组真实出行物品，请参与者判断能否装下、是否愿意携带，并说明取舍。",
        "有条件时使用同材质、不同尺寸的实物包体完成装载任务；记录装不下、挤压、过重和取物困难。",
        "对照标称容量、外部尺寸与重量，检查消费者理解的「大」是否与团队参数一致。",
      ],
    }
  }
  if (domain === "price") {
    return {
      title: "概念测试：低价表达 vs 价值表达",
      steps: [
        "保持商品、图片、规格与优惠一致，只改变首屏价值表达，避免把价格差异混入结论。",
        "A 版突出可核实低价，B 版突出可核实的材料、耐用性或退换保障；商品不具备的承诺不得写入。",
        "先让参与者自由选择并说明原因，再追问什么信息会让他们放弃下单。",
        "记录选择、信任度与质量疑虑；该结果只用于筛选文案方向，不等于真实市场提升。",
      ],
    }
  }
  return {
    title: "概念 / 原型测试：假设成立 vs 替代方案",
    steps: [
      "A 版直接表达当前假设，B 版提供替代价值或使用场景；除被测表达外保持其他信息一致。",
      "让目标用户完成同一任务，记录选择理由、困惑点与反对原因。",
      "把观察结果按使用场景编码，再决定保留、修改或拒绝该假设。",
    ],
  }
}

function buildCopyVariants(domain: PlanDomain, hypothesis: Hypothesis): CopyVariant[] {
  if (domain === "features") {
    return [
      { label: "A", text: "「多隔层分区，线材衣物各就各位」" },
      { label: "B", text: "「开放空间，厚衣物也能轻松装入」" },
    ]
  }
  if (domain === "capacity") {
    return [
      { label: "A", text: "「大容量，一包装齐出行物品」" },
      { label: "B", text: "「量化尺寸与容量，适配你的出行场景」" },
    ]
  }
  if (domain === "price") {
    return [
      { label: "A", text: "「更低价格，减少预算压力」" },
      { label: "B", text: "「耐用材料与退换保障，买得更放心」" },
    ]
  }
  return [
    { label: "A", text: `「${hypothesis.title}」` },
    { label: "B", text: "「先说明使用场景与可核实参数，再由用户判断是否值得」" },
  ]
}

function statusSummary(status: HypothesisStatus): string {
  if (status === "insufficient") {
    return "当前证据不足：先补目标市场 L1 一手反馈；访谈与原型只用于形成问题和解释行为，不能替代偏好证据。"
  }
  if (status === "conflicting") {
    return "当前样本内存在分歧：先按使用场景解释支持与反对，再用同组原型测试观察装取行为，不把分歧调和成单一结论。"
  }
  if (status === "supported") {
    return "当前样本已有有限支持：先扩大样本、检查差评与使用场景，再进入两版文案测试；不得表述为总体市场偏好。"
  }
  return "当前样本多数反对：先定位反对集中的具体损失与场景，修正或放弃该卖点，再测试替代方案。"
}

function nextSteps(status: HypothesisStatus, hypothesis: Hypothesis): string[] {
  if (status === "insufficient") {
    return [
      `为「${hypothesis.title}」补充目标市场授权 L1 评论，保留原始评论 ID、原文、日期、来源与授权依据。`,
      "访谈 5–8 位目标用户，只记录使用场景、反对原因与待验证问题。",
      "每条卖点达到 n≥30 的去重后有极性样本后，再判断是否进入 A/B。",
    ]
  }
  if (status === "conflicting") {
    return [
      "保留支持与反对原文，按使用场景编码分歧来源。",
      "执行同组受试者内原型测试，记录装什么、怎么取、哪里麻烦。",
      "场景解释与样本复核后，才选择两版文案做 A/B。",
    ]
  }
  if (status === "supported") {
    return [
      "扩大目标市场 L1 样本，检查差评、变体、日期与来源偏差。",
      "用访谈复核支持场景，再测试两版文案。",
      "预先登记指标与样本量，不把小样本或模拟结果当作市场效果。",
    ]
  }
  return [
    "定位反对原文中的具体损失与场景。",
    "修改或放弃该卖点，另立可验证假设。",
    "用原型或概念测试比较替代方案，再考虑 A/B。",
  ]
}

function buildBasis(
  support: ValidEvidenceCard[],
  oppose: ValidEvidenceCard[],
  decision: ClaimDecisionSummary,
): EvidenceBasis {
  const canonicalSupport = support.filter((card) => card.dedup?.is_canonical !== false)
  const canonicalOppose = oppose.filter((card) => card.dedup?.is_canonical !== false)
  const canonical = [...canonicalSupport, ...canonicalOppose]
  const demoCount = canonical.filter((card) => card.is_demo_data).length
  const realCount = canonical.length - demoCount
  const mode = canonical.length === 0 ? "empty" : realCount === 0 ? "demo" : demoCount === 0 ? "real" : "mixed"
  const summary = `L1 卡 ${decision.n_l1} 条；去重后支持 ${canonicalSupport.length} 条、反对 ${canonicalOppose.length} 条；有极性样本 n=${decision.n_polarized}。`
  return {
    mode,
    summary,
    cards: [...canonicalSupport.slice(0, 2), ...canonicalOppose.slice(0, 2)],
  }
}

export function buildValidationPlan(input: {
  hypothesis: Hypothesis
  status: HypothesisStatus
  product: string
  decision: ClaimDecisionSummary
  support: ValidEvidenceCard[]
  oppose: ValidEvidenceCard[]
}): ValidationPlan {
  const domain = inferDomain(input.hypothesis)
  const prototype = buildPrototype(domain)
  const basis = buildBasis(input.support, input.oppose, input.decision)
  const notice =
    basis.mode === "demo"
      ? "当前依据全部为模拟示例；以下计划只用于演示流程，不构成真实消费者证据或市场效果结论。"
      : basis.mode === "empty"
        ? "当前没有可引用的 L1 支持/反对原文；先补证据，计划中的问题与文案均为待测试草案。"
        : "以下文案均为待测试草案，不代表已测得市场效果；上线前必须与真实商品参数和授权证据核对。"

  return {
    hypothesisTitle: input.hypothesis.title,
    status: input.status,
    summary: statusSummary(input.status),
    notice,
    basis,
    interviews: buildInterviews(domain, input.hypothesis, input.product),
    prototypeTitle: prototype.title,
    prototypeSteps: prototype.steps,
    copyVariants: buildCopyVariants(domain, input.hypothesis),
    sampleCriteria: [
      "访谈：先做 5–8 位目标用户的探索性访谈，记录原话与场景，不把该小样本外推为总体偏好。",
      "原型测试：8–12 名目标用户做同组受试者内对照；报告任务完成率、取物耗时、困难评分与具体反对原因。",
      "A/B 测试：先按基线转化率与最小可检测效应计算样本量并登记主要指标；样本不足或置信区间跨 0 时，只报告不确定，不宣布胜出。",
      "所有待测试文案必须与实际商品能力一致；低价、材料、保障、容量与尺寸等承诺需有可核实依据。",
    ],
    nextSteps: nextSteps(input.status, input.hypothesis),
  }
}
