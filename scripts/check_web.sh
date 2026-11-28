#!/usr/bin/env bash
# 前端冒烟自检：npm run build → 独立端口起产物服务 → SSR HTML 内容断言。
# 覆盖：工作台三场景（/workbench?scenario=…）+ 产品概览落地页（/）。
set -euo pipefail
cd "$(dirname "$0")/../apps/web"

PORT=3100
export NUXT_TELEMETRY_DISABLED=1

node --experimental-strip-types --input-type=module <<'JS'
import {
  canConfirmOperatorTrial,
  emptyOperatorTrial,
  hasOperatorTrialContent,
  missingOperatorTrialFields,
  normalizeOperatorTrialRecord,
} from "./app/utils/operator-trial.ts"
import { buildValidationPlan } from "./app/utils/validation-plan.ts"
import {
  canConfirmValidationRound,
  emptyValidationRound,
  missingValidationRoundFields,
  normalizeValidationRounds,
  validationRoundErrors,
} from "./app/utils/validation-round.ts"
import { validateEvidenceCard } from "./app/utils/evidence-schema.ts"
import { buildCasePackage } from "./app/utils/case-export.ts"
import { buildL1ImportTemplate } from "./app/utils/l1-import-template.ts"
import {
  buildL1ReviewDocument,
  defaultL1ReviewDecision,
  filterL1ReviewCards,
  l1ReviewErrors,
  l1ReviewStorageKey,
  normalizeL1ReviewDecision,
} from "./app/utils/l1-review.ts"

const empty = emptyOperatorTrial()
if (hasOperatorTrialContent(empty) || canConfirmOperatorTrial(empty)) {
  throw new Error("空试用记录不得视为有内容或可确认")
}
if (!missingOperatorTrialFields(empty).includes("证据 ID / 链接")) {
  throw new Error("试用记录缺少证据依据时未报错")
}
const normalized = normalizeOperatorTrialRecord({ confirmation: "confirmed", trialDate: 123 })
if (normalized.confirmation !== "pending" || normalized.trialDate !== "") {
  throw new Error("本地存储中的非法字段未被归一化")
}
const complete = {
  ...empty,
  trialDate: "2026-11-27",
  operatorRole: "德国站品牌运营",
  evidenceRefs: "review-1: https://example.com/review-1",
  decision: "修改容量卖点为精确尺寸",
  prototypeObservation: "多隔层版取物更快，开放空间版装载更灵活",
  nextAction: "运营负责人完成 5 人原型复测",
  confirmation: "confirmed",
}
if (!canConfirmOperatorTrial(complete)) {
  throw new Error("完整试用记录不得被拒绝确认")
}
if (canConfirmOperatorTrial({ ...complete, trialDate: "2999-01-01" })) {
  throw new Error("未来试用日期不得通过确认")
}
if (canConfirmOperatorTrial({ ...complete, evidenceRefs: "x" })) {
  throw new Error("无评论出处的试用记录不得通过确认")
}
if (canConfirmOperatorTrial({ ...complete, evidenceRefs: "claim_id=capacity" })) {
  throw new Error("仅含 claim_id 的试用记录不得通过确认")
}
if (canConfirmOperatorTrial({ ...complete, decision: "联系 test@example.com" })) {
  throw new Error("试用记录含邮箱时不得通过确认")
}
if (canConfirmOperatorTrial({ ...complete, prototypeObservation: "电话 +49 30 12345678" })) {
  throw new Error("试用记录含电话号码时不得通过确认")
}
if (canConfirmOperatorTrial({ ...complete, sourceScenario: "conflict", sourceRoundId: "round-demo", isDemo: true })) {
  throw new Error("演示轮次派生记录不得标记为真人运营确认")
}

