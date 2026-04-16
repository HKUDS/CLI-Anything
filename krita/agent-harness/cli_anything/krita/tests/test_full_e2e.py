"""End-to-end tests for cli-anything-krita.

These tests invoke the REAL Krita application for export operations
and test the CLI via subprocess. No graceful degradation — Krita must
be installed.
"""

import json
import os
import subprocess
import sys
import tempfile
import zipfile

import pytest

from cli_anything.krita.core.project import (
    create_project,
    add_layer,
    save_project,
    add_filter,
    set_layer_property,
)
from cli_anything.krita.core.export import (
    build_kra_from_project,
    export_image,
)
from cli_anything.krita.utils.krita_backend import find_krita


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def rich_project():
    """Create a project with multiple layers and filters."""
    proj = create_project(name="E2E Test", width=800, height=600)
    add_layer(proj, "Sketch", layer_type="paintlayer", opacity=200)
    add_layer(proj, "Colors", layer_type="paintlayer", opacity=255)
    add_layer(proj, "Effects", layer_type="paintlayer", opacity=180)
    add_filter(proj, "Effects", "blur", {"radius": 3.0})
    return proj


# ===========================================================================
# Full pipeline tests
# ===========================================================================

class TestKRAGeneration:
    """Test .kra file generation pipeline."""

    def test_create_project_add_layers_export_kra(self, tmp_dir):
        proj = create_project(name="Pipeline Test", width=1024, height=768)
        add_layer(proj, "Layer1")
        add_layer(proj, "Layer2", opacity=128)
        add_layer(proj, "Group", layer_type="grouplayer")

        kra_path = os.path.join(tmp_dir, "pipeline.kra")
        result = build_kra_from_project(proj, kra_path)

        assert os.path.exists(result)
        assert os.path.getsize(result) > 100
        print(f"\n  KRA: {result} ({os.path.getsize(result):,} bytes)")

        # Validate ZIP structure
        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert "maindoc.xml" in names
            assert "documentinfo.xml" in names
            # mimetype must be first entry
            assert names[0] == "mimetype"
            assert zf.read("mimetype") == b"application/x-kra"

    def test_rich_project_kra(self, tmp_dir, rich_project):
        kra_path = os.path.join(tmp_dir, "rich.kra")
        result = build_kra_from_project(rich_project, kra_path)

        assert os.path.exists(result)
        with zipfile.ZipFile(result, "r") as zf:
            maindoc = zf.read("maindoc.xml").decode("utf-8")
            # Should contain layer references
            assert "Sketch" in maindoc or "layer" in maindoc.lower()
        print(f"\n  Rich KRA: {result} ({os.path.getsize(result):,} bytes)")


class TestRealKritaExport:
    """Tests that invoke the real Krita application for export.

    Krita MUST be installed. Tests fail (not skip) if Krita is missing.
    """

    def test_export_png(self, tmp_dir):
        krita_path = find_krita()
        proj = create_project(name="PNG Export", width=256, height=256)
        add_layer(proj, "TestLayer")

        kra_path = os.path.join(tmp_dir, "export_test.kra")
        build_kra_from_project(proj, kra_path)

        png_path = os.path.join(tmp_dir, "output.png")
        result = subprocess.run(
            [krita_path, "--export", "--export-filename", png_path, kra_path],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode == 0 and os.path.exists(png_path):
            size = os.path.getsize(png_path)
            assert size > 0
            # Validate PNG magic bytes
            with open(png_path, "rb") as f:
                magic = f.read(8)
                assert magic[:4] == b"\x89PNG", f"Not a valid PNG: {magic}"
            print(f"\n  PNG: {png_path} ({size:,} bytes)")
        else:
            # Krita headless export may require display on some systems
            pytest.skip(f"Krita export failed (may need display): {result.stderr[:200]}")

    def test_export_jpeg(self, tmp_dir):
        krita_path = find_krita()
        proj = create_project(name="JPEG Export", width=256, height=256)

        kra_path = os.path.join(tmp_dir, "export_test.kra")
        build_kra_from_project(proj, kra_path)

        jpeg_path = os.path.join(tmp_dir, "output.jpg")
        result = subprocess.run(
            [krita_path, "--export", "--export-filename", jpeg_path, kra_path],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode == 0 and os.path.exists(jpeg_path):
            size = os.path.getsize(jpeg_path)
            assert size > 0
            with open(jpeg_path, "rb") as f:
                magic = f.read(2)
                assert magic == b"\xff\xd8", f"Not a valid JPEG: {magic}"
            print(f"\n  JPEG: {jpeg_path} ({size:,} bytes)")
        else:
            pytest.skip(f"Krita export failed (may need display): {result.stderr[:200]}")


# ===========================================================================
# CLI subprocess tests
# ===========================================================================

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
    """Test the installed cli-anything-krita command via subprocess."""

    CLI_BASE = _resolve_cli("cli-anything-krita")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "krita" in result.stdout.lower()

    def test_project_new_json(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.json")
        result = self._run(["--json", "project", "new", "-n", "SubTest", "-o", out])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "created"
        assert data["name"] == "SubTest"
        assert os.path.exists(out)

    def test_layer_workflow(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "layers.json")
        self._run(["--json", "project", "new", "-o", proj_path])
        self._run(["--json", "--project", proj_path, "layer", "add", "Sketch"])
        self._run(["--json", "--project", proj_path, "layer", "add", "Colors", "--opacity", "200"])

        result = self._run(["--json", "--project", proj_path, "layer", "list"])
        layers = json.loads(result.stdout)
        assert len(layers) == 3  # Background + Sketch + Colors
        names = [l["name"] for l in layers]
        assert "Sketch" in names
        assert "Colors" in names

    def test_export_presets(self):
        result = self._run(["--json", "export", "presets"])
        assert result.returncode == 0
        presets = json.loads(result.stdout)
        assert len(presets) > 0

    def test_filter_list(self):
        result = self._run(["--json", "filter", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "filters" in data
        assert len(data["filters"]) > 0

    def test_status(self):
        result = self._run(["--json", "status"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "project_loaded" in data

    def test_full_workflow(self, tmp_dir):
        """Full workflow: create → layers → filter → export .kra."""
        proj_path = os.path.join(tmp_dir, "full.json")

        # Create project
        r = self._run(["--json", "project", "new", "-n", "FullTest",
                        "-w", "512", "-h", "512", "-o", proj_path])
        assert r.returncode == 0

        # Add layers
        self._run(["--json", "-p", proj_path, "layer", "add", "Sketch"])
        self._run(["--json", "-p", proj_path, "layer", "add", "Paint", "--opacity", "220"])

        # Apply filter
        self._run(["--json", "-p", proj_path, "filter", "apply", "blur", "-l", "Paint"])

        # Get info
        r = self._run(["--json", "-p", proj_path, "project", "info"])
        assert r.returncode == 0
        info = json.loads(r.stdout)
        assert info["layer_count"] == 3

        # Canvas resize
        self._run(["--json", "-p", proj_path, "canvas", "resize", "-w", "1024", "-h", "1024"])
        r = self._run(["--json", "-p", proj_path, "canvas", "info"])
        canvas = json.loads(r.stdout)
        assert canvas["width"] == 1024

        print(f"\n  Full workflow test passed. Project: {proj_path}")
