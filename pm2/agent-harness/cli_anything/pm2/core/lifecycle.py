"""Lifecycle commands — start, stop, restart, delete PM2 processes."""

import json
from typing import Any

from ..utils.pm2_backend import pm2_action, pm2_start as backend_start


def restart_process(name: str, as_json: bool = False) -> dict[str, Any]:
    """Restart a PM2 process.

    Args:
        name: Process name or ID.
        as_json: If True, return raw result dict.

    Returns:
        Result dict with success status and message.
    """
    result = pm2_action("restart", name)
    if as_json:
        return {
            "action": "restart",
            "process": name,
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
    return {
        "success": result["success"],
        "message": f"Restarted '{name}'" if result["success"]
                   else f"Failed to restart '{name}': {result['stderr'].strip()}",
    }


def stop_process(name: str, as_json: bool = False) -> dict[str, Any]:
    """Stop a PM2 process.

    Args:
        name: Process name or ID.
        as_json: If True, return raw result dict.

    Returns:
        Result dict with success status and message.
    """
    result = pm2_action("stop", name)
    if as_json:
        return {
            "action": "stop",
            "process": name,
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
    return {
        "success": result["success"],
        "message": f"Stopped '{name}'" if result["success"]
                   else f"Failed to stop '{name}': {result['stderr'].strip()}",
    }


def delete_process(name: str, as_json: bool = False) -> dict[str, Any]:
    """Delete a PM2 process.

    Args:
        name: Process name or ID.
        as_json: If True, return raw result dict.

    Returns:
        Result dict with success status and message.
    """
    result = pm2_action("delete", name)
    if as_json:
        return {
            "action": "delete",
            "process": name,
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
    return {
        "success": result["success"],
        "message": f"Deleted '{name}'" if result["success"]
                   else f"Failed to delete '{name}': {result['stderr'].strip()}",
    }


def start_process(
    script: str,
    name: str | None = None,
    as_json: bool = False,
) -> dict[str, Any]:
    """Start a new PM2 process.

    Args:
        script: Path to script or ecosystem file.
        name: Optional process name.
        as_json: If True, return raw result dict.

    Returns:
        Result dict with success status and message.
    """
    result = backend_start(script, name=name)
    display_name = name or script

    if as_json:
        return {
            "action": "start",
            "script": script,
            "name": name,
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
    return {
        "success": result["success"],
        "message": f"Started '{display_name}'" if result["success"]
                   else f"Failed to start '{display_name}': {result['stderr'].strip()}",
    }
