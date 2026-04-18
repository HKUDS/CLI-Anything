"""Unit tests for cli-anything-browser — Core modules with mocked MCP backend.

These tests use synthetic data and mock the MCP backend. No Chrome or DOMShell required.

Usage:
    python -m pytest cli_anything/browser/tests/test_core.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli_anything.browser.core.session import Session
from cli_anything.browser.core import page, fs
from cli_anything.browser.utils.repl_skin import ReplSkin


@pytest.fixture(autouse=True)
def force_non_daemon(monkeypatch):
    """Keep unit tests isolated from any real daemon running on the machine."""
    monkeypatch.setattr(fs.backend, "daemon_started", lambda: False)


class TestReplSkin:
    """Test compact REPL prompt/help formatting."""

    def test_prompt_is_plain_text(self):
        skin = ReplSkin("browser", version="1.0.0")
        assert skin.prompt(context="https://example.com /") == "browser [https://example.com /] > "

    def test_help_is_compact(self, capsys):
        skin = ReplSkin("browser", version="1.0.0")
        skin.help({"page": "open|reload", "fs": "ls|cd|cat|grep|pwd"})
        out = capsys.readouterr().out
        assert out == "Commands:\n  page  open|reload\n  fs    ls|cd|cat|grep|pwd\n\n"

    def test_banner_and_goodbye_are_compact(self, capsys):
        skin = ReplSkin("browser", version="1.0.0")
        skin.print_banner()
        skin.print_goodbye()
        out = capsys.readouterr().out
        assert "Browser v1.0.0" in out
        assert "Type help for commands, quit to exit" in out
        assert "Goodbye!" in out
        assert "╭" not in out
        assert "◆" not in out


# ── Session Tests ────────────────────────────────────────────────

class TestSession:
    """Test Session state management."""

    def test_session_initial_state(self):
        """Session starts with empty state."""
        sess = Session()
        assert sess.current_url == ""
        assert sess.working_dir == "/"
        assert sess.history == []
        assert sess.forward_stack == []
        assert not sess.daemon_mode

    def test_set_url(self):
        """Setting URL updates state and records history."""
        sess = Session()
        sess.set_url("https://example.com")
        assert sess.current_url == "https://example.com"
        assert sess.history == []

    def test_set_url_with_history(self):
        """Setting URL with history=True records previous URL."""
        sess = Session()
        sess.set_url("https://first.com")
        sess.set_url("https://second.com")
        assert sess.history == ["https://first.com"]
        assert sess.current_url == "https://second.com"

    def test_set_url_clears_forward_stack(self):
        """Setting URL clears forward stack."""
        sess = Session()
        sess.set_url("https://first.com")
        sess.set_url("https://second.com", record_history=True)
        sess.go_back()
        sess.set_url("https://third.com")
        assert sess.forward_stack == []

    def test_go_back(self):
        """Going back pops from history and pushes to forward stack."""
        sess = Session()
        sess.set_url("https://first.com")
        sess.set_url("https://second.com")
        sess.set_url("https://third.com")

        previous = sess.go_back()
        assert previous == "https://second.com"
        assert sess.current_url == "https://second.com"
        assert sess.history == ["https://first.com"]
        assert sess.forward_stack == ["https://third.com"]

    def test_go_back_empty_history(self):
        """Going back with empty history returns None."""
        sess = Session()
        result = sess.go_back()
        assert result is None

    def test_go_forward(self):
        """Going forward pops from forward stack and pushes to history."""
        sess = Session()
        sess.set_url("https://first.com")
        sess.set_url("https://second.com")
        sess.go_back()
        sess.go_back()  # Now at first.com

        next_url = sess.go_forward()
        assert next_url == "https://second.com"
        assert sess.current_url == "https://second.com"
        assert sess.history == ["https://first.com"]
        assert sess.forward_stack == []

    def test_go_forward_empty_stack(self):
        """Going forward with empty stack returns None."""
        sess = Session()
        result = sess.go_forward()
        assert result is None

    def test_set_working_dir(self):
        """Setting working dir updates state."""
        sess = Session()
        sess.set_working_dir("/main/div[0]")
        assert sess.working_dir == "/main/div[0]"

    def test_daemon_mode(self):
        """Daemon mode flag can be toggled."""
        sess = Session()
        assert not sess.daemon_mode

        sess.enable_daemon()
        assert sess.daemon_mode

        sess.disable_daemon()
        assert not sess.daemon_mode

    def test_status(self):
        """Status returns current state as dict."""
        sess = Session()
        sess.set_url("https://example.com")
        sess.set_working_dir("/main")

        status = sess.status()
        assert status["current_url"] == "https://example.com"
        assert status["working_dir"] == "/main"
        assert status["history_length"] == 0
        assert status["forward_stack_length"] == 0
        assert not status["daemon_mode"]

    def test_persisted_session_round_trip(self, tmp_path):
        """Persistent sessions can round-trip to disk."""
        state_file = tmp_path / "session.json"
        sess = Session(persist_state=True, state_path=str(state_file))
        sess.enable_daemon()
        sess.set_url("https://example.com")
        sess.set_working_dir("/main")
        sess.set_url("https://example.org")

        loaded = Session.load_persisted(str(state_file))
        assert loaded.daemon_mode is True
        assert loaded.current_url == "https://example.org"
        assert loaded.working_dir == "/main"
        assert loaded.history == ["https://example.com"]
        assert loaded.forward_stack == []


# ── Page Module Tests ────────────────────────────────────────────

class TestPageModule:
    """Test page command functions."""

    def test_open_page_updates_session(self):
        """Opening a page updates session state."""
        sess = Session()

        with patch("cli_anything.browser.core.page.backend.open_url") as mock_open:
            mock_open.return_value = {"url": "https://example.com", "status": "loaded"}

            result = page.open_page(sess, "https://example.com")

            assert sess.current_url == "https://example.com"
            assert sess.working_dir == "/"  # Reset on new page

    def test_reload_page(self):
        """Reloading page calls backend."""
        sess = Session()
        sess.set_url("https://example.com")

        with patch("cli_anything.browser.core.page.backend.reload") as mock_reload:
            mock_reload.return_value = {"status": "reloaded"}

            result = page.reload_page(sess)
            assert result["status"] == "reloaded"

    def test_go_back_updates_session(self):
        """Going back updates session and calls backend."""
        sess = Session()
        sess.set_url("https://first.com")
        sess.set_url("https://second.com")

        with patch("cli_anything.browser.core.page.backend.back") as mock_back:
            mock_back.return_value = {"url": "https://first.com", "status": "navigated"}

            result = page.go_back(sess)

            assert sess.current_url == "https://first.com"
            assert result["url"] == "https://first.com"

    def test_go_back_empty_history(self):
        """Going back with empty history returns error."""
        sess = Session()

        with patch("cli_anything.browser.core.page.backend.back") as mock_back:
            mock_back.return_value = {"error": "No history"}

            result = page.go_back(sess)
            assert "error" in result

    def test_go_forward_updates_session(self):
        """Going forward updates session and calls backend."""
        sess = Session()
        sess.set_url("https://first.com")
        sess.set_url("https://second.com")
        sess.go_back()  # Now at first.com

        with patch("cli_anything.browser.core.page.backend.forward") as mock_forward:
            mock_forward.return_value = {"url": "https://second.com", "status": "navigated"}

            result = page.go_forward(sess)

            assert sess.current_url == "https://second.com"

    def test_get_page_info(self):
        """Getting page info returns current state."""
        sess = Session()
        sess.set_url("https://example.com")
        sess.set_working_dir("/main")

        result = page.get_page_info(sess)
        assert result["url"] == "https://example.com"
        assert result["working_dir"] == "/main"

    def test_open_page_rejects_error_payload(self):
        """Open page should not mutate session on backend error payloads."""
        sess = Session()
        sess.set_url("https://first.com")
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.page.backend.open_url") as mock_open:
            mock_open.return_value = {
                "content": [{"type": "text", "text": "Could not open"}],
                "isError": False,
            }

            result = page.open_page(sess, "https://second.com")

            assert sess.current_url == "https://first.com"
            assert sess.working_dir == "/main"
            assert result["isError"] is False
            mock_open.assert_called_once_with("https://second.com", use_daemon=False)

    def test_act_click_rejects_error_payload(self):
        """CLI click should not claim success on backend error payloads."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_anything.browser.browser_cli.backend.click") as mock_click:
            mock_click.return_value = {
                "content": [{"type": "text", "text": "click: /main/does-not-exist: No such element"}],
                "isError": False,
            }
            result = runner.invoke(cli, ["act", "click", "/main/does-not-exist"])
            assert result.exit_code == 0
            assert "Clicked:" not in result.output
            assert "No such element" in result.output

    def test_act_type_rejects_error_payload(self):
        """CLI type should not claim success on backend error payloads."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_anything.browser.browser_cli.backend.type_text") as mock_type:
            mock_type.return_value = {
                "content": [{"type": "text", "text": "type failed: input not found"}],
                "isError": False,
            }
            result = runner.invoke(cli, ["act", "type", "/main/does-not-exist", "hello"])
            assert result.exit_code == 0
            assert "Typed into:" not in result.output
            assert "input not found" in result.output

    def test_type_text_preflight_blocks_invalid_path(self):
        """type_text should return fast on invalid paths instead of hanging."""
        from cli_anything.browser.utils import domshell_backend as backend

        with patch("cli_anything.browser.utils.domshell_backend.cat") as mock_cat, \
             patch("cli_anything.browser.utils.domshell_backend.asyncio.run") as mock_run:
            mock_cat.return_value = {
                "content": [{"type": "text", "text": "cat: /main/does-not-exist: No such file or directory"}],
                "isError": False,
            }
            mock_run.side_effect = AssertionError("asyncio.run should not be called for invalid paths")
            result = backend.type_text("/main/does-not-exist", "hello", use_daemon=True)
            assert isinstance(result, dict)
            assert "No such file or directory" in result["content"][0]["text"]

    def test_page_reload_rejects_error_payload(self):
        """Reload should not claim success on backend error payloads."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_anything.browser.browser_cli.page_mod.reload_page") as mock_reload:
            mock_reload.return_value = {
                "content": [{"type": "text", "text": "reload failed: could not refresh"}],
                "isError": False,
            }
            result = runner.invoke(cli, ["page", "reload"])
            assert result.exit_code == 0
            assert "Page reloaded" not in result.output
            assert "reload failed" in result.output
            assert "content:" not in result.output
            assert "isError" not in result.output

    def test_page_back_rejects_error_payload(self):
        """Back should not claim success on backend error payloads."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_anything.browser.browser_cli.page_mod.go_back") as mock_back:
            mock_back.return_value = {
                "content": [{"type": "text", "text": "back failed: No history"}],
                "isError": False,
            }
            result = runner.invoke(cli, ["page", "back"])
            assert result.exit_code == 0
            assert "Navigated back" not in result.output
            assert "No history" in result.output
            assert "content:" not in result.output
            assert "isError" not in result.output

    def test_fs_ls_rejects_error_payload(self):
        """ls should not claim success when backend returns an error payload."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_anything.browser.browser_cli.fs_mod.list_elements") as mock_ls:
            mock_ls.return_value = {
                "content": [{"type": "text", "text": "ls failed: No such directory"}],
                "isError": False,
            }
            result = runner.invoke(cli, ["fs", "ls", "/main"])
            assert result.exit_code == 0
            assert "No elements at" not in result.output
            assert "No such directory" in result.output
            assert "content:" not in result.output
            assert "isError" not in result.output

    def test_fs_cat_rejects_error_payload(self):
        """cat should show the backend error text instead of a fake success payload."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_anything.browser.browser_cli.fs_mod.read_element") as mock_cat:
            mock_cat.return_value = {
                "content": [{"type": "text", "text": "cat: /main/does-not-exist: No such file or directory"}],
                "isError": False,
            }
            result = runner.invoke(cli, ["fs", "cat", "/main/does-not-exist"])
            assert result.exit_code == 0
            assert "No such file or directory" in result.output
            assert "content:" not in result.output
            assert "isError" not in result.output

    def test_page_info_is_concise(self):
        """page info should render a concise summary instead of raw payload."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["page", "info"])
        assert result.exit_code == 0
        assert "URL:" in result.output
        assert "Working dir:" in result.output
        assert "current_url" not in result.output
        assert "working_dir" not in result.output
        assert "content:" not in result.output

    def test_session_status_is_concise(self):
        """session status should render a concise summary instead of raw payload."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["session", "status"])
        assert result.exit_code == 0
        assert "URL:" in result.output
        assert "Working dir:" in result.output
        assert "History:" in result.output
        assert "Forward:" in result.output
        assert "Daemon:" in result.output
        assert "current_url" not in result.output
        assert "forward_stack_length" not in result.output

    def test_session_daemon_start_is_concise(self):
        """daemon start should not print the payload dict in normal mode."""
        from cli_anything.browser.browser_cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_anything.browser.browser_cli.backend.start_daemon"):
            result = runner.invoke(cli, ["session", "daemon-start"])
            assert result.exit_code == 0
            assert "Daemon mode started" in result.output
            assert "daemon:" not in result.output

    def test_change_directory_rejects_text_error_payload(self):
        """cd should not update working_dir when backend returns an error text payload."""
        sess = Session()
        sess.set_working_dir("/")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd:
            mock_cd.return_value = {
                "content": [{"type": "text", "text": "cd: main: No such directory"}],
                "isError": False,
            }

            result = fs.change_directory(sess, "/main")

            assert sess.working_dir == "/"
            assert result["isError"] is False
            mock_cd.assert_called_once_with("/main", use_daemon=False)


# ── Filesystem Module Tests ───────────────────────────────────────

class TestFsModule:
    """Test filesystem command functions."""

    def test_list_elements(self):
        """Listing elements calls backend with session working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd, \
             patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_cd.return_value = {"path": "/main", "status": "changed"}
            mock_ls.return_value = {
                "path": "/main",
                "entries": [{"name": "button", "role": "button", "path": "/main/button[0]"}]
            }

            result = fs.list_elements(sess)

            mock_cd.assert_any_call("/main", use_daemon=False)
            mock_ls.assert_called_once_with("/main", use_daemon=False)

    def test_list_elements_with_path(self):
        """Listing elements with explicit path overrides working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd, \
             patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_cd.return_value = {"path": "/div", "status": "changed"}
            mock_ls.return_value = {"path": "/div", "entries": []}

            result = fs.list_elements(sess, "/div")

            mock_cd.assert_any_call("/div", use_daemon=False)
            mock_ls.assert_called_once_with("/div", use_daemon=False)

    def test_list_elements_empty_path_uses_working_dir(self):
        """Listing with empty path uses session working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd, \
             patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_cd.return_value = {"path": "/main", "status": "changed"}
            mock_ls.return_value = {"path": "/main", "entries": []}

            result = fs.list_elements(sess, "")

            mock_cd.assert_any_call("/main", use_daemon=False)
            mock_ls.assert_called_once_with("/main", use_daemon=False)

    def test_change_directory_absolute_path(self):
        """Changing to absolute path updates working_dir."""
        sess = Session()

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd:
            mock_cd.return_value = {"path": "/main", "status": "changed"}

            result = fs.change_directory(sess, "/main")

            assert sess.working_dir == "/main"
            mock_cd.assert_called_once_with("/main", use_daemon=False)

    def test_change_directory_relative_parent(self):
        """Changing to .. goes up one level."""
        sess = Session()
        sess.set_working_dir("/main/div[0]")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd:
            mock_cd.return_value = {"path": "/main", "status": "changed"}

            result = fs.change_directory(sess, "..")

            assert sess.working_dir == "/main"
            mock_cd.assert_called_once_with("/main", use_daemon=False)

    def test_change_directory_parent_from_root(self):
        """Changing to .. from root stays at root."""
        sess = Session()
        sess.set_working_dir("/")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd:
            result = fs.change_directory(sess, "..")

            assert result["error"] == "Already at root"

    def test_change_directory_current(self):
        """Changing to . stays in same directory."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd:
            mock_cd.return_value = {"path": "/main", "status": "changed"}

            result = fs.change_directory(sess, ".")

            assert sess.working_dir == "/main"

    def test_change_directory_relative_path(self):
        """Changing to relative path appends to working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.cd") as mock_cd:
            mock_cd.return_value = {"path": "/main/div[0]", "status": "changed"}

            result = fs.change_directory(sess, "div[0]")

            assert sess.working_dir == "/main/div[0]"
            mock_cd.assert_called_once_with("/main/div[0]", use_daemon=False)

    def test_read_element(self):
        """Reading element calls backend."""
        sess = Session()

        with patch("cli_anything.browser.core.fs.backend.cat") as mock_cat:
            mock_cat.return_value = {
                "name": "button",
                "role": "button",
                "text": "Click me"
            }

            result = fs.read_element(sess, "/main/button[0]")

            mock_cat.assert_called_once_with("/main/button[0]", use_daemon=False)

    def test_read_element_empty_path_uses_working_dir(self):
        """Reading with empty path uses session working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.cat") as mock_cat:
            mock_cat.return_value = {"name": "main", "role": "landmark"}

            result = fs.read_element(sess, "")

            mock_cat.assert_called_once_with("/main", use_daemon=False)

    def test_grep_elements(self):
        """Grepping calls backend with pattern."""
        sess = Session()

        with patch("cli_anything.browser.core.fs.backend.grep") as mock_grep:
            mock_grep.return_value = {
                "matches": ["/main/button[0]", "/main/link[1]"]
            }

            result = fs.grep_elements(sess, "Login")

            mock_grep.assert_called_once_with("Login", use_daemon=False)

    def test_grep_elements_with_path(self):
        """Grepping with path cds to that path first, then restores."""
        sess = Session()

        with patch("cli_anything.browser.core.fs.backend.grep") as mock_grep, \
             patch("cli_anything.browser.core.fs.backend.cd") as mock_cd:
            mock_grep.return_value = {"matches": ["/main/button[0]"]}
            mock_cd.return_value = {"path": "/main"}

            result = fs.grep_elements(sess, "Login", "/main")

            mock_grep.assert_called_once_with("Login", use_daemon=False)
            assert mock_cd.call_count == 2
            mock_cd.assert_any_call("/main", use_daemon=False)
            mock_cd.assert_any_call("/", use_daemon=False)


# ── Daemon Mode Tests ────────────────────────────────────────────

class TestDaemonMode:
    """Test daemon mode state propagation."""

    def test_daemon_mode_propagates_to_backend(self):
        """Commands use daemon mode when session.daemon_mode is True."""
        sess = Session()
        sess.enable_daemon()

        with patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_ls.return_value = {"path": "/", "entries": []}

            result = fs.list_elements(sess)

            mock_ls.assert_called_once_with("/", use_daemon=True)

    def test_normal_mode_does_not_use_daemon(self):
        """Commands don't use daemon mode when session.daemon_mode is False."""
        sess = Session()
        # daemon_mode defaults to False

        with patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_ls.return_value = {"path": "/", "entries": []}

            result = fs.list_elements(sess)

            mock_ls.assert_called_once_with("/", use_daemon=False)
