---
name: ljg-ppt-design
version: 0.1.0
description: "PPT 设计系统 —— 4 套预设 (学术/咨询/商务/科技) × 12 种布局 × 4 种演讲类型 (会议/汇报/答辩/学校) × 5 维度质量审查。纯 Python,无 WPS 依赖,产出 DeckSpec JSON 供 lark-slides / pptx / reveal.js 消费。当用户要做 PPT、问怎么选风格、需要演讲结构建议时使用。**注意**:本 skill 是**设计系统 + 可选渲染器**,出 PPTX 文件调 `data.pptx_renderer.render_to_pptx`,出飞书在线 PPT 调 `lark-slides` skill。"
metadata:
  requires:
    bins: ["python3"]
    python: ">=3.10"
  cliHelp: "python3 -c 'from ljg_ppt_design import render_deck, list_presets, list_talk_types, review_deck; print(list_presets()); print(list_talk_types())'"
---

# ljg-ppt-design

**身份:设计系统 + 可选 .pptx 渲染器。** 负责四件事:
1. **结构** — 选预设 + 选演讲类型 → 决定页面序列
2. **规范** — 出 `DeckSpec` JSON (平台中立)
3. **审查** — 5 维度质量自检
4. **可选渲染** — `data/pptx_renderer.py` 把 DeckSpec 直接出 .pptx (跨平台)

---

## 触发条件 (何时调我)

| 用户说 | 你要做的 |
|---|---|
| "做一份 PPT" / "帮我准备演讲" | 调 `render_deck` |
| "用什么风格好" / "选哪个 preset" | 调 `list_presets` |
| "会议要几页" / "答辩怎么排" | 调 `list_talk_types` + `get_talk_preset` |
| "这版 PPT 行不行" | 调 `review_deck` 做 5 维审查 |
| "想要科技风" / "要深色背景" | 按 `list_presets` 的字段筛 |
| "出 .pptx 文件" / "存到本地" | 调 `data.pptx_renderer.render_to_pptx` |

**不要**:
- ❌ 用户说"分享到飞书" → 切到 `lark-slides` skill (本 skill 出的 JSON 能直接消费)
- ❌ 用户说"只要 Markdown 大纲" → 用本 skill 的 talk_type.slides 列表就够了

---

## 4 套设计预设速查

| key | 名称 | 留白 | 最多要点 | 暗色? | 来源 | 适用 |
|---|---|---|---|---|---|---|
| `academic` | 学术答辩 | 40% | 6 | ❌ | scientific-slides | 论文答辩 / 基金 / Journal Club |
| `consultant` | 咨询顾问 | 40% | 5 | ❌ | pptx-from-layouts | 商业计划书 / 咨询报告 |
| `business` | 商务汇报 | 35% | 6 | ❌ | pptx | 会议汇报 / 教学课件 |
| `tech` | 科技极简 | 50% | 4 | ✅ | 现代科技设计 | 产品发布 / AI 演示 / 数据报告 |

**选择规则**:
- 用户没说 → 默认 `academic`
- 要暗色 → `tech`
- 商务提案 → `business` 或 `consultant`
- 中国高校招生 → `academic` + `school` talk_type

---

## 4 种演讲类型速查

| key | 名称 | 默认页数 | 上限 | 核心叙事 |
|---|---|---|---|---|
| `conference` | 学术会议 | 14 | 20 | Hook→Context→Problem→Approach→Results→Implications→Closure |
| `business` | 商务汇报 | 9 | 15 | 总览→指标→对比→计划→团队→Q&A |
| `defense` | 论文答辩 | 13 | 65 | 背景→方法→结果→对比→未来→致谢 |
| `school` | 学校介绍 | 9 | 14 | 概览→校史→学科→校友→校园→数据→校训 |

---

## 12 种布局速查

| key | 类别 | 用途 |
|---|---|---|
| `cover` | cover | 封面 (必出) |
| `toc` | content | 目录 |
| `overview` | content | 概览/背景 |
| `timeline` | column | 时间轴 (校史/发展) |
| `grid_cards` | grid | 卡片网格 (人物/产品) |
| `quadrant` | grid | 四象限 (分类/对比) |
| `stats` | content | 数字统计 |
| `three_col` | column | 三列对比 |
| `pipeline` | content | 流程图 |
| `data_table` | content | 数据表格 |
| `content_image` | image | 图文并茂 |
| `closing` | close | 结语 (必出) |

---

## 5 维度质量审查

| 维度 | 阈值 | 查什么 |
|---|---|---|
| `visual` | 70 | 字体层级/颜色对比/留白/布局 |
| `pedagogy` | 75 | 叙事弧 (首尾 cover/closing) / 中段内容支撑 |
| `proofreading` | 80 | 字号/对比度/标点 |
| `parity` | 85 | 页数/格式兼容 |
| `substance` | 90 | 文字量/数据/引用 |

---

## 快速使用

### 1. 查决策信息

```python
from ljg_ppt_design import list_presets, list_talk_types, list_layouts
print(list_presets())
print(list_talk_types())
print(list_layouts())
```

### 2. 渲染一份 deck

```python
from ljg_ppt_design import render_deck

deck = render_deck(
    preset="academic", talk_type="school",
    name="南科大 2026 招生宣讲",
    content={...},
)
```

### 3. 质量审查

```python
from ljg_ppt_design import review_deck, get_preset
review = review_deck(deck, get_preset("academic"))
print(review["summary"])
```

### 4. 出 .pptx 文件

```python
from ljg_ppt_design.data.pptx_renderer import render_to_pptx
render_to_pptx(deck, "/tmp/output.pptx")
```

---

## 数据契约

`DeckSpec.to_dict()` 输出 JSON: 颜色用语义名 (primary/secondary/...),坐标用 960x540 16:9。消费者按 `get_preset(key).hex_colors()` 解析颜色。

---

## 引用

- `references/presets.md` — 4 套预设完整字段对照
- `references/layouts.md` — 12 布局的元素详表 + 坐标
- `references/talk-types.md` — 4 演讲类型的 content 字段要求
- `references/quality-rubric.md` — 5 维度审查的算法说明

---

## 来源 / 致谢

本 skill 设计系统移植自 `yb2460/harness-anything` 的 `cli_anything/wps/styles/` 三个模块,去掉 WPS 依赖,改为平台中立 (lark-slides / pptx / reveal.js 都能消费)。

---

_ljg-ppt-design · OpenClaw skill_
_2026-06-17 · 慧慧 从 harness-anything 移植_
