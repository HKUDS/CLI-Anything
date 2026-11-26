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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinked plugins root test")
def test_symlinked_plugins_root_install_and_uninstall_roundtrip(tmp_path: Path) -> None:
    # Reproduce ~/.gemini/config/plugins -> <dir>/plugin-storage (basename != 'plugins')
    # and verify both repo uninstall.sh and self-invoked realpath uninstall.sh succeed cleanly.
    for mode in ("repo-uninstall", "self-symlink-uninstall", "self-realpath-uninstall"):
        case_dir = tmp_path / mode
        home = case_dir / "home"
        config_dir = home / ".gemini" / "config"
        config_dir.mkdir(parents=True)
        storage = case_dir / "plugin-storage"
        storage.mkdir(parents=True)
        plugins_link = config_dir / "plugins"
        plugins_link.symlink_to(storage)

        env = os.environ.copy()
        env["HOME"] = str(home)
        env.pop("ANTIGRAVITY_PLUGINS_HOME", None)

        inst = subprocess.run(
            ["bash", str(PLUGIN_SRC / "scripts" / "install.sh")],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert inst.returncode == 0, f"[{mode}] install failed:\n{inst.stdout}{inst.stderr}"

        installed = storage / "cli-anything"
        pointer = home / ".gemini" / "cli-anything-generator.root"
        assert (installed / "plugin.json").is_file()
        assert pointer.is_file()

        if mode == "repo-uninstall":
            uninstall_script = PLUGIN_SRC / "scripts" / "uninstall.sh"
        elif mode == "self-symlink-uninstall":
            uninstall_script = plugins_link / "cli-anything" / "scripts" / "uninstall.sh"
        else:
            uninstall_script = installed / "scripts" / "uninstall.sh"

        uninst = subprocess.run(
            ["bash", str(uninstall_script)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert uninst.returncode == 0, f"[{mode}] uninstall failed:\n{uninst.stdout}{uninst.stderr}"
        assert not installed.exists(), f"[{mode}] plugin directory was not removed"
        assert not pointer.exists(), f"[{mode}] discovery pointer was not removed"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX to_host_path preservation test")
def test_posix_single_letter_root_path_is_not_rewritten_to_windows_drive() -> None:
    lib_sh = PLUGIN_SRC / "scripts" / "lib.sh"
    proc = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{lib_sh}" && printf "%s\\n" "$(to_host_path "/q/custom/plugins/cli-anything")"',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "/q/custom/plugins/cli-anything"

    # On non-WSL native Linux/macOS, /mnt/c/... must also remain untouched POSIX.
    is_wsl = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
    if not is_wsl:
        osrelease = Path("/proc/sys/kernel/osrelease")
        if osrelease.is_file() and any(
            tok in osrelease.read_text(encoding="utf-8", errors="ignore").lower()
            for tok in ("microsoft", "wsl")
        ):
            is_wsl = True
    if not is_wsl:
        mnt_proc = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{lib_sh}" && printf "%s\\n" "$(to_host_path "/mnt/c/custom/plugins/cli-anything")"',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert mnt_proc.returncode == 0, mnt_proc.stderr
        assert mnt_proc.stdout.strip() == "/mnt/c/custom/plugins/cli-anything"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction plugins root test")
def test_windows_junction_plugins_root_workspace_and_global_uninstall(tmp_path: Path) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell, "PowerShell required on Windows"

    def _run_ps(script: Path, env: dict[str, str], *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *extra],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def _mkjunction(link: Path, target: Path) -> None:
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"mklink /J failed: {proc.stdout}{proc.stderr}"

    junctions: list[Path] = []
    try:
        # Case 1: Workspace plugins is a junction -> plugin-storage; invoking uninstall via
        # plugin-storage real path must remove only the workspace copy and leave global intact.
        c1 = tmp_path / "workspace_case"
        home1 = c1 / "home"
        home1.mkdir(parents=True)
        ws1 = c1 / "ws"
        (ws1 / ".agents").mkdir(parents=True)
        ws_storage = c1 / "plugin-storage"
        ws_storage.mkdir(parents=True)
        ws_plugins_link = ws1 / ".agents" / "plugins"
        _mkjunction(ws_plugins_link, ws_storage)
        junctions.append(ws_plugins_link)

        env1 = os.environ.copy()
        env1["HOME"] = str(home1)
        env1["USERPROFILE"] = str(home1)
        env1.pop("ANTIGRAVITY_PLUGINS_HOME", None)

        g_inst = _run_ps(PLUGIN_SRC / "scripts" / "install.ps1", env1)
        assert g_inst.returncode == 0, g_inst.stdout + g_inst.stderr
        global_installed = home1 / ".gemini" / "config" / "plugins" / "cli-anything"
        global_pointer = home1 / ".gemini" / "cli-anything-generator.root"
        assert (global_installed / "plugin.json").is_file()
        assert global_pointer.is_file()

        w_inst = _run_ps(PLUGIN_SRC / "scripts" / "install.ps1", env1, "-Workspace", str(ws1))
        assert w_inst.returncode == 0, w_inst.stdout + w_inst.stderr
        ws_installed = ws_storage / "cli-anything"
        assert (ws_installed / "plugin.json").is_file()

        w_uninst = _run_ps(ws_installed / "scripts" / "uninstall.ps1", env1)
        assert w_uninst.returncode == 0, w_uninst.stdout + w_uninst.stderr
        assert not ws_installed.exists(), "workspace install under junction target was not removed"
        assert (global_installed / "plugin.json").is_file(), "global install was unexpectedly removed"
        assert global_pointer.is_file(), "global discovery pointer was unexpectedly removed"

        # Case 2: Global plugins is a junction -> global-storage; invoking uninstall via
        # global-storage real path must remove both the plugin and the discovery pointer.
        c2 = tmp_path / "global_case"
        home2 = c2 / "home"
        (home2 / ".gemini" / "config").mkdir(parents=True)
        g_storage = c2 / "global-storage"
        g_storage.mkdir(parents=True)
        g_plugins_link = home2 / ".gemini" / "config" / "plugins"
        _mkjunction(g_plugins_link, g_storage)
        junctions.append(g_plugins_link)

        env2 = os.environ.copy()
        env2["HOME"] = str(home2)
        env2["USERPROFILE"] = str(home2)
        env2.pop("ANTIGRAVITY_PLUGINS_HOME", None)

        g2_inst = _run_ps(PLUGIN_SRC / "scripts" / "install.ps1", env2)
        assert g2_inst.returncode == 0, g2_inst.stdout + g2_inst.stderr
        g2_installed = g_storage / "cli-anything"
        g2_pointer = home2 / ".gemini" / "cli-anything-generator.root"
        assert (g2_installed / "plugin.json").is_file()
        assert g2_pointer.is_file()

        g2_uninst = _run_ps(g2_installed / "scripts" / "uninstall.ps1", env2)
        assert g2_uninst.returncode == 0, g2_uninst.stdout + g2_uninst.stderr
        assert not g2_installed.exists(), "global install under junction target was not removed"
        assert not g2_pointer.exists(), "global discovery pointer was not removed"
    finally:
        for junc in junctions:
            if junc.exists():
                os.rmdir(junc)
