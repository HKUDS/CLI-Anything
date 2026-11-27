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


@pytest.mark.skipif(sys.platform != "linux", reason="Case-sensitive Linux filesystem test")
def test_linux_uninstall_preserves_distinct_case_discovery_pointer(tmp_path: Path) -> None:
    upper = tmp_path / "Case" / "plugins"
    lower = tmp_path / "case" / "plugins"
    upper.mkdir(parents=True)
    lower.mkdir(parents=True)
    # Skip cleanly if running on a case-insensitive mount (e.g. NTFS /mnt/c).
    if os.path.samefile(upper, lower):
        pytest.skip("Mount is case-insensitive")

    home = tmp_path / "home"
    home.mkdir(parents=True)
    env_upper = os.environ.copy()
    env_upper["HOME"] = str(home)
    env_upper["ANTIGRAVITY_PLUGINS_HOME"] = str(upper)

    env_lower = os.environ.copy()
    env_lower["HOME"] = str(home)
    env_lower["ANTIGRAVITY_PLUGINS_HOME"] = str(lower)

    r1 = subprocess.run(
        ["bash", str(PLUGIN_SRC / "scripts" / "install.sh")],
        env=env_upper, capture_output=True, text=True, check=False,
    )
    assert r1.returncode == 0, r1.stdout + r1.stderr

    r2 = subprocess.run(
        ["bash", str(PLUGIN_SRC / "scripts" / "install.sh")],
        env=env_lower, capture_output=True, text=True, check=False,
    )
    assert r2.returncode == 0, r2.stdout + r2.stderr

    pointer = home / ".gemini" / "cli-anything-generator.root"
    assert pointer.read_text(encoding="utf-8").strip() == str((lower / "cli-anything").resolve())

    # Uninstalling the Uppercase install must NOT remove the lowercase discovery pointer.
    u1 = subprocess.run(
        ["bash", str(PLUGIN_SRC / "scripts" / "uninstall.sh")],
        env=env_upper, capture_output=True, text=True, check=False,
    )
    assert u1.returncode == 0, u1.stdout + u1.stderr
    assert not (upper / "cli-anything").exists()
    assert (lower / "cli-anything" / "plugin.json").is_file()
    assert pointer.is_file()
    assert pointer.read_text(encoding="utf-8").strip() == str((lower / "cli-anything").resolve())


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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell lock-ownership test")
def test_windows_release_lock_does_not_delete_unacquired_foreign_lock(tmp_path: Path) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell, "PowerShell required on Windows"

    lib_ps1 = PLUGIN_SRC / "scripts" / "lib.ps1"
    foreign_lock = tmp_path / ".cli-anything.lock"
    foreign_lock.write_text("99999\n", encoding="utf-8")

    # Simulate install.ps1's try/finally when Acquire-CliAnythingInstallLock times out against
    # a non-open Bash lock file: Release-CliAnythingInstallLock must NOT delete the foreign lock.
    script = (
        f'. "{lib_ps1}"; '
        f'$lockPath = "{foreign_lock}"; '
        "$lockHandle = $null; "
        "$threw = $false; "
        "try { "
        "  try { $lockHandle = Acquire-CliAnythingInstallLock -LockPath $lockPath -MaxAttempts 2 } "
        "  catch { $threw = $true } "
        "} finally { "
        "  Release-CliAnythingInstallLock -LockHandle $lockHandle -LockPath $lockPath "
        "}; "
        "if (-not $threw) { exit 2 }"
    )
    proc = subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert foreign_lock.is_file(), "unacquired foreign lock file was deleted"
    assert foreign_lock.read_text(encoding="utf-8").strip() == "99999"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction + Bash uninstall test")
