"""LibreOffice 后端 — 用 HKUDS 原版 cli-anything-libreoffice + soffice headless 出 .pptx/.pdf/.odp。

需要:
  - 装 LibreOffice: brew install --cask libreoffice (macOS) / apt install libreoffice (Linux)
  - 装原版 CLI: pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=libreoffice/agent-harness

后端优先级链:
  libreoffice (跨平台真 PPT)  →  python-pptx (无需 LO)  →  error

用法:
  from ljg_ppt_design import render_deck
  from ljg_ppt_design.data.backends import render_with_best_backend
  deck = render_deck("academic", "school", content)
  render_with_best_backend(deck, "/tmp/output.pptx")  # 自动选 backend
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from ..slide_spec import DeckSpec
from ..compat import deck_to_lo_project


def is_libreoffice_available() -> bool:
    """检查系统是否装了 LibreOffice。"""
    return shutil.which("libreoffice") is not None or shutil.which("soffice") is not None


def is_cli_anything_libreoffice_available() -> bool:
    """检查能不能 import HKUDS 原版 cli_anything.libreoffice。"""
    try:
        import cli_anything.libreoffice  # noqa: F401
        return True
    except ImportError:
        return False


def render_to_pptx_via_libreoffice(deck: DeckSpec, output_path: str) -> str:
    """用 LibreOffice 后端出 .pptx。

    流程:
      1. DeckSpec → LO project dict (compat 翻译)
      2. 用原版 cli_anything.libreoffice 写 ODF + 元素
      3. lo_backend.convert("pptx") 调 soffice 转格式
    """
    if not is_libreoffice_available():
        raise RuntimeError(
            "LibreOffice 没装。装一下:\n"
            "  macOS: brew install --cask libreoffice\n"
            "  Linux: apt install libreoffice\n"
            "然后再装原版: pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=libreoffice/agent-harness"
        )
    if not is_cli_anything_libreoffice_available():
        raise RuntimeError(
            "HKUDS 原版 cli_anything.libreoffice 没装。装:\n"
            "  pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=libreoffice/agent-harness"
        )

    # 1. 翻译
    project = deck_to_lo_project(deck)

    # 2. 用原版 impress 模块建 project
    from cli_anything.libreoffice.core import (
        document as doc_mod,
        impress as impress_mod,
    )
    from cli_anything.libreoffice.utils import lo_backend
    from cli_anything.libreoffice.core.session import Session

    # 把 project 灌进 session
    sess = Session()
    sess.set_project(project, path=None)

    # 把 slides 加到 session.project (原版 API)
    for src_slide in project["slides"]:
        slide = impress_mod.add_slide(
            sess.get_project(),
            title=src_slide.get("title", ""),
            content=src_slide.get("content", ""),
        )
        for el in src_slide.get("elements", []):
            # 原版 API 调
            try:
                impress_mod.add_slide_element(
                    sess.get_project(),
                    slide_index=len(sess.get_project()["slides"]) - 1,
                    element_type=_map_lo_el_type(el.get("type")),
                    text=el.get("text", ""),
                    x=el.get("x", "0cm"),
                    y=el.get("y", "0cm"),
                    width=el.get("width", "5cm"),
                    height=el.get("height", "2cm"),
                )
            except ValueError:
                # 元素类型不被原版支持,跳过 (e.g. _grid_cards_placeholder 等)
                pass

    # 3. 落盘 ODF + 转 PPTX
    with tempfile.TemporaryDirectory() as tmpdir:
        odf_path = Path(tmpdir) / f"{deck.name or 'deck'}.odp"
        # 用原版 export 模块
        from cli_anything.libreoffice.core.export import export
        export(sess.get_project(), str(odf_path), preset="odp", overwrite=True)
        # 用 lo_backend 调 soffice 转 pptx
        out_dir = Path(output_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        lo_backend.convert(str(odf_path), "pptx", output_dir=str(out_dir))
        # convert 把同名 .pptx 写到 out_dir
        converted = out_dir / f"{odf_path.stem}.pptx"
        if converted.exists() and str(converted.resolve()) != str(Path(output_path).resolve()):
            shutil.move(str(converted), output_path)

    return output_path


def _map_lo_el_type(t: str) -> str:
    """翻译元素类型到原版 API。"""
    if t in ("text_box", "shape", "image"):
        return t
    return "text_box"  # 默认


# ── 抽象层 ─────────────────────────────────────────────
def render_with_best_backend(deck: DeckSpec, output_path: str) -> tuple[str, str]:
    """按优先级选 backend: libreoffice → python-pptx → error。

    Returns:
        (output_path, backend_name)
    """
    if is_libreoffice_available() and is_cli_anything_libreoffice_available():
        try:
            render_to_pptx_via_libreoffice(deck, output_path)
            return output_path, "libreoffice"
        except Exception as e:
            print(f"[ljg-ppt-design] LO backend 失败: {e}; 降级到 python-pptx", file=sys.stderr)

    # 降级到 python-pptx
    from .pptx_renderer import render_to_pptx as render_to_pptx_via_python
    render_to_pptx_via_python(deck, output_path)
    return output_path, "python-pptx"
