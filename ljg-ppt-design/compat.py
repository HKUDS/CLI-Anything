"""ljg-ppt-design ↔ HKUDS CLI-Anything 兼容层。

把 ljg-ppt-design 的 DeckSpec (12 布局 / 语义色 / 像素坐标)
翻译成 HKUDS 原版 cli-anything-libreoffice 的 project dict (3 元素 / cm 字符串)。

为什么做这个:
  - ljg-ppt-design = 设计系统层 (4 preset × 12 layout × 5 维审查)
  - HKUDS 原版 = 工具控制层 (UNO 桥 / 元素 CRUD / 撤销栈)
  - 翻译 = 设计系统 → 工具控制,让 ljg-ppt-design 能复用 HKUDS 的 LibreOffice 渲染

反方向 (原版 project dict → DeckSpec) 也支持,用于读取他人用 cli-anything-libreoffice 做的 .pptx。

用法:
  from ljg_ppt_design import render_deck
  from ljg_ppt_design.compat import deck_to_lo_project, lo_project_to_deck

  deck = render_deck("academic", "school", content)
  project = deck_to_lo_project(deck)              # → 原版 project dict
  # 然后用原版 impress.add_slide + add_slide_element 喂给它
  # 最后 lo_backend.convert_to("pptx") 出文件

元素翻译表:
  bg             → 不支持 (LO 项目级背景需要 export 时设)
  line           → shape (细矩形, 0.1cm 厚)
  text           → text_box
  box            → shape (矩形, fill 色)
  image_placeholder → image
  grid_cards     → 拆成 N 个 shape + text_box
  grid_items     → 同上
  timeline_items → 拆成 N 个 shape (圆点) + text_box
  pipeline_items → 拆成 N 个 shape (色块) + text_box
  sidebar        → shape
  table          → 拆成多行 text_box + shape (LO 原版不直接支持 table)
"""

from __future__ import annotations

from typing import Any

from .design_presets import DesignPreset, get_preset
from .slide_spec import DeckSpec, SlideSpec, SlideElement


# LO 原版项目 dict 的 profile
LO_PROFILE_PRESENTATION = "presentation_16_9"
SLIDE_W_CM = 33.867
SLIDE_H_CM = 19.05
CANVAS_PX_W = 960
CANVAS_PX_H = 540


def px_to_cm(px: int, axis: str = "x") -> str:
    """960x540 px → 33.867x19.05 cm。"""
    if axis == "x":
        cm = px / CANVAS_PX_W * SLIDE_W_CM
    else:
        cm = px / CANVAS_PX_H * SLIDE_H_CM
    return f"{cm:.3f}cm"


def element_to_lo(el: SlideElement, preset: DesignPreset) -> list[dict]:
    """把一个 ljg 元素翻译成 0+ 个原版 LO 元素。"""
    out: list[dict] = []

    if el.type == "bg":
        # 背景色由 project 级别管理,这里跳过
        return out

    if el.type == "line":
        # 用细矩形代替
        is_horizontal = el.w >= el.h
        out.append({
            "type": "shape",
            "text": "",
            "x": px_to_cm(el.x, "x"),
            "y": px_to_cm(el.y, "y"),
            "width": px_to_cm(max(el.w, 1) if is_horizontal else 1, "x"),
            "height": px_to_cm(max(el.h, 1) if not is_horizontal else 1, "y"),
            "fill_color": preset.get_color(el.color),
        })
        return out

    if el.type == "text":
        out.append({
            "type": "text_box",
            "text": el.text,
            "x": px_to_cm(el.x, "x"),
            "y": px_to_cm(el.y, "y"),
            "width": px_to_cm(el.w, "x"),
            "height": px_to_cm(el.h, "y"),
            "font_size": el.fs,
            "bold": el.bold,
            "align": {0: "left", 1: "center", 2: "right"}.get(el.align, "left"),
            "color": preset.get_color(el.color),
        })
        return out

    if el.type == "box":
        out.append({
            "type": "shape",
            "text": el.text or "",
            "x": px_to_cm(el.x, "x"),
            "y": px_to_cm(el.y, "y"),
            "width": px_to_cm(el.w, "x"),
            "height": px_to_cm(el.h, "y"),
            "fill_color": preset.get_color(el.color),
        })
        return out

    if el.type == "image_placeholder":
        out.append({
            "type": "image",
            "text": el.text or "[ image ]",
            "x": px_to_cm(el.x, "x"),
            "y": px_to_cm(el.y, "y"),
            "width": px_to_cm(el.w, "x"),
            "height": px_to_cm(el.h, "y"),
        })
        return out

    if el.type in ("grid_cards", "grid_items"):
        # 拆成 N 个 card (shape + 文字)
        items = (el.fields and getattr(el, "_items", None)) or []
        # items 不在元素上,要从 slide data 取 — 这里由 deck_to_lo_project 处理
        out.append({
            "_grid_cards_placeholder": True,
            "spec": el,
            "x": px_to_cm(el.x, "x"),
            "y": px_to_cm(el.y, "y"),
        })
        return out

    if el.type == "timeline_items":
        out.append({"_timeline_placeholder": True, "spec": el})
        return out

    if el.type == "pipeline_items":
        out.append({"_pipeline_placeholder": True, "spec": el})
        return out

    if el.type == "sidebar":
        # 当作 box 处理
        out.append({
            "type": "shape",
            "text": el.text or "",
            "x": px_to_cm(el.x, "x"),
            "y": px_to_cm(el.y, "y"),
            "width": px_to_cm(el.w, "x"),
            "height": px_to_cm(el.h, "y"),
            "fill_color": preset.get_color(el.color),
        })
        return out

    if el.type == "table":
        # LO 原版不直接支持 table,丢成占位 (TODO)
        out.append({
            "type": "text_box",
            "text": el.data.get("interpretation", "[ table ]") if isinstance(el.data, dict) else "[ table ]",
            "x": px_to_cm(el.x, "x"),
            "y": px_to_cm(el.y, "y"),
            "width": px_to_cm(el.w, "x"),
            "height": px_to_cm(el.h, "y"),
        })
        return out

    return out


