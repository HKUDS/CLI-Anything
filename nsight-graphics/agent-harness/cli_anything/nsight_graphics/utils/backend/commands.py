"""Validation and command-building helpers for Nsight CLI invocations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional, Sequence

from cli_anything.nsight_graphics.utils.backend.discovery import INSTALL_INSTRUCTIONS


def require_binary(binaries: dict[str, Optional[str]], key: str) -> str:
    """Require a specific executable to exist."""
    path = binaries.get(key)
    if not path:
        raise RuntimeError(INSTALL_INSTRUCTIONS)
    return path


def require_launch_target(*, project: Optional[str], exe: Optional[str]) -> None:
    """Require at least one launch target input."""
    if not project and not exe:
        raise ValueError("Specify --exe or set --project at the root level.")


def prepare_output_dir(output_dir: Optional[str]) -> Optional[str]:
    """Resolve and create an explicit output directory before invoking Nsight."""
    if not output_dir:
        return None
    resolved = Path(output_dir).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def ensure_exactly_one(label: str, flags: dict[str, bool]) -> str:
    """Validate that exactly one flag in the set is selected."""
    selected = [name for name, enabled in flags.items() if enabled]
    if len(selected) != 1:
        choices = ", ".join(flags.keys())
        raise ValueError(f"{label}: choose exactly one of {choices}.")
    return selected[0]


def ensure_at_most_one(label: str, flags: dict[str, bool]) -> Optional[str]:
    """Validate that zero or one flags are selected."""
    selected = [name for name, enabled in flags.items() if enabled]
    if len(selected) > 1:
        choices = ", ".join(flags.keys())
        raise ValueError(f"{label}: choose at most one of {choices}.")
    return selected[0] if selected else None


def format_env_values(envs: Sequence[str]) -> Optional[str]:
    """Format KEY=VALUE entries for ngfx.exe."""
    cleaned = [entry.strip() for entry in envs if entry and entry.strip()]
    if not cleaned:
        return None
    joined = "; ".join(cleaned)
    if not joined.endswith(";"):
        joined += ";"
    return joined


def format_program_args(args: Sequence[str]) -> Optional[str]:
    """Format target executable arguments."""
    cleaned = [entry for entry in args if entry]
    if not cleaned:
        return None
    return subprocess.list2cmdline(cleaned)


def build_unified_command(
    binaries: dict[str, Optional[str]],
    *,
    activity: Optional[str] = None,
    project: Optional[str] = None,
    output_dir: Optional[str] = None,
    hostname: Optional[str] = None,
    platform_name: Optional[str] = None,
    exe: Optional[str] = None,
    working_dir: Optional[str] = None,
    args: Sequence[str] = (),
    envs: Sequence[str] = (),
    attach_pid: Optional[int] = None,
    launch_detached: bool = False,
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Build a command line for the unified ngfx.exe CLI."""
    ngfx = require_binary(binaries, "ngfx")
    command: list[str] = [ngfx]
    if hostname:
        command.extend(["--hostname", hostname])
    if project:
        command.extend(["--project", project])
    if output_dir:
        command.extend(["--output-dir", output_dir])
    if activity:
        command.extend(["--activity", activity])
    if platform_name:
        command.extend(["--platform", platform_name])
    if launch_detached:
        command.append("--launch-detached")
    if attach_pid is not None:
        command.extend(["--attach-pid", str(attach_pid)])
    if exe:
        command.extend(["--exe", exe])
    if working_dir:
        command.extend(["--dir", working_dir])
    formatted_args = format_program_args(args)
    if formatted_args:
        command.extend(["--args", formatted_args])
    formatted_env = format_env_values(envs)
    if formatted_env:
        command.extend(["--env", formatted_env])
    command.extend(extra_args)
    return command


def build_split_capture_command(
    binaries: dict[str, Optional[str]],
    *,
    exe: str,
    output_dir: Optional[str] = None,
    working_dir: Optional[str] = None,
    args: Sequence[str] = (),
    envs: Sequence[str] = (),
    wait_seconds: Optional[int] = None,
    wait_frames: Optional[int] = None,
    wait_hotkey: bool = False,
    frame_count: int = 1,
) -> list[str]:
    """Build a command line for the split ngfx-capture tool."""
    capture = require_binary(binaries, "ngfx_capture")
    command: list[str] = [capture, "--exe", exe, "--frame-count", str(frame_count)]
    if output_dir:
        command.extend(["--output-dir", output_dir])
    if working_dir:
        command.extend(["--working-dir", working_dir])
    formatted_args = format_program_args(args)
    if formatted_args:
        command.extend(["--args", formatted_args])
    formatted_env = format_env_values(envs)
    if formatted_env:
        command.extend(["--env", formatted_env])

    ensure_exactly_one(
        "frame trigger",
        {
            "wait_seconds": wait_seconds is not None,
            "wait_frames": wait_frames is not None,
            "wait_hotkey": wait_hotkey,
        },
    )
    if wait_seconds is not None:
        command.extend(["--capture-countdown-timer", str(wait_seconds * 1000)])
    elif wait_frames is not None:
        command.extend(["--capture-frame", str(wait_frames)])
    else:
        command.append("--capture-hotkey")
    return command


def build_replay_command(
    binaries: dict[str, Optional[str]],
    *,
    capture_file: str,
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Build a command line for ngfx-replay."""
    replay = require_binary(binaries, "ngfx_replay")
    return [replay, *extra_args, capture_file]
