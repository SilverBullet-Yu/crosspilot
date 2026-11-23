#!/usr/bin/env bash
# 前端冒烟自检：npm run build → 独立端口起产物服务 → SSR HTML 内容断言。
# 覆盖：工作台三场景（/workbench?scenario=…）+ 产品概览落地页（/）。
# 运行时机：前端改动后 / 提交前，独立于 scripts/check.sh（后者保持五道不动，本脚本不并入）。
# 说明：若 3000 端口有 dev 在跑，本脚本不受影响——断言走 build 产物 + 3100 端口；
#       但 build 与 dev 共用 .nuxt，若 build 偶发 EPERM/EBUSY，先停 dev 再跑本脚本。
set -euo pipefail
cd "$(dirname "$0")/../apps/web"

PORT=3100
export NUXT_TELEMETRY_DISABLED=1

echo "==> [1/3] npm run build（失败即退出非零）"
npm run build

echo "==> [2/3] 启动产物服务（node .output/server/index.mjs，端口 $PORT，避免与 dev:3000 冲突）"
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

echo "==> [3/3] SSR 内容断言（工作台三场景 + 落地页）"
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

results: list[tuple[bool, str]] = []

def check(ok: bool, label: str) -> None:
    results.append((ok, label))

# --- 场景 real：黄横幅 / L2 小节（真实知乎数据）/ 无演示标识 ---
r = pages["real"]
check("缺少有效数据" in r, "real: 横幅标题=缺少有效数据（黄）")
check('mode-badge--snapshot' in r and "快照 snapshot" in r, "real: 数据模式徽标=快照 snapshot")
check("本地 fixtures" in r, "real: 数据源=本地 fixtures")
check('class="l2zone"' in r, "real: 右栏渲染「中文侧经验（L2 · 知乎）」小节(l2zone)")
check("中文侧经验" in r, "real: L2 小节标题文案在页面中")
check(r.count("card--demo") == 0, f"real: 无演示卡（L2 已换真实数据，实测 card--demo={r.count('card--demo')}）")
check("（演示撰写）" not in r, "real: 不含「（演示撰写）」字样（真实快照数据）")
check("zhuanlan.zhihu.com" in r or "zhihu.com" in r, "real: L2 卡链接回源知乎")
check(r.count("L2 二手转述") >= 3, f"real: L2 徽标 ≥3（实测 {r.count('L2 二手转述')}）")
check(r.count("L3 宏观语境") >= 3, f"real: L3 徽标 ≥3（实测 {r.count('L3 宏观语境')}）")
check(r.count('target="_blank"') >= 6, f"real: 来源链接 target=_blank ≥6（实测 {r.count('target=\"_blank\"')}）")
check("未归属证据" in r, "real: 未归属证据组在页面中")
check(r.count("缺少有效数据（L1 零样本）") >= 3, "real: 三组黄底空状态卡醒目（非灰字）")
check("banner__demo-chip" not in r, "real: 不出现「演示场景 · 模拟回填」chip（非演示场景）")

# --- 场景 conflict：红横幅 / 左右并排 / L1 演示卡 / 判定可追溯小字 ---
r = pages["conflict"]
check("证据相互冲突" in r, "conflict: 横幅标题=证据相互冲突（红）")
check("banner__demo-chip" in r, "conflict: 「演示场景 · 模拟回填」chip 在横幅中")
check("hypo__groups--conflict" in r, "conflict: 支持证据/相反证据左右并排类名(hypo__groups--conflict)")
check('class="egroup egroup--support"' in r and 'class="egroup egroup--oppose"' in r,
      "conflict: 支持组/相反组结构在页面中")
check(r.count("card--demo") >= 30, f"conflict: L1 演示卡 card--demo ≥30（实测 {r.count('card--demo')}）")
check(r.count("L1 一手反馈") >= 30, f"conflict: L1 徽标 ≥30（实测 {r.count('L1 一手反馈')}）")
check(r.count("以下为演示数据（模拟回填）") >= 3,
      f"conflict: 「不与真实反馈混排」分隔条 ≥3（实测 {r.count('以下为演示数据（模拟回填）')}）")
