"""Unit tests for the `asset upload` command and the `attr` command family.

Tests CLI output formatting using Click's CliRunner with a mocked client.
No external dependencies or running SiYuan instance required.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.siyuan.siyuan_cli import (
    _dispatch_repl,
    _handle_asset_repl,
    _handle_attr_repl,
    cli,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_ctx():
    """Create a mock SiYuanContext with a mock client."""
    ctx = MagicMock()
    ctx.json_output = False
    return ctx


def _invoke(runner, mock_ctx, args):
    with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
        return runner.invoke(cli, args)


# ── asset upload ───────────────────────────────────────────────────────


class TestAssetUploadCommand:
    def test_upload_single_file(self, runner, mock_ctx, tmp_path):
        """upload passes the file path and prints the asset path to reference."""
        src = tmp_path / "pic.png"
        src.write_bytes(b"\x89PNG")
        mock_ctx.client.upload_asset.return_value = {
            "errFiles": [], "succMap": {"pic.png": "assets/pic-20260917120000-ab1cd.png"}}
        result = _invoke(runner, mock_ctx, ["asset", "upload", str(src)])
        assert result.exit_code == 0
        assert "assets/pic-20260917120000-ab1cd.png" in result.output
        mock_ctx.client.upload_asset.assert_called_once_with(
            [str(src)], assets_dir_path="/assets/")

    def test_upload_multiple_files_with_dir(self, runner, mock_ctx, tmp_path):
        """Several files plus --dir reach the client in one call."""
        a = tmp_path / "a.png"
        a.write_bytes(b"a")
        b = tmp_path / "b.jpg"
        b.write_bytes(b"b")
        mock_ctx.client.upload_asset.return_value = {
            "errFiles": [], "succMap": {"a.png": "assets/a.png", "b.jpg": "assets/b.jpg"}}
        result = _invoke(
            runner, mock_ctx, ["asset", "upload", str(a), str(b), "--dir", "/assets/notes/"])
        assert result.exit_code == 0
        mock_ctx.client.upload_asset.assert_called_once_with(
            [str(a), str(b)], assets_dir_path="/assets/notes/")

    def test_upload_json_output(self, runner, mock_ctx, tmp_path):
        """--json prints succMap/errFiles instead of the plain mapping."""
        src = tmp_path / "p.png"
        src.write_bytes(b"p")
        mock_ctx.client.upload_asset.return_value = {
            "errFiles": [], "succMap": {"p.png": "assets/p.png"}}
        mock_ctx.json_output = True
        result = _invoke(runner, mock_ctx, ["--json", "asset", "upload", str(src)])
        assert result.exit_code == 0
        assert json.loads(result.output)["succMap"] == {"p.png": "assets/p.png"}

    def test_upload_missing_file_refuses(self, runner, mock_ctx, tmp_path):
        """A local path that does not exist is rejected before any request."""
        result = _invoke(runner, mock_ctx, ["asset", "upload", str(tmp_path / "nope.png")])
        assert result.exit_code != 0
        mock_ctx.client.upload_asset.assert_not_called()

    def test_upload_reports_err_files(self, runner, mock_ctx, tmp_path):
        """Files the kernel rejected surface as a CLI error."""
        src = tmp_path / "big.bin"
        src.write_bytes(b"x")
        mock_ctx.client.upload_asset.return_value = {"errFiles": ["big.bin"], "succMap": {}}
        result = _invoke(runner, mock_ctx, ["asset", "upload", str(src)])
        assert result.exit_code != 0
        assert "big.bin" in result.output


# ── attr get / set / unset ─────────────────────────────────────────────


class TestAttrGetCommand:
    def test_get_lists_sorted_attributes(self, runner, mock_ctx):
        mock_ctx.client.get_block_attrs.return_value = {"custom-b": "2", "name": "标题"}
        result = _invoke(runner, mock_ctx, ["attr", "get", "b1"])
        assert result.exit_code == 0
        assert "custom-b: 2" in result.output
        assert "name: 标题" in result.output

    def test_get_without_attributes(self, runner, mock_ctx):
        mock_ctx.client.get_block_attrs.return_value = {}
        result = _invoke(runner, mock_ctx, ["attr", "get", "b1"])
        assert result.exit_code == 0
        assert "No attributes" in result.output

    def test_get_json(self, runner, mock_ctx):
        mock_ctx.client.get_block_attrs.return_value = {"custom-x": "1"}
        mock_ctx.json_output = True
        result = _invoke(runner, mock_ctx, ["--json", "attr", "get", "b1"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"custom-x": "1"}


class TestAttrSetCommand:
    def test_set_pairs(self, runner, mock_ctx):
        result = _invoke(
            runner, mock_ctx, ["attr", "set", "b1", "custom-status=todo", "name=待核验"])
        assert result.exit_code == 0
        mock_ctx.client.set_block_attrs.assert_called_once_with(
            "b1", {"custom-status": "todo", "name": "待核验"})
        assert "2 attribute(s)" in result.output

    def test_set_value_may_contain_equals(self, runner, mock_ctx):
        """Only the first '=' splits key from value."""
        result = _invoke(runner, mock_ctx, ["attr", "set", "b1", "custom-note=a=b"])
        assert result.exit_code == 0
        mock_ctx.client.set_block_attrs.assert_called_once_with("b1", {"custom-note": "a=b"})

    def test_set_without_equals_errors(self, runner, mock_ctx):
        result = _invoke(runner, mock_ctx, ["attr", "set", "b1", "custom-status"])
        assert result.exit_code != 0
        mock_ctx.client.set_block_attrs.assert_not_called()

    def test_set_requires_a_pair(self, runner, mock_ctx):
        result = _invoke(runner, mock_ctx, ["attr", "set", "b1"])
        assert result.exit_code != 0
        mock_ctx.client.set_block_attrs.assert_not_called()

    def test_set_json(self, runner, mock_ctx):
        mock_ctx.json_output = True
        result = _invoke(runner, mock_ctx, ["--json", "attr", "set", "b1", "custom-a=1"])
        assert result.exit_code == 0
        assert json.loads(result.output)["attrs"] == {"custom-a": "1"}


class TestAttrUnsetCommand:
    def test_unset_uses_empty_values(self, runner, mock_ctx):
        """Removal is expressed as an empty value (the kernel drops the key)."""
        result = _invoke(runner, mock_ctx, ["attr", "unset", "b1", "custom-a", "custom-b"])
        assert result.exit_code == 0
        mock_ctx.client.set_block_attrs.assert_called_once_with(
            "b1", {"custom-a": "", "custom-b": ""})

    def test_unset_json(self, runner, mock_ctx):
        mock_ctx.json_output = True
        result = _invoke(runner, mock_ctx, ["--json", "attr", "unset", "b1", "custom-a"])
        assert result.exit_code == 0
        assert json.loads(result.output)["removed"] == ["custom-a"]

    def test_unset_requires_a_key(self, runner, mock_ctx):
        result = _invoke(runner, mock_ctx, ["attr", "unset", "b1"])
        assert result.exit_code != 0
        mock_ctx.client.set_block_attrs.assert_not_called()


# ── REPL: asset / attr ─────────────────────────────────────────────────


class TestReplAssetUpload:
    def test_repl_upload_reaches_client(self, tmp_path):
        src = tmp_path / "pic.png"
        src.write_bytes(b"p")
        skin, client = MagicMock(), MagicMock()
        client.upload_asset.return_value = {
            "errFiles": [], "succMap": {"pic.png": "assets/pic.png"}}
        _handle_asset_repl(skin, client, ["asset", "upload", str(src)], False)
        client.upload_asset.assert_called_once_with([str(src)], assets_dir_path="/assets/")
        skin.success.assert_called_once()

    def test_repl_upload_dir_value_is_not_a_file(self, tmp_path):
        """The --dir value belongs to the flag, not to the upload targets."""
        src = tmp_path / "pic.png"
        src.write_bytes(b"p")
        skin, client = MagicMock(), MagicMock()
        client.upload_asset.return_value = {"errFiles": [], "succMap": {}}
        _handle_asset_repl(
            skin, client, ["asset", "upload", str(src), "--dir", "/assets/notes/"], False)
        client.upload_asset.assert_called_once_with([str(src)], assets_dir_path="/assets/notes/")

    def test_repl_upload_missing_file_errors(self):
        skin, client = MagicMock(), MagicMock()
        _handle_asset_repl(skin, client, ["asset", "upload", "C:/nope/none.png"], False)
        client.upload_asset.assert_not_called()
        skin.error.assert_called_once()

    def test_repl_upload_usage_error(self):
        skin, client = MagicMock(), MagicMock()
        _handle_asset_repl(skin, client, ["asset", "upload"], False)
        client.upload_asset.assert_not_called()
        skin.error.assert_called_once()


class TestReplAttr:
    def test_repl_attr_get(self):
        skin, client = MagicMock(), MagicMock()
        client.get_block_attrs.return_value = {"custom-a": "1"}
        _handle_attr_repl(skin, client, ["attr", "get", "b1"], False)
        client.get_block_attrs.assert_called_once_with("b1")
        skin.table.assert_called_once()

    def test_repl_attr_set(self):
        skin, client = MagicMock(), MagicMock()
        _handle_attr_repl(skin, client, ["attr", "set", "b1", "custom-a=1"], False)
        client.set_block_attrs.assert_called_once_with("b1", {"custom-a": "1"})
        skin.success.assert_called_once()

    def test_repl_attr_set_rejects_bad_pair(self):
        skin, client = MagicMock(), MagicMock()
        _handle_attr_repl(skin, client, ["attr", "set", "b1", "custom-a"], False)
        client.set_block_attrs.assert_not_called()
        skin.error.assert_called_once()

    def test_repl_attr_unset(self):
        skin, client = MagicMock(), MagicMock()
        _handle_attr_repl(skin, client, ["attr", "unset", "b1", "custom-a"], False)
        client.set_block_attrs.assert_called_once_with("b1", {"custom-a": ""})

    def test_repl_attr_usage_error(self):
        skin, client = MagicMock(), MagicMock()
        _handle_attr_repl(skin, client, ["attr", "get"], False)
        client.get_block_attrs.assert_not_called()
        skin.error.assert_called_once()


class TestReplDispatchRouting:
    def test_dispatch_routes_attr(self):
        """`attr get` reaches the attr handler rather than "Unknown command"."""
        skin = MagicMock()
        ctx = MagicMock()
        ctx.client.get_block_attrs.return_value = {}
        ctx.session = MagicMock()
        _dispatch_repl(skin, ctx, "attr get b1")
        ctx.client.get_block_attrs.assert_called_once_with("b1")
        skin.error.assert_not_called()

    def test_dispatch_routes_asset(self, tmp_path):
        src = tmp_path / "p.png"
        src.write_bytes(b"p")
        skin = MagicMock()
        ctx = MagicMock()
        ctx.client.upload_asset.return_value = {"errFiles": [], "succMap": {}}
        ctx.session = MagicMock()
        _dispatch_repl(skin, ctx, f"asset upload {src}")
        ctx.client.upload_asset.assert_called_once()
        skin.error.assert_not_called()
