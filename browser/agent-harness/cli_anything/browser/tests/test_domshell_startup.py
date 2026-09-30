"""Startup checks for the DOMShell subprocess configuration."""

import os
import subprocess
from unittest.mock import patch

import pytest

from cli_anything.browser.utils import domshell_backend as backend


def test_precheck_uses_resolved_npx_executable():
    npx = r"C:\Program Files\nodejs\npx.CMD"
    with patch.object(backend.shutil, "which", return_value=npx), patch.object(
        backend.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
    ) as run:
        assert backend._check_npx_has_domshell()

    assert run.call_args.args[0][0] == npx


@pytest.mark.skipif(os.name != "nt", reason="Windows .CMD execution")
def test_precheck_runs_cmd_shim_on_windows(tmp_path, monkeypatch):
    shim = tmp_path / "npx.cmd"
    shim.write_bytes(b"@echo off\r\necho 2.0.0\r\n")
    monkeypatch.setenv("PATH", str(tmp_path))

    assert backend._check_npx_has_domshell()


def test_version_check_uses_resolved_npx_executable():
    npx = r"C:\Program Files\nodejs\npx.CMD"
    result = subprocess.CompletedProcess([], 0, stdout="2.0.0")
    with patch.object(backend.shutil, "which", return_value=npx), patch.object(
        backend.subprocess, "run", return_value=result
    ) as run:
        assert backend.is_available() == (True, "DOMShell 2.0.0 is available")

    assert all(call.args[0][0] == npx for call in run.call_args_list)


def test_server_params_preserve_npm_configuration(monkeypatch):
    monkeypatch.setenv("DOMSHELL_TOKEN", "test-token")
    monkeypatch.setenv("npm_config_cache", r"C:\writable-cache")
    npx = r"C:\Program Files\nodejs\npx.CMD"
    with patch.object(backend.shutil, "which", return_value=npx):
        params = backend._server_params()

    assert params.command == npx
    assert next(value for key, value in params.env.items() if key.lower() == "npm_config_cache") == r"C:\writable-cache"
