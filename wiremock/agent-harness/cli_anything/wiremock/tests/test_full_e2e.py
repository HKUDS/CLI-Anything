"""E2E / subprocess tests for the cli-anything-wiremock CLI.

Tests that require a live WireMock server are automatically skipped unless
the WIREMOCK_URL environment variable is set (e.g. WIREMOCK_URL=http://localhost:8080).

Tests for --help and argument parsing work without a server.
"""
import json
import os
import subprocess
import sys
import unittest

# ---------------------------------------------------------------------------
# CLI resolution
# ---------------------------------------------------------------------------

CLI_ENV_KEY = "CLI_ANYTHING_FORCE_INSTALLED"


def _resolve_cli(name: str) -> list:
    """Resolve CLI name to a command list, supporting installed and dev modes.

    Returns a list suitable for use as the first argument to subprocess.run().
    """
    if os.environ.get(CLI_ENV_KEY):
        return [name]
    result = subprocess.run(["which", name], capture_output=True, text=True)
    if result.returncode == 0:
        return [result.stdout.strip()]
    # Fall back to running the module directly
    return [sys.executable, "-m", "cli_anything.wiremock.wiremock_cli"]


CLI_CMD = _resolve_cli("cli-anything-wiremock")

# ---------------------------------------------------------------------------
# Live-server guard
# ---------------------------------------------------------------------------

WIREMOCK_URL = os.environ.get("WIREMOCK_URL", "")
LIVE_SERVER_AVAILABLE = bool(WIREMOCK_URL)

skip_no_server = unittest.skipUnless(
    LIVE_SERVER_AVAILABLE,
    "WIREMOCK_URL not set — skipping live server tests",
)


def _run(*args, env_extras: dict = None, input_text: str = None) -> subprocess.CompletedProcess:
    """Run the CLI with the given arguments and return the CompletedProcess."""
    env = os.environ.copy()
    if WIREMOCK_URL:
        from urllib.parse import urlparse
        parsed = urlparse(WIREMOCK_URL)
        env["WIREMOCK_HOST"] = parsed.hostname or "localhost"
        env["WIREMOCK_PORT"] = str(parsed.port or 8080)
        env["WIREMOCK_SCHEME"] = parsed.scheme or "http"
    if env_extras:
        env.update(env_extras)
    return subprocess.run(
        CLI_CMD + list(args),
        capture_output=True,
        text=True,
        env=env,
        input=input_text,
    )


# ---------------------------------------------------------------------------
# TestCLISubprocess — argument parsing and --help (no server needed)
# ---------------------------------------------------------------------------


