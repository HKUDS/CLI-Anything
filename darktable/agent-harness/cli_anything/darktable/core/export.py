"""Darktable CLI — Export module with presets."""

import os
from typing import Dict, Any, Optional
from cli_anything.darktable.core.process import export_raw

EXPORT_PRESETS = {
    "jpeg-high": {"format": "JPEG", "ext": ".jpg", "quality": 95},
    "jpeg-medium": {"format": "JPEG", "ext": ".jpg", "quality": 80},
    "jpeg-low": {"format": "JPEG", "ext": ".jpg", "quality": 60},
    "png": {"format": "PNG", "ext": ".png", "quality": None},
    "tiff": {"format": "TIFF", "ext": ".tiff", "quality": None},
    "webp": {"format": "WEBP", "ext": ".webp", "quality": 85},
}


def list_presets():
    return [
        {"name": n, **{k: v for k, v in p.items()}} for n, p in EXPORT_PRESETS.items()
    ]


def get_preset_info(name: str) -> Dict[str, Any]:
    if name not in EXPORT_PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    return {"name": name, **EXPORT_PRESETS[name]}


def render(
    input_path: str,
    output_path: str,
    preset: str = "jpeg-high",
    quality: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    if preset not in EXPORT_PRESETS:
        raise ValueError(
            f"Unknown preset: {preset}. Available: {list(EXPORT_PRESETS.keys())}"
        )
    p = EXPORT_PRESETS[preset]
    q = quality if quality is not None else p.get("quality")
    return export_raw(input_path, output_path, quality=q, **kwargs)
