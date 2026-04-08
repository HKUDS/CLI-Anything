"""Backend adapter for the external dify-workflow CLI."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys


def _decode_output(data: bytes | None) -> str:
    """Decode subprocess bytes predictably across Windows locales."""
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def require_dify_workflow_command() -> list[str]:
    """Resolve the upstream dify-workflow executable or module."""
    cli_path = shutil.which("dify-workflow")
    if cli_path:
        return [cli_path]

    if importlib.util.find_spec("dify_workflow") is not None:
        return [sys.executable, "-m", "dify_workflow.cli"]

    raise RuntimeError(
        "dify-workflow command not found. Install the upstream project first with:\n"
        "  python -m pip install \"dify-ai-workflow-tools @ git+https://github.com/Akabane71/dify-workflow-cli.git@main\"\n"
        "If you later publish to PyPI, a normal pip install is also fine."
    )


def build_command(args: list[str]) -> list[str]:
    """Build the final subprocess command."""
    return [*require_dify_workflow_command(), *args]


def has_upstream_cli() -> bool:
    """Return whether the upstream CLI or module is available."""
    try:
        require_dify_workflow_command()
    except RuntimeError:
        return False
    return True


def run_dify_workflow(args: list[str]) -> str:
    """Run the upstream CLI and return stdout."""
    command = build_command(args)
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = (_decode_output(result.stderr) or _decode_output(result.stdout)).strip()
        raise RuntimeError(message or "dify-workflow exited with a non-zero status")
    return _decode_output(result.stdout).rstrip()
