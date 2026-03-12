#!/usr/bin/env python3
"""Unified CLI-Anything registration across all agent platforms.

Usage:
    scripts/register.py bootstrap [--target auto|claude|opencode|codex] [--dry-run] [--debug]
    scripts/register.py install [--targets claude,opencode,codex|all]
    scripts/register.py install-all [--debug]
    scripts/register.py status  [--targets claude,opencode,codex|all]
    scripts/register.py list [--debug]

Drop a new .py file in scripts/adapters/ to add a platform - no other
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
    "claude": "Open Claude Code in this repo and type:  /cli-anything:register",
    "opencode": "Open OpenCode in this repo and type:  /register",
    "codex": "Open Codex CLI in this repo and use the cli-anything skill",
}

_AUTO_PRIORITY = ["claude", "opencode", "codex"]


def _debug(enabled: bool, msg: str) -> None:
    if enabled:
        print(f"[debug] {msg}")


def _known_targets(registry: dict[str, type]) -> str:
    return ", ".join(sorted(registry.keys()))


def _all_targets(registry: dict[str, type]) -> list[str]:
    return sorted(registry.keys())


def _pick_auto_target(registry: dict[str, type], debug: bool) -> str:
    ordered = [name for name in _AUTO_PRIORITY if name in registry]
    ordered.extend([n for n in _all_targets(registry) if n not in ordered])

    _debug(debug, f"auto target order: {ordered}")

    for name in ordered:
        detected = registry[name]().detect()
        _debug(debug, f"detect({name})={detected}")
        if detected:
            return name

    sys.exit(
        "No agents detected. Install Claude Code, OpenCode, or Codex first,\n"
        "then re-run this command or specify --target manually."
    )


def resolve_targets(raw: str) -> list[str]:
    registry = get_adapters()
    if raw == "all":
        return _all_targets(registry)

    names = [t.strip() for t in raw.split(",") if t.strip()]
    if not names:
        sys.exit(f"error: empty targets. Known: {_known_targets(registry)}")

    for n in names:
        if n not in registry:
            sys.exit(f"error: unknown target '{n}'. Known: {_known_targets(registry)}")
    return names


def cmd_bootstrap(target: str, dry_run: bool, debug: bool) -> None:
    """First-time setup: install to one agent, then let it manage the rest."""
    registry = get_adapters()
    _debug(debug, f"available targets: {_known_targets(registry)}")

    if target == "auto":
        name = _pick_auto_target(registry, debug)
        print(f"Selected target (auto): {name}")
    else:
        if target not in registry:
            sys.exit(f"error: unknown target '{target}'. Known: {_known_targets(registry)}")
        name = target
        print(f"Selected target: {name}")

    adapter = registry[name]()
    src = adapter.source(REPO_ROOT)
    dst = adapter.destination()
    print(f"Planned source: {src}")
    print(f"Planned destination: {dst}")

    if dry_run:
        print("Dry-run only. No files were changed.")
        return

    _debug(debug, "starting install")
    print(adapter.install(REPO_ROOT))

    hint = _NEXT_STEPS.get(name, f"Use {name} in this repo to manage other adapters.")
    remaining = [n for n in _all_targets(registry) if n != name]
    print()
    print("Bootstrap complete!")
    if remaining:
        print(f"To register the remaining agents ({', '.join(remaining)}):")
        print(f"  {hint}")
    print("Lazy mode (install all now):")
    print(f"  {sys.argv[0]} install-all")


def cmd_install(targets: list[str], debug: bool) -> None:
    registry = get_adapters()
    print("Installing CLI-Anything adapters...")
    _debug(debug, f"install targets: {targets}")
    for name in targets:
        adapter = registry[name]()
        _debug(debug, f"installing {name}: src={adapter.source(REPO_ROOT)} dst={adapter.destination()}")
        print(adapter.install(REPO_ROOT))
    print(f"Done. Run '{sys.argv[0]} status' to verify.")


def cmd_install_all(debug: bool) -> None:
    registry = get_adapters()
    cmd_install(_all_targets(registry), debug)


def cmd_status(targets: list[str], debug: bool) -> None:
    registry = get_adapters()
    _debug(debug, f"status targets: {targets}")
    for name in targets:
        adapter = registry[name]()
        print(adapter.status())


def cmd_list(debug: bool) -> None:
    registry = get_adapters()
    _debug(debug, f"registered adapters: {_known_targets(registry)}")
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

    p_boot = sub.add_parser("bootstrap", help="First-time setup - install to one agent")
    p_boot.add_argument(
        "--target",
        default="auto",
        help="Bootstrap target: auto, claude, opencode, codex",
    )
    p_boot.add_argument("--dry-run", action="store_true", help="Show selected target and paths only")
    p_boot.add_argument("--debug", action="store_true", help="Print debug details")

    p_install = sub.add_parser("install", help="Install adapters")
    p_install.add_argument("--targets", default="all", help="Comma-separated targets or 'all'")
    p_install.add_argument("--debug", action="store_true", help="Print debug details")

    p_install_all = sub.add_parser("install-all", help="Install all adapters in one command")
    p_install_all.add_argument("--debug", action="store_true", help="Print debug details")

    p_status = sub.add_parser("status", help="Show installation status")
    p_status.add_argument("--targets", default="all", help="Comma-separated targets or 'all'")
    p_status.add_argument("--debug", action="store_true", help="Print debug details")

    p_list = sub.add_parser("list", help="List available adapters and detection status")
    p_list.add_argument("--debug", action="store_true", help="Print debug details")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "bootstrap":
        cmd_bootstrap(args.target, args.dry_run, args.debug)
    elif args.command == "install-all":
        cmd_install_all(args.debug)
    elif args.command == "list":
        cmd_list(args.debug)
    else:
        targets = resolve_targets(args.targets)
        if args.command == "install":
            cmd_install(targets, args.debug)
        elif args.command == "status":
            cmd_status(targets, args.debug)


if __name__ == "__main__":
    main()
