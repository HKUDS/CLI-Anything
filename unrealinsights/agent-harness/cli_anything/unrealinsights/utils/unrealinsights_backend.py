"""
Backend helpers for resolving and invoking Unreal Insights binaries.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
from datetime import datetime
from pathlib import Path
import time
from typing import Iterable

INSIGHTS_BINARY_NAME = "UnrealInsights.exe"
TRACE_SERVER_BINARY_NAME = "UnrealTraceServer.exe"


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def _extract_engine_version_hint(path: Path) -> str | None:
    for parent in path.parents:
        if parent.name.startswith("UE_"):
            return parent.name.removeprefix("UE_")
    return None


def _engine_sort_key(path: Path) -> tuple[int, ...]:
    match = re.findall(r"\d+", path.name)
    if not match:
        return (0,)
    return tuple(int(part) for part in match)


def _default_search_roots() -> list[Path]:
    roots: dict[str, Path] = {}

    for env_key in ("ProgramW6432", "ProgramFiles"):
        value = os.environ.get(env_key)
        if value:
            root = Path(value) / "Epic Games"
            roots[str(root).lower()] = root

    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(f"{drive}:/Program Files/Epic Games")
        roots[str(root).lower()] = root

    return [root for root in roots.values() if root.exists()]


def _existing_engine_installations(search_roots: Iterable[Path] | None = None) -> list[Path]:
    installs: dict[str, Path] = {}
    roots = list(search_roots) if search_roots is not None else _default_search_roots()
    for root in roots:
        if not root.exists():
            continue
        for candidate in root.glob("UE_*"):
            if candidate.is_dir():
                installs[str(candidate.resolve()).lower()] = candidate.resolve()
    return sorted(installs.values(), key=_engine_sort_key, reverse=True)


def _candidate_binary_paths(binary_name: str, search_roots: Iterable[Path] | None = None) -> list[Path]:
    candidates: list[Path] = []
    for install in _existing_engine_installations(search_roots):
        candidates.append(install / "Engine" / "Binaries" / "Win64" / binary_name)
    return candidates


def _read_windows_product_version(path: Path) -> str | None:
    if os.name != "nt":
        return None

    literal = str(path).replace("'", "''")
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"(Get-Item -LiteralPath '{literal}').VersionInfo.ProductVersion",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    version = result.stdout.strip()
    return version or None


def _build_resolution(path: Path, source: str) -> dict[str, object]:
    version = _read_windows_product_version(path)
    return {
        "available": True,
        "path": _normalize_path(path),
        "source": source,
        "version": version or _extract_engine_version_hint(path),
        "engine_version_hint": _extract_engine_version_hint(path),
    }


def _missing_resolution(binary_name: str, reason: str) -> dict[str, object]:
    return {
        "available": False,
        "path": None,
        "source": "unresolved",
        "version": None,
        "engine_version_hint": None,
        "error": f"{binary_name} not found: {reason}",
    }


def resolve_engine_root(engine_root: str | Path) -> Path:
    """Normalize a UE install root from either the install root or Engine subdir."""
    path = Path(engine_root).expanduser().resolve()
    root = path.parent if path.name.lower() == "engine" else path
    if not root.exists():
        raise RuntimeError(f"Engine root not found: {root}")
    if not (root / "Engine").is_dir():
        raise RuntimeError(f"Engine root must contain an Engine directory: {root}")
    return root


def resolve_binary_from_engine_root(
    binary_name: str,
    engine_root: str | Path,
    required: bool = True,
) -> dict[str, object]:
    """Resolve a UE program binary from a specific engine root."""
    root = resolve_engine_root(engine_root)
    candidate = root / "Engine" / "Binaries" / "Win64" / binary_name
    if candidate.is_file():
        return _build_resolution(candidate, f"engine:{root.name}")
    if required:
        raise RuntimeError(f"{binary_name} not found under engine root: {root}")
    return _missing_resolution(binary_name, f"missing under engine root {root}")


def resolve_windows_binary(
    binary_name: str,
    explicit_path: str | None = None,
    env_var_name: str | None = None,
    search_roots: Iterable[Path] | None = None,
    required: bool = True,
) -> dict[str, object]:
    """Resolve a UE program binary using explicit path, env var, then auto-discovery."""
    if explicit_path:
        explicit = Path(explicit_path).expanduser()
        if not explicit.is_file():
            raise RuntimeError(f"Explicit path does not exist: {explicit}")
        return _build_resolution(explicit.resolve(), "explicit")

    if env_var_name:
        env_value = os.environ.get(env_var_name, "").strip()
        if env_value:
            env_path = Path(env_value).expanduser()
            if not env_path.is_file():
                raise RuntimeError(f"{env_var_name} points to a missing file: {env_path}")
            return _build_resolution(env_path.resolve(), f"env:{env_var_name}")

    for candidate in _candidate_binary_paths(binary_name, search_roots):
        if candidate.is_file():
            return _build_resolution(candidate.resolve(), f"auto:{candidate.parents[3].name}")

    if required:
        raise RuntimeError(
            f"{binary_name} not found. Set an explicit path or install UE 5.5+ in an Epic Games directory."
        )
    return _missing_resolution(binary_name, "auto-discovery did not find a matching UE install")


def resolve_unrealinsights_exe(
    explicit_path: str | None = None,
    engine_root: str | None = None,
    search_roots: Iterable[Path] | None = None,
    required: bool = True,
) -> dict[str, object]:
    if engine_root:
        return resolve_binary_from_engine_root(INSIGHTS_BINARY_NAME, engine_root, required=required)
    return resolve_windows_binary(
        INSIGHTS_BINARY_NAME,
        explicit_path=explicit_path,
        env_var_name="UNREALINSIGHTS_EXE",
        search_roots=search_roots,
        required=required,
    )


def resolve_trace_server_exe(
    explicit_path: str | None = None,
    engine_root: str | None = None,
    search_roots: Iterable[Path] | None = None,
    required: bool = False,
) -> dict[str, object]:
    if engine_root:
        return resolve_binary_from_engine_root(TRACE_SERVER_BINARY_NAME, engine_root, required=required)
    return resolve_windows_binary(
        TRACE_SERVER_BINARY_NAME,
        explicit_path=explicit_path,
        env_var_name="UNREAL_TRACE_SERVER_EXE",
        search_roots=search_roots,
        required=required,
    )


def ensure_parent_dir(path: str | Path):
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def build_engine_program(
    engine_root: str | Path,
    target_name: str,
    *,
    platform: str = "Win64",
    configuration: str = "Development",
    timeout: float | None = None,
    log_path: str | None = None,
) -> dict[str, object]:
    """Build a UE program target using the engine's Build.bat."""
    root = resolve_engine_root(engine_root)
    build_bat = root / "Engine" / "Build" / "BatchFiles" / "Build.bat"
    if not build_bat.is_file():
        raise RuntimeError(f"Build.bat not found under engine root: {root}")

    if log_path is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = str(root / "Engine" / "Programs" / target_name / "Saved" / "Logs" / f"build-{target_name}-{timestamp}.log")
    ensure_parent_dir(log_path)

    command = [str(build_bat), target_name, platform, configuration, "-WaitMutex"]
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        exit_code = None
        timed_out = True

    Path(log_path).write_text(
        "\n".join(
            [
                f"# Command: {' '.join(command)}",
                "",
                stdout or "",
                stderr or "",
            ]
        ),
        encoding="utf-8",
        errors="replace",
    )

    return {
        "command": command,
        "cwd": str(root),
        "log_path": str(Path(log_path).resolve()),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "succeeded": (not timed_out and exit_code == 0),
    }


