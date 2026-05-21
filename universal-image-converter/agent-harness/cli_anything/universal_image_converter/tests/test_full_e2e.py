"""End-to-end tests for Universal Image Converter CLI with real images.

Reference: gimp/agent-harness/cli_anything/gimp/tests/test_full_e2e.py (E2E test structure)
"""

import json
import os
import sys
import tempfile
import subprocess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PIL import Image, ImageDraw
import numpy as np

from cli_anything.universal_image_converter.core.converter import (
    probe_image,
    convert_image,
    batch_convert,
)
from cli_anything.universal_image_converter.core.formats import (
    list_output_formats,
    get_output_format_info,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_png(tmp_dir):
    """A simple RGB PNG test image."""
    img = Image.new("RGB", (200, 150), "blue")
    path = os.path.join(tmp_dir, "sample.png")
    img.save(path)
    return path


@pytest.fixture
def sample_rgba_png(tmp_dir):
    """A RGBA PNG test image with transparency."""
    img = Image.new("RGBA", (200, 150), (255, 0, 0, 128))
    path = os.path.join(tmp_dir, "sample_rgba.png")
    img.save(path)
    return path


@pytest.fixture
def multi_images(tmp_dir):
    """Multiple test images for batch operations."""
    paths = []
    for i, color in enumerate(["red", "green", "blue"]):
        img = Image.new("RGB", (100, 100), color)
        path = os.path.join(tmp_dir, f"img_{i}.png")
        img.save(path)
        paths.append(path)
    return paths


# ── Format Conversion Tests ──────────────────────────────────────

class TestFormatConversion:
    def test_png_to_jpeg(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "output.jpg")
        result = convert_image(sample_png, out, "jpg", overwrite=True)
        assert os.path.exists(out)
        assert result["output_format"] == "JPEG"
        img = Image.open(out)
        assert img.format == "JPEG"
        assert img.size == (200, 150)

    def test_png_to_webp(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "output.webp")
        result = convert_image(sample_png, out, "webp", overwrite=True)
        assert os.path.exists(out)
        assert result["output_format"] == "WEBP"

    def test_png_to_bmp(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "output.bmp")
        result = convert_image(sample_png, out, "bmp", overwrite=True)
        assert os.path.exists(out)
        assert result["output_format"] == "BMP"

    def test_png_to_tiff(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "output.tiff")
        result = convert_image(sample_png, out, "tiff", overwrite=True)
        assert os.path.exists(out)
        assert result["output_format"] == "TIFF"

    def test_rgba_to_jpeg_flattens_alpha(self, tmp_dir, sample_rgba_png):
        """RGBA -> JPEG should flatten alpha onto white background."""
        out = os.path.join(tmp_dir, "flattened.jpg")
        result = convert_image(sample_rgba_png, out, "jpg", overwrite=True)
        assert os.path.exists(out)
        img = Image.open(out)
        assert img.mode == "RGB"


# ── Resize Conversion Tests ──────────────────────────────────────

class TestResizeConversion:
    def test_resize_width_only(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "resized.png")
        result = convert_image(sample_png, out, "png", width=100, overwrite=True)
        assert result["resized"] is True
        img = Image.open(out)
        assert img.width == 100
        assert img.height == 75  # aspect ratio preserved

    def test_resize_height_only(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "resized.png")
        result = convert_image(sample_png, out, "png", height=75, overwrite=True)
        img = Image.open(out)
        assert img.height == 75
        assert img.width == 100

    def test_resize_exact(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "exact.png")
        result = convert_image(sample_png, out, "png", width=80, height=60,
                               keep_aspect=False, overwrite=True)
        img = Image.open(out)
        assert img.size == (80, 60)


# ── Quality Preset Tests ─────────────────────────────────────────

class TestQualityPresets:
    def test_lossless_png(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "lossless.png")
        convert_image(sample_png, out, "png", quality="lossless", overwrite=True)
        assert os.path.exists(out)

    def test_low_quality_jpeg(self, tmp_dir, sample_png):
        out_high = os.path.join(tmp_dir, "high.jpg")
        out_low = os.path.join(tmp_dir, "low.jpg")
        convert_image(sample_png, out_high, "jpg", quality="high", overwrite=True)
        convert_image(sample_png, out_low, "jpg", quality="low", overwrite=True)
        # Low quality should produce smaller file
        assert os.path.getsize(out_low) <= os.path.getsize(out_high)


# ── Probe Tests ─────────────────────────────────────────────────

class TestProbeImage:
    def test_probe_png(self, sample_png):
        info = probe_image(sample_png)
        assert info["width"] == 200
        assert info["height"] == 150
        assert info["format"] == "PNG"
        assert "file_size_human" in info

    def test_probe_jpeg(self, tmp_dir):
        img = Image.new("RGB", (50, 50), "red")
        path = os.path.join(tmp_dir, "test.jpg")
        img.save(path, "JPEG")
        info = probe_image(path)
        assert info["format"] == "JPEG"
        assert info["width"] == 50


# ── Batch Conversion Tests ───────────────────────────────────────

class TestBatchConversion:
    def test_batch_convert_all(self, tmp_dir, multi_images):
        out_dir = os.path.join(tmp_dir, "batch_out")
        result = batch_convert(multi_images, out_dir, "jpg", overwrite=True)
        assert result["total"] == 3
        assert result["succeeded"] == 3
        for i in range(3):
            assert os.path.exists(os.path.join(out_dir, f"img_{i}.jpg"))

    def test_batch_skip_existing(self, tmp_dir, multi_images):
        out_dir = os.path.join(tmp_dir, "skip_out")
        # First pass
        batch_convert(multi_images, out_dir, "jpg", overwrite=True)
        # Second pass without overwrite
        result = batch_convert(multi_images, out_dir, "jpg", overwrite=False)
        assert result["skipped"] == 3

    def test_batch_with_prefix_suffix(self, tmp_dir, multi_images):
        out_dir = os.path.join(tmp_dir, "named_out")
        result = batch_convert(
            multi_images, out_dir, "png",
            prefix="thumb_", suffix="_sm",
            overwrite=True,
        )
        assert result["succeeded"] == 3
        assert os.path.exists(os.path.join(out_dir, "thumb_img_0_sm.png"))


# ── CLI Subprocess Tests ─────────────────────────────────────────

def _resolve_cli(name):
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH.")
    module = "cli_anything.universal_image_converter.uic_cli"
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-universal-image-converter")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Universal Image Converter" in result.stdout

    def test_formats_json(self):
        result = self._run(["--json", "formats"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) > 0
        assert any(f["format"] == "png" for f in data)

    def test_convert_workflow(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "cli_out.jpg")
        result = self._run([
            "--json", "convert", "-i", sample_png, "-o", out, "-f", "jpg", "--overwrite",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["output_format"] == "JPEG"
        assert os.path.exists(out)

    def test_convert_with_resize(self, tmp_dir, sample_png):
        out = os.path.join(tmp_dir, "resized.jpg")
        result = self._run([
            "--json", "convert", "-i", sample_png, "-o", out, "-f", "jpg",
            "-w", "100", "--overwrite",
        ])
        assert result.returncode == 0
        img = Image.open(out)
        assert img.width == 100

    def test_error_missing_file(self):
        result = subprocess.run(
            self.CLI_BASE + ["convert", "-i", "/nonexistent/img.png", "-o", "/tmp/out", "-f", "png"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
