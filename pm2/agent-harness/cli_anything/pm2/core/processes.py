"""Process commands — list, describe, and metrics for PM2 processes."""

import json
from typing import Any

from ..utils.pm2_backend import pm2_jlist, pm2_describe


def list_processes(as_json: bool = False) -> str | list[dict[str, Any]]:
    """List all PM2 processes.

    Args:
        as_json: If True, return raw list of dicts. Otherwise, formatted string.

    Returns:
        Formatted table string or list of process dicts.
    """
    processes = pm2_jlist()

    if as_json:
        return processes

    if not processes:
        return "No PM2 processes running."

    rows = []
    for p in processes:
        pm2_env = p.get("pm2_env", {})
        monit = p.get("monit", {})
        rows.append({
            "id": p.get("pm_id", "?"),
            "name": p.get("name", "unknown"),
            "status": pm2_env.get("status", "unknown"),
            "cpu": f"{monit.get('cpu', 0)}%",
            "memory": _format_bytes(monit.get("memory", 0)),
            "restarts": pm2_env.get("restart_time", 0),
            "uptime": _format_uptime(pm2_env.get("pm_uptime", 0)),
        })

    return rows


def describe_process(name: str, as_json: bool = False) -> str | dict[str, Any] | None:
    """Get detailed info for a specific process.

    Args:
        name: Process name or ID.
        as_json: If True, return raw dict.

    Returns:
        Formatted info string, raw dict, or None if not found.
    """
    info = pm2_describe(name)

    if info is None:
        return None

    if as_json:
        return info

    pm2_env = info.get("pm2_env", {})
    monit = info.get("monit", {})

    details = {
        "Name": info.get("name", "unknown"),
        "ID": str(info.get("pm_id", "?")),
        "Status": pm2_env.get("status", "unknown"),
        "Script": pm2_env.get("pm_exec_path", "N/A"),
        "CWD": pm2_env.get("pm_cwd", "N/A"),
        "Interpreter": pm2_env.get("exec_interpreter", "N/A"),
        "CPU": f"{monit.get('cpu', 0)}%",
        "Memory": _format_bytes(monit.get("memory", 0)),
        "Restarts": str(pm2_env.get("restart_time", 0)),
        "Uptime": _format_uptime(pm2_env.get("pm_uptime", 0)),
        "PID": str(info.get("pid", "N/A")),
        "Exec Mode": pm2_env.get("exec_mode", "N/A"),
        "Node Version": pm2_env.get("node_version", "N/A"),
    }

    return details


def get_metrics(as_json: bool = False) -> str | list[dict[str, Any]]:
    """Get CPU/memory metrics for all processes.

    Args:
        as_json: If True, return raw list of metric dicts.

    Returns:
        Formatted metrics string or list of metric dicts.
    """
    processes = pm2_jlist()

    if as_json:
        metrics = []
        for p in processes:
            monit = p.get("monit", {})
            pm2_env = p.get("pm2_env", {})
            metrics.append({
                "name": p.get("name", "unknown"),
                "pm_id": p.get("pm_id", "?"),
                "status": pm2_env.get("status", "unknown"),
                "cpu": monit.get("cpu", 0),
                "memory": monit.get("memory", 0),
                "memory_human": _format_bytes(monit.get("memory", 0)),
            })
        return metrics

    if not processes:
        return "No PM2 processes running."

    rows = []
    for p in processes:
        monit = p.get("monit", {})
        pm2_env = p.get("pm2_env", {})
        rows.append({
            "id": p.get("pm_id", "?"),
            "name": p.get("name", "unknown"),
            "status": pm2_env.get("status", "unknown"),
            "cpu": f"{monit.get('cpu', 0)}%",
            "memory": _format_bytes(monit.get("memory", 0)),
        })

    return rows


def _format_bytes(b: int) -> str:
    """Format bytes into human-readable string."""
    if b == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    val = float(b)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.1f} {units[i]}"


def _format_uptime(pm_uptime: int) -> str:
    """Format PM2 uptime timestamp to human-readable duration."""
    if pm_uptime == 0:
        return "N/A"

    import time
    now_ms = int(time.time() * 1000)
    diff_s = max(0, (now_ms - pm_uptime)) // 1000

    if diff_s < 60:
        return f"{diff_s}s"
    elif diff_s < 3600:
        return f"{diff_s // 60}m {diff_s % 60}s"
    elif diff_s < 86400:
        h = diff_s // 3600
        m = (diff_s % 3600) // 60
        return f"{h}h {m}m"
    else:
        d = diff_s // 86400
        h = (diff_s % 86400) // 3600
        return f"{d}d {h}h"
