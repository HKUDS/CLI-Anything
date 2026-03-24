"""FreeCAD backend — invoke FreeCAD headless for rendering.

Requires: FreeCAD (system package)
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


def find_freecad() -> str:
    """Find the FreeCAD executable. Raises RuntimeError if not found."""
    # Look for FreeCADCmd (preferred for headless) then FreeCAD
    for name in ("FreeCADCmd", "freecadcmd", "FreeCAD", "freecad"):
        path = shutil.which(name)
        if path:
            return path
    
    # Common Windows paths if not in PATH
    win_paths = [
        r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD\bin\FreeCADCmd.exe",
    ]
    for path in win_paths:
        if os.path.exists(path):
            return path
            
    raise RuntimeError(
        "FreeCAD is not installed or not in PATH. Please install FreeCAD."
    )


def get_version() -> str:
    """Get the installed FreeCAD version string."""
    freecad = find_freecad()
    # FreeCADCmd --version might not be supported in some versions,
    # we can run a small script to get it from FreeCAD module.
    script = "import FreeCAD; print(FreeCAD.version())"
    result = subprocess.run(
        [freecad, "--console"],
        input=script,
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return "Unknown Version"


def execute_script(
    script_path: str,
    timeout: int = 300,
) -> dict:
    """Run a Python script using FreeCAD headless.

    Args:
        script_path: Path to the Python script to execute
        timeout: Maximum seconds to wait

    Returns:
        Dict with stdout, stderr, return code
    """
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    freecad = find_freecad()
    
    # For FreeCADCmd, we can use --console or just pass the script
    cmd = [freecad, script_path]

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=timeout,
    )

    return {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def execute_freecad_python(
    script_content: str,
    timeout: int = 300,
) -> dict:
    """Write a script to a temp file and run with FreeCAD headless.

    Args:
        script_content: The Python script as a string
        timeout: Maximum seconds to wait

    Returns:
        Dict with result metadata
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, prefix="freecad_exec_"
    ) as f:
        f.write(script_content)
        script_path = f.name

    try:
        result = execute_script(script_path, timeout=timeout)

        if result["returncode"] != 0:
            raise RuntimeError(
                f"FreeCAD script execution failed (exit {result['returncode']}):\n"
                f"  stderr: {result['stderr'][-500:]}"
            )

        return {
            "success": True,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "script_path": script_path
        }
    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)
