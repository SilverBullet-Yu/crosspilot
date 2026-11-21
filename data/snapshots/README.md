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

## 当前快照的合规状态（2026-11-21 更新）

- `zhihu/旅行收纳包.json` 为**真实数据**（`is_demo_data=false`）：转录自 2026-11-18
  zhihu-cli v0.6.3 的真实采集成果（消耗 3/10 次搜索额度），引文、链接、AuthorityLevel、
  赞同数、时间戳逐字保留，溯源见工作区根目录（仓库外）的 `research/crosspilot-evidence_dim04.md` §4.1。
  收录 A/B/D 三条片段（EditTime 齐备，发布日期 2026-11-11 / 2026-10-10 / 2026-07-29）；
  C/E 两条因无发布日期元数据暂不收录（不以捕获日冒充发布日），待凭据重采补齐。
  片段 D 为中文二手归纳（AuthorityLevel=2 最低档），按 CONSTRAINTS 第四节仅计
  「问题来源」，不得作为德国消费者证据。
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
  `research/crosspilot-evidence_dim04.md`，工作区根目录），一次捕获消耗 1 次额度；额度耗尽时适配器
  抛 `QuotaExhaustedError` 并给出降级指引，**禁止静默返回空结果**（ADR-0002 决策 4）。
- 爬取红线（CONSTRAINTS 第四节）：只做实时检索 + 摘录引用（≤300 字符）+ 链接回源，
  **不建全文库**；适配器已硬实现摘录截断、作者匿名化与 PII 剔除。
- 快照有时效性：路演中必须主动说明数据截止时间（即快照 `generated_at_utc`），
  优于被评委问出（ADR-0002 后果节）。