check(r.count('target="_blank"') >= 30, f"conflict: target=_blank ≥30（实测 {r.count('target=\"_blank\"')}）")
check('class="l2zone"' not in r, "conflict: 不渲染 L2 小节（演示场景仅回填 L1）")
check("支持份额 95% 区间" in r, "conflict: 判定可追溯小字=两份额 Wilson 区间可见（ADR-0005）")
check('class="gauge"' in r, "conflict: 判定带 Wilson 区间标尺仪表渲染")
check("去重 2 条" in r, "conflict: 去重摘要可见（dup>0：R2 去重先于计数可追溯）")
check("样本量 n=1" in r, "conflict: 单卡样本量逐卡可见")

# --- 场景 limited：绿横幅 / 有限支持（公式判定：区间下界刚过决定线）---
r = pages["limited"]
check("已有有限支持" in r, "limited: 横幅标题=已有有限支持（绿）")
check("banner__demo-chip" in r, "limited: 「演示场景 · 模拟回填」chip 在横幅中")
check(r.count("card--demo") >= 25, f"limited: L1 演示卡 card--demo ≥25（实测 {r.count('card--demo')}）")
check(r.count("L1 一手反馈") >= 25, f"limited: L1 徽标 ≥25（实测 {r.count('L1 一手反馈')}）")
check("支持份额 95% 区间" in r, "limited: 判定可追溯小字=区间下界 0.52 可见（「有限」=区间宽的公式化表达）")
check("门禁 pass" in r, "limited: 门禁状态可见（判定路径可追溯）")
check(r.count("样本量 n=1") >= 25, f"limited: 单卡样本量逐卡可见 ≥25（实测 {r.count('样本量 n=1')}）")
check(r.count("以下为演示数据（模拟回填）") >= 1, "limited: 演示分隔条 ≥1")
check(r.count('target="_blank"') >= 25, f"limited: target=_blank ≥25（实测 {r.count('target=\"_blank\"')}）")
check('class="l2zone"' not in r, "limited: 不渲染 L2 小节")

# --- 落地页（产品概览）：外壳导航 + hero 叙事 + 演示示例标识 ---
r = pages["landing"]
check("你的出海卖点" in r, "landing: hero 主标题在页面中")
check("海外用户需求吗" in r, "landing: hero 强调句在页面中")
check("开始验证" in r and 'href="/workbench"' in r, "landing: 开始验证按钮指向工作台")
check("卖点验证工作台" in r and "历史验证项目" in r, "landing: 侧栏三项导航齐备（外壳）")
check("演示模式 · Mock 数据" in r, "landing: 顶栏演示模式徽标在页面中")
check("当前为演示模式" in r, "landing: 演示模式提示在页面中")
check(r.count("模拟示例") >= 3, f"landing: 模拟示例标识 ≥3（实测 {r.count('模拟示例')}）")
check("证据冲突" in r, "landing: hero 卡结论条=证据冲突")
check("隔层越多越好" in r, "landing: hero 卡卖点假设在页面中")
check("判定不是拍脑袋" in r, "landing: 判定演示器在页面中（产品真实公式）")
check("边界用例" in r and "15 : 15" in r, "landing: 演示器真实边界用例预设可见")
check("高频疑问" in r, "landing: FAQ 区（质疑预案）在页面中")
check('class="gauge"' in r, "landing: 演示器 Wilson 区间标尺 SVG 渲染")

# --- 全局：demo-note 合规说明 + 页脚（仅工作台三场景；落地页为产品叙事，无场景页脚） ---
# 演示卡合规说明文案只应出现在含演示卡的场景（conflict/limited）；
# real 场景已全部为真实数据（L3 语境 + L2 真实片段），不得出现演示说明。
for s, r in pages.items():
    if s == "landing":
        continue
    if s == "real":
        check("演示数据：模拟回填，非真实德国消费者反馈" not in r, f"{s}: 无演示卡合规说明文案（全真实数据）")
    else:
        check("演示数据：模拟回填，非真实德国消费者反馈" in r, f"{s}: 演示卡合规说明文案在页面中")
    check(re.search(r"scenario=(real|demo_conflict|demo_limited)", r) is not None, f"{s}: 页脚 scenario 标识在页面中")

passed = sum(1 for ok, _ in results if ok)
for ok, label in results:
    print(("PASS " if ok else "FAIL ") + label)
print(f"==> 断言 {passed}/{len(results)} 通过")
sys.exit(0 if passed == len(results) else 1)
PYEOF

echo "==> check_web 全部通过"
