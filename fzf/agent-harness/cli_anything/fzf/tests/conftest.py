"""Shared fixtures for the fzf harness release suite."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest


PINNED_BACKEND = Path("/var/home/louranicas/.local/bin/fzf")


@pytest.fixture(scope="session")
def backend() -> Path:
    value = os.environ.get("CLI_ANYTHING_FZF_BACKEND")
    path = Path(value).expanduser() if value else PINNED_BACKEND
    if not path.is_file() or not os.access(path, os.X_OK):
        pytest.fail(f"required real fzf backend is unavailable: {path}")
    return path.absolute()


@pytest.fixture(scope="session")
def installed_cli() -> Path:
    sibling = Path(sys.executable).with_name("cli-anything-fzf")
    value = str(sibling) if sibling.is_file() else shutil.which("cli-anything-fzf")
    if not value or not os.access(value, os.X_OK):
        pytest.fail("installed cli-anything-fzf console entry point is unavailable")
    return Path(value).absolute()