const decision = {
  state: "insufficient",
  gate_status: "no_l1",
  support_interval: null,
  oppose_interval: null,
  n_total: 0,
  n_l1: 0,
  n_polarized: 0,
  n_insufficient: 0,
  dedup_clusters: 0,
  dedup_duplicated: 0,
  power_note: "",
  inference_note: "非随机样本，不可外推总体。",
}
const capacityPlan = buildValidationPlan({
  hypothesis: { id: "capacity", title: "容量越大越好", probe: "便携性是否更重要？", keywords: [] },
  status: "insufficient",
  product: "旅行收纳包",
  decision,
  support: [],
  oppose: [],
})
if (!capacityPlan.summary.includes("证据不足") || capacityPlan.interviews.length !== 3) {
  throw new Error("证据不足计划未生成针对性访谈问题")
}
if (capacityPlan.copyVariants.length !== 2 || capacityPlan.nextSteps.length !== 3) {
  throw new Error("验证计划缺少两版文案或三步行动")
}
const featurePlan = buildValidationPlan({
  hypothesis: { id: "features", title: "功能越多越好", probe: "隔层是否增加负担？", keywords: [] },
  status: "conflicting",
  product: "旅行收纳包",
  decision: { ...decision, state: "conflicting", gate_status: "pass" },
  support: [],
  oppose: [],
})
if (!featurePlan.prototypeTitle.includes("多隔层 vs 开放空间")) {
  throw new Error("功能分歧未生成同组原型对照")
}
if (!featurePlan.prototypeSteps.some((step) => step.includes("记录装什么")) ||
    !featurePlan.prototypeSteps.some((step) => step.includes("记录怎么取")) ||
    !featurePlan.prototypeSteps.some((step) => step.includes("记录麻烦程度"))) {
  throw new Error("原型计划缺少装、取、麻烦程度观察")
}
const supportCard = {
  excerpt: "Die Fächer sind praktisch.", source_url: "https://example.com/support", language: "de",
  published_on: "2026-11-01", level: "L1", sample_size: 1, stance: "support", is_demo_data: true,
  claim_id: "features", review_id: "support-1", relevance: "relevant", dedup: { cluster_id: 0, dup_count: 1, is_canonical: true },
}
const opposeCard = {
  ...supportCard, excerpt: "Zu viele Fächer erschweren das Herausnehmen.", source_url: "https://example.com/oppose",
  stance: "oppose", review_id: "oppose-1", dedup: { cluster_id: 1, dup_count: 1, is_canonical: true },
}
const duplicateCard = {
  ...supportCard, excerpt: "Die Fächer sind praktisch und sinnvoll.", review_id: "support-dupe",
  dedup: { cluster_id: 0, dup_count: 2, is_canonical: false },
}
const basisPlan = buildValidationPlan({
  hypothesis: { id: "features", title: "功能越多越好", probe: "隔层是否增加负担？", keywords: [] },
  status: "conflicting",
  product: "旅行收纳包",
  decision: { ...decision, state: "conflicting", gate_status: "pass", n_l1: 3, n_polarized: 2 },
  support: [supportCard, duplicateCard],
  oppose: [opposeCard],
})
if (basisPlan.basis.cards.length !== 2 ||
    !basisPlan.basis.cards.some((card) => card.stance === "support") ||
    !basisPlan.basis.cards.some((card) => card.stance === "oppose")) {
  throw new Error("验证计划没有同时引用去重后的支持与反对原文")
}
if (!basisPlan.basis.summary.includes("支持 1 条、反对 1 条")) {
  throw new Error("验证计划依据摘要未按去重后立场计数")
}
const genericPlan = buildValidationPlan({
  hypothesis: { id: "custom", title: "自定义卖点", probe: "有什么反例？", keywords: [] },
  status: "supported",
  product: "新产品",
  decision: { ...decision, state: "supported", gate_status: "pass" },
  support: [],
  oppose: [],
})
if (genericPlan.copyVariants.length !== 2 || !genericPlan.notice.includes("待测试草案")) {
  throw new Error("自定义假设未生成两版待测试草案")
}
const importTemplate = buildL1ImportTemplate("旅行收纳包", [
  { id: "capacity", title: "容量", probe: "", keywords: ["容量"] },
  { id: "custom-waterproof", title: "防水", probe: "", keywords: ["wasserdicht", "waterproof", "wasserdicht"], custom: true },
  { id: "custom-empty", title: "无关键词", probe: "", keywords: [], custom: true },
])
if (importTemplate.query !== "旅行收纳包" || importTemplate.market !== "de") {
  throw new Error("L1 导入模板丢失产品或市场")
}
if (importTemplate.authorization_scope.join(",") !== "internal_product_validation") {
  throw new Error("L1 导入模板扩大了授权用途")
}
if (importTemplate.claim_terms["custom-waterproof"].join(",") !== "wasserdicht,waterproof") {
  throw new Error("L1 导入模板未去重保留自定义术语")
}
if ("capacity" in importTemplate.claim_terms || "custom-empty" in importTemplate.claim_terms) {
  throw new Error("L1 导入模板写入内置或空术语范围")
}
if (importTemplate.cards.length !== 0 || importTemplate.source_id !== "" || importTemplate.authorization !== "") {
  throw new Error("L1 导入模板不得伪造评论或授权凭据")
}
let templateRejected = false
try {
  buildL1ImportTemplate("", [])
} catch {
  templateRejected = true
}
if (!templateRejected) {
  throw new Error("空产品关键词未拦截 L1 模板导出")
}

