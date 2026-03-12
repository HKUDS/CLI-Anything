"""OpenCode adapter — copies command files + HARNESS.md to commands dir."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .base import Adapter

# Files that come from opencode-commands/
_COMMAND_FILES = [
    "cli-anything.md",
    "cli-anything-refine.md",
    "cli-anything-test.md",
    "cli-anything-validate.md",
    "cli-anything-list.md",
    "cli-anything-register.md",
]


class OpenCodeAdapter(Adapter):
    name = "opencode"

    def source(self, repo_root: Path) -> Path:
        return repo_root / "opencode-commands"

    def destination(self) -> Path:
        base = os.environ.get("OPENCODE_HOME", str(Path.home() / ".config" / "opencode"))
        return Path(base) / "commands"

    def detect(self) -> bool:
        return (
            shutil.which("opencode") is not None
            or (Path.home() / ".config" / "opencode").is_dir()
        )

    def _all_files(self, repo_root: Path) -> list[tuple[Path, str]]:
        """Return (source_path, filename) pairs for all files to install."""
        src_dir = self.source(repo_root)
        harness = repo_root / "cli-anything-plugin" / "HARNESS.md"
        pairs = [(src_dir / f, f) for f in _COMMAND_FILES]
        pairs.append((harness, "HARNESS.md"))
        return pairs

    def install(self, repo_root: Path) -> str:
        dst_dir = self.destination()
        dst_dir.mkdir(parents=True, exist_ok=True)
        installed, skipped = 0, 0
        for src, fname in self._all_files(repo_root):
            if not src.is_file():
                return f"  error  opencode  source missing: {src}"
            if self._copy_file(src, dst_dir / fname):
                installed += 1
            else:
                skipped += 1
        if installed == 0:
            return f"  skip     opencode (all {skipped} files exist)"
        return f"  installed opencode -> {dst_dir} ({installed} new, {skipped} existing)"

    def status(self) -> str:
        dst_dir = self.destination()
        total = len(_COMMAND_FILES) + 1  # +1 for HARNESS.md
        present = sum(1 for f in _COMMAND_FILES if (dst_dir / f).exists())
        if (dst_dir / "HARNESS.md").exists():
            present += 1
        return f"  opencode {present}/{total} files   {dst_dir}"
