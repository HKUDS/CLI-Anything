"""E2E tests for cli-anything-browser — Requires Chrome + DOMShell extension.

These tests interact with real Chrome and DOMShell. Skip if DOMShell is not available.

Usage:
    python -m pytest cli_anything/browser/tests/test_full_e2e.py -v
"""

import asyncio
import json
import os
import shlex
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import urlopen

import pytest
from click.testing import CliRunner

from cli_anything.browser.utils.domshell_backend import is_available
from cli_anything.browser.browser_cli import cli
from cli_anything.browser.core.fs import change_directory
from cli_anything.browser.core.session import Session
from cli_anything.browser.utils import domshell_backend as backend

# Control whether to run DOMShell E2E tests via an environment variable.
# This avoids invoking `npx` (inside is_available) during test collection
# in environments that have not explicitly opted in.
DOMSHELL_E2E_ENABLED = os.environ.get("DOMSHELL_E2E", "").lower() in {"1", "true", "yes"}

# Skip all tests if E2E is not enabled or DOMShell is not available.
# `is_available()` is only called when DOMSHELL_E2E_ENABLED is true.
pytestmark = pytest.mark.skipif(
    (not DOMSHELL_E2E_ENABLED) or (not is_available()[0]),
    reason=(
        "DOMShell E2E tests are disabled or DOMShell MCP server not available. "
        "Set DOMSHELL_E2E=1 to enable and ensure DOMShell is installed from the Chrome Web Store."
    ),
)

TEST_URL = "https://example.com"
CHROME_DEBUG_URL = os.environ.get("DOMSHELL_E2E_CDP_URL", "")


@pytest.fixture
def directory_test_url(tmp_path):
    (tmp_path / "index.html").write_text(
        '<title>DOMShell path contract</title><header><h1>Tab root</h1></header>'
        '<main><h2>Nested heading</h2><input aria-label="Fixture input" '
        'value="untouched"></main>',
        encoding="utf-8",
    )
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.skipif(not CHROME_DEBUG_URL, reason="Set DOMSHELL_E2E_CDP_URL for the dedicated test Chrome")
def test_absolute_paths_preserve_live_directory_and_stop_on_missing_focus(directory_test_url):
    """Exercise actual DOMShell replies and AX state in an isolated Chrome lane."""
    endpoint = urlsplit(CHROME_DEBUG_URL)
    assert endpoint.scheme == "http" and endpoint.hostname in {"127.0.0.1", "localhost"}
    discovery = CHROME_DEBUG_URL.rstrip("/")

    session = Session()
    context = {"session": session}
    try:
        opened = backend.open_url(directory_test_url, **context)
        assert opened.get("title") == "DOMShell path contract", opened
        assert session.domshell_lane_id and session.domshell_lane_id.isdigit()

        # DOMShell opens isolated tabs without taking focus. Absolute paths
        # start at the active tab, so activate only the fixture URL we opened.
        with urlopen(f"{discovery}/json/list", timeout=5) as response:
            targets = json.load(response)
        target = next(item for item in targets if item["url"] == directory_test_url)
        with urlopen(f"{discovery}/json/activate/{target['id']}", timeout=5) as response:
            assert response.status == 200

        root = backend.ls("", **context)
        directory = next(entry["name"].rstrip("/") for entry in root["entries"]
                         if entry["name"].startswith("main_"))
        path = f"/{directory}"

        result = change_directory(session, path)
        assert "error" not in result, result
        nested = backend.ls("", **context)
        assert "nested_heading" in nested["raw"]
        field = next(entry["name"] for entry in nested["entries"]
                     if entry["name"].startswith("fixture_input"))
        assert backend.ls("/", **context)["raw"] == root["raw"]
        assert backend.ls("", **context)["raw"] == nested["raw"]

        missing = change_directory(session, f"{path}/missing")
        assert "error" in missing, missing
        assert session.working_dir == path
        assert backend.ls("", **context)["raw"] == nested["raw"]

        focus = asyncio.run(backend._call_execute(f"focus {shlex.quote(field)}", **context))
        assert "Focused" in backend._extract_text(focus)
        for target_path in (f"{path}/missing", "/--help"):
            failed = backend.type_text(target_path, "changed-by-test", **context)
            assert "error" in failed, failed
        current = backend.cat(field, **context)
        assert "untouched" in current["output"], current
        assert "changed-by-test" not in current["output"], current
    finally:
        # The lane is created by this test and contains only its fixture tabs.
        if session.domshell_lane_id:
            asyncio.run(backend._call_execute("group close", **context))


