"""Claude Code adapter — copies cli-anything-plugin/ to ~/.claude/plugins/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import Adapter


class ClaudeAdapter(Adapter):
    name = "claude"

    @staticmethod
    def _registry_cache_paths() -> list[Path]:
        """Return active Claude cache install paths for cli-anything, if any."""
        registry = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
        if not registry.is_file():
            return []

        try:
            data = json.loads(registry.read_text())
            entries = data.get("plugins", {}).get("cli-anything@cli-anything", [])
            paths = [Path(e["installPath"]) for e in entries if isinstance(e, dict) and e.get("installPath")]
            return paths
        except Exception:
            return []

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

        # Always sync the direct plugin path.
        direct_state = "installed" if self._copy_dir(src, dst) else "updated"
        if direct_state == "updated":
            shutil.copytree(src, dst, dirs_exist_ok=True)

        # Also sync active cache installs from Claude's plugin registry.
        synced_cache = 0
        for cache_path in self._registry_cache_paths():
            if cache_path == dst:
                continue
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, cache_path, dirs_exist_ok=True)
            synced_cache += 1

        if synced_cache:
            return f"  {direct_state:<8} claude   -> {dst} (and synced {synced_cache} cache install)"
        return f"  {direct_state:<8} claude   -> {dst}"

    def status(self) -> str:
        dst = self.destination()
        state = "installed" if dst.is_dir() else "missing"
        return f"  claude   {state:<10} {dst}"
