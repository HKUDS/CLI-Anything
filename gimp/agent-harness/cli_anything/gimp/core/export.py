"""GIMP CLI - Export/rendering pipeline module.

This module handles the critical "rendering" step: flattening the layer stack
with all filters applied and exporting to various image formats.
"""

import os
from typing import Dict, Any, Optional
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont
import numpy as np


# Export presets
EXPORT_PRESETS = {
    "png": {"format": "PNG", "ext": ".png", "params": {"compress_level": 6}},
    "png-max": {"format": "PNG", "ext": ".png", "params": {"compress_level": 9}},
    "jpeg-high": {"format": "JPEG", "ext": ".jpg", "params": {"quality": 95, "subsampling": 0}},
    "jpeg-medium": {"format": "JPEG", "ext": ".jpg", "params": {"quality": 80}},
    "jpeg-low": {"format": "JPEG", "ext": ".jpg", "params": {"quality": 60}},
    "webp": {"format": "WEBP", "ext": ".webp", "params": {"quality": 85}},
    "webp-lossless": {"format": "WEBP", "ext": ".webp", "params": {"lossless": True}},
    "tiff": {"format": "TIFF", "ext": ".tiff", "params": {"compression": "lzw"}},
    "tiff-none": {"format": "TIFF", "ext": ".tiff", "params": {}},
    "bmp": {"format": "BMP", "ext": ".bmp", "params": {}},
    "gif": {"format": "GIF", "ext": ".gif", "params": {}},
    "pdf": {"format": "PDF", "ext": ".pdf", "params": {}},
    "ico": {"format": "ICO", "ext": ".ico", "params": {}},
}


def list_presets() -> list:
    """List available export presets."""
    result = []
    for name, p in EXPORT_PRESETS.items():
        result.append({
            "name": name,
            "format": p["format"],
            "extension": p["ext"],
            "params": p["params"],
        })
    return result


def get_preset_info(name: str) -> Dict[str, Any]:
    """Get details about an export preset."""
    if name not in EXPORT_PRESETS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(EXPORT_PRESETS.keys())}")
    p = EXPORT_PRESETS[name]
    return {"name": name, "format": p["format"], "extension": p["ext"], "params": p["params"]}


