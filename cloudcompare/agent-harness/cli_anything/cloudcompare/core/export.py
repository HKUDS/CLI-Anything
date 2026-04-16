"""Export pipeline for the CloudCompare CLI harness.

Handles format conversion and batch export using the real CloudCompare backend.
"""

import os
from pathlib import Path
from typing import Optional

from cli_anything.cloudcompare.utils.cc_backend import (
    CLOUD_FORMATS,
    MESH_FORMATS,
    convert_format,
    open_and_save,
    run_cloudcompare,
)


# ── Format presets ────────────────────────────────────────────────────────────

CLOUD_PRESETS = {
    "las":   {"format": "LAS",  "ext": "las",  "desc": "LAS point cloud"},
    "laz":   {"format": "LAS",  "ext": "laz",  "desc": "LAZ (compressed LAS)"},
    "ply":   {"format": "PLY",  "ext": "ply",  "desc": "PLY polygon file"},
    "pcd":   {"format": "PCD",  "ext": "pcd",  "desc": "Point Cloud Data"},
    "xyz":   {"format": "ASC",  "ext": "xyz",  "desc": "XYZ ASCII cloud"},
    "asc":   {"format": "ASC",  "ext": "asc",  "desc": "ASC ASCII cloud"},
    "csv":   {"format": "ASC",  "ext": "csv",  "desc": "CSV ASCII cloud"},
    "bin":   {"format": "BIN",  "ext": "bin",  "desc": "CloudCompare native binary"},
    "e57":   {"format": "E57",  "ext": "e57",  "desc": "E57 lidar exchange format"},
}

MESH_PRESETS = {
    "obj":   {"format": "OBJ",  "ext": "obj",  "desc": "Wavefront OBJ mesh"},
    "stl":   {"format": "STL",  "ext": "stl",  "desc": "STL mesh"},
    "ply":   {"format": "PLY",  "ext": "ply",  "desc": "PLY mesh"},
    "bin":   {"format": "BIN",  "ext": "bin",  "desc": "CloudCompare native binary"},
}


def list_presets() -> dict:
    """Return available presets for cloud and mesh export."""
    return {
        "cloud": {k: v["desc"] for k, v in CLOUD_PRESETS.items()},
        "mesh": {k: v["desc"] for k, v in MESH_PRESETS.items()},
    }


def export_cloud(
    input_path: str,
    output_path: str,
    preset: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
    overwrite: bool = False,
) -> dict:
    """Export a point cloud to a new format using CloudCompare.

    Args:
        input_path: Source cloud file.
        output_path: Destination file path (format from extension or preset).
        preset: Optional format preset name (e.g., 'las', 'ply').
        extra_args: Additional CC command args applied before saving.
        overwrite: Whether to overwrite existing output file.

    Returns:
        dict with output path, format, file_size, and backend result.

    Raises:
        FileNotFoundError: If input doesn't exist.
        FileExistsError: If output exists and overwrite=False.
        RuntimeError: If export fails.
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Determine format from preset or extension (must happen before overwrite check
    # because a preset can change the output file extension).
    if preset:
        preset = preset.lower()
        if preset not in CLOUD_PRESETS:
            raise ValueError(f"Unknown preset {preset!r}. Options: {list(CLOUD_PRESETS)}")
        info = CLOUD_PRESETS[preset]
        fmt = info["format"]
        ext = info["ext"]
        # If output_path has different extension, replace it
        out_base = os.path.splitext(output_path)[0]
        output_path = f"{out_base}.{ext}"
    else:
        out_ext = os.path.splitext(output_path)[1].lstrip(".").lower()
        fmt = CLOUD_FORMATS.get(out_ext, "ASC")
        ext = out_ext

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use overwrite=True."
        )

    result = open_and_save(input_path, output_path, extra_args)

    if result["returncode"] != 0:
        raise RuntimeError(
            f"CloudCompare export failed (exit {result['returncode']}):\n"
            f"  stderr: {result['stderr'][:500]}"
        )

    if not result.get("exists"):
        raise RuntimeError(
            f"CloudCompare ran but output file was not created: {output_path}"
        )

    return {
        "output": output_path,
        "format": fmt,
        "extension": ext,
        "file_size": result.get("file_size", 0),
        "returncode": result["returncode"],
        "command": result["command"],
    }


def export_mesh(
    input_path: str,
    output_path: str,
    preset: Optional[str] = None,
    overwrite: bool = False,
) -> dict:
    """Export a mesh to a new format using CloudCompare.

    Args:
        input_path: Source mesh file.
        output_path: Destination file path.
        preset: Optional format preset (e.g., 'obj', 'stl', 'ply').
        overwrite: Whether to overwrite existing output.

    Returns:
        dict with output info.
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Resolve preset before overwrite check — preset can change the output extension.
    if preset:
        preset = preset.lower()
        if preset not in MESH_PRESETS:
            raise ValueError(f"Unknown mesh preset {preset!r}. Options: {list(MESH_PRESETS)}")
        info = MESH_PRESETS[preset]
        fmt = info["format"]
        ext = info["ext"]
        out_base = os.path.splitext(output_path)[0]
        output_path = f"{out_base}.{ext}"
    else:
        out_ext = os.path.splitext(output_path)[1].lstrip(".").lower()
        fmt = MESH_FORMATS.get(out_ext, "OBJ")
        ext = out_ext

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use overwrite=True."
        )

    args = [
        "-O", input_path,
        "-M_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_MESHES", "FILE", output_path,
    ]

    result = run_cloudcompare(args)
    exists = os.path.exists(output_path)

    if result["returncode"] != 0:
        raise RuntimeError(
            f"CloudCompare mesh export failed (exit {result['returncode']}):\n"
            f"  stderr: {result['stderr'][:500]}"
        )

    if not exists:
        raise RuntimeError(
            f"CloudCompare ran but output file was not created: {output_path}"
        )

    return {
        "output": output_path,
        "format": fmt,
        "extension": ext,
        "file_size": os.path.getsize(output_path),
        "returncode": result["returncode"],
        "command": result["command"],
    }


def batch_export(
    input_paths: list[str],
    output_dir: str,
    preset: str = "las",
    overwrite: bool = False,
) -> list[dict]:
    """Batch export multiple clouds to a directory.

    Args:
        input_paths: List of input cloud files.
        output_dir: Directory for output files.
        preset: Format preset for all outputs.
        overwrite: Whether to overwrite existing files.

    Returns:
        List of result dicts (one per input).
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for inp in input_paths:
        stem = Path(inp).stem
        ext = CLOUD_PRESETS.get(preset, CLOUD_PRESETS["las"])["ext"]
        out = os.path.join(output_dir, f"{stem}.{ext}")
        try:
            r = export_cloud(inp, out, preset=preset, overwrite=overwrite)
            r["status"] = "ok"
        except Exception as e:
            r = {"input": inp, "output": out, "status": "error", "error": str(e)}
        results.append(r)
    return results
