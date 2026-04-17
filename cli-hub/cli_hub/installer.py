"""Install, uninstall, and manage CLIs and matrices."""

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from cli_hub.registry import get_cli
from cli_hub.matrix import get_matrix
from cli_hub.matrix_skill import render_matrix_skill_file

INSTALLED_FILE = Path.home() / ".cli-hub" / "installed.json"


def _load_installed():
    if INSTALLED_FILE.exists():
        try:
            return json.loads(INSTALLED_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_installed(data):
    INSTALLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    INSTALLED_FILE.write_text(json.dumps(data, indent=2))


def _find_npm():
    """Find npm executable. Returns path or None."""
    return shutil.which("npm")


def _find_uv():
    """Find uv executable. Returns path or None."""
    return shutil.which("uv")


_UV_INSTALL_HINT = (
    "uv is not installed. Install it first:\n"
    "  macOS / Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
    "  Windows:       powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"\n"
    "  pip:           pip install uv\n"
    "  brew:          brew install uv\n"
    "  See also:      https://docs.astral.sh/uv/getting-started/installation/"
)


_SHELL_METACHARACTERS = ("|", "&&", "||", ";", "$(", "`")


def _run_command(cmd):
    """Run a command string.

    Uses shell=True when the command contains shell operators (pipes, &&, etc.)
    so that script-type installs like ``curl … | bash`` work correctly.
    Commands come from the trusted registry, not from user input.
    """
    use_shell = any(c in cmd for c in _SHELL_METACHARACTERS)
    try:
        return subprocess.run(
            cmd if use_shell else shlex.split(cmd),
            capture_output=True,
            text=True,
            shell=use_shell,
        )
    except FileNotFoundError as exc:
        missing = exc.filename or shlex.split(cmd)[0]
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=127,
            stdout="",
            stderr=f"Command not found: {missing}",
        )


