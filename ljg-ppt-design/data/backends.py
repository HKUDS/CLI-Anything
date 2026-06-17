"""后端抽象层 (re-export)。

用法:
  from ljg_ppt_design.data.backends import render_with_best_backend
  deck = render_deck("academic", "school", content)
  path, backend = render_with_best_backend(deck, "/tmp/out.pptx")
  print(f"用 {backend} 出了 {path}")
"""

from .libreoffice_backend import (
    is_libreoffice_available,
    is_cli_anything_libreoffice_available,
    render_to_pptx_via_libreoffice,
    render_with_best_backend,
)
from .pptx_renderer import render_to_pptx as render_to_pptx_via_python

__all__ = [
    "is_libreoffice_available",
    "is_cli_anything_libreoffice_available",
    "render_to_pptx_via_libreoffice",
    "render_to_pptx_via_python",
    "render_with_best_backend",
]
