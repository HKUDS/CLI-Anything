"""Darktable CLI — RAW photo processing via darktable-cli."""

import os, subprocess, shutil, json
from typing import Dict, Any, Optional, List

STYLES_DIR = "/usr/share/darktable/styles"


def find_darktable_cli() -> str:
    for name in ("darktable-cli", "darktable"):
        p = shutil.which(name)
        if p:
            return p
    raise RuntimeError("darktable-cli not found. Install with: apt install darktable")


def export_raw(
    input_path: str,
    output_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    quality: Optional[int] = None,
    icc: Optional[str] = None,
    style: Optional[str] = None,
    xmp: Optional[str] = None,
) -> Dict[str, Any]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")
    cmd = [find_darktable_cli(), input_path, output_path]
    if width or height:
        w = width or 0
        h = height or 0
        cmd += [f"--width {w}", f"--height {h}"]
    if quality is not None:
        cmd += [f"--quality {quality}"]
    if icc:
        cmd += [f"--icc {icc}"]
    if style:
        cmd += [f"--style {style}"]
    if xmp:
        if not os.path.exists(xmp):
            raise FileNotFoundError(f"XMP not found: {xmp}")
        cmd += [xmp]
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"darktable-cli failed: {result.stderr.strip()}")
    return {
        "input": os.path.abspath(input_path),
        "output": os.path.abspath(output_path),
        "file_size": os.path.getsize(output_path),
        "format": os.path.splitext(output_path)[1].lstrip(".").upper(),
    }


def get_file_info(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    info = {
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "file_size": os.path.getsize(path),
        "extension": os.path.splitext(path)[1].lower(),
    }
    try:
        result = subprocess.run(
            ["exiftool", "-j", "-n", path], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data:
                info["exif"] = data[0]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    if "exif" not in info:
        try:
            result = subprocess.run(
                [find_darktable_cli(), path, "/dev/null", "--outfile-ext", "jpg"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            for line in result.stderr.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    if k.strip() and v.strip():
                        info.setdefault("exif", {})[k.strip()] = v.strip()
        except:
            pass
    return info


def batch_export(inputs: List[str], output_dir: str, **kwargs) -> List[Dict[str, Any]]:
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for inp in inputs:
        base = os.path.splitext(os.path.basename(inp))[0]
        ext = kwargs.get("format", "jpg").lower()
        out = os.path.join(output_dir, f"{base}.{ext}")
        try:
            r = export_raw(
                inp, out, **{k: v for k, v in kwargs.items() if k != "format"}
            )
            r["status"] = "success"
            results.append(r)
        except Exception as e:
            results.append({"input": inp, "status": "error", "error": str(e)})
    return results


def list_styles() -> List[str]:
    styles = []
    if os.path.isdir(STYLES_DIR):
        for f in os.listdir(STYLES_DIR):
            if f.endswith(".dtstyle"):
                styles.append(os.path.splitext(f)[0])
    home = os.path.expanduser("~/.config/darktable/styles")
    if os.path.isdir(home):
        for f in os.listdir(home):
            if f.endswith(".dtstyle"):
                styles.append(os.path.splitext(f)[0])
    return sorted(set(styles))


def export_with_style(
    input_path: str, output_path: str, style_name: str, **kwargs
) -> Dict[str, Any]:
    return export_raw(input_path, output_path, style=style_name, **kwargs)


def create_xmp(input_path: str) -> str:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")
    xmp_path = input_path + ".xmp"
    cmd = [find_darktable_cli(), input_path, "/dev/null"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if os.path.exists(xmp_path):
        return xmp_path
    with open(xmp_path, "w") as f:
        f.write(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
            f'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
            f'<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">\n'
            f"<xmp:CreatorTool>darktable-cli</xmp:CreatorTool>\n"
            f"</rdf:Description>\n</rdf:RDF>\n</x:xmpmeta>\n"
        )
    return xmp_path


def apply_xmp(
    xmp_path: str, input_path: str, output_path: str, **kwargs
) -> Dict[str, Any]:
    return export_raw(input_path, output_path, xmp=xmp_path, **kwargs)
