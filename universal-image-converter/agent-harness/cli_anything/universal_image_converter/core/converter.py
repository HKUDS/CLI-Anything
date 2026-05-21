"""Universal Image Converter — Core conversion engine using Pillow.

Reference: gimp/agent-harness/cli_anything/gimp/core/export.py (render pipeline)
Reference: gimp/agent-harness/cli_anything/gimp/core/media.py (probe_image)
"""

import os
from typing import Optional


def probe_image(path: str):
    """Analyze an image file and return metadata."""
    from PIL import Image

    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")

    img = Image.open(path)
    info = {
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "format": img.format,
        "mode": img.mode,
        "width": img.width,
        "height": img.height,
        "file_size": os.path.getsize(path),
        "file_size_human": _human_size(os.path.getsize(path)),
        "dpi": img.info.get("dpi", None),
    }
    img.close()
    return info


def convert_image(
    input_path: str,
    output_path: str,
    output_format: str,
    quality: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_aspect: bool = True,
    overwrite: bool = False,
    **extra_params,
):
    """Convert a single image to a new format.

    Args:
        input_path: Path to source image.
        output_path: Path for the converted output.
        output_format: Target format (png, jpg, webp, etc.).
        quality: Quality preset name (lossless, high, medium, low).
        width: Target width in pixels (optional).
        height: Target height in pixels (optional).
        keep_aspect: Maintain aspect ratio when resizing.
        overwrite: Overwrite existing output file.
        **extra_params: Additional format-specific parameters.

    Returns:
        dict with conversion result metadata.
    """
    from PIL import Image
    from cli_anything.universal_image_converter.core.formats import (
        get_output_format_info, get_quality_preset, OUTPUT_FORMATS,
    )

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}. Use --overwrite.")

    fmt_info = get_output_format_info(output_format)

    img = Image.open(input_path)
    input_info = {
        "format": img.format,
        "mode": img.mode,
        "width": img.width,
        "height": img.height,
    }

    # Handle resize
    if width or height:
        new_w = width or img.width
        new_h = height or img.height
        if keep_aspect:
            if width and height:
                img.thumbnail((new_w, new_h), Image.LANCZOS)
            elif width:
                ratio = width / img.width
                new_h = int(img.height * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
            elif height:
                ratio = height / img.height
                new_w = int(img.width * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
        else:
            img = img.resize((new_w, new_h), Image.LANCZOS)

    # Build save params
    save_params = dict(fmt_info["default_params"])

    if quality:
        qp = get_quality_preset(quality)
        for k, v in qp.items():
            save_params[k] = v

    save_params.update(extra_params)

    # Handle alpha channel for formats that don't support it
    pillow_fmt = fmt_info["pillow_format"]
    if not fmt_info["alpha_support"] and img.mode in ("RGBA", "LA", "P"):
        if img.mode == "P":
            img = img.convert("RGBA")
        if pillow_fmt in ("JPEG",):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert("RGB")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    img.save(output_path, format=pillow_fmt, **save_params)
    img.close()

    result = {
        "input": os.path.abspath(input_path),
        "output": os.path.abspath(output_path),
        "input_format": input_info["format"],
        "output_format": pillow_fmt,
        "input_size": f"{input_info['width']}x{input_info['height']}",
        "output_size": f"{img.width if 'img' in dir() else '?'}x{img.height if 'img' in dir() else '?'}",
        "file_size": os.path.getsize(output_path),
        "file_size_human": _human_size(os.path.getsize(output_path)),
        "resized": bool(width or height),
    }

    # Get actual output dimensions
    with Image.open(output_path) as out_img:
        result["output_size"] = f"{out_img.width}x{out_img.height}"

    return result


def batch_convert(
    input_paths: list,
    output_dir: str,
    output_format: str,
    quality: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_aspect: bool = True,
    overwrite: bool = False,
    prefix: str = "",
    suffix: str = "",
):
    """Batch convert multiple images.

    Returns:
        dict with summary and list of per-file results.
    """
    from cli_anything.universal_image_converter.core.formats import OUTPUT_FORMATS

    fmt_key = output_format.lower().lstrip(".")
    ext = OUTPUT_FORMATS[fmt_key]["ext"]

    os.makedirs(output_dir, exist_ok=True)

    results = []
    succeeded = 0
    skipped = 0
    failed = 0

    for path in input_paths:
        try:
            basename = os.path.splitext(os.path.basename(path))[0]
            out_name = f"{prefix}{basename}{suffix}{ext}"
            out_path = os.path.join(output_dir, out_name)

            if not overwrite and os.path.exists(out_path):
                results.append({
                    "input": path,
                    "output": out_path,
                    "status": "skipped",
                    "reason": "Output file exists (use --overwrite)",
                })
                skipped += 1
                continue

            result = convert_image(
                path, out_path, output_format,
                quality=quality, width=width, height=height,
                keep_aspect=keep_aspect, overwrite=overwrite,
            )
            result["status"] = "converted"
            results.append(result)
            succeeded += 1

        except Exception as e:
            results.append({
                "input": path,
                "status": "failed",
                "error": str(e),
            })
            failed += 1

    return {
        "total": len(input_paths),
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "output_dir": os.path.abspath(output_dir),
        "output_format": output_format,
        "results": results,
    }


def _human_size(nbytes: int) -> str:
    """Convert byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"
