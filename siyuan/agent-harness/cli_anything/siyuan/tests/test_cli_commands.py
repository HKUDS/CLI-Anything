"""Unit tests for cli-anything-siyuan CLI commands.

Tests CLI output formatting using Click's CliRunner with mocked client.
No external dependencies or running SiYuan instance required.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.siyuan.siyuan_cli import cli


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
