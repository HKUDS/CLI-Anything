"""Unit tests for cli-anything-obsidian — no Obsidian server required."""

import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner


# ── Backend URL construction & API calls ─────────────────────────

class TestBackend:
    def test_default_base_url(self):
        from cli_anything.obsidian.utils.obsidian_backend import DEFAULT_BASE_URL
        assert DEFAULT_BASE_URL == "https://localhost:27124"

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.get")
    def test_is_available_true(self, mock_get):
        from cli_anything.obsidian.utils.obsidian_backend import is_available
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        assert is_available("test-key") is True
        mock_get.assert_called_once_with(
            "https://localhost:27124/",
            headers={"Authorization": "Bearer test-key"},
            timeout=5,
            verify=False,
        )

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.get")
    def test_is_available_false(self, mock_get):
        from cli_anything.obsidian.utils.obsidian_backend import is_available
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        assert is_available("test-key") is False

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.get")
    def test_api_get_connection_error(self, mock_get):
        from cli_anything.obsidian.utils.obsidian_backend import api_get
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Obsidian"):
            api_get("https://localhost:27124", "/", "test-key")

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.post")
    def test_api_post_connection_error(self, mock_post):
        from cli_anything.obsidian.utils.obsidian_backend import api_post
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Obsidian"):
            api_post("https://localhost:27124", "/search/", "test-key", data={"query": "test"})

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.post")
    def test_api_post_raw_sends_body_and_content_type(self, mock_post):
        from cli_anything.obsidian.utils.obsidian_backend import api_post_raw
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'[]'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        api_post_raw(
            "https://localhost:27124", "/search/", "test-key",
            body='TABLE file.link FROM "x"',
            content_type="application/vnd.olrapi.dataview.dql+txt",
        )
        mock_post.assert_called_once_with(
            "https://localhost:27124/search/",
            headers={
                "Authorization": "Bearer test-key",
                "Accept": "application/json",
                "Content-Type": "application/vnd.olrapi.dataview.dql+txt",
            },
            data=b'TABLE file.link FROM "x"',
            params=None,
            timeout=30,
            verify=False,
        )

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.post")
    def test_api_post_raw_connection_error(self, mock_post):
        from cli_anything.obsidian.utils.obsidian_backend import api_post_raw
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Obsidian"):
            api_post_raw("https://localhost:27124", "/search/", "test-key",
                         body="x", content_type="text/plain")

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.delete")
    def test_api_delete_connection_error(self, mock_delete):
        from cli_anything.obsidian.utils.obsidian_backend import api_delete
        import requests
        mock_delete.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Obsidian"):
            api_delete("https://localhost:27124", "/vault/test.md", "test-key")

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.get")
    def test_api_get_json_response(self, mock_get):
        from cli_anything.obsidian.utils.obsidian_backend import api_get
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"files": []}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"files": []}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        result = api_get("https://localhost:27124", "/vault/", "test-key")
        assert result == {"files": []}

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.get")
    def test_api_get_text_response(self, mock_get):
        from cli_anything.obsidian.utils.obsidian_backend import api_get
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"# My Note\nHello world"
        mock_resp.headers = {"content-type": "text/markdown"}
        mock_resp.text = "# My Note\nHello world"
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        result = api_get("https://localhost:27124", "/vault/test.md", "test-key")
        assert result == {"content": "# My Note\nHello world"}

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.get")
    def test_api_get_trailing_slash_stripped(self, mock_get):
        from cli_anything.obsidian.utils.obsidian_backend import api_get
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"status": "ok"}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        api_get("https://localhost:27124/", "/", "test-key")
        mock_get.assert_called_once_with(
            "https://localhost:27124/",
            headers={"Authorization": "Bearer test-key", "Accept": "application/json"},
            params=None,
            timeout=30,
            verify=False,
        )

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.get")
    def test_api_get_timeout(self, mock_get):
        from cli_anything.obsidian.utils.obsidian_backend import api_get
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        with pytest.raises(RuntimeError, match="timed out"):
            api_get("https://localhost:27124", "/", "test-key")

    @patch("cli_anything.obsidian.utils.obsidian_backend.requests.put")
    def test_api_put_text(self, mock_put):
        from cli_anything.obsidian.utils.obsidian_backend import api_put
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        mock_resp.raise_for_status.return_value = None
        mock_put.return_value = mock_resp
        result = api_put("https://localhost:27124", "/vault/test.md", "test-key", content="# Hello")
        assert result == {"status": "ok"}



