"""Blender backend — invoke Blender headless for rendering.

Requires: blender (system package)
    apt install blender
"""

import glob
import os
import shutil
import subprocess
import tempfile
from typing import Optional


_FRAME_SUFFIXES = ("0001", "0000", "1")


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


def find_render_outputs(output_path: str, animation: bool = False) -> list[str]:
    """Resolve Blender's actual output file(s) for a requested render path."""
    abs_output_path = os.path.abspath(output_path)
    base, ext = os.path.splitext(abs_output_path)

    direct_candidates = [abs_output_path]
    if ext:
        direct_candidates.extend(f"{base}{suffix}{ext}" for suffix in _FRAME_SUFFIXES)
    else:
        direct_candidates.extend(f"{abs_output_path}{suffix}" for suffix in _FRAME_SUFFIXES)

    for candidate in direct_candidates:
        if os.path.exists(candidate):
            return [candidate]

    patterns = [f"{base}*{ext}"] if ext else [f"{abs_output_path}*"]
    matches = sorted(
        path
        for pattern in patterns
        for path in glob.glob(pattern)
        if os.path.isfile(path)
    )
    if animation:
        return matches
    return matches[:1]


def render_script(
    script_path: str,
    output_path: Optional[str] = None,
    animation: bool = False,
    timeout: int = 300,
) -> dict:
    """Run a bpy script using Blender headless.

    Args:
        script_path: Path to the Python script to execute
        output_path: Expected render output path
        animation: Whether Blender is expected to render an animation sequence
        timeout: Maximum seconds to wait

    Returns:
        Dict with stdout, stderr, return code, and optional output metadata
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

    render_result = {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

    if output_path and result.returncode == 0:
        outputs = find_render_outputs(output_path, animation=animation)
        if not outputs:
            raise RuntimeError(
                "Blender render produced no output file.\n"
                f"  Expected: {output_path}\n"
                f"  stdout: {result.stdout[-500:]}"
            )

        primary_output = outputs[0]
        render_result.update({
            "output": os.path.abspath(primary_output),
            "outputs": [os.path.abspath(path) for path in outputs],
            "output_count": len(outputs),
            "format": os.path.splitext(primary_output)[1].lstrip("."),
            "method": "blender-headless",
            "blender_version": get_version(),
            "file_size": os.path.getsize(primary_output),
        })

    return render_result


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
        result = render_script(script_path, output_path=output_path, timeout=timeout)

        if result["returncode"] != 0:
            raise RuntimeError(
                f"Blender render failed (exit {result['returncode']}):\n"
                f"  stderr: {result['stderr'][-500:]}"
            )
        return {
            "output": result["output"],
            "format": result["format"],
            "method": result["method"],
            "blender_version": result["blender_version"],
            "file_size": result["file_size"],
        }
    finally:
        os.unlink(script_path)
