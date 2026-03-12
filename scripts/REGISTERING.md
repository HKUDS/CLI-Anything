# Unified Registration Guide

This document explains how to use and extend the unified registration module.
It intentionally does not modify the main project README.

## User Commands

Run from repository root.

1. First install (recommended):

python3 scripts/register.py bootstrap --target auto

2. First install with explicit target:

python3 scripts/register.py bootstrap --target claude
python3 scripts/register.py bootstrap --target opencode
python3 scripts/register.py bootstrap --target codex

3. Confirm target and paths before changing files:

python3 scripts/register.py bootstrap --target auto --dry-run

4. Install selected targets:

python3 scripts/register.py install --targets claude,opencode

5. Lazy mode (one-click all):

python3 scripts/register.py install-all

6. Check installation status:

python3 scripts/register.py status --targets all

7. See local detection result:

python3 scripts/register.py list

## Debug Mode

Add --debug to bootstrap/install/install-all/status/list.

Example:

python3 scripts/register.py bootstrap --target auto --debug
python3 scripts/register.py install --targets all --debug

Debug output includes:
- detected adapter list
- auto selection order
- source and destination paths
- per-target operation trace

## Two-Phase Workflow

Phase 1: terminal bootstrap to one agent.

Phase 2: use that agent to manage others.
- Claude Code: /register
- OpenCode: /cli-anything-register
- Codex: use cli-anything skill

## Extending to New Platforms

1. Add one Python file under scripts/adapters.
2. Inherit Adapter from scripts/adapters/base.py.
3. Implement:
- name
- source(repo_root)
- destination()
- detect()
- install(repo_root)
- status()
4. Do not edit scripts/register.py for discovery. Adapters are auto-discovered.

Minimal skeleton:

from pathlib import Path
from .base import Adapter

class NewPlatformAdapter(Adapter):
    name = "newplatform"

    def source(self, repo_root: Path) -> Path:
        return repo_root / "newplatform-files"

    def destination(self) -> Path:
        return Path.home() / ".newplatform" / "cli-anything"

    def detect(self) -> bool:
        return self.destination().parent.exists()

    def install(self, repo_root: Path) -> str:
        src, dst = self.source(repo_root), self.destination()
        if not src.exists():
            return f"  error  newplatform source missing: {src}"
        if self._copy_dir(src, dst):
            return f"  installed newplatform -> {dst}"
        return f"  skip     newplatform (already at {dst})"

    def status(self) -> str:
        dst = self.destination()
        state = "installed" if dst.exists() else "missing"
        return f"  newplatform {state:<10} {dst}"

## Safety and Operational Notes

- No shell eval in register.py. Operations use Python filesystem APIs.
- Installs are idempotent by design (existing destination -> skip).
- Each adapter validates source paths before copy.
- Destination is scoped to per-agent config/plugin directories.
- For destructive cleanup tests, users should run explicit rm commands themselves.

## Performance Notes

- Adapter discovery is lightweight (package module scan + class registry).
- Normal operations are O(number_of_targets + copied_files).
- Most operations are local copy operations and complete quickly.

## Troubleshooting Quick Checks

1. python3 scripts/register.py list --debug
2. python3 scripts/register.py status --targets all --debug
3. python3 scripts/register.py bootstrap --target auto --dry-run --debug
4. Verify source directories exist in current branch.