const emptyRound = emptyValidationRound()
if (canConfirmValidationRound(emptyRound) || !missingValidationRoundFields(emptyRound).includes("本轮观察")) {
  throw new Error("空验证轮次不得通过运营确认")
}
const completeRound = {
  ...emptyRound,
  id: "round-test-20261128",
  createdAt: new Date().toISOString(),
  scenario: "real",
  query: "旅行收纳包",
  claimId: "features",
  hypothesisTitle: "功能越多越好",
  status: "conflicting",
  evidenceRefs: "claim_id=features; review-1: https://example.com/review-1",
  observation: "参与者先放厚衣物，再找充电线；开放空间首次取物更快。",
  decision: "modify",
  rationale: "支持与反对来自不同装载场景。",
  nextAction: "补充 5 位目标用户复测",
  owner: "德国站运营",
  confirmation: "confirmed",
  market: "de",
  l1SnapshotSha256: "d".repeat(64),
}
if (!canConfirmValidationRound(completeRound)) {
  throw new Error("完整验证轮次不得被拒绝确认")
}
const prototypeRound = {
  ...completeRound,
  id: "round-prototype-20261128",
  prototype: {
    participantCode: "P01",
    order: "multi_first",
    itemsLoaded: "厚衣物放开放空间，充电线放小隔层。",
    retrieval: "开放空间首次取物成功，多隔层版开合两次。",
    friction: "厚衣物卡住拉链。",
  },
}
if (!canConfirmValidationRound(prototypeRound)) {
  throw new Error("完整原型观察轮次不得被拒绝确认")
}
if (canConfirmValidationRound({ ...prototypeRound, prototype: { ...prototypeRound.prototype, friction: "" } })) {
  throw new Error("缺少原型麻烦点的已确认轮次不得通过")
}
if (validationRoundErrors({ ...prototypeRound, prototype: { ...prototypeRound.prototype, participantCode: "P01 test@example.com" } }).length === 0) {
  throw new Error("原型参与者编号未拦截邮箱")
}
if (normalizeValidationRounds([prototypeRound])[0]?.prototype?.order !== "multi_first") {
  throw new Error("原型观察顺序未保留")
}
if (validationRoundErrors({ ...completeRound, observation: "联系 test@example.com" }).length === 0) {
  throw new Error("验证轮次未拦截邮箱")
}
if (normalizeValidationRounds([completeRound, { id: "invalid" }]).length !== 1) {
  throw new Error("验证轮次本地存储归一化未剔除非法记录")
}
if (normalizeValidationRounds([{ ...completeRound, observation: "" }])[0]?.confirmation !== "pending") {
  throw new Error("损坏的已确认轮次未自动降级为待确认")
}
if (normalizeValidationRounds([{ ...completeRound, createdAt: "2999-01-01T00:00:00Z" }])[0]?.confirmation !== "pending") {
  throw new Error("未来时间的已确认轮次未自动降级为待确认")
}
if (normalizeValidationRounds([{ ...completeRound, observation: "联系 test@example.com" }])[0]?.confirmation !== "pending") {
  throw new Error("含联系方式的已确认轮次未自动降级为待确认")
}
if (normalizeValidationRounds([{ ...completeRound, l1SnapshotSha256: null }])[0]?.confirmation !== "pending") {
  throw new Error("未绑定 L1 快照的已确认 real 轮次未自动降级为待确认")
}

