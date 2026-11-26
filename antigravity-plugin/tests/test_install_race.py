"""Concurrency regression tests for antigravity-plugin install lock serialization."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_SRC = Path(__file__).resolve().parent.parent


def _installer_cmd(force: bool = False) -> list[str]:
    if sys.platform == "win32":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        assert shell, "PowerShell required on Windows"
        cmd = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PLUGIN_SRC / "scripts" / "install.ps1")]
        if force:
            cmd.append("-Force")
        return cmd
    cmd = ["bash", str(PLUGIN_SRC / "scripts" / "install.sh")]
    if force:
        cmd.append("--force")
    return cmd


def _isolated_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    home = tmp_path / "home"
    plugins = tmp_path / "plugins"
    home.mkdir(parents=True, exist_ok=True)
    plugins.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["ANTIGRAVITY_PLUGINS_HOME"] = str(plugins)
    return env, plugins


def test_concurrent_install_without_force_serializes_cleanly(tmp_path: Path) -> None:
    cmd = _installer_cmd(force=False)
    rounds = 5 if sys.platform != "win32" else 3
    for i in range(rounds):
        env, plugins = _isolated_env(tmp_path / f"round-{i}")

        p1 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = p1.communicate(timeout=30)
        out2, err2 = p2.communicate(timeout=30)

        codes = sorted([p1.returncode, p2.returncode])
        assert codes[0] == 0 and codes[1] != 0, (
            f"Round {i}: expected exactly one winner and one refusal; got {codes}\n"
            f"p1: {out1}{err1}\np2: {out2}{err2}"
        )

        installed = plugins / "cli-anything"
        assert (installed / "plugin.json").is_file()
        assert (installed / "references" / "HARNESS.md").is_file()
        assert not (installed / "antigravity-plugin").exists()
        assert not list(installed.glob(".cli-anything.tmp.*"))
        assert not (plugins / ".cli-anything.lock").exists()


def test_concurrent_install_with_force_both_succeed_without_corruption(tmp_path: Path) -> None:
    env, plugins = _isolated_env(tmp_path)
    cmd = _installer_cmd(force=True)

    p1 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out1, err1 = p1.communicate(timeout=30)
    out2, err2 = p2.communicate(timeout=30)

    assert p1.returncode == 0, f"p1 failed:\n{out1}{err1}"
    assert p2.returncode == 0, f"p2 failed:\n{out2}{err2}"

    installed = plugins / "cli-anything"
    assert (installed / "plugin.json").is_file()
    assert (installed / "references" / "HARNESS.md").is_file()
    assert (installed / "scripts" / "verify_harness.py").is_file()
    assert not (plugins / ".cli-anything.lock").exists()
