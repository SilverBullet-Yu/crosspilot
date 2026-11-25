<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

type SectionId = "layers" | "decision" | "sources" | "boundaries"
type DetailId =
  | "l1"
  | "l2"
  | "l3"
  | "demo"
  | "gate"
  | "wilson"
  | "conflict"
  | "dedup"
  | "amazon"
  | "zhihu"
  | "official"
  | "fixtures"
  | "scope"
  | "unknown"
  | "locale"
  | "action"

const activeSection = ref<SectionId>("layers")
const activeDetail = ref<DetailId>("l1")
const closeButton = ref<HTMLButtonElement | null>(null)

const sections: Array<{ id: SectionId; no: string; label: string; title: string; intro: string }> = [
  {
    id: "layers",
    no: "01",
    label: "证据分层",
    title: "不是所有证据，都有同等发言权。",
    intro: "证据层级决定它能回答什么问题。只有目标市场的一手消费者反馈，才能直接支撑偏好判断。",
  },
  {
    id: "decision",
    no: "02",
    label: "判定口径",
    title: "结论由规则产生，不由模型自由发挥。",
    intro: "先去重，再过样本门禁，最后计算 Wilson 95% 区间。每一步都保留可追溯数据。",
  },
  {
    id: "sources",
    no: "03",
    label: "来源与范围",
    title: "每条证据，都要能回到它的上下文。",
    intro: "来源、语言、日期、样本量与演示标识共同构成证据边界，避免把局部反馈误当成市场共识。",
  },
  {
    id: "boundaries",
    no: "04",
    label: "输出边界",
    title: "系统给出判断，也明确判断不能走多远。",
    intro: "证据不足、样本未知、语言与市场错位都必须显式呈现，并把结果转成下一步验证。",
  },
]

const details: Record<DetailId, { title: string; tag: string; body: string; points: string[] }> = {
  l1: {
    title: "L1 · 一手消费者反馈",
    tag: "可支撑偏好判定",
    body: "来自目标市场消费者对商品的直接反馈，例如品牌授权评论导出。只有当支持与反对样本达到门禁后，才进入区间判定。",
    points: ["保留原文摘录与来源链接", "标明语言、日期与样本量", "演示回填不能伪装成真实 L1"],
  },
  l2: {
    title: "L2 · 二手转述与从业经验",
    tag: "只生成待验证问题",
    body: "中文从业者经验、访谈转述与二手资料可以帮助发现问题，但不能单独证明海外消费者偏好。",
    points: ["不参与支持 / 反对计数", "输出必须标记为待验证假设", "保留来源属性与转述边界"],
  },
  l3: {
    title: "L3 · 宏观与监管语境",
    tag: "只提供背景",
    body: "监管、贸易与市场统计用于解释外部环境，不直接代表个体消费者的购买动机。",
    points: ["不参与偏好判定", "用于补充风险与市场背景", "必须链接到官方或授权来源"],
  },
  demo: {
    title: "演示数据 · Mock",
    tag: "显式标识",
    body: "用于体验验证流程的模拟回填。演示卡使用斜纹底与角标，并与真实反馈分组呈现，绝不混排。",
    points: ["每张卡都有演示标识", "场景与横幅同时提示 Mock", "不得用于真实市场结论"],
  },
  gate: {
    title: "样本门禁",
    tag: "n ≥ 30",
    body: "去重后有极性样本不足 30 时，系统直接输出「缺少有效数据」，不进入比例判断。",
    points: ["门禁不通过时区间为空", "避免小样本制造虚假确定性", "补样优先于改写卖点"],
  },
  wilson: {
    title: "Wilson 95% 区间",
    tag: "区间判定",
    body: "用区间而不是单点比例表达不确定性。n=30 时，份额需约达到 68%，下界才越过 0.5 决定线。",
    points: ["支持与反对分别计算区间", "保留 n 与区间端点", "有限支持仍需扩大样本复核"],
  },
  conflict: {
    title: "证据相互冲突",
    tag: "保留矛盾",
    body: "当支持与反对区间重叠，系统不做调和，而是把两侧原文并排呈现，要求进一步验证分歧场景。",
    points: ["支持 / 反对同时可见", "不删除少数意见", "下一步转向访谈与原型测试"],
  },
  dedup: {
    title: "先去重，再计数",
    tag: "R2",
    body: "重复评论不虚增一致性。同一去重簇只计一条，重复数量与簇数在判定追溯中公开。",
    points: ["去重先于样本统计", "保留 canonical 卡", "摘要显示去重前后的差异"],
  },
  amazon: {
    title: "Amazon Reviews 2023",
    tag: "评论数据源",
    body: "用于消费者反馈检索与证据卡构建。数据使用必须遵守原数据集许可，商业化路径下按白名单控制。",
    points: ["保留来源 URL 与日期", "样本量未知时显示偏差风险", "遵守许可与再发布限制"],
  },
  zhihu: {
    title: "知乎 · L2 经验",
    tag: "中文侧经验",
    body: "只做检索、匿名化摘录与链接回源，不建立全文库。内容只用于生成待验证问题。",
    points: ["摘录长度受限", "作者匿名化并剔除 PII", "不进入偏好判定"],
  },
  official: {
    title: "官方公开数据",
    tag: "L3 语境",
    body: "Safety Gate、Eurostat、Comext 等来源提供监管与贸易背景，帮助识别外部风险。",
    points: ["逐源许可入档", "保留抓取时间与 provenance", "不把宏观数据当成个体动机"],
  },
  fixtures: {
    title: "本地 fixtures",
    tag: "离线演示",
    body: "三个场景使用归一化后的本地夹具，字段与真实 API 契约一致，后端不可用时也能完整演示。",
    points: ["real / conflict / limited", "统一经过证据卡契约校验", "不静默忽略非法卡"],
  },
  scope: {
    title: "市场范围",
    tag: "德国固定场景",
    body: "当前演示边界为非电器旅行收纳包 → 德国市场 → 详情页首屏卖点验证。换市场需要重新定义证据范围。",
    points: ["语言不等于国家", "市场变化不能沿用旧结论", "搜索词变化会重新拉取证据"],
  },
  unknown: {
    title: "样本量未知",
    tag: "偏差风险",
    body: "当证据卡没有样本量时，系统显示「样本量未知 · 有偏差风险」，不把未知偷偷当作 1。",
    points: ["六必现字段缺一不可", "未知样本保留警示", "必要时拒绝渲染非法卡"],
  },
  locale: {
    title: "语言与本地化",
    tag: "正式测试前处理",
    body: "英文评论不代表特定国家，A/B 文案在正式测试前仍需本地化，并保持受众与素材一致。",
    points: ["保留语言与地区未知标识", "文案标注为待测试草案", "比较选择及其理由"],
  },
  action: {
    title: "从判断到行动",
    tag: "下一步验证",
    body: "每个结论都转化为访谈问题、A/B 文案或行动清单，确保工作台不止于展示数据。",
    points: ["先验证分歧场景", "记录执行状态", "复制完整验证计划"],
  },
}

