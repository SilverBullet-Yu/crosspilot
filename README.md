# CrossPilot 2.0

**出海卖点的上线前尽职调查工作台。**

帮准备进入德国市场的中国消费品牌，在商品详情页上线前回答一个问题：

> 这个卖点有没有真实用户证据支持？下一步该验证什么？

它不生成「德国消费者喜欢什么」的笼统结论，只把证据分层摆清楚，给出可执行的下一步。

## 产品逻辑

| 层级 | 证据 | 用途 |
|---|---|---|
| L1 | 德国消费者一手反馈 | 唯一能支撑「消费者偏好」结论 |
| L2 | 知乎中文从业经验 | 只产出待验证问题 |
| L3 | 监管、贸易、学术语境 | 只提供背景与约束 |

证据先按来源分层，再去重、计数、做 Wilson 区间估计，最后只输出四种状态：

- **缺少有效数据**：样本不足，不给结论
- **已有有限支持**：支持区间刚过决定线
- **多数反馈反对**：反对区间过决定线
- **证据相互冲突**：支持与反对同时成立

每轮输出证据卡、待验证问题、访谈问题与 A/B 测试方向。

## 演示场景

固定场景：旅行收纳包 × 德国市场 × 详情页首屏（容量、功能、低价三个卖点假设）。

| 场景 | 数据 | 判定 |
|---|---|---|
| `real` | 知乎真实快照 + L3 监管/贸易数据 | 缺少有效数据（德国 L1 尚未取得） |
| `limited` | 30 条分层模拟评论，21:9 | 已有有限支持 |
| `conflict` | 30 条分层模拟评论，15:15 + 重复摘录 | 证据相互冲突 |

演示数据均带显式标识，不与真实数据混排。

## 快速使用

要求：Python 3.12+、Node.js 20+、Git Bash（Windows）。

```bash
git clone https://github.com/SilverBullet-Yu/crosspilot.git
cd crosspilot

# 安装后端依赖、前端依赖，并生成 .env
bash scripts/bootstrap.sh

# 启动前端（默认读本地 fixtures，不需要后端、网络或凭据）
bash scripts/dev.sh web
```

打开 <http://localhost:3000>：

- `/`：产品概览
- `/workbench?scenario=real`：真实数据场景
- `/workbench?scenario=limited`：有限支持场景
- `/workbench?scenario=conflict`：证据冲突场景
- `/history`：历史验证项目（演示版为空态）

如需调用真实后端（另开终端）：

```bash
bash scripts/dev.sh api
NUXT_PUBLIC_API_BASE=http://localhost:8000 bash scripts/dev.sh web
```

凭据可选，仅在接入真实数据时需要，写入 `.env`：

| 变量 | 用途 |
|---|---|
| `ZHIHU_ACCESS_SECRET` | 知乎实时检索（实测 10 次/日） |
| `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` | LLM 立场抽取；缺省回退规则基线 |
| `COMTRADE_SUBSCRIPTION_KEY` | UN Comtrade 正式取数 |

Demo 默认快照模式，只读 `data/snapshots/`；实时模式需显式设 `CROSSPILOT_DATA_MODE=live`。

提交前自检：

```bash
bash scripts/check.sh      # ruff + mypy + 全量测试 + 数据区校验
bash scripts/check_web.sh  # 前端 56 断言
```

> 克隆后若 `check.sh` 的数据区校验红灯，通常是本地没有 MARC 主表：该数据依许可禁再发布，不随仓库分发，属预期。CI 只跑 ruff / mypy / 测试。

## 目录地图

| 路径 | 职责 |
|---|---|
| `apps/api/` | FastAPI 后端：检索、立场抽取、证据分层、判定 |
| `apps/web/` | Nuxt 4 + Vue 3 工作台前端 |
| `packages/contracts/` | 前后端共享证据卡契约 |
| `data/sources/` | 9 个外部数据源，每源四件套 + raw |
| `data/snapshots/` | 演示预跑快照，Demo 只读这里 |
| `data/licenses/` | 数据许可原件 |
| `docs/` | 状态、清单、需求、调研、报告、ADR、演示与开发日志 |
| `scripts/` | 初始化、启动与自检脚本 |

## 五条硬约束

1. L2/L3 证据不得单独支撑「消费者偏好」结论
2. MARC 数据集在商业化路径启动即下线
3. OPUS 只取 ParaCrawl，排除 OpenSubtitles
4. Comtrade 必须注册账号，禁用 preview 的截断结果
5. DeepL API Free 档禁止传入含个人数据的文本

另有两条产品级强制项：**证据不足必须渲染为独立空状态卡片**，**证据冲突必须左右并排原文**。

## 数据与许可

- 代码：MIT（见 [LICENSE](LICENSE)）
- 数据：逐源声明许可，汇总见 [data/sources/README.md](data/sources/README.md)
- MARC 依 Amazon 学术研究许可**禁再发布**，不随仓库分发
- 知乎内容只做实时检索 + 摘要引用 + 链接回源，不建全文库

## 文档与协作

- 文档总索引：[docs/README.md](docs/README.md)
- 当前状态与接管：[docs/status/STATUS.md](docs/status/STATUS.md)
- 演示 Runbook：[docs/demo/演示说明.md](docs/demo/演示说明.md)
- 分支：`feat/*`、`fix/*`、`docs/*`；提交信息 `type(scope): summary`
- 合并前 `bash scripts/check.sh` 全绿；每次 AI 辅助开发后在 `docs/devlog/` 追加记录
