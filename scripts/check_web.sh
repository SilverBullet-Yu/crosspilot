#!/usr/bin/env bash
# 前端冒烟自检：npm run build → 独立端口起产物服务 → 三场景 SSR HTML 内容断言。
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

echo "==> [3/3] 三场景 SSR 内容断言"
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

pages = {s: fetch(f"/?scenario={s}") for s in ("real", "conflict", "limited")}

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

# --- 场景 conflict：红横幅 / 左右并排 / L1 演示卡 ---
r = pages["conflict"]
check("证据相互冲突" in r, "conflict: 横幅标题=证据相互冲突（红）")
check("banner__demo-chip" in r, "conflict: 「演示场景 · 模拟回填」chip 在横幅中")
check("hypo__groups--conflict" in r, "conflict: 支持证据/相反证据左右并排类名(hypo__groups--conflict)")
check('class="egroup egroup--support"' in r and 'class="egroup egroup--oppose"' in r,
      "conflict: 支持组/相反组结构在页面中")
check(r.count("card--demo") >= 4, f"conflict: L1 演示卡 card--demo ≥4（实测 {r.count('card--demo')}）")
check(r.count("L1 一手反馈") >= 4, f"conflict: L1 徽标 ≥4（实测 {r.count('L1 一手反馈')}）")
check(r.count("以下为演示数据（模拟回填）") >= 3,
      f"conflict: 「不与真实反馈混排」分隔条 ≥3（实测 {r.count('以下为演示数据（模拟回填）')}）")
check(r.count('target="_blank"') >= 4, f"conflict: target=_blank ≥4（实测 {r.count('target=\"_blank\"')}）")
check('class="l2zone"' not in r, "conflict: 不渲染 L2 小节（演示场景仅回填 L1）")

# --- 场景 limited：绿横幅 / 有限支持 ---
r = pages["limited"]
check("已有有限支持" in r, "limited: 横幅标题=已有有限支持（绿）")
check("banner__demo-chip" in r, "limited: 「演示场景 · 模拟回填」chip 在横幅中")
check(r.count("card--demo") >= 2, f"limited: L1 演示卡 card--demo ≥2（实测 {r.count('card--demo')}）")
check(r.count("L1 一手反馈") >= 2, f"limited: L1 徽标 ≥2（实测 {r.count('L1 一手反馈')}）")
check(r.count("样本量未知·有偏差风险") >= 1, "limited: 样本量未知显式标注（不静默）")
check(r.count("以下为演示数据（模拟回填）") >= 1, "limited: 演示分隔条 ≥1")
check(r.count('target="_blank"') >= 3, f"limited: target=_blank ≥3（实测 {r.count('target=\"_blank\"')}）")
check('class="l2zone"' not in r, "limited: 不渲染 L2 小节")

# --- 全局：demo-note 合规说明 + 页脚 ---
# 演示卡合规说明文案只应出现在含演示卡的场景（conflict/limited）；
# real 场景已全部为真实数据（L3 语境 + L2 真实片段），不得出现演示说明。
for s, r in pages.items():
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
