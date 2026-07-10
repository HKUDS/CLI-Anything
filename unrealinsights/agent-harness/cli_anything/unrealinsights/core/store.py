"""
Trace Store discovery helpers.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from cli_anything.unrealinsights.utils import unrealinsights_backend as backend

TRACE_FILE_SUFFIXES = (".utrace", ".ucache")
DEFAULT_LIVE_WINDOW_SECONDS = 60.0


def default_trace_root() -> Path:
    """Return the default Unreal Trace root for the current user."""
    override = os.environ.get("UNREAL_TRACE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data).expanduser().resolve() / "UnrealEngine" / "Common" / "UnrealTrace"

    return Path.home() / "AppData" / "Local" / "UnrealEngine" / "Common" / "UnrealTrace"


def resolve_store_dir(store_dir: str | None = None) -> Path:
    """Resolve the Unreal Trace Store directory."""
    env_store = (
        os.environ.get("UNREALINSIGHTS_TRACE_STORE_DIR", "").strip()
        or os.environ.get("UNREAL_TRACE_STORE_DIR", "").strip()
    )
    if store_dir:
        return Path(store_dir).expanduser().resolve()
    if env_store:
        return Path(env_store).expanduser().resolve()
    return default_trace_root() / "Store"


def _iso_from_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


def _trace_file_info(path: Path, now: float, live_window_seconds: float) -> dict[str, object]:
    stat = path.stat()
    age = max(0.0, now - stat.st_mtime)
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "extension": path.suffix.lower(),
        "file_size": stat.st_size,
        "modified_at": _iso_from_mtime(stat.st_mtime),
        "age_seconds": age,
        "is_live_candidate": age <= live_window_seconds,
    }


def list_trace_files(
    store_dir: str | None = None,
    *,
    live_only: bool = False,
    include_cache: bool = True,
    live_window_seconds: float = DEFAULT_LIVE_WINDOW_SECONDS,
) -> dict[str, object]:
    """List trace files from the local Trace Store."""
    root = resolve_store_dir(store_dir)
    suffixes = set(TRACE_FILE_SUFFIXES if include_cache else (".utrace",))
    traces: list[dict[str, object]] = []
    now = datetime.now(timezone.utc).timestamp()

    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            info = _trace_file_info(path, now=now, live_window_seconds=live_window_seconds)
            if live_only and not info["is_live_candidate"]:
                continue
            traces.append(info)

    traces.sort(key=lambda item: (item.get("modified_at") or "", item.get("path") or ""), reverse=True)
    return {
        "store_dir": str(root),
        "exists": root.is_dir(),
        "include_cache": include_cache,
        "live_only": live_only,
        "live_window_seconds": live_window_seconds,
        "trace_count": len(traces),
        "traces": traces,
    }


def latest_trace_file(
    store_dir: str | None = None,
    *,
    live_only: bool = False,
    include_cache: bool = True,
    live_window_seconds: float = DEFAULT_LIVE_WINDOW_SECONDS,
) -> dict[str, object]:
    """Return the newest trace file from the Trace Store."""
    listing = list_trace_files(
        store_dir,
        live_only=live_only,
        include_cache=include_cache,
        live_window_seconds=live_window_seconds,
    )
    latest = listing["traces"][0] if listing["traces"] else None
    return {
        **listing,
        "latest": latest,
    }


def trace_store_info(store_dir: str | None = None, trace_server_exe: str | None = None) -> dict[str, object]:
    """Return local Trace Store and Trace Server status."""
    root = default_trace_root()
    resolved_store = resolve_store_dir(store_dir)
    trace_server = backend.resolve_trace_server_exe(trace_server_exe, required=False)
    listing = list_trace_files(str(resolved_store))

    logs = []
    if root.is_dir():
        for log_path in sorted(root.glob("Server_*.log"), key=lambda path: path.stat().st_mtime, reverse=True):
            stat = log_path.stat()
            logs.append(
                {
                    "path": str(log_path.resolve()),
                    "file_size": stat.st_size,
                    "modified_at": _iso_from_mtime(stat.st_mtime),
                }
            )

    return {
        "trace_root": str(root),
        "trace_root_exists": root.is_dir(),
        "store_dir": str(resolved_store),
        "store_exists": resolved_store.is_dir(),
        "trace_file_count": listing["trace_count"],
        "trace_server": trace_server,
        "watch_folders": [str(resolved_store)],
        "server_logs": logs[:10],
    }
