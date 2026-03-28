"""Subprocess backend for eth2-quickstart."""

from __future__ import annotations

import subprocess
from pathlib import Path

from cli_anything.eth2_quickstart.core.project import find_repo_root, wrapper_path


class Eth2QuickStartBackend:
    def __init__(self, repo_root: str | None = None):
        self.repo_root = find_repo_root(repo_root)

    def _run(self, command: list[str]) -> dict:
        completed = subprocess.run(
            command,
            cwd=str(self.repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
        return {
            "command": command,
            "cwd": str(self.repo_root),
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "ok": completed.returncode == 0,
        }

    def run_wrapper(self, *args: str) -> dict:
        return self._run([str(wrapper_path(self.repo_root)), *args])

    def run_script(self, relative_path: str, *args: str) -> dict:
        script_path = self.repo_root / Path(relative_path)
        return self._run([str(script_path), *args])

