"""Import existing Office/ODF files into the LibreOffice CLI project model."""

import os
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import fromstring as _defused_fromstring
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from cli_anything.libreoffice.core.document import create_document
from cli_anything.libreoffice.utils.lo_backend import convert
from cli_anything.libreoffice.utils.odf_utils import ODF_MIMETYPES, ODF_NS, parse_odf


ODF_EXTENSION_TYPES = {
    ".odt": "writer",
    ".ott": "writer",
    ".ods": "calc",
    ".ots": "calc",
    ".odp": "impress",
    ".otp": "impress",
}

OFFICE_EXTENSION_CONVERSIONS = {
    ".doc": ("writer", "odt"),
    ".docx": ("writer", "odt"),
    ".docm": ("writer", "odt"),
    ".rtf": ("writer", "odt"),
    ".txt": ("writer", "odt"),
    ".html": ("writer", "odt"),
    ".htm": ("writer", "odt"),
    ".xls": ("calc", "ods"),
    ".xlsx": ("calc", "ods"),
    ".xlsm": ("calc", "ods"),
    ".csv": ("calc", "ods"),
    ".ppt": ("impress", "odp"),
    ".pptx": ("impress", "odp"),
    ".pptm": ("impress", "odp"),
}

SUPPORTED_IMPORT_EXTENSIONS = tuple(
    sorted(set(ODF_EXTENSION_TYPES) | set(OFFICE_EXTENSION_CONVERSIONS))
)


def can_import(path: str) -> bool:
    """Return True if the path extension is supported by the import pipeline."""
    return os.path.splitext(path)[1].lower() in SUPPORTED_IMPORT_EXTENSIONS


def list_import_formats() -> List[Dict[str, str]]:
    """List importable document extensions."""
    formats = []
    for ext, doc_type in sorted(ODF_EXTENSION_TYPES.items()):
        formats.append({
            "extension": ext,
            "type": doc_type,
            "method": "native-odf",
        })
    for ext, (doc_type, odf_format) in sorted(OFFICE_EXTENSION_CONVERSIONS.items()):
        formats.append({
            "extension": ext,
            "type": doc_type,
            "method": "libreoffice-headless",
            "intermediate": odf_format,
        })
    return formats


def import_document(path: str, name: Optional[str] = None) -> Dict[str, Any]:
    """Import an existing Office/ODF file into a CLI project dict.

    ODF files are parsed directly. Microsoft Office, legacy Office, CSV, RTF,
    HTML, and text inputs are first converted to ODF with LibreOffice headless,
    then parsed into the harness state model.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Document file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext in ODF_EXTENSION_TYPES:
        doc_type = ODF_EXTENSION_TYPES[ext]
        project = import_odf(path, doc_type=doc_type, name=name)
        project["metadata"]["import_method"] = "native-odf"
        return project

    if ext not in OFFICE_EXTENSION_CONVERSIONS:
        raise ValueError(
            f"Unsupported import format: {ext or '(none)'}. "
            f"Supported: {', '.join(SUPPORTED_IMPORT_EXTENSIONS)}"
        )

    doc_type, odf_format = OFFICE_EXTENSION_CONVERSIONS[ext]
    with tempfile.TemporaryDirectory() as tmpdir:
        odf_path = convert(path, odf_format, output_dir=tmpdir)
        project = import_odf(odf_path, doc_type=doc_type, name=name)

    project["metadata"]["import_method"] = "libreoffice-headless"
    project["metadata"]["original_format"] = ext.lstrip(".")
    project["metadata"]["source_path"] = os.path.abspath(path)
    return project


def import_odf(
    path: str,
    doc_type: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import an ODF file into a CLI project dict."""
    try:
        parsed = parse_odf(path)
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ODF file: {path}") from e

    inferred_type = doc_type or _doc_type_from_mimetype(parsed.get("mimetype", ""))
    if inferred_type not in ("writer", "calc", "impress"):
        raise ValueError(f"Unsupported ODF document type: {inferred_type}")

    project_name = name or os.path.splitext(os.path.basename(path))[0]
    project = create_document(doc_type=inferred_type, name=project_name)
    _apply_metadata(project, parsed.get("meta_xml", ""), path)

    content_xml = parsed.get("content_xml")
    if not content_xml:
        return project

    try:
        root = _defused_fromstring(content_xml)
    except ET.ParseError as e:
        raise ValueError(f"Invalid ODF content.xml in: {path}") from e
    if inferred_type == "writer":
        project["content"] = _parse_writer_content(root)
    elif inferred_type == "calc":
        project["sheets"] = _parse_calc_content(root)
        if not project["sheets"]:
            project["sheets"] = [{"name": "Sheet1", "cells": {}}]
    elif inferred_type == "impress":
        project["slides"] = _parse_impress_content(root)

    return project


