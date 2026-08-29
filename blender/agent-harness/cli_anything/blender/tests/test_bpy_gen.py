"""Tests for bpy_gen.py — Blender Python script generation.

Tests verify that generated scripts are syntactically valid Python,
especially with Windows-style paths that could trigger escape errors.
"""

from typing import Any, Dict

import pytest

from cli_anything.blender.utils.bpy_gen import generate_full_script


def _minimal_project() -> Dict[str, Any]:
    """Return a minimal project dict sufficient for script generation."""
    return {
        "version": "1.0",
        "scene": {
            "unit_system": "METRIC",
            "unit_scale": 1.0,
            "frame_start": 1,
            "frame_end": 250,
            "frame_current": 1,
            "fps": 24,
        },
        "render": {
            "engine": "CYCLES",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "resolution_percentage": 100,
            "samples": 128,
            "use_denoising": True,
            "output_format": "PNG",
        },
        "objects": [],
        "cameras": [],
        "lights": [],
        "materials": [],
        "world": {
            "color": [0.0, 0.0, 0.0],
            "use_hdri": False,
        },
        "keyframes": [],
    }


class TestGeneratedScriptSyntax:
    """Generated scripts must produce valid Python, even on Windows."""

    @pytest.mark.parametrize("output_path", [
        r"C:\Users\user\Desktop\render.png",
        r"D:\data\scene\output.png",
        r"\\server\share\render_0001.png",
        r"C:\Users\test\AppData\Local\file.png",
        "/home/user/render.png",
        "./relative/render.png",
    ])
    def test_windows_paths_produce_valid_python(self, output_path: str) -> None:
        """Windows-style backslash paths must not cause SyntaxError."""
        project = _minimal_project()
        script = generate_full_script(project, output_path)

        # compile() will raise SyntaxError if the script is invalid
        try:
            compile(script, "<test>", "exec")
        except SyntaxError as e:
            pytest.fail(
                f"Generated script has SyntaxError with path {output_path!r}:\n"
                f"{e}\n"
                f"--- script excerpt around error ---\n"
                f"{_excerpt(e, script)}"
            )

    def test_trailing_backslash_path(self) -> None:
        """Paths ending in backslash must be handled correctly (raw-string edge case)."""
        project = _minimal_project()
        script = generate_full_script(project, "C:\\Users\\user\\output_dir\\")
        compile(script, "<test>", "exec")

    def test_path_with_quotes(self) -> None:
        """Paths containing single quotes must not break generated script."""
        project = _minimal_project()
        script = generate_full_script(project, "C:\\Users\\o'brien\\output.png")
        compile(script, "<test>", "exec")

    def test_hdri_path_with_windows_slashes(self) -> None:
        """HDRI paths on Windows must not cause SyntaxError."""
        project = _minimal_project()
        project["world"]["use_hdri"] = True
        project["world"]["hdri_path"] = r"C:\Users\user\assets\env.hdr"
        project["world"]["hdri_strength"] = 1.0
        script = generate_full_script(project, r"C:\Users\user\output.png")
        compile(script, "<test>", "exec")

    def test_print_statement_with_windows_path(self) -> None:
        """The 'Render complete:' print line must not cause Unicode escape error."""
        project = _minimal_project()
        script = generate_full_script(project, r"C:\Users\u\output.png")
        compile(script, "<test>", "exec")
        assert "Render complete:" in script

    def test_normal_unix_paths_still_work(self) -> None:
        """Existing Unix path behavior must not regress."""
        project = _minimal_project()
        script = generate_full_script(project, "/tmp/render.png")
        compile(script, "<test>", "exec")


def _excerpt(err: SyntaxError, script: str) -> str:
    """Return a short excerpt of the script around the syntax error."""
    lines = script.splitlines()
    lineno = err.lineno or 1
    start = max(0, lineno - 3)
    end = min(len(lines), lineno + 2)
    excerpt = lines[start:end]
    result = f"    Line {start + 1} to {end}:\n"
    for i, line in enumerate(excerpt, start=start + 1):
        marker = " >>> " if i == lineno else "     "
        result += f"{marker}{i}: {line}\n"
    return result
