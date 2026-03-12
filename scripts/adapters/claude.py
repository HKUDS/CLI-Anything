"""Claude Code adapter — copies cli-anything-plugin/ to ~/.claude/plugins/."""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import Adapter


class ClaudeAdapter(Adapter):
    name = "claude"

    def source(self, repo_root: Path) -> Path:
        return repo_root / "cli-anything-plugin"

    def destination(self) -> Path:
        return Path.home() / ".claude" / "plugins" / "cli-anything"

    def detect(self) -> bool:
        return (
            shutil.which("claude") is not None
            or (Path.home() / ".claude").is_dir()
        )

    def install(self, repo_root: Path) -> str:
        src, dst = self.source(repo_root), self.destination()
        if not src.is_dir():
            return f"  error  claude   source missing: {src}"
        if self._copy_dir(src, dst):
            return f"  installed claude   -> {dst}"
        return f"  skip     claude   (already at {dst})"

    def status(self) -> str:
        dst = self.destination()
        state = "installed" if dst.is_dir() else "missing"
        return f"  claude   {state:<10} {dst}"
