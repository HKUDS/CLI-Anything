"""Blender CLI - Render settings and export module.

Handles render configuration, preset management, and bpy script generation
for actual Blender rendering.
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime


# Render presets
RENDER_PRESETS = {
    "cycles_default": {
        "engine": "CYCLES",
        "samples": 128,
        "use_denoising": True,
        "resolution_percentage": 100,
    },
    "cycles_high": {
        "engine": "CYCLES",
        "samples": 512,
        "use_denoising": True,
        "resolution_percentage": 100,
    },
    "cycles_preview": {
        "engine": "CYCLES",
        "samples": 32,
        "use_denoising": True,
        "resolution_percentage": 50,
    },
    "eevee_default": {
        "engine": "EEVEE",
        "samples": 64,
        "use_denoising": False,
        "resolution_percentage": 100,
    },
    "eevee_high": {
        "engine": "EEVEE",
        "samples": 256,
        "use_denoising": False,
        "resolution_percentage": 100,
    },
    "eevee_preview": {
        "engine": "EEVEE",
        "samples": 16,
        "use_denoising": False,
        "resolution_percentage": 50,
    },
    "workbench": {
        "engine": "WORKBENCH",
        "samples": 1,
        "use_denoising": False,
        "resolution_percentage": 100,
    },
}

# Valid render settings
VALID_ENGINES = ["CYCLES", "EEVEE", "WORKBENCH"]
VALID_OUTPUT_FORMATS = ["PNG", "JPEG", "BMP", "TIFF", "OPEN_EXR", "HDR", "FFMPEG"]


def set_render_settings(
    project: Dict[str, Any],
    engine: Optional[str] = None,
    resolution_x: Optional[int] = None,
    resolution_y: Optional[int] = None,
    resolution_percentage: Optional[int] = None,
    samples: Optional[int] = None,
    use_denoising: Optional[bool] = None,
    film_transparent: Optional[bool] = None,
    output_format: Optional[str] = None,
    output_path: Optional[str] = None,
    preset: Optional[str] = None,
) -> Dict[str, Any]:
    """Configure render settings.

    Args:
        project: The scene dict
        engine: Render engine (CYCLES, EEVEE, WORKBENCH)
        resolution_x: Horizontal resolution in pixels
        resolution_y: Vertical resolution in pixels
        resolution_percentage: Resolution scale percentage (1-100)
        samples: Number of render samples
        use_denoising: Enable denoising
        film_transparent: Transparent film background
        output_format: Output format (PNG, JPEG, etc.)
        output_path: Output file path
        preset: Apply a render preset

    Returns:
        Dict with updated render settings
    """
    render = project.get("render", {})

    # Apply preset first, then individual overrides
    if preset:
        if preset not in RENDER_PRESETS:
            raise ValueError(
                f"Unknown render preset: {preset}. Available: {list(RENDER_PRESETS.keys())}"
            )
        for k, v in RENDER_PRESETS[preset].items():
            render[k] = v

    if engine is not None:
        if engine not in VALID_ENGINES:
            raise ValueError(f"Invalid engine: {engine}. Valid: {VALID_ENGINES}")
        render["engine"] = engine

    if resolution_x is not None:
        if resolution_x < 1:
            raise ValueError(f"Resolution X must be positive: {resolution_x}")
        render["resolution_x"] = resolution_x

    if resolution_y is not None:
        if resolution_y < 1:
            raise ValueError(f"Resolution Y must be positive: {resolution_y}")
        render["resolution_y"] = resolution_y

    if resolution_percentage is not None:
        if not 1 <= resolution_percentage <= 100:
            raise ValueError(f"Resolution percentage must be 1-100: {resolution_percentage}")
        render["resolution_percentage"] = resolution_percentage

    if samples is not None:
        if samples < 1:
            raise ValueError(f"Samples must be positive: {samples}")
        render["samples"] = samples

    if use_denoising is not None:
        render["use_denoising"] = bool(use_denoising)

    if film_transparent is not None:
        render["film_transparent"] = bool(film_transparent)

    if output_format is not None:
        if output_format not in VALID_OUTPUT_FORMATS:
            raise ValueError(f"Invalid format: {output_format}. Valid: {VALID_OUTPUT_FORMATS}")
        render["output_format"] = output_format

    if output_path is not None:
        render["output_path"] = output_path

    project["render"] = render
    return render


def get_render_settings(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get current render settings."""
    render = project.get("render", {})
    res_x = render.get("resolution_x", 1920)
    res_y = render.get("resolution_y", 1080)
    pct = render.get("resolution_percentage", 100)
    return {
        "engine": render.get("engine", "CYCLES"),
        "resolution": f"{res_x}x{res_y}",
        "effective_resolution": f"{res_x * pct // 100}x{res_y * pct // 100}",
        "resolution_percentage": pct,
        "samples": render.get("samples", 128),
        "use_denoising": render.get("use_denoising", True),
        "film_transparent": render.get("film_transparent", False),
        "output_format": render.get("output_format", "PNG"),
        "output_path": render.get("output_path", "./render/"),
    }


