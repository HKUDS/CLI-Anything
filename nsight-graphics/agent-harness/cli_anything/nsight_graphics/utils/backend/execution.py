"""Process execution and artifact tracking helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence

from cli_anything.nsight_graphics.utils.backend.shared import _command_string, _dedupe


def _combined_output(result: dict[str, Any]) -> str:
    """Combine stdout and stderr for downstream parsers."""
    stdout = result.get("stdout", "") or ""
    stderr = result.get("stderr", "") or ""
    return "\n".join(part for part in (stdout, stderr) if part)


def run_command(
    args: Sequence[str],
    *,
    cwd: Optional[str] = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run a subprocess and normalize the result."""
    try:
        env = os.environ.copy()
        env.setdefault("NSIGHT_SUGGEST_GRAPHICS_CAPTURE", "0")
        proc = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            env=env,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": _command_string(args),
        }
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "command": _command_string(args),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "command": _command_string(args),
        }


def default_output_dir() -> str:
    """Best-effort default output root used by the harness."""
    return str((Path.home() / "Documents" / "NVIDIA Nsight Graphics").resolve())


def activity_artifact_roots(activity: str, output_dir: Optional[str]) -> list[str]:
    """Return directories to scan for generated artifacts."""
    base = Path(default_output_dir())
    roots: list[str] = []
    if output_dir:
        roots.append(str(Path(output_dir).resolve()))
    else:
        roots.append(str(base))

    normalized = activity.lower()
    if normalized in {"frame debugger", "graphics capture"}:
        roots.extend([str(base), str(base / "GraphicsCaptures")])
    elif normalized == "gpu trace profiler":
        if not output_dir:
            roots.append(str(base / "GPUTrace"))
    elif normalized == "generate c++ capture":
        roots.append(str(base / "CppCaptures"))
    return _dedupe(roots)


def snapshot_files(roots: Sequence[str]) -> dict[str, tuple[int, int]]:
    """Snapshot file mtimes and sizes under the supplied roots."""
    snapshot: dict[str, tuple[int, int]] = {}
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path.resolve())] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def diff_snapshots(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> list[dict[str, Any]]:
    """Return non-empty files that were created or updated."""
    artifacts: list[dict[str, Any]] = []
    for path, (mtime_ns, size) in sorted(after.items()):
        previous = before.get(path)
        if size <= 0:
            continue
        if previous is None or previous != (mtime_ns, size):
            artifacts.append(
                {
                    "path": path,
                    "size": size,
                    "mtime_ns": mtime_ns,
                }
            )
    return artifacts


def run_with_artifacts(
    args: Sequence[str],
    *,
    output_roots: Sequence[str],
    cwd: Optional[str] = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Run a command and discover artifacts under the supplied roots."""
    before = snapshot_files(output_roots)
    result = run_command(args, cwd=cwd, timeout=timeout)
    after = snapshot_files(output_roots)
    result["artifacts"] = diff_snapshots(before, after)
    result["artifact_count"] = len(result["artifacts"])
    return result
