"""本地/CI 共用的 harness 单元测试发现与运行脚本（#403）。

发现 `*/agent-harness/cli_anything/*/tests/test_core.py`（后端无关的单测），
逐个用 pytest 运行并输出汇总；供 GitHub Actions 矩阵生成与本地核对使用。
"""

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path


def discover(repo_root: Path) -> list[Path]:
    return sorted(
        Path(p)
        for p in glob.glob(
            str(repo_root / "*/agent-harness/cli_anything/*/tests/test_core.py")
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--list", action="store_true", help="仅输出发现清单（JSON）")
    parser.add_argument("--test", type=str, default="", help="只跑指定测试文件")
    parser.add_argument("--out", type=str, default="", help="单测结果 JSON 输出路径")
    args = parser.parse_args()

    root = Path(args.repo_root)
    tests = discover(root)
    if args.test:
        t = Path(args.test)
        tests = [t if t.is_absolute() else (root / t)]
    if args.list:
        print(json.dumps([str(t.relative_to(root)) for t in tests], ensure_ascii=False))
        return 0

    results = []
    failed = 0
    for t in tests:
        harness_dir = t.parents[3]  # .../agent-harness/cli_anything/<h>/tests/test_core.py
        rel = t.relative_to(harness_dir)
        rel_root = t.relative_to(root)
        harness_name = rel_root.parts[0]
        try:
            out = subprocess.run(
                [sys.executable, "-m", "pytest", str(rel), "-q", "--no-header"],
                cwd=harness_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )
            lines = (out.stdout or out.stderr).strip().splitlines()
            tail = next(
                (ln.strip() for ln in reversed(lines) if "passed" in ln or "failed" in ln),
                (lines[-1].strip() if lines else ""),
            )
            ok = out.returncode == 0
            if not ok:
                failed += 1
            results.append(
                {
                    "harness": harness_name,
                    "test": str(rel),
                    "ok": ok,
                    "rc": out.returncode,
                    "summary": tail,
                }
            )
            print(f"{'PASS' if ok else 'FAIL'}  {rel}")
            if args.out:
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump(results[0], f, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            failed += 1
            results.append({"harness": t.parts[0], "test": str(rel), "ok": False,
                            "rc": "timeout", "summary": "timeout"})
            print(f"TIMEOUT  {rel}")

    print("\n== SUMMARY ==")
    print(f"total={len(results)} failed={failed}")
    for r in results:
        if not r["ok"]:
            print(f"  FAIL {r['test']} rc={r['rc']} {r['summary']}")
    with open(root / ".harness-unit-report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
