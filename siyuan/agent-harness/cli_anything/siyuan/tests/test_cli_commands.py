"""Unit tests for cli-anything-siyuan CLI commands.

Tests CLI output formatting using Click's CliRunner with mocked client.
No external dependencies or running SiYuan instance required.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from click import UsageError
from click.testing import CliRunner

from cli_anything.siyuan.siyuan_cli import (
    _dispatch_repl,
    _handle_asset_repl,
    _handle_attr_repl,
    _handle_block_repl,
    _handle_doc_repl,
    _handle_notebook_repl,
    _read_stdin,
    _tokenize_repl,
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


# ── Search command ─────────────────────────────────────────────────────


class TestSearchCommand:
    def test_search_returns_blocks_list(self, runner, mock_ctx):
        """search handles API returning list of blocks directly."""
        mock_ctx.client.search_blocks.return_value = [
            {"id": "b1", "content": "Dit模型训练结果如何"},
            {"id": "b2", "content": "训练完成，准确率90%"},
        ]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["search", "Dit模型"])
            assert result.exit_code == 0
            assert "b1" in result.output
            assert "Dit模型训练结果如何" in result.output
            assert "b2" in result.output

    def test_search_returns_dict_with_blocks_key(self, runner, mock_ctx):
        """search handles API returning dict with 'blocks' key (real SiYuan format).

        This is the fix for KeyError: slice — real SiYuan API returns
        {"blocks": [...], "rootBlocks": {...}} not a flat list.
        """
        mock_ctx.client.search_blocks.return_value = {
            "blocks": [
                {"id": "b1", "content": "Dit模型训练完成"},
                {"id": "b2", "content": "loss=0.02"},
            ],
            "rootBlocks": {},
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["search", "Dit模型"])
            assert result.exit_code == 0
            assert "b1" in result.output
            assert "Dit模型训练完成" in result.output

    def test_search_json_output(self, runner, mock_ctx):
        """--json search returns raw data."""
        mock_ctx.json_output = True
        mock_ctx.client.search_blocks.return_value = {
            "blocks": [{"id": "b1", "content": "test"}],
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "search", "test"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data[0]["id"] == "b1"

    def test_search_no_results(self, runner, mock_ctx):
        """search shows 'No results' when empty list."""
        mock_ctx.client.search_blocks.return_value = []
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["search", "nonexistent"])
            assert result.exit_code == 0
            assert "No results" in result.output

    def test_search_no_results_dict(self, runner, mock_ctx):
        """search shows 'No results' when dict with empty blocks list."""
        mock_ctx.client.search_blocks.return_value = {"blocks": [], "rootBlocks": {}}
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["search", "nonexistent"])
            assert result.exit_code == 0
            assert "No results" in result.output


# ── Doc list command ───────────────────────────────────────────────────


class TestDocListCommand:
    def test_doc_list_returns_files(self, runner, mock_ctx):
        """doc list handles API returning dict with 'files' key."""
        mock_ctx.client.list_docs_by_path.return_value = {
            "box": "nb1",
            "files": [
                {"id": "doc1", "name": "测试文档", "type": "d"},
                {"id": "doc2", "name": "笔记", "type": "d"},
            ],
            "path": "/",
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "list", "nb1"])
            assert result.exit_code == 0
            assert "doc1" in result.output
            assert "测试文档" in result.output
            assert "doc2" in result.output

    def test_doc_list_empty(self, runner, mock_ctx):
        """doc list handles empty files list."""
        mock_ctx.client.list_docs_by_path.return_value = {
            "box": "nb1", "files": [], "path": "/",
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "list", "nb1"])
            assert result.exit_code == 0
            # Should show header but no data rows
            assert "ID" in result.output
            assert "Name" in result.output

    def test_doc_list_json(self, runner, mock_ctx):
        """--json doc list returns raw files array."""
        mock_ctx.json_output = True
        mock_ctx.client.list_docs_by_path.return_value = {
            "box": "nb1", "files": [{"id": "doc1", "name": "Test"}], "path": "/",
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "doc", "list", "nb1"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data[0]["id"] == "doc1"


# ── Doc tree command ───────────────────────────────────────────────────


class TestDocTreeCommand:
    def test_doc_tree_returns_files(self, runner, mock_ctx):
        """doc tree handles API returning dict with 'files' key."""
        mock_ctx.client.list_doc_tree.return_value = {
            "files": [
                {"id": "doc1", "name": "根文档", "depth": 0},
                {"id": "doc2", "name": "子文档", "depth": 1},
            ],
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "tree", "nb1"])
            assert result.exit_code == 0
            assert "根文档" in result.output
            assert "子文档" in result.output

    def test_doc_tree_json(self, runner, mock_ctx):
        """--json doc tree returns raw files array."""
        mock_ctx.json_output = True
        mock_ctx.client.list_doc_tree.return_value = {
            "files": [{"id": "doc1", "name": "Root"}],
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "doc", "tree", "nb1"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data[0]["id"] == "doc1"


# ── Notebook list command ──────────────────────────────────────────────


class TestNotebookListCommand:
    def test_notebook_list(self, runner, mock_ctx):
        """notebook list returns formatted table."""
        mock_ctx.client.list_notebooks.return_value = [
            {"id": "nb1", "name": "工作笔记", "closed": False},
            {"id": "nb2", "name": "归档", "closed": True},
        ]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["notebook", "list"])
            assert result.exit_code == 0
            assert "工作笔记" in result.output
            assert "nb1" in result.output


# ── Tag list command ───────────────────────────────────────────────────


class TestTagListCommand:
    def test_tag_list(self, runner, mock_ctx):
        """tag list shows tag names with counts."""
        mock_ctx.client.get_tags.return_value = [
            {"name": "AI", "count": 5},
            {"name": "Python", "count": 12},
            {"name": "笔记", "count": 3},
        ]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["tag", "list"])
            assert result.exit_code == 0
            assert "AI" in result.output
            assert "5" in result.output
            assert "Python" in result.output
            assert "12" in result.output


# ── SQL command ────────────────────────────────────────────────────────


class TestSQLCommand:
    def test_sql_query(self, runner, mock_ctx):
        """sql returns query results."""
        mock_ctx.client.query_sql.return_value = [
            {"id": "b1", "content": "hello"},
            {"id": "b2", "content": "world"},
        ]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["sql", "SELECT * FROM blocks"])
            assert result.exit_code == 0
            assert "b1" in result.output
            assert "hello" in result.output


# ── Status command ─────────────────────────────────────────────────────


class TestStatusCommand:
    def test_status(self, runner, mock_ctx):
        """status shows connection info."""
        mock_ctx.client.status.return_value = {
            "connected": True,
            "version": "3.6.5",
        }
        mock_ctx.client.get_version.return_value = "3.6.5"
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            mock_session = MagicMock()
            mock_session.state.connected = True
            mock_session.state.current_notebook_id = "nb1"
            mock_session.state.current_notebook_name = "工作"
            mock_session.state.current_doc_id = "doc1"
            mock_ctx.client.get_version.return_value = "3.6.5"
            mock_ctx.session = mock_session
            mock_ctx.current_notebook_id = "nb1"
            mock_ctx.current_notebook_name = "工作"
            mock_ctx.current_doc_id = "doc1"

            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0
            assert "Connected" in result.output or "connected" in result.output.lower()


# ── Block insert command ────────────────────────────────────────────────


class TestBlockInsertCommand:
    def test_block_insert_with_parent(self, runner, mock_ctx):
        """block insert with --parent succeeds."""
        mock_ctx.client.insert_block.return_value = [{"id": "new-block"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "insert", "hello", "--parent", "pid"])
            assert result.exit_code == 0
            assert "Block inserted" in result.output
            mock_ctx.client.insert_block.assert_called_once_with(
                "markdown", "hello", parent_id="pid", previous_id="", next_id=""
            )

    def test_block_insert_with_previous(self, runner, mock_ctx):
        """block insert with --previous succeeds."""
        mock_ctx.client.insert_block.return_value = [{"id": "new-block"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "insert", "hello", "--previous", "prev"])
            assert result.exit_code == 0
            assert "Block inserted" in result.output
            mock_ctx.client.insert_block.assert_called_once_with(
                "markdown", "hello", parent_id="", previous_id="prev", next_id=""
            )

    def test_block_insert_with_next(self, runner, mock_ctx):
        """block insert with --next succeeds."""
        mock_ctx.client.insert_block.return_value = [{"id": "new-block"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "insert", "hello", "--next", "nid"])
            assert result.exit_code == 0
            assert "Block inserted" in result.output
            mock_ctx.client.insert_block.assert_called_once_with(
                "markdown", "hello", parent_id="", previous_id="", next_id="nid"
            )

    def test_block_insert_without_anchor_errors(self, runner, mock_ctx):
        """block insert without any anchor raises UsageError."""
        mock_ctx.client.insert_block.return_value = [{"id": "new-block"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "insert", "hello"])
            assert result.exit_code == 2
            assert "anchor" in result.output.lower() or "Error" in result.output

    def test_block_insert_json_output(self, runner, mock_ctx):
        """--json block insert returns raw data."""
        mock_ctx.json_output = True
        mock_ctx.client.insert_block.return_value = [{"id": "new-block"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "block", "insert", "hello", "--parent", "pid"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data[0]["id"] == "new-block"


# ── Doc get command ────────────────────────────────────────────────────


class TestDocGetCommand:
    def test_doc_get(self, runner, mock_ctx):
        """doc get shows document path."""
        mock_ctx.client.get_hpath_by_id.return_value = "/我的文档/测试"
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "get", "doc123"])
            assert result.exit_code == 0
            assert "/我的文档/测试" in result.output


# ── Doc create command ──────────────────────────────────────────────────


class TestDocCreateCommand:
    def test_doc_create_without_md(self, runner, mock_ctx):
        """doc create without --md does not read stdin (passes empty string)."""
        mock_ctx.client.create_doc_with_md.return_value = "doc123"
        with (
            patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx),
        ):
            result = runner.invoke(cli, ["doc", "create", "nb1", "/test"])
            assert result.exit_code == 0
            assert "doc123" in result.output

    def test_doc_create_with_md(self, runner, mock_ctx):
        """doc create with --md passes the markdown content."""
        mock_ctx.client.create_doc_with_md.return_value = "doc123"
        with (
            patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx),
        ):
            result = runner.invoke(cli, ["doc", "create", "nb1", "/test", "--md", "# Hello"])
            assert result.exit_code == 0
            mock_ctx.client.create_doc_with_md.assert_called_with("nb1", "/test", "# Hello")
            assert "doc123" in result.output

    def test_doc_create_json_output(self, runner, mock_ctx):
        """--json doc create returns doc ID."""
        mock_ctx.json_output = True
        mock_ctx.client.create_doc_with_md.return_value = "doc123"
        with (
            patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx),
        ):
            result = runner.invoke(cli, ["--json", "doc", "create", "nb1", "/test"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["id"] == "doc123"


# ── Doc tree recursive rendering ──────────────────────────────────────


class TestDocTreeRecursiveCommand:
    def test_doc_tree_handle_nested_children(self, runner, mock_ctx):
        """doc tree recursively renders nested children."""
        mock_ctx.client.list_doc_tree.return_value = {
            "files": [
                {
                    "id": "doc1", "name": "Root", "depth": 0,
                    "children": [
                        {"id": "doc2", "name": "Child", "depth": 1, "children": []},
                    ],
                },
                {"id": "doc3", "name": "Sibling", "depth": 0, "children": []},
            ],
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "tree", "nb1"])
            assert result.exit_code == 0
            assert "Root" in result.output
            assert "Child" in result.output
            assert "Sibling" in result.output
            assert "doc1" in result.output
            assert "doc2" in result.output

    def test_doc_tree_flat_items(self, runner, mock_ctx):
        """doc tree also works with flat items (no children key)."""
        mock_ctx.client.list_doc_tree.return_value = [
            {"id": "doc1", "name": "Flat1", "depth": 0},
            {"id": "doc2", "name": "Flat2", "depth": 1},
        ]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "tree", "nb1"])
            assert result.exit_code == 0
            assert "Flat1" in result.output
            assert "Flat2" in result.output

    def test_doc_tree_nested_json_output(self, runner, mock_ctx):
        """--json doc tree with nested children returns raw data."""
        mock_ctx.json_output = True
        mock_ctx.client.list_doc_tree.return_value = {
            "files": [{"id": "doc1", "name": "Root", "children": []}],
        }
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "doc", "tree", "nb1"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data[0]["id"] == "doc1"


# ── Destructive commands require --dangerous ───────────────────────────


class TestDocRemoveCommand:
    def test_doc_remove_without_dangerous_refuses(self, runner, mock_ctx):
        """doc remove refuses to run without --dangerous confirmation."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "remove", "doc1"])
            assert result.exit_code == 1
            assert "dangerous" in result.output.lower()
            mock_ctx.client.remove_doc_by_id.assert_not_called()

    def test_doc_remove_with_dangerous_succeeds(self, runner, mock_ctx):
        """doc remove proceeds when --dangerous is passed."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "remove", "doc1", "--dangerous"])
            assert result.exit_code == 0
            mock_ctx.client.remove_doc_by_id.assert_called_once_with("doc1")


class TestNotebookRemoveCommand:
    def test_notebook_remove_without_dangerous_refuses(self, runner, mock_ctx):
        """notebook remove refuses to run without --dangerous confirmation."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["notebook", "remove", "nb1"])
            assert result.exit_code == 1
            assert "dangerous" in result.output.lower()
            mock_ctx.client.remove_notebook.assert_not_called()

    def test_notebook_remove_with_dangerous_succeeds(self, runner, mock_ctx):
        """notebook remove proceeds when --dangerous is passed."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["notebook", "remove", "nb1", "--dangerous"])
            assert result.exit_code == 0
            mock_ctx.client.remove_notebook.assert_called_once_with("nb1")


class TestBlockDeleteCommand:
    def test_block_delete_without_dangerous_refuses(self, runner, mock_ctx):
        """block delete refuses to run without --dangerous confirmation."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "delete", "b1"])
            assert result.exit_code == 1
            assert "dangerous" in result.output.lower()
            mock_ctx.client.delete_block.assert_not_called()

    def test_block_delete_with_dangerous_succeeds(self, runner, mock_ctx):
        """block delete proceeds when --dangerous is passed."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "delete", "b1", "--dangerous"])
            assert result.exit_code == 0
            mock_ctx.client.delete_block.assert_called_once_with("b1")


# ── block move ─────────────────────────────────────────────────────────


class TestBlockMoveCommand:
    def test_move_after_previous(self, runner, mock_ctx):
        """block move --previous reorders the block at its own level."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "move", "b1", "--previous", "b2"])
            assert result.exit_code == 0
            mock_ctx.client.move_block.assert_called_once_with(
                "b1", previous_id="b2", parent_id=""
            )
            assert "b1" in result.output

    def test_move_into_parent(self, runner, mock_ctx):
        """block move --parent nests the block under another block."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "move", "b1", "--parent", "p1"])
            assert result.exit_code == 0
            mock_ctx.client.move_block.assert_called_once_with(
                "b1", previous_id="", parent_id="p1"
            )

    def test_move_without_destination_errors(self, runner, mock_ctx):
        """block move needs one destination anchor."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "move", "b1"])
            assert result.exit_code == 2
            assert "destination" in result.output.lower()
            mock_ctx.client.move_block.assert_not_called()

    def test_move_with_both_destinations_errors(self, runner, mock_ctx):
        """--previous and --parent are mutually exclusive."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(
                cli, ["block", "move", "b1", "--previous", "b2", "--parent", "p1"]
            )
            assert result.exit_code == 2
            mock_ctx.client.move_block.assert_not_called()

    def test_move_json_output(self, runner, mock_ctx):
        """--json block move reports the destination anchors."""
        mock_ctx.json_output = True
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "block", "move", "b1", "--previous", "b2"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data == {"moved": "b1", "previousID": "b2", "parentID": ""}


class TestReplBlockMove:
    def test_repl_move_with_previous(self):
        """REPL block move --previous reaches the client."""
        skin = MagicMock()
        client = MagicMock()
        _handle_block_repl(
            skin, client, ["block", "move", "b1", "--previous", "b2"], False, False
        )
        client.move_block.assert_called_once_with("b1", previous_id="b2", parent_id="")
        skin.success.assert_called_once()

    def test_repl_move_with_parent(self):
        """REPL block move --parent reaches the client."""
        skin = MagicMock()
        client = MagicMock()
        _handle_block_repl(
            skin, client, ["block", "move", "b1", "--parent", "p1"], False, False
        )
        client.move_block.assert_called_once_with("b1", previous_id="", parent_id="p1")

    def test_repl_move_without_destination_errors(self):
        """REPL block move refuses without a destination."""
        skin = MagicMock()
        client = MagicMock()
        _handle_block_repl(skin, client, ["block", "move", "b1"], False, False)
        client.move_block.assert_not_called()
        skin.error.assert_called_once()


# ── a repeated option is an error, not last-wins ───────────────────────


class TestRepeatedOptions:
    """click's default is last-wins; the REPL rejects a repeat, so one-shot does too."""

    @pytest.mark.parametrize("args", [
        ["doc", "tree", "nb1", "--path", "/a", "--path", "/b"],
        ["doc", "tree", "nb1", "--depth", "1", "--depth", "2"],
        ["doc", "create", "nb1", "/p", "--md", "a", "--md", "b"],
        ["doc", "create", "nb1", "/p", "--file", "a.md", "--file", "b.md"],
        ["block", "update", "b1", "x", "--file", "a.md", "--file", "b.md"],
        ["block", "move", "b1", "--previous", "a", "--previous", "b"],
        ["block", "insert", "x", "--parent", "a", "--parent", "b"],
        ["asset", "upload", "PLACEHOLDER", "--dir", "/a/", "--dir", "/b/"],
        ["--port", "1", "--port", "2", "version"],
    ])
    def test_repeated_option_is_rejected(self, runner, mock_ctx, tmp_path, args):
        if "PLACEHOLDER" in args:
            src = tmp_path / "p.png"
            src.write_bytes(b"p")
            args = [str(src) if a == "PLACEHOLDER" else a for a in args]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, args)
        assert result.exit_code == 2
        assert "more than once" in result.output

    def test_single_occurrence_keeps_its_value(self, runner, mock_ctx):
        """The multiple=True plumbing must not wrap the value in a tuple."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "tree", "nb1", "--depth", "3"])
        assert result.exit_code == 0
        mock_ctx.client.list_doc_tree.assert_called_once_with("nb1", path="/", max_depth=3)

    def test_option_defaults_survive(self, runner, mock_ctx, tmp_path):
        """Every fallback is now supplied by the callback, so check the ones with real defaults."""
        src = tmp_path / "p.png"
        src.write_bytes(b"p")
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            runner.invoke(cli, ["block", "update", "b1", "hi"])
            runner.invoke(cli, ["doc", "create", "nb1", "/p"])
            runner.invoke(cli, ["asset", "upload", str(src)])
        mock_ctx.client.update_block.assert_called_once_with("markdown", "hi", "b1")
        mock_ctx.client.create_doc_with_md.assert_called_once_with("nb1", "/p", "")
        mock_ctx.client.upload_asset.assert_called_once_with(
            [str(src)], assets_dir_path="/assets/")

    def test_connection_flags_still_reach_the_config(self, runner, mock_ctx):
        """--port carries an int fallback; a tuple or a string would break the URL."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanClient") as client_cls, \
                patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            runner.invoke(cli, ["--host", "10.0.0.1", "--port", "7777", "version"])
        cfg = client_cls.call_args[0][0]
        assert (cfg.host, cfg.port) == ("10.0.0.1", 7777)


