"""Godot script execution — run GDScript files in headless mode."""

import tempfile
from pathlib import Path

from cli_anything.godot.utils.godot_backend import run_godot, validate_project


def run_script(
    project_path: str,
    script_path: str,
    timeout: int = 60,
) -> dict:
    """Execute a GDScript file in headless mode.

    The script must extend SceneTree or MainLoop.

    Args:
        project_path: Godot project directory.
        script_path: Path to the .gd file (relative to project or absolute).
        timeout: Execution timeout in seconds.

    Returns:
        Dict with status and script output.
    """
    if not validate_project(project_path):
        return {"status": "error", "message": f"Not a Godot project: {project_path}"}

    full_script = Path(project_path) / script_path
    if not full_script.exists():
        return {"status": "error", "message": f"Script not found: {script_path}"}

    # Godot expects res:// paths
    res_path = f"res://{script_path}"

    result = run_godot(
        ["--script", res_path, "--quit"],
        project_path=project_path,
        headless=True,
        timeout=timeout,
    )

    return {
        "status": "ok" if result["returncode"] == 0 else "error",
        "script": script_path,
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def run_inline(
    project_path: str,
    code: str,
    timeout: int = 60,
) -> dict:
    """Run inline GDScript code by writing a temporary .gd file.

    The code is wrapped in an extends SceneTree boilerplate with _init().

    Args:
        project_path: Godot project directory.
        code: GDScript code to execute (function body).
        timeout: Execution timeout in seconds.

    Returns:
        Dict with status and output.
    """
    if not validate_project(project_path):
        return {"status": "error", "message": f"Not a Godot project: {project_path}"}

    # Wrap user code in SceneTree boilerplate
    wrapped = (
        "extends SceneTree\n\n"
        "func _init():\n"
    )
    for line in code.splitlines():
        wrapped += f"\t{line}\n"
    wrapped += "\tquit()\n"

    # Write to a temp file inside the project (so res:// can find it)
    script_name = "_cli_anything_tmp.gd"
    script_path = Path(project_path) / script_name
    script_path.write_text(wrapped, encoding="utf-8")

    try:
        result = run_godot(
            ["--script", f"res://{script_name}", "--quit"],
            project_path=project_path,
            headless=True,
            timeout=timeout,
        )
        return {
            "status": "ok" if result["returncode"] == 0 else "error",
            "code": code,
            "returncode": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }
    finally:
        # Clean up temp script
        script_path.unlink(missing_ok=True)


def validate_script(project_path: str, script_path: str) -> dict:
    """Check if a GDScript file has valid syntax using Godot's parser.

    Args:
        project_path: Godot project directory.
        script_path: Relative path to the .gd file.

    Returns:
        Dict with validation results.
    """
    full_script = Path(project_path) / script_path
    if not full_script.exists():
        return {"status": "error", "message": f"Script not found: {script_path}"}

    # Use --check-only to validate without running
    result = run_godot(
        ["--check-only", "--script", f"res://{script_path}", "--quit"],
        project_path=project_path,
        headless=True,
        timeout=30,
    )

    valid = result["returncode"] == 0
    return {
        "status": "ok",
        "script": script_path,
        "valid": valid,
        "errors": result["stderr"] if not valid else "",
    }
