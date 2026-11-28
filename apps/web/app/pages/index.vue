<script setup lang="ts">
/**
 * 产品概览（落地页）—— 产品叙事一屏：hero 卖点之问 + 一次验证如何发生（模拟示例卡）
 * + 四步方法（编号大卡）+ 样本量→判定交互演示器 + 工作台入口 + FAQ。
 * 演示内容一律带「模拟示例」标识（CONSTRAINTS 第四节）；演示器公式为产品真实口径
 * （decideFromVotes 与工作台兜底判定共用一份，ADR-0005），不编造任何数字。
 * 兼容旧深链：/?scenario=x 直达工作台对应场景（2026-11-22 多页化前的 URL 形态）。
 */
import { decideFromVotes, DECISION_LABEL } from "../composables/useEvidence"

const route = useRoute()

if (route.query.scenario) {
  await navigateTo({ path: "/workbench", query: route.query }, { replace: true })
}

useHead({ title: "产品概览 · CrossPilot 2.0" })

/** 方法四步（产品叙事：假设 → 对照 → 差异 → 下一轮验证） */
const STEPS = [
  { no: "01", title: "提出卖点假设", body: "把产品优点变成可检验的问题" },
  { no: "02", title: "对照多来源证据", body: "区分消费者反馈、经验与背景" },
  { no: "03", title: "识别认知差异", body: "看见支持、冲突与证据缺口" },
  { no: "04", title: "启动下一轮验证", body: "带着问题和实验回到市场" },
]

const SOURCE_LAYERS = [
  { code: "L1", title: "一手消费者反馈", body: "消费者对商品的直接评价，是偏好判定的核心证据。", tag: "可判定", cls: "source--l1" },
  { code: "L2", title: "从业经验与转述", body: "帮助发现问题与补充语境，不直接证明海外偏好。", tag: "待验证", cls: "source--l2" },
  { code: "L3", title: "宏观与监管背景", body: "解释市场、贸易与监管环境，不代表个体购买动机。", tag: "背景", cls: "source--l3" },
  { code: "M", title: "演示数据", body: "用于体验流程的模拟回填，始终带明确标识。", tag: "Mock", cls: "source--demo" },
]

/** 判定 → 建议动作（与演示说明 8.3 映射一致；三态语义色与工作台同源） */
const ACTIONS = [
  { tag: "已有有限支持", cls: "tag--ok", action: "扩大样本复核后，再写入详情页卖点" },
  { tag: "样本分歧", cls: "tag--bad", action: "先验证冲突维度，不急于修改详情页" },
  { tag: "缺少有效数据", cls: "tag--warn", action: "启动用户访谈与评论补样" },
]

/**
 * 「样本量 → 判定」演示器：滑块跑工作台同款判定公式（decideFromVotes）。
 * 初始 30/21 = limited 场景同款边界（下界 0.521 刚过决定线）；三个预设按钮
 * 为 test_decision.py 同款真实边界用例。
 */
const demoN = ref(30)
const demoK = ref(21)

watch(demoN, (n) => {
  if (demoK.value > n) demoK.value = n
})

const demo = computed(() => decideFromVotes(demoK.value, demoN.value - demoK.value))

const demoLabel = computed(() => DECISION_LABEL[demo.value.state])

const DEMO_CLS: Record<string, string> = {
  supported: "tag--ok",
  conflicting: "tag--bad",
  refuted: "tag--bad",
  insufficient: "tag--warn",
}
const demoCls = computed(() => DEMO_CLS[demo.value.state])