# ── Core module tests ────────────────────────────────────────────

class TestServerModule:
    @patch("cli_anything.obsidian.core.server.api_get")
    def test_server_status(self, mock_api):
        from cli_anything.obsidian.core.server import server_status
        mock_api.return_value = {"status": "OK", "authenticated": True}
        result = server_status("https://localhost:27124", "test-key")
        assert result["status"] == "OK"
        mock_api.assert_called_once_with("https://localhost:27124", "/", "test-key")


class TestVaultModule:
    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_list_files_root(self, mock_api):
        from cli_anything.obsidian.core.vault import list_files
        mock_api.return_value = {"files": ["note1.md", "folder/note2.md"]}
        result = list_files("https://localhost:27124", "test-key")
        assert len(result["files"]) == 2
        mock_api.assert_called_once_with("https://localhost:27124", "/vault/", "test-key")

    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_list_files_subfolder(self, mock_api):
        from cli_anything.obsidian.core.vault import list_files
        mock_api.return_value = {"files": ["note2.md"]}
        result = list_files("https://localhost:27124", "test-key", path="folder")
        mock_api.assert_called_once_with("https://localhost:27124", "/vault/folder/", "test-key")

    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_read_note(self, mock_api):
        from cli_anything.obsidian.core.vault import read_note
        mock_api.return_value = {"content": "# Hello\nWorld"}
        result = read_note("https://localhost:27124", "test-key", "note.md")
        assert result["content"] == "# Hello\nWorld"

    @patch("cli_anything.obsidian.core.vault.api_put")
    def test_create_note(self, mock_api):
        from cli_anything.obsidian.core.vault import create_note
        mock_api.return_value = {"status": "ok"}
        result = create_note("https://localhost:27124", "test-key", "new.md", "# New")
        assert result["status"] == "ok"
        mock_api.assert_called_once_with(
            "https://localhost:27124", "/vault/new.md", "test-key", content="# New"
        )

    @patch("cli_anything.obsidian.core.vault.api_put")
    def test_update_note(self, mock_api):
        from cli_anything.obsidian.core.vault import update_note
        mock_api.return_value = {"status": "ok"}
        result = update_note("https://localhost:27124", "test-key", "note.md", "# Updated")
        assert result["status"] == "ok"

    @patch("cli_anything.obsidian.core.vault.api_delete")
    def test_delete_note(self, mock_api):
        from cli_anything.obsidian.core.vault import delete_note
        mock_api.return_value = {"status": "ok"}
        result = delete_note("https://localhost:27124", "test-key", "note.md")
        assert result["status"] == "ok"

    @patch("cli_anything.obsidian.core.vault.api_put")
    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_append_note(self, mock_get, mock_put):
        from cli_anything.obsidian.core.vault import append_note
        mock_get.return_value = {"content": "# Existing"}
        mock_put.return_value = {"status": "ok"}
        result = append_note("https://localhost:27124", "test-key", "note.md",
                            "\nnew content", position="end")
        assert result["status"] == "ok"
        mock_put.assert_called_once_with(
            "https://localhost:27124", "/vault/note.md", "test-key",
            content="# Existing\nnew content"
        )


