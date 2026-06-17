"""ljg-ppt-design — PPT 设计系统 skill。

跨平台、纯 Python、无 WPS 依赖。
提供 4 套预设 + 12 种布局 + 4 种演讲类型 + 5 维度质量审查。

主入口:
  from ljg_ppt_design import render_deck
  deck = render_deck("academic", "school", content_dict)
  deck.write("out.json")

下游消费者 (按需):
  - lark-slides   → 飞书 PPT
  - pptx          → 本地 python-pptx
  - reveal.js     → Web slide
"""

from __future__ import annotations

from .design_presets import (
    PRESETS,
    DesignPreset,
    get_preset,
    list_presets,
    rgb_to_hex,
    hex_to_rgb,
)
from .layout_templates import (
    LAYOUTS,
    TALK_PRESETS,
    LayoutTemplate,
    get_layout,
    get_talk_preset,
    list_layouts,
    list_talk_types,
)
from .slide_spec import SlideSpec, SlideElement, DeckSpec
from .renderer import render_deck, CONTENT_SCHEMA
from .quality_checks import (
    REVIEW_DIMENSIONS,
    validate_slide,
    review_deck,
    contrast_ratio,
)

__version__ = "0.1.0"
__all__ = [
    # 数据
    "PRESETS", "LAYOUTS", "TALK_PRESETS", "CONTENT_SCHEMA",
    # 类型
    "DesignPreset", "LayoutTemplate", "SlideSpec", "SlideElement", "DeckSpec",
    # 预设/布局查询
    "get_preset", "list_presets",
    "get_layout", "list_layouts",
    "get_talk_preset", "list_talk_types",
    # 颜色
    "rgb_to_hex", "hex_to_rgb",
    # 渲染
    "render_deck",
    # 审查
    "REVIEW_DIMENSIONS", "validate_slide", "review_deck", "contrast_ratio",
]
