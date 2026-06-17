"""12 种布局模板 + 4 种演讲类型预设。

布局 = 单页元素模板 (含坐标、字体、颜色占位)。
演讲类型 = 推荐页面序列 + 全局规则。

来源: harness-anything (yb2460) — 去 WPS 依赖,纯 Python。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LayoutTemplate:
    name: str
    key: str
    category: str
    description: str
    elements: tuple
    structural_rules: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "name": self.name, "category": self.category,
            "description": self.description,
            "elements": [list(e) if isinstance(e, tuple) else e for e in self.elements],
            "structural_rules": self.structural_rules,
        }


LAYOUTS: dict[str, LayoutTemplate] = {}

# 1. 封面
LAYOUTS["cover"] = LayoutTemplate(
    key="cover", name="封面", category="cover",
    description="深色全屏 + 72pt 大字标题 + 装饰线 + 副标题/日期。开场用。",
    elements=(
        {"type": "bg", "color": "primary"},
        {"type": "line", "x": 0, "y": 0, "w": 960, "h": 18, "color": "secondary"},
        {"type": "text", "x": 0, "y": 100, "w": 960, "h": 150, "text": "{title}",
         "role": "title", "fs": 72, "color": "white", "bold": True, "align": 2},
        {"type": "line", "x": 280, "y": 270, "w": 400, "h": 5, "color": "white"},
        {"type": "text", "x": 0, "y": 365, "w": 960, "h": 60, "text": "{subtitle}",
         "role": "subtitle", "fs": 32, "color": "light", "bold": True, "align": 2},
        {"type": "line", "x": 0, "y": 530, "w": 960, "h": 8, "color": "secondary"},
    ),
)

# 2. 目录
LAYOUTS["toc"] = LayoutTemplate(
    key="toc", name="目录", category="content",
    description="左侧蓝色装饰条 + 编号圆角方块 + 6 项导航。",
    elements=(
        {"type": "line", "x": 0, "y": 0, "w": 22, "h": 540, "color": "primary"},
        {"type": "text", "x": 60, "y": 25, "w": 400, "h": 65, "text": "目  录",
         "role": "title", "fs": 50, "color": "primary", "bold": True},
        {"type": "line", "x": 60, "y": 100, "w": 120, "h": 5, "color": "secondary"},
        {"type": "grid_items", "x": 60, "y": 140, "cols": 1, "rows": 6, "gap": 63,
         "item_w": 840, "item_h": 56,
         "fields": ["{num}", "{title}", "{desc}"],
         "styles": [
             {"fs": 24, "color": "white", "bold": True, "bg": "primary", "w": 56},
             {"fs": 28, "color": "dark", "bold": True},
             {"fs": 14, "color": "gray"},
         ]},
    ),
    structural_rules={"max_items": 6},
)

# 3. 概览
LAYOUTS["overview"] = LayoutTemplate(
    key="overview", name="概览", category="content",
    description="顶部深色横幅 + 信息卡片矩阵 + 侧边荣誉栏。",
    elements=(
        {"type": "line", "x": 0, "y": 0, "w": 960, "h": 100, "color": "primary"},
        {"type": "text", "x": 0, "y": 15, "w": 960, "h": 50, "text": "{title}",
         "role": "title", "fs": 42, "color": "white", "bold": True, "align": 2},
        {"type": "grid_cards", "x": 35, "y": 120, "cols": 2, "rows": 4,
         "gap_x": 20, "gap_y": 88, "item_w": 430, "item_h": 80,
         "fields": ["{label}", "{value}"],
         "styles": [
             {"fs": 16, "color": "white", "bold": True, "bg": "primary", "h": 38},
             {"fs": 19, "color": "dark", "bold": True},
         ]},
        {"type": "sidebar", "x": 720, "y": 120, "w": 200, "h": 360,
         "color": "light", "text": "{sidebar}"},
    ),
    structural_rules={"max_cards": 8},
)

# 4. 时间轴
LAYOUTS["timeline"] = LayoutTemplate(
    key="timeline", name="时间轴", category="column",
    description="左侧圆点+竖线+右侧事件,适合历史/发展内容。",
    elements=(
        {"type": "text", "x": 35, "y": 30, "w": 800, "h": 50, "text": "{title}",
         "role": "title", "fs": 38, "color": "primary", "bold": True},
        {"type": "line", "x": 35, "y": 85, "w": 150, "h": 3, "color": "secondary"},
        {"type": "timeline_items", "x": 40, "start_y": 120, "count": 6, "gap": 55,
         "fields": ["{date}", "{event}"],
         "styles": [
             {"fs": 16, "color": "primary", "bold": True, "w": 110},
             {"fs": 16, "color": "dark", "w": 550},
         ]},
        {"type": "sidebar", "x": 650, "y": 120, "w": 280, "h": 360,
         "color": "light", "text": "{sidebar}"},
    ),
    structural_rules={"max_items": 6},
)

# 5. 卡片网格
LAYOUTS["grid_cards"] = LayoutTemplate(
    key="grid_cards", name="卡片网格", category="grid",
    description="2-4 列卡片网格,适合人物/地标/产品/特征等并行信息。",
    elements=(
        {"type": "text", "x": 0, "y": 15, "w": 960, "h": 55, "text": "{title}",
         "role": "title", "fs": 44, "color": "primary", "bold": True, "align": 2},
        {"type": "line", "x": 350, "y": 72, "w": 260, "h": 3, "color": "secondary"},
        {"type": "grid_cards", "x": 25, "y": 100, "cols": 4, "rows": 2,
         "gap_x": 20, "gap_y": 200, "item_w": 220, "item_h": 190,
         "fields": ["{name}", "{period}", "{desc}"],
         "styles": [
             {"fs": 22, "color": "primary", "bold": True, "align": 2},
             {"fs": 12, "color": "gray", "align": 2},
             {"fs": 12, "color": "dark", "align": 2},
         ],
         "decorations": [{"type": "circle_avatar",
                          "x_offset": 70, "y_offset": 15, "size": 80}]},
    ),
    structural_rules={"max_cards": 8},
)

# 6. 四象限
LAYOUTS["quadrant"] = LayoutTemplate(
    key="quadrant", name="四象限", category="grid",
    description="2x2 四象限对比布局,适合分类展示。",
    elements=(
        {"type": "text", "x": 0, "y": 10, "w": 960, "h": 55, "text": "{title}",
         "role": "title", "fs": 44, "color": "primary", "bold": True, "align": 2},
        {"type": "line", "x": 350, "y": 68, "w": 260, "h": 4, "color": "secondary"},
        {"type": "grid_cards", "x": 25, "y": 95, "cols": 2, "rows": 2,
         "gap_x": 20, "gap_y": 210, "item_w": 440, "item_h": 195,
         "fields": ["{subtitle}", "{content}"],
         "styles": [
             {"fs": 24, "color": "white", "bold": True, "bg": "{color}", "h": 52},
             {"fs": 17, "color": "dark", "y_offset": 60},
         ]},
    ),
    structural_rules={"max_cards": 4},
)

# 7. 数字统计
LAYOUTS["stats"] = LayoutTemplate(
    key="stats", name="数字统计", category="content",
    description="6 大数字统计卡片 + 底部荣誉/说明。",
    elements=(
        {"type": "text", "x": 0, "y": 10, "w": 960, "h": 55, "text": "{title}",
         "role": "title", "fs": 44, "color": "primary", "bold": True, "align": 2},
        {"type": "line", "x": 350, "y": 68, "w": 260, "h": 4, "color": "secondary"},
        {"type": "grid_cards", "x": 20, "y": 120, "cols": 6, "rows": 1,
         "gap_x": 15, "gap_y": 0, "item_w": 140, "item_h": 120,
         "fields": ["{num}", "{label}"],
         "styles": [
             {"fs": 34, "color": "white", "bold": True, "align": 2, "bg": "primary"},
             {"fs": 15, "color": "light", "align": 2},
         ]},
        {"type": "box", "x": 30, "y": 270, "w": 900, "h": 240,
         "color": "light", "text": "{summary}"},
    ),
    structural_rules={"max_cards": 6},
)

# 8. 三列对比
LAYOUTS["three_col"] = LayoutTemplate(
    key="three_col", name="三列对比", category="column",
    description="深色全屏背景 + 三列并排,适合三种方案/三个时期/三个角度对比。",
    elements=(
        {"type": "text", "x": 0, "y": 20, "w": 960, "h": 50, "text": "{title}",
         "role": "title", "fs": 40, "color": "white", "bold": True, "align": 2},
        {"type": "bg", "color": "primary"},
        {"type": "grid_cards", "x": 25, "y": 120, "cols": 3, "rows": 1,
         "gap_x": 20, "gap_y": 0, "item_w": 290, "item_h": 360,
         "fields": ["{col_title}", "{col_subtitle}", "{col_content}"],
         "styles": [
             {"fs": 24, "color": "white", "bold": True, "align": 2, "bg": "accent"},
             {"fs": 16, "color": "light", "align": 2},
             {"fs": 15, "color": "white", "align": 2, "y_offset": 60},
         ]},
    ),
    structural_rules={"max_cards": 3},
)

# 9. 流程图
LAYOUTS["pipeline"] = LayoutTemplate(
    key="pipeline", name="流程图", category="content",
    description="水平管道流程,带彩色模块和连接箭头。",
    elements=(
        {"type": "text", "x": 0, "y": 15, "w": 960, "h": 55, "text": "{title}",
         "role": "title", "fs": 42, "color": "primary", "bold": True, "align": 2},
        {"type": "line", "x": 350, "y": 72, "w": 260, "h": 4, "color": "secondary"},
        {"type": "pipeline_items", "x": 35, "y": 100, "count": 6, "gap": 20,
         "item_w": 140, "item_h": 320,
         "fields": ["{step_num}", "{step_name}", "{step_detail}"],
         "styles": [
             {"fs": 16, "color": "white", "bold": True, "bg": "{color}", "h": 55},
             {"fs": 12, "color": "dark", "y_offset": 65, "w": 128, "h": 240},
         ]},
        {"type": "box", "x": 30, "y": 450, "w": 900, "h": 60,
         "color": "light", "text": "{pipeline_summary}"},
    ),
    structural_rules={"max_steps": 6},
)

# 10. 数据表格
LAYOUTS["data_table"] = LayoutTemplate(
    key="data_table", name="数据表格", category="content",
    description="左表格 + 右解读区,适合排名/对比/指标。",
    elements=(
        {"type": "text", "x": 30, "y": 10, "w": 500, "h": 50, "text": "{title}",
         "role": "title", "fs": 40, "color": "primary", "bold": True},
        {"type": "line", "x": 30, "y": 65, "w": 200, "h": 4, "color": "secondary"},
        {"type": "table", "x": 30, "y": 90, "rows": 7, "cols": 2, "row_h": 42,
         "col_w": [180, 280], "header": ["{col1_name}", "{col2_name}"],
         "data": "{table_data}"},
        {"type": "box", "x": 530, "y": 90, "w": 400, "h": 410,
         "color": "light", "text": "{interpretation}"},
    ),
    structural_rules={"max_rows": 7},
)

# 11. 内容+图片
LAYOUTS["content_image"] = LayoutTemplate(
    key="content_image", name="内容+图片", category="image",
    description="左文右图 / 左图右文,图文并茂。",
    elements=(
        {"type": "text", "x": 40, "y": 20, "w": 450, "h": 55, "text": "{title}",
         "role": "title", "fs": 38, "color": "primary", "bold": True},
        {"type": "line", "x": 40, "y": 80, "w": 120, "h": 3, "color": "secondary"},
        {"type": "text", "x": 40, "y": 100, "w": 440, "h": 400, "text": "{content}",
         "role": "body", "fs": 18, "color": "dark"},
        {"type": "image_placeholder", "x": 510, "y": 60, "w": 420, "h": 440,
         "text": "{image_label}"},
    ),
)

# 12. 结语
LAYOUTS["closing"] = LayoutTemplate(
    key="closing", name="结语", category="close",
    description="深色全屏 + 总结 + 联系方式/校训。收尾用。",
    elements=(
        {"type": "bg", "color": "primary"},
        {"type": "line", "x": 0, "y": 0, "w": 960, "h": 15, "color": "secondary"},
        {"type": "text", "x": 0, "y": 80, "w": 960, "h": 100, "text": "{summary_title}",
         "role": "title", "fs": 52, "color": "white", "bold": True, "align": 2},
        {"type": "line", "x": 280, "y": 200, "w": 400, "h": 4, "color": "white"},
        {"type": "text", "x": 60, "y": 230, "w": 840, "h": 200, "text": "{summary_text}",
         "role": "body", "fs": 18, "color": "light", "align": 2},
        {"type": "line", "x": 280, "y": 450, "w": 400, "h": 4, "color": "white"},
        {"type": "text", "x": 0, "y": 470, "w": 960, "h": 50, "text": "{motto}",
         "role": "subtitle", "fs": 30, "color": "light", "bold": True, "align": 2},
        {"type": "line", "x": 0, "y": 530, "w": 960, "h": 8, "color": "secondary"},
    ),
)


TALK_PRESETS: dict[str, dict] = {
    "conference": {
        "name": "学术会议", "description": "12-20 页,学术演讲。",
        "slides": ["cover", "toc", "overview", "timeline", "quadrant",
                   "grid_cards", "stats", "pipeline", "data_table",
                   "content_image", "quadrant", "timeline", "stats", "closing"],
        "rules": {"max_slides": 20, "visual_ratio": 0.65, "key_findings": 2},
    },
    "business": {
        "name": "商务汇报", "description": "8-15 页,提案/汇报。",
        "slides": ["cover", "toc", "overview", "stats", "three_col",
                   "pipeline", "grid_cards", "data_table", "closing"],
        "rules": {"max_slides": 15, "visual_ratio": 0.50},
    },
    "defense": {
        "name": "论文答辩", "description": "45-65 页,完整答辩。",
        "slides": ["cover", "toc", "overview", "timeline", "quadrant",
                   "content_image", "pipeline", "data_table", "stats",
                   "quadrant", "timeline", "stats", "closing"],
        "rules": {"max_slides": 65, "visual_ratio": 0.60},
    },
    "school": {
        "name": "学校介绍", "description": "14 页,中国高校招生宣讲。",
        "slides": ["cover", "toc", "overview", "timeline", "three_col",
                   "grid_cards", "quadrant", "stats", "closing"],
        "rules": {"max_slides": 14, "visual_ratio": 0.55},
    },
}


def get_layout(key: str) -> LayoutTemplate:
    if key not in LAYOUTS:
        raise ValueError(f"未知布局: {key!r}。可用: {', '.join(LAYOUTS.keys())}")
    return LAYOUTS[key]


def get_talk_preset(key: str) -> dict:
    if key not in TALK_PRESETS:
        raise ValueError(f"未知演讲类型: {key!r}。可用: {', '.join(TALK_PRESETS.keys())}")
    return TALK_PRESETS[key]


def list_layouts() -> list[dict]:
    return [
        {"key": k, "name": v.name, "category": v.category, "description": v.description}
        for k, v in LAYOUTS.items()
    ]


def list_talk_types() -> list[dict]:
    return [
        {"key": k, "name": v["name"], "description": v["description"],
         "slide_count": len(v["slides"]), "max_slides": v["rules"].get("max_slides")}
        for k, v in TALK_PRESETS.items()
    ]
