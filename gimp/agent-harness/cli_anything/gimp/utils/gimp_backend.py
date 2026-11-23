"""GIMP backend — invoke GIMP in batch mode for image processing.

Uses GIMP's Script-Fu batch mode for true image processing.

Requires: gimp (system package)
    apt install gimp
"""

import os
import re
import shutil
import subprocess
from typing import Dict, Any, Optional, List


def _script_fu_escape(value: str) -> str:
    """Escape a Python string for safe use inside Script-Fu double quotes."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def _layer_new(
    width: int, height: int, img_type: str, name: str,
    opacity: int, blend: str, gimp3: bool,
) -> str:
    """Return the gimp-layer-new call for the running GIMP version.

    GIMP 3 moved the layer name to the second argument.
    """
    safe_name = _script_fu_escape(name)
    if gimp3:
        return f'(car (gimp-layer-new image "{safe_name}" {width} {height} {img_type} {opacity} {blend}))'
    return f'(car (gimp-layer-new image {width} {height} {img_type} "{safe_name}" {opacity} {blend}))'


def find_gimp() -> str:
    """Find the GIMP executable. Raises RuntimeError if not found."""
    for name in ("gimp", "gimp-3.0", "gimp-3", "gimp-2.10", "gimp-2.99"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(
        "GIMP is not installed. Install it with:\n"
        "  apt install gimp   # Debian/Ubuntu"
    )


def get_version() -> str:
    """Get the installed GIMP version string."""
    gimp = find_gimp()
    result = subprocess.run(
        [gimp, "--version"],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


_gimp_major: Optional[int] = None


def get_major_version() -> int:
    """Return the installed GIMP major version, or 0 when it cannot be parsed."""
    global _gimp_major
    if _gimp_major is None:
        match = re.search(r"version\s+(\d+)", get_version())
        _gimp_major = int(match.group(1)) if match else 0
    return _gimp_major


def batch_script_fu(
    script: str,
    timeout: int = 120,
    gimp3: Optional[bool] = None,
) -> dict:
    """Run a Script-Fu command in GIMP batch mode.

    Args:
        script: Script-Fu command string (single-quoted safe)
        timeout: Maximum seconds to wait
        gimp3: Override GIMP 3 detection (used by tests)

    Returns:
        Dict with stdout, stderr, return code
    """
    gimp = find_gimp()
    if gimp3 is None:
        gimp3 = get_major_version() >= 3

    # GIMP 3 needs a named interpreter when several batch interpreters are
    # installed, and --quit still exits after a failing command instead of
    # waiting forever. GIMP 2.10 defaults to the same interpreter.
    cmd = [gimp, "-i", "--batch-interpreter=plug-in-script-fu-eval"]
    if gimp3:
        cmd.append("--quit")
    cmd += ["-b", script, "-b", "(gimp-quit 0)"]

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


_FMT_BY_EXT = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".bmp": "BMP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".gif": "GIF",
}


def _export_statements(
    fmt: str,
    safe_path: str,
    gimp3: bool,
    drawable: str = "drawable",
    quality: float = 0.85,
    compression: int = 6,
) -> List[str]:
    """Return Script-Fu statements that export the current image.

    GIMP 3 dropped the GIMP 2 save procedures and their drawable argument.
    The *-export procedures take the image plus a NULL options object (-1).
    """
    q = f"{quality:.2f}"

    if gimp3:
        calls = {
            "PNG": (
                f'(file-png-export RUN-NONINTERACTIVE image "{safe_path}" -1 '
                f'FALSE {compression} TRUE TRUE TRUE TRUE TRUE FALSE "auto" FALSE)'
            ),
            "JPEG": (
                f'(file-jpeg-export RUN-NONINTERACTIVE image "{safe_path}" -1 '
                f'{q} 0.0 FALSE FALSE FALSE "sub-sampling-1x1" TRUE 0 "integer" FALSE)'
            ),
            "BMP": f'(file-bmp-export RUN-NONINTERACTIVE image "{safe_path}" -1 FALSE FALSE "rgb-888")',
            "TIFF": (
                f'(file-tiff-export RUN-NONINTERACTIVE image "{safe_path}" -1 '
                f'FALSE "lzw" FALSE FALSE FALSE FALSE FALSE FALSE FALSE FALSE)'
            ),
            "GIF": f'(file-gif-export RUN-NONINTERACTIVE image "{safe_path}" -1)',
        }
        if fmt not in calls:
            raise ValueError(f"GIMP 3 export is not implemented for format: {fmt}")
        return [calls[fmt]]

    calls = {
        "PNG": f'(file-png-save RUN-NONINTERACTIVE image {drawable} "{safe_path}" "{safe_path}" 0 {compression} 1 1 1 1 1)',
        "JPEG": f'(file-jpeg-save RUN-NONINTERACTIVE image {drawable} "{safe_path}" "{safe_path}" {q} 0.0 0 0 "" 0 1 0 2)',
        "BMP": f'(file-bmp-save RUN-NONINTERACTIVE image {drawable} "{safe_path}" "{safe_path}" 0)',
        "TIFF": f'(file-tiff-save RUN-NONINTERACTIVE image {drawable} "{safe_path}" "{safe_path}" 1)',
        "GIF": f'(file-gif-save RUN-NONINTERACTIVE image {drawable} "{safe_path}" "{safe_path}" 0 0 0 0)',
    }
    if fmt not in calls:
        return [
            f'(gimp-file-overwrite RUN-NONINTERACTIVE image {drawable} "{safe_path}" "{safe_path}")'
        ]
    if fmt == "GIF":
        return [
            '(gimp-image-convert-indexed image CONVERT-DITHER-TYPE-NO-DITHER '
            'CONVERT-PALETTE-TYPE-GENERATE 256 FALSE FALSE "")',
            calls["GIF"],
        ]
    return [calls[fmt]]


def create_and_export(
    width: int,
    height: int,
    output_path: str,
    fill_color: str = "white",
    timeout: int = 120,
) -> dict:
    """Create a new image in GIMP and export it."""
    find_gimp()
    gimp3 = get_major_version() >= 3

    abs_output = os.path.abspath(output_path)
    safe_abs_output = _script_fu_escape(abs_output)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    ext = os.path.splitext(output_path)[1].lower()
    fmt = _FMT_BY_EXT.get(ext)
    if fmt is None and gimp3:
        raise ValueError(f"GIMP 3 export is not implemented for extension: {ext or '(none)'}")

    # Color mapping
    color_map = {
        "white": "255 255 255",
        "black": "0 0 0",
        "red": "255 0 0",
        "green": "0 255 0",
        "blue": "0 0 255",
    }
    rgb = color_map.get(fill_color, "255 255 255")

    export = " ".join(
        _export_statements(fmt or "UNKNOWN", safe_abs_output, gimp3, drawable="layer")
    )

    # Build Script-Fu — use plain strings, subprocess handles quoting
    script = (
        f'(let* ('
        f'(image (car (gimp-image-new {width} {height} RGB)))'
        f'(layer {_layer_new(width, height, "RGB-IMAGE", "BG", 100, "LAYER-MODE-NORMAL", gimp3)})'
        f')'
        f'(gimp-image-insert-layer image layer 0 -1)'
        f"(gimp-context-set-foreground '({rgb}))"
        f'(gimp-drawable-edit-fill layer FILL-FOREGROUND)'
        f'{export}'
        f'(gimp-image-delete image))'
    )

    result = batch_script_fu(script, timeout=timeout, gimp3=gimp3)

    if not os.path.exists(abs_output):
        raise RuntimeError(
            f"GIMP export produced no output file.\n"
            f"  Expected: {abs_output}\n"
            f"  stderr: {result['stderr'][-500:]}\n"
            f"  stdout: {result['stdout'][-500:]}"
        )

    return {
        "output": abs_output,
        "format": ext.lstrip("."),
        "method": "gimp-batch",
        "gimp_version": get_version(),
        "file_size": os.path.getsize(abs_output),
    }


def apply_filter_and_export(
    input_path: str,
    output_path: str,
    script_fu_filter: str = "",
    timeout: int = 120,
) -> dict:
    """Load an image in GIMP, apply a Script-Fu filter, and export.

    Args:
        input_path: Path to input image
        output_path: Path for output image
        script_fu_filter: Script-Fu commands to apply (uses 'image' and 'drawable' vars)
        timeout: Max seconds
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    gimp3 = get_major_version() >= 3
    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    safe_abs_input = _script_fu_escape(abs_input)
    safe_abs_output = _script_fu_escape(abs_output)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    ext = os.path.splitext(output_path)[1].lower()
    fmt = _FMT_BY_EXT.get(ext)
    if fmt is None and gimp3:
        raise ValueError(f"GIMP 3 export is not implemented for extension: {ext or '(none)'}")

    # GIMP 3 takes a single file argument; 2.10 also wants the raw filename
    load_args = (
        f'"{safe_abs_input}"'
        if gimp3
        else f'"{safe_abs_input}" "{safe_abs_input}"'
    )
    export = " ".join(
        _export_statements(fmt or "UNKNOWN", safe_abs_output, gimp3, drawable="drawable")
    )

    script = (
        f'(let* ('
        f'(image (car (gimp-file-load RUN-NONINTERACTIVE {load_args})))'
        f'(drawable (car (gimp-image-flatten image)))'
        f')'
        f'{script_fu_filter}'
        f'(set! drawable (car (gimp-image-flatten image)))'
        f'{export}'
        f'(gimp-image-delete image))'
    )

    result = batch_script_fu(script, timeout=timeout, gimp3=gimp3)

    if not os.path.exists(abs_output):
        raise RuntimeError(
            f"GIMP filter+export produced no output.\n"
            f"  stderr: {result['stderr'][-500:]}"
        )

    return {
        "output": abs_output,
        "format": ext.lstrip("."),
        "method": "gimp-batch",
        "file_size": os.path.getsize(abs_output),
    }