def _command_exists(cmd):
    """Check whether the executable for a command string exists on PATH."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return False
    if not parts:
        return False
    return shutil.which(parts[0]) is not None


def _install_strategy(cli):
    """Return the install strategy for a CLI entry."""
    strategy = cli.get("install_strategy")
    if strategy:
        return strategy
    if cli.get("_source", "harness") == "harness":
        return "pip"
    if cli.get("npm_package") or cli.get("package_manager") == "npm":
        return "npm"
    if cli.get("package_manager") == "uv":
        return "uv"
    if cli.get("package_manager") == "bundled":
        return "bundled"
    return "command"


def _generic_install(cli):
    install_cmd = cli.get("install_cmd")
    if not install_cmd:
        return False, f"No install command is defined for {cli['display_name']}."
    result = _run_command(install_cmd)
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"Install failed:\n{result.stderr or result.stdout}"


def _generic_uninstall(cli):
    uninstall_cmd = cli.get("uninstall_cmd")
    if not uninstall_cmd:
        note = cli.get("uninstall_notes") or f"No uninstall command is defined for {cli['display_name']}."
        return False, note
    result = _run_command(uninstall_cmd)
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"Uninstall failed:\n{result.stderr or result.stdout}"


def _generic_update(cli):
    update_cmd = cli.get("update_cmd")
    if not update_cmd:
        note = cli.get("update_notes") or f"No update command is defined for {cli['display_name']}."
        return False, note
    result = _run_command(update_cmd)
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']}"
    return False, f"Update failed:\n{result.stderr or result.stdout}"


def _bundled_install(cli):
    detect_cmd = cli.get("detect_cmd") or cli.get("entry_point")
    if detect_cmd and _command_exists(detect_cmd):
        return True, f"{cli['display_name']} is already available ({cli['entry_point']})"
    note = cli.get("install_notes") or (
        f"{cli['display_name']} is bundled with its parent app. "
        "Install or enable it in the upstream app first, then run this command again."
    )
    return False, note


def _bundled_uninstall(cli):
    note = cli.get("uninstall_notes") or (
        f"{cli['display_name']} is bundled with its parent app. "
        "Disable it in the upstream app or uninstall the parent app manually."
    )
    return False, note


def _bundled_update(cli):
    note = cli.get("update_notes") or (
        f"{cli['display_name']} is bundled with its parent app. "
        "Update the parent app to update this CLI."
    )
    return False, note


# ── pip operations (harness CLIs) ──


def _pip_install(cli):
    install_cmd = cli["install_cmd"]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install"] + install_cmd.replace("pip install ", "").split(),
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"pip install failed:\n{result.stderr}"


def _pip_uninstall(cli):
    pkg_name = f"cli-anything-{cli['name']}"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", pkg_name],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"pip uninstall failed:\n{result.stderr}"


def _pip_update(cli):
    install_cmd = cli["install_cmd"]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall"]
        + install_cmd.replace("pip install ", "").split(),
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']} to {cli['version']}"
    return False, f"Update failed:\n{result.stderr}"


# ── uv operations (public CLIs) ──


def _uv_install(cli):
    if _find_uv() is None:
        return False, _UV_INSTALL_HINT
    result = _run_command(cli["install_cmd"])
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"uv install failed:\n{result.stderr or result.stdout}"


def _uv_uninstall(cli):
    if _find_uv() is None:
        return False, _UV_INSTALL_HINT
    uninstall_cmd = cli.get("uninstall_cmd")
    if not uninstall_cmd:
        return False, f"No uninstall command is defined for {cli['display_name']}."
    result = _run_command(uninstall_cmd)
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"uv uninstall failed:\n{result.stderr or result.stdout}"


def _uv_update(cli):
    if _find_uv() is None:
        return False, _UV_INSTALL_HINT
    update_cmd = cli.get("update_cmd")
    if not update_cmd:
        return False, f"No update command is defined for {cli['display_name']}."
    result = _run_command(update_cmd)
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']}"
    return False, f"uv update failed:\n{result.stderr or result.stdout}"


# ── npm operations (public CLIs) ──


def _npm_install(cli):
    npm = _find_npm()
    if npm is None:
        return False, (
            "npm is not installed. Install Node.js first:\n"
            "  macOS: brew install node\n"
            "  Linux: curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs\n"
            "  Windows: Download from https://nodejs.org"
        )
    result = subprocess.run(
        [npm, "install", "-g", cli["npm_package"]],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"npm install failed:\n{result.stderr}"


def _npm_uninstall(cli):
    npm = _find_npm()
    if npm is None:
        return False, "npm is not installed."
    result = subprocess.run(
        [npm, "uninstall", "-g", cli["npm_package"]],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"npm uninstall failed:\n{result.stderr}"


def _npm_update(cli):
    npm = _find_npm()
    if npm is None:
        return False, "npm is not installed."
    result = subprocess.run(
        [npm, "install", "-g", cli["npm_package"] + "@latest"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']} to latest"
    return False, f"Update failed:\n{result.stderr}"


def _perform_action(cli, action):
    """Dispatch install/uninstall/update based on CLI strategy."""
    strategy = _install_strategy(cli)
    actions = {
        "pip": {"install": _pip_install, "uninstall": _pip_uninstall, "update": _pip_update},
        "npm": {"install": _npm_install, "uninstall": _npm_uninstall, "update": _npm_update},
        "uv": {"install": _uv_install, "uninstall": _uv_uninstall, "update": _uv_update},
        "command": {"install": _generic_install, "uninstall": _generic_uninstall, "update": _generic_update},
        "bundled": {"install": _bundled_install, "uninstall": _bundled_uninstall, "update": _bundled_update},
    }
    handler = actions.get(strategy, actions["command"]).get(action)
    return strategy, handler(cli)


def _installed_entry(cli, source, strategy):
    """Return the installed.json payload for a CLI."""
    entry = {
        "version": cli["version"],
        "entry_point": cli["entry_point"],
        "source": source,
        "strategy": strategy,
    }
    if cli.get("package_manager"):
        entry["package_manager"] = cli["package_manager"]
    if cli.get("npm_package"):
        entry["npm_package"] = cli["npm_package"]
    if cli.get("install_cmd"):
        entry["install_cmd"] = cli["install_cmd"]
    if cli.get("uninstall_cmd"):
        entry["uninstall_cmd"] = cli["uninstall_cmd"]
    if cli.get("update_cmd"):
        entry["update_cmd"] = cli["update_cmd"]
    return entry


# ── Unified interface ──


def install_cli(name):
    """Install a CLI by name. Dispatches to pip or npm based on source. Returns (success, message)."""
    cli = get_cli(name)
    if cli is None:
        return False, f"CLI '{name}' not found in registry. Use 'cli-hub list' to see available CLIs."

    source = cli.get("_source", "harness")
    strategy, (success, msg) = _perform_action(cli, "install")

    if success:
        installed = _load_installed()
        installed[cli["name"]] = _installed_entry(cli, source, strategy)
        _save_installed(installed)

    return success, msg


def uninstall_cli(name):
    """Uninstall a CLI by name. Returns (success, message)."""
    cli = get_cli(name)
    if cli is None:
        return False, f"CLI '{name}' not found in registry."

    _, (success, msg) = _perform_action(cli, "uninstall")

    if success:
        installed = _load_installed()
        installed.pop(cli["name"], None)
        _save_installed(installed)

    return success, msg


def update_cli(name):
    """Update a CLI by reinstalling. Returns (success, message)."""
    cli = get_cli(name, force_refresh=True)
    if cli is None:
        return False, f"CLI '{name}' not found in registry."

    source = cli.get("_source", "harness")
    strategy, (success, msg) = _perform_action(cli, "update")

    if success:
        installed = _load_installed()
        installed[cli["name"]] = _installed_entry(cli, source, strategy)
        _save_installed(installed)

    return success, msg


def get_installed():
    """Return dict of installed CLIs."""
    return _load_installed()


def install_matrix(name):
    """Install every CLI in a named matrix.

    Returns ``(success, payload)`` where payload contains the matrix metadata,
    per-CLI results, and an aggregate summary. Success is false when any member
    install fails or the matrix cannot be found.
    """
    matrix_item = get_matrix(name)
    if matrix_item is None:
        return False, {"error": f"Matrix '{name}' not found. Use 'cli-hub matrix list' to see available matrices."}

    installed = set(get_installed())
    results = []

    for cli_name in matrix_item.get("clis", []):
        cli = get_cli(cli_name)
        display_name = cli["display_name"] if cli else cli_name

        if cli_name in installed:
            results.append({
                "name": cli_name,
                "display_name": display_name,
                "status": "skipped",
                "message": "Already installed",
            })
            continue

        if cli is None:
            results.append({
                "name": cli_name,
                "display_name": display_name,
                "status": "failed",
                "message": "CLI not found in registry",
            })
            continue

        success, msg = install_cli(cli_name)
        results.append({
            "name": cli_name,
            "display_name": display_name,
            "status": "installed" if success else "failed",
            "message": msg,
        })
        if success:
            installed.add(cli_name)

    summary = {
        "total": len(results),
        "installed": sum(1 for result in results if result["status"] == "installed"),
        "skipped": sum(1 for result in results if result["status"] == "skipped"),
        "failed": sum(1 for result in results if result["status"] == "failed"),
    }
    installed_state = get_installed()
    rendered_skill_path = render_matrix_skill_file(matrix_item, installed=installed_state)
    payload = {
        "matrix": matrix_item,
        "results": results,
        "summary": summary,
        "rendered_skill_path": str(rendered_skill_path),
    }
    return summary["failed"] == 0, payload
