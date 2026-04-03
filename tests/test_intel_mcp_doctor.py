import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path("/Users/lixun/Documents/codex ")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_skills.intel_mcp_doctor import (  # noqa: E402
    SERVER_NAME,
    inspect_claude_config,
    inspect_codex_config,
    inspect_pre_push_hook,
    run_doctor,
)


class IntelMcpDoctorTests(unittest.TestCase):
    def test_inspect_claude_config_reports_matching_server(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "claude.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            SERVER_NAME: {
                                "type": "stdio",
                                "command": "/tmp/run-intel-mcp.sh",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = inspect_claude_config(config_path, expected_command="/tmp/run-intel-mcp.sh")

            self.assertTrue(result["configured"])
            self.assertTrue(result["matches_expected_command"])
            self.assertEqual(result["type"], "stdio")

    def test_inspect_codex_config_reports_matching_server(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                f"""
[mcp_servers.{SERVER_NAME}]
type = "stdio"
command = "/tmp/run-intel-mcp.sh"
""".strip(),
                encoding="utf-8",
            )

            result = inspect_codex_config(config_path, expected_command="/tmp/run-intel-mcp.sh")

            self.assertTrue(result["configured"])
            self.assertTrue(result["matches_expected_command"])
            self.assertEqual(result["type"], "stdio")

    def test_run_doctor_reports_ok_when_all_checks_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper_path = Path(tmpdir) / "run-intel-mcp.sh"
            wrapper_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            wrapper_path.chmod(0o755)

            claude_path = Path(tmpdir) / "claude.json"
            claude_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            SERVER_NAME: {
                                "type": "stdio",
                                "command": str(wrapper_path),
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            codex_path = Path(tmpdir) / "config.toml"
            codex_path.write_text(
                f"""
[mcp_servers.{SERVER_NAME}]
type = "stdio"
command = "{wrapper_path}"
""".strip(),
                encoding="utf-8",
            )

            with mock.patch(
                "agent_skills.intel_mcp_doctor.run_handshake",
                return_value={
                    "ok": True,
                    "exit_code": 0,
                    "stderr": None,
                    "tool_count": 3,
                    "resource_count": 6,
                    "server_name": SERVER_NAME,
                    "protocol_version": "2025-06-18",
                },
            ), mock.patch(
                "agent_skills.intel_mcp_doctor.run_live_prompt_checks",
                return_value={
                    "ok": True,
                    "exit_code": 0,
                    "stderr": None,
                    "prompt_count": 3,
                    "prompts": {
                        "source-health-triage": {"ok": True},
                        "briefing-analyst": {"ok": True},
                    },
                },
            ), mock.patch(
                "agent_skills.intel_mcp_doctor.run_live_tool_calls",
                return_value={
                    "ok": True,
                    "exit_code": 0,
                    "stderr": None,
                    "tool_count": 3,
                    "tools": {
                        "intel-health": {"ok": True, "is_error": False, "missing_fields": []},
                        "intel-ops-overview": {"ok": True, "is_error": False, "missing_fields": []},
                        "intel-briefing": {"ok": True, "is_error": False, "missing_fields": []},
                    },
                },
            ):
                result = run_doctor(
                    wrapper_path=wrapper_path,
                    claude_config_path=claude_path,
                    codex_config_path=codex_path,
                )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(
                result["checks"],
                {
                    "wrapper": True,
                    "claude": True,
                    "codex": True,
                    "handshake": True,
                    "live_prompts": True,
                    "live_tools": True,
                },
            )

    def test_run_doctor_reports_degraded_when_client_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper_path = Path(tmpdir) / "run-intel-mcp.sh"
            wrapper_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            wrapper_path.chmod(0o755)

            claude_path = Path(tmpdir) / "claude.json"
            claude_path.write_text("{}", encoding="utf-8")

            codex_path = Path(tmpdir) / "config.toml"
            codex_path.write_text("", encoding="utf-8")

            with mock.patch(
                "agent_skills.intel_mcp_doctor.run_handshake",
                return_value={
                    "ok": True,
                    "exit_code": 0,
                    "stderr": None,
                    "tool_count": 3,
                    "resource_count": 6,
                    "server_name": SERVER_NAME,
                    "protocol_version": "2025-06-18",
                },
            ), mock.patch(
                "agent_skills.intel_mcp_doctor.run_live_prompt_checks",
                return_value={
                    "ok": True,
                    "exit_code": 0,
                    "stderr": None,
                    "prompt_count": 3,
                    "prompts": {
                        "source-health-triage": {"ok": True},
                        "briefing-analyst": {"ok": True},
                    },
                },
            ), mock.patch(
                "agent_skills.intel_mcp_doctor.run_live_tool_calls",
                return_value={
                    "ok": True,
                    "exit_code": 0,
                    "stderr": None,
                    "tool_count": 3,
                    "tools": {
                        "intel-health": {"ok": True, "is_error": False, "missing_fields": []},
                        "intel-ops-overview": {"ok": True, "is_error": False, "missing_fields": []},
                        "intel-briefing": {"ok": True, "is_error": False, "missing_fields": []},
                    },
                },
            ):
                result = run_doctor(
                    wrapper_path=wrapper_path,
                    claude_config_path=claude_path,
                    codex_config_path=codex_path,
                )

            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["checks"]["claude"])
            self.assertFalse(result["checks"]["codex"])

    def test_inspect_pre_push_hook_reports_release_gate_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hook_path = Path(tmpdir) / "pre-push"
            hook_path.write_text(
                "#!/bin/sh\nexec sh '/Users/lixun/Documents/codex /scripts/test_intel_mcp_stack.sh'\n",
                encoding="utf-8",
            )

            result = inspect_pre_push_hook(hook_path)

            self.assertTrue(result["installed"])
            self.assertTrue(result["matches_release_gate"])
