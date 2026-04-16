"""Blender backend — invoke Blender headless for rendering.

Requires: blender (system package)
    apt install blender
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


def find_blender() -> str:
    """Find the Blender executable. Raises RuntimeError if not found."""
    for name in ("blender",):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(
        "Blender is not installed. Install it with:\n"
        "  apt install blender   # Debian/Ubuntu\n"
        "  brew install --cask blender  # macOS"
    )


def get_version() -> str:
    """Get the installed Blender version string."""
    blender = find_blender()
    result = subprocess.run(
        [blender, "--version"],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip().split("\n")[0]


def render_script(
    script_path: str,
    timeout: int = 300,
) -> dict:
    """Run a bpy script using Blender headless.

    Args:
        script_path: Path to the Python script to execute
        timeout: Maximum seconds to wait

    Returns:
        Dict with stdout, stderr, return code
    """
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    blender = find_blender()
    cmd = [blender, "--background", "--python", script_path]

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


def render_scene_headless(
    bpy_script_content: str,
    output_path: str,
    timeout: int = 300,
) -> dict:
    """Write a bpy script to a temp file and render with Blender headless.

    Args:
        bpy_script_content: The bpy Python script as a string
        output_path: Expected output path (set in the script)
        timeout: Maximum seconds to wait

    Returns:
        Dict with output path, file size, method, blender version
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, prefix="blender_render_"
    ) as f:
        f.write(bpy_script_content)
        script_path = f.name

    try:
        result = render_script(script_path, timeout=timeout)

        if result["returncode"] != 0:
            raise RuntimeError(
                f"Blender render failed (exit {result['returncode']}):\n"
                f"  stderr: {result['stderr'][-500:]}"
            )

        # Verify the output file was created
        # Blender appends frame number to output path for single frames
        # e.g., /tmp/render.png becomes /tmp/render0001.png
        actual_output = output_path
        if not os.path.exists(actual_output):
            # Try with frame number suffix
            base, ext = os.path.splitext(output_path)
            for suffix in ["0001", "0000", "1"]:
                candidate = f"{base}{suffix}{ext}"
                if os.path.exists(candidate):
                    actual_output = candidate
                    break

        if not os.path.exists(actual_output):
            raise RuntimeError(
                f"Blender render produced no output file.\n"
                f"  Expected: {output_path}\n"
                f"  stdout: {result['stdout'][-500:]}"
            )

        return {
            "output": os.path.abspath(actual_output),
            "format": os.path.splitext(actual_output)[1].lstrip("."),
            "method": "blender-headless",
            "blender_version": get_version(),
            "file_size": os.path.getsize(actual_output),
        }
    finally:
        os.unlink(script_path)
