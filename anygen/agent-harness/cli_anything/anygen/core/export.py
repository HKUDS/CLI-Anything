"""Export utilities — file format verification for downloaded AnyGen outputs."""

import zipfile
from pathlib import Path


def verify_file(file_path: str) -> dict:
    """Verify a downloaded file's integrity and format.

    Returns {"valid": bool, "format": str, "file_size": int, "details": str}.
    """
    path = Path(file_path)
    if not path.exists():
        return {"valid": False, "format": "unknown", "file_size": 0, "details": "File not found"}

    size = path.stat().st_size
    if size == 0:
        return {"valid": False, "format": "unknown", "file_size": 0, "details": "Empty file"}

    suffix = path.suffix.lower()

    with open(path, "rb") as f:
        header = f.read(8)

    if suffix in (".pptx", ".docx", ".xlsx"):
        is_zip = header[:4] == b"PK\x03\x04"
        if is_zip:
            try:
                with zipfile.ZipFile(path) as zf:
                    names = zf.namelist()
                has_content_types = "[Content_Types].xml" in names
                fmt = "OOXML" if has_content_types else "ZIP"
                return {
                    "valid": has_content_types,
                    "format": fmt,
                    "file_size": size,
                    "details": f"Valid {suffix.upper().lstrip('.')} ({len(names)} entries)",
                }
            except zipfile.BadZipFile:
                return {"valid": False, "format": "corrupt_zip", "file_size": size, "details": "Bad ZIP"}
        return {"valid": False, "format": "not_zip", "file_size": size, "details": "Expected ZIP/OOXML"}

    if suffix == ".pdf":
        is_pdf = header[:5] == b"%PDF-"
        return {
            "valid": is_pdf,
            "format": "PDF",
            "file_size": size,
            "details": "Valid PDF" if is_pdf else "Missing %PDF- header",
        }

    if suffix == ".png":
        is_png = header[:8] == b"\x89PNG\r\n\x1a\n"
        return {
            "valid": is_png,
            "format": "PNG",
            "file_size": size,
            "details": "Valid PNG" if is_png else "Bad PNG header",
        }

    if suffix == ".svg":
        try:
            text = path.read_text(encoding="utf-8")[:500]
            is_svg = "<svg" in text.lower()
            return {
                "valid": is_svg,
                "format": "SVG",
                "file_size": size,
                "details": "Valid SVG" if is_svg else "Missing <svg> tag",
            }
        except UnicodeDecodeError:
            return {"valid": False, "format": "binary", "file_size": size, "details": "Not valid SVG text"}

    if suffix in (".xml", ".drawio"):
        try:
            text = path.read_text(encoding="utf-8")[:500]
            is_xml = text.strip().startswith("<?xml") or text.strip().startswith("<")
            return {
                "valid": is_xml,
                "format": "XML",
                "file_size": size,
                "details": "Valid XML/drawio" if is_xml else "Not valid XML",
            }
        except UnicodeDecodeError:
            return {"valid": False, "format": "binary", "file_size": size, "details": "Not valid XML text"}

    if suffix == ".json":
        try:
            import json
            with open(path) as f:
                json.load(f)
            return {"valid": True, "format": "JSON", "file_size": size, "details": "Valid JSON"}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"valid": False, "format": "invalid_json", "file_size": size, "details": "Invalid JSON"}

    return {
        "valid": True,
        "format": suffix.lstrip(".") or "unknown",
        "file_size": size,
        "details": f"File exists ({size:,} bytes), format not verified",
    }
