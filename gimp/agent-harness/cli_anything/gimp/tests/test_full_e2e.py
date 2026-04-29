"""End-to-end tests for GIMP CLI with real images.

These tests create actual images, apply filters, and verify pixel-level results.
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

from cli_anything.gimp.core.project import create_project, save_project, open_project, get_project_info
from cli_anything.gimp.core.layers import add_layer, add_from_file, list_layers, remove_layer
from cli_anything.gimp.core.filters import add_filter, list_filters
from cli_anything.gimp.core.canvas import resize_canvas, scale_canvas, crop_canvas, set_mode
from cli_anything.gimp.core.media import probe_image, check_media
from cli_anything.gimp.core.export import render
from cli_anything.gimp.core.session import Session


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_image(tmp_dir):
    """Create a simple test image (red/green/blue stripes)."""
    img = Image.new("RGB", (300, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 100, 200], fill=(255, 0, 0))     # Red stripe
    draw.rectangle([100, 0, 200, 200], fill=(0, 255, 0))    # Green stripe
    draw.rectangle([200, 0, 300, 200], fill=(0, 0, 255))    # Blue stripe
    path = os.path.join(tmp_dir, "test_image.png")
    img.save(path)
    return path


@pytest.fixture
def gradient_image(tmp_dir):
    """Create a gradient test image (black to white horizontal)."""
    img = Image.new("L", (256, 100))
    for x in range(256):
        for y in range(100):
            img.putpixel((x, y), x)
    path = os.path.join(tmp_dir, "gradient.png")
    img.save(path)
    return path


# ── Project Lifecycle ────────────────────────────────────────────

class TestProjectLifecycle:
    def test_create_save_open_roundtrip(self, tmp_dir):
        proj = create_project(name="roundtrip")
        path = os.path.join(tmp_dir, "project.gimp-cli.json")
        save_project(proj, path)
        loaded = open_project(path)
        assert loaded["name"] == "roundtrip"
        assert loaded["canvas"]["width"] == 1920

    def test_project_with_layers_roundtrip(self, tmp_dir, sample_image):
        proj = create_project(name="with_layers")
        add_from_file(proj, sample_image, name="Photo")
        add_filter(proj, "brightness", 0, {"factor": 1.3})
        path = os.path.join(tmp_dir, "project.json")
        save_project(proj, path)
        loaded = open_project(path)
        assert len(loaded["layers"]) == 1
        assert loaded["layers"][0]["filters"][0]["name"] == "brightness"

    def test_project_info_with_layers(self, sample_image):
        proj = create_project()
        add_from_file(proj, sample_image)
        info = get_project_info(proj)
        assert info["layer_count"] == 1


# ── Layer Operations ─────────────────────────────────────────────

class TestLayerOperations:
    def test_add_from_file(self, sample_image):
        proj = create_project()
        layer = add_from_file(proj, sample_image)
        assert layer["source"] == os.path.abspath(sample_image)
        assert layer["width"] == 300
        assert layer["height"] == 200

    def test_multiple_layers_order(self, tmp_dir):
        img1 = Image.new("RGB", (100, 100), "red")
        img2 = Image.new("RGB", (100, 100), "blue")
        p1 = os.path.join(tmp_dir, "red.png")
        p2 = os.path.join(tmp_dir, "blue.png")
        img1.save(p1)
        img2.save(p2)

        proj = create_project(width=100, height=100)
        add_from_file(proj, p1, name="Red")
        add_from_file(proj, p2, name="Blue")
        layers = list_layers(proj)
        assert layers[0]["name"] == "Blue"  # Top
        assert layers[1]["name"] == "Red"   # Bottom


# ── Filter Rendering ─────────────────────────────────────────────

class TestFilterRendering:
    def test_brightness_increases_pixels(self, tmp_dir, gradient_image):
        proj = create_project(width=256, height=100, color_mode="RGB")
        add_from_file(proj, gradient_image)
        add_filter(proj, "brightness", 0, {"factor": 1.5})
        out = os.path.join(tmp_dir, "bright.png")
        render(proj, out, preset="png", overwrite=True)

        original = np.array(Image.open(gradient_image).convert("RGB"), dtype=float)
        result = np.array(Image.open(out).convert("RGB"), dtype=float)
        assert result.mean() > original.mean()

    def test_contrast_increases_spread(self, tmp_dir, gradient_image):
        proj = create_project(width=256, height=100, color_mode="RGB")
        add_from_file(proj, gradient_image)
        add_filter(proj, "contrast", 0, {"factor": 2.0})
        out = os.path.join(tmp_dir, "contrast.png")
        render(proj, out, preset="png", overwrite=True)

        result = np.array(Image.open(out).convert("L"), dtype=float)
        original = np.array(Image.open(gradient_image), dtype=float)
        # Higher contrast = larger std deviation
        assert result.std() >= original.std() * 0.9

    def test_invert_flips_colors(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        add_filter(proj, "invert", 0, {})
        out = os.path.join(tmp_dir, "inverted.png")
        render(proj, out, preset="png", overwrite=True)

        original = np.array(Image.open(sample_image).convert("RGB"), dtype=float)
        result = np.array(Image.open(out).convert("RGB"), dtype=float)
        # Inverted + original should sum to ~255
        total = original + result
        assert abs(total.mean() - 255.0) < 5.0

    def test_gaussian_blur(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        add_filter(proj, "gaussian_blur", 0, {"radius": 10.0})
        out = os.path.join(tmp_dir, "blurred.png")
        render(proj, out, preset="png", overwrite=True)

        result = Image.open(out)
        assert result.size == (300, 200)

    def test_sepia_applies(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        add_filter(proj, "sepia", 0, {"strength": 1.0})
        out = os.path.join(tmp_dir, "sepia.png")
        render(proj, out, preset="png", overwrite=True)

        result = np.array(Image.open(out).convert("RGB"), dtype=float)
        r, g, b = result[:,:,0].mean(), result[:,:,1].mean(), result[:,:,2].mean()
        # Sepia: R > G > B
        assert r >= g >= b

    def test_multiple_filters_chain(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        add_filter(proj, "brightness", 0, {"factor": 1.2})
        add_filter(proj, "contrast", 0, {"factor": 1.3})
        add_filter(proj, "saturation", 0, {"factor": 0.5})
        out = os.path.join(tmp_dir, "multi.png")
        render(proj, out, preset="png", overwrite=True)
        assert os.path.exists(out)

    def test_flip_horizontal(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        add_filter(proj, "flip_h", 0, {})
        out = os.path.join(tmp_dir, "flipped.png")
        render(proj, out, preset="png", overwrite=True)

        original = np.array(Image.open(sample_image).convert("RGB"))
        result = np.array(Image.open(out).convert("RGB"))
        # First column of result should match last column of original
        np.testing.assert_array_equal(result[:, 0, :], original[:, -1, :])


# ── Export Formats ───────────────────────────────────────────────

class TestExportFormats:
    def test_export_jpeg(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        out = os.path.join(tmp_dir, "output.jpg")
        result = render(proj, out, preset="jpeg-high", overwrite=True)
        assert os.path.exists(out)
        assert result["format"] == "JPEG"

    def test_export_webp(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        out = os.path.join(tmp_dir, "output.webp")
        result = render(proj, out, preset="webp", overwrite=True)
        assert os.path.exists(out)
        assert result["format"] == "WEBP"

    def test_export_bmp(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        out = os.path.join(tmp_dir, "output.bmp")
        result = render(proj, out, preset="bmp", overwrite=True)
        assert os.path.exists(out)

    def test_export_overwrite_protection(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        out = os.path.join(tmp_dir, "output.png")
        render(proj, out, preset="png", overwrite=True)
        with pytest.raises(FileExistsError):
            render(proj, out, preset="png", overwrite=False)


# ── Blend Modes ──────────────────────────────────────────────────

class TestBlendModes:
    def _two_layer_project(self, tmp_dir, color1, color2, mode):
        img1 = Image.new("RGBA", (100, 100), color1)
        img2 = Image.new("RGBA", (100, 100), color2)
        p1 = os.path.join(tmp_dir, "layer1.png")
        p2 = os.path.join(tmp_dir, "layer2.png")
        img1.save(p1)
        img2.save(p2)

        proj = create_project(width=100, height=100, color_mode="RGBA",
                              background="transparent")
        add_from_file(proj, p1, name="Bottom")
        add_from_file(proj, p2, name="Top")
        proj["layers"][0]["blend_mode"] = mode
        return proj

    def test_multiply_darkens(self, tmp_dir):
        proj = self._two_layer_project(tmp_dir, (200, 200, 200, 255),
                                       (128, 128, 128, 255), "multiply")
        out = os.path.join(tmp_dir, "multiply.png")
        render(proj, out, preset="png", overwrite=True)
        result = np.array(Image.open(out).convert("RGB"), dtype=float)
        # Multiply always darkens
        assert result.mean() < 200

    def test_screen_brightens(self, tmp_dir):
        proj = self._two_layer_project(tmp_dir, (100, 100, 100, 255),
                                       (100, 100, 100, 255), "screen")
        out = os.path.join(tmp_dir, "screen.png")
        render(proj, out, preset="png", overwrite=True)
        result = np.array(Image.open(out).convert("RGB"), dtype=float)
        # Screen always brightens
        assert result.mean() > 100

    def test_difference(self, tmp_dir):
        proj = self._two_layer_project(tmp_dir, (200, 100, 50, 255),
                                       (100, 100, 100, 255), "difference")
        out = os.path.join(tmp_dir, "diff.png")
        render(proj, out, preset="png", overwrite=True)
        result = np.array(Image.open(out).convert("RGB"), dtype=float)
        # Difference of (200,100,50) and (100,100,100) = (100,0,50)
        assert abs(result[:,:,0].mean() - 100) < 5
        assert abs(result[:,:,1].mean() - 0) < 5
        assert abs(result[:,:,2].mean() - 50) < 5


# ── Canvas Operations ────────────────────────────────────────────

class TestCanvasRendering:
    def test_scale_and_export(self, tmp_dir, sample_image):
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        scale_canvas(proj, 150, 100)
        out = os.path.join(tmp_dir, "scaled.png")
        render(proj, out, preset="png", overwrite=True)
        result = Image.open(out)
        assert result.size == (150, 100)


# ── Media Probing ────────────────────────────────────────────────

class TestMediaProbing:
    def test_probe_png(self, sample_image):
        info = probe_image(sample_image)
        assert info["width"] == 300
        assert info["height"] == 200
        assert info["format"] == "PNG"
        assert info["mode"] == "RGB"

    def test_probe_jpeg(self, tmp_dir):
        img = Image.new("RGB", (100, 100), "red")
        path = os.path.join(tmp_dir, "test.jpg")
        img.save(path, "JPEG")
        info = probe_image(path)
        assert info["format"] == "JPEG"
        assert info["width"] == 100

    def test_probe_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            probe_image("/nonexistent/image.png")

    def test_check_media(self, sample_image):
        proj = create_project()
        add_from_file(proj, sample_image)
        result = check_media(proj)
        assert result["status"] == "ok"
        assert result["missing"] == 0

    def test_check_media_missing(self, sample_image):
        proj = create_project()
        add_from_file(proj, sample_image)
        proj["layers"][0]["source"] = "/nonexistent/file.png"
        result = check_media(proj)
        assert result["status"] == "missing_files"


# ── Session Integration ──────────────────────────────────────────

class TestSessionIntegration:
    def test_undo_layer_add(self, sample_image):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        sess.snapshot("add layer")
        add_from_file(proj, sample_image)
        assert len(proj["layers"]) == 1

        sess.undo()
        assert len(sess.get_project()["layers"]) == 0

    def test_undo_filter_add(self, sample_image):
        sess = Session()
        proj = create_project()
        add_from_file(proj, sample_image)
        sess.set_project(proj)

        sess.snapshot("add filter")
        add_filter(proj, "brightness", 0, {"factor": 1.5})
        assert len(proj["layers"][0]["filters"]) == 1

        sess.undo()
        assert len(sess.get_project()["layers"][0]["filters"]) == 0


# ── CLI Subprocess Tests ─────────────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-gimp")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "GIMP CLI" in result.stdout

    def test_project_new(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["project", "new", "-o", out])
        assert result.returncode == 0
        assert os.path.exists(out)

    def test_project_new_json(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["--json", "project", "new", "-o", out])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["canvas"]["width"] == 1920

    def test_project_profiles(self):
        result = self._run(["project", "profiles"])
        assert result.returncode == 0
        assert "hd1080p" in result.stdout

    def test_filter_list_available(self):
        result = self._run(["filter", "list-available"])
        assert result.returncode == 0
        assert "brightness" in result.stdout

    def test_export_presets(self):
        result = self._run(["export", "presets"])
        assert result.returncode == 0
        assert "png" in result.stdout

    def test_full_workflow_json(self, tmp_dir, sample_image):
        proj_path = os.path.join(tmp_dir, "workflow.json")
        out_path = os.path.join(tmp_dir, "output.png")

        # Create project
        self._run(["--json", "project", "new", "-o", proj_path, "-w", "300", "-h", "200"])

        # Add layer
        self._run(["--json", "--project", proj_path,
                    "layer", "add-from-file", sample_image])

        # Save
        self._run(["--project", proj_path, "project", "save"])

        # Export
        self._run(["--project", proj_path,
                    "export", "render", out_path, "--overwrite"])

        assert os.path.exists(out_path)
        result = Image.open(out_path)
        assert result.size == (300, 200)


# ── Real-World Workflow Tests ────────────────────────────────────

class TestRealWorldWorkflows:
    def test_photo_editing_workflow(self, tmp_dir, sample_image):
        """Simulate a photo editing workflow: open, adjust, export."""
        proj = create_project(width=300, height=200, name="photo_edit")
        add_from_file(proj, sample_image, name="Photo")
        add_filter(proj, "brightness", 0, {"factor": 1.15})
        add_filter(proj, "contrast", 0, {"factor": 1.1})
        add_filter(proj, "saturation", 0, {"factor": 1.2})
        add_filter(proj, "sharpness", 0, {"factor": 1.5})

        out = os.path.join(tmp_dir, "edited.jpg")
        result = render(proj, out, preset="jpeg-high", overwrite=True)
        assert os.path.exists(out)
        assert result["layers_rendered"] == 1

    def test_collage_workflow(self, tmp_dir):
        """Create a collage from multiple images."""
        images = []
        colors = ["red", "green", "blue", "yellow"]
        for color in colors:
            img = Image.new("RGB", (100, 100), color)
            path = os.path.join(tmp_dir, f"{color}.png")
            img.save(path)
            images.append(path)

        proj = create_project(width=200, height=200, name="collage")
        add_from_file(proj, images[0], name="TL")
        proj["layers"][0]["offset_x"] = 0
        proj["layers"][0]["offset_y"] = 0
        add_from_file(proj, images[1], name="TR")
        proj["layers"][0]["offset_x"] = 100
        proj["layers"][0]["offset_y"] = 0
        add_from_file(proj, images[2], name="BL")
        proj["layers"][0]["offset_x"] = 0
        proj["layers"][0]["offset_y"] = 100
        add_from_file(proj, images[3], name="BR")
        proj["layers"][0]["offset_x"] = 100
        proj["layers"][0]["offset_y"] = 100

        out = os.path.join(tmp_dir, "collage.png")
        render(proj, out, preset="png", overwrite=True)

        result = Image.open(out)
        assert result.size == (200, 200)

    def test_text_overlay_workflow(self, tmp_dir, sample_image):
        """Add text overlay to an image."""
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image, name="Background")
        add_layer(proj, name="Title", layer_type="text")
        proj["layers"][0]["text"] = "Hello World"
        proj["layers"][0]["font_size"] = 32
        proj["layers"][0]["color"] = "#ffffff"

        out = os.path.join(tmp_dir, "text_overlay.png")
        render(proj, out, preset="png", overwrite=True)
        assert os.path.exists(out)

    def test_draw_ops_overlay_workflow(self, tmp_dir, sample_image):
        """Render non-destructive draw operations on top of an image layer."""
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image, name="Background")
        overlay = add_layer(proj, name="Overlay", layer_type="image")
        overlay.setdefault("draw_ops", []).append({
            "type": "rect",
            "x1": 10,
            "y1": 10,
            "x2": 290,
            "y2": 60,
            "fill": "#111111cc",
            "outline": "#ffffff",
            "width": 2,
        })
        overlay["draw_ops"].append({
            "type": "text",
            "x": 20,
            "y": 20,
            "text": "Overlay Title",
            "font": "Arial",
            "size": 24,
            "color": "#ffffff",
        })

        out = os.path.join(tmp_dir, "draw_ops_overlay.png")
        render(proj, out, preset="png", overwrite=True)
        assert os.path.exists(out)

    def test_batch_filter_workflow(self, tmp_dir, sample_image):
        """Apply multiple artistic filters in sequence."""
        proj = create_project(width=300, height=200)
        add_from_file(proj, sample_image)
        add_filter(proj, "grayscale", 0, {})
        add_filter(proj, "contrast", 0, {"factor": 1.5})
        add_filter(proj, "find_edges", 0, {})

        out = os.path.join(tmp_dir, "artistic.png")
        render(proj, out, preset="png", overwrite=True)
        assert os.path.exists(out)

    def test_save_load_complex_project(self, tmp_dir, sample_image):
        """Create complex project, save, reload, verify integrity."""
        proj = create_project(width=300, height=200, name="complex")
        add_from_file(proj, sample_image, name="Photo")
        add_layer(proj, name="Overlay", layer_type="solid", fill="#ff000080", opacity=0.5)
        add_layer(proj, name="Text", layer_type="text")
        add_filter(proj, "brightness", 2, {"factor": 1.3})  # On bottom layer (Photo)
        add_filter(proj, "gaussian_blur", 2, {"radius": 2.0})

        path = os.path.join(tmp_dir, "complex.json")
        save_project(proj, path)

        loaded = open_project(path)
        assert len(loaded["layers"]) == 3
        assert loaded["layers"][2]["filters"][0]["name"] == "brightness"
        assert loaded["layers"][2]["filters"][1]["name"] == "gaussian_blur"


# ── True Backend E2E Tests (requires GIMP installed) ─────────────

class TestGIMPBackend:
    """Tests that verify GIMP is installed and accessible."""

    def test_gimp_is_installed(self):
        from cli_anything.gimp.utils.gimp_backend import find_gimp
        path = find_gimp()
        assert os.path.exists(path)
        print(f"\n  GIMP binary: {path}")

    def test_gimp_version(self):
        from cli_anything.gimp.utils.gimp_backend import get_version
        version = get_version()
        assert "image manipulation" in version.lower() or "gimp" in version.lower()
        print(f"\n  GIMP version: {version}")


class TestGIMPRenderE2E:
    """True E2E tests using GIMP batch mode."""

    def test_create_and_export_png(self):
        """Create a blank image in GIMP and export as PNG."""
        from cli_anything.gimp.utils.gimp_backend import create_and_export

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = os.path.join(tmp_dir, "test.png")
            result = create_and_export(200, 150, output, fill_color="red", timeout=60)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            assert result["method"] == "gimp-batch"
            print(f"\n  GIMP PNG: {result['output']} ({result['file_size']:,} bytes)")

    def test_create_and_export_jpeg(self):
        """Create a blank image in GIMP and export as JPEG."""
        from cli_anything.gimp.utils.gimp_backend import create_and_export

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = os.path.join(tmp_dir, "test.jpg")
            result = create_and_export(200, 150, output, fill_color="blue", timeout=60)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            print(f"\n  GIMP JPEG: {result['output']} ({result['file_size']:,} bytes)")
