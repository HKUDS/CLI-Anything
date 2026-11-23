"""Script-Fu generation for GIMP 2.10 and 3.x.

No GIMP installation is required: the tests inspect the generated batch
script and command line.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.gimp.utils import gimp_backend


PROJECT = {
    "canvas": {"width": 64, "height": 48, "background": "#ffffff"},
    "layers": [
        {
            "type": "text",
            "name": "Title",
            "text": "Hello",
            "font": "Sans",
            "font_size": 12,
            "visible": True,
            "offset_x": 4,
            "offset_y": 8,
        },
    ],
}


def _render(gimp3, fmt="PNG", preset="png", quality=None):
    return gimp_backend._render_script(
        PROJECT, "/tmp/out", fmt, preset, quality, gimp3
    )


def test_gimp3_render_uses_gimp3_pdb_names():
    script = _render(True)

    assert "file-png-export" in script
    assert "file-png-save" not in script
    assert "gimp-text-font" in script
    assert "gimp-fonts-get-list" in script
    assert "gimp-text-fontname" not in script
    assert "gimp-context-set-foreground" in script
    assert "gimp-palette-set-foreground" not in script
    assert "gimp-drawable-edit-fill" in script
    assert "gimp-edit-fill" not in script
    assert "gimp-image-get-active-drawable" not in script
    assert script.count("gimp-image-flatten") == 1


def test_gimp3_render_keeps_the_210_pdb_names():
    script = _render(False)

    assert "file-png-save" in script
    assert "file-png-export" not in script
    assert "gimp-text-fontname" in script
    assert "gimp-fonts-get-list" not in script
    assert "gimp-context-set-foreground" in script
    assert "gimp-palette-set-foreground" not in script


def test_gimp3_layer_new_puts_the_name_second():
    script = _render(True)

    assert '(gimp-layer-new image "Background" 64 48 RGB-IMAGE 100 LAYER-MODE-NORMAL)' in script


def test_gimp2_layer_new_keeps_the_name_after_the_type():
    script = _render(False)

    assert '(gimp-layer-new image 64 48 RGB-IMAGE "Background" 100 LAYER-MODE-NORMAL)' in script


def test_gimp3_text_layer_is_created_with_a_font_id():
    script = _render(True)

    assert '(gimp-text-font image -1 0 0 "Hello" 0 TRUE 12 font)' in script
    # gimp-text-font inserts the layer itself
    assert "gimp-image-insert-layer image l0" not in script


def test_gimp2_text_layer_is_auto_inserted_by_text_fontname():
    script = _render(False)

    assert '(gimp-text-fontname image -1 0 0 "Hello" 0 TRUE 12 UNIT-PIXEL "Sans")' in script
    assert "gimp-image-insert-layer image l0" not in script


def test_gimp3_jpeg_export_uses_the_quality_and_export_api():
    script = _render(True, fmt="JPEG", preset="jpeg-high")

    assert "file-jpeg-export" in script
    assert '"/tmp/out" -1 0.95 0.0 FALSE FALSE FALSE "sub-sampling-1x1"' in script


def test_gimp3_gif_export_does_not_convert_indexed_first():
    script = _render(True, fmt="GIF", preset="gif")

    assert "file-gif-export" in script
    assert "gimp-image-convert-indexed" not in script


def test_gimp2_gif_still_converts_to_indexed():
    script = _render(False, fmt="GIF", preset="gif")

    assert "gimp-image-convert-indexed" in script
    assert "file-gif-save" in script


def test_gimp3_unsupported_format_raises():
    with pytest.raises(ValueError, match="GIMP 3 export is not implemented"):
        _render(True, fmt="WEBP", preset="webp")


def test_gimp2_unsupported_format_keeps_the_overwrite_fallback():
    script = _render(False, fmt="WEBP", preset="webp")

    assert "gimp-file-overwrite" in script


def _capture_batch_command(monkeypatch, gimp3):
    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(gimp_backend, "find_gimp", lambda: "/usr/bin/gimp")
    monkeypatch.setattr(gimp_backend.subprocess, "run", fake_run)

    gimp_backend.batch_script_fu("(gimp-quit 0)", gimp3=gimp3)
    return captured[0]


def test_gimp3_batch_names_the_interpreter_and_quits(monkeypatch):
    cmd = _capture_batch_command(monkeypatch, gimp3=True)

    assert "--batch-interpreter=plug-in-script-fu-eval" in cmd
    assert "--quit" in cmd
    assert cmd[-2:] == ["-b", "(gimp-quit 0)"]


def test_gimp2_batch_names_the_interpreter_without_quit(monkeypatch):
    cmd = _capture_batch_command(monkeypatch, gimp3=False)

    assert "--batch-interpreter=plug-in-script-fu-eval" in cmd
    assert "--quit" not in cmd


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("GNU Image Manipulation Program version 3.2.6", 3),
        ("GNU Image Manipulation Program version 2.10.38", 2),
        ("unexpected output", 0),
    ],
)
def test_major_version_parsing(monkeypatch, output, expected):
    monkeypatch.setattr(gimp_backend, "get_version", lambda: output)
    monkeypatch.setattr(gimp_backend, "_gimp_major", None)

    assert gimp_backend.get_major_version() == expected