const demoNote = computed(() => {
  const n = demoN.value
  const k = demoK.value
  if (demo.value.state === "insufficient" && n < 30) {
    return `去重后有极性样本 ${n} 低于门禁 30，按口径强制 insufficient；补样至 30 后决定线为份额 ≥68%`
  }
  const s = demo.value.supportInterval
  if (!s) return "无决定性多数且区间不重叠——缺少有效数据"
  const fmt = (v: number) => v.toFixed(2)
  if (demo.value.state === "supported") {
    return `支持份额 ${fmt(k / n)} · 95% 下界 ${fmt(s.lo)} 刚过决定线（n=30 时需份额 ≥68% 才判决定性多数）`
  }
  if (demo.value.state === "refuted") {
    return `反对份额 ${fmt((n - k) / n)} · 95% 下界 ${fmt(demo.value.opposeInterval!.lo)} 过决定线——决定性多数反对`
  }
  return `支持下界 ${fmt(s.lo)} 与反支持下界 ${fmt(demo.value.opposeInterval!.lo)} 的区间重叠——95% 置信下难分高下`
})

/** 真实边界用例预设（与后端 test_decision.py 用例一致） */
const DEMO_PRESETS = [
  { n: 30, k: 15, label: "15 : 15 → 样本内存在分歧" },
  { n: 30, k: 21, label: "21 : 9 → 已有有限支持" },
  { n: 30, k: 9, label: "9 : 21 → 多数反馈反对" },
]
function applyPreset(p: { n: number; k: number }) {
  demoN.value = p.n
  demoK.value = p.k
}

/** FAQ（内容 = 演示说明 8.5 高频质疑预案，口径一致、零编造） */
const FAQS = [
  {
    q: "拿不到德国消费者一手反馈，你们给什么？",
    a: "不辩解，把问题本身亮出来。「缺少有效数据」是系统的诚实输出：每个假设下都给出该核实什么（应核实方向 + 待验证问题），而不是编一段结论。L1 获取路径（品牌授权导出）已在方案中，是下一轮接入的第一优先级。",
  },
  {
    q: "「证据不足」是拍脑袋吗？",
    a: "不是——是公式。门禁（去重后有极性样本 n≥30）+ Wilson 95% 区间（决定线：n=30 时份额 ≥68% 才判决定性多数）+ 区间重叠判冲突。判定依据在工作台横幅逐项可读，下方演示器跑的就是同一条公式，边界用例写入测试。",
  },
  {
    q: "为什么不训练一个模型来下结论？",
    a: "全链路零训练是设计选择。不训练 = 可审计（每条证据带规则命中与区间）、可复现（无随机种子波动）、不受一手标注稀缺制约、部署零 GPU；LLM 只做零样本立场抽取备胎，属推理不属训练。含拟合成分的方案被显式排除。",
  },
  {
    q: "数据从哪来，会爬知乎吗？",
    a: "不建全文库。知乎侧只做检索 + 摘录引用（≤300 字符、作者匿名化、PII 剔除）+ 链接回源；监管与贸易语境来自 Safety Gate / Eurostat / Comext 等官方公开数据，逐源许可入档。重复评论不虚增一致性——去重先于计数，同簇只计 1 条。",
  },
]
</script>