# ---------------------------------------------------------------------------
# GIMP availability check
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Return True if GIMP is installed and reachable on $PATH."""
    try:
        find_gimp()
        return True
    except RuntimeError:
        return False


# ---------------------------------------------------------------------------
# Blend-mode & filter maps  (CLI name → GIMP 2.10+ Script-Fu constant/call)
# ---------------------------------------------------------------------------

GIMP_BLEND_MODES: Dict[str, str] = {
    "normal":        "LAYER-MODE-NORMAL",
    "multiply":      "LAYER-MODE-MULTIPLY",
    "screen":        "LAYER-MODE-SCREEN",
    "overlay":       "LAYER-MODE-OVERLAY",
    "soft_light":    "LAYER-MODE-SOFTLIGHT",
    "hard_light":    "LAYER-MODE-HARDLIGHT",
    "difference":    "LAYER-MODE-DIFFERENCE",
    "darken":        "LAYER-MODE-DARKEN-ONLY",
    "lighten":       "LAYER-MODE-LIGHTEN-ONLY",
    "color_dodge":   "LAYER-MODE-DODGE",
    "color_burn":    "LAYER-MODE-BURN",
    "addition":      "LAYER-MODE-ADDITION",
    "subtract":      "LAYER-MODE-SUBTRACT",
    "grain_merge":   "LAYER-MODE-GRAIN-MERGE",
    "grain_extract": "LAYER-MODE-GRAIN-EXTRACT",
}

# Export-preset → Script-Fu save call.  Placeholders: {img}, {drw}, {path}
_EXPORT_COMMANDS: Dict[str, str] = {
    "PNG":  '(file-png-save RUN-NONINTERACTIVE {img} {drw} "{path}" "{path}" 0 {compress} 1 1 1 1 1)',
    "JPEG": '(file-jpeg-save RUN-NONINTERACTIVE {img} {drw} "{path}" "{path}" {quality} 0.0 0 0 "" 0 1 0 2)',
    "BMP":  '(file-bmp-save RUN-NONINTERACTIVE {img} {drw} "{path}" "{path}" 0)',
    "TIFF": '(file-tiff-save RUN-NONINTERACTIVE {img} {drw} "{path}" "{path}" 1)',
    "GIF":  '(file-gif-save RUN-NONINTERACTIVE {img} {drw} "{path}" "{path}" 0 0 0 0)',
}


def _filter_to_script_fu(name: str, params: Dict[str, Any],
                          img_var: str, drw_var: str,
                          gimp3: bool = False) -> Optional[str]:
    """Convert a CLI filter name + params into a Script-Fu expression.

    Returns None when there is no GIMP-native equivalent for *name*.
    """
    p = params or {}
    i, d = img_var, drw_var

    if name == "brightness":
        factor = p.get("factor", 1.0) - 1.0
        if gimp3:
            return f"(gimp-drawable-brightness-contrast {d} {factor:.3f} 0)"
        val = int(factor * 127)
        return f"(gimp-brightness-contrast {d} {val} 0)"
    if name == "contrast":
        factor = p.get("factor", 1.0) - 1.0
        if gimp3:
            return f"(gimp-drawable-brightness-contrast {d} 0 {factor:.3f})"
        val = int(factor * 127)
        return f"(gimp-brightness-contrast {d} 0 {val})"
    if name == "saturation":
        val = int((p.get("factor", 1.0) - 1.0) * 100)
        return f"(gimp-drawable-hue-saturation {d} HUE-RANGE-ALL 0 0 {val} 0)"
    if name == "sharpness":
        amt = max(0.0, p.get("factor", 1.0) - 1.0)
        return f"(plug-in-unsharp-mask RUN-NONINTERACTIVE {i} {d} 3.0 {amt:.2f} 0)"
    if name == "gaussian_blur":
        r = p.get("radius", 2.0)
        return f"(plug-in-gauss RUN-NONINTERACTIVE {i} {d} {r} {r} 0)"
    if name == "box_blur":
        r = p.get("radius", 2.0)
        return f"(plug-in-gauss RUN-NONINTERACTIVE {i} {d} {r} {r} 1)"
    if name == "unsharp_mask":
        r = p.get("radius", 2.0)
        pct = p.get("percent", 150) / 100.0
        t = p.get("threshold", 3)
        return f"(plug-in-unsharp-mask RUN-NONINTERACTIVE {i} {d} {r} {pct:.2f} {t})"
    if name == "smooth":
        return f"(plug-in-gauss RUN-NONINTERACTIVE {i} {d} 3 3 0)"
    if name == "invert":
        return f"(gimp-drawable-invert {d} FALSE)"
    if name == "grayscale":
        return f"(gimp-drawable-desaturate {d} DESATURATE-AVERAGE)"
    if name == "posterize":
        bits = p.get("bits", 4)
        return f"(gimp-drawable-posterize {d} {bits})"
    if name == "equalize":
        return f"(gimp-drawable-equalize {d} FALSE)"
    if name == "autocontrast":
        return f"(gimp-drawable-levels {d} HISTOGRAM-VALUE 0.0 1.0 FALSE 1.0 0.0 1.0 FALSE)"
    if name == "find_edges":
        return f"(plug-in-edge RUN-NONINTERACTIVE {i} {d} 1 0 0)"
    if name == "emboss":
        return f"(plug-in-emboss RUN-NONINTERACTIVE {i} {d} 315.0 45.0 7 TRUE)"
    if name == "contour":
        return f"(plug-in-edge RUN-NONINTERACTIVE {i} {d} 1 0 0)"
    if name == "detail":
        return f"(plug-in-unsharp-mask RUN-NONINTERACTIVE {i} {d} 3.0 0.3 0)"
    if name == "sepia":
        return f"(gimp-drawable-desaturate {d} DESATURATE-AVERAGE) (gimp-drawable-colorize-hsl {d} 35 40 0)"
    if name == "solarize":
        t = p.get("threshold", 128) / 255.0
        return f"(gimp-drawable-threshold {d} HISTOGRAM-VALUE {t:.3f} 1.0)"
    if name == "rotate":
        angle = p.get("angle", 0.0) * 0.017453292519943295  # deg→rad
        return f"(gimp-item-transform-rotate-default {d} {angle:.6f} TRUE 0 0)"
    if name == "flip_h":
        return f"(gimp-item-transform-flip-simple {d} ORIENTATION-HORIZONTAL TRUE 0)"
    if name == "flip_v":
        return f"(gimp-item-transform-flip-simple {d} ORIENTATION-VERTICAL TRUE 0)"
    if name == "resize":
        w = p.get("width", 100)
        h = p.get("height", 100)
        return f"(gimp-layer-scale {d} {w} {h} TRUE)"
    if name == "crop":
        l, t_, r, b = p.get("left", 0), p.get("top", 0), p.get("right", 0), p.get("bottom", 0)
        new_w, new_h = r - l, b - t_
        if new_w > 0 and new_h > 0:
            return (f"(gimp-layer-resize {d} {new_w} {new_h} {-l} {-t_})"
                    f" (gimp-layer-flatten-image {i})")
        return None

    return None


def _hex_to_rgb(color: str) -> str:
    """'#rrggbb' → 'r g b' (space-separated decimal) for Script-Fu palettes."""
    c = color.lstrip("#")
    if len(c) == 6:
        return f"{int(c[0:2], 16)} {int(c[2:4], 16)} {int(c[4:6], 16)}"
    return "255 255 255"


_NAMED_COLORS = {
    "white": "255 255 255", "black": "0 0 0",
    "red": "255 0 0", "green": "0 255 0", "blue": "0 0 255",
}


# ---------------------------------------------------------------------------
# Full-project rendering via GIMP Script-Fu
# ---------------------------------------------------------------------------

def _render_script(
    project: Dict[str, Any],
    safe_output: str,
    fmt: str,
    preset: str,
    quality: Optional[int],
    gimp3: bool,
) -> str:
    """Build the Script-Fu expression that renders a whole project."""
    from cli_anything.gimp.core.export import EXPORT_PRESETS

    canvas = project["canvas"]
    cw, ch = canvas["width"], canvas["height"]
    bg_color = canvas.get("background", "#ffffff")

    # --- build Script-Fu ---
    s = []
    s.append(f"(let* ((image (car (gimp-image-new {cw} {ch} RGB))))")

    # Background layer
    if bg_color.lower() != "transparent":
        rgb = _NAMED_COLORS.get(bg_color.lower(), _hex_to_rgb(bg_color))
        bg = _layer_new(cw, ch, "RGB-IMAGE", "Background", 100, "LAYER-MODE-NORMAL", gimp3)
        s.append(f"(let* ((bg {bg}))")
        s.append("(gimp-image-insert-layer image bg 0 -1)")
        s.append(f"(gimp-context-set-foreground '({rgb}))")
        s.append("(gimp-drawable-edit-fill bg FILL-FOREGROUND))")

    # Composite layers bottom → top
    layers = project.get("layers", [])
    for idx, layer in enumerate(reversed(layers)):
        if not layer.get("visible", True):
            continue
        _build_layer_script(s, layer, idx, cw, ch, gimp3)

    if fmt == "JPEG":
        quality = quality or EXPORT_PRESETS.get(preset, {}).get("params", {}).get("quality", 85)
    else:
        quality = 85
    compression = EXPORT_PRESETS.get(preset, {}).get("params", {}).get("compress_level", 6)

    # Flatten and export
    s.append("(let* ((drawable (car (gimp-image-flatten image))))")
    s.extend(_export_statements(
        fmt, safe_output, gimp3,
        quality=quality / 100.0, compression=compression,
    ))
    s.append(")")

    # Cleanup
    s.append("(gimp-image-delete image))")  # closes outer let*

    return " ".join(s)


def render_project(
    project: Dict[str, Any],
    output_path: str,
    preset: str = "png",
    overwrite: bool = False,
    quality: Optional[int] = None,
    format_override: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """Render a complete GIMP CLI project using GIMP's Script-Fu batch mode.

    Builds a single Script-Fu expression that creates the canvas, inserts all
    visible layers with their blend modes / opacities / filters, flattens the
    image, and exports to the requested format.
    """
    from cli_anything.gimp.core.export import EXPORT_PRESETS

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}. Use --overwrite.")

    abs_output = os.path.abspath(output_path).replace("\\", "/")
    safe_output = _script_fu_escape(abs_output)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    canvas = project["canvas"]
    cw, ch = canvas["width"], canvas["height"]

    if format_override:
        fmt = format_override.upper()
    elif preset in EXPORT_PRESETS:
        fmt = EXPORT_PRESETS[preset]["format"]
    else:
        raise ValueError(f"Unknown preset: {preset}")

    gimp3 = get_major_version() >= 3
    script = _render_script(project, safe_output, fmt, preset, quality, gimp3)
    result = batch_script_fu(script, timeout=timeout, gimp3=gimp3)

    if not os.path.exists(abs_output):
        raise RuntimeError(
            f"GIMP rendering produced no output file.\n"
            f"  Expected: {abs_output}\n"
            f"  stderr: {result['stderr'][-500:]}\n"
            f"  stdout: {result['stdout'][-500:]}"
        )

    file_size = os.path.getsize(abs_output)
    layers = project.get("layers", [])
    return {
        "output": abs_output,
        "format": fmt,
        "size": f"{cw}x{ch}",
        "file_size": file_size,
        "file_size_human": _human_size(file_size),
        "preset": preset,
        "method": "gimp-batch",
        "layers_rendered": sum(1 for l in layers if l.get("visible", True)),
    }


def _build_layer_script(
    s: List[str], layer: Dict[str, Any], idx: int,
    canvas_w: int, canvas_h: int, gimp3: bool = False,
) -> None:
    """Append Script-Fu expressions for a single layer."""
    var = f"l{idx}"
    ltype = layer.get("type", "image")
    opacity = int(layer.get("opacity", 1.0) * 100)
    blend = GIMP_BLEND_MODES.get(layer.get("blend_mode", "normal"), "LAYER-MODE-NORMAL")
    w = layer.get("width", canvas_w)
    h = layer.get("height", canvas_h)

    if ltype == "image" and layer.get("source") and os.path.exists(layer["source"]):
        src = _script_fu_escape(os.path.abspath(layer["source"]).replace("\\", "/"))
        s.append(f'(let* (({var} (car (gimp-file-load-layer RUN-NONINTERACTIVE image "{src}"))))')
    elif ltype == "text":
        text = _script_fu_escape(layer.get("text", ""))
        font_size = layer.get("font_size", 24)
        font = _script_fu_escape(layer.get("font", "Sans"))
        if gimp3:
            # GIMP 3 takes a font ID instead of a name and has no size type.
            s.append(
                f'(let* ((ctxfont (car (gimp-context-get-font)))'
                f'(matches (car (gimp-fonts-get-list "{font}")))'
                f'(font (if (> (vector-length matches) 0) (vector-ref matches 0) ctxfont))'
                f'({var} (car (gimp-text-font image -1 0 0 "{text}" 0 TRUE {font_size} font))))'
            )
        else:
            s.append(
                f'(let* (({var} (car (gimp-text-fontname image -1 0 0 "{text}" 0 TRUE {font_size} UNIT-PIXEL "{font}"))))'
            )
    else:
        fill = layer.get("fill", "transparent")
        img_type = "RGBA-IMAGE" if fill == "transparent" else "RGB-IMAGE"
        name = layer.get("name", f"Layer {idx}")
        s.append(f"(let* (({var} {_layer_new(w, h, img_type, name, opacity, blend, gimp3)}))")
        s.append(f"(gimp-image-insert-layer image {var} 0 -1)")
        if fill != "transparent":
            rgb = _NAMED_COLORS.get(fill, _hex_to_rgb(fill))
            s.append(f"(gimp-context-set-foreground '({rgb}))")
            s.append(f"(gimp-drawable-edit-fill {var} FILL-FOREGROUND)")

    # For file/text layers, insert into image and configure
    if ltype == "image" and layer.get("source") and os.path.exists(layer["source"]):
        s.append(f"(gimp-image-insert-layer image {var} 0 -1)")
    # Text layers are auto-inserted by gimp-text-fontname and gimp-text-font

    # Offsets
    ox, oy = layer.get("offset_x", 0), layer.get("offset_y", 0)
    if ox or oy:
        s.append(f"(gimp-layer-set-offsets {var} {ox} {oy})")

    # Opacity & blend mode (set explicitly for file/text layers)
    if ltype in ("image", "text"):
        s.append(f"(gimp-layer-set-opacity {var} {opacity})")
        s.append(f"(gimp-layer-set-mode {var} {blend})")

    # Filters
    for filt in layer.get("filters", []):
        sf = _filter_to_script_fu(filt["name"], filt.get("params", {}), "image", var, gimp3)
        if sf:
            s.append(sf)

    s.append(")")  # close this layer's let*


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"