const baseCard = {
  excerpt: "Ich bin sehr enttäuscht und komme nicht wieder.",
  source_url: "https://example.com/review-1",
  language: "de",
  published_on: "2026-11-01",
  level: "L1",
  sample_size: 1,
  stance: "support",
  is_demo_data: false,
  claim_id: "features",
  review_id: "review-1",
  market: "de",
  source_id: "brand-export",
  authorization: "品牌授权导出",
  authorization_ref: "brand-2026",
  relevance: "relevant",
  stance_votes: { rule: "oppose", llm: null },
  annotator_agreement: false,
  classification_method: "manual",
  classification_note: "人工复核：反讽。",
}
const manualCard = validateEvidenceCard(baseCard)
if (!manualCard.ok || manualCard.card.classification_method !== "manual") {
  throw new Error("人工立场覆盖卡未通过前端契约")
}
const incompleteManualCard = validateEvidenceCard({ ...baseCard, classification_note: null })
if (!incompleteManualCard.ok || defaultL1ReviewDecision(incompleteManualCard.card).reviewed) {
  throw new Error("缺少复核说明的人工分类不得默认视为已复核")
}
const conflictManualCard = validateEvidenceCard({ ...baseCard, review_required: true, review_reasons: ["重复评论立场冲突"] })
if (!conflictManualCard.ok || defaultL1ReviewDecision(conflictManualCard.card).reviewed) {
  throw new Error("重复评论立场冲突未解决时不得默认视为已复核")
}
if (validateEvidenceCard({ ...baseCard, classification_method: "unknown" }).ok) {
  throw new Error("非法分类方法未拦截")
}
if (validateEvidenceCard({ ...baseCard, classification_method: null }).ok) {
  throw new Error("缺少分类方法的复核说明未拦截")
}
if (validateEvidenceCard({ ...baseCard, level: "L2" }).ok) {
  throw new Error("L2 证据卡被错误允许人工立场分类")
}
const ruleCard = validateEvidenceCard({
  ...baseCard,
  classification_method: "rule",
  classification_note: null,
  review_required: true,
  review_reasons: ["规则净分低于保守阈值"],
})
if (!ruleCard.ok || ruleCard.card.review_required !== true) {
  throw new Error("规则复核标记未通过前端契约")
}
if (validateEvidenceCard({ ...baseCard, classification_method: "rule", review_required: null, review_reasons: ["需要复核"] }).ok) {
  throw new Error("缺少 review_required 的复核理由未拦截")
}
const customClaimCard = validateEvidenceCard({
  ...baseCard,
  claim_id: "custom-waterproof",
  aspect_terms: ["wasserdicht", "waterproof"],
  classification_method: "rule",
  classification_note: null,
})
if (!customClaimCard.ok || customClaimCard.card.aspect_terms?.[0] !== "wasserdicht") {
  throw new Error("自定义卖点术语未通过前端契约")
}
if (validateEvidenceCard({ ...baseCard, level: "L2", aspect_terms: ["wasserdicht"] }).ok) {
  throw new Error("L2 证据卡被错误允许自定义卖点术语")
}
if (validateEvidenceCard({ ...baseCard, relevance: "irrelevant", claim_id: null, aspect_terms: ["wasserdicht"] }).ok) {
  throw new Error("不相关评论被错误允许自定义卖点术语")
}
if (validateEvidenceCard({ ...baseCard, aspect_terms: ["x".repeat(81)] }).ok) {
  throw new Error("超长卖点术语未拦截")
}
const customReviewDocument = buildL1ReviewDocument(
  [customClaimCard.card],
  { [customClaimCard.card.review_id]: { ...defaultL1ReviewDecision(customClaimCard.card), reviewed: true, note: "术语范围已核对。" } },
  "旅行收纳包",
  ["internal_product_validation"],
)
if (customReviewDocument.claim_terms?.["custom-waterproof"]?.[0] !== "wasserdicht") {
  throw new Error("复核回导 JSON 未保留自定义卖点术语")
}
const reassignedReviewDocument = buildL1ReviewDocument(
  [customClaimCard.card],
  { [customClaimCard.card.review_id]: { ...defaultL1ReviewDecision(customClaimCard.card), reviewed: true, claim_id: "capacity", note: "人工改归容量卖点。" } },
  "旅行收纳包",
  ["internal_product_validation"],
)
if (Object.keys(reassignedReviewDocument.claim_terms ?? {}).length !== 0) {
  throw new Error("改归其他卖点后仍导出旧自定义术语")
}
const reviewCard = ruleCard.card
const reviewDraft = defaultL1ReviewDecision(reviewCard)
if (reviewDraft.reviewed || l1ReviewErrors(reviewDraft).length) {
  throw new Error("规则卡默认复核状态不合法")
}
const reviewed = {
  ...reviewDraft,
  reviewed: true,
  claim_id: "capacity",
  stance: "oppose",
  note: "人工确认：描述明确负面。",
}
if (l1ReviewErrors(reviewed).length) {
  throw new Error("完整人工复核被拒绝")
}
const filterCards = [
  { ...manualCard.card, review_id: "filter-r1", claim_id: "capacity", excerpt: "Die Tasche ist geräumig." },
  { ...manualCard.card, review_id: "filter-r2", claim_id: "features", excerpt: "Die Fächer sind praktisch.", source_url: "https://example.com/filter-r2" },
  { ...manualCard.card, review_id: "filter-r3", claim_id: null, relevance: "irrelevant", stance: "insufficient", excerpt: "Kein Bezug zum Produkt." },
]
if (filterL1ReviewCards(filterCards, "features", "").length !== 1 ||
    filterL1ReviewCards(filterCards, "irrelevant", "").length !== 1 ||
    filterL1ReviewCards(filterCards, "all", "FILTER-R2").length !== 1 ||
    filterL1ReviewCards(filterCards, "all", "example.com/filter").length !== 1) {
  throw new Error("复核队列按卖点或关键词筛选失败")
}
const snapshotSha = "a".repeat(64)
const reviewDocument = buildL1ReviewDocument(
  [reviewCard],
  { [reviewCard.review_id]: reviewed },
  "旅行收纳包",
  ["internal_product_validation"],
  snapshotSha,
)
if (reviewDocument.cards[0].stance !== "oppose" || reviewDocument.cards[0].stance_note !== reviewed.note) {
  throw new Error("人工复核立场未进入回导 JSON")
}
if (reviewDocument.source_snapshot_sha256 !== snapshotSha) {
  throw new Error("复核回导 JSON 未保留来源快照版本")
}
if (l1ReviewStorageKey("旅行收纳包", snapshotSha) === l1ReviewStorageKey("旅行收纳包", "b".repeat(64))) {
  throw new Error("不同快照版本复用了人工复核草稿键")
}
let draftKeyRejected = false
try {
  l1ReviewStorageKey("旅行收纳包", "invalid")
} catch {
  draftKeyRejected = true
}
if (!draftKeyRejected) {
  throw new Error("非法快照指纹未拦截复核草稿键")
}
if (l1ReviewErrors({ ...reviewed, note: "" }).length === 0) {
  throw new Error("已复核但缺少说明时未拦截")
}
const irrelevant = normalizeL1ReviewDecision(
  { ...reviewed, relevance: "irrelevant", claim_id: "capacity", stance: "support" },
  reviewCard,
)
if (irrelevant.claim_id !== "" || irrelevant.stance !== "insufficient") {
  throw new Error("不相关复核未清空归属并强制无极性")
}
let scopeRejected = false
try {
  buildL1ReviewDocument([reviewCard], { [reviewCard.review_id]: reviewed }, "旅行收纳包", ["model_processing"])
} catch {
  scopeRejected = true
}
if (!scopeRejected) {
  throw new Error("缺少内部验证授权范围的复核导出未拦截")
}
const exportEnvelope = {
  query: '旅行收纳包',
  market: 'de',
  data_mode: 'snapshot',
  scenario: 'conflict',
  stance: 'conflicting',
  cards: [{ ...reviewCard, is_demo_data: true }],
  invalidCards: [{ errors: ["缺少 review_id"], raw: {} }],
  questions: [{ text: '核对使用场景', source: 'L1: https://example.com/review-1' }],
  generated_at: '2026-11-28T00:00:00Z',
  decision,
  claimDecisions: [{ ...decision, claim_id: 'capacity' }],
  l1Notice: null,
  l1AuthorizationScope: ['internal_product_validation'],
  l1SnapshotSha256: 'c'.repeat(64),
  l2Cards: [],
  l2InvalidCards: [{ errors: ["L2 授权范围缺失"], raw: {} }],
  l2Notice: null,
  comparisons: [],
  dataSource: 'fixtures',
}
const casePackage = buildCasePackage(
  exportEnvelope,
  [{
    hypothesis: { id: 'capacity', title: '容量越大越好', probe: '便携性是否更重要？', keywords: [] },
    status: 'insufficient',
    statusNote: '样本不足',
    decision: { ...decision, claim_id: 'capacity' },
    plan: capacityPlan,
  }],
  [],
  '2026-11-28T01:00:00Z',
)
if (!casePackage.is_demo_data || casePackage.market_effect_claim_allowed !== false) {
  throw new Error('演示案例包边界未写入')
}
if (casePackage.hypotheses.length !== 1 || casePackage.evidence.cards.length !== 1) {
  throw new Error('案例包未打包全部假设与证据')
}
if (casePackage.evidence.l1_authorization_scope[0] !== 'internal_product_validation') {
  throw new Error('案例包未保留快照授权范围')
}
if (casePackage.evidence.l1_snapshot_sha256 !== 'c'.repeat(64)) {
  throw new Error('案例包未保留快照版本指纹')
}
if (casePackage.evidence.invalid_card_count !== 1 ||
    casePackage.evidence.invalid_card_errors[0][0] !== '缺少 review_id' ||
    casePackage.evidence.l2_invalid_card_count !== 1 ||
    casePackage.evidence.l2_invalid_card_errors[0][0] !== 'L2 授权范围缺失') {
  throw new Error('案例包未保留被拒绝证据的数量与错误')
}
const realCasePackage = buildCasePackage(
  { ...exportEnvelope, scenario: 'real', cards: [{ ...reviewCard, is_demo_data: false }] },
  [],
  [],
  '2026-11-28T01:00:00Z',
)
if (realCasePackage.is_demo_data || !realCasePackage.disclaimer.includes('非随机样本')) {
  throw new Error('真实案例包缺少非随机样本边界')
}
console.log('运营试用记录、动态验证计划、验证轮次、人工分类、L1 复核与案例包契约校验通过')
JS

