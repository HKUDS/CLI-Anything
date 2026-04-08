"""GIMP backend — invoke GIMP in batch mode for image processing.

Uses GIMP's Script-Fu batch mode for true image processing.

Requires: gimp (system package)
    apt install gimp
"""

import os
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


def find_gimp() -> str:
    """Find the GIMP executable. Raises RuntimeError if not found."""
    for name in ("gimp", "gimp-2.10", "gimp-2.99"):
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


def batch_script_fu(
    script: str,
    timeout: int = 120,
) -> dict:
    """Run a Script-Fu command in GIMP batch mode.

    Args:
        script: Script-Fu command string (single-quoted safe)
        timeout: Maximum seconds to wait

    Returns:
        Dict with stdout, stderr, return code
    """
    gimp = find_gimp()
    cmd = [gimp, "-i", "-b", script, "-b", "(gimp-quit 0)"]

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


def create_and_export(
    width: int,
    height: int,
    output_path: str,
    fill_color: str = "white",
    timeout: int = 120,
) -> dict:
    """Create a new image in GIMP and export it."""
    abs_output = os.path.abspath(output_path)
    safe_abs_output = _script_fu_escape(abs_output)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    ext = os.path.splitext(output_path)[1].lower()

    # Build the export command based on format
    if ext == ".png":
        export_cmd = (
            f'(file-png-save RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}" 0 9 1 1 1 1 1)'
        )
    elif ext in (".jpg", ".jpeg"):
        export_cmd = (
            f'(file-jpeg-save RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}" 0.85 0.0 0 0 "" 0 1 0 2)'
        )
    elif ext == ".bmp":
        export_cmd = (
            f'(file-bmp-save RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}" 0)'
        )
    else:
        export_cmd = (
            f'(gimp-file-overwrite RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}")'
        )

    # Color mapping
    color_map = {
        "white": "255 255 255",
        "black": "0 0 0",
        "red": "255 0 0",
        "green": "0 255 0",
        "blue": "0 0 255",
    }
    rgb = color_map.get(fill_color, "255 255 255")

    # Build Script-Fu — use plain strings, subprocess handles quoting
    script = (
        f'(let* ('
        f'(image (car (gimp-image-new {width} {height} RGB)))'
        f'(layer (car (gimp-layer-new image {width} {height} '
        f'RGB-IMAGE "BG" 100 LAYER-MODE-NORMAL)))'
        f')'
        f'(gimp-image-insert-layer image layer 0 -1)'
        f'(gimp-image-set-active-layer image layer)'
        f"(gimp-palette-set-foreground '({rgb}))"
        f'(gimp-edit-fill layer FILL-FOREGROUND)'
        f'{export_cmd}'
        f'(gimp-image-delete image))'
    )

    result = batch_script_fu(script, timeout=timeout)

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

    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    safe_abs_input = _script_fu_escape(abs_input)
    safe_abs_output = _script_fu_escape(abs_output)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".png":
        export_cmd = (
            f'(file-png-save RUN-NONINTERACTIVE image drawable '
            f'"{safe_abs_output}" "{safe_abs_output}" 0 9 1 1 1 1 1)'
        )
    elif ext in (".jpg", ".jpeg"):
        export_cmd = (
            f'(file-jpeg-save RUN-NONINTERACTIVE image drawable '
            f'"{safe_abs_output}" "{safe_abs_output}" 0.85 0.0 0 0 "" 0 1 0 2)'
        )
    else:
        export_cmd = (
            f'(gimp-file-overwrite RUN-NONINTERACTIVE image drawable '
            f'"{safe_abs_output}" "{safe_abs_output}")'
        )

    script = (
        f'(let* ('
        f'(image (car (gimp-file-load RUN-NONINTERACTIVE "{safe_abs_input}" "{safe_abs_input}")))'
        f'(drawable (car (gimp-image-flatten image)))'
        f')'
        f'{script_fu_filter}'
        f'(set! drawable (car (gimp-image-flatten image)))'
        f'{export_cmd}'
        f'(gimp-image-delete image))'
    )

    result = batch_script_fu(script, timeout=timeout)

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
                          img_var: str, drw_var: str) -> Optional[str]:
    """Convert a CLI filter name + params into a Script-Fu expression.

    Returns None when there is no GIMP-native equivalent for *name*.
    """
    p = params or {}
    i, d = img_var, drw_var

    if name == "brightness":
        val = int((p.get("factor", 1.0) - 1.0) * 127)
        return f"(gimp-brightness-contrast {d} {val} 0)"
    if name == "contrast":
        val = int((p.get("factor", 1.0) - 1.0) * 127)
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
    bg_color = canvas.get("background", "#ffffff")

    if format_override:
        fmt = format_override.upper()
    elif preset in EXPORT_PRESETS:
        fmt = EXPORT_PRESETS[preset]["format"]
    else:
        raise ValueError(f"Unknown preset: {preset}")

    # --- build Script-Fu ---
    s = []
    s.append(f"(let* ((image (car (gimp-image-new {cw} {ch} RGB))))")

    # Background layer
    if bg_color.lower() != "transparent":
        rgb = _NAMED_COLORS.get(bg_color.lower(), _hex_to_rgb(bg_color))
        s.append(f"(let* ((bg (car (gimp-layer-new image {cw} {ch} RGB-IMAGE \"Background\" 100 LAYER-MODE-NORMAL))))")
        s.append(f"(gimp-image-insert-layer image bg 0 -1)")
        s.append(f"(gimp-palette-set-foreground '({rgb}))")
        s.append(f"(gimp-edit-fill bg FILL-FOREGROUND))")

    # Composite layers bottom → top
    layers = project.get("layers", [])
    for idx, layer in enumerate(reversed(layers)):
        if not layer.get("visible", True):
            continue
        _build_layer_script(s, layer, idx, cw, ch)

    # Flatten
    s.append("(gimp-image-flatten image)")

    # Export
    _build_export_cmd(s, safe_output, fmt, preset, quality)

    # Cleanup
    s.append("(gimp-image-delete image))")  # closes outer let*

    script = " ".join(s)
    result = batch_script_fu(script, timeout=timeout)

    if not os.path.exists(abs_output):
        raise RuntimeError(
            f"GIMP rendering produced no output file.\n"
            f"  Expected: {abs_output}\n"
            f"  stderr: {result['stderr'][-500:]}\n"
            f"  stdout: {result['stdout'][-500:]}"
        )

    file_size = os.path.getsize(abs_output)
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
    canvas_w: int, canvas_h: int,
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
        s.append(
            f'(let* (({var} (car (gimp-text-fontname image -1 0 0 "{text}" 0 TRUE {font_size} UNIT-PIXEL "{font}"))))'
        )
    else:
        fill = layer.get("fill", "transparent")
        img_type = "RGBA-IMAGE" if fill == "transparent" else "RGB-IMAGE"
        name_safe = _script_fu_escape(layer.get("name", f"Layer {idx}"))
        s.append(f'(let* (({var} (car (gimp-layer-new image {w} {h} {img_type} "{name_safe}" {opacity} {blend}))))')
        s.append(f"(gimp-image-insert-layer image {var} 0 -1)")
        if fill != "transparent":
            rgb = _NAMED_COLORS.get(fill, _hex_to_rgb(fill))
            s.append(f"(gimp-palette-set-foreground '({rgb}))")
            s.append(f"(gimp-edit-fill {var} FILL-FOREGROUND)")

    # For file/text layers, insert into image and configure
    if ltype == "image" and layer.get("source") and os.path.exists(layer["source"]):
        s.append(f"(gimp-image-insert-layer image {var} 0 -1)")
    # Text layers are auto-inserted by gimp-text-fontname

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
        sf = _filter_to_script_fu(filt["name"], filt.get("params", {}), "image", var)
        if sf:
            s.append(sf)

    s.append(")")  # close this layer's let*


