"""Amazon Reviews 2023 试点接入（L1 一手评论，Apache-2.0，Amazon.com 美国全站）。

镜像能力边界（2026-11-21 实测，本机）：
- huggingface.co 官方站 TCP 443 仍全程超时，不可达。
- hf-mirror.com 可用：/api/datasets/{repo} 200；/tree 200；/resolve/ 文件下载
  307 -> 镜像内 resolve-cache -> 302 -> cas-bridge.xethub.hf.co（官方 CDN，
  本机可达），支持 Range（206）与 HEAD（X-Linked-Size/X-Linked-Etag 给出
  精确字节数与 sha256，用于完整性校验）。
- 镜像不代理 datasets-server：/rows 307 到 /Rows 网页路由，/filter 返回网页
  HTML，均不是 JSON API。故「≤100 行显式分页」路径不可用。
- /api/datasets/{repo}/parquet 返回 400：该数据集是脚本加载型（runs arbitrary
  Python code），viewer 不支持，无 parquet 分片可下。接入路径只能是
  /resolve/ 直下原始 jsonl 分片 + 本地过滤。
- 镜像共享 HF 配额 10000 次/5 分钟，超限返回 429 并带 retryAfter 秒数；
  本脚本固定请求间隔并在 429 时按 retryAfter 退避。

结构（实测）：
- 34 个品类全部为 Amazon.com 类目（all_categories.txt）；无独立
  Luggage/Travel_Accessories 品类；评论无 language/marketplace 列，
  官方 tags 标 language:en —— 无法筛出德国/德语子集，对德国市场
  不构成 L1（README 详述）。
- 评论分片 raw/review_categories/{category}.jsonl；字段 rating/title/text/
  images/asin/parent_asin/user_id/timestamp(ms)/verified_purchase/helpful_vote。
- 元数据分片 raw/meta_categories/meta_{category}.jsonl，经 parent_asin 联结。

试点量级纪律：仅下载 1 个最小评论分片（Subscription_Boxes，约 8.5MB）+
对应最小 meta 分片（约 1.3MB）+ 品类清单与官方 README，合计约 10MB，
远低于 200MB 上限。这是管线试点，不是全量迁移；品类相关分片
（Clothing_Shoes_and_Jewelry 26.5GB 等）超出试点预算，见 README。

中断恢复：已落盘且大小与镜像一致的原始文件直接跳过；探测结论缓存在
raw/probe_summary.json，存在且结论齐备即不再重复探测；主表每次从本地
raw 重建。provenance.csv 按 URL 去重合并（保留最新一次调用），重跑不丢
历史留痕。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    UA,
    WINDOW_END,
    WINDOW_START,
    Call,
    Provenance,
    now_utc,
    write_csv,
    write_manifest,
)

OUT = Path(__file__).resolve().parents[1] / "amazon_reviews_2023"
RAW_DIR = OUT / "raw"
MIRROR = "https://hf-mirror.com"
REPO = "McAuley-Lab/Amazon-Reviews-2023"
RAW_BASE = f"{MIRROR}/datasets/{REPO}/resolve/main"
API_BASE = f"{MIRROR}/api/datasets/{REPO}"
# 试点分片：全库最小评论分片 + 对应最小 meta 分片（tree API 实测字节数）
REVIEW_SHARD = "Subscription_Boxes"
META_SHARD = "Subscription_Boxes"
# 共享配额 10000 次/5 分钟：固定间隔 + 429 按 retryAfter 退避
SPACING_S = 2.5
BACKOFF_S = 8.0
MAX_RETRY_AFTER_S = 180.0
# 主表字段截断（与 Safety Gate 清洗口径一致）；raw/ 保留全文
TITLE_MAX = 200
TEXT_MAX = 600
# 时间覆盖密度阈值，与 validate_coverage.py 的 MIN_DENSITY 一致
MIN_DENSITY = 0.5
MAIN_TABLE = "amazon_reviews_2023_pilot_2021_2026.csv"
# 个人数据清洗：剔除邮箱、电话（与 fetch_safety_gate.py 同一正则口径）
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){7,14}\d(?!\d)")


def review_id(dp: dict[str, object]) -> str:
    """稳定评论 ID（修复 D-05）。

    源数据没有原生 review_id，早期主表只能用 `(asin, timestamp_ms)` 这种弱
    组合键去重，窗口内出现 61 个重复键。实测 `(user_id, asin, timestamp)`
    在分片内可唯一区分 16,016/16,216 条记录，其余 200 条是源端重复投递
    （198 条整条逐字段相同）。

    ID 取该三元组的 sha1 前 16 位：
    - 稳定可复现：同一条评论每次重建得到同一 ID；
    - 不泄露 user_id：主表按数据最小化不写入 user_id（GDPR），哈希不可逆；
    - 可用于下游去重、样本量统计与证据卡溯源。
    """
    key = "|".join([
        str(dp.get("user_id") or ""),
        str(dp.get("asin") or ""),
        str(dp.get("timestamp") or ""),
    ])
    # sha1 在此仅作稳定标识（非安全用途）：不做认证、不防篡改
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def sha256_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def scrub(text: str) -> str:
    """自由文本剔除邮箱与电话。评论描述体验而非个人，但正文可能夹带联系方式。"""
    text = RE_EMAIL.sub("[email-removed]", text)
    return RE_PHONE.sub("[phone-removed]", text)


def window_ms() -> tuple[int, int]:
    """从 common 单点时间窗推导毫秒区间，不在本脚本散落硬编码。"""
    start = datetime.strptime(WINDOW_START, "%Y-%m-%d").replace(tzinfo=UTC)
    end = datetime.strptime(WINDOW_END, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(start.timestamp() * 1000), int((end.timestamp() + 86399) * 1000)


def _retry_wait_s(exc: urllib.error.HTTPError, body: bytes) -> float:
    """429 时从 Retry-After 头或响应体 JSON 的 retryAfter 取等待秒数。"""
    wait = 0.0
    header = exc.headers.get("Retry-After") or ""
    if header.isdigit():
        wait = float(header)
    try:
        payload = float(json.loads(body.decode("utf-8", "replace")).get("retryAfter", 0))
        wait = max(wait, payload)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError, AttributeError):
        pass
    if wait <= 0:
        wait = 8.0
    return min(wait + 3.0, MAX_RETRY_AFTER_S)


def mirror_get(url: str, *, prov: Provenance, note: str = "", timeout: int = 120,
               retries: int = 3, capture_error_body: bool = False) -> bytes | None:
    """镜像 GET：固定间隔、429 按 retryAfter 退避、逐次留痕。

    - 4xx（400/404 等）是探测的**结论性结果**而非网络失败：capture_error_body
      为 True 时把响应体返回给调用方解析（如 parquet 400 的 error 文案）；
      为 False（下载场景）直接返回 None，避免把错误页写进 raw/。
    - 429 按 retryAfter 退避重试；5xx 按固定退避重试。
    """
    for attempt in range(1, retries + 1):
        time.sleep(SPACING_S)
        started = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                status = resp.status
            prov.record(Call("amazon_reviews_2023", url, status, len(body),
                             time.time() - started, sha256_of(body), now_utc(),
                             f"{note} attempt={attempt}".strip()))
            return body
        except urllib.error.HTTPError as exc:
            err_body = exc.read()
            last = f"HTTP {exc.code}"
            prov.record(Call("amazon_reviews_2023", url, exc.code, len(err_body),
                             time.time() - started, sha256_of(err_body), now_utc(),
                             f"{note} attempt={attempt} {last}".strip()))
            if attempt >= retries:
                print(f"  [!] 放弃 {url[:90]} ({last})")
                return err_body if capture_error_body else None
            if exc.code == 429:
                wait = _retry_wait_s(exc, err_body)
                print(f"  [429] {note} 共享配额限速，等待 {wait:.0f}s")
                time.sleep(wait)
            elif 500 <= exc.code < 600:
                time.sleep(BACKOFF_S * attempt)
            else:
                return err_body if capture_error_body else None  # 结论性 4xx
        except Exception as exc:  # noqa: BLE001 - 网络层异常种类多，统一留痕
            prov.record(Call("amazon_reviews_2023", url, "ERR", 0,
                             time.time() - started, "", now_utc(),
                             f"{note} attempt={attempt} {type(exc).__name__}".strip()))
            if attempt >= retries:
                print(f"  [!] 放弃 {url[:90]} ({type(exc).__name__})")
                return None
            time.sleep(BACKOFF_S * attempt)
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """禁用自动重定向，用于手动追踪 /resolve/ 的 307 -> 302 链。"""

    def redirect_request(self, req: urllib.request.Request, fp, code, msg,
                         headers, newurl):  # type: ignore[override]
        return None


def head_probe(url: str, *, prov: Provenance) -> tuple[int, str]:
    """HEAD 追踪重定向链，取 X-Linked-Size（精确字节数）与 X-Linked-Etag
    （文件 sha256）。provenance 只记规范 URL 一行，避免签名 CDN URL
    （每次都变）污染留痕。"""
    opener = urllib.request.build_opener(_NoRedirect)
    current = url
    for _hop in range(5):
        time.sleep(SPACING_S)
        started = time.time()
        req = urllib.request.Request(current, headers={"User-Agent": UA},
                                     method="HEAD")
        try:
            with opener.open(req, timeout=60) as resp:
                headers, code = resp.headers, resp.status
        except urllib.error.HTTPError as exc:
            headers, code = exc.headers, exc.code
        except Exception as exc:  # noqa: BLE001 - 网络层异常统一留痕
            prov.record(Call("amazon_reviews_2023", url, "ERR", 0,
                             time.time() - started, "", now_utc(),
                             f"HEAD {type(exc).__name__}"))
            return 0, ""
        size = int(headers.get("X-Linked-Size") or headers.get("Content-Length") or 0)
        etag = (headers.get("X-Linked-Etag") or "").strip('"')
        if size:
            prov.record(Call("amazon_reviews_2023", url, code, 0,
                             time.time() - started, "", now_utc(),
                             f"HEAD X-Linked-Size={size} etag={etag[:16]} "
                             f"final_host={urllib.parse.urlparse(current).hostname}"))
            return size, etag
        loc = headers.get("Location") or ""
        if code in (301, 302, 307, 308) and loc:
            current = urllib.parse.urljoin(current, loc)
            continue
        prov.record(Call("amazon_reviews_2023", url, code, 0, time.time() - started,
                         "", now_utc(), f"HEAD 无尺寸信息（HTTP {code}）"))
        return 0, ""
    prov.record(Call("amazon_reviews_2023", url, "ERR", 0, 0.0, "", now_utc(),
                     "HEAD 重定向链超过 5 跳"))
    return 0, ""


def tree_sizes(body: bytes | None) -> dict[str, int]:
    """从 tree API 响应提取 {文件名: 字节数}。"""
    if not body:
        return {}
    try:
        items = json.loads(body.decode("utf-8", "replace"))
        return {it["path"].split("/")[-1]: int(it.get("size") or 0) for it in items}
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError,
            UnicodeDecodeError):
        return {}


def load_sizes() -> dict[str, int]:
    """合并三份 tree 清单的文件大小，供下载前做「已存在即跳过」判断。"""
    sizes: dict[str, int] = {}
    for name in ("api_tree_main.json", "api_tree_review_categories.json",
                 "api_tree_meta_categories.json"):
        path = RAW_DIR / name
        if path.exists():
            sizes.update(tree_sizes(path.read_bytes()))
    return sizes


def is_html(body: bytes | None) -> bool:
    """镜像把 /rows /filter 等路径路由到网页，返回 HTML 而非 JSON API。"""
    return body is None or body.lstrip()[:9].lower().startswith(b"<!doctype")


def run_probes(prov: Provenance) -> dict[str, object]:
    """镜像能力边界探测。结论写入 raw/probe_summary.json，重跑时复用。"""
    marker = RAW_DIR / "probe_summary.json"
    if marker.exists():
        cached = json.loads(marker.read_text(encoding="utf-8"))
        if cached.get("probes_conclusive"):
            print("[probe] 复用既有探测结论 raw/probe_summary.json")
            return cached

    print("[probe] 探测 hf-mirror.com 能力边界")
    summary: dict[str, object] = {}
    conclusive = True

    meta_body = mirror_get(API_BASE, prov=prov, note="api_meta")
    summary["api_meta"] = "200 可达" if meta_body is not None else "不可达，须重跑复核"
    conclusive = conclusive and meta_body is not None

    parquet_body = mirror_get(f"{API_BASE}/parquet", prov=prov, note="api_parquet",
                              capture_error_body=True)
    if parquet_body is not None:
        try:
            err = str(json.loads(parquet_body.decode("utf-8", "replace")).get("error", ""))
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            err = "响应体非 JSON error"
        summary["api_parquet"] = f"400（结论性）：{err[:160]}"
    else:
        summary["api_parquet"] = "未取得响应（网络受限），须重跑复核"
        conclusive = False

    tree_main = mirror_get(f"{API_BASE}/tree/main", prov=prov, note="tree_main")
    if tree_main is not None:
        (RAW_DIR / "api_tree_main.json").write_bytes(tree_main)
        summary["api_tree"] = ("200 可达（顶层含 Amazon-Reviews-2023.py 加载脚本、"
                               "all_categories.txt 与 raw/ 目录）")
    else:
        summary["api_tree"] = "不可达，须重跑复核"
        conclusive = False

    tree_reviews_body = mirror_get(f"{API_BASE}/tree/main/raw/review_categories",
                                   prov=prov, note="tree_review_categories")
    tree_meta_body = mirror_get(f"{API_BASE}/tree/main/raw/meta_categories",
                                prov=prov, note="tree_meta_categories")
    if tree_reviews_body is not None:
        review_sizes = tree_sizes(tree_reviews_body)
        (RAW_DIR / "api_tree_review_categories.json").write_bytes(tree_reviews_body)
        smallest = sorted(review_sizes.items(), key=lambda kv: kv[1])[:1]
        summary["api_tree_review_categories"] = (
            f"200 可达，{len(review_sizes)} 个品类分片；最小分片 {smallest}")
    else:
        summary["api_tree_review_categories"] = "不可达，须重跑复核"
        conclusive = False
    if tree_meta_body is not None:
        (RAW_DIR / "api_tree_meta_categories.json").write_bytes(tree_meta_body)
    else:
        summary["api_tree_meta_categories"] = "不可达，须重跑复核"
        conclusive = False

    # datasets-server /rows 与 /filter 在镜像上不存在（307 到网页路由 / 返回网页）
    repo_quoted = urllib.parse.quote(REPO, safe="")
    rows_body = mirror_get(
        f"{MIRROR}/rows?dataset={repo_quoted}"
        f"&config=raw_review_{REVIEW_SHARD}&split=full&offset=0&length=100",
        prov=prov, note="datasets_server_rows_probe")
    summary["datasets_server_rows"] = (
        "不可用：307 重定向到 /Rows 网页路由，返回网页而非 JSON API"
        if is_html(rows_body) else "意外返回非网页内容，须人工复核")
    filter_body = mirror_get(
        f"{MIRROR}/filter?dataset={repo_quoted}"
        f"&config=raw_review_{REVIEW_SHARD}&split=full&where=%22rating%22%3D5",
        prov=prov, note="datasets_server_filter_probe")
    summary["datasets_server_filter"] = (
        "不可用：返回网页 HTML（huggingface.co 的用户页路由），非 JSON API"
        if is_html(filter_body) else "意外返回非网页内容，须人工复核")

    review_url = f"{RAW_BASE}/raw/review_categories/{REVIEW_SHARD}.jsonl"
    size, etag = head_probe(review_url, prov=prov)
    summary["resolve_head"] = (
        f"可达：X-Linked-Size={size}，302 -> cas-bridge.xethub.hf.co（官方 CDN "
        f"本机可达），X-Linked-Etag={etag[:16]}…，支持 Range 分段（另经 curl "
        "实测 206）" if size else "HEAD 探测失败，须重跑复核")
    if not size:
        conclusive = False

    summary["probes_conclusive"] = conclusive
    summary["official_site"] = ("huggingface.co TCP 443 超时（2026-11-21 复测仍不可达，"
                                "由 curl --connect-timeout 8 实测）")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return summary


def download_shard(url: str, dest: Path, *, prov: Provenance,
                   expected_size: int, note: str) -> bool:
    """下载单个分片到 raw/。已存在且大小一致即跳过（中断恢复核心）。
    整读后一次落盘，避免写出半截文件。"""
    if dest.exists() and expected_size > 0 and dest.stat().st_size == expected_size:
        print(f"  [skip] {dest.name} 已存在（{dest.stat().st_size} 字节），跳过")
        return True
    body = mirror_get(url, prov=prov, note=note, timeout=600)
    if body is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    print(f"  [ok] {dest.name} {len(body)} 字节"
          + ("" if expected_size == 0 else
             f"（镜像清单 {expected_size} 字节"
             f"{'，一致' if len(body) == expected_size else '，不一致，须复核'}）"))
    return True


def download_all(prov: Provenance, sizes: dict[str, int]) -> dict[str, str]:
    """下载品类清单、官方 README、最小评论分片与对应 meta 分片。"""
    status: dict[str, str] = {}
    targets: list[tuple[str, str, str, Path]] = [
        ("all_categories.txt", "all_categories.txt",
         f"{RAW_BASE}/all_categories.txt", RAW_DIR / "all_categories.txt"),
        ("README.md", "README.md",
         f"{RAW_BASE}/README.md", RAW_DIR / "dataset_readme.md"),
        ("Subscription_Boxes.jsonl", f"review_categories/{REVIEW_SHARD}.jsonl",
         f"{RAW_BASE}/raw/review_categories/{REVIEW_SHARD}.jsonl",
         RAW_DIR / "review_categories" / f"{REVIEW_SHARD}.jsonl"),
        ("meta_Subscription_Boxes.jsonl", f"meta_categories/meta_{META_SHARD}.jsonl",
         f"{RAW_BASE}/raw/meta_categories/meta_{META_SHARD}.jsonl",
         RAW_DIR / "meta_categories" / f"meta_{META_SHARD}.jsonl"),
    ]
    for size_key, name, url, dest in targets:
        ok = download_shard(url, dest, prov=prov, expected_size=sizes.get(size_key, 0),
                            note=f"download {name}")
        status[name] = "ok" if ok else "failed"
    return status


def load_meta_lookup() -> tuple[dict[str, tuple[str, str]], dict[str, int]]:
    """parent_asin -> (item_title, price)。元数据是卖家自撰文案，只用于
    标注商品名与价格，不得写入消费者证据侧。

    D-05 价格字段核查（2026-11-24 实测）：meta 分片 641 条记录的 `price`
    字段**全部为 JSON null**，并非联结逻辑写丢。因此 `price_usd` 全空是
    上游分片的事实，不是本地缺陷；此处统计并回报可用价格数，由 manifest
    与 README 如实声明，避免再被当作"待修复的联结 bug"。
    """
    meta_path = RAW_DIR / "meta_categories" / f"meta_{META_SHARD}.jsonl"
    lookup: dict[str, tuple[str, str]] = {}
    stats = {"meta_records": 0, "price_present": 0, "title_present": 0}
    if not meta_path.exists():
        return lookup, stats
    with meta_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                dp = json.loads(line)
            except json.JSONDecodeError:
                continue
            stats["meta_records"] += 1
            parent = str(dp.get("parent_asin") or "")
            raw_price = dp.get("price")
            # 源端用 JSON null / "None" 表示缺价；统一归一为空串
            price = "" if raw_price in (None, "", "None") else str(raw_price)
            title = str(dp.get("title") or "")
            if price:
                stats["price_present"] += 1
            if title:
                stats["title_present"] += 1
            if parent:
                lookup[parent] = (title, price)
    return lookup, stats


def build_main_table() -> tuple[dict[str, object], dict[str, int], float]:
    """从本地 raw 重建主表：窗口过滤 + 稳定 ID 去重 + PII 清洗 + meta 联结。

    返回 (质量报告, 年份分布, 时间覆盖密度)。
    user_id 不写入主表（数据最小化，GDPR；原始分片留在 gitignore 的 raw/）。

    D-05 处置：
    - 新增 `review_id`（稳定哈希 ID）与 `is_empty_text` 标记列；
    - 按 `review_id` 去重，而非弱组合键 `(asin, timestamp_ms)`；
    - 空正文**不静默删除**，保留并以 `is_empty_text=True` 显式标记，
      由下游按用途过滤；
    - 输出去重前后行数报告，写入 manifest `quality_report`。
    """
    review_path = RAW_DIR / "review_categories" / f"{REVIEW_SHARD}.jsonl"
    lookup, meta_stats = load_meta_lookup()
    start_ms, end_ms = window_ms()

    by_id: dict[str, list[object]] = {}
    total = 0
    in_window = 0
    dup_dropped = 0
    dup_identical = 0
    empty_text = 0
    years: dict[str, int] = {}
    dates: set[str] = set()
    seen_payload: dict[str, str] = {}

    with review_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                dp = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = int(dp.get("timestamp") or 0)
            if not start_ms <= ts <= end_ms:
                continue
            in_window += 1

            rid = review_id(dp)
            payload = json.dumps(dp, sort_keys=True, ensure_ascii=False)
            if rid in by_id:
                # 源端重复投递：保留首条，统计丢弃数并区分是否逐字段相同
                dup_dropped += 1
                if seen_payload.get(rid) == payload:
                    dup_identical += 1
                continue
            seen_payload[rid] = payload

            dt = datetime.fromtimestamp(ts / 1000, tz=UTC)
            date_iso = dt.strftime("%Y-%m-%d")
            dates.add(date_iso)
            years[date_iso[:4]] = years.get(date_iso[:4], 0) + 1
            parent = str(dp.get("parent_asin") or "")
            item_title, price = lookup.get(parent, ("", ""))
            text = scrub(str(dp.get("text") or ""))[:TEXT_MAX]
            is_empty = not text.strip()
            if is_empty:
                empty_text += 1
            by_id[rid] = [
                rid, f"raw_review_{REVIEW_SHARD}", REVIEW_SHARD,
                str(dp.get("asin") or ""), parent,
                item_title[:TITLE_MAX], price,
                dp.get("rating"), scrub(str(dp.get("title") or ""))[:TITLE_MAX],
                text, ts, date_iso,
                bool(dp.get("verified_purchase")), int(dp.get("helpful_vote") or 0),
                is_empty,
            ]

    rows = sorted(by_id.values(), key=lambda r: (str(r[11]), str(r[0])))

    write_csv(OUT / MAIN_TABLE, [
        "review_id", "shard", "category", "asin", "parent_asin",
        "item_title", "price_usd", "rating", "title", "text",
        "timestamp_ms", "review_date", "verified_purchase", "helpful_vote",
        "is_empty_text",
    ], rows)

    density = 0.0
    if dates:
        span = (datetime.strptime(max(dates), "%Y-%m-%d")
                - datetime.strptime(min(dates), "%Y-%m-%d")).days + 1
        density = len(dates) / span

    report: dict[str, object] = {
        "shard_rows_total": total,
        "rows_in_window_before_dedup": in_window,
        "rows_after_dedup": len(rows),
        "duplicates_dropped": dup_dropped,
        "duplicates_byte_identical": dup_identical,
        "duplicates_differing_fields": dup_dropped - dup_identical,
        "dedup_key": "review_id = sha1(user_id|asin|timestamp)[:16]",
        "dedup_key_note": ("源数据无原生 review_id；旧口径用弱组合键 "
                           "(asin, timestamp_ms)，窗口内有 61 个重复键。"
                           "改用含 user_id 的稳定哈希后重复键为 0"),
        "empty_text_rows": empty_text,
        "empty_text_policy": "保留并以 is_empty_text=True 标记，不静默删除",
        "review_id_unique": len(rows) == len(by_id),
        "price_usd_present": sum(1 for r in rows if str(r[6]).strip()),
        "price_usd_note": ("meta 分片 price 字段上游全为 null（641/641），"
                           "非联结缺陷；主表 price_usd 因此全空，不可用于价格分析"),
        "meta_join": meta_stats,
    }
    return report, years, density


def write_provenance_merged(prov: Provenance) -> Path:
    """provenance 按 URL 去重合并（保留最新一次调用），重跑不丢历史留痕。"""
    path = OUT / "provenance.csv"
    header = ["source", "url", "http_status", "bytes", "elapsed_s",
              "sha256", "fetched_at_utc", "note"]
    merged: dict[str, list[str]] = {}
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if len(row) >= 8 and row[0] != "source":
                    merged[row[1]] = row
    for c in prov.calls:
        merged[c.url] = [c.source, c.url, str(c.http_status), str(c.bytes_len),
                         f"{c.elapsed_s:.2f}", c.sha256, c.fetched_at, c.note]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(merged.values())
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    prov = Provenance("amazon_reviews_2023", OUT)

    probes = run_probes(prov)
    print("[probe] 结论：")
    for key in sorted(k for k in probes if k != "probes_conclusive"):
        print(f"  {key}: {probes[key]}")

    sizes = load_sizes()
    downloads = download_all(prov, sizes)
    failed = [k for k, v in downloads.items() if v != "ok"]
    if failed:
        print(f"[fetch] 下载失败：{failed}（可重跑本脚本续传）")
        write_provenance_merged(prov)
        return 1

    quality, years, density = build_main_table()
    total = int(quality["shard_rows_total"])
    kept = int(quality["rows_after_dedup"])
    write_provenance_merged(prov)
    sparse = density < MIN_DENSITY
    write_manifest(OUT, {
        "source": "amazon_reviews_2023", "tier": "L1", "license": "Apache-2.0",
        "requires_credential": False,
        "pipeline": "hf-mirror.com /resolve/ 分片直下 + 本地窗口过滤与 PII 清洗",
        "pilot_shard": f"raw_review_{REVIEW_SHARD}（全库最小评论分片，完整下载）",
        "meta_shard": f"raw_meta_{META_SHARD}",
        "shard_rows_total": total,
        "rows_in_window": kept,
        "years_covered": sorted(years),
        "year_counts": years,
        "time_coverage_density": round(density, 4),
        "time_coverage_sparse": sparse,
        "time_coverage_note": (
            "源数据止于 2023-09，窗口内 2023-10 之后源端无数据；"
            "试点仅取全库最小分片，不可当作全库覆盖声明。"
            if sparse else
            "试点分片窗口内按日分布密度达标；但样本仅为全库最小分片，"
            "且源数据止于 2023-09，不可当作全库覆盖声明。"),
        "coverage_complete": False,
        "coverage_note": (
            "覆盖不完整：这是管线试点样本（1 个最小评论分片 + 1 个最小 meta "
            "分片），不是全量迁移；源数据止于 2023-09，窗口 2023-10~2026-12 "
            "源端无数据；品类相关分片（Clothing_Shoes_and_Jewelry 26.5GB、"
            "Sports_and_Outdoors 8.8GB）超出试点 200MB 预算，未下载"),
        "german_market_adaptability": {
            "conclusion": "不可适配：无法筛出德国/德语评论子集",
            "evidence": [
                "评论与元数据均无 marketplace、language 列",
                "官方 tags 标 language:en；数据为 Amazon.com 美国全站",
                "34 个品类全部为 Amazon.com 类目，无独立 Luggage/Travel_Accessories 品类",
                "对德国市场不构成 L1；德国侧 L1 仍需品牌授权导出",
            ],
        },
        "tier_caveat": ("tier=L1 仅就「一手消费者反馈数据集」类别成立；本库为 "
                        "Amazon.com 美国市场数据，对目标市场（德国）不构成 L1 证据"),
        "mirror_endpoints": probes,
        "page_limit_rows": 100,
        "page_limit_note": ("镜像不代理 datasets-server，/rows /filter 不可用；"
                            "100 行分页纪律（CONSTRAINTS 一之二）暂无生效场景，"
                            "留作官方站可达后的约束"),
        "pii_scrubbed": ["email", "phone"],
        "text_truncation": {"title": TITLE_MAX, "text": TEXT_MAX},
        "quality_report": quality,
        "downloads": downloads,
    })
    print(f"[amazon] 分片 {total} 条，窗口内写出 {kept} 条；年份 {years}；"
          f"密度 {density:.1%}（{'SPARSE' if sparse else 'OK'}）")
    print(f"[amazon] 去重丢弃 {quality['duplicates_dropped']} 条"
          f"（逐字段相同 {quality['duplicates_byte_identical']}）；"
          f"空正文标记 {quality['empty_text_rows']} 条；"
          f"可用价格 {quality['price_usd_present']} 条")
    print(f"[amazon] 主表 {OUT / MAIN_TABLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
