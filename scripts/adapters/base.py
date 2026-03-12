"""Abstract base class for agent platform adapters."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class Adapter(ABC):
    """Base class for all agent platform adapters.

    To add a new platform, create a .py file in this directory with a class
    that inherits from Adapter and implements the required methods.  The
    adapter is discovered automatically — no editing of other files needed.
    """

    name: str  # e.g. "claude", "codex"

    @abstractmethod
    def source(self, repo_root: Path) -> Path:
        """Path to the adapter source files inside the repository."""

    @abstractmethod
    def destination(self) -> Path:
        """Path where the adapter should be installed for the user."""

    @abstractmethod
    def install(self, repo_root: Path) -> str:
        """Install the adapter.  Return a status message."""

    @abstractmethod
    def status(self) -> str:
        """Return a one-line status string."""

    def detect(self) -> bool:
        """Return True if this agent appears to be available locally."""
        return True  # default: always eligible

    # -- shared helpers available to all adapters --

    @staticmethod
    def _copy_dir(src: Path, dst: Path) -> bool:
        """Copy a directory tree.  Returns False if dst already exists."""
        if dst.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
        return True

    @staticmethod
    def _copy_file(src: Path, dst: Path) -> bool:
        """Copy a single file.  Returns False if dst already exists."""
        if dst.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
