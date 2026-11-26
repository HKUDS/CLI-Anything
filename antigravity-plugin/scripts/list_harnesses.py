#!/usr/bin/env python3
"""Deterministic discovery of installed and generated CLI-Anything harnesses.

Implements the canonical `/cli-anything-list` contract (`commands/list.md`)
using only the Python standard library, with cross-platform UTF-8 output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from importlib.metadata import distributions
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".mypy_cache",
}


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _extract_version(harness_dir: Path) -> str | None:
    for filename in ("setup.py", "pyproject.toml"):
        candidate = harness_dir / filename
        if not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    return None


def scan_installed(*, include_hub: bool = False) -> dict[str, dict[str, object]]:
    installed: dict[str, dict[str, object]] = {}
    for dist in distributions():
        raw_name = (dist.metadata.get("Name") or "").strip()
        norm_name = raw_name.lower().replace("_", "-")
        if not norm_name.startswith("cli-anything-"):
            continue
        if not include_hub and norm_name == "cli-anything-hub":
            continue
        software = norm_name[len("cli-anything-"):]
        exe = shutil.which(norm_name)
        installed[software] = {
            "name": software,
            "status": "installed",
            "version": dist.version,
            "executable": exe,
            "source": None,
        }
    return installed


def scan_generated(base_path: Path, max_depth: int | None = None) -> dict[str, dict[str, object]]:
    """Walk base_path finding <...>/agent-harness/cli_anything/<software>/__init__.py."""
    base = base_path.resolve()
    generated: dict[str, dict[str, object]] = {}

    for root, dirs, _files in os.walk(base, followlinks=False):
        root_path = Path(root)
        try:
            rel_parts = root_path.relative_to(base).parts
        except ValueError:
            rel_parts = ()
        depth = len(rel_parts)

        # Prune irrelevant directories to keep scans fast.
        dirs[:] = [
            d for d in sorted(dirs)
            if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]

        if root_path.name == "agent-harness" and (root_path / "cli_anything").is_dir():
            ns_dir = root_path / "cli_anything"
            for pkg in sorted(ns_dir.iterdir()):
                if pkg.is_dir() and (pkg / "__init__.py").is_file():
                    software = pkg.name.replace("_", "-")
                    try:
                        display_src = str(root_path.relative_to(base)).replace("\\", "/")
                        if not display_src.startswith("."):
                            display_src = "./" + display_src
                    except ValueError:
                        display_src = str(root_path)
                    generated[software] = {
                        "name": software,
                        "status": "generated",
                        "version": _extract_version(root_path),
                        "executable": None,
                        "source": display_src,
                    }
            # No need to descend further into an already-matched agent-harness.
            dirs[:] = []
            continue

        if max_depth is not None and depth >= max_depth:
            # Allow checking an immediate `agent-harness` child at max_depth.
            dirs[:] = [d for d in dirs if d == "agent-harness"]

    return generated


def collect_tools(
    base_path: Path,
    *,
    max_depth: int | None = None,
    include_hub: bool = False,
) -> dict[str, object]:
    installed = scan_installed(include_hub=include_hub)
    generated = scan_generated(base_path, max_depth=max_depth)

    merged: dict[str, dict[str, object]] = {}
    for name in sorted(set(installed) | set(generated)):
        if name in installed:
            entry = dict(installed[name])
            if name in generated:
                entry["source"] = generated[name]["source"]
            merged[name] = entry
        else:
            merged[name] = dict(generated[name])

    tools = list(merged.values())
    installed_count = sum(1 for t in tools if t["status"] == "installed")
    generated_only = sum(1 for t in tools if t["status"] == "generated")
    return {
        "tools": tools,
        "total": len(tools),
        "installed": installed_count,
        "generated_only": generated_only,
    }


def _print_table(payload: dict[str, object]) -> None:
    tools: list[dict[str, object]] = payload["tools"]  # type: ignore[assignment]
    if not tools:
        print("No CLI-Anything tools found.")
        return

    print(f"CLI-Anything Tools (found {payload['total']})\n")
    print(f"{'Name':<20} {'Status':<11} {'Version':<10} Source / Executable")
    print("-" * 74)
    for t in tools:
        loc = t.get("source") or t.get("executable") or "-"
        ver = t.get("version") or "-"
        print(f"{str(t['name']):<20} {str(t['status']):<11} {str(ver):<10} {loc}")


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="List installed and locally generated CLI-Anything tools."
    )
    parser.add_argument("--path", default=".", help="Directory to scan for generated harnesses (default: .)")
    parser.add_argument("--depth", type=int, default=None, help="Maximum directory recursion depth")
    parser.add_argument("--json", dest="use_json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--include-hub",
        action="store_true",
        help="Include cli-anything-hub package manager alongside harnesses",
    )
    args = parser.parse_args(argv)

    base = Path(args.path)
    if not base.exists() or not base.is_dir():
        msg = f"Path not found: {args.path}"
        if args.use_json:
            print(json.dumps({"error": msg}))
        else:
            print(f"Error: {msg}", file=sys.stderr)
        return 1

    payload = collect_tools(base, max_depth=args.depth, include_hub=args.include_hub)
    if args.use_json:
        print(json.dumps(payload, indent=2))
    else:
        _print_table(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
