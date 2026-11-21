"""捕获知乎检索快照：live 模式 + 真实凭据 → 站内搜索 → 落盘 data/snapshots/zhihu/。

用途（ADR-0002 决策 2）：正式路演/演示前预跑「旅行收纳包 → 德国」，以真实检索结果
替换 data/snapshots/zhihu/ 下的演示撰写快照（演示标识规则见 docs/CONSTRAINTS.md 第四节，
操作说明见 data/snapshots/README.md）。

合规边界（本脚本只做这些）：
- 实时检索 + 摘录引用 + 链接回源，**不建全文库**：落盘内容经 zhihu_client 清洗链
  （剥 HTML → 剔 PII → 摘录 ≤300 字符），作者仅保留匿名化 ID。
- 配额保护：--dry-run 零消耗预检；真实调用捕获 QuotaExhaustedError 并给出降级指引，
  绝不重试硬撞额度（实测搜索 10 次/日）。

用法：
    export ZHIHU_ACCESS_SECRET="<Access Secret>"   # developer.zhihu.com 个人中心
    python scripts/capture_zhihu_snapshot.py --dry-run   # 试运行，不调用 API 不写文件
    python scripts/capture_zhihu_snapshot.py             # 默认检索「旅行收纳包」
    python scripts/capture_zhihu_snapshot.py --query "收纳包 德国"

退出码：0 成功；2 凭据缺失；3 配额耗尽；4 网络/响应异常。

本脚本不进 ruff/mypy 强检范围（check.sh 只检 apps/api 与 data/sources/_scripts），
但保持同等质量：完整类型注解、无未用导入。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))  # noqa: E402  # 未安装为包，注入 src

from crosspilot_api.config import settings  # noqa: E402
from crosspilot_api.services.zhihu_client import (  # noqa: E402
    QUOTA_GUIDANCE,
    REQUEST_COUNT,
    ZHIHU_SEARCH_URL,
    ZhihuCredentialError,
    ZhihuError,
    ZhihuExtraction,
    ZhihuNetworkError,
    ZhihuResponseError,
    QuotaExhaustedError,
    search_zhihu_extractions,
)
from crosspilot_api.services.zhihu_snapshot import (  # noqa: E402
    build_snapshot_document,
    sanitize_query_filename,
    snapshot_path,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="捕获知乎站内搜索快照（每次真实调用消耗 1 次搜索额度，实测 10 次/日）",
    )
    parser.add_argument("--query", default="旅行收纳包", help="检索关键词（默认：旅行收纳包）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将执行的请求与落盘路径，不调用 API、不写文件、不消耗额度",
    )
    return parser.parse_args(argv)


def print_plan(query: str) -> Path:
    """打印执行计划并返回落盘路径（dry-run 与真实执行共用，保证描述一致）。"""
    target = snapshot_path(query)
    print(f"端点：{ZHIHU_SEARCH_URL}（GET，站内搜索）")
    print(f"参数：Query={query!r} Count={REQUEST_COUNT}")
    print("鉴权：Bearer <ZHIHU_ACCESS_SECRET> + X-Request-Timestamp（秒级时间戳）")
    print(f"落盘：{target}（已存在时覆盖）")
    print("清洗：剥 HTML → 剔 PII（邮箱/电话）→ 摘录 ≤300 字符；作者仅保留匿名化 ID；不落全文")
    return target


def write_snapshot(query: str, extractions: list[ZhihuExtraction]) -> Path:
    """合规最小集 → 快照文档 → 落盘（覆盖既有文件前打印提示）。"""
    target = snapshot_path(query)
    if target.exists():
        print(f"提示：快照已存在，将覆盖 {target}")
    document = build_snapshot_document(extractions, is_demo_data=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query = args.query.strip()
    if not query:
        print("错误：--query 不能为空", file=sys.stderr)
        return 2

    target = print_plan(query)
    if args.dry_run:
        # dry-run 是零消耗预检：不调用 API 不写文件，因此不要求凭据。
        print("dry-run：以上为将执行的操作，本次未调用 API、未消耗额度、未写文件。")
        return 0

    # 凭据守卫：缺失时明确报错退出，绝不静默降级为空快照。
    secret = settings.zhihu_secret
    if not secret:
        print(
            "错误：未配置知乎凭据。请先在 developer.zhihu.com 个人中心获取 Access Secret，"
            "然后 export ZHIHU_ACCESS_SECRET=<secret>；未配置时禁止调用知乎 API。",
            file=sys.stderr,
        )
        return 2

    print(f"本次真实调用将消耗 1 次知乎搜索额度（{QUOTA_GUIDANCE}）。")
    try:
        extractions = search_zhihu_extractions(query, secret=secret)
    except QuotaExhaustedError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 3
    except ZhihuCredentialError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except (ZhihuNetworkError, ZhihuResponseError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 4
    except ZhihuError as exc:  # 兜底：适配器其他错误
        print(f"错误：{exc}", file=sys.stderr)
        return 4

    if not extractions:
        # 零命中也是有效结果：落盘空 cards 的快照，避免演示期反复消耗额度重查。
        print("提示：检索零命中，落盘空快照（EmptyReason 语义见端点文档）。")
    write_snapshot(query, extractions)
    generated = sanitize_query_filename(query)
    print(f"完成：{len(extractions)} 张卡已写入 {target}（查询词 {query!r} → 文件 {generated}.json）")
    print("提醒：路演中请主动说明数据截止时间（快照 generated_at_utc），优于被评委问出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