def list_render_presets() -> List[Dict[str, Any]]:
    """List available render presets."""
    result = []
    for name, p in RENDER_PRESETS.items():
        result.append({
            "name": name,
            "engine": p["engine"],
            "samples": p["samples"],
            "use_denoising": p["use_denoising"],
            "resolution_percentage": p["resolution_percentage"],
        })
    return result


def render_scene(
    project: Dict[str, Any],
    output_path: str,
    frame: Optional[int] = None,
    animation: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Render the scene by generating a bpy script.

    Since we cannot call Blender directly in all environments, this generates
    a Python script that can be run with `blender --background --python script.py`.

    Args:
        project: The scene dict
        output_path: Output file or directory path
        frame: Specific frame to render (None = current frame)
        animation: If True, render the full animation range
        overwrite: Allow overwriting existing files

    Returns:
        Dict with render info and script path
    """
    if os.path.exists(output_path) and not overwrite and not animation:
        raise FileExistsError(f"Output file exists: {output_path}. Use --overwrite.")

    render_settings = project.get("render", {})
    scene_settings = project.get("scene", {})

    # Determine output directory for the script
    script_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(script_dir, exist_ok=True)

    script_path = os.path.join(script_dir, "_render_script.py")
    # Ensure output_path is absolute before passing it to the script generator
    # as Blender's background process may have a different CWD.
    abs_output_path = os.path.abspath(output_path)
    script_content = generate_bpy_script(project, abs_output_path, frame=frame, animation=animation)

    with open(script_path, "w") as f:
        f.write(script_content)

    result = {
        "script_path": os.path.abspath(script_path),
        "output_path": os.path.abspath(output_path),
        "engine": render_settings.get("engine", "CYCLES"),
        "resolution": f"{render_settings.get('resolution_x', 1920)}x{render_settings.get('resolution_y', 1080)}",
        "samples": render_settings.get("samples", 128),
        "format": render_settings.get("output_format", "PNG"),
        "animation": animation,
        "command": f"blender --background --python {os.path.abspath(script_path)}",
    }

    if animation:
        result["frame_range"] = f"{scene_settings.get('frame_start', 1)}-{scene_settings.get('frame_end', 250)}"
    else:
        result["frame"] = frame or scene_settings.get("frame_current", 1)

    return result


def generate_bpy_script(
    project: Dict[str, Any],
    output_path: str,
    frame: Optional[int] = None,
    animation: bool = False,
) -> str:
    """Generate a Blender Python (bpy) script from the scene JSON.

    This creates a complete bpy script that reconstructs the entire scene
    and renders it.

    Args:
        project: The scene dict
        output_path: Render output path
        frame: Specific frame to render
        animation: Render full animation

    Returns:
        The bpy script as a string
    """
    from cli_anything.blender.utils.bpy_gen import generate_full_script
    return generate_full_script(project, output_path, frame=frame, animation=animation)
