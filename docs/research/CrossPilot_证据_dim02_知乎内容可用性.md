# 维度 02｜知乎内容是否可用且有增量（对应清单 P0-2）

核对日期：2026-11-18

## 2.1 官方查询入口、申请方式、配额、返回字段

**入口与申请方式（已核实）**[^docs]

- 文档中心：<https://developer.zhihu.com/docs>
- 鉴权：`Authorization: Bearer <access_secret>` + `X-Request-Timestamp`（秒级 Unix 时间戳）
- Access Secret 在开放平台个人中心 <https://developer.zhihu.com/profile> 自助生成
- 本次比赛官方推荐路径：下载黑客松官方 Skill 交给 Agent 调用[^manual]
  <https://developer-cdn.zhihu.com/zhihu-cli/releases/stable/skill/zhihu-cli-skill.zip>

**配额（已核实，来自手册技术指南）**[^manual]

| 能力 | 单用户上限 |
| --- | --- |
| 知乎热榜 | 100 次/天 |
| 知乎搜索 | 5000 次/天 |
| 直答 Agent | 100 次/天 |
| 全网搜索 | 抓取到的段落未写明数值，需用 `quota` 实测 |

**知乎搜索 API 返回字段（已核实）**[^search]

`Title`、`Headline`、`ContentType`、`ContentID`、**`ContentText`（字段定义为「内容摘要」）**、`Url`（带溯源 UTM 参数）、`CommentCount`、`VoteUpCount`、`AuthorName`、`AuthorAvatar`、`AuthorBadge`、`AuthorBadgeText`、`EditTime`、`CreateTime`、`CommentInfoList`（精选评论，仅 `Content`）、`AuthorityLevel`、`RankingScore`。

请求侧约束：`Count` 默认 10、**最大 10**；`HasMore` 当前实现固定返回 `false`。

## 2.2 四类权限分别核实：能查询 ≠ 能建库

清单要求分别核实「摘录展示 / 内容留存 / 模型处理 / 建库」四类权限。核实结果：

| 权限类型 | 结论 | 依据 |
| --- | --- | --- |
| 摘录展示 | **可行**。接口返回 `ContentText` 摘要与带 UTM 的 `Url`，设计用途即为展示并回源 | 搜索 API 字段定义[^search] |
| 内容留存 | **受限**。接口不返回正文全文，`ContentText` 为摘要；留存只能是「摘要 + 链接 + 时间」级别的引用记录 | 搜索 API 字段定义[^search] |
| 模型处理 | **可行但受配额约束**。直答 Agent 为官方提供的模型侧能力，100 次/天 | 手册技术指南[^manual] |
| 建立全文库 / 向量库 | **不可行**。① 搜索接口无全文字段，单次最多 10 条且 `HasMore` 固定 false，不提供翻页遍历；② 手册明文「严禁批量爬取、滥用站内用户数据」；③ 官方知识库 API 只接受**本地文件上传**（`multipart/form-data`，pdf/md/txt/docx 等扩展名），不提供「把搜索结果灌入知识库」的接口 | 搜索 API[^search]、手册合规条款[^manual]、知识库上传 API[^kbup]、知识库检索 API[^kbsearch] |

**这条结论直接推翻了原方案的一项技术设计。** 方案 5.1 写有「可选 pgvector / ChromaDB（语义检索）」用于知乎侧内容。合规可行的形态只能是：

> 实时调用知乎搜索 → 保留「标题 + 摘要 + 作者 + 链接 + 时间 + 赞同/评论数 + 权威等级」作为证据卡字段 → 展示时回源链接。

自建向量库的对象只能是**用户自行上传的、有授权的企业资料**，不能是知乎站内内容。

附带可用信号：`AuthorityLevel`（权威等级）与 `RankingScore` 可作为证据卡的来源质量标注字段，这是原方案未利用的现成能力。

## 2.3 实查「旅行收纳包／出海卖点 × 容量／便携」

**状态：阻塞，未执行。**

阻塞原因：本机知乎 CLI 未安装且未配置 Access Secret。状态检查返回：

```json
{"installed": false, "next_action": "request_install_consent", "auth": {"configured": false}}
```

同时 `web_extract` 对 `zhihu.com` 域名返回 `Domain is blocked`，无法用通用抓取通道替代官方接口做站内检索。

**解除条件（二选一，均需你方操作）：**
1. 授权安装知乎 CLI，并在 <https://developer.zhihu.com/profile> 生成 Access Secret 后提供；之后可直接执行实查并记录检索词、日期、链接与片段。
2. 你方自行在开放平台调用搜索接口，把返回结果提供给我做整理与归因标注。

**注意：** 该项即便完成，按清单口径也只能计为「问题来源」，不计为德国消费者证据。

## 2.4 能改变核查方向的问题

**状态：方法已就绪，结论待 2.3 完成后产出。**

清单举例的「容量带来的装载收益是否会被携带不便抵消」这一问句，在证据层面属于**可由知乎从业经验提出、但必须由德国侧反馈回答**的典型结构。在 2.3 未完成前，不能把它写成「知乎已提出的问题」——那会把假设伪装成证据。

## 状态

| 清单项 | 状态 |
| --- | --- |
| 官方入口、申请方式、配额、返回字段 | **已核实** |
| 摘录展示 / 留存 / 模型处理 / 建库 四类权限分别核实 | **已核实**（建库判定为不可行） |
| 实查并记录检索词与片段 | **阻塞**：CLI 未安装、Secret 未配置 |
| 提取可改变核查方向的问题并由运营确认 | **阻塞**：依赖上一项 + 运营方确认 |

[^docs]: 知乎数据开放平台 · 文档中心（Bearer 鉴权说明）. 2026-11-18 读取. https://developer.zhihu.com/docs
[^search]: 知乎数据开放平台 · 知乎搜索 API. 2026-11-18 读取. https://developer.zhihu.com/docs?key=zhihu_search
[^kbup]: 知乎数据开放平台 · 知识库文件上传 API. 2026-11-18 读取. https://developer.zhihu.com/docs?key=knowledge_file_upload
[^kbsearch]: 知乎数据开放平台 · 知识库检索 API. 2026-11-18 读取. https://developer.zhihu.com/docs?key=knowledge_search
[^manual]: 知乎黑客松S3·湾区共创季 开发者手册（最新修改 2026-11-05）. 2026-11-18 读取. https://pcnsiq9mmnww.feishu.cn/wiki/W1DVwHiJSigXq1k6ys7cHTuOnBe