echo "==> [1/3] npm run build（失败即退出非零）"
npm run build

echo "==> [2/3] 启动产物服务（node .output/server/index.mjs，端口 $PORT）"
PORT=$PORT node .output/server/index.mjs &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT

READY=0
for _ in $(seq 1 30); do
  if curl -s -o /dev/null -m 2 "http://localhost:$PORT/"; then READY=1; break; fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "FAIL: 产物服务 $PORT 秒内未就绪" >&2
  exit 1
fi
echo "产物服务就绪：http://localhost:$PORT/"

echo "==> [3/3] SSR 内容断言（卖点级判定 + 跨来源对照 + 验证计划）"
export PYTHONIOENCODING=utf-8
python -X utf8 - "$PORT" <<'PYEOF'
import re
import sys
import urllib.request

port = sys.argv[1]
base = f"http://localhost:{port}"


def fetch(path: str) -> str:
    with urllib.request.urlopen(base + path, timeout=10) as resp:
        return resp.read().decode("utf-8")


pages = {s: fetch(f"/workbench?scenario={s}") for s in ("real", "conflict", "limited")}
pages["landing"] = fetch("/")
pages["history"] = fetch("/history")
pages["review"] = fetch("/review")
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((ok, label))


r = pages["real"]
check("每条卖点独立判定" in r, "real: 横幅按卖点独立判定")
check("证据不足" in r, "real: 三条卖点均显示证据不足")
check("L1 数据提示" in r, "real: 德国 L1 缺失提示可见")
check("推断边界" in r, "real: 非随机样本推断边界可见")
check('mode-badge--snapshot' in r and "快照 snapshot" in r, "real: 数据模式徽标=快照 snapshot")
check("本地 fixtures" in r, "real: 数据源=本地 fixtures")
check('class="l2zone"' in r and "跨来源附录" in r, "real: L2 跨来源附录存在")
check(r.count("card--demo") == 0, "real: 无演示卡")
check("zhuanlan.zhihu.com" in r or "zhihu.com" in r, "real: L2 卡链接回源知乎")
check(r.count("L2 二手转述") >= 3, "real: L2 徽标 ≥3")
check(r.count("L3 宏观语境") >= 3, "real: L3 徽标 ≥3")
check(r.count('target="_blank"') >= 6, "real: 来源链接 ≥6")
check("不相关 / 未归属证据" in r and "不参与状态判定" in r, "real: 不相关/未归属证据组存在")
check("相关但未归属" in r, "real: 相关但未归属证据单独呈现")
check(r.count("缺少有效数据（L1 零样本）") >= 3, "real: 三组零样本空状态")
check("L1 消费者 × L2 从业经验" in r and "缺消费者证据" in r, "real: 结构化跨来源对照显示证据缺口")
check("当前假设：容量越大越好" in r, "real: 验证计划绑定当前假设")
check("两版待测试文案" in r and "A 版" in r and "B 版" in r, "real: 当前假设直接生成两版文案")
check("导出案例证据包" in r and "复制完整验证计划" in r, "real: 案例证据包与计划导出入口存在")
check("L1 数据导入模板" in r and "补齐 source_id" in r, "real: L1 数据导入模板入口与补齐提示存在")
check("自动保存在本机浏览器" in r, "real: 假设与行动本地持久化提示可见")
check("banner__demo-chip" not in r, "real: 无演示场景 chip")
check("固定演示场景" in r and "不检索任意商品" in r, "real: fixtures 固定场景说明")
check('class="wb__search"' not in r, "real: fixtures 不展示任意商品检索表单")
check("假设 1 标题" in r and "核实问题" in r, "real: 假设标题与核实问题可编辑")
check("＋ 新增假设" in r, "real: 自定义假设创建入口存在")
check("记录本轮验证结果" in r and "开始记录本轮" in r, "real: 假设级验证轮次入口存在")
check("review_id: source_url" in r and "绑定当前 L1 snapshot_sha256" in r and "旧快照轮次不计入运营闭环" in r, "real: 运营轮次消费者证据引用要求可见")
check("同组原型测试" in r and "装什么" in r, "real: 结构化原型观察入口存在")

