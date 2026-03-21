"""Krita CLI — Canvas and layer operations for .kra files."""

import os, subprocess, shutil, zipfile, xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List


def find_krita() -> str:
    p = shutil.which("krita")
    if p:
        return p
    raise RuntimeError("Krita not found. Install with: apt install krita")


def get_file_info(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    info = {
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "file_size": os.path.getsize(path),
    }
    if path.endswith(".kra") and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as zf:
            info["contents"] = zf.namelist()
            if "maindoc.xml" in zf.namelist():
                with zf.open("maindoc.xml") as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    info["width"] = int(root.attrib.get("width", 0))
                    info["height"] = int(root.attrib.get("height", 0))
                    info["colorspace"] = root.attrib.get("colorspacename", "RGBA")
                    layers = []
                    for layer in root.iter():
                        if layer.tag.endswith("layer"):
                            layers.append(
                                {
                                    "name": layer.attrib.get("name", "Layer"),
                                    "type": layer.attrib.get("nodetype", "paintlayer"),
                                    "visible": layer.attrib.get("visible", "1") == "1",
                                    "opacity": int(layer.attrib.get("opacity", 255)),
                                }
                            )
                    info["layers"] = layers
                    info["layer_count"] = len(layers)
    return info


def list_layers(path: str) -> List[Dict[str, Any]]:
    if not path.endswith(".kra"):
        raise ValueError("Only .kra files supported")
    with zipfile.ZipFile(path, "r") as zf:
        if "maindoc.xml" not in zf.namelist():
            raise ValueError("Invalid .kra: no maindoc.xml")
        with zf.open("maindoc.xml") as f:
            tree = ET.parse(f)
            root = tree.getroot()
            layers = []
            for i, layer in enumerate(root.iter()):
                if layer.tag.endswith("layer"):
                    layers.append(
                        {
                            "index": i,
                            "name": layer.attrib.get("name", "Layer"),
                            "type": layer.attrib.get("nodetype", "paintlayer"),
                            "visible": layer.attrib.get("visible", "1") == "1",
                            "opacity": int(layer.attrib.get("opacity", 255)),
                        }
                    )
            return layers


def export_file(
    input_path: str,
    output_path: str,
    flatten: bool = False,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Dict[str, Any]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")
    cmd = [find_krita(), "--export", input_path, "--output", output_path]
    if flatten:
        cmd.append("--flatten")
    if width:
        cmd += [f"--width", str(width)]
    if height:
        cmd += [f"--height", str(height)]
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Krita export failed: {result.stderr.strip()}")
    return {
        "input": os.path.abspath(input_path),
        "output": os.path.abspath(output_path),
        "file_size": os.path.getsize(output_path),
        "format": os.path.splitext(output_path)[1].lstrip(".").upper(),
    }


def batch_export(
    inputs: List[str], output_dir: str, fmt: str = "png", **kwargs
) -> List[Dict[str, Any]]:
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for inp in inputs:
        base = os.path.splitext(os.path.basename(inp))[0]
        out = os.path.join(output_dir, f"{base}.{fmt}")
        try:
            r = export_file(inp, out, **kwargs)
            r["status"] = "success"
            results.append(r)
        except Exception as e:
            results.append({"input": inp, "status": "error", "error": str(e)})
    return results


def export_layer(path: str, index: int, output: str) -> Dict[str, Any]:
    layers = list_layers(path)
    if index < 0 or index >= len(layers):
        raise IndexError(f"Layer index {index} out of range")
    layer = layers[index]
    with zipfile.ZipFile(path, "r") as zf:
        layer_file = f"layer{index:04d}/content.png"
        if layer_file in zf.namelist():
            os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
            with zf.open(layer_file) as src, open(output, "wb") as dst:
                dst.write(src.read())
            return {
                "layer": layer["name"],
                "output": os.path.abspath(output),
                "file_size": os.path.getsize(output),
            }
    raise RuntimeError(f"Layer content not found at index {index}")


def create_canvas(
    width: int, height: int, output: str, background: str = "#ffffff"
) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise RuntimeError("Pillow required. pip install Pillow")
    bg = background if background != "transparent" else (0, 0, 0, 0)
    img = Image.new("RGBA", (width, height), bg)
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    img.save(output)
    return {
        "output": os.path.abspath(output),
        "width": width,
        "height": height,
        "background": background,
    }


def resize_canvas(
    input_path: str, output_path: str, width: int, height: int
) -> Dict[str, Any]:
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow required. pip install Pillow")
    img = Image.open(input_path)
    img = img.resize((width, height), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path)
    return {
        "input": os.path.abspath(input_path),
        "output": os.path.abspath(output_path),
        "old_size": f"{img.width}x{img.height}",
        "new_size": f"{width}x{height}",
    }


def apply_filter(input_path: str, output_path: str, filter_name: str) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    except ImportError:
        raise RuntimeError("Pillow required. pip install Pillow")
    img = Image.open(input_path)
    filters = {
        "blur": ImageFilter.GaussianBlur(2),
        "sharpen": ImageFilter.UnsharpMask(radius=2, percent=150),
        "emboss": ImageFilter.EMBOSS,
        "edges": ImageFilter.FIND_EDGES,
        "contour": ImageFilter.CONTOUR,
        "detail": ImageFilter.DETAIL,
        "smooth": ImageFilter.SMOOTH_MORE,
    }
    if filter_name in filters:
        img = img.filter(filters[filter_name])
    elif filter_name == "grayscale":
        img = ImageOps.grayscale(img).convert("RGBA")
    elif filter_name == "invert":
        img = ImageOps.invert(img.convert("RGB")).convert("RGBA")
    elif filter_name == "brightness":
        img = ImageEnhance.Brightness(img).enhance(1.3)
    elif filter_name == "contrast":
        img = ImageEnhance.Contrast(img).enhance(1.3)
    else:
        raise ValueError(
            f"Unknown filter: {filter_name}. Available: {list(filters.keys()) + ['grayscale', 'invert', 'brightness', 'contrast']}"
        )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path)
    return {
        "input": os.path.abspath(input_path),
        "output": os.path.abspath(output_path),
        "filter": filter_name,
    }


def convert_colorspace(input_path: str, output_path: str, space: str) -> Dict[str, Any]:
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow required. pip install Pillow")
    img = Image.open(input_path)
    space = space.upper()
    if space in ("SRGB", "RGB"):
        img = img.convert("RGB")
    elif space == "RGBA":
        img = img.convert("RGBA")
    elif space == "CMYK":
        img = img.convert("CMYK")
    elif space == "GRAYSCALE":
        img = img.convert("L")
    else:
        raise ValueError(f"Unknown colorspace: {space}")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path)
    return {
        "input": os.path.abspath(input_path),
        "output": os.path.abspath(output_path),
        "colorspace": space,
    }