def deck_to_lo_project(deck: DeckSpec) -> dict:
    """把 DeckSpec → HKUDS 原版 project dict (type=impress)。"""
    preset = get_preset(deck.preset)
    project: dict = {
        "type": "impress",
        "profile": LO_PROFILE_PRESENTATION,
        "title": deck.name,
        "slides": [],
    }

    for slide_spec in deck.slides:
        slide = {
            "title": slide_spec.title or "",
            "content": "",
            "elements": [],
        }
        # 处理特殊元素 (需要 slide.data 介入)
        for el in slide_spec.elements:
            translated = element_to_lo(el, preset)
            for item in translated:
                if item.get("_grid_cards_placeholder"):
                    # 拆 grid: 用 slide.data
                    items_data = _extract_items(slide_spec)
                    grid_elements = _expand_grid(item["spec"], items_data, preset)
                    slide["elements"].extend(grid_elements)
                elif item.get("_timeline_placeholder"):
                    items_data = _extract_items(slide_spec)
                    slide["elements"].extend(_expand_timeline(item["spec"], items_data, preset))
                elif item.get("_pipeline_placeholder"):
                    items_data = _extract_items(slide_spec)
                    slide["elements"].extend(_expand_pipeline(item["spec"], items_data, preset))
                else:
                    slide["elements"].append(item)
        project["slides"].append(slide)

    return project


def lo_project_to_deck(project: dict, name: str = "imported", preset_key: str = "academic") -> DeckSpec:
    """把 HKUDS 原版 project dict → DeckSpec (只翻译 text_box / shape / image)。"""
    from .slide_spec import SlideSpec, SlideElement, DeckSpec
    from .layout_templates import LAYOUTS
    preset = get_preset(preset_key)

    slides: list[SlideSpec] = []
    for i, src_slide in enumerate(project.get("slides", [])):
        elements: list[SlideElement] = []
        for src_el in src_slide.get("elements", []):
            el = _lo_element_to_slide(src_el)
            if el:
                elements.append(el)
        slide = SlideSpec(
            layout="content_image",  # 默认 layout
            index=i, title=src_slide.get("title", ""),
            elements=elements, data=src_slide,
        )
        slides.append(slide)

    return DeckSpec(name=name, preset=preset_key, talk_type="business",
                    slides=slides, metadata={"source": "cli-anything-libreoffice"})


# ── 内部工具 ───────────────────────────────────────────
def _extract_items(slide_spec: SlideSpec) -> list[dict]:
    """从 slide.data 抽 items 列表。"""
    data = slide_spec.data
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("cards"), list):
            return data["cards"]
    return []