def _doc_type_from_mimetype(mimetype: str) -> str:
    for doc_type, expected in ODF_MIMETYPES.items():
        if mimetype == expected:
            return doc_type
    raise ValueError(f"Unsupported or missing ODF mimetype: {mimetype}")


def _apply_metadata(project: Dict[str, Any], meta_xml: str, source_path: str) -> None:
    metadata = project.setdefault("metadata", {})
    metadata.update({
        "source_path": os.path.abspath(source_path),
        "imported_at": datetime.now().isoformat(),
    })
    if not meta_xml:
        return

    try:
        root = _defused_fromstring(meta_xml)
    except ET.ParseError as e:
        raise ValueError(f"Invalid ODF meta.xml in: {source_path}") from e

    mappings = {
        "title": ("dc", "title"),
        "author": ("dc", "creator"),
        "description": ("dc", "description"),
        "subject": ("dc", "subject"),
        "created": ("meta", "creation-date"),
        "modified": ("dc", "date"),
    }
    for key, (prefix, local) in mappings.items():
        elem = root.find(f".//{_q(prefix, local)}")
        if elem is not None and elem.text:
            metadata[key] = elem.text


def _parse_writer_content(root: ET.Element) -> List[Dict[str, Any]]:
    body = root.find(_q("office", "body"))
    text_root = body.find(_q("office", "text")) if body is not None else None
    if text_root is None:
        return []

    content = []
    for child in list(text_root):
        local = _local_name(child.tag)
        if local == "h":
            text = _text_content(child)
            if text:
                level = _int_attr(child, "text", "outline-level", default=1)
                content.append({
                    "type": "heading",
                    "level": max(1, min(level, 6)),
                    "text": text,
                    "style": {},
                })
        elif local == "p":
            text = _text_content(child)
            if text:
                content.append({"type": "paragraph", "text": text, "style": {}})
        elif local == "list":
            items = _parse_list_items(child)
            if items:
                content.append({
                    "type": "list",
                    "list_style": "bullet",
                    "items": items,
                })
        elif local == "table":
            table = _parse_writer_table(child)
            if table is not None:
                content.append(table)

    return content


def _parse_list_items(list_elem: ET.Element) -> List[str]:
    items = []
    for item_elem in _children_by_local(list_elem, "list-item"):
        text = _text_content(item_elem)
        if text:
            items.append(text)
    return items


def _parse_writer_table(table_elem: ET.Element) -> Optional[Dict[str, Any]]:
    rows = []
    max_cols = 0
    for row_elem in _children_by_local(table_elem, "table-row"):
        row_values = _parse_table_row_values(row_elem)
        if any(value != "" for value in row_values):
            rows.append(row_values)
            max_cols = max(max_cols, len(row_values))

    if not rows:
        return None

    for row in rows:
        row.extend([""] * (max_cols - len(row)))

    return {
        "type": "table",
        "rows": len(rows),
        "cols": max_cols,
        "data": rows,
    }


def _parse_calc_content(root: ET.Element) -> List[Dict[str, Any]]:
    body = root.find(_q("office", "body"))
    spreadsheet = body.find(_q("office", "spreadsheet")) if body is not None else None
    if spreadsheet is None:
        return []

    sheets = []
    for i, table_elem in enumerate(_children_by_local(spreadsheet, "table")):
        name = _attr(table_elem, "table", "name") or f"Sheet{i + 1}"
        cells = _parse_calc_cells(table_elem)
        sheets.append({"name": name, "cells": cells})
    return sheets


def _parse_calc_cells(table_elem: ET.Element) -> Dict[str, Dict[str, Any]]:
    cells: Dict[str, Dict[str, Any]] = {}
    row_index = 1

    for row_elem in _children_by_local(table_elem, "table-row"):
        row_repeat = max(1, _int_attr(row_elem, "table", "number-rows-repeated", 1))
        row_cells = _parse_calc_row(row_elem, row_index)
        if row_cells:
            for repeat_offset in range(min(row_repeat, 1000)):
                for ref, cell in row_cells.items():
                    col, row = _split_ref(ref)
                    repeated_ref = f"{col}{int(row) + repeat_offset}"
                    cells[repeated_ref] = dict(cell)
        row_index += row_repeat

    return cells


