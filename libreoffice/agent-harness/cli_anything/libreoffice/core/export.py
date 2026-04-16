"""LibreOffice CLI - Export module.

Exports project JSON to ODF files (real ZIP archives), HTML, plain text,
and via LibreOffice headless to PDF, DOCX, XLSX, PPTX, and other formats.
"""

import os
import html as html_module
import tempfile
from typing import Dict, Any, Optional, List

from cli_anything.libreoffice.utils.odf_utils import write_odf, ODF_EXTENSIONS
from cli_anything.libreoffice.utils.lo_backend import convert_odf_to


# Export presets
# "native" presets produce ODF/HTML/text directly (no LibreOffice needed)
# "lo_convert" presets use LibreOffice headless to convert from ODF
EXPORT_PRESETS = {
    # Native ODF
    "odt": {"format": "odt", "ext": ".odt", "description": "ODF Writer document", "method": "native"},
    "ods": {"format": "ods", "ext": ".ods", "description": "ODF Calc spreadsheet", "method": "native"},
    "odp": {"format": "odp", "ext": ".odp", "description": "ODF Impress presentation", "method": "native"},
    "html": {"format": "html", "ext": ".html", "description": "HTML document", "method": "native"},
    "text": {"format": "text", "ext": ".txt", "description": "Plain text", "method": "native"},
    # LibreOffice headless conversions
    "pdf": {"format": "pdf", "ext": ".pdf", "description": "PDF document (via LibreOffice)", "method": "lo_convert", "source_odf": "writer"},
    "docx": {"format": "docx", "ext": ".docx", "description": "MS Word DOCX (via LibreOffice)", "method": "lo_convert", "source_odf": "writer"},
    "xlsx": {"format": "xlsx", "ext": ".xlsx", "description": "MS Excel XLSX (via LibreOffice)", "method": "lo_convert", "source_odf": "calc"},
    "pptx": {"format": "pptx", "ext": ".pptx", "description": "MS PowerPoint PPTX (via LibreOffice)", "method": "lo_convert", "source_odf": "impress"},
    "csv": {"format": "csv", "ext": ".csv", "description": "CSV spreadsheet (via LibreOffice)", "method": "lo_convert", "source_odf": "calc"},
}

# Map format to doc type
_FORMAT_TO_DOCTYPE = {
    "odt": "writer",
    "ods": "calc",
    "odp": "impress",
}


def list_presets() -> List[Dict[str, Any]]:
    """List available export presets."""
    result = []
    for name, p in EXPORT_PRESETS.items():
        result.append({
            "name": name,
            "format": p["format"],
            "extension": p["ext"],
            "description": p["description"],
        })
    return result


def get_preset_info(name: str) -> Dict[str, Any]:
    """Get details about an export preset."""
    if name not in EXPORT_PRESETS:
        raise ValueError(
            f"Unknown preset: {name}. "
            f"Available: {', '.join(EXPORT_PRESETS.keys())}"
        )
    p = EXPORT_PRESETS[name]
    return {"name": name, **p}


def to_odt(project: Dict[str, Any], path: str, overwrite: bool = False) -> Dict[str, Any]:
    """Export to ODF Writer (.odt) format."""
    return _export_odf(project, path, "writer", overwrite)


def to_ods(project: Dict[str, Any], path: str, overwrite: bool = False) -> Dict[str, Any]:
    """Export to ODF Calc (.ods) format."""
    return _export_odf(project, path, "calc", overwrite)


def to_odp(project: Dict[str, Any], path: str, overwrite: bool = False) -> Dict[str, Any]:
    """Export to ODF Impress (.odp) format."""
    return _export_odf(project, path, "impress", overwrite)


def to_html(project: Dict[str, Any], path: str, overwrite: bool = False) -> Dict[str, Any]:
    """Export to HTML format."""
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"Output file exists: {path}. Use --overwrite.")

    doc_type = project.get("type", "writer")
    html_content = _build_html(project, doc_type)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "output": os.path.abspath(path),
        "format": "html",
        "file_size": os.path.getsize(path),
    }


def to_text(project: Dict[str, Any], path: str, overwrite: bool = False) -> Dict[str, Any]:
    """Export to plain text format."""
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"Output file exists: {path}. Use --overwrite.")

    doc_type = project.get("type", "writer")
    text_content = _build_text(project, doc_type)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text_content)

    return {
        "output": os.path.abspath(path),
        "format": "text",
        "file_size": os.path.getsize(path),
    }


