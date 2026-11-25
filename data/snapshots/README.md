# data/snapshots/ —— 演示快照目录（ADR-0002）

本目录存放演示默认使用的本地快照（`CROSSPILOT_DATA_MODE` 默认 `snapshot`，只读本目录，
`live` 需显式开启）。当前仅有知乎 L2 中文侧子目录 `zhihu/`。

## 目录结构

```
data/snapshots/
  zhihu/<查询词>.json   # 知乎站内搜索快照，文件名 = 查询词（非法字符替换为 _）
```

快照文件 schema（唯一校验口径：`apps/api/src/crosspilot_api/services/zhihu_snapshot.py`）：
顶层必现 `generated_at_utc` / `source_api` / `cards[]`；卡字段对齐
`packages/contracts/evidence-card.schema.json`（六必现字段 + stance）+ `is_demo_data`，
另附快照扩展 `title` / `author_anonymous_id`（作者匿名化，合规最小集见
`services/zhihu_client.py`）。摘录一律 ≤300 字符（不落全文红线）。

**治理字段（2026-11-24 新增，修复 D-09）**，由 `validate_quality.py` 对
`is_demo_data=false` 的快照强制校验：

| 字段 | 作用 |
|---|---|
| `captured_at` | API 实际检索日。**判断新鲜度一律以此为准** |
| `freshness_note` | 显式区分 `captured_at` 与 `generated_at_utc`，防止消费端用文件生成时间冒充采集日 |
| `raw_payload_ref` | 脱敏原始响应的路径 + SHA-256；无原件时须 `status: "missing"` 并说明原因与补救方式 |
| `excluded_cards` | 被排除片段的 ContentID 与原因，使"快照≠完整采集结果"可审计 |
| `completeness` | 检索次数、返回数、相关片段数、收录/排除数；引用样本量以 `cards_kept` 为准 |

`capture_zhihu_snapshot.py` 现会把脱敏后的原始响应落盘到
`data/snapshots/zhihu/raw/{查询词}_{captured_at}.json` 并自动登记上述字段。
脱敏规则：剔除作者昵称/头像/认证与精选评论，`ContentText` 按 300 字符截断，
保留 `Title`/`ContentID`/`Url`/`EditTime`/统计数以便逐字复核。

## 当前快照的合规状态（2026-11-24 更新）

- `zhihu/旅行收纳包.json` 为**真实数据**（`is_demo_data=false`）：转录自 2026-11-18
  zhihu-cli v0.6.3 的真实采集成果（消耗 3/10 次搜索额度），引文、链接、AuthorityLevel、
  赞同数、时间戳逐字保留，溯源材料见 `docs/research/CrossPilot_证据_dim04_知乎实查记录.md` §4.1。
  收录 A/B/D 三条片段（EditTime 齐备，发布日期 2026-11-11 / 2026-10-10 / 2026-07-29）；
  C/E 两条因无发布日期元数据暂不收录（不以捕获日冒充发布日），已记入 `excluded_cards`。
  片段 D 为中文二手归纳（AuthorityLevel=2 最低档），按 CONSTRAINTS 第四节仅计
  「问题来源」，不得作为德国消费者证据。
- **该快照无原始 API 响应**（`raw_payload_ref.status="missing"`）：2026-11-18 采集时
  未保存原始 JSON，且历史响应不可重放，故不可逐字复核；卡片字段的权威版本是
  `source_url` 对应的知乎页面。后续采集由 capture 脚本自动落盘脱敏原件。
- 链接为 API 原样返回；2026-11-21 匿名 curl 实测 403/超时为知乎反爬，浏览器可正常打开。
- 演示撰写的样例已迁至 `apps/api/tests/fixtures/zhihu/旅行收纳包.json`（测试专用，
  全部 `is_demo_data=true`），加载器强制同一快照文件内演示/真实标识一致、不混排。

## 需要更新快照时

**用捕获脚本以真实凭据预跑**（覆盖上面的真实快照或新增其他查询词）：

```bash
# 1. 导出凭据（developer.zhihu.com 个人中心获取 Access Secret）
export ZHIHU_ACCESS_SECRET="<你的 Access Secret>"

# 2. 预跑（可先 --dry-run 查看将执行的请求与落盘路径，不调用 API 不写文件）
python scripts/capture_zhihu_snapshot.py            # 默认检索「旅行收纳包」
python scripts/capture_zhihu_snapshot.py --dry-run  # 试运行

# 3. 校验落盘快照可被加载
#    （服务以 snapshot 模式启动后 GET /api/evidence?query=旅行收纳包 应返回 l2_cards）
```

注意：

- 实测额度 **知乎搜索 10 次/日**（手册称 5000，差 500 倍，见
  `docs/research/CrossPilot_证据_dim04_知乎实查记录.md`），一次捕获消耗 1 次额度；额度耗尽时适配器
  抛 `QuotaExhaustedError` 并给出降级指引，**禁止静默返回空结果**（ADR-0002 决策 4）。
- 爬取红线（CONSTRAINTS 第四节）：只做实时检索 + 摘录引用（≤300 字符）+ 链接回源，
  **不建全文库**；适配器已硬实现摘录截断、作者匿名化与 PII 剔除。
- 快照有时效性：路演中必须主动说明数据截止时间（即快照 `captured_at`，**不是**
  `generated_at_utc`——后者只是转录文件的生成时间），优于被评委问出（ADR-0002 后果节）。
- 每次捕获会在 `zhihu/raw/` 落盘脱敏原始响应并登记 SHA-256；该目录内容属原始
  响应，受 `data/sources/*/raw/` 同类治理口径约束，公开仓库只保留脱敏衍生件。