r = pages["conflict"]
check("每条卖点独立判定" in r, "conflict: 横幅按卖点独立判定")
check("证据不足" in r, "conflict: 单卖点样本不足不冒充总体冲突结论")
check("banner__demo-chip" in r, "conflict: 演示场景 chip 存在")
check("hypo__groups--conflict" in r, "conflict: 有支持/反对的卖点左右并排")
check('class="egroup egroup--support"' in r and 'class="egroup egroup--oppose"' in r,
      "conflict: 支持组/反对组结构存在")
check(r.count("card--demo") >= 30, "conflict: L1 演示卡 ≥30")
check(r.count("L1 一手反馈") >= 30, "conflict: L1 徽标 ≥30")
check(r.count("以下为演示数据（模拟回填）") >= 2, "conflict: 演示分隔条 ≥2")
check(r.count('target="_blank"') >= 30, "conflict: 来源链接 ≥30")
check('class="l2zone"' in r and "全部模拟" in r, "conflict: 模拟 L2 跨来源附录存在")
check(r.count("跨来源待验证") >= 1, "conflict: 当前假设的 L1/L2 跨来源问题可见")
check("L1 消费者 × L2 从业经验" in r and "双方都有线索，需核对场景" in r, "conflict: 跨来源对照分列样本与经验")
check("不相关证据 · 1 张" in r and "相关但未归属 · 1 张" in r, "conflict: 不相关与未归属分组独立")
check("example.com/crosspilot-demo" in r, "conflict: 模拟 L2 出处明确")
check("支持份额 95% 区间" in r, "conflict: Wilson 区间可追溯")
check('class="gauge"' in r, "conflict: Wilson 标尺渲染")
check("门禁 below_minimum" in r, "conflict: 当前卖点显示低于门禁")
check("样本量 n=1" in r and r.count("评论 ID") >= 32 and "未归属" in r, "conflict: 单卡样本量、评论 ID 与未归属标签可见")
check("原型测试" in r and "大容量 vs 轻便尺寸" in r, "conflict: 当前容量假设的原型测试方案可见")
check("五、原型测试方案" in r, "conflict: 完整计划包含原型测试")
check("推断边界" in r, "conflict: 采样偏差边界可见")

