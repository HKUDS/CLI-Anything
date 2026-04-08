"""PM2 Backend — subprocess wrapper for all PM2 CLI commands.

All PM2 interactions go through this module. It finds the pm2 binary,
runs commands via subprocess.run(), and returns structured results.
"""

import json
import os
import shutil
import subprocess
from typing import Any

# Common directories where pm2 may be installed (Homebrew, global npm, system).
_EXTRA_PATH_DIRS = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]


def _augmented_path(base_path: str | None = None) -> str:
    """Return PATH string with _EXTRA_PATH_DIRS prepended if missing."""
    path = base_path if base_path is not None else os.environ.get("PATH", "")
    for p in _EXTRA_PATH_DIRS:
        if p not in path:
            path = f"{p}:{path}"
    return path


def _find_pm2() -> str:
    """Locate the pm2 binary on the system.

    Checks common Homebrew and global npm paths in addition to PATH.

    Returns:
        Absolute path to the pm2 binary.

    Raises:
        RuntimeError: If pm2 is not found.
    """
    pm2_path = shutil.which("pm2", path=_augmented_path())
    if pm2_path is None:
        raise RuntimeError(
            "pm2 not found on this system. "
            "Install it with: npm install -g pm2"
        )
    return pm2_path


# Cache the pm2 path at module level
_PM2_BIN: str | None = None


def _get_pm2() -> str:
    """Get cached pm2 binary path."""
    global _PM2_BIN
    if _PM2_BIN is None:
        _PM2_BIN = _find_pm2()
    return _PM2_BIN


def _build_env() -> dict[str, str]:
    """Build environment dict with proper PATH for subprocess."""
    env = os.environ.copy()
    env["PATH"] = _augmented_path(env.get("PATH", ""))
    return env


def run_pm2(
    *args: str,
    capture_json: bool = False,
    timeout: int = 30,
) -> dict[str, Any]:
    """Run a pm2 command and return the result.

    Args:
        *args: Arguments to pass to pm2 (e.g., "jlist", "restart", "myapp").
        capture_json: If True, attempt to parse stdout as JSON.
        timeout: Command timeout in seconds.

    Returns:
        Dict with keys:
            - success (bool): Whether command exited with code 0.
            - returncode (int): Process return code.
            - stdout (str): Raw stdout.
            - stderr (str): Raw stderr.
            - data (Any): Parsed JSON data if capture_json=True, else None.
    """
    pm2 = _get_pm2()
    cmd = [pm2, *args]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s: {' '.join(cmd)}",
            "data": None,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"pm2 binary not found at: {pm2}",
            "data": None,
        }

    parsed_data = None
    if capture_json and result.returncode == 0:
        try:
            parsed_data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            # stdout may contain non-JSON preamble; try to extract JSON array
            stdout = result.stdout.strip()
            # Look for JSON array or object
            for start_char, end_char in [("[", "]"), ("{", "}")]:
                idx_start = stdout.find(start_char)
                idx_end = stdout.rfind(end_char)
                if idx_start != -1 and idx_end > idx_start:
                    try:
                        parsed_data = json.loads(stdout[idx_start:idx_end + 1])
                        break
                    except (json.JSONDecodeError, ValueError):
                        continue

    return {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "data": parsed_data,
    }


def pm2_jlist() -> list[dict[str, Any]]:
    """Get JSON list of all PM2 processes.

    Returns:
        List of process info dicts, or empty list on failure.
    """
    result = run_pm2("jlist", capture_json=True)
    if result["success"] and isinstance(result["data"], list):
        return result["data"]
    return []


def pm2_describe(name: str) -> dict[str, Any] | None:
    """Get detailed info for a specific process.

    Uses pm2 jlist and filters by name/id, since pm2 describe
    does not produce JSON output.

    Args:
        name: Process name or ID.

    Returns:
        Process description dict, or None on failure.
    """
    processes = pm2_jlist()
    for p in processes:
        if p.get("name") == name or str(p.get("pm_id")) == str(name):
            return p
    return None


def pm2_action(action: str, name: str) -> dict[str, Any]:
    """Run a lifecycle action (restart, stop, delete) on a process.

    Args:
        action: One of "restart", "stop", "delete".
        name: Process name or ID.

    Returns:
        Result dict from run_pm2.
    """
    return run_pm2(action, str(name))


def pm2_start(script: str, name: str | None = None) -> dict[str, Any]:
    """Start a new PM2 process.

    Args:
        script: Path to script or ecosystem file.
        name: Optional process name.

    Returns:
        Result dict from run_pm2.
    """
    args = ["start", script]
    if name:
        args.extend(["--name", name])
    return run_pm2(*args)


def pm2_logs(name: str, lines: int = 20) -> dict[str, Any]:
    """Get recent logs for a process.

    Args:
        name: Process name or ID.
        lines: Number of log lines to retrieve.

    Returns:
        Result dict from run_pm2.
    """
    return run_pm2("logs", str(name), "--lines", str(lines), "--nostream")


def pm2_flush(name: str | None = None) -> dict[str, Any]:
    """Flush logs for a process or all processes.

    Args:
        name: Process name or ID. If None, flushes all.

    Returns:
        Result dict from run_pm2.
    """
    args = ["flush"]
    if name:
        args.append(str(name))
    return run_pm2(*args)


def pm2_save() -> dict[str, Any]:
    """Save the current PM2 process list."""
    return run_pm2("save")


def pm2_startup() -> dict[str, Any]:
    """Generate PM2 startup script."""
    return run_pm2("startup")


def pm2_version() -> str:
    """Get PM2 version string."""
    result = run_pm2("--version")
    if result["success"]:
        return result["stdout"].strip()
    return "unknown"