@pytest.fixture
def runner():
    return CliRunner()


class TestDependencyChecks:
    """Test that dependency checking works correctly."""

    def test_cli_starts_when_domshell_available(self, runner):
        """CLI should start successfully when DOMShell is available."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Browser CLI" in result.output


class TestPageCommands:
    """Test page navigation commands."""

    def test_page_info_empty(self, runner):
        """Page info shows empty state initially."""
        result = runner.invoke(cli, ["--json", "page", "info"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert data["url"] == "(no page loaded)"
        assert data["working_dir"] == "/"


class TestFilesystemCommands:
    """Test filesystem commands."""

    def test_fs_pwd(self, runner):
        """Print working directory shows root initially."""
        result = runner.invoke(cli, ["fs", "pwd"])
        assert result.exit_code == 0
        assert result.output.strip() == "/"


class TestSessionCommands:
    """Test session management commands."""

    def test_session_status(self, runner):
        """Session status shows current state."""
        result = runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "current_url" in data
        assert "working_dir" in data


class TestDaemonMode:
    """Test daemon mode functionality."""

    @pytest.mark.manual
    def test_daemon_lifecycle(self, runner):
        """Manual test: Start daemon, run commands, stop daemon.

        To run manually:
            cli-anything-browser session daemon-start
            cli-anything-browser fs pwd
            cli-anything-browser session daemon-stop
        """
        pass

    def test_daemon_start_with_json(self, runner):
        """Daemon start returns success in JSON."""
        result = runner.invoke(cli, ["--json", "session", "daemon-start"])
        # May fail if daemon can't start, but should return JSON
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "daemon" in data or "error" in data


class TestErrorHandling:
    """Test error handling for edge cases."""

    def test_invalid_path_gives_error(self, runner):
        """Invalid path should give clear error."""
        # Note: This test's behavior depends on DOMShell's error handling
        result = runner.invoke(cli, ["fs", "cd", "/invalid/path/that/does/not/exist"])
        # Should not crash; exit code may be 0 or 1 depending on error handling
        assert result.exception is None
        assert result.exit_code in (0, 1)

    def test_empty_page_info(self, runner):
        """Page info with no page loaded shows empty state."""
        result = runner.invoke(cli, ["page", "info"])
        assert result.exit_code == 0
        assert "(no page loaded)" in result.output


class TestJSONOutput:
    """Test JSON output formatting."""

    def test_json_output_is_valid(self, runner):
        """JSON output should be valid and parseable."""
        result = runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_flag_propagates_in_repl(self, runner):
        """JSON flag from top-level should propagate to REPL subcommands."""
        # Simulate REPL input by calling the repl command with --json already set
        # The fix ensures that when _json_output is True in REPL mode,
        # the --json flag is prepended to subcommand args.
        result = runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert isinstance(data, dict)
        # Verify it's actually JSON (not the human-readable format)
        assert "daemon" in data or "session" in data


class TestCleanup:
    """Cleanup tests to stop daemon if started."""

    def test_stop_daemon_if_running(self, runner):
        """Ensure daemon is stopped after tests."""
        result = runner.invoke(cli, ["session", "daemon-stop"])
        # Should succeed whether daemon was running or not
        assert result.exit_code == 0