r = pages["limited"]
check("每条卖点独立判定" in r, "limited: 横幅按卖点独立判定")
check("证据不足" in r, "limited: 单卖点样本不足不冒充总体支持结论")
check("banner__demo-chip" in r, "limited: 演示场景 chip 存在")
check(r.count("card--demo") >= 25, "limited: L1 演示卡 ≥25")
check(r.count("L1 一手反馈") >= 25, "limited: L1 徽标 ≥25")
check(r.count("以下为演示数据（模拟回填）") >= 1, "limited: 演示分隔条存在")
check(r.count('target="_blank"') >= 25, "limited: 来源链接 ≥25")
check('class="l2zone"' in r and "全部模拟" in r, "limited: 模拟 L2 跨来源附录存在")
check(r.count("跨来源待验证") >= 1, "limited: 当前假设的 L1/L2 跨来源问题可见")
check("支持份额 95% 区间" in r, "limited: Wilson 区间可追溯")
check("门禁 below_minimum" in r, "limited: 当前卖点显示低于门禁")
check(r.count("样本量 n=1") >= 25 and r.count("评论 ID") >= 30, "limited: 单卡样本量与评论 ID 可见")
check("原型测试" in r and "A/B" in r, "limited: 验证建议包含原型与 A/B")
check("七、采样偏差与推断边界" in r, "limited: 完整计划包含采样偏差")

