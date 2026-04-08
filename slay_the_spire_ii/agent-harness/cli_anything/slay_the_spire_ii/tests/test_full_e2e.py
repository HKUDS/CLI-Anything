"""CLI subprocess tests for the Slay the Spire II harness using a fake bridge."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.slay_the_spire_ii"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class _BridgeHandler(BaseHTTPRequestHandler):
    raw_state = {
        "state_type": "menu",
        "run": {"act": None, "floor": None, "ascension": None},
        "menu": {
            "screen": "main_menu",
            "can_continue_game": True,
            "can_start_new_game": True,
            "can_abandon_game": False,
            "characters": ["IRONCLAD", "SILENT", "DEFECT"],
            "ascension": 4,
        },
        "message": "Ready",
    }
    requests: list[dict[str, object]] = []

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/api/v1/singleplayer?format=json":
            self.send_error(404)
            return
        body = json.dumps(type(self).raw_state).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/v1/singleplayer":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).requests.append(payload)

        body = json.dumps({"ok": True, "received": payload}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class BridgeServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _BridgeHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.agent_harness_dir = Path(__file__).resolve().parents[3]
        cls.cli_base = _resolve_cli("cli-anything-sts2")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)
        cls.httpd.server_close()

    def setUp(self) -> None:
        _BridgeHandler.requests.clear()

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.agent_harness_dir)
        return subprocess.run(
            self.cli_base + ["--base-url", f"http://127.0.0.1:{self.port}", *args],
            cwd=self.agent_harness_dir,
            capture_output=True,
            text=True,
            env=env,
            check=check,
        )


class TestBridgeSubprocess(BridgeServerTestCase):
    def test_help(self) -> None:
        result = self._run(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("cli-anything-sts2", result.stdout)
        self.assertIn("Run without a subcommand to enter interactive REPL mode.", result.stdout)

    def test_raw_state_returns_server_payload(self) -> None:
        result = self._run(["raw-state"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["state_type"], "menu")
        self.assertEqual(data["menu"]["screen"], "main_menu")

    def test_state_returns_normalized_decision(self) -> None:
        result = self._run(["state"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["decision"], "menu")
        self.assertTrue(data["can_continue_game"])
        self.assertEqual(data["characters"], ["IRONCLAD", "SILENT", "DEFECT"])

    def test_action_posts_kv_payload(self) -> None:
        result = self._run(["action", "custom_ping", "--kv", "floor=12", "--kv", "urgent=true"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["received"]["action"], "custom_ping")
        self.assertEqual(data["received"]["floor"], 12)
        self.assertEqual(data["received"]["urgent"], True)
        self.assertEqual(_BridgeHandler.requests[-1]["action"], "custom_ping")


class TestCommandSubprocess(BridgeServerTestCase):
    def test_continue_game_uses_action_adapter_payload(self) -> None:
        result = self._run(["continue-game"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["received"], {"action": "continue_game"})
        self.assertEqual(_BridgeHandler.requests[-1], {"action": "continue_game"})


if __name__ == "__main__":
    unittest.main()
