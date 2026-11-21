"""抓取脚本共用工具：时间窗、限速、留痕。

设计约束（对应 docs/CONSTRAINTS.md）：
- 所有抓取只覆盖 2021-01-01 ~ 2026-12-31，窗口在此处单点定义。
- 每个来源必须产出 provenance.csv：一行一次 HTTP 调用，可追溯。
- 截断风险源（分页上限）必须显式记录 page_limit 与实际取回行数。
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---- 全局时间窗：唯一定义处 ----
WINDOW_START = "2021-01-01"
WINDOW_END = "2026-12-31"
WINDOW_YEARS = tuple(str(y) for y in range(2021, 2027))

UA = "CrossPilot/0.1 (Zhihu Hackathon S3; research; contact via repo)"


@dataclass
class Call:
    """一次 HTTP 调用的留痕记录。"""

    source: str
    url: str
    http_status: int | str
    bytes_len: int
    elapsed_s: float
    sha256: str
    fetched_at: str
    note: str = ""


@dataclass
class Provenance:
    """来源级留痕收集器。"""

    source: str
    out_dir: Path
    calls: list[Call] = field(default_factory=list)

    def record(self, call: Call) -> None:
        self.calls.append(call)

    def write(self) -> Path:
        path = self.out_dir / "provenance.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["source", "url", "http_status", "bytes", "elapsed_s",
                 "sha256", "fetched_at_utc", "note"]
            )
            for c in self.calls:
                w.writerow([c.source, c.url, c.http_status, c.bytes_len,
                            f"{c.elapsed_s:.2f}", c.sha256, c.fetched_at, c.note])
        return path


def now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(
    url: str,
    *,
    source: str,
    prov: Provenance,
    timeout: int = 90,
    retries: int = 3,
    backoff_s: float = 8.0,
    note: str = "",
) -> bytes | None:
    """带退避重试的 GET。429/超时按 backoff_s 退避（GDELT 实测需 >=7s）。"""
    last_err: str = ""
    for attempt in range(1, retries + 1):
        started = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # 显式注解：urlopen 无精确 stub，resp.read() 推断为 Any，
                # 会让 --strict 的 warn_return_any 在引用方误报
                body: bytes = resp.read()
                status = resp.status
            prov.record(Call(source, url, status, len(body), time.time() - started,
                             hashlib.sha256(body).hexdigest(), now_utc(),
                             f"{note} attempt={attempt}".strip()))
            return body
        except urllib.error.HTTPError as exc:
            last_err = f"HTTP {exc.code}"
            prov.record(Call(source, url, exc.code, 0, time.time() - started,
                             "", now_utc(), f"{note} attempt={attempt} {last_err}".strip()))
        except Exception as exc:  # noqa: BLE001 - 网络层异常种类多，统一留痕
            last_err = type(exc).__name__
            prov.record(Call(source, url, "ERR", 0, time.time() - started,
                             "", now_utc(), f"{note} attempt={attempt} {last_err}".strip()))
        if attempt < retries:
            time.sleep(backoff_s * attempt)
    print(f"  [!] 放弃 {url[:90]} ({last_err})")
    return None


def save_raw(out_dir: Path, filename: str, body: bytes) -> Path:
    path = out_dir / "raw" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> Path:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def write_manifest(out_dir: Path, payload: dict[str, object]) -> Path:
    path = out_dir / "manifest.json"
    payload = {"window_start": WINDOW_START, "window_end": WINDOW_END, **payload}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
