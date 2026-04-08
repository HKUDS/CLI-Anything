"""Unit tests for the PM2 CLI-Anything harness.

All subprocess calls are mocked -- no pm2 binary required.
Covers: pm2_backend, core/processes, core/lifecycle, core/logs, core/system,
        pm2_cli output formatting, and error handling.
"""

import json
import subprocess
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_result(stdout="", stderr="", returncode=0):
    """Build a mock subprocess.CompletedProcess."""
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


FAKE_JLIST = json.dumps([
    {
        "pm_id": 0,
        "name": "seaclip-dev",
        "pid": 12345,
        "monit": {"cpu": 2.5, "memory": 52428800},
        "pm2_env": {
            "status": "online",
            "restart_time": 3,
            "pm_uptime": 1700000000000,
            "pm_exec_path": "/app/index.js",
            "pm_cwd": "/app",
            "exec_interpreter": "node",
            "exec_mode": "fork_mode",
            "node_version": "20.11.0",
        },
    },
    {
        "pm_id": 1,
        "name": "hub-dashboard",
        "pid": 12346,
        "monit": {"cpu": 0.1, "memory": 10485760},
        "pm2_env": {
            "status": "stopped",
            "restart_time": 0,
            "pm_uptime": 0,
            "pm_exec_path": "/dash/server.js",
            "pm_cwd": "/dash",
            "exec_interpreter": "node",
            "exec_mode": "fork_mode",
            "node_version": "20.11.0",
        },
    },
])


# ===========================================================================
# 1. pm2_backend._find_pm2
# ===========================================================================

class TestFindPm2:
    """Tests for pm2 binary discovery."""

    @patch("shutil.which", return_value="/opt/homebrew/bin/pm2")
    def test_find_pm2_found(self, mock_which):
        from cli_anything.pm2.utils.pm2_backend import _find_pm2
        assert _find_pm2() == "/opt/homebrew/bin/pm2"

    @patch("shutil.which", return_value=None)
    def test_find_pm2_not_found_raises(self, mock_which):
        from cli_anything.pm2.utils.pm2_backend import _find_pm2
        with pytest.raises(RuntimeError, match="pm2 not found"):
            _find_pm2()


# ===========================================================================
# 2. pm2_backend.run_pm2
# ===========================================================================

class TestRunPm2:
    """Tests for the core run_pm2 subprocess wrapper."""

    @patch("cli_anything.pm2.utils.pm2_backend._get_pm2", return_value="/usr/bin/pm2")
    @patch("subprocess.run")
    def test_run_pm2_success(self, mock_run, mock_get):
        mock_run.return_value = _make_run_result(stdout="OK\n", returncode=0)
        from cli_anything.pm2.utils.pm2_backend import run_pm2
        result = run_pm2("save")
        assert result["success"] is True
        assert result["returncode"] == 0
        assert "OK" in result["stdout"]

    @patch("cli_anything.pm2.utils.pm2_backend._get_pm2", return_value="/usr/bin/pm2")
    @patch("subprocess.run")
    def test_run_pm2_failure(self, mock_run, mock_get):
        mock_run.return_value = _make_run_result(stderr="error", returncode=1)
        from cli_anything.pm2.utils.pm2_backend import run_pm2
        result = run_pm2("restart", "ghost")
        assert result["success"] is False
        assert result["returncode"] == 1

    @patch("cli_anything.pm2.utils.pm2_backend._get_pm2", return_value="/usr/bin/pm2")
    @patch("subprocess.run")
    def test_run_pm2_json_parsing(self, mock_run, mock_get):
        mock_run.return_value = _make_run_result(stdout=FAKE_JLIST, returncode=0)
        from cli_anything.pm2.utils.pm2_backend import run_pm2
        result = run_pm2("jlist", capture_json=True)
        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "seaclip-dev"

    @patch("cli_anything.pm2.utils.pm2_backend._get_pm2", return_value="/usr/bin/pm2")
    @patch("subprocess.run")
    def test_run_pm2_json_with_preamble(self, mock_run, mock_get):
        """JSON extraction works even with non-JSON text before the array."""
        preamble = "PM2 info line\n" + FAKE_JLIST
        mock_run.return_value = _make_run_result(stdout=preamble, returncode=0)
        from cli_anything.pm2.utils.pm2_backend import run_pm2
        result = run_pm2("jlist", capture_json=True)
        assert result["data"] is not None
        assert isinstance(result["data"], list)

    @patch("cli_anything.pm2.utils.pm2_backend._get_pm2", return_value="/usr/bin/pm2")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pm2", timeout=30))
    def test_run_pm2_timeout(self, mock_run, mock_get):
        from cli_anything.pm2.utils.pm2_backend import run_pm2
        result = run_pm2("jlist", timeout=30)
        assert result["success"] is False
        assert "timed out" in result["stderr"]

    @patch("cli_anything.pm2.utils.pm2_backend._get_pm2", return_value="/nonexistent/pm2")
    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_run_pm2_binary_missing(self, mock_run, mock_get):
        from cli_anything.pm2.utils.pm2_backend import run_pm2
        result = run_pm2("jlist")
        assert result["success"] is False
        assert "not found" in result["stderr"]


