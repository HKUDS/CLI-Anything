"""4 套设计预设 (Design Presets)。

每个预设包含:
  - 配色 (colors) — 语义命名: primary/secondary/accent/dark/light/bg
  - 字体 (fonts)   — title/subtitle/body/caption/chinese
  - 间距 (spacing) — margin/gap/card_padding/line_height
  - 规则 (rules)   — 视觉密度/留白/单页要点数 等

来源: harness-anything (yb2460) — 已去掉 WPS 依赖,改为纯 Python。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


# ── 类型别名 ────────────────────────────────────────────────
RGB = Tuple[int, int, int]
FontSpec = Tuple[str, int, RGB]


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def hex_to_rgb(hex_str: str) -> RGB:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


@dataclass(frozen=True)
class DesignPreset:
    name: str
    key: str
    colors: dict
    fonts: dict
    spacing: dict
    rules: dict
    description: str = ""
    source: str = ""

    def hex_colors(self) -> dict:
        return {k: rgb_to_hex(v) for k, v in self.colors.items()}

    def get_color(self, role: str) -> RGB:
        if role in ("white",):
            return (255, 255, 255)
        if role in ("black",):
            return (0, 0, 0)
        if role in ("gray", "light_text", "accent_light"):
            return (160, 160, 160)
        return self.colors.get(role, self.colors["dark"])

    def get_font(self, role: str = "body") -> FontSpec:
        return self.fonts.get(role, self.fonts["body"])

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "colors": {k: list(v) if isinstance(v, tuple) else v for k, v in self.colors.items()},
            "hex_colors": self.hex_colors(),
            "fonts": {k: {"family": v[0], "size": v[1], "color": list(v[2])} for k, v in self.fonts.items()},
            "spacing": self.spacing,
            "rules": self.rules,
        }


PRESETS: dict[str, DesignPreset] = {}

PRESETS["academic"] = DesignPreset(
    key="academic", name="学术答辩",
    description="学术会议 / 论文答辩 / 基金申请 / Journal Club 适用。色盲友好,留白 40%,每页一个主题。",
    source="scientific-slides",
    colors={
        "primary": (26, 60, 139), "secondary": (230, 119, 51), "accent": (24, 128, 80),
        "dark": (34, 34, 34), "light": (245, 248, 252), "bg": (255, 255, 255),
    },
    fonts={
        "title": ("Arial", 40, (26, 60, 139)),
        "subtitle": ("Arial", 22, (100, 100, 100)),
        "body": ("Arial", 24, (34, 34, 34)),
        "caption": ("Arial", 16, (128, 128, 128)),
        "chinese": ("Microsoft YaHei", 24, (34, 34, 34)),
    },
    spacing={"margin": 80, "gap": 24, "card_padding": 20, "line_height": 1.5},
    rules={"visual_ratio": 0.65, "max_colors": 5, "colorblind_safe": True,
           "one_idea_per_slide": True, "white_space": 0.40, "max_bullets": 6,
           "prefer_sans_serif": True},
)

PRESETS["consultant"] = DesignPreset(
    key="consultant", name="咨询顾问",
    description="商业计划书 / 咨询报告 / 年度汇报适用。59 种网格布局,4 色限制,中等密度。",
    source="pptx-from-layouts",
    colors={
        "primary": (0, 51, 102), "secondary": (0, 168, 232), "accent": (255, 140, 0),
        "dark": (33, 33, 33), "light": (242, 246, 250), "bg": (255, 255, 255),
    },
    fonts={
        "title": ("Arial", 36, (0, 51, 102)),
        "subtitle": ("Arial", 20, (80, 80, 80)),
        "body": ("Arial", 18, (33, 33, 33)),
        "caption": ("Arial", 14, (140, 140, 140)),
        "chinese": ("Microsoft YaHei", 18, (33, 33, 33)),
    },
    spacing={"margin": 60, "gap": 20, "card_padding": 16, "line_height": 1.4},
    rules={"visual_ratio": 0.50, "max_colors": 4, "colorblind_safe": False,
           "one_idea_per_slide": True, "white_space": 0.40, "max_bullets": 5,
           "prefer_sans_serif": True, "grid_layout": True, "content_density": "medium"},
)

PRESETS["business"] = DesignPreset(
    key="business", name="商务汇报",
    description="会议汇报 / 项目提案 / 教学课件适用。商务蓝 + 强调红 + 绿,留白 35%,最多 6 要点。",
    source="pptx",
    colors={
        "primary": (0, 82, 148), "secondary": (200, 40, 40), "accent": (45, 160, 80),
        "dark": (45, 45, 48), "light": (248, 249, 250), "bg": (255, 255, 255),
    },
    fonts={
        "title": ("Arial", 36, (0, 82, 148)),
        "subtitle": ("Arial", 20, (90, 90, 90)),
        "body": ("Arial", 18, (45, 45, 48)),
        "caption": ("Arial", 14, (140, 140, 140)),
        "chinese": ("Microsoft YaHei", 18, (45, 45, 48)),
    },
    spacing={"margin": 70, "gap": 22, "card_padding": 18, "line_height": 1.4},
    rules={"visual_ratio": 0.45, "max_colors": 4, "colorblind_safe": False,
           "one_idea_per_slide": True, "white_space": 0.35, "max_bullets": 6,
           "prefer_sans_serif": True, "content_density": "medium"},
)

PRESETS["tech"] = DesignPreset(
    key="tech", name="科技极简",
    description="科技产品发布 / AI 技术演示 / 数据报告适用。暗色模式,3 色极简,留白 50%,低密度。",
    source="modern-tech-design",
    colors={
        "primary": (15, 20, 35), "secondary": (0, 200, 255), "accent": (255, 100, 60),
        "dark": (15, 20, 35), "light": (240, 242, 245), "bg": (15, 20, 35),
    },
    fonts={
        "title": ("Arial", 44, (255, 255, 255)),
        "subtitle": ("Arial", 20, (160, 180, 200)),
        "body": ("Arial", 20, (255, 255, 255)),
        "caption": ("Arial", 14, (120, 130, 150)),
        "chinese": ("Microsoft YaHei", 20, (255, 255, 255)),
    },
    spacing={"margin": 100, "gap": 30, "card_padding": 24, "line_height": 1.6},
    rules={"visual_ratio": 0.55, "max_colors": 3, "colorblind_safe": True,
           "one_idea_per_slide": True, "white_space": 0.50, "max_bullets": 4,
           "prefer_sans_serif": True, "dark_mode": True, "content_density": "low"},
)


def get_preset(key: str) -> DesignPreset:
    if key not in PRESETS:
        raise ValueError(f"未知预设: {key!r}。可用: {', '.join(PRESETS.keys())}")
    return PRESETS[key]


def list_presets() -> list[dict]:
    return [
        {
            "key": p.key, "name": p.name, "description": p.description,
            "max_bullets": p.rules.get("max_bullets"),
            "white_space": p.rules.get("white_space"),
            "visual_ratio": p.rules.get("visual_ratio"),
            "dark_mode": p.rules.get("dark_mode", False),
        }
        for p in PRESETS.values()
    ]
