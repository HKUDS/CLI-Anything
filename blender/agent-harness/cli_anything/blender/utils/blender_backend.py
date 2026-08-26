"""Blender backend — invoke Blender headless for rendering.

Requires: blender (system package)
    apt install blender
"""

import glob
import os
import platform
import shutil
import subprocess
import tempfile
from typing import Optional


def _fingerprint(path: str) -> Optional[tuple[int, int]]:
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _is_fresh(path: str, prior: dict[str, tuple[int, int]]) -> bool:
    return prior.get(os.path.abspath(path)) != _fingerprint(path)


def _windows_install_candidates() -> list[str]:
    """Common Blender install locations when PATH lookup misses."""
    candidates: list[str] = []
    for root in (
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ):
        pattern = os.path.join(root, "Blender Foundation", "Blender *", "blender.exe")
        candidates.extend(sorted(glob.glob(pattern), reverse=True))
    return candidates


def find_blender() -> str:
    """Find the Blender executable. Raises RuntimeError if not found."""
    env_path = os.environ.get("BLENDER_EXECUTABLE", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path

    for name in ("blender", "blender.exe"):
        path = shutil.which(name)
        if path:
            return path

    if platform.system().lower() == "windows":
        for candidate in _windows_install_candidates():
            if os.path.isfile(candidate):
                return candidate

    raise RuntimeError(
        "Blender is not installed. Install it with:\n"
        "  apt install blender   # Debian/Ubuntu\n"
        "  brew install --cask blender  # macOS\n"
        "  https://www.blender.org/download/  # Windows"
    )


def get_version() -> str:
    """Get the installed Blender version string."""
    blender = find_blender()
    result = subprocess.run(
        [blender, "--version"],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip().split("\n")[0]


def _is_render_output(path: str, abs_output_path: str) -> bool:
    """Whether a path is a file Blender writes for this render target."""
    stem = os.path.splitext(path)[0]
    base = os.path.splitext(abs_output_path)[0]
    return stem == base or (stem.startswith(base) and stem[len(base):].isdigit())


def find_render_outputs(
    output_path: str,
    animation: bool = False,
    prior: Optional[dict[str, tuple[int, int]]] = None,
) -> list[str]:
    """Resolve Blender's actual output file(s) for a requested render path."""
    abs_output_path = os.path.abspath(output_path)
    base, ext = os.path.splitext(abs_output_path)
    stale = prior or {}

    matches = sorted(
        path
        for pattern in ([f"{base}*{ext}"] if ext else [f"{abs_output_path}*"])
        for path in glob.glob(pattern)
        if os.path.isfile(path) and _is_fresh(path, stale)
        and _is_render_output(path, abs_output_path)
    )
    if animation:
        return matches
    return matches[:1]


def render_script(
    script_path: str,
    timeout: Optional[int] = 300,
    *,
    output_path: Optional[str] = None,
    animation: bool = False,
    expected_outputs: Optional[list[str]] = None,
) -> dict:
    """Run a bpy script using Blender headless.

    Args:
        script_path: Path to the Python script to execute
        timeout: Maximum seconds to wait, or None to wait until Blender exits
        output_path: Expected render output path
        animation: Whether Blender is expected to render an animation sequence
        expected_outputs: Exact artifact paths derived by the render caller

    Returns:
        Dict with stdout, stderr, return code, and optional output metadata
    """
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    if output_path and os.path.exists(output_path) and not os.path.isfile(output_path):
        raise ValueError(f"Output path is not a file: {output_path}")

    blender = find_blender()
    cmd = [blender, "--background", "--python", script_path]
    prior = None
    if output_path:
        prior = {}
        candidates = expected_outputs or find_render_outputs(output_path, animation=True)
        for path in candidates:
            fp = _fingerprint(path)
            if fp is not None:
                prior[os.path.abspath(path)] = fp

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Blender render timed out after {timeout} seconds"
        ) from exc

    render_result = {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

    if result.returncode != 0:
        return render_result

    if output_path:
        outputs = (
            [
                path for path in expected_outputs
                if os.path.isfile(path) and _is_fresh(path, prior or {})
            ]
            if expected_outputs is not None
            else find_render_outputs(output_path, animation=animation, prior=prior)
        )
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
            "method": "blender-headless",
            "blender_version": result["blender_version"],
            "file_size": result["file_size"],
        }
    finally:
        os.unlink(script_path)