# ── block prepend / append (one-shot parity with the REPL) ─────────────


class TestBlockPrependAppendCommand:
    """The REPL exposed prepend/append while one-shot had no wrapper for them."""

    def test_prepend_reaches_client(self, runner, mock_ctx):
        mock_ctx.client.prepend_block.return_value = [{"id": "new1"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "prepend", "p1", "hello"])
        assert result.exit_code == 0
        mock_ctx.client.prepend_block.assert_called_once_with("markdown", "hello", "p1")
        assert "p1" in result.output

    def test_append_reaches_client(self, runner, mock_ctx):
        mock_ctx.client.append_block.return_value = [{"id": "new1"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "append", "p1", "hello"])
        assert result.exit_code == 0
        mock_ctx.client.append_block.assert_called_once_with("markdown", "hello", "p1")

    def test_append_json(self, runner, mock_ctx):
        mock_ctx.json_output = True
        mock_ctx.client.append_block.return_value = [{"id": "new1"}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "block", "append", "p1", "hi"])
        assert json.loads(result.output) == [{"id": "new1"}]

    def test_prepend_reads_file(self, runner, mock_ctx, tmp_path):
        src = tmp_path / "note.md"
        src.write_text("来自文件", encoding="utf-8")
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "prepend", "p1", "--file", str(src)])
        assert result.exit_code == 0
        mock_ctx.client.prepend_block.assert_called_once_with("markdown", "来自文件", "p1")

    def test_prepend_requires_parent(self, runner, mock_ctx):
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "prepend"])
        assert result.exit_code == 2
        mock_ctx.client.prepend_block.assert_not_called()

    def test_prepend_rejects_argument_and_file(self, runner, mock_ctx, tmp_path):
        src = tmp_path / "note.md"
        src.write_text("x", encoding="utf-8")
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(
                cli, ["block", "prepend", "p1", "arg", "--file", str(src)])
        assert result.exit_code == 2
        mock_ctx.client.prepend_block.assert_not_called()

    def test_append_explicit_empty_is_content(self, runner, mock_ctx):
        """An explicit empty argument is content, not a missing-content error."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "append", "p1", ""])
        assert result.exit_code == 0
        mock_ctx.client.append_block.assert_called_once_with("markdown", "", "p1")


# ── --file reads content directly (avoids PowerShell pipe mangling) ────


class TestFileContentReading:
    def test_doc_create_with_file(self, runner, mock_ctx):
        """doc create --file reads UTF-8 content directly from a file."""
        mock_ctx.client.create_doc_with_md.return_value = "doc123"
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            with runner.isolated_filesystem():
                with open("note.md", "w", encoding="utf-8") as f:
                    f.write("# 中文标题\n\n正文内容")
                result = runner.invoke(
                    cli, ["doc", "create", "nb1", "/test", "--file", "note.md"]
                )
                assert result.exit_code == 0
                mock_ctx.client.create_doc_with_md.assert_called_with(
                    "nb1", "/test", "# 中文标题\n\n正文内容"
                )

    def test_doc_create_file_and_md_conflict(self, runner, mock_ctx):
        """doc create refuses to accept both --file and --md."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            with runner.isolated_filesystem():
                with open("note.md", "w", encoding="utf-8") as f:
                    f.write("x")
                result = runner.invoke(
                    cli,
                    ["doc", "create", "nb1", "/test", "--file", "note.md", "--md", "y"],
                )
                assert result.exit_code == 2
                mock_ctx.client.create_doc_with_md.assert_not_called()

    def test_doc_create_non_utf8_file_is_usage_error(self, runner, mock_ctx):
        """doc create --file with non-UTF-8 bytes yields a usage error, not a traceback."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            with runner.isolated_filesystem():
                with open("note.md", "wb") as f:
                    f.write(b"\xff\xfe\xfd\xfc not utf-8")
                result = runner.invoke(
                    cli, ["doc", "create", "nb1", "/test", "--file", "note.md"]
                )
                assert result.exit_code == 2
                assert "not valid UTF-8" in result.output
                assert "Traceback" not in result.output
                mock_ctx.client.create_doc_with_md.assert_not_called()

    def test_block_update_with_file(self, runner, mock_ctx):
        """block update --file reads UTF-8 content directly from a file."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            with runner.isolated_filesystem():
                with open("block.md", "w", encoding="utf-8") as f:
                    f.write("更新后的中文内容")
                result = runner.invoke(
                    cli, ["block", "update", "b1", "--file", "block.md"]
                )
                assert result.exit_code == 0
                mock_ctx.client.update_block.assert_called_with(
                    "markdown", "更新后的中文内容", "b1"
                )

    def test_block_update_no_content_empty_stdin_refused(self, runner, mock_ctx):
        """block update with no data/--file and empty stdin refuses, not erasing the block."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "update", "b1"])
            assert result.exit_code == 2
            assert "content" in result.output.lower()
            mock_ctx.client.update_block.assert_not_called()

    def test_block_update_explicit_empty_payload_allowed(self, runner, mock_ctx):
        """block update b1 \"\" (explicit empty) is honoured, clearing the block."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "update", "b1", ""])
            assert result.exit_code == 0
            mock_ctx.client.update_block.assert_called_once_with("markdown", "", "b1")


