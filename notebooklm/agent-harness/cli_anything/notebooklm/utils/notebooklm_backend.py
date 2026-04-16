"""NotebookLM backend adapter.

This module wraps an installed `notebooklm` CLI for use inside a CLI-Anything
harness. It does not implement a Google official API client.

References:
- CLI-Anything methodology: https://github.com/HKUDS/CLI-Anything
- notebooklm-py project: https://github.com/teng-lin/notebooklm-py

Security rules:
- never print credential files or cookies
- never commit auth state into the repository
- prefer explicit notebook IDs
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess


JSON_SUPPORTED_COMMANDS = {
    ("auth", "check"),
    ("status",),
    ("list",),
    ("create",),
    ("source", "list"),
    ("source", "add"),
    ("ask",),
    ("history",),
    ("artifact", "list"),
    ("generate", "report"),
    ("download", "report"),
    ("share", "status"),
}
TWO_PART_COMMAND_GROUPS = {"auth", "source", "artifact", "generate", "download", "share"}


def require_notebooklm() -> str:
    """Resolve the notebooklm command from PATH."""
    path = shutil.which("notebooklm")
    if path:
        return path
    raise RuntimeError(
        "notebooklm command not found. Install it with:\n"
        "  python3 -m pip install --user 'notebooklm-py[browser]'\n"
        "  python3 -m playwright install chromium"
    )


def command_supports_json(args: list[str]) -> bool:
    """Return whether the wrapped notebooklm command supports --json."""
    if not args:
        return False
    if len(args) > 1 and args[0] in TWO_PART_COMMAND_GROUPS:
        key = tuple(args[:2])
    else:
        key = tuple(args[:1])
    return key in JSON_SUPPORTED_COMMANDS


def build_command(
    args: list[str],
    *,
    notebook_id: str | None = None,
    json_output: bool = False,
) -> list[str]:
    """Build a notebooklm command with explicit notebook context."""
    command = ["notebooklm", *args]
    if notebook_id:
        command.extend(["-n", notebook_id])
    if json_output and command_supports_json(args):
        command.append("--json")
    return command


def sanitize_error(text: str) -> str:
    """Redact local auth file paths from stderr/stdout."""
    patterns = [
        r"/Users/[^/\s]+/\.notebooklm/storage_state\.json",
        r"/home/[^/\s]+/\.notebooklm/storage_state\.json",
        r"[A-Za-z]:\\\\Users\\\\[^\\\s]+\\\\\.notebooklm\\\\storage_state\.json",
    ]
    sanitized = text
    for pattern in patterns:
        sanitized = re.sub(pattern, "[redacted-auth-path]", sanitized)
    sanitized = sanitized.replace("storage_state.json", "[redacted-auth-path]")
    return sanitized


def run_notebooklm(
    args: list[str],
    *,
    notebook_id: str | None = None,
    json_output: bool = False,
) -> dict | str:
    """Run notebooklm and optionally parse JSON output."""
    if json_output and not command_supports_json(args):
        raise RuntimeError(
            f"JSON output is not supported for command: {' '.join(args)}"
        )

    command = build_command(
        args,
        notebook_id=notebook_id,
        json_output=json_output,
    )
    command[0] = require_notebooklm()

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(sanitize_error(result.stderr or result.stdout))

    if json_output:
        return json.loads(result.stdout or "{}")
    return result.stdout.strip()
