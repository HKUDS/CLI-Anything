"""
End-to-end tests for RenderDoc CLI.

These tests require:
  1. RenderDoc installed with Python bindings accessible
  2. A .rdc capture file (set via RENDERDOC_TEST_CAPTURE env var)

Skip gracefully if either is unavailable.

Run with: pytest test_full_e2e.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from cli_anything.renderdoc.core.capture import open_capture
from cli_anything.renderdoc.core import preview as preview_mod

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HARNESS_ROOT = str(Path(__file__).resolve().parents[3])

TEST_CAPTURE = os.environ.get("RENDERDOC_TEST_CAPTURE", "")
HAS_CAPTURE = os.path.isfile(TEST_CAPTURE) if TEST_CAPTURE else False

try:
    import renderdoc as rd
    HAS_RD = True
except ImportError:
    HAS_RD = False

skip_no_rd = pytest.mark.skipif(not HAS_RD, reason="renderdoc module not available")
skip_no_cap = pytest.mark.skipif(not HAS_CAPTURE, reason="RENDERDOC_TEST_CAPTURE not set or file missing")


def _run_cli(*args, json_mode=True) -> dict | list | str:
    """Run CLI via module invocation and parse output."""
    cmd = [sys.executable, "-m", "cli_anything.renderdoc.renderdoc_cli"]
    if TEST_CAPTURE:
        cmd.extend(["--capture", TEST_CAPTURE])
    if json_mode:
        cmd.append("--json")
    cmd.extend(args)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=HARNESS_ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed: {result.stderr}\n{result.stdout}")

    if json_mode:
        return json.loads(result.stdout)
    return result.stdout


def _artifact_path(manifest, artifact_id: str) -> str:
    for artifact in manifest["artifacts"]:
        if artifact["artifact_id"] == artifact_id:
            return os.path.join(manifest["_bundle_dir"], artifact["path"])
    raise KeyError(f"Artifact not found: {artifact_id}")


# ===========================================================================
# E2E: Capture info
# ===========================================================================

@skip_no_rd
@skip_no_cap
class TestCaptureE2E:
    def test_capture_info(self):
        data = _run_cli("capture", "info")
        assert "path" in data
        assert "api" in data
        assert "sections" in data
        assert isinstance(data["sections"], list)

    def test_capture_thumb(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "thumb.png")
            data = _run_cli("capture", "thumb", "--output", output)
            # May fail if no thumbnail - that's ok
            if "error" not in data:
                assert os.path.isfile(output)


# ===========================================================================
# E2E: Actions
# ===========================================================================

@skip_no_rd
@skip_no_cap
class TestActionsE2E:
    def test_actions_list(self):
        data = _run_cli("actions", "list")
        assert isinstance(data, list)
        assert len(data) > 0
        assert "eventId" in data[0]

    def test_actions_summary(self):
        data = _run_cli("actions", "summary")
        assert "total_actions" in data
        assert data["total_actions"] > 0

    def test_actions_draws_only(self):
        data = _run_cli("actions", "list", "--draws-only")
        assert isinstance(data, list)
        for a in data:
            assert "Drawcall" in a["flags"]

    def test_actions_get(self):
        # First get list to find a valid eventId
        actions = _run_cli("actions", "list")
        if actions:
            eid = actions[0]["eventId"]
            data = _run_cli("actions", "get", str(eid))
            assert data["eventId"] == eid


# ===========================================================================
# E2E: Textures
# ===========================================================================

@skip_no_rd
@skip_no_cap
class TestTexturesE2E:
    def test_textures_list(self):
        data = _run_cli("textures", "list")
        assert isinstance(data, list)
        if len(data) > 0:
            assert "resourceId" in data[0]
            assert "width" in data[0]

    def test_textures_save(self):
        textures = _run_cli("textures", "list")
        if not textures:
            pytest.skip("No textures in capture")
        rid = textures[0]["resourceId"]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "tex.png")
            data = _run_cli("textures", "save", rid, "--output", output)
            if "error" not in data:
                assert os.path.isfile(output)


# ===========================================================================
# E2E: Resources
# ===========================================================================

@skip_no_rd
@skip_no_cap
class TestResourcesE2E:
    def test_resources_list(self):
        data = _run_cli("resources", "list")
        assert isinstance(data, list)

    def test_resources_buffers(self):
        data = _run_cli("resources", "buffers")
        assert isinstance(data, list)


# ===========================================================================
# E2E: Pipeline
# ===========================================================================

@skip_no_rd
@skip_no_cap
class TestPipelineE2E:
    def test_pipeline_state(self):
        # Get first draw call
        draws = _run_cli("actions", "list", "--draws-only")
        if not draws:
            pytest.skip("No draw calls in capture")
        eid = draws[0]["eventId"]
        data = _run_cli("pipeline", "state", str(eid))
        assert "shaders" in data
        assert "eventId" in data

    def test_pipeline_shader_export(self):
        draws = _run_cli("actions", "list", "--draws-only")
        if not draws:
            pytest.skip("No draw calls")
        eid = draws[0]["eventId"]
        data = _run_cli("pipeline", "shader-export", str(eid), "--stage", "Fragment")
        # May have error if no pixel shader - acceptable
        assert "eventId" in data or "error" in data


# ===========================================================================
# E2E: Counters
# ===========================================================================

@skip_no_rd
@skip_no_cap
class TestCountersE2E:
    def test_counters_list(self):
        data = _run_cli("counters", "list")
        assert isinstance(data, list)


# ===========================================================================
# Workflow: Full analysis pipeline
# ===========================================================================

@skip_no_rd
@skip_no_cap
class TestWorkflowE2E:
    def test_full_analysis_workflow(self):
        """Simulate a typical analysis: info → list draws → inspect → export."""
        # Step 1: Capture info
        info = _run_cli("capture", "info")
        assert "api" in info

        # Step 2: Action summary
        summary = _run_cli("actions", "summary")
        assert summary["total_actions"] > 0

        # Step 3: Find draw calls
        draws = _run_cli("actions", "list", "--draws-only")
        if not draws:
            return  # No draws to inspect

        # Step 4: Inspect pipeline at first draw
        eid = draws[0]["eventId"]
        pipeline = _run_cli("pipeline", "state", str(eid))
        assert "shaders" in pipeline

        # Step 5: List textures
        textures = _run_cli("textures", "list")
        assert isinstance(textures, list)


@skip_no_rd
@skip_no_cap
class TestPreviewAPIE2E:
    def test_preview_capture_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open_capture(TEST_CAPTURE) as handle:
                manifest = preview_mod.capture(
                    handle,
                    TEST_CAPTURE,
                    root_dir=tmpdir,
                    force=True,
                )

            assert manifest["software"] == "renderdoc"
            assert manifest["bundle_kind"] == "capture"
            assert manifest["status"] in ("ok", "partial")

            artifact_ids = {artifact["artifact_id"] for artifact in manifest["artifacts"]}
            assert "action_summary" in artifact_ids
            summary_path = _artifact_path(manifest, "action_summary")
            assert os.path.isfile(summary_path)

            latest = preview_mod.latest(
                project_path=TEST_CAPTURE,
                recipe="quick",
                bundle_kind="capture",
                root_dir=tmpdir,
            )
            assert latest["bundle_id"] == manifest["bundle_id"]

            print(f"\n  RenderDoc preview bundle: {manifest['_bundle_dir']}")
            print(f"  RenderDoc action summary: {summary_path}")

    def test_preview_diff_bundle(self):
        draws = _run_cli("actions", "list", "--draws-only")
        if not draws:
            pytest.skip("No draw calls in capture")

        event_a = int(draws[0]["eventId"])
        event_b = int(draws[-1]["eventId"])

        with tempfile.TemporaryDirectory() as tmpdir:
            with open_capture(TEST_CAPTURE) as handle_a, open_capture(TEST_CAPTURE) as handle_b:
                manifest = preview_mod.diff(
                    handle_a,
                    TEST_CAPTURE,
                    event_a,
                    handle_b,
                    TEST_CAPTURE,
                    event_b,
                    root_dir=tmpdir,
                    force=True,
                )

            assert manifest["software"] == "renderdoc"
            assert manifest["bundle_kind"] == "diff"
            diff_path = _artifact_path(manifest, "pipeline_diff")
            assert os.path.isfile(diff_path)
            with open(diff_path, "r", encoding="utf-8") as fh:
                diff_data = json.load(fh)
            assert isinstance(diff_data, dict)

            latest = preview_mod.latest(
                project_path=TEST_CAPTURE,
                recipe="diff",
                bundle_kind="diff",
                root_dir=tmpdir,
            )
            assert latest["bundle_id"] == manifest["bundle_id"]

            print(f"\n  RenderDoc diff bundle: {manifest['_bundle_dir']}")
            print(f"  RenderDoc pipeline diff: {diff_path}")


@skip_no_rd
@skip_no_cap
class TestPreviewCLIE2E:
    def test_cli_preview_capture(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = _run_cli("preview", "capture", "--root-dir", tmpdir)
            assert manifest["software"] == "renderdoc"
            summary_path = _artifact_path(manifest, "action_summary")
            assert os.path.isfile(summary_path)

            latest = _run_cli(
                "preview",
                "latest",
                "--recipe",
                "quick",
                "--bundle-kind",
                "capture",
                "--root-dir",
                tmpdir,
            )
            assert latest["bundle_id"] == manifest["bundle_id"]

            print(f"\n  RenderDoc preview bundle: {manifest['_bundle_dir']}")
            print(f"  RenderDoc action summary: {summary_path}")

    def test_cli_preview_diff(self):
        draws = _run_cli("actions", "list", "--draws-only")
        if not draws:
            pytest.skip("No draw calls in capture")

        event_a = int(draws[0]["eventId"])
        event_b = int(draws[-1]["eventId"])

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = _run_cli(
                "preview",
                "diff",
                str(event_a),
                str(event_b),
                "--root-dir",
                tmpdir,
            )
            assert manifest["software"] == "renderdoc"
            assert manifest["bundle_kind"] == "diff"
            diff_path = _artifact_path(manifest, "pipeline_diff")
            assert os.path.isfile(diff_path)

            latest = _run_cli(
                "preview",
                "latest",
                "--recipe",
                "diff",
                "--bundle-kind",
                "diff",
                "--root-dir",
                tmpdir,
            )
            assert latest["bundle_id"] == manifest["bundle_id"]

            print(f"\n  RenderDoc diff bundle: {manifest['_bundle_dir']}")
            print(f"  RenderDoc pipeline diff: {diff_path}")