def _expand_grid(el: SlideElement, items: list[dict], preset: DesignPreset) -> list[dict]:
    """拆 grid_cards / grid_items 为 N 个 shape + text_box。"""
    if not items:
        return []
    out: list[dict] = []
    cols = max(el.cols, 1)
    rows = max(el.rows, 1) if el.rows else 1
    item_w = el.item_w or (el.w // cols)
    item_h = el.item_h or (el.h // rows)

    for idx, item in enumerate(items[:cols * rows]):
        c = idx % cols
        r = idx // cols
        ix = el.x + c * (item_w + el.gap_x)
        iy = el.y + r * (item_h + el.gap_y)
        # 卡片底框
        out.append({
            "type": "shape",
            "text": "",
            "x": px_to_cm(ix, "x"),
            "y": px_to_cm(iy, "y"),
            "width": px_to_cm(item_w, "x"),
            "height": px_to_cm(item_h, "y"),
            "fill_color": preset.get_color("light"),
        })
        # 字段文字
        if el.fields:
            for fi, field_tpl in enumerate(el.fields):
                field_key = field_tpl.strip("{}")
                value = str(item.get(field_key, ""))
                style = el.styles[fi] if fi < len(el.styles) else {}
                fs = style.get("fs", 16)
                bold = style.get("bold", False)
                color_role = style.get("color", "dark")
                y_offset = style.get("y_offset", 0)
                if style.get("bg") and not str(style["bg"]).startswith("{"):
                    out.append({
                        "type": "shape",
                        "text": "",
                        "x": px_to_cm(ix, "x"),
                        "y": px_to_cm(iy + y_offset, "y"),
                        "width": px_to_cm(item_w, "x"),
                        "height": px_to_cm(30, "y"),
                        "fill_color": preset.get_color(style["bg"]),
                    })
                out.append({
                    "type": "text_box",
                    "text": value,
                    "x": px_to_cm(ix + 4, "x"),
                    "y": px_to_cm(iy + y_offset + 4, "y"),
                    "width": px_to_cm(item_w - 8, "x"),
                    "height": px_to_cm(30, "y"),
                    "font_size": fs,
                    "bold": bold,
                    "color": preset.get_color(color_role),
                })
    return out


def _expand_timeline(el: SlideElement, items: list[dict], preset: DesignPreset) -> list[dict]:
    out: list[dict] = []
    count = min(len(items), el.count or len(items))
    for i, item in enumerate(items[:count]):
        iy = el.start_y + i * el.gap
        # 圆点 (LO 用 shape 圆形)
        out.append({
            "type": "shape",
            "text": "",
            "x": px_to_cm(el.x - 6, "x"),
            "y": px_to_cm(iy + 4, "y"),
            "width": px_to_cm(8, "x"),
            "height": px_to_cm(8, "y"),
            "fill_color": preset.get_color("primary"),
            "shape_kind": "ellipse",
        })
        # date
        out.append({
            "type": "text_box",
            "text": str(item.get("date", "")),
            "x": px_to_cm(el.x + 6, "x"),
            "y": px_to_cm(iy, "y"),
            "width": px_to_cm(100, "x"),
            "height": px_to_cm(20, "y"),
            "font_size": 16, "bold": True,
            "color": preset.get_color("primary"),
        })
        # event
        out.append({
            "type": "text_box",
            "text": str(item.get("event", "")),
            "x": px_to_cm(el.x + 110, "x"),
            "y": px_to_cm(iy, "y"),
            "width": px_to_cm(500, "x"),
            "height": px_to_cm(30, "y"),
            "font_size": 16,
            "color": preset.get_color("dark"),
        })
    return out


def _expand_pipeline(el: SlideElement, items: list[dict], preset: DesignPreset) -> list[dict]:
    out: list[dict] = []
    for i, item in enumerate(items):
        ix = el.x + i * (el.item_w + el.gap)
        color_role = item.get("color", ["primary", "secondary", "accent", "dark"][i % 4])
        # 色块
        out.append({
            "type": "shape",
            "text": str(item.get("step_num", str(i + 1))),
            "x": px_to_cm(ix, "x"),
            "y": px_to_cm(el.y, "y"),
            "width": px_to_cm(el.item_w, "x"),
            "height": px_to_cm(40, "y"),
            "fill_color": preset.get_color(color_role),
            "font_size": 16, "bold": True, "align": "center",
            "color": preset.get_color("white"),
        })
        # 名称
        out.append({
            "type": "text_box",
            "text": str(item.get("step_name", "")),
            "x": px_to_cm(ix, "x"),
            "y": px_to_cm(el.y + 45, "y"),
            "width": px_to_cm(el.item_w, "x"),
            "height": px_to_cm(20, "y"),
            "font_size": 12, "bold": True, "align": "center",
            "color": preset.get_color("primary"),
        })
    return out


def _lo_element_to_slide(src_el: dict) -> SlideElement | None:
    """反向: LO 元素 dict → SlideElement。"""
    el_type = src_el.get("type")
    if el_type not in ("text_box", "shape", "image"):
        return None
    # cm → px (粗略 1cm ≈ 28.35px @ 960x540→33.867x19.05 cm)
    x_cm = _parse_cm(src_el.get("x", "0cm"))
    y_cm = _parse_cm(src_el.get("y", "0cm"))
    w_cm = _parse_cm(src_el.get("width", "0cm"))
    h_cm = _parse_cm(src_el.get("height", "0cm"))
    px = lambda c, axis: int(c / (SLIDE_W_CM if axis == "x" else SLIDE_H_CM) * (CANVAS_PX_W if axis == "x" else CANVAS_PX_H))
    return SlideElement(
        type="text" if el_type == "text_box" else ("box" if el_type == "shape" else "image_placeholder"),
        x=px(x_cm, "x"), y=px(y_cm, "y"),
        w=px(w_cm, "x"), h=px(h_cm, "y"),
        text=src_el.get("text", ""),
        fs=src_el.get("font_size", 18),
        bold=src_el.get("bold", False),
    )


def _parse_cm(s: str) -> float:
    """'2cm' → 2.0; '10.5cm' → 10.5。"""
    if isinstance(s, (int, float)):
        return float(s)
    s = s.strip()
    if s.endswith("cm"):
        return float(s[:-2])
    if s.endswith("mm"):
        return float(s[:-2]) / 10
    if s.endswith("in"):
        return float(s[:-2]) * 2.54
    try:
        return float(s)
    except ValueError:
        return 0.0