def ensure_engine_unrealinsights(
    engine_root: str | Path,
    *,
    build_if_missing: bool = True,
    configuration: str = "Development",
    platform: str = "Win64",
    timeout: float | None = None,
) -> dict[str, object]:
    """Resolve UnrealInsights.exe for a given engine root, building it if requested."""
    root = resolve_engine_root(engine_root)
    trace_server = resolve_binary_from_engine_root(
        TRACE_SERVER_BINARY_NAME,
        root,
        required=False,
    )
    existing = resolve_binary_from_engine_root(
        INSIGHTS_BINARY_NAME,
        root,
        required=False,
    )
    result = {
        "engine_root": str(root),
        "trace_server": trace_server,
        "build_attempted": False,
        "build": None,
    }
    if existing["available"]:
        result["insights"] = existing
        return result

    if not build_if_missing:
        raise RuntimeError(f"{INSIGHTS_BINARY_NAME} not found under engine root: {root}")

    build = build_engine_program(
        root,
        "UnrealInsights",
        platform=platform,
        configuration=configuration,
        timeout=timeout,
    )
    result["build_attempted"] = True
    result["build"] = build
    if not build["succeeded"]:
        raise RuntimeError(f"Failed to build UnrealInsights for engine root: {root}")

    result["insights"] = resolve_binary_from_engine_root(INSIGHTS_BINARY_NAME, root, required=True)
    return result


