"""Unit tests for Universal Image Converter CLI core modules.

Reference: gimp/agent-harness/cli_anything/gimp/tests/test_core.py (test structure)
"""

import json
import os
import sys
import tempfile
import pytest
from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.universal_image_converter.core.formats import (
    list_input_formats,
    list_output_formats,
    get_output_format_info,
    list_quality_presets,
    get_quality_preset,
    INPUT_FORMATS,
    OUTPUT_FORMATS,
    QUALITY_PRESETS,
)
from cli_anything.universal_image_converter.core.converter import (
    probe_image,
    convert_image,
    batch_convert,
)
from cli_anything.universal_image_converter import uic_cli


# ── Format Tests ─────────────────────────────────────────────────

class TestFormats:
    def test_list_input_formats(self):
        fmts = list_input_formats()
        assert len(fmts) > 0
        names = [f["format"] for f in fmts]
        assert "png" in names
        assert "jpg" in names
        assert "webp" in names

    def test_list_output_formats(self):
        fmts = list_output_formats()
        assert len(fmts) > 0
        names = [f["format"] for f in fmts]
        assert "png" in names
        assert "jpg" in names
        assert "webp" in names

    def test_get_output_format_info_valid(self):
        info = get_output_format_info("png")
        assert info["format"] == "png"
        assert info["extension"] == ".png"
        assert info["pillow_format"] == "PNG"

    def test_get_output_format_info_with_dot_prefix(self):
        info = get_output_format_info(".jpg")
        assert info["format"] == "jpg"
        assert info["pillow_format"] == "JPEG"

    def test_get_output_format_info_invalid(self):
        with pytest.raises(ValueError, match="Unsupported output format"):
            get_output_format_info("invalid_format")

    def test_list_quality_presets(self):
        presets = list_quality_presets()
        assert len(presets) > 0
        names = [p["name"] for p in presets]
        assert "lossless" in names
        assert "high" in names

    def test_get_quality_preset_valid(self):
        preset = get_quality_preset("high")
        assert "quality" in preset

    def test_get_quality_preset_invalid(self):
        with pytest.raises(ValueError, match="Unknown quality preset"):
            get_quality_preset("invalid")


# ── Converter Tests ──────────────────────────────────────────────

class TestConverter:
    def _make_test_image(self, tmp_dir, name="test.png", fmt="PNG",
                         size=(100, 100), color="red"):
        from PIL import Image
        img = Image.new("RGB", size, color)
        path = os.path.join(tmp_dir, name)
        img.save(path, fmt)
        return path

    def test_probe_image(self, tmp_path):
        path = self._make_test_image(str(tmp_path))
        info = probe_image(path)
        assert info["width"] == 100
        assert info["height"] == 100
        assert info["format"] == "PNG"
        assert info["mode"] == "RGB"
        assert "file_size" in info

    def test_probe_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            probe_image("/nonexistent/image.png")

    def test_convert_png_to_jpeg(self, tmp_path):
        d = str(tmp_path)
        inp = self._make_test_image(d, "input.png")
        out = os.path.join(d, "output.jpg")
        result = convert_image(inp, out, "jpg")
        assert os.path.exists(out)
        assert result["output_format"] == "JPEG"
        assert result["input_format"] == "PNG"

    def test_convert_with_resize(self, tmp_path):
        d = str(tmp_path)
        inp = self._make_test_image(d, "input.png", size=(200, 100))
        out = os.path.join(d, "output.png")
        result = convert_image(inp, out, "png", width=100)
        assert os.path.exists(out)
        assert result["resized"] is True

    def test_convert_with_quality(self, tmp_path):
        d = str(tmp_path)
        inp = self._make_test_image(d, "input.png")
        out = os.path.join(d, "output.jpg")
        result = convert_image(inp, out, "jpg", quality="low")
        assert os.path.exists(out)
        assert result["output_format"] == "JPEG"

    def test_convert_overwrite_protection(self, tmp_path):
        d = str(tmp_path)
        inp = self._make_test_image(d, "input.png")
        out = os.path.join(d, "output.png")
        convert_image(inp, out, "png", overwrite=True)
        with pytest.raises(FileExistsError):
            convert_image(inp, out, "png", overwrite=False)

    def test_convert_nonexistent_input(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            convert_image("/nonexistent/in.png", os.path.join(str(tmp_path), "out.png"), "png")

    def test_convert_invalid_format(self, tmp_path):
        d = str(tmp_path)
        inp = self._make_test_image(d, "input.png")
        out = os.path.join(d, "output.xyz")
        with pytest.raises(ValueError, match="Unsupported output format"):
            convert_image(inp, out, "xyz")

    def test_batch_convert(self, tmp_path):
        d = str(tmp_path)
        out_dir = os.path.join(d, "converted")
        paths = [
            self._make_test_image(d, "img1.png"),
            self._make_test_image(d, "img2.png"),
        ]
        result = batch_convert(paths, out_dir, "jpg", overwrite=True)
        assert result["succeeded"] == 2
        assert result["failed"] == 0
        assert os.path.exists(os.path.join(out_dir, "img1.jpg"))
        assert os.path.exists(os.path.join(out_dir, "img2.jpg"))

    def test_batch_convert_with_prefix_suffix(self, tmp_path):
        d = str(tmp_path)
        out_dir = os.path.join(d, "out")
        path = self._make_test_image(d, "photo.png")
        result = batch_convert([path], out_dir, "jpg", prefix="thumb_", suffix="_v2", overwrite=True)
        assert result["succeeded"] == 1
        assert os.path.exists(os.path.join(out_dir, "thumb_photo_v2.jpg"))


# ── CLI Tests ────────────────────────────────────────────────────

class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["--help"])
        assert result.exit_code == 0
        assert "Universal Image Converter" in result.stdout

    def test_formats_command(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["formats"])
        assert result.exit_code == 0
        assert "png" in result.stdout

    def test_formats_input(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["formats", "--type", "input"])
        assert result.exit_code == 0
        assert "png" in result.stdout

    def test_format_info(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["format-info", "png"])
        assert result.exit_code == 0
        assert "PNG" in result.stdout

    def test_quality_presets(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["quality-presets"])
        assert result.exit_code == 0
        assert "lossless" in result.stdout

    def test_info_nonexistent(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["info", "/nonexistent/file.png"])
        assert result.exit_code != 0

    def test_convert_help(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.stdout

    def test_convert_json_output(self, tmp_path):
        d = str(tmp_path)
        from PIL import Image
        img = Image.new("RGB", (50, 50), "blue")
        inp = os.path.join(d, "test.png")
        img.save(inp)
        out = os.path.join(d, "out.jpg")

        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, [
            "--json", "convert", "-i", inp, "-o", out, "-f", "jpg", "--overwrite",
        ])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["output_format"] == "JPEG"

    def test_resize_help(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["resize", "--help"])
        assert result.exit_code == 0
        assert "--width" in result.stdout

    def test_convert_no_input(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["convert", "-o", "/tmp/out", "-f", "png"])
        assert result.exit_code != 0

    def test_convert_invalid_format(self):
        runner = CliRunner()
        result = runner.invoke(uic_cli.cli, ["convert", "-i", "/tmp/test.png", "-o", "/tmp/out", "-f", "xyz"])
        assert result.exit_code != 0