class TestSearchModule:
    @patch("cli_anything.obsidian.core.search.api_post_raw")
    def test_search_query_default_dql(self, mock_api):
        from cli_anything.obsidian.core.search import search_query
        mock_api.return_value = [{"filename": "note.md", "score": 0.9}]
        search_query("https://localhost:27124", "test-key",
                     'TABLE file.link FROM "90-System"')
        mock_api.assert_called_once_with(
            "https://localhost:27124", "/search/", "test-key",
            body='TABLE file.link FROM "90-System"',
            content_type="application/vnd.olrapi.dataview.dql+txt",
        )

    @patch("cli_anything.obsidian.core.search.api_post_raw")
    def test_search_query_jsonlogic(self, mock_api):
        from cli_anything.obsidian.core.search import search_query
        mock_api.return_value = [{"filename": "note.md"}]
        body = '{"==":[{"var":"frontmatter.status"},"active"]}'
        search_query("https://localhost:27124", "test-key", body,
                     query_type="jsonlogic")
        mock_api.assert_called_once_with(
            "https://localhost:27124", "/search/", "test-key",
            body=body,
            content_type="application/vnd.olrapi.jsonlogic+json",
        )

    def test_search_query_invalid_type_raises(self):
        from cli_anything.obsidian.core.search import search_query
        with pytest.raises(ValueError, match="Unsupported search query_type"):
            search_query("https://localhost:27124", "test-key", "x",
                         query_type="grep")

    @patch("cli_anything.obsidian.core.search.api_post")
    def test_search_simple(self, mock_api):
        from cli_anything.obsidian.core.search import search_simple
        mock_api.return_value = [{"filename": "note.md", "matches": []}]
        result = search_simple("https://localhost:27124", "test-key", "hello", context_length=50)
        mock_api.assert_called_once_with(
            "https://localhost:27124", "/search/simple/", "test-key",
            params={"query": "hello", "contextLength": 50}
        )


class TestNoteModule:
    @patch("cli_anything.obsidian.core.note.api_get")
    def test_get_active(self, mock_api):
        from cli_anything.obsidian.core.note import get_active
        mock_api.return_value = {"content": "# Active Note"}
        result = get_active("https://localhost:27124", "test-key")
        assert result["content"] == "# Active Note"

    @patch("cli_anything.obsidian.core.note.api_put")
    def test_open_note(self, mock_api):
        from cli_anything.obsidian.core.note import open_note
        mock_api.return_value = {"status": "ok"}
        result = open_note("https://localhost:27124", "test-key", "folder/note.md")
        assert result["status"] == "ok"


class TestCommandModule:
    @patch("cli_anything.obsidian.core.command.api_get")
    def test_list_commands(self, mock_api):
        from cli_anything.obsidian.core.command import list_commands
        mock_api.return_value = {"commands": [{"id": "editor:toggle-bold", "name": "Bold"}]}
        result = list_commands("https://localhost:27124", "test-key")
        assert len(result["commands"]) == 1

    @patch("cli_anything.obsidian.core.command.api_post")
    def test_execute_command(self, mock_api):
        from cli_anything.obsidian.core.command import execute_command
        mock_api.return_value = {"status": "ok"}
        result = execute_command("https://localhost:27124", "test-key", "editor:toggle-bold")
        assert result["status"] == "ok"
        mock_api.assert_called_once_with(
            "https://localhost:27124", "/commands/editor:toggle-bold/", "test-key"
        )


# ── CLI tests ────────────────────────────────────────────────────