def build_insights_command(
    insights_exe: str,
    trace_path: str,
    exec_on_complete: str,
    log_path: str,
) -> list[str]:
    """Build the UnrealInsights.exe command line."""
    return [
        _normalize_path(insights_exe),
        f"-OpenTraceFile={_normalize_path(trace_path)}",
        f"-ABSLOG={_normalize_path(log_path)}",
        "-AutoQuit",
        "-NoUI",
        f"-ExecOnAnalysisCompleteCmd={exec_on_complete}",
        "-log",
    ]


def _quote_cmd_value(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def build_insights_command_line(
    insights_exe: str,
    trace_path: str,
    exec_on_complete: str,
    log_path: str,
) -> str:
    """Build a raw Windows command line for UnrealInsights.exe.

    This avoids CreateProcess argv wrapping the whole -ExecOnAnalysisCompleteCmd
    argument in outer quotes, which older UnrealInsights builds fail to parse.
    """
    exe = _quote_cmd_value(_normalize_path(insights_exe))
    trace = _quote_cmd_value(_normalize_path(trace_path))
    log = _quote_cmd_value(_normalize_path(log_path))
    exec_value = _quote_cmd_value(exec_on_complete)
    return (
        f"{exe} "
        f"-OpenTraceFile={trace} "
        f"-ABSLOG={log} "
        f"-AutoQuit -NoUI "
        f"-ExecOnAnalysisCompleteCmd={exec_value} "
        f"-log"
    )


def run_process(command: list[str] | str, timeout: float | None = None, wait: bool = True) -> dict[str, object]:
    """Run or launch a subprocess and return structured execution metadata."""
    if wait:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return {
                "command": command,
                "waited": True,
                "timed_out": False,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "pid": None,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "command": command,
                "waited": True,
                "timed_out": True,
                "exit_code": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "pid": None,
            }

    process = subprocess.Popen(command)
    return {
        "command": command,
        "waited": False,
        "timed_out": False,
        "exit_code": None,
        "stdout": None,
        "stderr": None,
        "pid": process.pid,
    }


def is_process_running(pid: int | None) -> bool:
    """Check whether a process is still running."""
    if not pid or pid <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        stdout = result.stdout.strip()
        return bool(stdout) and "No tasks are running" not in stdout and "INFO:" not in stdout

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_process(pid: int, force: bool = False, timeout: float | None = None) -> dict[str, object]:
    """Terminate a process tree and report whether it stopped."""
    if pid <= 0:
        raise RuntimeError(f"Invalid PID: {pid}")

    if os.name == "nt":
        command = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        result = run_process(command, timeout=timeout, wait=True)
    else:
        sig = signal.SIGKILL if force else signal.SIGTERM
        signal_arg = f"-{sig.name}"
        try:
            os.kill(pid, sig)
            result = {
                "command": ["kill", signal_arg, str(pid)],
                "waited": True,
                "timed_out": False,
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "pid": None,
            }
        except OSError as exc:
            result = {
                "command": ["kill", signal_arg, str(pid)],
                "waited": True,
                "timed_out": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": str(exc),
                "pid": None,
            }

    deadline = time.time() + (timeout or 10)
    while time.time() < deadline and is_process_running(pid):
        time.sleep(0.25)

    result["stopped"] = not is_process_running(pid)
    result["requested_pid"] = pid
    result["force"] = force
    return result


def parse_unreal_log(log_path: str | Path) -> dict[str, object]:
    """Extract warning and error lines from an Unreal log file."""
    path = Path(log_path).expanduser().resolve()
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "warnings": [],
            "errors": [],
            "tail": [],
        }

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    warnings = [line for line in lines if "Warning:" in line]
    errors = [line for line in lines if "Error:" in line]
    return {
        "path": str(path),
        "exists": True,
        "warnings": warnings,
        "errors": errors,
        "tail": lines[-20:],
    }