# ===========================================================================
# 3. core/processes.py
# ===========================================================================

class TestProcesses:
    """Tests for process listing, describe, and metrics."""

    @patch("cli_anything.pm2.core.processes.pm2_jlist")
    def test_list_processes_json(self, mock_jlist):
        mock_jlist.return_value = json.loads(FAKE_JLIST)
        from cli_anything.pm2.core.processes import list_processes
        result = list_processes(as_json=True)
        assert isinstance(result, list)
        assert len(result) == 2

    @patch("cli_anything.pm2.core.processes.pm2_jlist")
    def test_list_processes_human(self, mock_jlist):
        mock_jlist.return_value = json.loads(FAKE_JLIST)
        from cli_anything.pm2.core.processes import list_processes
        result = list_processes(as_json=False)
        assert isinstance(result, list)
        assert result[0]["name"] == "seaclip-dev"
        assert result[0]["status"] == "online"

    @patch("cli_anything.pm2.core.processes.pm2_jlist")
    def test_list_processes_empty(self, mock_jlist):
        mock_jlist.return_value = []
        from cli_anything.pm2.core.processes import list_processes
        result = list_processes(as_json=False)
        assert result == "No PM2 processes running."

    @patch("cli_anything.pm2.core.processes.pm2_describe")
    def test_describe_process_found(self, mock_desc):
        mock_desc.return_value = json.loads(FAKE_JLIST)[0]
        from cli_anything.pm2.core.processes import describe_process
        result = describe_process("seaclip-dev", as_json=False)
        assert isinstance(result, dict)
        assert result["Name"] == "seaclip-dev"

    @patch("cli_anything.pm2.core.processes.pm2_describe")
    def test_describe_process_not_found(self, mock_desc):
        mock_desc.return_value = None
        from cli_anything.pm2.core.processes import describe_process
        result = describe_process("ghost", as_json=False)
        assert result is None

    @patch("cli_anything.pm2.core.processes.pm2_jlist")
    def test_get_metrics_json(self, mock_jlist):
        mock_jlist.return_value = json.loads(FAKE_JLIST)
        from cli_anything.pm2.core.processes import get_metrics
        result = get_metrics(as_json=True)
        assert isinstance(result, list)
        assert result[0]["cpu"] == 2.5


# ===========================================================================
# 4. core/lifecycle.py
# ===========================================================================