# ── stdin decoding fallback ────────────────────────────────────────────


class _FakeStdinBuffer:
    def __init__(self, raw: bytes):
        self._raw = raw

    def read(self) -> bytes:
        return self._raw


class _FakeStdin:
    def __init__(self, raw: bytes):
        self.buffer = _FakeStdinBuffer(raw)

    def isatty(self) -> bool:
        return False


class TestStdinDecoding:
    def test_read_stdin_utf8(self, monkeypatch):
        """_read_stdin decodes UTF-8 bytes correctly."""
        monkeypatch.setattr(sys, "stdin", _FakeStdin("中文内容".encode("utf-8")))
        assert _read_stdin() == "中文内容"

    def test_read_stdin_gbk_fallback(self, monkeypatch):
        """_read_stdin falls back to GB18030 when bytes are not UTF-8."""
        monkeypatch.setattr(sys, "stdin", _FakeStdin("中文内容".encode("gb18030")))
        assert _read_stdin() == "中文内容"

    def test_read_stdin_pinned_encoding(self, monkeypatch):
        """SIYUAN_STDIN_ENCODING pins the pipe encoding for GB18030/UTF-8 ambiguity.

        毛 is c3 ab in GB18030, which is also valid UTF-8 (ë), so the fallback
        never triggers without an explicit encoding.
        """
        monkeypatch.setattr(sys, "stdin", _FakeStdin("毛".encode("gb18030")))
        monkeypatch.setenv("SIYUAN_STDIN_ENCODING", "gb18030")
        assert _read_stdin() == "毛"

    def test_read_stdin_pinned_bad_encoding_errors(self, monkeypatch):
        """An unknown pinned encoding is a usage error, not a silent fallback."""
        monkeypatch.setattr(sys, "stdin", _FakeStdin("中文".encode("utf-8")))
        monkeypatch.setenv("SIYUAN_STDIN_ENCODING", "no-such-codec")
        with pytest.raises(UsageError):
            _read_stdin()

    def test_read_stdin_undecodable_errors(self, monkeypatch):
        """Bytes that fit neither candidate are refused, not stored as mojibake."""
        monkeypatch.setattr(sys, "stdin", _FakeStdin(b"\xff\xfe\x81"))
        with pytest.raises(UsageError) as exc:
            _read_stdin()
        assert "SIYUAN_STDIN_ENCODING" in str(exc.value)