def export(
    project: Dict[str, Any],
    output_path: str,
    preset: str = "odt",
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Export using a named preset.

    Native presets (odt, ods, odp, html, text) produce files directly.
    LibreOffice presets (pdf, docx, xlsx, pptx, csv) first generate an
    ODF intermediate file, then convert it using `libreoffice --headless`.
    """
    if preset not in EXPORT_PRESETS:
        raise ValueError(
            f"Unknown preset: {preset}. "
            f"Available: {', '.join(EXPORT_PRESETS.keys())}"
        )

    preset_cfg = EXPORT_PRESETS[preset]
    fmt = preset_cfg["format"]
    method = preset_cfg.get("method", "native")

    if method == "lo_convert":
        return _export_via_libreoffice(project, output_path, preset_cfg, overwrite)
    elif fmt == "html":
        return to_html(project, output_path, overwrite)
    elif fmt == "text":
        return to_text(project, output_path, overwrite)
    elif fmt in _FORMAT_TO_DOCTYPE:
        doc_type = _FORMAT_TO_DOCTYPE[fmt]
        return _export_odf(project, output_path, doc_type, overwrite)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def _export_via_libreoffice(
    project: Dict[str, Any],
    output_path: str,
    preset_cfg: Dict[str, Any],
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Export by generating an ODF intermediate then converting via LibreOffice.

    This is the key integration point: we generate a valid ODF file using our
    own XML builder, then hand it to LibreOffice headless for conversion to
    PDF/DOCX/XLSX/PPTX/CSV. LibreOffice does the real rendering.
    """
    target_format = preset_cfg["format"]
    source_odf_type = preset_cfg.get("source_odf", "writer")
    doc_type = project.get("type", "writer")

    # Determine correct ODF intermediate format based on document type
    odf_ext = {
        "writer": ".odt",
        "calc": ".ods",
        "impress": ".odp",
    }.get(doc_type, ".odt")

    # Generate the ODF intermediate in a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        odf_path = os.path.join(tmpdir, f"intermediate{odf_ext}")
        write_odf(odf_path, doc_type, project)

        result = convert_odf_to(
            odf_path,
            output_format=target_format,
            output_path=output_path,
            overwrite=overwrite,
        )

    result["preset"] = target_format
    result["source_type"] = doc_type
    return result


def _export_odf(
    project: Dict[str, Any],
    path: str,
    doc_type: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Export to an ODF file."""
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"Output file exists: {path}. Use --overwrite.")

    abs_path = write_odf(path, doc_type, project)

    return {
        "output": abs_path,
        "format": doc_type,
        "extension": ODF_EXTENSIONS.get(doc_type, ".odf"),
        "file_size": os.path.getsize(abs_path),
    }


def _build_html(project: Dict[str, Any], doc_type: str) -> str:
    """Build HTML content from a project."""
    title = project.get("metadata", {}).get("title", project.get("name", "Document"))
    parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<meta charset=\"utf-8\">",
        f"<title>{html_module.escape(title)}</title>",
        "<style>body { font-family: serif; max-width: 800px; margin: 2em auto; padding: 0 1em; }</style>",
        "</head>",
        "<body>",
    ]

    if doc_type == "writer":
        for item in project.get("content", []):
            parts.append(_content_item_to_html(item))
    elif doc_type == "calc":
        for sheet in project.get("sheets", []):
            parts.append(f"<h2>{html_module.escape(sheet.get('name', 'Sheet'))}</h2>")
            parts.append(_sheet_to_html(sheet))
    elif doc_type == "impress":
        for i, slide in enumerate(project.get("slides", [])):
            parts.append(f"<section>")
            if slide.get("title"):
                parts.append(f"<h1>{html_module.escape(slide['title'])}</h1>")
            if slide.get("content"):
                parts.append(f"<p>{html_module.escape(slide['content'])}</p>")
            parts.append("</section>")
            if i < len(project.get("slides", [])) - 1:
                parts.append("<hr>")

    parts.extend(["</body>", "</html>"])
    return "\n".join(parts)


def _content_item_to_html(item: Dict[str, Any]) -> str:
    """Convert a single content item to HTML."""
    item_type = item.get("type", "paragraph")

    if item_type == "heading":
        level = item.get("level", 1)
        text = html_module.escape(item.get("text", ""))
        return f"<h{level}>{text}</h{level}>"
    elif item_type == "paragraph":
        text = html_module.escape(item.get("text", ""))
        return f"<p>{text}</p>"
    elif item_type == "list":
        tag = "ul" if item.get("list_style") == "bullet" else "ol"
        items = "".join(
            f"<li>{html_module.escape(str(i))}</li>"
            for i in item.get("items", [])
        )
        return f"<{tag}>{items}</{tag}>"
    elif item_type == "table":
        rows = item.get("data", [])
        html_rows = ""
        for row in rows:
            cells = "".join(
                f"<td>{html_module.escape(str(c))}</td>" for c in row
            )
            html_rows += f"<tr>{cells}</tr>"
        return f"<table border='1'>{html_rows}</table>"
    elif item_type == "page_break":
        return "<hr style='page-break-before: always;'>"
    return ""


def _sheet_to_html(sheet: Dict[str, Any]) -> str:
    """Convert a spreadsheet sheet to HTML table."""
    cells = sheet.get("cells", {})
    if not cells:
        return "<p>(empty sheet)</p>"

    # Determine grid bounds
    max_row = 0
    max_col = 0
    for ref in cells:
        col, row = _split_ref(ref)
        col_num = _col_to_num(col)
        row_num = int(row)
        if row_num > max_row:
            max_row = row_num
        if col_num > max_col:
            max_col = col_num

    rows = []
    for r in range(1, max_row + 1):
        row_cells = []
        for c in range(1, max_col + 1):
            ref = _num_to_col(c) + str(r)
            if ref in cells:
                val = html_module.escape(str(cells[ref].get("value", "")))
            else:
                val = ""
            row_cells.append(f"<td>{val}</td>")
        rows.append(f"<tr>{''.join(row_cells)}</tr>")

    return f"<table border='1'>{''.join(rows)}</table>"


def _build_text(project: Dict[str, Any], doc_type: str) -> str:
    """Build plain text content from a project."""
    lines = []

    if doc_type == "writer":
        for item in project.get("content", []):
            lines.append(_content_item_to_text(item))
    elif doc_type == "calc":
        for sheet in project.get("sheets", []):
            lines.append(f"=== {sheet.get('name', 'Sheet')} ===")
            lines.append(_sheet_to_text(sheet))
            lines.append("")
    elif doc_type == "impress":
        for i, slide in enumerate(project.get("slides", [])):
            lines.append(f"--- Slide {i + 1} ---")
            if slide.get("title"):
                lines.append(slide["title"])
            if slide.get("content"):
                lines.append(slide["content"])
            lines.append("")

    return "\n".join(lines)


def _content_item_to_text(item: Dict[str, Any]) -> str:
    """Convert a content item to plain text."""
    item_type = item.get("type", "paragraph")

    if item_type == "heading":
        text = item.get("text", "")
        level = item.get("level", 1)
        prefix = "#" * level + " "
        return prefix + text
    elif item_type == "paragraph":
        return item.get("text", "")
    elif item_type == "list":
        items = item.get("items", [])
        is_numbered = item.get("list_style") == "number"
        lines = []
        for i, li in enumerate(items):
            if is_numbered:
                lines.append(f"  {i + 1}. {li}")
            else:
                lines.append(f"  - {li}")
        return "\n".join(lines)
    elif item_type == "table":
        rows = item.get("data", [])
        lines = []
        for row in rows:
            lines.append("\t".join(str(c) for c in row))
        return "\n".join(lines)
    elif item_type == "page_break":
        return "\n--- Page Break ---\n"
    return ""


def _sheet_to_text(sheet: Dict[str, Any]) -> str:
    """Convert a sheet to plain text."""
    cells = sheet.get("cells", {})
    if not cells:
        return "(empty)"

    max_row = 0
    max_col = 0
    for ref in cells:
        col, row = _split_ref(ref)
        col_num = _col_to_num(col)
        row_num = int(row)
        if row_num > max_row:
            max_row = row_num
        if col_num > max_col:
            max_col = col_num

    lines = []
    for r in range(1, max_row + 1):
        row_vals = []
        for c in range(1, max_col + 1):
            ref = _num_to_col(c) + str(r)
            if ref in cells:
                row_vals.append(str(cells[ref].get("value", "")))
            else:
                row_vals.append("")
        lines.append("\t".join(row_vals))

    return "\n".join(lines)


def _split_ref(ref: str):
    """Split cell ref like A1 -> ('A', '1')."""
    col = ""
    row = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            row += ch
    return col.upper(), row


def _col_to_num(col: str) -> int:
    """A=1, B=2, ..., Z=26, AA=27."""
    result = 0
    for ch in col.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result


def _num_to_col(num: int) -> str:
    """1=A, 2=B, ..., 26=Z, 27=AA."""
    result = ""
    while num > 0:
        num, r = divmod(num - 1, 26)
        result = chr(65 + r) + result
    return result
