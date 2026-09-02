"""Unit tests for cli-anything-siyuan CLI commands.

Tests CLI output formatting using Click's CliRunner with mocked client.
No external dependencies or running SiYuan instance required.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.siyuan.siyuan_cli import (
    _handle_block_repl,
    _handle_doc_repl,
    _handle_notebook_repl,
    _read_stdin,
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

    def test_read_stdin_pinned_bad_encoding_falls_back(self, monkeypatch):
        """An invalid pinned encoding falls back to utf-8-sig."""
        monkeypatch.setattr(sys, "stdin", _FakeStdin("中文".encode("utf-8")))
        monkeypatch.setenv("SIYUAN_STDIN_ENCODING", "no-such-codec")
        assert _read_stdin() == "中文"


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


class TestBlockContentConflict:
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