r = pages["landing"]
check("你的出海卖点" in r, "landing: hero 主标题存在")
check("海外用户需求吗" in r, "landing: hero 强调句存在")
check("开始验证" in r and 'href="/workbench"' in r, "landing: 开始验证按钮存在")
check("卖点验证工作台" in r and "历史验证项目" in r, "landing: 导航齐备")
check("演示模式 · Mock 数据" in r, "landing: 演示模式徽标存在")
check("当前为演示模式" in r, "landing: 演示模式提示存在")
check(r.count("模拟示例") >= 3, "landing: 模拟示例标识 ≥3")
check("样本分歧" in r, "landing: 分歧标签使用样本语义")
check("隔层越多越好" in r, "landing: 演示假设存在")
check("判定不是拍脑袋" in r, "landing: 判定演示器存在")
check("边界用例" in r and "15 : 15" in r, "landing: 边界用例存在")
check("高频疑问" in r, "landing: FAQ 存在")
check('class="gauge"' in r, "landing: Wilson 标尺渲染")

r = pages["history"]
check("运营试用记录" in r, "history: 本地运营试用表单存在")
check("验证轮次" in r and "导出全部轮次 JSON" in r, "history: 验证轮次回看与导出入口存在")
check("保存本地记录" in r and "导出 JSON" in r, "history: 本地保存与导出入口存在")
check("本地保存不等于已完成真人试用" in r and "完整填写后方可标记" in r, "history: 不冒充人工试用且确认需完整记录")
check("不要填写评论作者姓名" in r, "history: 隐私提示存在")
check("L1 人工复核" in r, "history: L1 复核导航存在")
check("完成状态审计" in r and "未读取服务端真实案例门禁" in r, "history: 真实案例门禁入口存在且 fixtures 不伪造结果")
check("审计卖点（逗号分隔，留空=全部）" in r, "history: 活跃卖点审计范围入口存在")
check("审计结果同时绑定 L1 snapshot_sha256" in r and "rounds_archive_sha256" in r, "history: readiness 双版本绑定说明可见")
check("演示评论和演示轮次不计入真实案例完成" in r, "history: 演示轮次隔离提示存在")

r = pages["review"]
check("把规则判断变成可追溯的人工决定" in r, "review: 人工复核页存在")
check("record_sha256" in r and "旧版本人工决定不会套用" in r, "review: 快照版本隔离说明可见")
check("当前为 fixtures 演示模式" in r and "不用演示评论伪造复核数据" in r, "review: fixtures 模式不伪造复核数据")
check("review-card" not in r, "review: fixtures 模式不渲染伪造复核卡")

for scenario, r in pages.items():
    if scenario in ("landing", "history", "review"):
        continue
    if scenario == "real":
        check("演示数据：模拟回填，非真实德国消费者反馈" not in r,
              "real: 无演示数据合规说明")
    else:
        check("演示数据：模拟回填，非真实德国消费者反馈" in r,
              f"{scenario}: 演示数据合规说明存在")
    check(re.search(r"scenario=(real|demo_conflict|demo_limited)", r) is not None,
          f"{scenario}: 页脚 scenario 标识存在")

passed = sum(1 for ok, _ in results if ok)
for ok, label in results:
    print(("PASS " if ok else "FAIL ") + label)
print(f"==> 断言 {passed}/{len(results)} 通过")
sys.exit(0 if passed == len(results) else 1)
PYEOF

echo "==> check_web 全部通过"