def _parse_calc_row(row_elem: ET.Element, row_index: int) -> Dict[str, Dict[str, Any]]:
    row_cells: Dict[str, Dict[str, Any]] = {}
    col_index = 1

    for cell_elem in list(row_elem):
        if _local_name(cell_elem.tag) not in ("table-cell", "covered-table-cell"):
            continue

        col_repeat = max(1, _int_attr(cell_elem, "table", "number-columns-repeated", 1))
        cell_data = _cell_data(cell_elem)
        if cell_data is not None:
            for repeat_offset in range(min(col_repeat, 1000)):
                ref = f"{_num_to_col(col_index + repeat_offset)}{row_index}"
                row_cells[ref] = dict(cell_data)
        col_index += col_repeat

    return row_cells


def _cell_data(cell_elem: ET.Element) -> Optional[Dict[str, Any]]:
    value_type = _attr(cell_elem, "office", "value-type") or "string"
    formula = _normalize_formula(_attr(cell_elem, "table", "formula"))
    text = _text_content(cell_elem)
    numeric_value = _attr(cell_elem, "office", "value")

    if not formula and not numeric_value and not text:
        return None

    if value_type in ("float", "currency", "percentage") and numeric_value is not None:
        try:
            value: Any = float(numeric_value)
            cell_type = "float"
        except ValueError:
            value = numeric_value
            cell_type = "string"
    elif value_type == "boolean":
        value = (_attr(cell_elem, "office", "boolean-value") or text).lower() == "true"
        cell_type = "boolean"
    else:
        value = text if text != "" else (numeric_value or "")
        cell_type = "string"

    data = {"value": value, "type": cell_type}
    if formula:
        data["formula"] = formula
    return data


def _normalize_formula(formula: Optional[str]) -> Optional[str]:
    """Strip ODF formula namespace prefixes before storing project state."""
    if formula is None:
        return None
    for prefix in ("of:", "oooc:"):
        if formula.startswith(prefix):
            return formula[len(prefix):]
    return formula


def _parse_impress_content(root: ET.Element) -> List[Dict[str, Any]]:
    body = root.find(_q("office", "body"))
    presentation = body.find(_q("office", "presentation")) if body is not None else None
    if presentation is None:
        return []

    slides = []
    for page in _children_by_local(presentation, "page"):
        texts = [_text_content(elem) for elem in page.iter() if _local_name(elem.tag) in ("h", "p")]
        texts = [text for text in texts if text]
        title = texts[0] if texts else (_attr(page, "draw", "name") or "")
        content = "\n".join(texts[1:]) if len(texts) > 1 else ""
        slides.append({
            "title": title,
            "content": content,
            "elements": [],
        })
    return slides


def _parse_table_row_values(row_elem: ET.Element) -> List[str]:
    values = []
    for cell_elem in list(row_elem):
        if _local_name(cell_elem.tag) not in ("table-cell", "covered-table-cell"):
            continue
        repeat = max(1, _int_attr(cell_elem, "table", "number-columns-repeated", 1))
        text = _text_content(cell_elem)
        for _ in range(min(repeat, 1000)):
            values.append(text)
    return values


def _children_by_local(elem: ET.Element, local_name: str) -> List[ET.Element]:
    return [child for child in list(elem) if _local_name(child.tag) == local_name]


def _text_content(elem: ET.Element) -> str:
    return "".join(elem.itertext()).strip()


def _q(prefix: str, local: str) -> str:
    return f"{{{ODF_NS[prefix]}}}{local}"


def _attr(elem: ET.Element, prefix: str, local: str) -> Optional[str]:
    return elem.get(_q(prefix, local))


def _int_attr(elem: ET.Element, prefix: str, local: str, default: int = 1) -> int:
    value = _attr(elem, prefix, local)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _num_to_col(num: int) -> str:
    result = ""
    while num > 0:
        num, rem = divmod(num - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def _split_ref(ref: str) -> Tuple[str, str]:
    col = ""
    row = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            row += ch
    return col, row