class TestLifecycle:
    """Tests for lifecycle commands."""

    @patch("cli_anything.pm2.core.lifecycle.pm2_action")
    def test_restart_success(self, mock_action):
        mock_action.return_value = {
            "success": True, "returncode": 0,
            "stdout": "restarted", "stderr": "",
        }
        from cli_anything.pm2.core.lifecycle import restart_process
        result = restart_process("seaclip-dev", as_json=False)
        assert result["success"] is True
        assert "Restarted" in result["message"]

    @patch("cli_anything.pm2.core.lifecycle.pm2_action")
    def test_stop_failure(self, mock_action):
        mock_action.return_value = {
            "success": False, "returncode": 1,
            "stdout": "", "stderr": "process not found",
        }
        from cli_anything.pm2.core.lifecycle import stop_process
        result = stop_process("ghost", as_json=False)
        assert result["success"] is False
        assert "Failed" in result["message"]

    @patch("cli_anything.pm2.core.lifecycle.backend_start")
    def test_start_with_name(self, mock_start):
        mock_start.return_value = {
            "success": True, "returncode": 0,
            "stdout": "started", "stderr": "",
        }
        from cli_anything.pm2.core.lifecycle import start_process
        result = start_process("/app/index.js", name="my-app", as_json=True)
        assert result["success"] is True
        assert result["name"] == "my-app"


# ===========================================================================
# 5. core/logs.py
# ===========================================================================

class TestLogs:
    """Tests for log commands."""

    @patch("cli_anything.pm2.core.logs.backend_logs")
    def test_view_logs_success(self, mock_logs):
        mock_logs.return_value = {
            "success": True, "returncode": 0,
            "stdout": "line1\nline2\n", "stderr": "",
        }
        from cli_anything.pm2.core.logs import view_logs
        result = view_logs("seaclip-dev", lines=20, as_json=False)
        assert result["success"] is True
        assert "line1" in result["content"]

    @patch("cli_anything.pm2.core.logs.backend_flush")
    def test_flush_all(self, mock_flush):
        mock_flush.return_value = {
            "success": True, "returncode": 0,
            "stdout": "flushed", "stderr": "",
        }
        from cli_anything.pm2.core.logs import flush_logs
        result = flush_logs(name=None, as_json=False)
        assert result["success"] is True
        assert "all processes" in result["message"]


# ===========================================================================
# 6. core/system.py
# ===========================================================================

class TestSystem:
    """Tests for system commands."""

    @patch("cli_anything.pm2.core.system.backend_version")
    def test_version_json(self, mock_ver):
        mock_ver.return_value = "5.3.0"
        from cli_anything.pm2.core.system import version
        result = version(as_json=True)
        assert result["version"] == "5.3.0"

    @patch("cli_anything.pm2.core.system.backend_save")
    def test_save_success(self, mock_save):
        mock_save.return_value = {
            "success": True, "returncode": 0,
            "stdout": "saved", "stderr": "",
        }
        from cli_anything.pm2.core.system import save
        result = save(as_json=False)
        assert result["success"] is True
        assert "saved" in result["message"].lower()


# ===========================================================================
# 7. Output formatting (_output helper)
# ===========================================================================

class TestOutputFormatting:
    """Tests for the _output helper in pm2_cli."""

    def test_output_json_string(self, capsys):
        from cli_anything.pm2.pm2_cli import _output
        _output("hello", as_json=True)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["result"] == "hello"

    def test_output_json_dict(self, capsys):
        from cli_anything.pm2.pm2_cli import _output
        _output({"key": "val"}, as_json=True)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["key"] == "val"

    def test_output_human_string(self, capsys):
        from cli_anything.pm2.pm2_cli import _output
        _output("hello world", as_json=False)
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_output_human_dict_with_message(self, capsys):
        from cli_anything.pm2.pm2_cli import _output
        _output({"success": True, "message": "Done"}, as_json=False)
        captured = capsys.readouterr()
        assert "[OK] Done" in captured.out

    def test_output_human_error_message(self, capsys):
        from cli_anything.pm2.pm2_cli import _output
        _output({"success": False, "message": "Oops"}, as_json=False)
        captured = capsys.readouterr()
        assert "[ERROR] Oops" in captured.out


# ===========================================================================
# 8. Utility: _format_bytes
# ===========================================================================

class TestFormatBytes:
    """Tests for the byte formatting utility."""

    def test_zero_bytes(self):
        from cli_anything.pm2.core.processes import _format_bytes
        assert _format_bytes(0) == "0 B"

    def test_megabytes(self):
        from cli_anything.pm2.core.processes import _format_bytes
        result = _format_bytes(52428800)  # 50 MB
        assert "MB" in result
        assert "50.0" in result
