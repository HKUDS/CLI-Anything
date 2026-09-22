"""把各 harness 单测结果 JSON 汇总为 Markdown 表（供 GITHUB_STEP_SUMMARY 输出）。"""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="单测结果 JSON 文件")
    args = parser.parse_args()

    rows = []
    for f in args.files:
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(data)
    rows.sort(key=lambda r: (r.get("test", ""), r.get("rc", "")))

    lines = [
        "## Harness 单元测试汇总",
        "",
        "| Harness | 测试文件 | 结果 | rc | 摘要 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        status = "✅" if r.get("ok") else "❌"
        lines.append(
            f"| {r.get('harness', '-')} | {r.get('test', '-')} | {status} | "
            f"{r.get('rc', '-')} | {str(r.get('summary', ''))[:60]} |"
        )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
