"""Krita CLI — Export module with presets."""

import os
from typing import Dict, Any, Optional
from cli_anything.krita.core.canvas import export_file as _export

EXPORT_PRESETS = {
    "png": {"format": "PNG", "ext": ".png"},
    "jpeg-high": {"format": "JPEG", "ext": ".jpg", "quality": 95},
    "jpeg-medium": {"format": "JPEG", "ext": ".jpg", "quality": 80},
    "tiff": {"format": "TIFF", "ext": ".tiff"},
    "psd": {"format": "PSD", "ext": ".psd"},
    "pdf": {"format": "PDF", "ext": ".pdf"},
}


def list_presets():
    return [{"name": n, **p} for n, p in EXPORT_PRESETS.items()]


def get_preset_info(name: str) -> Dict[str, Any]:
    if name not in EXPORT_PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    return {"name": name, **EXPORT_PRESETS[name]}


def render(
    input_path: str, output_path: str, preset: str = "png", **kwargs
) -> Dict[str, Any]:
    if preset not in EXPORT_PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    return _export(input_path, output_path, **kwargs)
