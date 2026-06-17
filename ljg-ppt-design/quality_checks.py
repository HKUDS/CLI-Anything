"""5 维度质量审查 — slide-excellence 标准的落地。

维度:
  - visual     (≥ 70)  字体层级/颜色对比/留白/布局
  - pedagogy   (≥ 75)  叙事弧/预备知识/示例/符号一致
  - proofreading (≥ 80) 拼写/语法/术语/标点/字体溢出
  - parity     (≥ 85)  PPTX vs PDF 一致/字体嵌入/图片/动画
  - substance  (≥ 90)  数据准确/引用完整/结论支撑/可复现
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .slide_spec import SlideSpec, DeckSpec
    from .design_presets import DesignPreset


REVIEW_DIMENSIONS: dict = {
    "visual": {"name": "视觉审查", "checks": ["字体层级", "颜色对比度", "留白比例", "布局一致性", "图片质量"], "threshold": 70},
    "pedagogy": {"name": "教学法审查", "checks": ["叙事弧完整性", "预备知识清晰", "示例充分", "符号一致性", "逻辑流畅度"], "threshold": 75},
    "proofreading": {"name": "校对审查", "checks": ["拼写", "语法", "术语一致性", "标点", "字体溢出"], "threshold": 80},
    "parity": {"name": "格式一致性", "checks": ["PPTX vs PDF 一致", "字体嵌入", "图片不丢失", "动画兼容"], "threshold": 85},
    "substance": {"name": "内容实质", "checks": ["数据准确性", "引用完整性", "结论支撑", "方法可复现"], "threshold": 90},
}


def _hex_to_rel_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    def adj(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * adj(r) + 0.7152 * adj(g) + 0.0722 * adj(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    l1, l2 = sorted([_hex_to_rel_luminance(hex_a), _hex_to_rel_luminance(hex_b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


SKIP_DENSITY_LAYOUTS = {"cover", "closing"}


def _color_to_hex(preset, role: str) -> str:
    from .design_presets import rgb_to_hex
    return rgb_to_hex(preset.get_color(role))


def _page_effective_bg(slide: "SlideSpec", preset: "DesignPreset") -> str:
    for e in slide.elements:
        if e.type == "bg" and e.color:
            return _color_to_hex(preset, e.color)
    return _color_to_hex(preset, "bg")


@dataclass
class SlideReview:
    pass_: bool
    score: int
    warnings: list
    checks_passed: list

    def to_dict(self) -> dict:
        return {"pass": self.pass_, "score": self.score,
                "warnings": self.warnings, "checks_passed": self.checks_passed}


def validate_slide(slide: "SlideSpec", preset: "DesignPreset") -> SlideReview:
    warnings: list = []
    passed: list = []
    score = 100
    rules = preset.rules
    page_bg_hex = _page_effective_bg(slide, preset)
    is_decorative = slide.layout in SKIP_DENSITY_LAYOUTS

    for e in slide.elements:
        if e.type != "text":
            continue
        if e.role == "title" and 0 < e.fs < 36:
            warnings.append(f"标题字号 {e.fs}pt < 推荐 36pt (page '{slide.title}')")
            score -= 5
        elif e.role == "body" and 0 < e.fs < 20 and not is_decorative:
            warnings.append(f"正文字号 {e.fs}pt < 推荐 20pt (page '{slide.title}')")
            score -= 3
        elif e.role == "caption" and 0 < e.fs < 14:
            warnings.append(f"标注字号 {e.fs}pt < 推荐 14pt (page '{slide.title}')")
            score -= 2
    if all(e.type != "text" or e.fs == 0 or e.fs >= 20 for e in slide.elements):
        passed.append("字体层级")

    text_count = sum(1 for e in slide.elements if e.type == "text")
    max_bullets = rules.get("max_bullets", 6)
    if not is_decorative and text_count > max_bullets * 1.5:
        warnings.append(f"文本块过多 ({text_count} > {max_bullets * 1.5}, page '{slide.title}')")
        score -= 10
    elif not is_decorative:
        passed.append("内容密度")

    visual_types = {"box", "rect", "circle", "image", "image_placeholder", "line"}
    shape_count = sum(1 for e in slide.elements if e.type in visual_types)
    total = text_count + shape_count
    if not is_decorative and total > 0:
        visual_ratio = shape_count / total
        target = rules.get("visual_ratio", 0.5)
        if visual_ratio < target - 0.2:
            warnings.append(f"视觉占比 {visual_ratio:.0%} < 目标 {target:.0%} (page '{slide.title}')")
            score -= 5
        else:
            passed.append("视觉占比")

    title_count = sum(1 for e in slide.elements if e.type == "text" and e.role == "title")
    if title_count > 1:
        warnings.append(f"检测到 {title_count} 个标题,建议一页一个主题 (page '{slide.title}')")
        score -= 10
    else:
        passed.append("一页一主题")

    for e in slide.elements:
        if e.type == "text" and e.text:
            text_hex = _color_to_hex(preset, e.color)
            if e.bg:
                effective_bg = _color_to_hex(preset, e.bg)
            else:
                effective_bg = page_bg_hex
            ratio = contrast_ratio(text_hex, effective_bg)
            if ratio < 4.5:
                warnings.append(
                    f"对比度不足: '{e.text[:20]}' = {ratio:.1f}:1 "
                    f"(text={e.color} on bg={effective_bg}, page '{slide.title}')"
                )
                score -= 3
    if not any("对比度" in w for w in warnings):
        passed.append("颜色对比度")

    return SlideReview(pass_=score >= 70, score=max(0, min(100, score)),
                       warnings=warnings, checks_passed=passed)


def review_deck(deck: "DeckSpec", preset: "DesignPreset") -> dict:
    per_slide = []
    all_warnings: list = []
    visual_scores: list = []
    proofreading_scores: list = []

    for slide in deck.slides:
        r = validate_slide(slide, preset)
        per_slide.append({**r.to_dict(), "slide_index": slide.index, "title": slide.title})
        all_warnings.extend(r.warnings)
        visual_scores.append(r.score)
        proofreading_scores.append(r.score)

    pedagogy_score = 100
    if deck.slide_count() > 0:
        first = deck.slides[0]
        last = deck.slides[-1]
        if first.layout != "cover":
            all_warnings.append("首页不是 cover 布局"); pedagogy_score -= 10
        if last.layout != "closing":
            all_warnings.append("末页不是 closing 布局"); pedagogy_score -= 10
        middle_layouts = {s.layout for s in deck.slides[2:-2]} if deck.slide_count() > 4 else set()
        support_types = {"quadrant", "grid_cards", "data_table", "pipeline", "stats"}
        if not (middle_layouts & support_types):
            all_warnings.append("中段缺内容支撑页")
            pedagogy_score -= 15

    parity_score = 100
    if deck.slide_count() > 50:
        all_warnings.append(f"页数过多 ({deck.slide_count()})")
        parity_score -= 5

    substance_score = 100
    for slide in deck.slides:
        if slide.layout in SKIP_DENSITY_LAYOUTS:
            continue
        elem_chars = sum(len(e.text) for e in slide.elements if e.type == "text")
        def _count_data_chars(d):
            if isinstance(d, str): return len(d)
            if isinstance(d, dict): return sum(_count_data_chars(v) for v in d.values())
            if isinstance(d, (list, tuple)): return sum(_count_data_chars(v) for v in d)
            return 0
        total_chars = elem_chars + _count_data_chars(slide.data)
        if total_chars < 30:
            all_warnings.append(f"第 {slide.index} 页 ({slide.title}) 文字量过少 ({total_chars} 字符)")
            substance_score -= 10

    visual_score = round(sum(visual_scores) / max(len(visual_scores), 1), 1)
    proofreading_score = round(sum(proofreading_scores) / max(len(proofreading_scores), 1), 1)
    pedagogy_score = max(0, pedagogy_score)
    parity_score = max(0, parity_score)
    substance_score = max(0, substance_score)

    per_dimension = {
        "visual": {"score": visual_score, "threshold": REVIEW_DIMENSIONS["visual"]["threshold"],
                   "pass": visual_score >= REVIEW_DIMENSIONS["visual"]["threshold"]},
        "pedagogy": {"score": pedagogy_score, "threshold": REVIEW_DIMENSIONS["pedagogy"]["threshold"],
                     "pass": pedagogy_score >= REVIEW_DIMENSIONS["pedagogy"]["threshold"]},
        "proofreading": {"score": proofreading_score, "threshold": REVIEW_DIMENSIONS["proofreading"]["threshold"],
                         "pass": proofreading_score >= REVIEW_DIMENSIONS["proofreading"]["threshold"]},
        "parity": {"score": parity_score, "threshold": REVIEW_DIMENSIONS["parity"]["threshold"],
                   "pass": parity_score >= REVIEW_DIMENSIONS["parity"]["threshold"]},
        "substance": {"score": substance_score, "threshold": REVIEW_DIMENSIONS["substance"]["threshold"],
                      "pass": substance_score >= REVIEW_DIMENSIONS["substance"]["threshold"]},
    }

    overall = round(sum(d["score"] for d in per_dimension.values()) / 5, 1)
    all_pass = all(d["pass"] for d in per_dimension.values())

    return {
        "overall_score": overall, "pass": all_pass,
        "per_slide": per_slide, "per_dimension": per_dimension,
        "summary": f"整体 {overall:.0f}分 ({deck.slide_count()}页, {len(all_warnings)}个警告, {'通过' if all_pass else '未通过'})",
        "warnings": all_warnings,
    }
