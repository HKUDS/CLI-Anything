"""Install, uninstall, and manage CLI-Anything harnesses via pip."""

import json
import subprocess
import sys
from pathlib import Path

from cli_hub.registry import get_cli, fetch_registry

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


def install_cli(name):
    """Install a CLI harness by name. Returns (success, message)."""
    cli = get_cli(name)
    if cli is None:
        return False, f"CLI '{name}' not found in registry. Use 'cli-hub list' to see available CLIs."

    install_cmd = cli["install_cmd"]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install"] + install_cmd.replace("pip install ", "").split(),
        capture_output=True, text=True
    )

    if result.returncode == 0:
        installed = _load_installed()
        installed[cli["name"]] = {
            "version": cli["version"],
            "entry_point": cli["entry_point"],
            "install_cmd": install_cmd,
        }
        _save_installed(installed)
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    else:
        return False, f"pip install failed:\n{result.stderr}"


def uninstall_cli(name):
    """Uninstall a CLI harness by name. Returns (success, message)."""
    cli = get_cli(name)
    if cli is None:
        return False, f"CLI '{name}' not found in registry."

    # The pip package name follows the pattern: cli-anything-<name> with underscores
    # but we derive it from the install_cmd's subdirectory
    # The namespace package is cli_anything.<name>, entry point is cli-anything-<name>
    # pip package name in subdirectory installs is the name from setup.py
    # We'll uninstall by the entry_point pattern
    pkg_name = f"cli-anything-{cli['name']}"

    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", pkg_name],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        installed = _load_installed()
        installed.pop(cli["name"], None)
        _save_installed(installed)
        return True, f"Uninstalled {cli['display_name']}"
    else:
        return False, f"pip uninstall failed:\n{result.stderr}"


def get_installed():
    """Return dict of installed CLIs."""
    return _load_installed()


def update_cli(name):
    """Update a CLI by reinstalling from the latest source."""
    cli = get_cli(name, fetch_registry(force_refresh=True))
    if cli is None:
        return False, f"CLI '{name}' not found in registry."

    install_cmd = cli["install_cmd"]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall"]
        + install_cmd.replace("pip install ", "").split(),
        capture_output=True, text=True
    )

    if result.returncode == 0:
        installed = _load_installed()
        installed[cli["name"]] = {
            "version": cli["version"],
            "entry_point": cli["entry_point"],
            "install_cmd": install_cmd,
        }
        _save_installed(installed)
        return True, f"Updated {cli['display_name']} to {cli['version']}"
    else:
        return False, f"Update failed:\n{result.stderr}"
