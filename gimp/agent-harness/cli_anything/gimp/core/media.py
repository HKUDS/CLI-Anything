"""GIMP CLI - Media file analysis module.

Uses Pillow when available for rich metadata (EXIF, histograms).  Falls back
to pure-Python header parsing for basic dimensions / format detection when
Pillow is not installed.
"""

import os
import json
import subprocess
from typing import Dict, Any, Optional


def probe_image(path: str) -> Dict[str, Any]:
    """Analyze an image file and return metadata.

    Tries Pillow for rich metadata; degrades gracefully to pure-Python
    header parsing when Pillow is absent.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image file not found: {path}")

    info: Dict[str, Any] = {
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "file_size": os.path.getsize(path),
        "file_size_human": _human_size(os.path.getsize(path)),
    }

    try:
        from PIL import Image
        return _probe_via_pillow(path, info, Image)
    except ImportError:
        pass

    return _probe_basic(path, info)


def _probe_via_pillow(path: str, info: Dict[str, Any], Image) -> Dict[str, Any]:
    """Full metadata probe using Pillow."""
    try:
        with Image.open(path) as img:
            info["width"] = img.width
            info["height"] = img.height
            info["mode"] = img.mode
            info["format"] = img.format
            info["format_description"] = img.format_description if hasattr(img, "format_description") else img.format
            info["megapixels"] = f"{img.width * img.height / 1_000_000:.2f}"

            dpi = img.info.get("dpi")
            if dpi:
                info["dpi"] = {"x": round(dpi[0]), "y": round(dpi[1])}

            info["is_animated"] = getattr(img, "is_animated", False)
            if info["is_animated"]:
                info["n_frames"] = getattr(img, "n_frames", 1)

            if img.mode == "P":
                palette = img.getpalette()
                info["palette_colors"] = len(palette) // 3 if palette else 0

            exif = img.getexif()
            if exif:
                exif_data = {}
                tag_names = {
                    271: "Make", 272: "Model", 274: "Orientation",
                    305: "Software", 306: "DateTime",
                    36867: "DateTimeOriginal", 37378: "ApertureValue",
                    33434: "ExposureTime", 34855: "ISOSpeedRatings",
                }
                for tag_id, name in tag_names.items():
                    if tag_id in exif:
                        exif_data[name] = str(exif[tag_id])
                if exif_data:
                    info["exif"] = exif_data

            info["channels"] = len(img.getbands())
            info["bands"] = list(img.getbands())

            bits_per_channel = {"1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8,
                                "CMYK": 8, "I": 32, "F": 32, "LA": 8}
            bpc = bits_per_channel.get(img.mode, 8)
            info["bits_per_pixel"] = bpc * info["channels"]

    except Exception as e:
        info["error"] = str(e)

    return info


def _probe_basic(path: str, info: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight probe using pure-Python header parsing (no Pillow)."""
    from cli_anything.gimp.core.layers import _read_image_dimensions

    dims = _read_image_dimensions(path)
    if dims:
        info["width"], info["height"] = dims
        info["megapixels"] = f"{dims[0] * dims[1] / 1_000_000:.2f}"

    ext = os.path.splitext(path)[1].lower()
    fmt_map = {
        ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
        ".gif": "GIF", ".bmp": "BMP", ".webp": "WEBP",
        ".tiff": "TIFF", ".tif": "TIFF",
    }
    info["format"] = fmt_map.get(ext, ext.lstrip(".").upper())
    return info


def list_media_in_project(project: Dict[str, Any]) -> list:
    """List all media files referenced in the project."""
    media = []
    for i, layer in enumerate(project.get("layers", [])):
        source = layer.get("source")
        if source:
            exists = os.path.exists(source)
            media.append({
                "layer_index": i,
                "layer_name": layer.get("name", f"Layer {i}"),
                "source": source,
                "exists": exists,
            })
    return media


def check_media(project: Dict[str, Any]) -> Dict[str, Any]:
    """Check that all referenced media files exist."""
    media = list_media_in_project(project)
    missing = [m for m in media if not m["exists"]]
    return {
        "total": len(media),
        "found": len(media) - len(missing),
        "missing": len(missing),
        "missing_files": [m["source"] for m in missing],
        "status": "ok" if not missing else "missing_files",
    }


def get_image_histogram(path: str) -> Dict[str, Any]:
    """Get histogram data for an image.  Requires Pillow."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image file not found: {path}")

    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "Histogram analysis requires Pillow.  Install it with:\n"
            "  pip install Pillow"
        )

    with Image.open(path) as img:
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")

        hist = img.histogram()

        if img.mode in ("RGB", "RGBA"):
            r_hist = hist[0:256]
            g_hist = hist[256:512]
            b_hist = hist[512:768]
            return {
                "mode": img.mode,
                "channels": {
                    "red": {"min": _first_nonzero(r_hist), "max": _last_nonzero(r_hist),
                            "mean": _hist_mean(r_hist)},
                    "green": {"min": _first_nonzero(g_hist), "max": _last_nonzero(g_hist),
                              "mean": _hist_mean(g_hist)},
                    "blue": {"min": _first_nonzero(b_hist), "max": _last_nonzero(b_hist),
                             "mean": _hist_mean(b_hist)},
                },
            }
        else:
            return {
                "mode": img.mode,
                "channels": {
                    "luminance": {"min": _first_nonzero(hist), "max": _last_nonzero(hist),
                                  "mean": _hist_mean(hist)},
                },
            }


def _human_size(nbytes: int) -> str:
    """Convert byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def _first_nonzero(hist: list) -> int:
    for i, v in enumerate(hist):
        if v > 0:
            return i
    return 0


def _last_nonzero(hist: list) -> int:
    for i in range(len(hist) - 1, -1, -1):
        if hist[i] > 0:
            return i
    return 0


def _hist_mean(hist: list) -> float:
    total = sum(hist)
    if total == 0:
        return 0.0
    weighted = sum(i * v for i, v in enumerate(hist))
    return round(weighted / total, 1)