def test_windows_junction_ps_install_and_bash_self_uninstall(tmp_path: Path) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell, "PowerShell required on Windows"
    git_bash = None
    for candidate in (
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
    ):
        if candidate.is_file():
            git_bash = str(candidate)
            break
    if git_bash is None:
        which_bash = shutil.which("bash")
        if which_bash and "system32" not in which_bash.lower():
            git_bash = which_bash
    if git_bash is None:
        pytest.skip("Git Bash / MSYS bash not installed")

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
        # Case 1: Workspace installed via install.ps1 under a junctioned plugins root; invoking
        # Bash uninstall.sh via the physical junction target must remove ONLY the workspace copy
        # and leave the separate global install & pointer untouched.
        c1 = tmp_path / "ws_case"
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

        b_uninst = subprocess.run(
            [git_bash, str(ws_installed / "scripts" / "uninstall.sh")],
            env=env1,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert b_uninst.returncode == 0, b_uninst.stdout + b_uninst.stderr
        assert not ws_installed.exists(), "workspace install under junction target was not removed by uninstall.sh"
        assert (global_installed / "plugin.json").is_file(), "global install was unexpectedly deleted by uninstall.sh"
        assert global_pointer.is_file(), "global discovery pointer was unexpectedly deleted"

        # Case 2: Global installed via install.ps1 under a junctioned plugins root; invoking
        # Bash uninstall.sh via the physical junction target removes both the install and pointer.
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

        b2_uninst = subprocess.run(
            [git_bash, str(g2_installed / "scripts" / "uninstall.sh")],
            env=env2,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert b2_uninst.returncode == 0, b2_uninst.stdout + b2_uninst.stderr
        assert not g2_installed.exists(), "global install under junction target was not removed by uninstall.sh"
        assert not g2_pointer.exists(), "global discovery pointer was not removed by uninstall.sh"
    finally:
        for junc in junctions:
            if junc.exists():
                os.rmdir(junc)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink workspace self-uninstall test")
def test_posix_symlink_workspace_self_uninstall_preserves_global(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    ws = tmp_path / "ws"
    (ws / ".agents").mkdir(parents=True)
    ws_storage = tmp_path / "plugin-storage"
    ws_storage.mkdir(parents=True)
    (ws / ".agents" / "plugins").symlink_to(ws_storage)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("ANTIGRAVITY_PLUGINS_HOME", None)

    g_inst = subprocess.run(
        ["bash", str(PLUGIN_SRC / "scripts" / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert g_inst.returncode == 0, g_inst.stdout + g_inst.stderr
    global_installed = home / ".gemini" / "config" / "plugins" / "cli-anything"
    global_pointer = home / ".gemini" / "cli-anything-generator.root"
    assert (global_installed / "plugin.json").is_file()
    assert global_pointer.is_file()

    w_inst = subprocess.run(
        ["bash", str(PLUGIN_SRC / "scripts" / "install.sh"), "--workspace", str(ws)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert w_inst.returncode == 0, w_inst.stdout + w_inst.stderr
    ws_installed = ws_storage / "cli-anything"
    assert (ws_installed / "plugin.json").is_file()
    # Stamp logical symlinked destination (simulating an installer that stamps logical paths).
    (ws_installed / "PLUGIN_ROOT.txt").write_text(
        f"{ws / '.agents' / 'plugins' / 'cli-anything'}\n", encoding="utf-8"
    )

    u_ws = subprocess.run(
        ["bash", str(ws_installed / "scripts" / "uninstall.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert u_ws.returncode == 0, u_ws.stdout + u_ws.stderr
    assert not ws_installed.exists()
    assert (global_installed / "plugin.json").is_file()
    assert global_pointer.is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows stale PLUGIN_ROOT.txt refusal test")
def test_windows_stale_plugin_root_refuses_global_fallback(tmp_path: Path) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell, "PowerShell required on Windows"

    git_bash = None
    for candidate in (
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
    ):
        if candidate.is_file():
            git_bash = str(candidate)
            break
    if git_bash is None:
        which_bash = shutil.which("bash")
        if which_bash and "system32" not in which_bash.lower():
            git_bash = which_bash

    home = tmp_path / "home"
    home.mkdir(parents=True)
    ws = tmp_path / "ws"
    ws.mkdir(parents=True)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env.pop("ANTIGRAVITY_PLUGINS_HOME", None)

    def _run_ps(script: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *extra],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    assert _run_ps(PLUGIN_SRC / "scripts" / "install.ps1").returncode == 0
    assert _run_ps(PLUGIN_SRC / "scripts" / "install.ps1", "-Workspace", str(ws)).returncode == 0

    global_installed = home / ".gemini" / "config" / "plugins" / "cli-anything"
    global_pointer = home / ".gemini" / "cli-anything-generator.root"
    assert (global_installed / "plugin.json").is_file()
    assert global_pointer.is_file()

    # Rename workspace so its installed PLUGIN_ROOT.txt stamp becomes stale.
    ws_renamed = tmp_path / "ws-renamed"
    ws.rename(ws_renamed)
    stale_ws_installed = ws_renamed / ".agents" / "plugins" / "cli-anything"
    assert (stale_ws_installed / "PLUGIN_ROOT.txt").is_file()

    # Invoking uninstall.ps1 from the relocated copy without -Workspace MUST fail and preserve global.
    ps_res = _run_ps(stale_ws_installed / "scripts" / "uninstall.ps1")
    assert ps_res.returncode != 0, "expected stale PLUGIN_ROOT.txt to refuse global fallback"
    assert (global_installed / "plugin.json").is_file(), "global install was unexpectedly deleted"
    assert global_pointer.is_file(), "global discovery pointer was unexpectedly deleted"
    assert (stale_ws_installed / "plugin.json").is_file(), "relocated workspace copy was unexpectedly deleted"

    # Invoking uninstall.sh from the relocated copy without --workspace MUST also fail and preserve global.
    if git_bash is not None:
        sh_res = subprocess.run(
            [git_bash, str(stale_ws_installed / "scripts" / "uninstall.sh")],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert sh_res.returncode != 0, "expected stale PLUGIN_ROOT.txt to refuse global fallback in uninstall.sh"
        assert (global_installed / "plugin.json").is_file(), "global install was deleted by uninstall.sh"
        assert global_pointer.is_file(), "global discovery pointer was deleted by uninstall.sh"
        assert (stale_ws_installed / "plugin.json").is_file()

    # Explicit -Workspace targeting the renamed workspace removes only the relocated copy.
    ws_rm = _run_ps(stale_ws_installed / "scripts" / "uninstall.ps1", "-Workspace", str(ws_renamed))
    assert ws_rm.returncode == 0, ws_rm.stdout + ws_rm.stderr
    assert not stale_ws_installed.exists()
    assert (global_installed / "plugin.json").is_file()
    assert global_pointer.is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX stale PLUGIN_ROOT.txt refusal test")
def test_posix_stale_plugin_root_refuses_global_fallback(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    ws = tmp_path / "ws"
    ws.mkdir(parents=True)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("ANTIGRAVITY_PLUGINS_HOME", None)

    g_inst = subprocess.run(
        ["bash", str(PLUGIN_SRC / "scripts" / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert g_inst.returncode == 0, g_inst.stdout + g_inst.stderr
    w_inst = subprocess.run(
        ["bash", str(PLUGIN_SRC / "scripts" / "install.sh"), "--workspace", str(ws)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert w_inst.returncode == 0, w_inst.stdout + w_inst.stderr

    global_installed = home / ".gemini" / "config" / "plugins" / "cli-anything"
    global_pointer = home / ".gemini" / "cli-anything-generator.root"
    assert (global_installed / "plugin.json").is_file()
    assert global_pointer.is_file()

    ws_renamed = tmp_path / "ws-renamed"
    ws.rename(ws_renamed)
    stale_ws_installed = ws_renamed / ".agents" / "plugins" / "cli-anything"
    assert (stale_ws_installed / "PLUGIN_ROOT.txt").is_file()

    # Invoking uninstall.sh from the relocated copy without --workspace MUST fail and preserve global.
    u_stale = subprocess.run(
        ["bash", str(stale_ws_installed / "scripts" / "uninstall.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert u_stale.returncode != 0, "expected stale PLUGIN_ROOT.txt to refuse global fallback"
    assert (global_installed / "plugin.json").is_file(), "global install was unexpectedly deleted"
    assert global_pointer.is_file(), "global discovery pointer was unexpectedly deleted"
    assert (stale_ws_installed / "plugin.json").is_file()

    # Explicit --workspace targeting the renamed workspace removes only the relocated copy.
    u_ws = subprocess.run(
        ["bash", str(stale_ws_installed / "scripts" / "uninstall.sh"), "--workspace", str(ws_renamed)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert u_ws.returncode == 0, u_ws.stdout + u_ws.stderr
    assert not stale_ws_installed.exists()
    assert (global_installed / "plugin.json").is_file()
    assert global_pointer.is_file()


def test_concurrent_distinct_roots_publish_discovery_pointer_atomically(tmp_path: Path) -> None:
    cmd = _installer_cmd(force=True)
    rounds = 6 if sys.platform != "win32" else 3
    for i in range(rounds):
        case_dir = tmp_path / f"ptr-race-{i}"
        home = case_dir / "home"
        short_plugins = case_dir / "a" / "plugins"
        long_plugins = (
            case_dir
            / "very-long-distinct-plugin-root-directory-name-for-atomic-pointer-race"
            / "plugins"
        )
        home.mkdir(parents=True)
        short_plugins.mkdir(parents=True)
        long_plugins.mkdir(parents=True)

        env_short = os.environ.copy()
        env_short["HOME"] = str(home)
        env_short["USERPROFILE"] = str(home)
        env_short["ANTIGRAVITY_PLUGINS_HOME"] = str(short_plugins)

        env_long = os.environ.copy()
        env_long["HOME"] = str(home)
        env_long["USERPROFILE"] = str(home)
        env_long["ANTIGRAVITY_PLUGINS_HOME"] = str(long_plugins)

        p1 = subprocess.Popen(cmd, env=env_short, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen(cmd, env=env_long, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = p1.communicate(timeout=45)
        out2, err2 = p2.communicate(timeout=45)

        assert p1.returncode == 0, f"Round {i} short failed:\n{out1}{err1}"
        assert p2.returncode == 0, f"Round {i} long failed:\n{out2}{err2}"

        pointer = home / ".gemini" / "cli-anything-generator.root"
        assert pointer.is_file(), f"Round {i}: discovery pointer missing"
        raw_lines = pointer.read_text(encoding="utf-8").splitlines()
        assert len(raw_lines) == 1, f"Round {i}: pointer corrupted with multiple/empty lines: {raw_lines!r}"

        expected = {
            str((short_plugins / "cli-anything").resolve()),
            str((long_plugins / "cli-anything").resolve()),
        }
        got = raw_lines[0].strip()
        if sys.platform == "win32":
            assert got.lower() in {e.lower() for e in expected}, f"Round {i}: unexpected pointer {got!r} not in {expected}"
        else:
            assert got in expected, f"Round {i}: unexpected pointer {got!r} not in {expected}"

        gemini_dir = home / ".gemini"
        assert not (gemini_dir / ".cli-anything-generator.root.lock").exists()
        assert not list(gemini_dir.glob(".cli-anything-generator.root.tmp.*"))


def test_uninstall_holds_pointer_lock_against_concurrent_install_publication(tmp_path: Path) -> None:
    import time

    def _uninstall_cmd(script_dir: Path) -> list[str]:
        if sys.platform == "win32":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            assert shell, "PowerShell required on Windows"
            return [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_dir / "uninstall.ps1"),
            ]
        return ["bash", str(script_dir / "uninstall.sh")]

    # Part 1 (deterministic): hold .cli-anything-generator.root.lock while root A uninstalls,
    # swap the discovery pointer to root B before releasing the lock, and verify A waits for
    # the lock and leaves B's pointer intact.
    det_dir = tmp_path / "deterministic"
    home = det_dir / "home"
    root_a = det_dir / "root-a" / "plugins"
    root_b = det_dir / "root-b" / "plugins"
    home.mkdir(parents=True)
    root_a.mkdir(parents=True)
    root_b.mkdir(parents=True)

    env_a = os.environ.copy()
    env_a["HOME"] = str(home)
    env_a["USERPROFILE"] = str(home)
    env_a["ANTIGRAVITY_PLUGINS_HOME"] = str(root_a)

    inst_a = subprocess.run(_installer_cmd(force=True), env=env_a, capture_output=True, text=True, check=False)
    assert inst_a.returncode == 0, inst_a.stdout + inst_a.stderr

    pointer = home / ".gemini" / "cli-anything-generator.root"
    ptr_lock = home / ".gemini" / ".cli-anything-generator.root.lock"
    assert pointer.is_file()

    # Hold the shared pointer lock, launch uninstall of root A, then simulate root B updating
    # the pointer atomically before releasing the lock.
    ptr_lock.write_text("holder\n", encoding="utf-8")
    try:
        uninst_proc = subprocess.Popen(
            _uninstall_cmd(PLUGIN_SRC / "scripts"),
            env=env_a,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Wait until root A's directory has been deleted and uninstall is blocked on ptr_lock.
        deadline = time.monotonic() + 20.0
        while (root_a / "cli-anything").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(0.3)
        assert uninst_proc.poll() is None, "uninstall did not wait for shared discovery-pointer lock"

        b_target = str((root_b / "cli-anything").resolve())
        pointer.write_text(b_target + "\n", encoding="utf-8")
    finally:
        if ptr_lock.exists():
            ptr_lock.unlink()

    out_u, err_u = uninst_proc.communicate(timeout=30)
    assert uninst_proc.returncode == 0, f"uninstall failed:\n{out_u}{err_u}"
    assert not (root_a / "cli-anything").exists()
    assert pointer.is_file(), "root A uninstall deleted root B's newly published discovery pointer"
    assert pointer.read_text(encoding="utf-8").strip().lower() == b_target.lower()
    assert not ptr_lock.exists()

    # Part 2 (concurrent stress): overlap root A uninstall and root B install under the same HOME.
    rounds = 5 if sys.platform != "win32" else 3
    for i in range(rounds):
        case_dir = tmp_path / f"overlap-{i}"
        h = case_dir / "home"
        pa = case_dir / "root-a" / "plugins"
        pb = case_dir / "root-b" / "plugins"
        h.mkdir(parents=True)
        pa.mkdir(parents=True)
        pb.mkdir(parents=True)

        ea = os.environ.copy()
        ea["HOME"] = str(h)
        ea["USERPROFILE"] = str(h)
        ea["ANTIGRAVITY_PLUGINS_HOME"] = str(pa)

        eb = os.environ.copy()
        eb["HOME"] = str(h)
        eb["USERPROFILE"] = str(h)
        eb["ANTIGRAVITY_PLUGINS_HOME"] = str(pb)

        r_setup = subprocess.run(_installer_cmd(force=True), env=ea, capture_output=True, text=True, check=False)
        assert r_setup.returncode == 0, r_setup.stdout + r_setup.stderr

        p_uninst = subprocess.Popen(
            _uninstall_cmd(PLUGIN_SRC / "scripts"),
            env=ea,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        p_inst = subprocess.Popen(
            _installer_cmd(force=True),
            env=eb,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        u_out, u_err = p_uninst.communicate(timeout=45)
        i_out, i_err = p_inst.communicate(timeout=45)
        assert p_uninst.returncode == 0, f"Round {i} uninstall A failed:\n{u_out}{u_err}"
        assert p_inst.returncode == 0, f"Round {i} install B failed:\n{i_out}{i_err}"

        assert not (pa / "cli-anything").exists()
        assert (pb / "cli-anything" / "plugin.json").is_file()
        ptr = h / ".gemini" / "cli-anything-generator.root"
        assert ptr.is_file(), f"Round {i}: discovery pointer was deleted during A uninstall / B install overlap"
        exp_b = str((pb / "cli-anything").resolve())
        got_ptr = ptr.read_text(encoding="utf-8").strip()
        if sys.platform == "win32":
            assert got_ptr.lower() == exp_b.lower(), f"Round {i}: pointer={got_ptr!r}, expected {exp_b!r}"
        else:
            assert got_ptr == exp_b, f"Round {i}: pointer={got_ptr!r}, expected {exp_b!r}"
        assert not (h / ".gemini" / ".cli-anything-generator.root.lock").exists()


def test_uninstall_serializes_with_same_root_reinstall_via_install_lock(tmp_path: Path) -> None:
    import time

    def _uninstall_cmd(script_dir: Path) -> list[str]:
        if sys.platform == "win32":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            assert shell, "PowerShell required on Windows"
            return [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_dir / "uninstall.ps1"),
            ]
        return ["bash", str(script_dir / "uninstall.sh")]

    # Part 1 (deterministic): pause uninstall right after directory removal by holding the shared
    # pointer lock, then launch a reinstall targeting the SAME plugins root. The reinstall MUST
    # wait on the per-root `.cli-anything.lock` held by uninstall so it publishes its pointer
    # only AFTER uninstall finishes cleanup.
    det_dir = tmp_path / "same-root-det"
    home = det_dir / "home"
    plugins = det_dir / "plugins"
    home.mkdir(parents=True)
    plugins.mkdir(parents=True)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["ANTIGRAVITY_PLUGINS_HOME"] = str(plugins)

    setup_res = subprocess.run(_installer_cmd(force=True), env=env, capture_output=True, text=True, check=False)
    assert setup_res.returncode == 0, setup_res.stdout + setup_res.stderr

    pointer = home / ".gemini" / "cli-anything-generator.root"
    ptr_lock = home / ".gemini" / ".cli-anything-generator.root.lock"
    root_lock = plugins / ".cli-anything.lock"
    assert pointer.is_file()

    ptr_lock.write_text("pause-after-rm\n", encoding="utf-8")
    p_reinstall = None
    try:
        p_uninst = subprocess.Popen(
            _uninstall_cmd(PLUGIN_SRC / "scripts"),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 20.0
        while (plugins / "cli-anything").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not (plugins / "cli-anything").exists(), "uninstall did not remove plugin directory in time"
        time.sleep(0.25)
        assert p_uninst.poll() is None, "uninstall did not wait on shared pointer lock"
        assert root_lock.exists(), "uninstall did not hold per-root .cli-anything.lock across cleanup"

        # Start reinstall into the same root while uninstall is paused between rm and pointer cleanup.
        p_reinstall = subprocess.Popen(
            _installer_cmd(force=True),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.35)
        assert p_reinstall.poll() is None, "reinstall did not wait for per-root .cli-anything.lock"
    finally:
        if ptr_lock.exists():
            ptr_lock.unlink()

    u_out, u_err = p_uninst.communicate(timeout=30)
    assert p_uninst.returncode == 0, f"uninstall failed:\n{u_out}{u_err}"
    assert p_reinstall is not None
    i_out, i_err = p_reinstall.communicate(timeout=30)
    assert p_reinstall.returncode == 0, f"reinstall failed:\n{i_out}{i_err}"

    expected = str((plugins / "cli-anything").resolve())
    assert (plugins / "cli-anything" / "plugin.json").is_file(), "reinstalled plugin missing"
    assert pointer.is_file(), "discovery pointer was deleted after same-root reinstall"
    got = pointer.read_text(encoding="utf-8").strip()
    if sys.platform == "win32":
        assert got.lower() == expected.lower()
    else:
        assert got == expected
    assert not root_lock.exists()
    assert not ptr_lock.exists()

    # Part 2 (concurrent stress): overlapping same-root uninstall + reinstall must always end in
    # a consistent state where plugin presence and discovery pointer presence match.
    rounds = 5 if sys.platform != "win32" else 3
    for i in range(rounds):
        case_dir = tmp_path / f"same-root-stress-{i}"
        h = case_dir / "home"
        pdir = case_dir / "plugins"
        h.mkdir(parents=True)
        pdir.mkdir(parents=True)

        e = os.environ.copy()
        e["HOME"] = str(h)
        e["USERPROFILE"] = str(h)
        e["ANTIGRAVITY_PLUGINS_HOME"] = str(pdir)

        r0 = subprocess.run(_installer_cmd(force=True), env=e, capture_output=True, text=True, check=False)
        assert r0.returncode == 0, r0.stdout + r0.stderr

        pu = subprocess.Popen(
            _uninstall_cmd(PLUGIN_SRC / "scripts"),
            env=e,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        pi = subprocess.Popen(
            _installer_cmd(force=True),
            env=e,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        uo, ue = pu.communicate(timeout=45)
        io, ie = pi.communicate(timeout=45)
        assert pu.returncode == 0, f"Round {i} uninstall failed:\n{uo}{ue}"
        assert pi.returncode == 0, f"Round {i} reinstall failed:\n{io}{ie}"

        installed_exists = (pdir / "cli-anything" / "plugin.json").is_file()
        ptr = h / ".gemini" / "cli-anything-generator.root"
        if installed_exists:
            assert ptr.is_file(), f"Round {i}: plugin present but discovery pointer missing"
            exp = str((pdir / "cli-anything").resolve())
            val = ptr.read_text(encoding="utf-8").strip()
            assert (val.lower() == exp.lower()) if sys.platform == "win32" else (val == exp)
        else:
            assert not (pdir / "cli-anything").exists(), f"Round {i}: partial plugin directory left behind"
            assert not ptr.exists(), f"Round {i}: plugin removed but stale discovery pointer remained"
        assert not (pdir / ".cli-anything.lock").exists()
        assert not (h / ".gemini" / ".cli-anything-generator.root.lock").exists()


def test_uninstall_acquires_lock_even_when_plugins_root_absent(tmp_path: Path) -> None:
    """Uninstall targeting a not-yet-created plugins root must still acquire the per-root lock
    so a concurrent first install cannot race with discovery-pointer cleanup."""
    import time

    def _uninstall_cmd(script_dir: Path) -> list[str]:
        if sys.platform == "win32":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            assert shell, "PowerShell required on Windows"
            return [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_dir / "uninstall.ps1"),
            ]
        return ["bash", str(script_dir / "uninstall.sh")]

    home = tmp_path / "home"
    plugins = tmp_path / "absent-root" / "plugins"
    gemini_dir = home / ".gemini"
    gemini_dir.mkdir(parents=True)
    # Note: `plugins` intentionally does NOT exist yet.

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["ANTIGRAVITY_PLUGINS_HOME"] = str(plugins)

    pointer = gemini_dir / "cli-anything-generator.root"
    ptr_lock = gemini_dir / ".cli-anything-generator.root.lock"
    root_lock = plugins / ".cli-anything.lock"

    # Hold the shared pointer lock so uninstall pauses after checking DEST_DIR and before pointer cleanup.
    ptr_lock.write_text("99999\n", encoding="utf-8")
    p_install: subprocess.Popen[str] | None = None
    try:
        p_uninst = subprocess.Popen(
            _uninstall_cmd(PLUGIN_SRC / "scripts"),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not root_lock.exists():
            if p_uninst.poll() is not None:
                break
            time.sleep(0.05)
        assert root_lock.exists(), "uninstall skipped per-root .cli-anything.lock when plugins root was absent"
        assert p_uninst.poll() is None, "uninstall did not wait on shared pointer lock"

        # Start the first install into the same root; it MUST block on root_lock until uninstall finishes.
        p_install = subprocess.Popen(
            _installer_cmd(force=True),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.35)
        assert p_install.poll() is None, "first install did not serialize against uninstall's per-root lock"
    finally:
        if ptr_lock.exists():
            ptr_lock.unlink()

    u_out, u_err = p_uninst.communicate(timeout=30)
    assert p_uninst.returncode == 0, f"uninstall failed:\n{u_out}{u_err}"
    assert p_install is not None
    i_out, i_err = p_install.communicate(timeout=30)
    assert p_install.returncode == 0, f"first install failed:\n{i_out}{i_err}"

    expected = str((plugins / "cli-anything").resolve())
    assert (plugins / "cli-anything" / "plugin.json").is_file(), "installed plugin missing"
    assert pointer.is_file(), "uninstall deleted the discovery pointer written by the first install"
    got = pointer.read_text(encoding="utf-8").strip()
    assert (got.lower() == expected.lower()) if sys.platform == "win32" else (got == expected)
    assert not root_lock.exists()
    assert not ptr_lock.exists()


def test_workspace_install_into_source_directory_excludes_staging_subtree(tmp_path: Path) -> None:
    """Running workspace install with --workspace . from the plugin source directory itself
    must exclude .agents / staging subtrees instead of copying staging into itself."""
    sandbox = tmp_path / "self_ws_repo"
    if (PLUGIN_SRC.parent / "cli-anything-plugin" / "HARNESS.md").is_file():
        # Monorepo checkout layout (CLI-Anything/antigravity-plugin + sibling cli-anything-plugin + docs/)
        src_copy = sandbox / "antigravity-plugin"
        shutil.copytree(
            PLUGIN_SRC,
            src_copy,
            ignore=shutil.ignore_patterns(".git", ".agents", "__pycache__", ".pytest_cache"),
        )
        shutil.copytree(
            PLUGIN_SRC.parent / "cli-anything-plugin",
            sandbox / "cli-anything-plugin",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (sandbox / "docs").mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            PLUGIN_SRC.parent / "docs" / "PREVIEW_PROTOCOL.md",
            sandbox / "docs" / "PREVIEW_PROTOCOL.md",
        )
    else:
        # Standalone Community Edition layout
        src_copy = sandbox / "cli-anything-antigravity"
        shutil.copytree(
            PLUGIN_SRC,
            src_copy,
            ignore=shutil.ignore_patterns(".git", ".agents", "__pycache__", ".pytest_cache"),
        )

    home = tmp_path / "home"
    home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)

    if sys.platform == "win32":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        assert shell, "PowerShell required on Windows"
        cmd = [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(src_copy / "scripts" / "install.ps1"),
            "-Workspace",
            ".",
        ]
    else:
        cmd = ["bash", str(src_copy / "scripts" / "install.sh"), "--workspace", "."]

    res = subprocess.run(cmd, cwd=src_copy, env=env, capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"self-workspace install failed:\n{res.stdout}\n{res.stderr}"

    installed = src_copy / ".agents" / "plugins" / "cli-anything"
    assert (installed / "plugin.json").is_file()
    assert not (installed / ".agents").exists(), "staging/workspace .agents subtree leaked into installed plugin"


def test_custom_plugins_home_inside_source_directory_excludes_staging_subtree(tmp_path: Path) -> None:
    """Setting ANTIGRAVITY_PLUGINS_HOME to <plugin-src>/plugins places staging/dest under a non-excluded
    source subdirectory; both PowerShell and Bash installers must exclude that ancestor using matching
    normalized path separators rather than recursing into staging or copying plugins/ into itself."""
    sandbox = tmp_path / "self_custom_plugins_repo"
    if (PLUGIN_SRC.parent / "cli-anything-plugin" / "HARNESS.md").is_file():
        src_copy = sandbox / "antigravity-plugin"
        shutil.copytree(
            PLUGIN_SRC,
            src_copy,
            ignore=shutil.ignore_patterns(".git", ".agents", "__pycache__", ".pytest_cache"),
        )
        shutil.copytree(
            PLUGIN_SRC.parent / "cli-anything-plugin",
            sandbox / "cli-anything-plugin",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (sandbox / "docs").mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            PLUGIN_SRC.parent / "docs" / "PREVIEW_PROTOCOL.md",
            sandbox / "docs" / "PREVIEW_PROTOCOL.md",
        )
    else:
        src_copy = sandbox / "cli-anything-antigravity"
        shutil.copytree(
            PLUGIN_SRC,
            src_copy,
            ignore=shutil.ignore_patterns(".git", ".agents", "__pycache__", ".pytest_cache"),
        )

    home = tmp_path / "home"
    home.mkdir(parents=True)
    custom_plugins = src_copy / "plugins"

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["ANTIGRAVITY_PLUGINS_HOME"] = str(custom_plugins)

    def _run_install(*extra: str) -> subprocess.CompletedProcess[str]:
        if sys.platform == "win32":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            assert shell, "PowerShell required on Windows"
            cmd = [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(src_copy / "scripts" / "install.ps1"),
                *extra,
            ]
        else:
            cmd = ["bash", str(src_copy / "scripts" / "install.sh"), *extra]
        return subprocess.run(cmd, cwd=src_copy, env=env, capture_output=True, text=True, check=False)

    res1 = _run_install()
    assert res1.returncode == 0, f"initial install into <src>/plugins failed:\n{res1.stdout}\n{res1.stderr}"
    installed = custom_plugins / "cli-anything"
    assert (installed / "plugin.json").is_file()
    assert not (installed / "plugins").exists(), "plugins/ ancestor subtree leaked into installed plugin"
    assert not list(installed.glob(".cli-anything.tmp.*")), "staging directory leaked into installed plugin"
    assert not (installed / ".cli-anything.lock").exists(), "lock file leaked into installed plugin"

    force_flag = "-Force" if sys.platform == "win32" else "--force"
    res2 = _run_install(force_flag)
    assert res2.returncode == 0, f"force reinstall into <src>/plugins failed:\n{res2.stdout}\n{res2.stderr}"
    assert (installed / "plugin.json").is_file()
    assert not (installed / "plugins").exists(), "plugins/ ancestor subtree leaked on force reinstall"


def test_nested_install_inside_required_source_subdir_preserves_all_skills(tmp_path: Path) -> None:
    """Installing with --workspace <plugin-src>/skills or ANTIGRAVITY_PLUGINS_HOME=<plugin-src>/skills/plugins
    must preserve all required skills/*/SKILL.md files while excluding only the nested install root."""
    expected_skills = (
        "cli-anything",
        "cli-anything-refine",
        "cli-anything-test",
        "cli-anything-validate",
        "cli-anything-list",
    )

    def _clone_sandbox(name: str, *, dir_name: str | None = None) -> Path:
        sandbox = tmp_path / name
        if (PLUGIN_SRC.parent / "cli-anything-plugin" / "HARNESS.md").is_file():
            src_copy = sandbox / (dir_name or "antigravity-plugin")
            shutil.copytree(
                PLUGIN_SRC,
                src_copy,
                ignore=shutil.ignore_patterns(".git", ".agents", "__pycache__", ".pytest_cache"),
            )
            shutil.copytree(
                PLUGIN_SRC.parent / "cli-anything-plugin",
                sandbox / "cli-anything-plugin",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            (sandbox / "docs").mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                PLUGIN_SRC.parent / "docs" / "PREVIEW_PROTOCOL.md",
                sandbox / "docs" / "PREVIEW_PROTOCOL.md",
            )
            return src_copy
        src_copy = sandbox / (dir_name or "cli-anything-antigravity")
        shutil.copytree(
            PLUGIN_SRC,
            src_copy,
            ignore=shutil.ignore_patterns(".git", ".agents", "__pycache__", ".pytest_cache"),
        )
        return src_copy

    def _run_install(src_copy: Path, env: dict[str, str], *extra: str) -> subprocess.CompletedProcess[str]:
        if sys.platform == "win32":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            assert shell, "PowerShell required on Windows"
            cmd = [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(src_copy / "scripts" / "install.ps1"),
                *extra,
            ]
        else:
            cmd = ["bash", str(src_copy / "scripts" / "install.sh"), *extra]
        return subprocess.run(cmd, cwd=src_copy, env=env, capture_output=True, text=True, check=False)

    # Case 1: --workspace <plugin-src>/skills (workspace install nested inside skills/)
    src1 = _clone_sandbox("nested_ws_skills")
    home1 = tmp_path / "home1"
    home1.mkdir(parents=True)
    env1 = os.environ.copy()
    env1["HOME"] = str(home1)
    env1["USERPROFILE"] = str(home1)
    env1.pop("ANTIGRAVITY_PLUGINS_HOME", None)
    ws_flag = "-Workspace" if sys.platform == "win32" else "--workspace"
    force_flag = "-Force" if sys.platform == "win32" else "--force"

    r1 = _run_install(src1, env1, ws_flag, str(src1 / "skills"))
    assert r1.returncode == 0, f"nested --workspace skills/ install failed:\n{r1.stdout}\n{r1.stderr}"
    inst1 = src1 / "skills" / ".agents" / "plugins" / "cli-anything"
    for sk in expected_skills:
        assert (inst1 / "skills" / sk / "SKILL.md").is_file(), f"missing {sk}/SKILL.md in nested workspace install"
    assert not (inst1 / "skills" / ".agents").exists(), ".agents subtree leaked inside installed skills/"

    # Force upgrade in the same nested workspace must keep all skills intact.
    r1_up = _run_install(src1, env1, ws_flag, str(src1 / "skills"), force_flag)
    assert r1_up.returncode == 0, f"nested --workspace skills/ upgrade failed:\n{r1_up.stdout}\n{r1_up.stderr}"
    for sk in expected_skills:
        assert (inst1 / "skills" / sk / "SKILL.md").is_file(), f"missing {sk}/SKILL.md after upgrade"
    assert not (inst1 / "skills" / ".agents").exists()

    # Case 2: ANTIGRAVITY_PLUGINS_HOME=<plugin-src>/skills/plugins (custom plugins home nested inside skills/)
    src2 = _clone_sandbox("nested_custom_skills_plugins")
    home2 = tmp_path / "home2"
    home2.mkdir(parents=True)
    env2 = os.environ.copy()
    env2["HOME"] = str(home2)
    env2["USERPROFILE"] = str(home2)
    env2["ANTIGRAVITY_PLUGINS_HOME"] = str(src2 / "skills" / "plugins")

    r2 = _run_install(src2, env2)
    assert r2.returncode == 0, f"nested skills/plugins install failed:\n{r2.stdout}\n{r2.stderr}"
    inst2 = src2 / "skills" / "plugins" / "cli-anything"
    for sk in expected_skills:
        assert (inst2 / "skills" / sk / "SKILL.md").is_file(), f"missing {sk}/SKILL.md in skills/plugins install"
    assert not (inst2 / "skills" / "plugins").exists(), "skills/plugins subtree leaked inside installed skills/"

    # Case 3: Refusing to install when DEST_DIR equals PLUGIN_SRC (e.g. <plugins>/cli-anything).
    src3 = _clone_sandbox("plugins", dir_name="cli-anything")
    home3 = tmp_path / "home3"
    home3.mkdir(parents=True)
    env3 = os.environ.copy()
    env3["HOME"] = str(home3)
    env3["USERPROFILE"] = str(home3)
    env3["ANTIGRAVITY_PLUGINS_HOME"] = str(src3.parent)

    r3 = _run_install(src3, env3, force_flag)
    assert r3.returncode != 0, "installer must refuse overwriting its own source directory"
    assert (src3 / "plugin.json").is_file(), "source directory was modified on refused self-overwrite"



