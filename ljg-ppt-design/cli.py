"""ljg-ppt-design 命令行入口。

用法:
  # 查预设
  python3 -m ljg_ppt_design.cli list-presets
  python3 -m ljg_ppt_design.cli list-talk-types
  python3 -m ljg_ppt_design.cli list-layouts

  # 渲染 (从 JSON content 读,出 .pptx 或 .json)
  python3 -m ljg_ppt_design.cli render \\
      --preset academic --talk-type school \\
      --input content.json --output out.pptx

  # 同时跑质量审查
  python3 -m ljg_ppt_design.cli render \\
      --preset academic --talk-type school \\
      --input content.json --output out.pptx --review
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_list_presets(_args) -> int:
    from . import list_presets
    print(json.dumps(list_presets(), ensure_ascii=False, indent=2))
    return 0


def cmd_list_talk_types(_args) -> int:
    from . import list_talk_types
    print(json.dumps(list_talk_types(), ensure_ascii=False, indent=2))
    return 0


def cmd_list_layouts(_args) -> int:
    from . import list_layouts
    print(json.dumps(list_layouts(), ensure_ascii=False, indent=2))
    return 0


def cmd_render(args) -> int:
    from . import render_deck, get_preset
    from .quality_checks import review_deck

    if args.input == "-":
        content = json.load(sys.stdin)
    else:
        content = json.loads(Path(args.input).read_text(encoding="utf-8"))

    deck = render_deck(
        preset=args.preset,
        talk_type=args.talk_type,
        content=content,
        name=args.name or Path(args.input).stem,
    )

    print(f"✓ 渲染: {deck.slide_count()} 页 / preset={deck.preset} / talk_type={deck.talk_type}",
          file=sys.stderr)

    out = Path(args.output)
    if out.suffix == ".json":
        out.write_text(deck.to_json(), encoding="utf-8")
        print(f"✓ 写 JSON: {out}", file=sys.stderr)
    elif out.suffix == ".pptx":
        from .data.pptx_renderer import render_to_pptx
        render_to_pptx(deck, str(out))
        print(f"✓ 写 PPTX: {out} ({out.stat().st_size // 1024}KB)", file=sys.stderr)
    else:
        print(f"✗ 未知后缀 {out.suffix} (支持 .json / .pptx)", file=sys.stderr)
        return 1

    if args.review:
        review = review_deck(deck, get_preset(args.preset))
        print(file=sys.stderr)
        print(f"审查: {review['summary']}", file=sys.stderr)
        for dim, info in review["per_dimension"].items():
            mark = "✓" if info["pass"] else "✗"
            print(f"  {mark} {dim:14s}: {info['score']:5.1f} / 阈值 {info['threshold']}", file=sys.stderr)
        if review["warnings"]:
            print(f"\n{len(review['warnings'])} 个警告:", file=sys.stderr)
            for w in review["warnings"]:
                print(f"  ⚠️  {w}", file=sys.stderr)
        return 0 if review["pass"] else 2

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ljg-ppt-design",
        description="PPT 设计系统 CLI — 选 preset + talk_type,从 JSON content 出 .pptx",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("list-presets", help="列出 4 套设计预设")
    p1.set_defaults(func=cmd_list_presets)

    p2 = sub.add_parser("list-talk-types", help="列出 4 种演讲类型")
    p2.set_defaults(func=cmd_list_talk_types)

    p3 = sub.add_parser("list-layouts", help="列出 12 种布局")
    p3.set_defaults(func=cmd_list_layouts)

    p4 = sub.add_parser("render", help="从 JSON content 渲染 .pptx 或 .json")
    p4.add_argument("--preset", "-p", required=True, choices=["academic", "consultant", "business", "tech"])
    p4.add_argument("--talk-type", "-t", required=True, choices=["conference", "business", "defense", "school"])
    p4.add_argument("--input", "-i", required=True, help="content JSON 文件路径,或 - 读 stdin")
    p4.add_argument("--output", "-o", required=True, help="输出文件 (.pptx 或 .json)")
    p4.add_argument("--name", "-n", default=None, help="deck 名称 (默认从 input 文件名取)")
    p4.add_argument("--review", "-r", action="store_true", help="渲染后跑 5 维质量审查")
    p4.set_defaults(func=cmd_render)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
