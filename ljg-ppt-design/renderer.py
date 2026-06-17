"""主入口 — render_deck(preset, talk_type, content) → DeckSpec。

content 的 schema 由 talk_type 决定,详见 references/talk-types.md。
"""

from __future__ import annotations

from typing import Any

from .design_presets import get_preset
from .layout_templates import get_layout, get_talk_preset, TALK_PRESETS
from .slide_spec import DeckSpec, SlideSpec, SlideElement


CONTENT_SCHEMA: dict = {
    "conference": [
        {"layout": "cover", "content_key": "_cover", "title_from": "title"},
        {"layout": "toc", "content_key": "toc_items", "title_from": "目录"},
        {"layout": "overview", "content_key": "overview_cards", "title_from": "概览"},
        {"layout": "timeline", "content_key": "timeline", "title_from": "发展历程"},
        {"layout": "quadrant", "content_key": "quadrants_1", "title_from": "研究分类"},
        {"layout": "grid_cards", "content_key": "grid_items_1", "title_from": "研究亮点"},
        {"layout": "stats", "content_key": "stats", "title_from": "关键数据"},
        {"layout": "pipeline", "content_key": "pipeline", "title_from": "方法流程"},
        {"layout": "data_table", "content_key": "table_1", "title_from": "实验对比"},
        {"layout": "content_image", "content_key": "image_1", "title_from": "案例分析"},
        {"layout": "quadrant", "content_key": "quadrants_2", "title_from": "应用方向"},
        {"layout": "timeline", "content_key": "timeline_2", "title_from": "研究计划"},
        {"layout": "stats", "content_key": "stats_2", "title_from": "预期成果"},
        {"layout": "closing", "content_key": "_closing", "title_from": "致谢"},
    ],
    "business": [
        {"layout": "cover", "content_key": "_cover", "title_from": "title"},
        {"layout": "toc", "content_key": "toc_items", "title_from": "目录"},
        {"layout": "overview", "content_key": "overview_cards", "title_from": "项目总览"},
        {"layout": "stats", "content_key": "stats", "title_from": "关键指标"},
        {"layout": "three_col", "content_key": "three_col", "title_from": "方案对比"},
        {"layout": "pipeline", "content_key": "pipeline", "title_from": "执行计划"},
        {"layout": "grid_cards", "content_key": "grid_items", "title_from": "团队/资源"},
        {"layout": "data_table", "content_key": "table", "title_from": "数据支撑"},
        {"layout": "closing", "content_key": "_closing", "title_from": "Q&A"},
    ],
    "defense": [
        {"layout": "cover", "content_key": "_cover", "title_from": "title"},
        {"layout": "toc", "content_key": "toc_items", "title_from": "目录"},
        {"layout": "overview", "content_key": "overview_cards", "title_from": "研究背景"},
        {"layout": "timeline", "content_key": "timeline", "title_from": "研究脉络"},
        {"layout": "quadrant", "content_key": "quadrants", "title_from": "研究问题"},
        {"layout": "content_image", "content_key": "image_1", "title_from": "关键方法"},
        {"layout": "pipeline", "content_key": "pipeline", "title_from": "技术路线"},
        {"layout": "data_table", "content_key": "table_1", "title_from": "实验结果"},
        {"layout": "stats", "content_key": "stats", "title_from": "性能指标"},
        {"layout": "quadrant", "content_key": "quadrants_2", "title_from": "对比分析"},
        {"layout": "timeline", "content_key": "timeline_2", "title_from": "未来工作"},
        {"layout": "stats", "content_key": "stats_2", "title_from": "总结"},
        {"layout": "closing", "content_key": "_closing", "title_from": "致谢"},
    ],
    "school": [
        {"layout": "cover", "content_key": "_cover", "title_from": "title"},
        {"layout": "toc", "content_key": "toc_items", "title_from": "目录"},
        {"layout": "overview", "content_key": "overview_cards", "title_from": "学校概览"},
        {"layout": "timeline", "content_key": "timeline", "title_from": "历史沿革"},
        {"layout": "three_col", "content_key": "three_col", "title_from": "优势学科"},
        {"layout": "grid_cards", "content_key": "grid_items", "title_from": "知名校友"},
        {"layout": "quadrant", "content_key": "quadrants", "title_from": "校园生活"},
        {"layout": "stats", "content_key": "stats", "title_from": "招生数据"},
        {"layout": "closing", "content_key": "_closing", "title_from": "校训"},
    ],
}


def _render_slide(layout_key: str, content: Any, page_index: int, fallback_title: str = "") -> SlideSpec:
    layout = get_layout(layout_key)
    page_title = ""

    if layout_key in ("cover", "closing"):
        if not isinstance(content, dict):
            content = {}
        if "title" not in content and layout_key == "cover":
            content["title"] = content.get("_title") or fallback_title
        elements = _substitute_elements(layout.elements, content)
        return SlideSpec(
            layout=layout_key, index=page_index,
            title=content.get("title") or content.get("summary_title") or fallback_title,
            elements=elements, data=content or {},
        )

    original_content = content
    if isinstance(content, list):
        content = {"items": content}
    elif not isinstance(content, dict):
        content = {}

    if "title" not in content:
        content["title"] = fallback_title

    page_title = content.get("_title") or content.get("title") or fallback_title
    elements = _substitute_elements(layout.elements, content)
    return SlideSpec(
        layout=layout_key, index=page_index, title=page_title,
        elements=elements, data=original_content,
    )


def _substitute_elements(elements: tuple, content: dict) -> list:
    out: list = []
    for raw in elements:
        resolved = _resolve_placeholders(raw, content)
        out.append(SlideElement(**resolved))
    return out


def _resolve_placeholders(obj: Any, content: dict) -> Any:
    if isinstance(obj, str):
        return _substitute_str(obj, content)
    if isinstance(obj, dict):
        return {k: _resolve_placeholders(v, content) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_resolve_placeholders(v, content) for v in obj)
    return obj


def _substitute_str(s: str, content: dict) -> str:
    out = s
    for k, v in content.items():
        if not isinstance(v, (str, int, float)):
            continue
        token = "{" + k + "}"
        if token in out:
            out = out.replace(token, str(v))
    return out


def render_deck(preset: str, talk_type: str, content: dict, *, name: str = "untitled-deck", metadata: dict | None = None) -> DeckSpec:
    if talk_type not in CONTENT_SCHEMA:
        raise ValueError(f"未知 talk_type: {talk_type!r}。可用: {', '.join(CONTENT_SCHEMA.keys())}")

    schema = CONTENT_SCHEMA[talk_type]
    slides: list = []

    for i, spec in enumerate(schema):
        key = spec["content_key"]
        layout_key = spec["layout"]
        fallback_title = spec["title_from"]

        if key.startswith("_"):
            page_content = content.get(key.lstrip("_"), {})
        else:
            page_content = content.get(key)

        if page_content is None:
            if layout_key in ("cover", "closing"):
                page_content = {}
            else:
                continue

        slide = _render_slide(layout_key=layout_key, content=page_content,
                              page_index=i, fallback_title=fallback_title)
        slides.append(slide)

    return DeckSpec(name=name, preset=preset, talk_type=talk_type,
                    slides=slides, metadata=metadata or {})
