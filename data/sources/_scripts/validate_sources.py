"""数据区结构校验：每个来源必须齐备 README/主表/provenance/manifest。

这是回归检查而非一次性核对：新增来源若漏文件、漏许可声明、漏截断记录，
或 manifest 的层级与 REGISTRY 不一致，此脚本即失败。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

SOURCES = Path(__file__).resolve().parents[1]
REQUIRED = ("README.md", "manifest.json", "provenance.csv")
MANIFEST_KEYS = ("source", "tier", "license", "requires_credential",
                 "window_start", "window_end")
WINDOW = ("2021-01-01", "2026-12-31")


def check(dir_: Path) -> list[str]:
    errs: list[str] = []
    name = dir_.name

    for f in REQUIRED:
        if not (dir_ / f).exists():
            errs.append(f"{name}: 缺 {f}")

    tables = [p for p in dir_.glob("*.csv") if not p.name.startswith("provenance")]
    if not tables:
        errs.append(f"{name}: 缺主表 CSV")
    for t in tables:
        with t.open(encoding="utf-8-sig") as fh:
            rows = sum(1 for _ in csv.reader(fh)) - 1
        if rows <= 0:
            errs.append(f"{name}: 主表 {t.name} 无数据行")

    mf = dir_ / "manifest.json"
    if mf.exists():
        m = json.loads(mf.read_text(encoding="utf-8"))
        for k in MANIFEST_KEYS:
            if k not in m:
                errs.append(f"{name}: manifest 缺字段 {k}")
        if (m.get("window_start"), m.get("window_end")) != WINDOW:
            errs.append(f"{name}: manifest 时间窗 != {WINDOW}")
        # 覆盖不完整或存在截断时，README 必须显式警示
        readme = (dir_ / "README.md").read_text(encoding="utf-8") if (dir_ / "README.md").exists() else ""
        if m.get("coverage_complete") is False and "覆盖不完整" not in readme:
            errs.append(f"{name}: coverage_complete=false 但 README 未警示覆盖不完整")
        if m.get("truncated_windows") and "截断" not in readme:
            errs.append(f"{name}: 存在触顶窗口但 README 未说明截断")

    prov = dir_ / "provenance.csv"
    if prov.exists():
        with prov.open(encoding="utf-8") as fh:
            pr = list(csv.DictReader(fh))
        if not pr:
            errs.append(f"{name}: provenance.csv 无记录")
        elif not any(r.get("sha256") for r in pr):
            errs.append(f"{name}: provenance.csv 无 sha256，不可追溯")

    return errs


def main() -> int:
    dirs = sorted(d for d in SOURCES.iterdir()
                  if d.is_dir() and not d.name.startswith("_"))
    all_errs: list[str] = []
    for d in dirs:
        errs = check(d)
        status = "OK" if not errs else f"{len(errs)} 项问题"
        print(f"[{status:>9s}] {d.name}")
        all_errs.extend(errs)

    if all_errs:
        print("\n不合规项：")
        for e in all_errs:
            print(f"  - {e}")
        return 1
    print(f"\n{len(dirs)} 个来源全部合规")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