def render(
    project: Dict[str, Any],
    output_path: str,
    preset: str = "png",
    overwrite: bool = False,
    quality: Optional[int] = None,
    format_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Render the project: flatten layers, apply filters, export.

    This is the main rendering pipeline.
    """
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}. Use --overwrite.")

    canvas = project["canvas"]
    cw, ch = canvas["width"], canvas["height"]
    bg_color = canvas.get("background", "#ffffff")
    mode = canvas.get("color_mode", "RGB")

    # Determine output format
    if format_override:
        fmt = format_override.upper()
        save_params = {}
    elif preset in EXPORT_PRESETS:
        p = EXPORT_PRESETS[preset]
        fmt = p["format"]
        save_params = dict(p["params"])
    else:
        raise ValueError(f"Unknown preset: {preset}")

    if quality is not None:
        save_params["quality"] = quality

    # Create canvas
    if mode in ("RGBA", "LA"):
        canvas_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        # Draw background if not transparent
        if bg_color.lower() != "transparent":
            bg = Image.new("RGBA", (cw, ch), bg_color)
            canvas_img = Image.alpha_composite(canvas_img, bg)
    else:
        canvas_img = Image.new("RGB", (cw, ch), bg_color)

    layers, applied_layer_operations = _prepare_layers_for_export(project, cw, ch)

    # Composite layers bottom-to-top
    for layer in reversed(layers):
        if not layer.get("visible", True):
            continue

        layer_img = _render_layer_to_canvas(layer, cw, ch)
        if layer_img is None:
            continue

        canvas_img = _composite_layer(
            canvas_img, layer_img, layer.get("blend_mode", "normal")
        )

    # Convert mode for export
    if fmt == "JPEG":
        if canvas_img.mode == "RGBA":
            # Flatten alpha onto white background for JPEG
            bg = Image.new("RGB", canvas_img.size, (255, 255, 255))
            bg.paste(canvas_img, mask=canvas_img.split()[3])
            canvas_img = bg
        elif canvas_img.mode != "RGB":
            canvas_img = canvas_img.convert("RGB")
    elif fmt == "GIF":
        canvas_img = canvas_img.convert("P", palette=Image.ADAPTIVE, colors=256)

    # Set DPI
    dpi = canvas.get("dpi", 72)
    save_params["dpi"] = (dpi, dpi)

    # Save
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    canvas_img.save(output_path, format=fmt, **save_params)

    # Verify output
    result = {
        "output": os.path.abspath(output_path),
        "format": fmt,
        "size": f"{canvas_img.width}x{canvas_img.height}",
        "file_size": os.path.getsize(output_path),
        "file_size_human": _human_size(os.path.getsize(output_path)),
        "preset": preset,
        "layers_rendered": sum(1 for l in layers if l.get("visible", True)),
        "applied_layer_operations": applied_layer_operations,
    }

    return result


def _prepare_layers_for_export(
    project: Dict[str, Any], canvas_w: int, canvas_h: int
) -> tuple[list[Dict[str, Any]], list[str]]:
    """Resolve deferred layer operations against a working layer stack."""
    layers = list(project.get("layers", []))
    applied: list[str] = []

    merge_index = project.get("_merge_down_pending")
    if isinstance(merge_index, int) and 0 <= merge_index < len(layers) - 1:
        merged = _merge_layers(layers[merge_index], layers[merge_index + 1], canvas_w, canvas_h)
        layers = layers[:merge_index] + [merged] + layers[merge_index + 2:]
        applied.append("merge_down")

    if project.get("_flatten_pending"):
        flattened = _flatten_visible_layers(layers, canvas_w, canvas_h)
        if flattened is not None:
            layers = [flattened]
            applied.append("flatten")

    return layers, applied


def _merge_layers(
    top_layer: Dict[str, Any], bottom_layer: Dict[str, Any], canvas_w: int, canvas_h: int
) -> Dict[str, Any]:
    """Merge one layer into the layer immediately below it for export."""
    bottom_canvas = _render_layer_to_canvas(bottom_layer, canvas_w, canvas_h)
    top_canvas = _render_layer_to_canvas(top_layer, canvas_w, canvas_h)

    if bottom_canvas is None:
        bottom_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    if top_canvas is None:
        merged = bottom_canvas
    else:
        merged = _composite_layer(
            bottom_canvas,
            top_canvas,
            top_layer.get("blend_mode", "normal"),
        )

    return {
        "name": bottom_layer.get("name", "Merged Layer"),
        "type": "image",
        "visible": True,
        "opacity": 1.0,
        "blend_mode": "normal",
        "_rendered_image": merged,
    }


def _flatten_visible_layers(
    layers: list[Dict[str, Any]], canvas_w: int, canvas_h: int
) -> Optional[Dict[str, Any]]:
    """Flatten all visible layers into a single rasterized layer for export."""
    visible_layers = [layer for layer in layers if layer.get("visible", True)]
    if not visible_layers:
        return None

    flattened = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    for layer in reversed(visible_layers):
        layer_canvas = _render_layer_to_canvas(layer, canvas_w, canvas_h)
        if layer_canvas is None:
            continue
        flattened = _composite_layer(
            flattened,
            layer_canvas,
            layer.get("blend_mode", "normal"),
        )

    return {
        "name": "Flattened Layer",
        "type": "image",
        "visible": True,
        "opacity": 1.0,
        "blend_mode": "normal",
        "_rendered_image": flattened,
    }


def _render_layer_to_canvas(
    layer: Dict[str, Any], canvas_w: int, canvas_h: int
) -> Optional[Image.Image]:
    """Render a single layer into a full-canvas RGBA image."""
    if "_rendered_image" in layer:
        rendered = layer["_rendered_image"]
        return rendered.convert("RGBA") if rendered.mode != "RGBA" else rendered.copy()

    layer_img = _load_layer(layer, canvas_w, canvas_h)
    if layer_img is None:
        return None

    layer_img = _apply_filters(layer_img, layer.get("filters", []))

    if "_scale_x" in layer:
        new_w = max(1, round(layer_img.width * layer["_scale_x"]))
        new_h = max(1, round(layer_img.height * layer["_scale_y"]))
        resample_map = {
            "nearest": Image.NEAREST, "bilinear": Image.BILINEAR,
            "bicubic": Image.BICUBIC, "lanczos": Image.LANCZOS,
        }
        resample = resample_map.get(layer.get("_resample", "lanczos"), Image.LANCZOS)
        layer_img = layer_img.resize((new_w, new_h), resample)

    if layer_img.mode != "RGBA":
        layer_img = layer_img.convert("RGBA")

    opacity = layer.get("opacity", 1.0)
    if opacity < 1.0:
        alpha = layer_img.split()[3].point(lambda a: int(a * opacity))
        layer_img.putalpha(alpha)

    ox = layer.get("offset_x", 0)
    oy = layer.get("offset_y", 0)

    layer_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    layer_canvas.paste(layer_img, (ox, oy), layer_img)
    return layer_canvas


def _load_layer(layer: Dict[str, Any], canvas_w: int, canvas_h: int) -> Optional[Image.Image]:
    """Load a layer's content as a PIL Image."""
    layer_type = layer.get("type", "image")

    if layer_type == "image":
        source = layer.get("source")
        if source and os.path.exists(source):
            img = Image.open(source).convert("RGBA")
            return img
        # Blank layer with fill
        fill = layer.get("fill", "transparent")
        w = layer.get("width", canvas_w)
        h = layer.get("height", canvas_h)
        if fill == "transparent":
            return Image.new("RGBA", (w, h), (0, 0, 0, 0))
        elif fill == "white":
            return Image.new("RGBA", (w, h), (255, 255, 255, 255))
        elif fill == "black":
            return Image.new("RGBA", (w, h), (0, 0, 0, 255))
        else:
            return Image.new("RGBA", (w, h), fill)

    elif layer_type == "solid":
        fill = layer.get("fill", "#ffffff")
        w = layer.get("width", canvas_w)
        h = layer.get("height", canvas_h)
        return Image.new("RGBA", (w, h), fill)

    elif layer_type == "text":
        return _render_text_layer(layer, canvas_w, canvas_h)

    return None


def _render_text_layer(layer: Dict[str, Any], canvas_w: int, canvas_h: int) -> Image.Image:
    """Render a text layer to an image."""
    text = layer.get("text", "")
    font_size = layer.get("font_size", 24)
    color = layer.get("color", "#000000")
    w = layer.get("width", canvas_w)
    h = layer.get("height", canvas_h)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    draw.text((0, 0), text, fill=color, font=font)
    return img


def _apply_filters(img: Image.Image, filters: list) -> Image.Image:
    """Apply a chain of filters to an image."""
    for f in filters:
        name = f["name"]
        params = f.get("params", {})
        img = _apply_single_filter(img, name, params)
    return img


def _apply_single_filter(img: Image.Image, name: str, params: Dict) -> Image.Image:
    """Apply a single filter to an image."""
    from cli_anything.gimp.core.filters import FILTER_REGISTRY

    if name not in FILTER_REGISTRY:
        return img  # Skip unknown filters

    spec = FILTER_REGISTRY[name]
    engine = spec["engine"]

    # Convert to appropriate mode for processing
    original_mode = img.mode
    needs_rgba = original_mode == "RGBA"

    if engine == "pillow_enhance":
        cls_name = spec["pillow_class"]
        factor = params.get("factor", 1.0)
        # ImageEnhance needs RGB, handle RGBA by separating alpha
        if needs_rgba:
            alpha = img.split()[3]
            rgb = img.convert("RGB")
            enhancer = getattr(ImageEnhance, cls_name)(rgb)
            result = enhancer.enhance(factor).convert("RGBA")
            result.putalpha(alpha)
            return result
        else:
            enhancer = getattr(ImageEnhance, cls_name)(img)
            return enhancer.enhance(factor)

    elif engine == "pillow_ops":
        func_name = spec["pillow_func"]
        if needs_rgba:
            alpha = img.split()[3]
            rgb = img.convert("RGB")
        else:
            rgb = img

        if func_name == "autocontrast":
            result = ImageOps.autocontrast(rgb, cutoff=params.get("cutoff", 0))
        elif func_name == "equalize":
            result = ImageOps.equalize(rgb)
        elif func_name == "invert":
            result = ImageOps.invert(rgb)
        elif func_name == "posterize":
            result = ImageOps.posterize(rgb, bits=params.get("bits", 4))
        elif func_name == "solarize":
            result = ImageOps.solarize(rgb, threshold=params.get("threshold", 128))
        elif func_name == "grayscale":
            result = ImageOps.grayscale(rgb)
            if needs_rgba:
                result = result.convert("RGBA")
                result.putalpha(alpha)
                return result
            return result
        else:
            return img

        if needs_rgba:
            result = result.convert("RGBA")
            result.putalpha(alpha)
        return result

    elif engine == "pillow_filter":
        filter_name = spec["pillow_filter"]
        if filter_name == "GaussianBlur":
            pf = ImageFilter.GaussianBlur(radius=params.get("radius", 2.0))
        elif filter_name == "BoxBlur":
            pf = ImageFilter.BoxBlur(radius=params.get("radius", 2.0))
        elif filter_name == "UnsharpMask":
            pf = ImageFilter.UnsharpMask(
                radius=params.get("radius", 2.0),
                percent=params.get("percent", 150),
                threshold=params.get("threshold", 3),
            )
        elif filter_name == "SMOOTH_MORE":
            pf = ImageFilter.SMOOTH_MORE
        elif filter_name == "FIND_EDGES":
            pf = ImageFilter.FIND_EDGES
        elif filter_name == "EMBOSS":
            pf = ImageFilter.EMBOSS
        elif filter_name == "CONTOUR":
            pf = ImageFilter.CONTOUR
        elif filter_name == "DETAIL":
            pf = ImageFilter.DETAIL
        else:
            return img
        return img.filter(pf)

    elif engine == "pillow_transform":
        method = spec["pillow_method"]
        if method == "rotate":
            angle = params.get("angle", 0.0)
            expand = params.get("expand", True)
            return img.rotate(-angle, expand=expand, resample=Image.BICUBIC)
        elif method == "flip_h":
            return img.transpose(Image.FLIP_LEFT_RIGHT)
        elif method == "flip_v":
            return img.transpose(Image.FLIP_TOP_BOTTOM)
        elif method == "resize":
            w = params.get("width", img.width)
            h = params.get("height", img.height)
            resample_map = {
                "nearest": Image.NEAREST, "bilinear": Image.BILINEAR,
                "bicubic": Image.BICUBIC, "lanczos": Image.LANCZOS,
            }
            rs = resample_map.get(params.get("resample", "lanczos"), Image.LANCZOS)
            return img.resize((w, h), rs)
        elif method == "crop":
            left = params.get("left", 0)
            top = params.get("top", 0)
            right = params.get("right", img.width)
            bottom = params.get("bottom", img.height)
            return img.crop((left, top, right, bottom))

    elif engine == "custom":
        func_name = spec["custom_func"]
        if func_name == "apply_sepia":
            return _apply_sepia(img, params.get("strength", 0.8))

    return img


def _apply_sepia(img: Image.Image, strength: float = 0.8) -> Image.Image:
    """Apply sepia tone effect."""
    needs_rgba = img.mode == "RGBA"
    if needs_rgba:
        alpha = img.split()[3]

    gray = ImageOps.grayscale(img)
    sepia = ImageOps.colorize(gray, "#704214", "#C0A080")

    if strength < 1.0:
        # Blend with original
        rgb = img.convert("RGB")
        from PIL import Image as PILImage
        sepia = PILImage.blend(rgb, sepia, strength)

    if needs_rgba:
        sepia = sepia.convert("RGBA")
        sepia.putalpha(alpha)

    return sepia


def _composite_layer(
    base: Image.Image,
    layer: Image.Image,
    blend_mode: str,
) -> Image.Image:
    """Composite a full-canvas layer image onto the base canvas."""
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    if layer.mode != "RGBA":
        layer = layer.convert("RGBA")

    if blend_mode == "normal":
        return Image.alpha_composite(base, layer)

    # For other blend modes, we need numpy
    try:
        return _blend_with_mode(base, layer, blend_mode)
    except ImportError:
        # Fallback to normal if numpy not available
        return Image.alpha_composite(base, layer)


def _blend_with_mode(base: Image.Image, layer: Image.Image, mode: str) -> Image.Image:
    """Apply blend mode using numpy pixel math."""
    base_arr = np.array(base, dtype=np.float64)
    layer_arr = np.array(layer, dtype=np.float64)

    # Extract channels
    b_rgb = base_arr[:, :, :3] / 255.0
    l_rgb = layer_arr[:, :, :3] / 255.0
    b_alpha = base_arr[:, :, 3:4] / 255.0
    l_alpha = layer_arr[:, :, 3:4] / 255.0

    # Apply blend formula to RGB channels
    if mode == "multiply":
        blended = b_rgb * l_rgb
    elif mode == "screen":
        blended = 1.0 - (1.0 - b_rgb) * (1.0 - l_rgb)
    elif mode == "overlay":
        mask = b_rgb < 0.5
        blended = np.where(mask, 2 * b_rgb * l_rgb, 1 - 2 * (1 - b_rgb) * (1 - l_rgb))
    elif mode == "soft_light":
        blended = np.where(
            l_rgb <= 0.5,
            b_rgb - (1 - 2 * l_rgb) * b_rgb * (1 - b_rgb),
            b_rgb + (2 * l_rgb - 1) * (np.sqrt(b_rgb) - b_rgb),
        )
    elif mode == "hard_light":
        mask = l_rgb < 0.5
        blended = np.where(mask, 2 * b_rgb * l_rgb, 1 - 2 * (1 - b_rgb) * (1 - l_rgb))
    elif mode == "difference":
        blended = np.abs(b_rgb - l_rgb)
    elif mode == "darken":
        blended = np.minimum(b_rgb, l_rgb)
    elif mode == "lighten":
        blended = np.maximum(b_rgb, l_rgb)
    elif mode == "color_dodge":
        blended = np.clip(b_rgb / (1.0 - l_rgb + 1e-10), 0, 1)
    elif mode == "color_burn":
        blended = np.clip(1.0 - (1.0 - b_rgb) / (l_rgb + 1e-10), 0, 1)
    elif mode == "addition":
        blended = np.clip(b_rgb + l_rgb, 0, 1)
    elif mode == "subtract":
        blended = np.clip(b_rgb - l_rgb, 0, 1)
    elif mode == "grain_merge":
        blended = np.clip(b_rgb + l_rgb - 0.5, 0, 1)
    elif mode == "grain_extract":
        blended = np.clip(b_rgb - l_rgb + 0.5, 0, 1)
    else:
        blended = l_rgb  # Fallback to normal

    # Composite: result = blended * layer_alpha + base * (1 - layer_alpha)
    result_rgb = blended * l_alpha + b_rgb * (1.0 - l_alpha)
    result_alpha = np.clip(b_alpha + l_alpha * (1.0 - b_alpha), 0, 1)

    result = np.concatenate([result_rgb, result_alpha], axis=2)
    result = np.clip(result * 255, 0, 255).astype(np.uint8)

    return Image.fromarray(result, "RGBA")


def _human_size(nbytes: int) -> str:
    """Convert byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"