from cli_anything.obsidian.obsidian_cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIParsing:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Obsidian CLI" in result.output

    def test_vault_help(self, runner):
        result = runner.invoke(cli, ["vault", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "read" in result.output
        assert "create" in result.output
        assert "update" in result.output
        assert "delete" in result.output
        assert "append" in result.output

    def test_search_help(self, runner):
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output
        assert "simple" in result.output

    def test_note_help(self, runner):
        result = runner.invoke(cli, ["note", "--help"])
        assert result.exit_code == 0
        assert "active" in result.output
        assert "open" in result.output

    def test_command_help(self, runner):
        result = runner.invoke(cli, ["command", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "execute" in result.output

    def test_server_help(self, runner):
        result = runner.invoke(cli, ["server", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_session_help(self, runner):
        result = runner.invoke(cli, ["session", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_json_flag(self, runner):
        result = runner.invoke(cli, ["--json", "--api-key", "test", "session", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "host" in data

    def test_api_key_flag(self, runner):
        result = runner.invoke(cli, ["--json", "--api-key", "my-key", "session", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["api_key_set"] is True

    def test_host_flag(self, runner):
        result = runner.invoke(cli, ["--host", "https://example:1234", "--api-key", "k",
                                     "--json", "session", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["host"] == "https://example:1234"


class TestSessionState:
    def test_session_status_defaults(self, runner):
        result = runner.invoke(cli, ["--json", "--api-key", "test", "session", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["api_key_set"] is True


class TestVaultCommands:
    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_vault_list_json(self, mock_api, runner):
        mock_api.return_value = {"files": ["note1.md", "folder/note2.md"]}
        result = runner.invoke(cli, ["--json", "--api-key", "k", "vault", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "files" in data

    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_vault_read_json(self, mock_api, runner):
        mock_api.return_value = {"content": "# Hello"}
        result = runner.invoke(cli, ["--json", "--api-key", "k", "vault", "read", "note.md"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["content"] == "# Hello"

    @patch("cli_anything.obsidian.core.vault.api_put")
    def test_vault_create_json(self, mock_api, runner):
        mock_api.return_value = {"status": "ok"}
        result = runner.invoke(cli, ["--json", "--api-key", "k", "vault", "create",
                                     "new.md", "--content", "# New Note"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    @patch("cli_anything.obsidian.core.vault.api_delete")
    def test_vault_delete_json(self, mock_api, runner):
        mock_api.return_value = {"status": "ok"}
        result = runner.invoke(cli, ["--json", "--api-key", "k", "vault", "delete", "old.md"])
        assert result.exit_code == 0

    @patch("cli_anything.obsidian.core.vault.api_put")
    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_vault_append_json(self, mock_get, mock_put, runner):
        mock_get.return_value = {"content": "existing"}
        mock_put.return_value = {"status": "ok"}
        result = runner.invoke(cli, ["--json", "--api-key", "k", "vault", "append",
                                     "note.md", "--content", "extra text"])
        assert result.exit_code == 0


class TestSearchCommands:
    @patch("cli_anything.obsidian.core.search.api_post_raw")
    def test_search_query_json(self, mock_api, runner):
        mock_api.return_value = [{"filename": "note.md", "score": 0.9}]
        result = runner.invoke(cli, ["--json", "--api-key", "k", "search", "query", "test"])
        assert result.exit_code == 0
        # Default --type is dql; body should be sent verbatim
        args, kwargs = mock_api.call_args
        assert kwargs["body"] == "test"
        assert kwargs["content_type"] == "application/vnd.olrapi.dataview.dql+txt"

    @patch("cli_anything.obsidian.core.search.api_post_raw")
    def test_search_query_jsonlogic_flag(self, mock_api, runner):
        mock_api.return_value = [{"filename": "note.md"}]
        body = '{"==":[{"var":"frontmatter.status"},"active"]}'
        result = runner.invoke(cli, ["--json", "--api-key", "k",
                                     "search", "query", body,
                                     "--type", "jsonlogic"])
        assert result.exit_code == 0
        _, kwargs = mock_api.call_args
        assert kwargs["content_type"] == "application/vnd.olrapi.jsonlogic+json"
        assert kwargs["body"] == body

    @patch("cli_anything.obsidian.core.search.api_post")
    def test_search_simple_json(self, mock_api, runner):
        mock_api.return_value = [{"filename": "note.md", "matches": []}]
        result = runner.invoke(cli, ["--json", "--api-key", "k", "search", "simple", "hello"])
        assert result.exit_code == 0


class TestErrorHandling:
    @patch("cli_anything.obsidian.core.server.api_get")
    def test_server_status_error(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Obsidian")
        result = runner.invoke(cli, ["--api-key", "k", "server", "status"])
        assert result.exit_code == 1

    @patch("cli_anything.obsidian.core.server.api_get")
    def test_server_status_error_json(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Obsidian")
        result = runner.invoke(cli, ["--json", "--api-key", "k", "server", "status"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key(self, runner):
        result = runner.invoke(cli, ["server", "status"], env={"OBSIDIAN_API_KEY": ""})
        assert result.exit_code == 1

    @patch("cli_anything.obsidian.core.vault.api_get")
    def test_vault_list_error_json(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Obsidian")
        result = runner.invoke(cli, ["--json", "--api-key", "k", "vault", "list"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data