const sectionDetails: Record<SectionId, DetailId[]> = {
  layers: ["l1", "l2", "l3", "demo"],
  decision: ["gate", "wilson", "conflict", "dedup"],
  sources: ["amazon", "zhihu", "official", "fixtures"],
  boundaries: ["scope", "unknown", "locale", "action"],
}

const currentSection = computed(() => sections.find((section) => section.id === activeSection.value) ?? sections[0])
const currentDetail = computed(() => details[activeDetail.value])

function selectSection(id: SectionId) {
  activeSection.value = id
  activeDetail.value = sectionDetails[id][0]
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && props.open) emit("close")
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      document.body.style.overflow = "hidden"
      await nextTick()
      closeButton.value?.focus()
    } else {
      document.body.style.overflow = ""
    }
  },
)

onMounted(() => document.addEventListener("keydown", onKeydown))
onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown)
  document.body.style.overflow = ""
})
</script>

<template>
  <Teleport to="body">
    <Transition name="guide">
      <div v-if="open" class="guide" @click.self="emit('close')">
        <section class="guide__panel" role="dialog" aria-modal="true" aria-labelledby="guide-title">
          <header class="guide__head">
            <div>
              <p class="guide__eyebrow">RESEARCH GUIDE</p>
              <h2 id="guide-title">研究方法与证据规则</h2>
            </div>
            <button ref="closeButton" type="button" class="guide__close" aria-label="关闭研究方法" @click="emit('close')">×</button>
          </header>

          <div class="guide__layout">
            <nav class="guide__nav" aria-label="研究指南章节">
              <p class="guide__nav-label">章节</p>
              <button
                v-for="section in sections"
                :key="section.id"
                type="button"
                :class="{ active: activeSection === section.id }"
                @click="selectSection(section.id)"
              >
                <span class="num">{{ section.no }}</span>
                {{ section.label }}
              </button>
              <div class="guide__nav-note">
                <span aria-hidden="true">↗</span>
                <p>规则与工作台使用同一份证据契约。</p>
              </div>
            </nav>

            <div class="guide__content">
              <p class="guide__chapter num">{{ currentSection.no }} / 04</p>
              <h3>{{ currentSection.title }}</h3>
              <p class="guide__intro">{{ currentSection.intro }}</p>

              <div v-if="activeSection === 'layers'" class="guide__source-grid">
                <button type="button" class="guide__source guide__source--l1" @click="activeDetail = 'l1'">
                  <strong>L1</strong><span>一手反馈</span><small>可判定</small>
                </button>
                <button type="button" class="guide__source guide__source--l2" @click="activeDetail = 'l2'">
                  <strong>L2</strong><span>二手经验</span><small>待验证</small>
                </button>
                <button type="button" class="guide__source guide__source--l3" @click="activeDetail = 'l3'">
                  <strong>L3</strong><span>宏观语境</span><small>背景</small>
                </button>
                <button type="button" class="guide__source guide__source--demo" @click="activeDetail = 'demo'">
                  <strong>M</strong><span>演示数据</span><small>显式标识</small>
                </button>
              </div>

              <div class="guide__rules">
                <button
                  v-for="id in sectionDetails[activeSection]"
                  :key="id"
                  type="button"
                  :class="{ active: activeDetail === id }"
                  @click="activeDetail = id"
                >
                  <span class="guide__rule-dot" aria-hidden="true"></span>
                  <span>
                    <strong>{{ details[id].title }}</strong>
                    <small>{{ details[id].tag }}</small>
                  </span>
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>

            <aside class="guide__detail">
              <span class="guide__detail-tag">{{ currentDetail.tag }}</span>
              <h4>{{ currentDetail.title }}</h4>
              <p>{{ currentDetail.body }}</p>
              <ul>
                <li v-for="point in currentDetail.points" :key="point">{{ point }}</li>
              </ul>
              <NuxtLink to="/workbench" class="guide__cta" @click="emit('close')">回到工作台验证 ↗</NuxtLink>
            </aside>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
