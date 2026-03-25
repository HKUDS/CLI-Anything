"""Unit tests for cli-anything-browser — Core modules with mocked MCP backend.

These tests use synthetic data and mock the MCP backend. No Chrome or DOMShell required.

Usage:
    python -m pytest cli_anything/browser/tests/test_core.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cli_anything.browser.core.session import Session
from cli_anything.browser.core import page, fs


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


# ── Filesystem Module Tests ───────────────────────────────────────

class TestFsModule:
    """Test filesystem command functions."""

    def test_list_elements(self):
        """Listing elements calls backend with session working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_ls.return_value = {
                "path": "/main",
                "entries": [{"name": "button", "role": "button", "path": "/main/button[0]"}]
            }

            result = fs.list_elements(sess)

            mock_ls.assert_called_once_with("/main", use_daemon=False)

    def test_list_elements_with_path(self):
        """Listing elements with explicit path overrides working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_ls.return_value = {"path": "/div", "entries": []}

            result = fs.list_elements(sess, "/div")

            mock_ls.assert_called_once_with("/div", use_daemon=False)

    def test_list_elements_empty_path_uses_working_dir(self):
        """Listing with empty path uses session working_dir."""
        sess = Session()
        sess.set_working_dir("/main")

        with patch("cli_anything.browser.core.fs.backend.ls") as mock_ls:
            mock_ls.return_value = {"path": "/main", "entries": []}

            result = fs.list_elements(sess, "")

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
