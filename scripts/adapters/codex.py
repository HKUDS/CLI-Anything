"""Codex adapter — copies codex-skill/ to the Codex skills directory."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .base import Adapter


class CodexAdapter(Adapter):
    name = "codex"

    def source(self, repo_root: Path) -> Path:
        return repo_root / "codex-skill"

    def destination(self) -> Path:
        base = os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
        return Path(base) / "skills" / "cli-anything"

    def detect(self) -> bool:
        return (
            shutil.which("codex") is not None
            or (Path.home() / ".codex").is_dir()
            or "CODEX_HOME" in os.environ
        )

    def install(self, repo_root: Path) -> str:
        src, dst = self.source(repo_root), self.destination()
        if not src.is_dir():
            return f"  error  codex    source missing: {src}"
        if self._copy_dir(src, dst):
            return f"  installed codex    -> {dst}"
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return f"  updated  codex    -> {dst}"

    def status(self) -> str:
        dst = self.destination()
        state = "installed" if dst.is_dir() else "missing"
        return f"  codex    {state:<10} {dst}"
