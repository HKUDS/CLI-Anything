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
