"""Log commands — view and flush PM2 process logs."""

from typing import Any

from ..utils.pm2_backend import pm2_logs as backend_logs, pm2_flush as backend_flush


def view_logs(name: str, lines: int = 20, as_json: bool = False) -> dict[str, Any]:
    """View recent logs for a PM2 process.

    Args:
        name: Process name or ID.
        lines: Number of log lines to retrieve.
        as_json: If True, return structured dict.

    Returns:
        Dict with log content and metadata.
    """
    result = backend_logs(name, lines=lines)

    if as_json:
        return {
            "process": name,
            "lines_requested": lines,
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

    if result["success"]:
        output = result["stdout"].strip() or result["stderr"].strip()
        return {
            "success": True,
            "message": f"Logs for '{name}' (last {lines} lines)",
            "content": output if output else "(no log output)",
        }
    else:
        return {
            "success": False,
            "message": f"Failed to get logs for '{name}': {result['stderr'].strip()}",
            "content": "",
        }


def flush_logs(name: str | None = None, as_json: bool = False) -> dict[str, Any]:
    """Flush logs for a process or all processes.

    Args:
        name: Process name or ID. If None, flushes all logs.
        as_json: If True, return structured dict.

    Returns:
        Dict with success status and message.
    """
    result = backend_flush(name)
    target = f"'{name}'" if name else "all processes"

    if as_json:
        return {
            "action": "flush",
            "process": name or "all",
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

    return {
        "success": result["success"],
        "message": f"Flushed logs for {target}" if result["success"]
                   else f"Failed to flush logs for {target}: {result['stderr'].strip()}",
    }