# ── REPL delete confirmation and --file ────────────────────────────────


class TestReplDeleteConfirmation:
    def test_notebook_remove_requires_dangerous(self):
        """REPL notebook remove refuses without --dangerous."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        _handle_notebook_repl(skin, client, session, ["notebook", "remove", "nb1"], False, False)
        client.remove_notebook.assert_not_called()
        skin.error.assert_called_once()

    def test_notebook_remove_with_dangerous(self):
        """REPL notebook remove proceeds with --dangerous."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        _handle_notebook_repl(skin, client, session, ["notebook", "remove", "nb1"], False, True)
        client.remove_notebook.assert_called_once_with("nb1")

    def test_doc_remove_requires_dangerous(self):
        """REPL doc remove refuses without --dangerous."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        _handle_doc_repl(skin, client, session, ["doc", "remove", "doc1"], False, False)
        client.remove_doc_by_id.assert_not_called()
        skin.error.assert_called_once()

    def test_doc_remove_with_dangerous(self):
        """REPL doc remove proceeds with --dangerous."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        _handle_doc_repl(skin, client, session, ["doc", "remove", "doc1"], False, True)
        client.remove_doc_by_id.assert_called_once_with("doc1")

    def test_block_delete_requires_dangerous(self):
        """REPL block delete refuses without --dangerous."""
        skin = MagicMock()
        client = MagicMock()
        _handle_block_repl(skin, client, ["block", "delete", "b1"], False, False)
        client.delete_block.assert_not_called()
        skin.error.assert_called_once()

    def test_block_delete_with_dangerous(self):
        """REPL block delete proceeds with --dangerous."""
        skin = MagicMock()
        client = MagicMock()
        _handle_block_repl(skin, client, ["block", "delete", "b1"], False, True)
        client.delete_block.assert_called_once_with("b1")


