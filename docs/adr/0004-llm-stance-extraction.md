# ADR-0004 LLM 立场抽取采用 OpenAI 兼容适配层，默认仍走规则基线

状态：已接受（实现就绪，待凭据实测）｜ 日期：2026-11-21

## 背景

规则立场基线（`services/stance_baseline.py`）在双域对照靶上有已知短板：GERestaurant 餐厅域 oppose 召回不足（oppose→support 570 条，正词负用/反讽）；商品域词典覆盖缺口（MARC accuracy 0.580，域退化 -0.030，商品缺陷词不在餐厅域词表）。STATUS 待办 #4 的正式方案是 LLM API，但 800 美元 Token 补贴细则未确认，且本机此前无任何 LLM 凭据——不能因为「等凭据」就推迟全部开发工作。

## 决策

1. **供应商无关适配层**：`services/stance_llm.py` 走 OpenAI 兼容 `chat/completions`（`LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` 三项齐备才可用），智谱 / DeepSeek / Moonshot / OpenAI 等均可接入，不绑定任何一家。
2. **默认不变**：产品与评测的默认分类器仍是透明规则基线；LLM 只经显式配置（环境变量）启用。没有凭据时一切行为与过去完全一致。
3. **诚实降级**：LLM 运行时故障（网络 / HTTP / 响应结构 / JSON 契约）逐条回退规则基线并标记 `fallback_used` 与原因，回退率可统计、进报告；配置缺失与输入违约响亮失败，不静默降级（ADR-0002 决策 4 同源哲学）。
4. **LLM 是判定工具，不是证据源**：输出不携带证据层级、不进证据卡；三类口径（support/oppose/insufficient）与规则基线、`resolve_stance` 一致；输入只接受 ≤300 字符已清洗摘录（`zhihu_client.sanitize_excerpt` 口径），超长拒绝、不发全文。
5. **成本与复现守卫**：temperature=0 + max_tokens 320 + 单条 ≤300 字符；评测脚本带磁盘缓存（`data/sources/_eval_cache/`，按模型、端点哈希与提示词指纹隔离，可中断续跑）与 `--limit` 成本冒烟；正式子集用 `--sample-size N --seed 42` 固定种子随机抽样。只缓存成功的 LLM 结果，规则回退必须逐次重试并计入回退率，不能伪装成模型缓存命中。
6. **启用验收线**：LLM 必须在双域评测中至少 oppose recall 超过规则基线（GERestaurant oppose recall / MARC oppose recall）才允许进入任何产品路径；未达标则继续用规则基线，评测报告如实记录。

## 后果

- 正面：凭据到位后零改动即可实测（`eval_stance_baseline.py --classifier llm`），把「等 Token 补贴细则」从开发阻塞降级为执行阻塞。
- 代价：响应结构与供应商行为未经真实调用核验（与本机无凭据的事实一致，已在模块 docstring 声明）；首跑若不符规格需按实际响应修订适配器并回填核验记录。
- 风险：个别供应商不支持 `response_format={"type":"json_object"}`（会 HTTP 400）——表现为系统性回退规则基线，回退率会暴露该问题，届时删除该字段重试并回填记录。
