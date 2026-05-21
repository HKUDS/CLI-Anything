"""Universal Image Converter — Format registry and supported format info."""

# Pillow-supported formats for reading and writing
# Source: gimp/agent-harness/cli_anything/gimp/core/export.py EXPORT_PRESETS

INPUT_FORMATS = {
    "png":  {"mime": "image/png",  "lossless": True,  "alpha": True},
    "jpg":  {"mime": "image/jpeg", "lossless": False, "alpha": False},
    "jpeg": {"mime": "image/jpeg", "lossless": False, "alpha": False},
    "webp": {"mime": "image/webp", "lossless": True,  "alpha": True},
    "tiff": {"mime": "image/tiff", "lossless": True,  "alpha": True},
    "tif":  {"mime": "image/tiff", "lossless": True,  "alpha": True},
    "bmp":  {"mime": "image/bmp",  "lossless": True,  "alpha": False},
    "ico":  {"mime": "image/x-icon", "lossless": True, "alpha": True},
    "gif":  {"mime": "image/gif",  "lossless": True,  "alpha": True},
    "heic": {"mime": "image/heic", "lossless": False, "alpha": False},
    "heif": {"mime": "image/heif", "lossless": False, "alpha": False},
}

OUTPUT_FORMATS = {
    "png":  {"ext": ".png",  "pillow_fmt": "PNG",  "lossless": True,  "alpha": True,
             "params": {"compress_level": 6}},
    "jpg":  {"ext": ".jpg",  "pillow_fmt": "JPEG", "lossless": False, "alpha": False,
             "params": {"quality": 92, "optimize": True}},
    "jpeg": {"ext": ".jpg",  "pillow_fmt": "JPEG", "lossless": False, "alpha": False,
             "params": {"quality": 92, "optimize": True}},
    "webp": {"ext": ".webp", "pillow_fmt": "WEBP", "lossless": True,  "alpha": True,
             "params": {"quality": 85}},
    "tiff": {"ext": ".tiff", "pillow_fmt": "TIFF", "lossless": True,  "alpha": True,
             "params": {"compression": "tiff_lzw"}},
    "bmp":  {"ext": ".bmp",  "pillow_fmt": "BMP",  "lossless": True,  "alpha": False,
             "params": {}},
    "ico":  {"ext": ".ico",  "pillow_fmt": "ICO",  "lossless": True,  "alpha": True,
             "params": {}},
    "gif":  {"ext": ".gif",  "pillow_fmt": "GIF",  "lossless": True,  "alpha": True,
             "params": {}},
}

QUALITY_PRESETS = {
    "lossless": {"compress_level": 0, "quality": 100, "lossless": True},
    "high":     {"compress_level": 3, "quality": 92},
    "medium":   {"compress_level": 6, "quality": 80},
    "low":      {"compress_level": 9, "quality": 50},
}


def list_input_formats():
    """List all supported input formats."""
    return [
        {"format": k, "mime": v["mime"], "lossless": v["lossless"], "alpha": v["alpha"]}
        for k, v in INPUT_FORMATS.items()
    ]


def list_output_formats():
    """List all supported output formats."""
    return [
        {"format": k, "extension": v["ext"], "lossless": v["lossless"], "alpha": v["alpha"]}
        for k, v in OUTPUT_FORMATS.items()
    ]


def get_output_format_info(fmt: str):
    """Get details about an output format."""
    key = fmt.lower().lstrip(".")
    if key not in OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {fmt}. Available: {list(OUTPUT_FORMATS.keys())}")
    f = OUTPUT_FORMATS[key]
    return {
        "format": key,
        "extension": f["ext"],
        "pillow_format": f["pillow_fmt"],
        "lossless": f["lossless"],
        "alpha_support": f["alpha"],
        "default_params": f["params"],
    }


def get_quality_preset(name: str):
    """Get quality preset parameters."""
    if name not in QUALITY_PRESETS:
        raise ValueError(f"Unknown quality preset: {name}. Available: {list(QUALITY_PRESETS.keys())}")
    return dict(QUALITY_PRESETS[name])


def list_quality_presets():
    """List all quality presets."""
    return [{"name": k, "params": v} for k, v in QUALITY_PRESETS.items()]