class TestReplDangerousParsing:
    """--dangerous is parsed only for deletion commands in the dispatcher."""

    def _dispatch(self, cmd):
        skin = MagicMock()
        ctx = MagicMock()
        ctx.client = MagicMock()
        ctx.session = MagicMock()
        _dispatch_repl(skin, ctx, cmd)
        return skin, ctx

    def test_notebook_remove_parses_dangerous(self):
        """notebook remove --dangerous reaches the handler as confirmation."""
        skin, ctx = self._dispatch("notebook remove nb1 --dangerous")
        ctx.client.remove_notebook.assert_called_once_with("nb1")
        skin.error.assert_not_called()

    def test_notebook_remove_without_dangerous_refuses(self):
        """notebook remove without --dangerous is refused."""
        skin, ctx = self._dispatch("notebook remove nb1")
        ctx.client.remove_notebook.assert_not_called()
        skin.error.assert_called_once()

    def test_doc_remove_parses_dangerous(self):
        """doc remove --dangerous reaches the handler as confirmation."""
        skin, ctx = self._dispatch("doc remove doc1 --dangerous")
        ctx.client.remove_doc_by_id.assert_called_once_with("doc1")
        skin.error.assert_not_called()

    def test_block_delete_parses_dangerous(self):
        """block delete --dangerous reaches the handler as confirmation."""
        skin, ctx = self._dispatch("block delete b1 --dangerous")
        ctx.client.delete_block.assert_called_once_with("b1")
        skin.error.assert_not_called()

    def test_block_delete_without_dangerous_refuses(self):
        """block delete without --dangerous is refused."""
        skin, ctx = self._dispatch("block delete b1")
        ctx.client.delete_block.assert_not_called()
        skin.error.assert_called_once()

    def test_dangerous_rejected_for_non_delete(self):
        """--dangerous outside a delete command is an error, not content."""
        skin, ctx = self._dispatch("search --dangerous")
        ctx.client.search_blocks.assert_not_called()
        skin.error.assert_called_once()

    def test_dangerous_rejected_for_block_insert(self):
        """--dangerous is not valid outside delete commands."""
        skin, ctx = self._dispatch("block insert p --dangerous")
        ctx.client.insert_block.assert_not_called()
        skin.error.assert_called_once()


