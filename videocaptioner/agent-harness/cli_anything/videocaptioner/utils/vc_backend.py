"""VideoCaptioner CLI backend — subprocess wrapper for the videocaptioner command.

All core modules call through this single module to invoke the existing
videocaptioner CLI. This keeps the Click harness thin and delegates real
work to the production-tested videocaptioner package.
"""

import json
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Any
from functools import lru_cache

UPSTREAM_REQUIRES_PYTHON = ">=3.10,<3.13"
UPSTREAM_COMPATIBLE_MINORS = "3.10-3.12"


def get_runtime_guidance() -> dict[str, str]:
    """Return install/runtime guidance for the upstream backend."""
    return {
        "python_runtime": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "upstream_requires_python": UPSTREAM_REQUIRES_PYTHON,
        "recommended_python": UPSTREAM_COMPATIBLE_MINORS,
    }


def _find_vc() -> str:
    """Locate the videocaptioner binary."""
    path = shutil.which("videocaptioner")
    if not path:
        guidance = get_runtime_guidance()
        raise RuntimeError(
            "videocaptioner not found on PATH. "
            "Install with: pip install videocaptioner. "
            f"Upstream videocaptioner 1.4.1 requires Python {guidance['upstream_requires_python']} "
            f"(use Python {guidance['recommended_python']})."
        )
    return path


def run(args: list[str], timeout: int = 600) -> dict[str, Any]:
    """Run a videocaptioner CLI command and return structured result.

    Args:
        args: Command arguments (without 'videocaptioner' prefix).
        timeout: Max seconds to wait.

    Returns:
        Dict with 'exit_code', 'stdout', 'stderr', 'output_path' (if found).
    """
    cmd = [_find_vc()] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(cmd)}")

    # Extract output path from quiet mode stdout
    stdout = result.stdout.strip()
    output_path = stdout if stdout and Path(stdout).suffix else None

    return {
        "exit_code": result.returncode,
        "stdout": stdout,
        "stderr": result.stderr.strip(),
        "output_path": output_path,
        "command": " ".join(cmd),
    }


def run_quiet(args: list[str], timeout: int = 600) -> str:
    """Run in quiet mode and return the output file path.

    Raises RuntimeError on failure.
    """
    result = run(args + ["-q"], timeout=timeout)
    if result["exit_code"] != 0:
        error_msg = result["stderr"] or result["stdout"] or "Unknown error"
        raise RuntimeError(f"videocaptioner failed (exit {result['exit_code']}): {error_msg}")
    return result["stdout"]


def get_version() -> str:
    """Get videocaptioner version string."""
    result = run(["--version"])
    return result["stdout"]


def get_config() -> str:
    """Get current configuration."""
    result = run(["config", "show"])
    return result["stdout"]


@lru_cache(maxsize=None)
def get_command_help(command: str) -> str:
    """Return backend help text for a subcommand, or an empty string."""
    result = run([command, "--help"])
    if result["exit_code"] != 0:
        return ""
    return result["stdout"]


@lru_cache(maxsize=None)
def has_subcommand(command: str) -> bool:
    """Check whether the installed backend exposes a subcommand."""
    result = run(["--help"])
    if result["exit_code"] != 0:
        return False
    return command in result["stdout"]


def get_styles() -> str:
    """Get available subtitle styles, or explain when unsupported."""
    if not has_subcommand("style"):
        version = get_version()
        return (
            f"{version}\n"
            "Installed backend does not expose a 'style' subcommand. "
            "Style presets are not available in this VideoCaptioner version."
        )
    result = run(["style"])
    return result["stdout"]
