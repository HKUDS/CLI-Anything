"""
Unit tests for RenderDoc CLI core modules.

These tests use mocks and synthetic data — no renderdoc dependency needed.
Run with: pytest test_core.py -v
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ===========================================================================
# Test utils/output.py
# ===========================================================================

class TestOutputUtils:
    def test_output_json(self):
        from cli_anything.renderdoc.utils.output import output_json
        import io
        buf = io.StringIO()
        output_json({"key": "value", "num": 42}, file=buf)
        result = json.loads(buf.getvalue())
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_output_table(self):
        from cli_anything.renderdoc.utils.output import output_table
        import io
        buf = io.StringIO()
        output_table(
            [["Alice", 30], ["Bob", 25]],
            ["Name", "Age"],
            file=buf,
        )
        text = buf.getvalue()
        assert "Alice" in text
        assert "Bob" in text
        assert "Name" in text

    def test_output_table_empty(self):
        from cli_anything.renderdoc.utils.output import output_table
        import io
        buf = io.StringIO()
        output_table([], ["Name"], file=buf)
        assert "(no data)" in buf.getvalue()

    def test_format_size(self):
        from cli_anything.renderdoc.utils.output import format_size
        assert format_size(512) == "512 B"
        assert "KB" in format_size(2048)
        assert "MB" in format_size(2 * 1024 * 1024)
        assert "GB" in format_size(3 * 1024 * 1024 * 1024)


# ===========================================================================
# Test utils/errors.py
# ===========================================================================

class TestErrorUtils:
    def test_handle_error(self):
        from cli_anything.renderdoc.utils.errors import handle_error
        result = handle_error(ValueError("test error"))
        assert result["error"] == "test error"
        assert result["type"] == "ValueError"
        assert "traceback" not in result

    def test_handle_error_debug(self):
        from cli_anything.renderdoc.utils.errors import handle_error
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            result = handle_error(e, debug=True)
        assert "traceback" in result
        assert "boom" in result["traceback"]


# ===========================================================================
# Test core/actions.py (with mock rd)
# ===========================================================================

class MockActionFlags:
    Clear = 0x0001
    Drawcall = 0x0002
    Dispatch = 0x0004
    CmdList = 0x0008
    SetMarker = 0x0010
    PushMarker = 0x0020
    PopMarker = 0x0040
    Present = 0x0080
    MultiAction = 0x0100
    Copy = 0x0200
    Resolve = 0x0400
    GenMips = 0x0800
    PassBoundary = 0x1000
    Indexed = 0x2000
    Instanced = 0x4000
    Auto = 0x8000
    Indirect = 0x10000
    ClearColor = 0x20000
    ClearDepthStencil = 0x40000
    BeginPass = 0x80000
    EndPass = 0x100000


def _make_mock_action(event_id, name, flags=0x0002, num_indices=100, children=None):
    action = MagicMock()
    action.eventId = event_id
    action.actionId = event_id
    action.customName = name
    action.GetName = MagicMock(return_value=name)
    action.flags = flags
    action.numIndices = num_indices
    action.numInstances = 1
    action.indexOffset = 0
    action.baseVertex = 0
    action.vertexOffset = 0
    action.instanceOffset = 0
    action.outputs = []
    action.depthOut = MagicMock()
    action.depthOut.__str__ = lambda s: "0"
    action.children = children or []
    action.next = None
    return action


class TestActionsModule:
    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_decode_flags(self, mock_rd):
        # Patch the flag values
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import _decode_flags
        result = _decode_flags(0x0002)  # Drawcall
        assert "Drawcall" in result

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_decode_flags_multiple(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import _decode_flags
        result = _decode_flags(0x0002 | 0x2000)  # Drawcall + Indexed
        assert "Drawcall" in result
        assert "Indexed" in result

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_action_to_dict(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import _action_to_dict
        action = _make_mock_action(1, "Draw Triangle", 0x0002)
        d = _action_to_dict(action, None)
        assert d["eventId"] == 1
        assert d["name"] == "Draw Triangle"
        assert "Drawcall" in d["flags"]

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_list_actions_flat(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import list_actions

        child = _make_mock_action(2, "DrawIndexed", 0x0002)
        root = _make_mock_action(1, "RenderPass", 0x0020, children=[child])

        controller = MagicMock()
        controller.GetRootActions.return_value = [root]
        controller.GetStructuredFile.return_value = MagicMock()

        result = list_actions(controller, flat=True)
        assert len(result) == 2
        assert result[0]["eventId"] == 1
        assert result[1]["eventId"] == 2
        assert result[1]["depth"] == 1

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_list_actions_root_only(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import list_actions

        child = _make_mock_action(2, "DrawIndexed")
        root = _make_mock_action(1, "RenderPass", 0x0020, children=[child])

        controller = MagicMock()
        controller.GetRootActions.return_value = [root]
        controller.GetStructuredFile.return_value = MagicMock()

        result = list_actions(controller, flat=False)
        assert len(result) == 1

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_find_actions_by_name(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import find_actions_by_name

        a1 = _make_mock_action(1, "Clear RenderTarget", 0x0001)
        a2 = _make_mock_action(2, "DrawIndexed(100)", 0x0002)
        a3 = _make_mock_action(3, "DrawIndexed(200)", 0x0002)

        controller = MagicMock()
        controller.GetRootActions.return_value = [a1, a2, a3]
        controller.GetStructuredFile.return_value = MagicMock()

        result = find_actions_by_name(controller, "drawindex")
        assert len(result) == 2

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_find_action_by_event(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import find_action_by_event

        a1 = _make_mock_action(10, "Draw", 0x0002)
        controller = MagicMock()
        controller.GetRootActions.return_value = [a1]
        controller.GetStructuredFile.return_value = MagicMock()

        result = find_action_by_event(controller, 10)
        assert result is not None
        assert result["eventId"] == 10

        result = find_action_by_event(controller, 999)
        assert result is None

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_get_drawcalls_only(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import get_drawcalls_only

        a1 = _make_mock_action(1, "Clear", 0x0001)  # Clear
        a2 = _make_mock_action(2, "Draw", 0x0002)    # Drawcall
        a3 = _make_mock_action(3, "Marker", 0x0020)  # PushMarker

        controller = MagicMock()
        controller.GetRootActions.return_value = [a1, a2, a3]
        controller.GetStructuredFile.return_value = MagicMock()

        result = get_drawcalls_only(controller)
        assert len(result) == 1
        assert result[0]["name"] == "Draw"

    @patch("cli_anything.renderdoc.core.actions.rd")
    def test_action_summary(self, mock_rd):
        mock_rd.ActionFlags = MockActionFlags
        from cli_anything.renderdoc.core.actions import action_summary

        actions = [
            _make_mock_action(1, "Clear", 0x0001),
            _make_mock_action(2, "Draw1", 0x0002),
            _make_mock_action(3, "Draw2", 0x0002),
            _make_mock_action(4, "Dispatch", 0x0004),
            _make_mock_action(5, "Copy", 0x0200),
            _make_mock_action(6, "Marker", 0x0020),
            _make_mock_action(7, "Present", 0x0080),
        ]
        controller = MagicMock()
        controller.GetRootActions.return_value = actions
        controller.GetStructuredFile.return_value = MagicMock()

        result = action_summary(controller)
        assert result["total_actions"] == 7
        assert result["drawcalls"] == 2
        assert result["clears"] == 1
        assert result["dispatches"] == 1
        assert result["copies"] == 1
        assert result["markers"] == 1
        assert result["presents"] == 1


# ===========================================================================
# Test core/textures.py (mock-based)
# ===========================================================================

class TestTexturesModule:
    def _make_mock_tex(self, rid="123", w=512, h=512, mips=1, fmt="R8G8B8A8_UNORM"):
        tex = MagicMock()
        tex.resourceId = MagicMock()
        tex.resourceId.__str__ = lambda s: rid
        tex.name = f"Texture_{rid}"
        tex.width = w
        tex.height = h
        tex.depth = 1
        tex.mips = mips
        tex.arraysize = 1
        tex.msQual = 0
        tex.msSamp = 1
        tex.format = MagicMock()
        tex.format.__str__ = lambda s: fmt
        tex.dimension = 2
        tex.type = MagicMock()
        tex.type.__str__ = lambda s: "Texture2D"
        tex.cubemap = False
        tex.byteSize = w * h * 4
        tex.creationFlags = 0
        return tex

    def test_tex_to_dict(self):
        from cli_anything.renderdoc.core.textures import _tex_to_dict
        tex = self._make_mock_tex()
        d = _tex_to_dict(tex)
        assert d["resourceId"] == "123"
        assert d["width"] == 512
        assert d["height"] == 512
        assert d["mips"] == 1

    def test_list_textures(self):
        from cli_anything.renderdoc.core.textures import list_textures
        controller = MagicMock()
        controller.GetTextures.return_value = [
            self._make_mock_tex("1", 256, 256),
            self._make_mock_tex("2", 1024, 1024),
        ]
        result = list_textures(controller)
        assert len(result) == 2
        assert result[0]["width"] == 256
        assert result[1]["width"] == 1024

    def test_get_texture_found(self):
        from cli_anything.renderdoc.core.textures import get_texture
        controller = MagicMock()
        controller.GetTextures.return_value = [
            self._make_mock_tex("42", 800, 600),
        ]
        result = get_texture(controller, "42")
        assert result is not None
        assert result["width"] == 800

    def test_get_texture_not_found(self):
        from cli_anything.renderdoc.core.textures import get_texture
        controller = MagicMock()
        controller.GetTextures.return_value = []
        result = get_texture(controller, "999")
        assert result is None


# ===========================================================================
# Test core/resources.py (mock-based)
# ===========================================================================

class TestResourcesModule:
    def test_list_resources(self):
        from cli_anything.renderdoc.core.resources import list_resources

        r1 = MagicMock()
        r1.resourceId = MagicMock()
        r1.resourceId.__str__ = lambda s: "1"
        r1.name = "Backbuffer"
        r1.type = MagicMock()
        r1.type.__str__ = lambda s: "Texture"

        controller = MagicMock()
        controller.GetResources.return_value = [r1]

        result = list_resources(controller)
        assert len(result) == 1
        assert result[0]["name"] == "Backbuffer"

    def test_list_buffers(self):
        from cli_anything.renderdoc.core.resources import list_buffers

        b1 = MagicMock()
        b1.resourceId = MagicMock()
        b1.resourceId.__str__ = lambda s: "5"
        b1.length = 4096
        b1.creationFlags = 0

        controller = MagicMock()
        controller.GetBuffers.return_value = [b1]

        result = list_buffers(controller)
        assert len(result) == 1
        assert result[0]["length"] == 4096

    def test_get_buffer_data_hex(self):
        from cli_anything.renderdoc.core.resources import get_buffer_data

        b1 = MagicMock()
        b1.resourceId = MagicMock()
        b1.resourceId.__str__ = lambda s: "5"

        controller = MagicMock()
        controller.GetBuffers.return_value = [b1]
        controller.GetBufferData.return_value = b"\x01\x02\x03\x04"

        result = get_buffer_data(controller, "5", 0, 4, "hex")
        assert result["data"] == "01020304"
        assert result["length"] == 4

    def test_get_buffer_data_float32(self):
        from cli_anything.renderdoc.core.resources import get_buffer_data

        b1 = MagicMock()
        b1.resourceId = MagicMock()
        b1.resourceId.__str__ = lambda s: "5"

        controller = MagicMock()
        controller.GetBuffers.return_value = [b1]
        test_data = struct.pack("<2f", 1.0, 2.5)
        controller.GetBufferData.return_value = test_data

        result = get_buffer_data(controller, "5", 0, 8, "float32")
        assert len(result["data"]) == 2
        assert abs(result["data"][0] - 1.0) < 0.001
        assert abs(result["data"][1] - 2.5) < 0.001

    def test_get_buffer_data_not_found(self):
        from cli_anything.renderdoc.core.resources import get_buffer_data

        controller = MagicMock()
        controller.GetBuffers.return_value = []

        result = get_buffer_data(controller, "999", 0, 4, "hex")
        assert "error" in result


# ===========================================================================
# Test CLI entry point (Click testing)
# ===========================================================================

class TestCLIHelp:
    """Test that CLI help works without renderdoc installed."""

    def test_main_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "RenderDoc CLI" in result.output

    def test_capture_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["capture", "--help"])
        assert result.exit_code == 0
        assert "info" in result.output

    def test_actions_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["actions", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output

    def test_textures_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["textures", "--help"])
        assert result.exit_code == 0
        assert "save" in result.output

    def test_pipeline_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["pipeline", "--help"])
        assert result.exit_code == 0
        assert "state" in result.output

    def test_resources_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["resources", "--help"])
        assert result.exit_code == 0
        assert "buffers" in result.output

    def test_mesh_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["mesh", "--help"])
        assert result.exit_code == 0
        assert "inputs" in result.output

    def test_counters_help(self):
        from click.testing import CliRunner
        from cli_anything.renderdoc.renderdoc_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["counters", "--help"])
        assert result.exit_code == 0
        assert "fetch" in result.output


# ===========================================================================
# Test subprocess invocation pattern
# ===========================================================================

class TestCLISubprocess:
    """Test CLI via subprocess from agent-harness root (namespace on cwd)."""

    def test_cli_help_subprocess(self):
        import subprocess

        harness_root = Path(__file__).resolve().parents[3]
        try:
            result = subprocess.run(
                [sys.executable, "-m", "cli_anything.renderdoc.renderdoc_cli", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(harness_root),
            )
            assert result.returncode == 0
            assert "RenderDoc CLI" in result.stdout
        except FileNotFoundError:
            pytest.skip("CLI not installed")


# ===========================================================================
# Test core/diff.py (snapshot-based, no renderdoc needed)
# ===========================================================================

class TestDiffModule:
    """Unit tests for diff_pipeline_from_snapshots and helpers."""

    @staticmethod
    def _make_snapshot(event_id, pipeline_state=None):
        """Build a minimal snapshot dict."""
        return {
            "eventId": event_id,
            "PipelineState": pipeline_state or {},
        }

    def test_identical_snapshots(self):
        from cli_anything.renderdoc.core.diff import diff_pipeline_from_snapshots

        ps = {
            "pipelineType": "Graphics",
            "viewport": {"x": 0, "y": 0, "width": 1920, "height": 1080},
            "rasterizer": {"fillMode": "Solid"},
            "depthStencil": {"depthEnable": True},
            "stages": {},
        }
        snap = self._make_snapshot(100, ps)
        result = diff_pipeline_from_snapshots(snap, snap)
        assert result["identical"] is True

    def test_different_viewport(self):
        from cli_anything.renderdoc.core.diff import diff_pipeline_from_snapshots

        ps_a = {"viewport": {"x": 0, "y": 0, "width": 1920, "height": 1080}}
        ps_b = {"viewport": {"x": 0, "y": 0, "width": 1280, "height": 720}}
        result = diff_pipeline_from_snapshots(
            self._make_snapshot(1, ps_a),
            self._make_snapshot(2, ps_b),
        )
        assert result["identical"] is False
        assert "viewport" in result
        assert result["viewport"]["width"]["A"] == 1920
        assert result["viewport"]["width"]["B"] == 1280

    def test_float_tolerance(self):
        from cli_anything.renderdoc.core.diff import _values_equal

        assert _values_equal(1.0, 1.0 + 1e-9) is True
        assert _values_equal(1.0, 1.1) is False

    def test_float_nan_equal(self):
        import math
        from cli_anything.renderdoc.core.diff import _values_equal

        assert _values_equal(float("nan"), float("nan")) is True
        assert _values_equal(float("inf"), float("inf")) is True
        assert _values_equal(float("inf"), float("-inf")) is False

    def test_diff_lists_only_in_one_side(self):
        from cli_anything.renderdoc.core.diff import diff_pipeline_from_snapshots

        ps_a = {
            "vertexInputs": [
                {"name": "POSITION", "format": "R32G32B32_FLOAT"},
            ],
        }
        ps_b = {
            "vertexInputs": [
                {"name": "POSITION", "format": "R32G32B32_FLOAT"},
                {"name": "TEXCOORD", "format": "R32G32_FLOAT"},
            ],
        }
        result = diff_pipeline_from_snapshots(
            self._make_snapshot(1, ps_a),
            self._make_snapshot(2, ps_b),
        )
        assert result["identical"] is False
        assert isinstance(result["vertexInputs"], list)
        statuses = [d["status"] for d in result["vertexInputs"]]
        assert "only_in_B" in statuses

    def test_diff_dicts_missing_key(self):
        from cli_anything.renderdoc.core.diff import _diff_dicts

        a = {"x": 1, "y": 2}
        b = {"x": 1, "z": 3}
        result = _diff_dicts(a, b)
        assert result is not None
        assert "y" in result
        assert "z" in result

    def test_diff_dicts_identical(self):
        from cli_anything.renderdoc.core.diff import _diff_dicts

        a = {"x": 1, "y": 2}
        result = _diff_dicts(a, a)
        assert result is None

    def test_diff_dicts_none_inputs(self):
        from cli_anything.renderdoc.core.diff import _diff_dicts

        assert _diff_dicts(None, None) is None
        result = _diff_dicts(None, {"x": 1})
        assert result is not None
        assert result["A"] is None

    def test_stage_diff_shader_changed(self):
        from cli_anything.renderdoc.core.diff import diff_pipeline_from_snapshots

        ps_a = {
            "stages": {
                "Vertex": {
                    "shader": "ResourceId::100",
                    "entryPoint": "main",
                    "ShaderReflection": {},
                    "bindings": {"constantBlocks": [], "readOnlyResources": [],
                                 "readWriteResources": [], "samplers": []},
                },
            },
        }
        ps_b = {
            "stages": {
                "Vertex": {
                    "shader": "ResourceId::200",
                    "entryPoint": "main",
                    "ShaderReflection": {},
                    "bindings": {"constantBlocks": [], "readOnlyResources": [],
                                 "readWriteResources": [], "samplers": []},
                },
            },
        }
        result = diff_pipeline_from_snapshots(
            self._make_snapshot(1, ps_a),
            self._make_snapshot(2, ps_b),
        )
        assert result["identical"] is False
        assert result["stages"]["Vertex"]["shader"]["shader"]["A"] == "ResourceId::100"
        assert result["stages"]["Vertex"]["shader"]["shader"]["B"] == "ResourceId::200"

    def test_cbuffer_variable_diff(self):
        from cli_anything.renderdoc.core.diff import _diff_cbuffer_vars

        vars_a = [
            {"name": "color", "values": [1.0, 0.0, 0.0, 1.0]},
            {"name": "intensity", "values": [0.5]},
        ]
        vars_b = [
            {"name": "color", "values": [0.0, 1.0, 0.0, 1.0]},
            {"name": "intensity", "values": [0.5]},
        ]
        result = _diff_cbuffer_vars(vars_a, vars_b)
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "color"
        assert result[0]["status"] == "changed"

    def test_cbuffer_variable_identical(self):
        from cli_anything.renderdoc.core.diff import _diff_cbuffer_vars

        vars_a = [{"name": "x", "values": [1.0]}]
        result = _diff_cbuffer_vars(vars_a, vars_a)
        assert result is None

    def test_output_table_extra_columns(self):
        """Verify output_table truncates rows longer than headers."""
        from cli_anything.renderdoc.utils.output import output_table
        import io

        buf = io.StringIO()
        output_table(
            [["Alice", 30, "extra_col"]],
            ["Name", "Age"],
            file=buf,
        )
        text = buf.getvalue()
        assert "Alice" in text
        assert "extra_col" not in text