class TestReplBlockFile:
    def test_block_update_with_file(self, tmp_path):
        """REPL block update --file reads UTF-8 content from a file."""
        skin = MagicMock()
        client = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("更新后的中文内容", encoding="utf-8")

        _handle_block_repl(skin, client, ["block", "update", "b1", "--file", str(note)], False, False)
        client.update_block.assert_called_once_with("markdown", "更新后的中文内容", "b1")

    def test_block_insert_with_file(self, tmp_path):
        """REPL block insert --file reads UTF-8 content from a file."""
        skin = MagicMock()
        client = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("文件内容", encoding="utf-8")

        _handle_block_repl(skin, client, ["block", "insert", "p", "--file", str(note)], False, False)
        client.insert_block.assert_called_once_with("markdown", "文件内容", parent_id="p")

    def test_block_update_data_and_file_conflict(self, tmp_path):
        """REPL block update with positional data + --file is rejected."""
        skin = MagicMock()
        client = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("文件内容", encoding="utf-8")

        _handle_block_repl(skin, client, ["block", "update", "b1", "inline", "--file", str(note)], False, False)
        client.update_block.assert_not_called()
        skin.error.assert_called_once()
        assert "not both" in skin.error.call_args[0][0].lower()

    def test_block_update_dangling_file_flag(self):
        """REPL block update --file without a value is rejected."""
        skin = MagicMock()
        client = MagicMock()

        _handle_block_repl(skin, client, ["block", "update", "b1", "--file"], False, False)
        client.update_block.assert_not_called()
        skin.error.assert_called_once()
        assert "value" in skin.error.call_args[0][0].lower()

    def test_block_prepend_with_file(self, tmp_path):
        """REPL block prepend --file reads UTF-8 content from a file."""
        skin = MagicMock()
        client = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("前置内容", encoding="utf-8")

        _handle_block_repl(skin, client, ["block", "prepend", "p", "--file", str(note)], False, False)
        client.prepend_block.assert_called_once_with("markdown", "前置内容", "p")

    def test_block_append_with_file(self, tmp_path):
        """REPL block append --file reads UTF-8 content from a file."""
        skin = MagicMock()
        client = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("追加内容", encoding="utf-8")

        _handle_block_repl(skin, client, ["block", "append", "p", "--file", str(note)], False, False)
        client.append_block.assert_called_once_with("markdown", "追加内容", "p")


class TestReplBlockMissingContent:
    def test_block_update_without_content_refuses(self):
        """REPL block update without data or --file is rejected, not erasing the block."""
        skin = MagicMock()
        client = MagicMock()

        _handle_block_repl(skin, client, ["block", "update", "b1"], False, False)
        client.update_block.assert_not_called()
        skin.error.assert_called_once()

    def test_block_update_explicit_empty_preserved(self):
        """REPL `block update b1 \"\"` keeps the intentional empty payload (clears block)."""
        skin = MagicMock()
        client = MagicMock()

        _handle_block_repl(skin, client, ["block", "update", "b1", ""], False, False)
        client.update_block.assert_called_once_with("markdown", "", "b1")
        skin.error.assert_not_called()

    def test_block_insert_without_content_refuses(self):
        """REPL block insert without data or --file is rejected."""
        skin = MagicMock()
        client = MagicMock()

        _handle_block_repl(skin, client, ["block", "insert", "p"], False, False)
        client.insert_block.assert_not_called()
        skin.error.assert_called_once()

    def test_block_prepend_without_content_refuses(self):
        """REPL block prepend without data or --file is rejected."""
        skin = MagicMock()
        client = MagicMock()

        _handle_block_repl(skin, client, ["block", "prepend", "p"], False, False)
        client.prepend_block.assert_not_called()
        skin.error.assert_called_once()

    def test_block_append_without_content_refuses(self):
        """REPL block append without data or --file is rejected."""
        skin = MagicMock()
        client = MagicMock()

        _handle_block_repl(skin, client, ["block", "append", "p"], False, False)
        client.append_block.assert_not_called()
        skin.error.assert_called_once()


