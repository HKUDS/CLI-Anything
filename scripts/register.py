#!/usr/bin/env python3
"""Unified CLI-Anything registration across all agent platforms.

Usage:
    scripts/register.py bootstrap [TARGET]   # first install — one agent
    scripts/register.py install [--targets claude,opencode,codex|all]
    scripts/register.py status  [--targets claude,opencode,codex|all]
    scripts/register.py list

Drop a new .py file in scripts/adapters/ to add a platform — no other
files need to change.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the scripts directory is importable so `adapters` resolves.
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from adapters import get_adapters  # noqa: E402

# Agent-specific hints shown after bootstrap.
_NEXT_STEPS = {
    "claude": "Open Claude Code in this repo and type:  /register",
    "opencode": "Open OpenCode in this repo and type:  /cli-anything-register",
    "codex": "Open Codex CLI in this repo and use the cli-anything skill",
}


def resolve_targets(raw: str) -> list[str]:
    registry = get_adapters()
    if raw == "all":
        return list(registry.keys())
    names = [t.strip() for t in raw.split(",")]
    for n in names:
        if n not in registry:
            sys.exit(f"error: unknown target '{n}'. Known: {', '.join(registry)}")
    return names


def cmd_bootstrap(target: str | None) -> None:
    """First-time setup: install to one agent, then let it manage the rest."""
    registry = get_adapters()

    if target:
        if target not in registry:
            sys.exit(f"error: unknown target '{target}'. Known: {', '.join(registry)}")
        name = target
    else:
        # Auto-detect: pick the first agent that is found locally.
        detected = [n for n, cls in registry.items() if cls().detect()]
        if not detected:
            sys.exit(
                "No agents detected. Install Claude Code, OpenCode, or Codex first,\n"
                "then re-run this command."
            )
        name = detected[0]
        print(f"Auto-detected: {name}")

    adapter = registry[name]()
    print(adapter.install(REPO_ROOT))

    hint = _NEXT_STEPS.get(name, f"Use {name} in this repo to manage other adapters.")
    remaining = [n for n in registry if n != name]
    print()
    print("Bootstrap complete!")
    if remaining:
        print(f"To register the remaining agents ({', '.join(remaining)}):")
        print(f"  {hint}")


def cmd_install(targets: list[str]) -> None:
    registry = get_adapters()
    print("Installing CLI-Anything adapters...")
    for name in targets:
        adapter = registry[name]()
        print(adapter.install(REPO_ROOT))
    print(f"Done. Run '{sys.argv[0]} status' to verify.")


def cmd_status(targets: list[str]) -> None:
    registry = get_adapters()
    for name in targets:
        adapter = registry[name]()
        print(adapter.status())


def cmd_list() -> None:
    registry = get_adapters()
    print("Available adapters:")
    for name, cls in registry.items():
        adapter = cls()
        detected = "detected" if adapter.detect() else "not found"
        print(f"  {name:<12} {detected}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified CLI-Anything registration across agent platforms.",
    )
    sub = parser.add_subparsers(dest="command")

    p_boot = sub.add_parser("bootstrap", help="First-time setup — install to one agent")
    p_boot.add_argument("target", nargs="?", help="Agent to bootstrap (auto-detects if omitted)")

    p_install = sub.add_parser("install", help="Install adapters")
    p_install.add_argument("--targets", default="all", help="Comma-separated targets or 'all'")

    p_status = sub.add_parser("status", help="Show installation status")
    p_status.add_argument("--targets", default="all", help="Comma-separated targets or 'all'")

    sub.add_parser("list", help="List available adapters and detection status")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "bootstrap":
        cmd_bootstrap(args.target)
    elif args.command == "list":
        cmd_list()
    else:
        targets = resolve_targets(args.targets)
        if args.command == "install":
            cmd_install(targets)
        elif args.command == "status":
            cmd_status(targets)


if __name__ == "__main__":
    main()
