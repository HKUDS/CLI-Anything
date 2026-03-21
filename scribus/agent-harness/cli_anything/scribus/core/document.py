"""Scribus CLI — Document operations for .sla files."""

import os, subprocess, shutil, tempfile, math
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List

UNITS = {"mm": 1.0, "inches": 25.4, "points": 0.3528}


def find_scribus() -> str:
    for name in ("scribus", "scribus-ng"):
        p = shutil.which(name)
        if p:
            return p
    raise RuntimeError("Scribus not found. Install with: apt install scribus")


def create_document(
    output: str,
    width: float = 210.0,
    height: float = 297.0,
    pages: int = 1,
    orientation: str = "portrait",
    unit: str = "mm",
) -> Dict[str, Any]:
    if orientation == "landscape":
        width, height = height, width
    doc = _build_sla_template(width, height, pages, unit)
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(doc)
    return {
        "output": os.path.abspath(output),
        "width": width,
        "height": height,
        "pages": pages,
        "orientation": orientation,
        "unit": unit,
    }


def get_file_info(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    info = {
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "file_size": os.path.getsize(path),
    }
    if path.endswith(".sla"):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            info["scribus_version"] = root.attrib.get("Version", "unknown")
            info["width"] = float(root.attrib.get("PAGEWIDTH", 0))
            info["height"] = float(root.attrib.get("PAGEHEIGHT", 0))
            info["unit"] = root.attrib.get("UNITS", "mm")
            pages = [n for n in root.iter() if n.tag == "PAGE"]
            info["page_count"] = len(pages)
            layers = [n for n in root.iter() if n.tag == "LAYERS"]
            info["layer_count"] = len(layers)
            objects = [n for n in root.iter() if n.tag == "PAGEOBJECT"]
            info["object_count"] = len(objects)
        except ET.ParseError as e:
            info["parse_error"] = str(e)
    return info


def export_to_pdf(
    input_path: str,
    output_path: str,
    preset: str = "print",
    quality: Optional[int] = None,
    pages: Optional[str] = None,
) -> Dict[str, Any]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")
    script = _build_pdf_script(input_path, output_path, preset, quality, pages)
    script_path = tempfile.mktemp(suffix=".py")
    with open(script_path, "w") as f:
        f.write(script)
    try:
        cmd = [find_scribus(), "-g", "-py", script_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 and not os.path.exists(output_path):
            raise RuntimeError(f"Scribus export failed: {result.stderr.strip()}")
    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)
    if not os.path.exists(output_path):
        raise RuntimeError(f"PDF not produced at {output_path}")
    return {
        "input": os.path.abspath(input_path),
        "output": os.path.abspath(output_path),
        "file_size": os.path.getsize(output_path),
        "preset": preset,
    }


def add_page(path: str, output: str) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    page_count = len([n for n in root.iter() if n.tag == "PAGE"])
    doc_element = root.find(".")
    new_page = ET.SubElement(doc_element, "PAGE")
    new_page.attrib = {
        "NUM": str(page_count),
        "XPOS": "0",
        "YPOS": str(page_count * 297),
        "Width": "210",
        "Height": "297",
        "PAGEVORDER": "0",
        "Left": "0",
        "Right": "0",
        "Top": "0",
        "Bottom": "0",
    }
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    tree.write(output, encoding="UTF-8", xml_declaration=True)
    return {"pages": page_count + 1, "output": os.path.abspath(output)}


def list_pages(path: str) -> List[Dict[str, Any]]:
    tree = ET.parse(path)
    pages = []
    for p in tree.iter():
        if p.tag == "PAGE":
            pages.append(
                {
                    "num": int(p.attrib.get("NUM", 0)),
                    "width": float(p.attrib.get("Width", 0)),
                    "height": float(p.attrib.get("Height", 0)),
                    "x": float(p.attrib.get("XPOS", 0)),
                    "y": float(p.attrib.get("YPOS", 0)),
                }
            )
    return pages


def add_text_frame(
    path: str,
    page: int,
    x: float,
    y: float,
    w: float,
    h: float,
    content: str,
    output: str,
) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    obj_count = len([n for n in root.iter() if n.tag == "PAGEOBJECT"])
    obj = ET.SubElement(root, "PAGEOBJECT")
    obj.attrib = {
        "ItemID": str(obj_count),
        "ItemType": "4",
        "XPOS": str(x),
        "YPOS": str(y),
        "Width": str(w),
        "Height": str(h),
        "OwnPage": str(page),
    }
    itext = ET.SubElement(obj, "ITEXT")
    itext.attrib = {"CH": content}
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    tree.write(output, encoding="UTF-8", xml_declaration=True)
    return {"object_id": obj_count, "page": page, "output": os.path.abspath(output)}


def add_image_frame(
    path: str,
    page: int,
    x: float,
    y: float,
    w: float,
    h: float,
    image_path: str,
    output: str,
) -> Dict[str, Any]:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    tree = ET.parse(path)
    root = tree.getroot()
    obj_count = len([n for n in root.iter() if n.tag == "PAGEOBJECT"])
    obj = ET.SubElement(root, "PAGEOBJECT")
    obj.attrib = {
        "ItemID": str(obj_count),
        "ItemType": "2",
        "XPOS": str(x),
        "YPOS": str(y),
        "Width": str(w),
        "Height": str(h),
        "OwnPage": str(page),
        "PFILE": os.path.abspath(image_path),
    }
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    tree.write(output, encoding="UTF-8", xml_declaration=True)
    return {
        "object_id": obj_count,
        "page": page,
        "image": os.path.abspath(image_path),
        "output": os.path.abspath(output),
    }


def list_layers_sla(path: str) -> List[Dict[str, Any]]:
    tree = ET.parse(path)
    layers = []
    for l in tree.iter():
        if l.tag == "LAYERS":
            layers.append(
                {
                    "name": l.attrib.get("NAME", "Layer"),
                    "id": int(l.attrib.get("NUM", 0)),
                    "visible": l.attrib.get("VVisible", "1") == "1",
                    "editable": l.attrib.get("VEditable", "1") == "1",
                }
            )
    return layers


def add_layer_sla(path: str, name: str, output: str) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    layer_count = len([n for n in root.iter() if n.tag == "LAYERS"])
    layer = ET.SubElement(root, "LAYERS")
    layer.attrib = {
        "NUM": str(layer_count),
        "NAME": name,
        "VVisible": "1",
        "VEditable": "1",
    }
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    tree.write(output, encoding="UTF-8", xml_declaration=True)
    return {"layer_id": layer_count, "name": name, "output": os.path.abspath(output)}


def list_fonts() -> List[str]:
    try:
        script = "import scribus; print('\\n'.join(scribus.getFontNames()))"
        script_path = tempfile.mktemp(suffix=".py")
        with open(script_path, "w") as f:
            f.write(script)
        result = subprocess.run(
            [find_scribus(), "-g", "-py", script_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        os.unlink(script_path)
        if result.returncode == 0 and result.stdout.strip():
            return sorted(result.stdout.strip().split("\n"))
    except:
        pass
    font_dirs = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
    ]
    fonts = set()
    for d in font_dirs:
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith((".ttf", ".otf")):
                        fonts.add(os.path.splitext(f)[0])
    return sorted(fonts)


def _build_sla_template(width: float, height: float, pages: int, unit: str) -> str:
    page_objects = ""
    for i in range(pages):
        page_objects += f'    <PAGE NUM="{i}" XPOS="0" YPOS="{i * height}" Width="{width}" Height="{height}" PAGEVORDER="0" Left="0" Right="0" Top="0" Bottom="0"/>\n'
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<SCRIBUSUTF8 Version="1.5.8">\n'
        f'  <DOCUMENT PAGEWIDTH="{width}" PAGEHEIGHT="{height}" UNITS="{unit}">\n'
        f"{page_objects}"
        f'    <LAYERS NUM="0" NAME="Background" VVisible="1" VEditable="1"/>\n'
        f"  </DOCUMENT>\n"
        f"</SCRIBUSUTF8>\n"
    )


def _build_pdf_script(
    input_path: str,
    output_path: str,
    preset: str,
    quality: Optional[int],
    pages: Optional[str],
) -> str:
    abs_in = os.path.abspath(input_path).replace("\\", "\\\\")
    abs_out = os.path.abspath(output_path).replace("\\", "\\\\")
    return (
        f"import scribus\n"
        f'scribus.openDoc("{abs_in}")\n'
        f"pdf = scribus.PDFfile()\n"
        f'pdf.file = "{abs_out}"\n'
        f"pdf.save()\n"
    )
