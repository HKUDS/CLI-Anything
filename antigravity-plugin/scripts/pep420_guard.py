#!/usr/bin/env python3
"""PreToolUse lifecycle hook guard enforcing the PEP 420 namespace rule.

Blocks accidental creation of `cli_anything/__init__.py` inside a
CLI-Anything harness (which breaks PEP 420 namespace package coexistence
across separately installed `cli-anything-*` packages).

Designed to run under `python -S` with zero third-party imports and fail
open for all unrelated file writes.
"""

import json
import posixpath
import sys


def _extract_target_path(payload: dict) -> str:
    tool_call = payload.get("toolCall") or {}
    args = tool_call.get("args") or {}
    for key in ("Path", "path", "TargetFile", "targetFile", "file_path", "filePath"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _extract_cwd(payload: dict) -> str:
    tool_call = payload.get("toolCall") or {}
    for container in (tool_call, payload):
        for key in ("cwd", "workingDirectory", "working_directory"):
            val = container.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _normalize_guard_path(raw_path: str, cwd: str = "") -> str:
    p = raw_path.strip().replace("\\", "/")
    has_drive = len(p) >= 2 and p[1] == ":" and p[0].isalpha()
    if cwd and not has_drive and not p.startswith("/"):
        p = f"{cwd.strip().replace(chr(92), '/').rstrip('/')}/{p}"
        has_drive = len(p) >= 2 and p[1] == ":" and p[0].isalpha()

    drive = ""
    if has_drive:
        drive = p[:2].lower()
        p = p[2:]
        if not p.startswith("/"):
            p = "/" + p

    if p.startswith("/"):
        p = "/" + p.lstrip("/")

    norm = posixpath.normpath(p).lower()
    if drive:
        return f"{drive}{norm}"
    return norm


def evaluate(payload: dict) -> dict:
    raw_path = _extract_target_path(payload)
    if not raw_path:
        return {"decision": "allow"}

    norm = _normalize_guard_path(raw_path, _extract_cwd(payload))
    if norm.endswith("/cli_anything/__init__.py") or norm == "cli_anything/__init__.py":
        return {
            "decision": "deny",
            "reason": (
                "PEP 420 namespace violation: cli_anything/ MUST NOT contain __init__.py "
                "(see HARNESS.md Phase 7). Place __init__.py only inside cli_anything/<software>/."
            ),
        }
    return {"decision": "allow"}


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        result = evaluate(payload)
    except Exception:
        result = {"decision": "allow"}

    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
