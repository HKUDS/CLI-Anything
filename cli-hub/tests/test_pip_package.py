"""Pip distribution names may differ from registry identifiers."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from cli_hub.installer import uninstall_cli


def test_cc_switch_uninstall_uses_its_registered_distribution(tmp_path):
    registry = Path(__file__).resolve().parents[2] / "registry.json"
    entries = json.loads(registry.read_text(encoding="utf-8"))["clis"]
    cli = next(entry for entry in entries if entry["name"] == "cc-switch")
    state = tmp_path / "installed.json"
    state.write_text(json.dumps({"cc-switch": {"version": "1.0.0"}}))

    with patch("cli_hub.installer.get_cli", return_value=cli), \
            patch("cli_hub.installer.INSTALLED_FILE", state), \
            patch("cli_hub.installer.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        success, _ = uninstall_cli("cc-switch")

    assert success
    run.assert_called_once_with(
        [sys.executable, "-m", "pip", "uninstall", "-y", "cli-anything-ccswitch"],
        capture_output=True, text=True,
    )
    assert json.loads(state.read_text()) == {}


def test_default_distribution_name_still_works(tmp_path):
    cli = {"name": "gimp", "display_name": "GIMP"}
    with patch("cli_hub.installer.get_cli", return_value=cli), \
            patch("cli_hub.installer.INSTALLED_FILE", tmp_path / "installed.json"), \
            patch("cli_hub.installer.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        success, _ = uninstall_cli("gimp")

    assert success
    assert run.call_args.args[0][-1] == "cli-anything-gimp"


def test_failed_distribution_uninstall_preserves_tracking(tmp_path):
    cli = {"name": "custom", "display_name": "Custom", "pip_package": "custom-dist"}
    state = tmp_path / "installed.json"
    original = json.dumps({"custom": {"version": "1.0.0"}})
    state.write_text(original)
    with patch("cli_hub.installer.get_cli", return_value=cli), \
            patch("cli_hub.installer.INSTALLED_FILE", state), \
            patch("cli_hub.installer.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 1, "", "permission denied")
        success, message = uninstall_cli("custom")

    assert not success
    assert "permission denied" in message
    assert run.call_args.args[0][-1] == "custom-dist"
    assert state.read_text() == original