class TestReplDocCreateFile:
    def test_doc_create_with_file(self, tmp_path):
        """REPL doc create --file reads UTF-8 content from a file."""
        skin = MagicMock()
        client = MagicMock()
        client.create_doc_with_md.return_value = "doc123"
        session = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("# 标题\n\n正文", encoding="utf-8")

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "/test", "--file", str(note)],
            False, False,
        )
        client.create_doc_with_md.assert_called_once_with("nb1", "/test", "# 标题\n\n正文")

    def test_doc_create_file_then_md_conflict(self, tmp_path):
        """--file before --md still reports the mutual-exclusion error."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("from file", encoding="utf-8")

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "/test", "--file", str(note), "--md", "inline"],
            False, False,
        )
        client.create_doc_with_md.assert_not_called()
        skin.error.assert_called_once()
        assert "either" in skin.error.call_args[0][0].lower()

    def test_doc_create_md_then_file_conflict(self, tmp_path):
        """--md before --file reports the mutual-exclusion error."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("from file", encoding="utf-8")

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "/test", "--md", "inline", "--file", str(note)],
            False, False,
        )
        client.create_doc_with_md.assert_not_called()
        skin.error.assert_called_once()
        assert "either" in skin.error.call_args[0][0].lower()

    def test_doc_create_dangling_file_flag(self):
        """REPL doc create --file without a value is rejected."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "/test", "--file"],
            False, False,
        )
        client.create_doc_with_md.assert_not_called()
        skin.error.assert_called_once()
        assert "value" in skin.error.call_args[0][0].lower()

    def test_doc_create_dangling_md_flag(self):
        """REPL doc create --md without a value is rejected."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "/test", "--md"],
            False, False,
        )
        client.create_doc_with_md.assert_not_called()
        skin.error.assert_called_once()
        assert "value" in skin.error.call_args[0][0].lower()

    def test_doc_create_missing_path_after_file_reports_usage(self, tmp_path):
        """doc create nb1 --file x (missing path) reports usage, not IndexError."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("from file", encoding="utf-8")

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "--file", str(note)],
            False, False,
        )
        client.create_doc_with_md.assert_not_called()
        skin.error.assert_called_once()
        assert "usage" in skin.error.call_args[0][0].lower()

    def test_doc_create_missing_path_after_md_reports_usage(self):
        """doc create nb1 --md x (missing path) reports usage, not IndexError."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "--md", "content"],
            False, False,
        )
        client.create_doc_with_md.assert_not_called()
        skin.error.assert_called_once()
        assert "usage" in skin.error.call_args[0][0].lower()

    def test_doc_create_stdin_sentinel_with_file_conflict(self, tmp_path):
        """--md - combined with --file is rejected, not silently preferring the file."""
        skin = MagicMock()
        client = MagicMock()
        session = MagicMock()
        note = tmp_path / "note.md"
        note.write_text("from file", encoding="utf-8")

        _handle_doc_repl(
            skin, client, session,
            ["doc", "create", "nb1", "/test", "--md", "-", "--file", str(note)],
            False, False,
        )
        client.create_doc_with_md.assert_not_called()
        skin.error.assert_called_once()


class TestDocCreateContentConflict:
    def test_one_shot_stdin_sentinel_with_file_conflict(self, runner, mock_ctx, tmp_path):
        """one-shot doc create --md - --file is rejected, not silently preferring the file."""
        note = tmp_path / "note.md"
        note.write_text("from file", encoding="utf-8")
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(
                cli, ["doc", "create", "nb1", "/test", "--md", "-", "--file", str(note)]
            )
            assert result.exit_code == 2
            assert "both" in result.output.lower()
            mock_ctx.client.create_doc_with_md.assert_not_called()

    def test_explicit_empty_md_with_file_conflict(self, runner, mock_ctx, tmp_path):
        """`--md "" --file x` gives both sources; emptiness must not decide."""
        note = tmp_path / "note.md"
        note.write_text("from file", encoding="utf-8")
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(
                cli, ["doc", "create", "nb1", "/test", "--md", "", "--file", str(note)]
            )
            assert result.exit_code == 2
            assert "both" in result.output.lower()
            mock_ctx.client.create_doc_with_md.assert_not_called()

    def test_empty_md_alone_is_accepted(self, runner, mock_ctx):
        """`--md ""` on its own is an empty document, not a missing argument."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["doc", "create", "nb1", "/test", "--md", ""])
        assert result.exit_code == 0
        mock_ctx.client.create_doc_with_md.assert_called_once_with("nb1", "/test", "")


class TestBlockContentConflict:
    def test_insert_rejects_two_anchors(self, runner, mock_ctx):
        """The kernel applies nextID > previousID > parentID and drops the rest."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(
                cli, ["block", "insert", "hi", "--parent", "p1", "--previous", "p2"]
            )
        assert result.exit_code == 2
        assert "exactly one anchor" in result.output
        mock_ctx.client.insert_block.assert_not_called()

    def test_insert_rejects_three_anchors(self, runner, mock_ctx):
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, [
                "block", "insert", "hi", "--parent", "p1", "--previous", "p2", "--next", "p3"])
        assert result.exit_code == 2
        mock_ctx.client.insert_block.assert_not_called()

    def test_insert_with_one_anchor_still_works(self, runner, mock_ctx):
        mock_ctx.client.insert_block.return_value = []
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "insert", "hi", "--previous", "p2"])
        assert result.exit_code == 0
        mock_ctx.client.insert_block.assert_called_once_with(
            "markdown", "hi", parent_id="", previous_id="p2", next_id="")

    def test_block_insert_data_and_file_conflict(self, runner, mock_ctx, tmp_path):
        """block insert positional data + --file is rejected."""
        note = tmp_path / "note.md"
        note.write_text("file content", encoding="utf-8")
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(
                cli, ["block", "insert", "inline", "--parent", "p", "--file", str(note)]
            )
            assert result.exit_code == 2
            assert "not both" in result.output.lower()
            mock_ctx.client.insert_block.assert_not_called()

    def test_block_update_data_and_file_conflict(self, runner, mock_ctx, tmp_path):
        """block update positional data + --file is rejected."""
        note = tmp_path / "note.md"
        note.write_text("file content", encoding="utf-8")
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(
                cli, ["block", "update", "b1", "inline", "--file", str(note)]
            )
            assert result.exit_code == 2
            assert "not both" in result.output.lower()
            mock_ctx.client.update_block.assert_not_called()

    def test_empty_file_value_is_an_error_not_the_pipe(self, runner, mock_ctx):
        """`--file=` names no file; it must not quietly fall through to stdin."""
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "update", "b1", "--file="],
                                   input="piped content")
        assert result.exit_code == 2
        assert "Cannot read file ''" in result.output
        mock_ctx.client.update_block.assert_not_called()

    def test_empty_file_value_with_data_is_an_error_too(self, runner, mock_ctx):
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["block", "update", "b1", "inline", "--file="])
        assert result.exit_code == 2
        mock_ctx.client.update_block.assert_not_called()




