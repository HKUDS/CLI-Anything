"""Blender backend — invoke Blender headless for rendering.

Requires: blender (system package)
    apt install blender
"""

import os
import re
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
    # Without --python-exit-code, Blender exits 0 even when the bpy script
    # raises, so returncode alone cannot tell a completed render from a
    # script that died partway through.
    cmd = [blender, "--background", "--python-exit-code", "1",
           "--python", script_path]

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


def resolve_output(output_path: str, expected_ext: Optional[str] = None) -> Optional[str]:
    """Return the real rendered file, or None if nothing was produced.

    Blender appends a frame number to the output path for single frames,
    e.g. /tmp/render.png becomes /tmp/render0001.png. With the default
    ``use_file_extension`` it also appends the format's extension when the
    path has none, so ``render execute /tmp/result`` with PNG output writes
    /tmp/result.png — pass ``expected_ext`` so that spelling is probed too.
    """
    base, ext = os.path.splitext(output_path)

    # Blender only appends an extension when the path lacks one; if the path
    # already has an extension it is used as written. When it does append,
    # that spelling is what this render just wrote — probe it first, or an
    # older bare file of the same name wins and the freshness check then
    # rejects a render that actually succeeded.
    tails = []
    if expected_ext and not ext:
        tails.append(expected_ext if expected_ext.startswith(".") else f".{expected_ext}")
    tails.append(ext)

    for tail in tails:
        for suffix in ("", "0001", "0000", "1"):
            candidate = f"{base}{suffix}{tail}"
            # isfile, not exists: an output_path naming an existing directory
            # would otherwise be returned as the rendered artifact, with the
            # directory entry's size reported as the image size.
            if os.path.isfile(candidate):
                return candidate
    return None


def _frame_files(output_path: str, expected_ext: Optional[str] = None,
                 frame_range: Optional[tuple] = None) -> set:
    """Names in the output directory that are frames of this sequence.

    Blender numbers frames as <prefix><digits><ext>. Matching on prefix and
    extension alone would also pick up unrelated neighbours such as
    frame_preview.png, which would then block a render without --overwrite
    and be miscounted as an emitted frame with it.

    ``frame_range`` narrows the match to (start, end) inclusive. The collision
    preflight passes it so that rendering frames 1-10 is not refused because
    frame_0250.png from an unrelated earlier range happens to be present.
    """
    base, ext = os.path.splitext(os.path.abspath(output_path))
    frame_dir = os.path.dirname(base) or "."
    prefix = os.path.basename(base)
    if not ext and expected_ext:
        ext = expected_ext if expected_ext.startswith(".") else f".{expected_ext}"
    if not os.path.isdir(frame_dir):
        return set()

    pattern = re.compile(
        rf"^{re.escape(prefix)}(\d+){re.escape(ext)}$" if ext
        else rf"^{re.escape(prefix)}(\d+)$"
    )
    matches = set()
    for f in os.listdir(frame_dir):
        m = pattern.match(f)
        if not m:
            continue
        if frame_range is not None:
            n = int(m.group(1))
            if not (frame_range[0] <= n <= frame_range[1]):
                continue
        matches.add(f)
    return matches


def render_script_file(
    script_path: str,
    output_path: str,
    timeout: int = 300,
    animation: bool = False,
    expected_ext: Optional[str] = None,
    movie: bool = False,
) -> dict:
    """Render an on-disk bpy script with Blender headless and verify the output.

    Args:
        script_path: Path to the bpy script to execute
        output_path: Expected output file, or the frame-sequence base for animation
        timeout: Maximum seconds to wait
        animation: True when the script renders a frame range

    Returns:
        Dict with output path, file size, method, blender version, command
    """
    # Frames already on disk from an earlier render with the same prefix are
    # not ours; without this snapshot a 10-frame render into a directory
    # holding 250 old frames would report 250.
    # A video format emits one movie file, not a numbered sequence, so it
    # follows the single-artifact path even when rendering a frame range.
    sequence = animation and not movie
    pre_existing = _frame_files(output_path, expected_ext) if sequence else set()

    # Mark the start on the same filesystem as the frames rather than trusting
    # wall-clock time: the two can disagree, and mtime granularity varies.
    marker_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    os.makedirs(marker_dir, exist_ok=True)
    fd, started_marker = tempfile.mkstemp(prefix=".render_started_", dir=marker_dir)
    os.close(fd)
    render_started = os.path.getmtime(started_marker)

    try:
        result = render_script(script_path, timeout=timeout)
    finally:
        if started_marker and os.path.exists(started_marker):
            os.unlink(started_marker)

    if result["returncode"] != 0:
        raise RuntimeError(
            f"Blender render failed (exit {result['returncode']}):\n"
            f"  stderr: {result['stderr'][-500:]}"
        )

    if sequence:
        base, ext = os.path.splitext(os.path.abspath(output_path))
        frame_dir = os.path.dirname(base) or "."
        after = _frame_files(output_path, expected_ext)
        # Re-rendered frames keep their names, so compare mtimes rather than
        # names alone: a frame is ours if it is new or was just rewritten.
        mine = [
            f for f in after
            if f not in pre_existing
            or os.path.getmtime(os.path.join(frame_dir, f)) >= render_started
        ]

        # Sort by frame number, not lexicographically: across a digit-width
        # boundary a plain sort puts frame10000.png before frame9999.png, and
        # first_frame would then name the wrong frame.
        def _frame_number(name: str) -> int:
            m = re.search(r"(\d+)(?:\.[^.]*)?$", name)
            return int(m.group(1)) if m else 0

        frames = sorted(mine, key=_frame_number)
        if not frames:
            raise RuntimeError(
                f"Blender render produced no frames.\n"
                f"  Expected: {output_path}\n"
                f"  stdout: {result['stdout'][-500:]}"
            )
        # An animation prefix is usually extensionless ("frame_"), so take the
        # format from expected_ext or an emitted frame rather than returning ""
        # and clobbering the caller's already-correct format.
        fmt = ext.lstrip(".")
        if not fmt:
            fmt = (expected_ext or os.path.splitext(frames[0])[1]).lstrip(".")

        return {
            "output": frame_dir,
            "frames": len(frames),
            "first_frame": os.path.join(frame_dir, frames[0]),
            "format": fmt,
            "method": "blender-headless",
            "blender_version": get_version(),
            "command": result["command"],
        }

    actual_output = resolve_output(output_path, expected_ext)

    # A pre-existing file at the target is not proof of a render. With
    # --overwrite the guard in render_scene deliberately steps aside, so a
    # script that died before writing would otherwise let the stale file be
    # reported as this run's output.
    if actual_output is not None and os.path.getmtime(actual_output) < render_started:
        raise RuntimeError(
            f"Blender left the existing file untouched — no new render was produced.\n"
            f"  Path: {actual_output}\n"
            f"  stderr: {result['stderr'][-500:]}"
        )
    if actual_output is None:
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
        "command": result["command"],
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
        return render_script_file(script_path, output_path, timeout=timeout)
    finally:
        os.unlink(script_path)
