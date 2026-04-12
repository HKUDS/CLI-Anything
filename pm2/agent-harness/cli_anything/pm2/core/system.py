"""System commands — save, startup, version for PM2."""

from typing import Any

from ..utils.pm2_backend import pm2_save as backend_save
from ..utils.pm2_backend import pm2_startup as backend_startup
from ..utils.pm2_backend import pm2_version as backend_version


def save(as_json: bool = False) -> dict[str, Any]:
    """Save the current PM2 process list.

    Args:
        as_json: If True, return structured dict.

    Returns:
        Dict with success status and message.
    """
    result = backend_save()

    if as_json:
        return {
            "action": "save",
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

    return {
        "success": result["success"],
        "message": "PM2 process list saved" if result["success"]
                   else f"Failed to save: {result['stderr'].strip()}",
    }


def startup(as_json: bool = False) -> dict[str, Any]:
    """Generate PM2 startup script.

    Args:
        as_json: If True, return structured dict.

    Returns:
        Dict with success status, message, and any instructions.
    """
    result = backend_startup()

    if as_json:
        return {
            "action": "startup",
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

    output = result["stdout"].strip()
    return {
        "success": result["success"],
        "message": "Startup script generated" if result["success"]
                   else f"Startup command output:\n{output}",
        "instructions": output,
    }


def version(as_json: bool = False) -> dict[str, Any] | str:
    """Get PM2 version.

    Args:
        as_json: If True, return structured dict.

    Returns:
        Version string or dict.
    """
    ver = backend_version()

    if as_json:
        return {
            "version": ver,
        }

    return ver
