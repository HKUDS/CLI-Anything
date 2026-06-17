---
name: cli-anything-ljg-ppt-design
version: 0.1.0
description: PPT 设计系统 —— 4 套预设 × 12 布局 × 4 演讲类型 × 5 维审查。出 .pptx / .odp / .pdf。python-pptx 默认后端,LibreOffice 可选。比 cli-anything-libreoffice 轻,有完整设计系统。
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.9"
  cliHelp: "cli-anything-ljg-ppt-design --help"
---

# cli-anything-ljg-ppt-design

PPT 设计系统。lifestyle CLI for AI agents to create polished .pptx files with design system intelligence.

## When to use

- 用户说 "做一份 PPT" / "做一份幻灯片" / "准备演讲"
- 需要选风格 (学术/咨询/商务/科技)
- 需要按演讲类型 (会议/汇报/答辩/学校) 决定页面结构
- 需要 5 维质量自检 (visual / pedagogy / proofreading / parity / substance)
- 出 .pptx (默认) 或 .odp (需 LO) 或 .pdf (需 LO)

## When NOT to use

- 用户要"全功能 LibreOffice 控制" → 用 `cli-anything-libreoffice`
- 用户要"飞书在线 PPT" → 切 Lark skill,本 skill 出的 JSON 兼容
- 简单 Markdown 大纲 → 用本 skill 的 talk_type.slides 列表就行

## 4 presets

`academic` (学术答辩) · `consultant` (咨询顾问) · `business` (商务汇报) · `tech` (科技极简,暗色)

## 4 talk types

`conference` (14页学术会议) · `business` (9页商务) · `defense` (13页答辩) · `school` (9页学校)

## Quick start

```bash
# 装
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=ljg-ppt-design

# 查决策信息
cli-anything-ljg-ppt-design list-presets
cli-anything-ljg-ppt-design list-talk-types

# 渲染
cli-anything-ljg-ppt-design render \
    --preset academic --talk-type school \
    --input content.json --output out.pptx --review
```

## Compatibility

- `python-pptx` (默认,无需 LO) → 出 .pptx 直接
- `libreoffice` (可选) → 出 .odp / .pdf / 任何 LO 支持的格式
- Lark skill (飞书) → DeckSpec JSON 直接消费

## Why this vs cli-anything-libreoffice

| 维度 | ljg-ppt-design | cli-anything-libreoffice |
|---|---|---|
| 设计系统 (4 preset × 12 layout × 4 talk) | ✅ | ❌ |
| 5 维质量审查 | ✅ | ❌ |
| 默认后端 | python-pptx (无依赖) | LO (1GB) |
| 跨平台 | 任何 Python 3.9+ | 仅装 LO 机器 |
| Talk type 叙事结构 | ✅ | ❌ |

## Source

设计系统 (4 preset / 12 layout / 4 talk type / 5 维审查) 来自 `yb2460/harness-anything` (fork of HKUDS) 的 `cli_anything/wps/styles/` 三个模块。质量阈值是 slide-excellence 行业标准。

lal
