"""Unit tests for the Notepad GUI harness.

No live Notepad required: the transport (utils/uia_runner.py) is exercised as
a subprocess against its own guard logic, and the CLI surface is checked via
Click's test runner.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from cli_anything.notepad.core import backend
from cli_anything.notepad.notepad_cli import main

RUNNER = Path(__file__).parent.parent / "utils" / "uia_runner.py"


def test_backend_constants():
    assert backend.TARGET_WINDOW_PROCESS == "Notepad"
    assert backend.TARGET_WINDOW_TITLE == ""  # match any window by class


def test_ui_command_surface():
    names = {c.name for c in main.commands.values()}
    assert {"ui-tree", "ui-menus", "ui-invoke", "ui-select", "ui-set-text"} <= names


def test_ui_runner_compiles():
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(RUNNER)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr


def test_ui_runner_refuses_without_yes():
    """The transport itself must gate driving, not just the CLI."""
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "invoke", "Notepad > File", "--process", "Notepad"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert "--yes" in proc.stdout


def test_ui_runner_refuses_destructive_even_with_yes():
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "invoke",
            "Notepad > File > Save",
            "--process",
            "Notepad",
            "--yes",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert "destructive" in proc.stdout


def test_ui_runner_allows_destructive_with_flag():
    """With --allow-destructive the refusal lifts (then fails on no window)."""
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "invoke",
            "Notepad > File > Save",
            "--process",
            "NoSuchWindow",
            "--yes",
            "--allow-destructive",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # got past the destructive gate; fails later because the window is absent
    assert "destructive" not in proc.stdout


def test_cli_invoke_requires_yes():
    from click.testing import CliRunner

    res = CliRunner().invoke(main, ["ui-invoke", "Notepad > File"])
    assert res.exit_code == 2
    assert "--yes" in res.output


def test_cli_tree_is_read_only():
    """ui-tree needs no confirmation and no window (fails cleanly if absent)."""
    from click.testing import CliRunner

    res = CliRunner().invoke(main, ["ui-tree"])
    assert res.exit_code in (0, 2)
