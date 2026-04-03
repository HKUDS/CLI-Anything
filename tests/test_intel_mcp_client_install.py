import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_skills.intel_mcp_client_install import (  # noqa: E402
    SERVER_NAME,
    check_claude_config,
    check_codex_config,
    install_claude_config,
    install_codex_config,
    run_client_install,
)


class IntelMcpClientInstallTests(unittest.TestCase):
    def test_install_claude_config_creates_mcp_server_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "claude.json"

            result = install_claude_config(config_path, command="/tmp/run-intel-mcp.sh")

            self.assertTrue(result["configured"])
            self.assertTrue(result["matches_expected_command"])
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["mcpServers"][SERVER_NAME]["command"], "/tmp/run-intel-mcp.sh")

    def test_install_codex_config_appends_or_updates_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text('model = "gpt-5.4"\n', encoding="utf-8")

            result = install_codex_config(config_path, command="/tmp/run-intel-mcp.sh")

            self.assertTrue(result["configured"])
            self.assertTrue(result["matches_expected_command"])
            text = config_path.read_text(encoding="utf-8")
            self.assertIn(f"[mcp_servers.{SERVER_NAME}]", text)
            self.assertIn('command = "/tmp/run-intel-mcp.sh"', text)

    def test_check_helpers_report_missing_and_present_states(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_path = Path(tmpdir) / "claude.json"
            codex_path = Path(tmpdir) / "config.toml"

            self.assertEqual(check_claude_config(claude_path, expected_command="/tmp/x")["error"], "missing")
            self.assertEqual(check_codex_config(codex_path, expected_command="/tmp/x")["error"], "missing")

            install_claude_config(claude_path, command="/tmp/run-intel-mcp.sh")
            install_codex_config(codex_path, command="/tmp/run-intel-mcp.sh")

            self.assertTrue(check_claude_config(claude_path, expected_command="/tmp/run-intel-mcp.sh")["matches_expected_command"])
            self.assertTrue(check_codex_config(codex_path, expected_command="/tmp/run-intel-mcp.sh")["matches_expected_command"])

    def test_run_client_install_check_only_is_ok_for_matching_configs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper_path = Path(tmpdir) / "run-intel-mcp.sh"
            wrapper_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            claude_path = Path(tmpdir) / "claude.json"
            codex_path = Path(tmpdir) / "config.toml"
            install_claude_config(claude_path, command=str(wrapper_path))
            install_codex_config(codex_path, command=str(wrapper_path))

            result = run_client_install(
                wrapper_path=wrapper_path,
                claude_config_path=claude_path,
                codex_config_path=codex_path,
                check_only=True,
            )

            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["claude"]["matches_expected_command"])
            self.assertTrue(result["codex"]["matches_expected_command"])