class TestCLISubprocess(unittest.TestCase):
    """Tests that exercise CLI argument parsing without a live WireMock server."""

    def test_top_level_help(self):
        result = _run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("stub", result.stdout)
        self.assertIn("request", result.stdout)
        self.assertIn("scenario", result.stdout)
        self.assertIn("record", result.stdout)
        self.assertIn("settings", result.stdout)

    def test_stub_group_help(self):
        result = _run("stub", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("list", result.stdout)
        self.assertIn("create", result.stdout)
        self.assertIn("quick", result.stdout)
        self.assertIn("delete", result.stdout)

    def test_stub_list_help(self):
        result = _run("stub", "list", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--limit", result.stdout)
        self.assertIn("--offset", result.stdout)

    def test_stub_quick_help(self):
        result = _run("stub", "quick", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("METHOD", result.stdout)
        self.assertIn("URL", result.stdout)
        self.assertIn("STATUS", result.stdout)
        self.assertIn("--body", result.stdout)

    def test_request_group_help(self):
        result = _run("request", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("list", result.stdout)
        self.assertIn("find", result.stdout)
        self.assertIn("count", result.stdout)
        self.assertIn("unmatched", result.stdout)
        self.assertIn("reset", result.stdout)

    def test_scenario_group_help(self):
        result = _run("scenario", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("list", result.stdout)
        self.assertIn("set", result.stdout)
        self.assertIn("reset", result.stdout)

    def test_record_group_help(self):
        result = _run("record", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("start", result.stdout)
        self.assertIn("stop", result.stdout)
        self.assertIn("status", result.stdout)
        self.assertIn("snapshot", result.stdout)

    def test_settings_group_help(self):
        result = _run("settings", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("get", result.stdout)
        self.assertIn("version", result.stdout)

    def test_status_help(self):
        result = _run("status", "--help")
        self.assertEqual(result.returncode, 0)

    def test_global_json_flag_in_help(self):
        result = _run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--json", result.stdout)

    def test_global_host_flag_in_help(self):
        result = _run("--help")
        self.assertIn("--host", result.stdout)

    def test_global_port_flag_in_help(self):
        result = _run("--help")
        self.assertIn("--port", result.stdout)

    def test_record_start_help_shows_match_header(self):
        result = _run("record", "start", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--match-header", result.stdout)

    def test_status_fails_gracefully_when_no_server(self):
        """status should exit non-zero or print 'stopped' — not crash."""
        result = _run(
            "status",
            env_extras={
                "WIREMOCK_HOST": "127.0.0.1",
                "WIREMOCK_PORT": "19999",  # nothing listening here
            },
        )
        # Either it prints "stopped" (exit 0) or exits with 1 — both are acceptable
        # It must NOT raise an unhandled exception
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        if result.returncode == 0:
            self.assertIn("stopped", result.stdout)

    def test_status_json_fails_gracefully_when_no_server(self):
        """--json status should output valid JSON even when server is unreachable."""
        result = _run(
            "--json", "status",
            env_extras={
                "WIREMOCK_HOST": "127.0.0.1",
                "WIREMOCK_PORT": "19999",
            },
        )
        self.assertNotIn("Traceback", result.stdout)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            self.assertIn("status", data)


# ---------------------------------------------------------------------------
# TestLiveServer — tests that require WIREMOCK_URL
# ---------------------------------------------------------------------------


class TestLiveServer(unittest.TestCase):
    """Tests against a live WireMock instance.

    Set WIREMOCK_URL=http://localhost:8080 before running.
    """

    @skip_no_server
    def setUp(self):
        """Reset WireMock state before each test."""
        _run("reset", input_text="y\n")  # confirm the prompt if any
        # Also try a clean reset via the full-reset command
        result = subprocess.run(
            CLI_CMD + ["reset"],
            capture_output=True, text=True,
            env={**os.environ, **self._env()},
        )
        # Ignore reset errors — server might already be clean

    def _env(self):
        from urllib.parse import urlparse
        parsed = urlparse(WIREMOCK_URL)
        return {
            "WIREMOCK_HOST": parsed.hostname or "localhost",
            "WIREMOCK_PORT": str(parsed.port or 8080),
            "WIREMOCK_SCHEME": parsed.scheme or "http",
        }

    @skip_no_server
    def test_status_running(self):
        result = _run("--json", "status")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "running")

    @skip_no_server
    def test_stub_list_empty(self):
        result = _run("--json", "stub", "list")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        # WireMock may have default stubs; just check the structure
        self.assertIn("mappings", data)

    @skip_no_server
    def test_stub_quick_create_and_list(self):
        # Create a stub
        result = _run("--json", "stub", "quick", "GET", "/test-endpoint", "200",
                      "--body", '{"hello":"world"}')
        self.assertEqual(result.returncode, 0)
        created = json.loads(result.stdout)
        self.assertEqual(created["status"], "ok")
        stub_id = created["data"]["id"]
        self.assertIsNotNone(stub_id)

        # List and find it
        result = _run("--json", "stub", "list")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        ids = [m["id"] for m in data.get("mappings", [])]
        self.assertIn(stub_id, ids)

    @skip_no_server
    def test_stub_create_full_json(self):
        mapping = {
            "request": {"method": "POST", "url": "/api/orders"},
            "response": {"status": 201, "body": '{"id":42}',
                         "headers": {"Content-Type": "application/json"}},
        }
        result = _run("--json", "stub", "create", json.dumps(mapping))
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")

    @skip_no_server
    def test_stub_get(self):
        # Create a stub first
        r = _run("--json", "stub", "quick", "GET", "/get-test", "200")
        stub_id = json.loads(r.stdout)["data"]["id"]

        result = _run("--json", "stub", "get", stub_id)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["id"], stub_id)

    @skip_no_server
    def test_stub_delete(self):
        # Create then delete
        r = _run("--json", "stub", "quick", "GET", "/delete-me", "200")
        stub_id = json.loads(r.stdout)["data"]["id"]

        result = _run("--json", "stub", "delete", stub_id)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")

    @skip_no_server
    def test_stub_reset(self):
        # Create a stub, then reset
        _run("stub", "quick", "GET", "/ephemeral", "200")
        result = _run("--json", "stub", "reset")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")

    @skip_no_server
    def test_request_list_and_reset(self):
        # List requests
        result = _run("--json", "request", "list")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("serveEvents", data)

        # Reset
        result = _run("--json", "request", "reset")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")

    @skip_no_server
    def test_request_count(self):
        pattern = json.dumps({"method": "GET", "url": "/nonexistent"})
        result = _run("--json", "request", "count", pattern)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("count", data)

    @skip_no_server
    def test_scenario_list(self):
        result = _run("--json", "scenario", "list")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("scenarios", data)

    @skip_no_server
    def test_scenario_reset(self):
        result = _run("--json", "scenario", "reset")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")

    @skip_no_server
    def test_record_status(self):
        result = _run("--json", "record", "status")
        self.assertEqual(result.returncode, 0)
        # WireMock returns {"status": "NeverStarted"} or "Recording" or "Stopped"
        # just verify we got a valid response
        data = json.loads(result.stdout)
        self.assertIn("status", data)

    @skip_no_server
    def test_settings_version(self):
        result = _run("--json", "settings", "version")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("version", data)

    @skip_no_server
    def test_settings_get(self):
        result = _run("--json", "settings", "get")
        self.assertEqual(result.returncode, 0)
        # Should return a JSON object (no crash)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)

    @skip_no_server
    def test_request_unmatched(self):
        result = _run("--json", "request", "unmatched")
        self.assertEqual(result.returncode, 0)
        # Just verify it returns valid JSON
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
