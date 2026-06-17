"""Self-contained hub bridge for cli-anything-ljg-ppt-design.

在 HKUDS/CLI-Anything 仓库 fork 里,这个包和 ljg_ppt_design 是同 package 的兄弟。
所以可以直接 import 兄弟包,不用 sys.path 黑魔法。
"""

from __future__ import annotations

# 兄弟包: ljg_ppt_design/ 就在同一父目录
from ljg_ppt_design import (
    PRESETS,
    LAYOUTS,
    TALK_PRESETS,
    CONTENT_SCHEMA,
    DesignPreset,
    LayoutTemplate,
    SlideSpec,
    SlideElement,
    DeckSpec,
    get_preset,
    list_presets,
    get_layout,
    list_layouts,
    get_talk_preset,
    list_talk_types,
    rgb_to_hex,
    hex_to_rgb,
    render_deck,
    REVIEW_DIMENSIONS,
    validate_slide,
    review_deck,
    contrast_ratio,
)
from ljg_ppt_design.compat import deck_to_lo_project, lo_project_to_deck
from ljg_ppt_design.data.backends import (
    is_libreoffice_available,
    is_cli_anything_libreoffice_available,
    render_with_best_backend,
)

__version__ = "0.1.0"

__all__ = [
    "PRESETS", "LAYOUTS", "TALK_PRESETS", "CONTENT_SCHEMA",
    "DesignPreset", "LayoutTemplate", "SlideSpec", "SlideElement", "DeckSpec",
    "get_preset", "list_presets",
    "get_layout", "list_layouts",
    "get_talk_preset", "list_talk_types",
    "rgb_to_hex", "hex_to_rgb",
    "render_deck", "render_with_best_backend",
    "deck_to_lo_project", "lo_project_to_deck",
    "REVIEW_DIMENSIONS", "validate_slide", "review_deck", "contrast_ratio",
    "is_libreoffice_available", "is_cli_anything_libreoffice_available",
]
