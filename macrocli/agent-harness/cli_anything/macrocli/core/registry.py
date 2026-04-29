"""MacroRegistry — discovers and loads macro definitions from a directory.

The registry scans a macros/ directory (and subdirectories) for *.yaml files,
optionally guided by a manifest.yaml index.

Usage:
    from cli_anything.macrocli.core.registry import MacroRegistry
    registry = MacroRegistry("/path/to/macros")
    macro = registry.load("export_file")
    all_macros = registry.list_all()
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError as e:
    raise ImportError("PyYAML is required: pip install PyYAML") from e

from cli_anything.macrocli.core.macro_model import MacroDefinition, load_from_yaml


class MacroRegistry:
    """Discovers and caches macro definitions from a macros/ directory."""

    def __init__(self, macros_dir: Optional[str] = None):
        """
        Args:
            macros_dir: Path to the directory containing macro YAML files.
                        Defaults to the macros/ directory bundled with the package.
        """
        if macros_dir is None:
            macros_dir = str(Path(__file__).resolve().parent.parent / "macro_definitions")
        self.macros_dir = Path(macros_dir)
        self._cache: dict[str, MacroDefinition] = {}
        self._scanned = False

    # ── Internal scan ────────────────────────────────────────────────────

    def _scan(self) -> None:
        """Scan macros_dir and populate the cache."""
        if self._scanned:
            return

        if not self.macros_dir.is_dir():
            self._scanned = True
            return

        # Try manifest.yaml first (explicit ordered index)
        manifest_path = self.macros_dir / "manifest.yaml"
        if manifest_path.is_file():
            self._load_from_manifest(manifest_path)
        else:
            # Fallback: scan all *.yaml files recursively (except manifest.yaml)
            for yaml_path in sorted(self.macros_dir.rglob("*.yaml")):
                if yaml_path.name == "manifest.yaml":
                    continue
                self._load_file(yaml_path)

        self._scanned = True

    def _load_from_manifest(self, manifest_path: Path) -> None:
        """Load macros listed in manifest.yaml."""
        with open(manifest_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}

        macros_list = manifest.get("macros", [])
        for entry in macros_list:
            if isinstance(entry, dict):
                rel_path = entry.get("path")
            else:
                rel_path = str(entry)
            if not rel_path:
                continue
            yaml_path = self.macros_dir / rel_path
            if yaml_path.is_file():
                self._load_file(yaml_path)

        # Also scan for any yaml files NOT in the manifest (permissive)
        listed_names = {m.name for m in self._cache.values()}
        for yaml_path in sorted(self.macros_dir.rglob("*.yaml")):
            if yaml_path.name == "manifest.yaml":
                continue
            try:
                # Quick peek to get the name without full parse
                with open(yaml_path, encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                name = raw.get("name", yaml_path.stem)
                if name not in listed_names:
                    self._load_file(yaml_path)
            except Exception:
                pass

    def _load_file(self, yaml_path: Path) -> Optional[MacroDefinition]:
        """Parse one yaml file and cache the result."""
        try:
            macro = load_from_yaml(str(yaml_path))
            self._cache[macro.name] = macro
            return macro
        except Exception as exc:
            # Log but don't crash — bad macros should not block the registry
            import sys
            print(f"[registry] Warning: failed to load {yaml_path}: {exc}", file=sys.stderr)
            return None

    # ── Public API ───────────────────────────────────────────────────────

    def load(self, name: str) -> MacroDefinition:
        """Load a macro by name.

        Raises:
            KeyError: if the macro is not found.
        """
        self._scan()
        if name not in self._cache:
            available = sorted(self._cache.keys())
            raise KeyError(
                f"Macro '{name}' not found. Available: {available}"
            )
        return self._cache[name]

    def list_all(self) -> list[MacroDefinition]:
        """Return all loaded macro definitions, sorted by name."""
        self._scan()
        return sorted(self._cache.values(), key=lambda m: m.name)

    def list_names(self) -> list[str]:
        """Return all macro names, sorted."""
        self._scan()
        return sorted(self._cache.keys())

    def reload(self, name: Optional[str] = None) -> None:
        """Force reload from disk.

        Args:
            name: If given, reload just that macro file.
                  If None, rescan the entire directory.
        """
        if name is None:
            self._cache.clear()
            self._scanned = False
            self._scan()
        elif name in self._cache:
            path = self._cache[name].source_path
            if path and Path(path).is_file():
                self._load_file(Path(path))

    def register(self, macro: MacroDefinition) -> None:
        """Programmatically register a macro (e.g. from tests)."""
        self._cache[macro.name] = macro
        self._scanned = True  # Don't re-scan over in-memory registrations

    def info(self) -> dict:
        """Return registry metadata."""
        self._scan()
        return {
            "macros_dir": str(self.macros_dir),
            "total": len(self._cache),
            "names": self.list_names(),
        }