def _build_export_cmd(
    s: List[str], safe_path: str, fmt: str,
    preset: str, quality: Optional[int],
) -> None:
    """Append the Script-Fu export call."""
    from cli_anything.gimp.core.export import EXPORT_PRESETS

    s.append("(let* ((drawable (car (gimp-image-get-active-drawable image))))")

    if fmt == "JPEG":
        q = (quality or EXPORT_PRESETS.get(preset, {}).get("params", {}).get("quality", 85)) / 100.0
        s.append(f'(file-jpeg-save RUN-NONINTERACTIVE image drawable "{safe_path}" "{safe_path}" {q:.2f} 0.0 0 0 "" 0 1 0 2)')
    elif fmt == "PNG":
        comp = EXPORT_PRESETS.get(preset, {}).get("params", {}).get("compress_level", 6)
        s.append(f'(file-png-save RUN-NONINTERACTIVE image drawable "{safe_path}" "{safe_path}" 0 {comp} 1 1 1 1 1)')
    elif fmt == "BMP":
        s.append(f'(file-bmp-save RUN-NONINTERACTIVE image drawable "{safe_path}" "{safe_path}" 0)')
    elif fmt == "TIFF":
        s.append(f'(file-tiff-save RUN-NONINTERACTIVE image drawable "{safe_path}" "{safe_path}" 1)')
    elif fmt == "GIF":
        s.append(f"(gimp-image-convert-indexed image CONVERT-DITHER-TYPE-NO-DITHER CONVERT-PALETTE-TYPE-GENERATE 256 FALSE FALSE \"\")")
        s.append(f"(set! drawable (car (gimp-image-get-active-drawable image)))")
        s.append(f'(file-gif-save RUN-NONINTERACTIVE image drawable "{safe_path}" "{safe_path}" 0 0 0 0)')
    else:
        s.append(f'(gimp-file-overwrite RUN-NONINTERACTIVE image drawable "{safe_path}" "{safe_path}")')

    s.append(")")  # close export let*


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"