<template>
  <AppShell crumb="产品概览">
    <div class="landing">
      <!-- Hero：卖点之问 + 一次验证如何发生 -->
      <section class="hero">
        <div class="hero__copy">
          <p class="hero__chapter num">01 / 从真实的人开始</p>
          <h1 class="hero__title">
            你的出海卖点，<br>真的符合<br>
            <span class="hero__accent">海外用户需求吗？</span>
          </h1>
          <p class="hero__lead">
            别把团队共识当成市场答案。CrossPilot 把消费者的原话、来源与样本边界放在同一张桌上，让每个卖点假设都能被验证。
          </p>
          <div class="hero__actions">
            <NuxtLink to="/workbench" class="btn btn--primary">开始验证 <span aria-hidden="true">→</span></NuxtLink>
            <NuxtLink to="/workbench?scenario=conflict" class="btn btn--ghost">查看演示案例 ↗</NuxtLink>
          </div>
          <p class="hero__note">
            <span class="dot" aria-hidden="true"></span>
            当前为演示模式 · 无需登录 · 不调用真实 AI
          </p>
        </div>

        <div class="hero__card">
          <div class="herocard">
            <header class="herocard__head">
              <span class="herocard__cap">
                <svg class="herocard__capicon" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" fill="var(--accent)" />
                  <path d="M15.8 8.2 10.6 10.6 8.2 15.8 13.4 13.4Z" fill="var(--accent-ink)" />
                </svg>
                一次卖点验证，如何发生
              </span>
              <span class="tag tag--demo">模拟示例</span>
            </header>
            <div class="herocard__body">
              <p class="herocard__eyebrow">企业卖点假设</p>
              <p class="herocard__hyp">“隔层越多越好”</p>
              <p class="herocard__meta">旅行收纳包 / 海外英文电商市场</p>
              <div class="herocard__cut"><span class="herocard__cutmark" aria-hidden="true">✂</span></div>
              <div class="herocard__pair">
                <div class="vote vote--support">
                  <span class="vote__tag">✓ 支持观点</span>
                  <p class="vote__quote">“独立口袋让我把线材和洗漱用品分开。”</p>
                  <p class="vote__src">消费者直接反馈 · 模拟示例</p>
                </div>
                <div class="vote vote--oppose">
                  <span class="vote__tag">反对观点</span>
                  <p class="vote__quote">“小隔层太多，我更希望有一个开放的大空间。”</p>
                  <p class="vote__src">消费者直接反馈 · 模拟示例</p>
                </div>
              </div>
            </div>
            <div class="herocard__verdict">
              <span class="tag tag--demo">⇄ 样本分歧</span>
              <p class="herocard__verdict-text">分区需求存在差异，先验证收纳习惯。</p>
              <NuxtLink to="/workbench?scenario=conflict" class="herocard__link">查看完整证据链 →</NuxtLink>
            </div>
          </div>
        </div>
        <a class="hero__scroll" href="#method"><span>继续探索验证方法</span><span aria-hidden="true">↓</span></a>
      </section>
      <section id="method" class="method chapter">
        <header class="chapter__head">
          <p class="chapter__no num">02 / 验证方法</p>
          <div>
            <h2 class="method__title">真正稀缺的不是数据，而是可追溯的判断。</h2>
            <p class="method__sub">先提出假设，再让证据接受检验，最后把分歧变成下一轮验证。</p>
          </div>
        </header>
        <ol class="steps">
          <li v-for="s in STEPS" :key="s.no" class="step">
            <div class="step__no num">{{ s.no }}</div>
            <p class="step__title">{{ s.title }}</p>
            <p class="step__body">{{ s.body }}</p>
          </li>
        </ol>
      </section>

      <section class="source-map chapter">
        <header class="chapter__head">
          <p class="chapter__no num">03 / 证据分层</p>
          <div>
            <h2 class="method__title">不是所有证据，都有同等发言权。</h2>
            <p class="method__sub">颜色代表证据角色，而不是装饰。L1 负责判断，L2 提出问题，L3 补充背景，Mock 只用于演示。</p>
          </div>
        </header>
        <div class="source-grid">
          <article v-for="source in SOURCE_LAYERS" :key="source.code" class="source-card" :class="source.cls">
            <strong class="source-card__code num">{{ source.code }}</strong>
            <span class="source-card__tag">{{ source.tag }}</span>
            <h3>{{ source.title }}</h3>
            <p>{{ source.body }}</p>
          </article>
        </div>
      </section>

      <!-- 样本量 → 判定 交互演示器（产品真实公式） -->
      <section class="method calc chapter">
        <header class="chapter__head">
          <p class="chapter__no num">04 / 判定口径</p>
          <div>
            <h2 class="method__title">判定不是拍脑袋，证据必须过门禁。</h2>
            <span class="tag tag--demo">模拟示例 · 公式为产品真实口径</span>
            <p class="method__sub">拖动滑块，看样本量与支持票数如何改变判定——演示器跑的就是工作台使用的 Wilson 95% 区间与门禁公式。</p>
          </div>
        </header>

        <div class="calc__card">
          <div class="calc__controls">
            <div class="ctl">
              <div class="ctl__labelrow">
                <span class="ctl__name">样本量 n（去重后有极性样本）</span>
                <span class="ctl__value num">{{ demoN }}</span>
              </div>
              <input v-model.number="demoN" type="range" min="10" max="60" step="1" aria-label="样本量">
              <p class="ctl__hint">门禁：n ≥ 30 才进入区间判定，否则直接判「缺少有效数据」</p>
            </div>
            <div class="ctl">
              <div class="ctl__labelrow">
                <span class="ctl__name">支持票 k（其中支持样本数）</span>
                <span class="ctl__value num">{{ demoK }}</span>
              </div>
              <input v-model.number="demoK" type="range" min="0" :max="demoN" step="1" aria-label="支持票数">
              <p class="ctl__hint">决定线：支持份额 95% 区间下界 &gt; 0.5 → 判「已有有限支持」</p>
            </div>
            <div class="calc__presets">
              <button
                v-for="p in DEMO_PRESETS"
                :key="p.label"
                type="button"
                class="preset"
                @click="applyPreset(p)"
              >
                边界用例 <span class="num">{{ p.label }}</span>
              </button>
            </div>
          </div>

          <div class="calc__out">
            <div class="calc__verdict">
              <span class="tag" :class="demoCls">{{ demoLabel }}</span>
              <span class="calc__verdict-label">{{ demoLabel }}</span>
            </div>
            <IntervalGauge
              variant="plain"
              :lo-s="demo.supportInterval?.lo ?? null"
              :hi-s="demo.supportInterval?.hi ?? null"
              :lo-o="demo.opposeInterval?.lo ?? null"
              :hi-o="demo.opposeInterval?.hi ?? null"
              :share-s="demoN > 0 ? demoK / demoN : null"
              :share-o="demoN > 0 ? (demoN - demoK) / demoN : null"
            />
            <p class="calc__note num">{{ demoNote }}</p>
          </div>
        </div>
      </section>

      <!-- 工作台 CTA：判定 → 动作 -->
      <section class="cta chapter">
        <div class="cta__head">
          <div>
            <p class="chapter__no num">05 / 下一步验证</p>
            <h2 class="cta__title">每个发现，都应该变成下一步验证。</h2>
            <p class="cta__sub">假设、证据、行动，在同一个工作台完成。</p>
          </div>
          <NuxtLink to="/workbench" class="cta__link">进入工作台 ↗</NuxtLink>
        </div>
        <div class="cta__card">
          <p class="cta__card-title">拿到验证结果，直接转成下一步行动</p>
          <div class="cta__rows">
            <div v-for="a in ACTIONS" :key="a.tag" class="cta__row">
              <span class="tag" :class="a.cls">{{ a.tag }}</span>
              <span>{{ a.action }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- FAQ（口径 = 演示说明 8.5 质疑预案） -->
      <section class="method faq chapter">
        <header class="chapter__head">
          <p class="chapter__no num">06 / 直接回答</p>
          <div>
            <h2 class="method__title">高频疑问，直接回答。</h2>
            <p class="method__sub">与评委和卖家的问答口径一致，答案可追溯到 ADR-0005 与数据区 README。</p>
          </div>
        </header>
        <div class="faq__list">
          <details v-for="(f, i) in FAQS" :key="i" class="faq__item">
            <summary>
              <span class="faq__qno num">{{ String(i + 1).padStart(2, "0") }}</span>
              {{ f.q }}
              <span class="faq__mark" aria-hidden="true"></span>
            </summary>
            <p class="faq__body">{{ f.a }}</p>
          </details>
        </div>
      </section>

      <footer class="landing__footer">
        <span>固定演示边界：非电器旅行收纳包 → 德国市场 → 详情页首屏卖点验证</span>
        <span class="num">演示构建 · fixtures 数据</span>
      </footer>
    </div>
  </AppShell>
</template>