class TestReplTokenizer:
    def test_windows_path_backslash_kept(self):
        """Windows --file paths keep their backslashes through tokenizing."""
        tokens = _tokenize_repl(r"block update b1 --file C:\data\note.md")
        assert r"C:\data\note.md" in tokens

    def test_quoted_multiword_kept(self):
        """Double-quoted values survive as a single token."""
        tokens = _tokenize_repl('doc create nb /x --md "hello world"')
        assert "hello world" in tokens


class TestReplDispatchRobustness:
    def _dispatch(self, cmd):
        skin = MagicMock()
        ctx = MagicMock()
        ctx.client = MagicMock()
        ctx.session = MagicMock()
        _dispatch_repl(skin, ctx, cmd)
        return skin, ctx

    def test_misplaced_json_switch_rejected(self):
        """A --json anywhere but the front is an error, not data."""
        skin, ctx = self._dispatch("block insert p -- --json hello")
        ctx.client.insert_block.assert_not_called()
        skin.error.assert_called_once()

    def test_bare_export_reports_usage(self):
        """`export` alone shows usage instead of an IndexError."""
        skin, ctx = self._dispatch("export")
        ctx.client.export_md_content.assert_not_called()
        skin.error.assert_called_once()


class TestMutationJsonOutput:
    def test_block_update_json(self, runner, mock_ctx):
        """--json block update emits a machine-readable object."""
        mock_ctx.json_output = True
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "block", "update", "b1", "text"])
            assert result.exit_code == 0
            assert json.loads(result.output) == {"updated": "b1"}

    def test_block_delete_json(self, runner, mock_ctx):
        """--json block delete emits a machine-readable object."""
        mock_ctx.json_output = True
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanContext", return_value=mock_ctx):
            result = runner.invoke(cli, ["--json", "block", "delete", "b1", "--dangerous"])
            assert result.exit_code == 0
            assert json.loads(result.output) == {"deleted": "b1"}


class TestReplBlockChildrenAlias:
    def test_children_alias_accepted(self):
        """REPL accepts the plural `block children` subcommand (matches one-shot)."""
        skin = MagicMock()
        client = MagicMock()
        _handle_block_repl(skin, client, ["block", "children", "b1"], False, False)
        client.get_child_blocks.assert_called_once_with("b1")


class TestReplJsonFlag:
    def _dispatch(self, cmd):
        skin = MagicMock()
        ctx = MagicMock()
        ctx.client = MagicMock()
        ctx.session = MagicMock()
        _dispatch_repl(skin, ctx, cmd)
        return skin, ctx

    def test_leading_json_switch(self):
        """A leading --json switches to JSON mode (one-shot parity)."""
        skin = MagicMock()
        ctx = MagicMock()
        ctx.client = MagicMock()
        ctx.session = MagicMock()
        ctx.client.list_notebooks.return_value = [
            {"id": "nb1", "name": "N", "closed": False}]
        _dispatch_repl(skin, ctx, "--json notebook list")
        ctx.client.list_notebooks.assert_called_once()
        skin.table.assert_not_called()

    def test_json_switch_must_lead(self):
        """--json mid-command is rejected; it works only as the first token."""
        skin, ctx = self._dispatch("block insert p --json hello")
        ctx.client.insert_block.assert_not_called()
        skin.error.assert_called_once()

    def test_option_value_may_look_like_a_flag(self):
        """A --md value that is literally "--json" is data, not a switch."""
        skin, ctx = self._dispatch('doc create nb1 /x --md "--json"')
        ctx.client.create_doc_with_md.assert_called_once_with("nb1", "/x", "--json")
        skin.error.assert_not_called()


class TestReplUnmatchedQuote:
    def test_unmatched_quote_rejected(self):
        """An unclosed quote is rejected before dispatch, not run as data."""
        skin = MagicMock()
        ctx = MagicMock()
        ctx.client = MagicMock()
        ctx.session = MagicMock()
        _dispatch_repl(skin, ctx, 'block update b1 "new text')
        ctx.client.update_block.assert_not_called()
        skin.error.assert_called_once()


# ── the global flags reach the context through the real group callback ──


class TestGlobalFlagWiring:
    """Drive `cli()` itself instead of handing the command a made-up context.

    The other tests patch `SiYuanContext` outright and set `json_output` by
    hand, so the `--json` -> context line had no coverage at all: it could stop
    crossing over and every one of them would still pass.
    """

    @pytest.fixture
    def client(self):
        client = MagicMock()
        client.list_notebooks.return_value = [
            {"id": "nb1", "name": "N", "closed": False}]
        with patch("cli_anything.siyuan.siyuan_cli.SiYuanClient",
                   return_value=client):
            yield client

    def test_json_flag_reaches_the_command(self, runner, client):
        result = runner.invoke(cli, ["--json", "notebook", "list"])
        assert result.exit_code == 0
        assert json.loads(result.output) == [
            {"id": "nb1", "name": "N", "closed": False}]

    def test_without_the_flag_the_output_is_plain_text(self, runner, client):
        result = runner.invoke(cli, ["notebook", "list"])
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.output)

    def test_repeated_global_option_is_rejected(self, runner, client):
        result = runner.invoke(
            cli, ["--host", "a", "--host", "b", "notebook", "list"])
        assert result.exit_code == 2
        assert "more than once" in result.output

    def test_non_numeric_port_is_rejected(self, runner, client):
        result = runner.invoke(cli, ["--port", "abc", "notebook", "list"])
        assert result.exit_code == 2
        client.list_notebooks.assert_not_called()
