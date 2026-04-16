"""LibreOffice CLI - ODF XML helpers.

ODF (Open Document Format) files are ZIP archives containing XML files.
This module provides utilities for creating, parsing, and writing ODF documents.

Key ODF structure:
  mimetype          - MIME type (stored uncompressed, first entry)
  content.xml       - Document content
  styles.xml        - Document styles
  meta.xml          - Metadata
  META-INF/manifest.xml - Manifest of all files in the archive
"""

import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from datetime import datetime


# ODF XML Namespaces
ODF_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
    "number": "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
}

# MIME types for ODF document types
ODF_MIMETYPES = {
    "writer": "application/vnd.oasis.opendocument.text",
    "calc": "application/vnd.oasis.opendocument.spreadsheet",
    "impress": "application/vnd.oasis.opendocument.presentation",
}

# File extensions for ODF document types
ODF_EXTENSIONS = {
    "writer": ".odt",
    "calc": ".ods",
    "impress": ".odp",
}


def _register_namespaces():
    """Register all ODF namespaces with ElementTree to preserve prefixes."""
    for prefix, uri in ODF_NS.items():
        ET.register_namespace(prefix, uri)


def _ns(prefix: str, local: str) -> str:
    """Create a fully-qualified XML element name."""
    return f"{{{ODF_NS[prefix]}}}{local}"


def _nsattr(prefix: str, local: str) -> str:
    """Create a fully-qualified XML attribute name."""
    return f"{{{ODF_NS[prefix]}}}{local}"


def create_content_xml(doc_type: str, project: Dict[str, Any]) -> str:
    """Create content.xml for an ODF document from a project dict."""
    _register_namespaces()

    # Root element
    root = ET.Element(_ns("office", "document-content"))
    root.set(_nsattr("office", "version"), "1.2")

    # Automatic styles
    auto_styles = ET.SubElement(root, _ns("office", "automatic-styles"))

    if doc_type == "writer":
        _build_writer_content(root, auto_styles, project)
    elif doc_type == "calc":
        _build_calc_content(root, auto_styles, project)
    elif doc_type == "impress":
        _build_impress_content(root, auto_styles, project)

    return _xml_to_string(root)


def _build_writer_content(root: ET.Element, auto_styles: ET.Element,
                          project: Dict[str, Any]) -> None:
    """Build Writer content.xml body."""
    body = ET.SubElement(root, _ns("office", "body"))
    text_elem = ET.SubElement(body, _ns("office", "text"))

    content_items = project.get("content", [])
    style_counter = [0]

    for item in content_items:
        item_type = item.get("type", "paragraph")

        if item_type == "heading":
            _add_heading_element(text_elem, auto_styles, item, style_counter)
        elif item_type == "paragraph":
            _add_paragraph_element(text_elem, auto_styles, item, style_counter)
        elif item_type == "list":
            _add_list_element(text_elem, auto_styles, item, style_counter)
        elif item_type == "table":
            _add_table_element(text_elem, auto_styles, item, style_counter)
        elif item_type == "page_break":
            _add_page_break_element(text_elem, auto_styles, style_counter)
        elif item_type == "image_ref":
            _add_image_ref_element(text_elem, auto_styles, item, style_counter)


def _add_heading_element(parent: ET.Element, auto_styles: ET.Element,
                         item: Dict, style_counter: list) -> None:
    """Add a heading element to the content."""
    heading = ET.SubElement(parent, _ns("text", "h"))
    heading.set(_nsattr("text", "outline-level"), str(item.get("level", 1)))
    style = item.get("style", {})

    if style:
        style_name = f"H_auto{style_counter[0]}"
        style_counter[0] += 1
        heading.set(_nsattr("text", "style-name"), style_name)
        _create_text_auto_style(auto_styles, style_name, style, parent_style="Heading")
    heading.text = item.get("text", "")


def _add_paragraph_element(parent: ET.Element, auto_styles: ET.Element,
                           item: Dict, style_counter: list) -> None:
    """Add a paragraph element to the content."""
    para = ET.SubElement(parent, _ns("text", "p"))
    style = item.get("style", {})

    if style:
        style_name = f"P_auto{style_counter[0]}"
        style_counter[0] += 1
        para.set(_nsattr("text", "style-name"), style_name)
        _create_text_auto_style(auto_styles, style_name, style)

    text = item.get("text", "")

    # Handle styled spans within text
    spans = item.get("spans", [])
    if spans:
        last_end = 0
        for span_info in spans:
            start = span_info.get("start", 0)
            end = span_info.get("end", len(text))
            span_style = span_info.get("style", {})

            # Text before span
            if start > last_end:
                if para.text is None:
                    para.text = text[last_end:start]
                else:
                    # Add as tail of last sub-element
                    children = list(para)
                    if children:
                        if children[-1].tail is None:
                            children[-1].tail = text[last_end:start]
                        else:
                            children[-1].tail += text[last_end:start]
                    else:
                        para.text = (para.text or "") + text[last_end:start]

            # Span element
            span_style_name = f"S_auto{style_counter[0]}"
            style_counter[0] += 1
            span = ET.SubElement(para, _ns("text", "span"))
            span.set(_nsattr("text", "style-name"), span_style_name)
            span.text = text[start:end]
            _create_char_auto_style(auto_styles, span_style_name, span_style)

            last_end = end

        # Text after last span
        if last_end < len(text):
            children = list(para)
            if children:
                if children[-1].tail is None:
                    children[-1].tail = text[last_end:]
                else:
                    children[-1].tail += text[last_end:]
            else:
                para.text = (para.text or "") + text[last_end:]
    else:
        para.text = text


def _add_list_element(parent: ET.Element, auto_styles: ET.Element,
                      item: Dict, style_counter: list) -> None:
    """Add a list element to the content."""
    list_style = item.get("style", "bullet")
    list_elem = ET.SubElement(parent, _ns("text", "list"))

    for list_item in item.get("items", []):
        li = ET.SubElement(list_elem, _ns("text", "list-item"))
        para = ET.SubElement(li, _ns("text", "p"))
        para.text = str(list_item)


def _add_table_element(parent: ET.Element, auto_styles: ET.Element,
                       item: Dict, style_counter: list) -> None:
    """Add a table element to the content."""
    table_name = f"Table{style_counter[0]}"
    style_counter[0] += 1

    table = ET.SubElement(parent, _ns("table", "table"))
    table.set(_nsattr("table", "name"), table_name)

    cols = item.get("cols", 0)
    rows_data = item.get("data", [])

    # Columns
    for c in range(cols):
        col = ET.SubElement(table, _ns("table", "table-column"))

    # Rows
    for row_data in rows_data:
        row = ET.SubElement(table, _ns("table", "table-row"))
        for cell_value in row_data:
            cell = ET.SubElement(row, _ns("table", "table-cell"))
            para = ET.SubElement(cell, _ns("text", "p"))
            para.text = str(cell_value)


def _add_page_break_element(parent: ET.Element, auto_styles: ET.Element,
                            style_counter: list) -> None:
    """Add a page break element."""
    style_name = f"PB_auto{style_counter[0]}"
    style_counter[0] += 1

    # Create a style with page-break-before
    style_el = ET.SubElement(auto_styles, _ns("style", "style"))
    style_el.set(_nsattr("style", "name"), style_name)
    style_el.set(_nsattr("style", "family"), "paragraph")
    pp = ET.SubElement(style_el, _ns("style", "paragraph-properties"))
    pp.set(_nsattr("fo", "break-before"), "page")

    para = ET.SubElement(parent, _ns("text", "p"))
    para.set(_nsattr("text", "style-name"), style_name)


def _add_image_ref_element(parent: ET.Element, auto_styles: ET.Element,
                           item: Dict, style_counter: list) -> None:
    """Add an image reference (frame) element."""
    para = ET.SubElement(parent, _ns("text", "p"))
    frame = ET.SubElement(para, _ns("draw", "frame"))
    frame.set(_nsattr("draw", "name"), item.get("name", "Image"))
    frame.set(_nsattr("svg", "width"), item.get("width", "10cm"))
    frame.set(_nsattr("svg", "height"), item.get("height", "10cm"))
    image = ET.SubElement(frame, _ns("draw", "image"))
    image.set(_nsattr("xlink", "href"), item.get("path", ""))
    image.set(_nsattr("xlink", "type"), "simple")
    image.set(_nsattr("xlink", "show"), "embed")
    image.set(_nsattr("xlink", "actuate"), "onLoad")


def _create_text_auto_style(auto_styles: ET.Element, name: str,
                            style: Dict, parent_style: str = "Standard") -> None:
    """Create an automatic paragraph style."""
    style_el = ET.SubElement(auto_styles, _ns("style", "style"))
    style_el.set(_nsattr("style", "name"), name)
    style_el.set(_nsattr("style", "family"), "paragraph")

    # Text properties
    tp = ET.SubElement(style_el, _ns("style", "text-properties"))
    if "font_size" in style:
        tp.set(_nsattr("fo", "font-size"), str(style["font_size"]))
    if "font_name" in style:
        tp.set(_nsattr("fo", "font-family"), str(style["font_name"]))
    if style.get("bold"):
        tp.set(_nsattr("fo", "font-weight"), "bold")
    if style.get("italic"):
        tp.set(_nsattr("fo", "font-style"), "italic")
    if style.get("underline"):
        tp.set(_nsattr("style", "text-underline-style"), "solid")
        tp.set(_nsattr("style", "text-underline-width"), "auto")
    if "color" in style:
        tp.set(_nsattr("fo", "color"), str(style["color"]))

    # Paragraph properties
    pp = ET.SubElement(style_el, _ns("style", "paragraph-properties"))
    if "alignment" in style:
        pp.set(_nsattr("fo", "text-align"), str(style["alignment"]))


def _create_char_auto_style(auto_styles: ET.Element, name: str,
                            style: Dict) -> None:
    """Create an automatic character style for spans."""
    style_el = ET.SubElement(auto_styles, _ns("style", "style"))
    style_el.set(_nsattr("style", "name"), name)
    style_el.set(_nsattr("style", "family"), "text")

    tp = ET.SubElement(style_el, _ns("style", "text-properties"))
    if "font_size" in style:
        tp.set(_nsattr("fo", "font-size"), str(style["font_size"]))
    if "font_name" in style:
        tp.set(_nsattr("fo", "font-family"), str(style["font_name"]))
    if style.get("bold"):
        tp.set(_nsattr("fo", "font-weight"), "bold")
    if style.get("italic"):
        tp.set(_nsattr("fo", "font-style"), "italic")
    if style.get("underline"):
        tp.set(_nsattr("style", "text-underline-style"), "solid")
        tp.set(_nsattr("style", "text-underline-width"), "auto")
    if "color" in style:
        tp.set(_nsattr("fo", "color"), str(style["color"]))


def _build_calc_content(root: ET.Element, auto_styles: ET.Element,
                        project: Dict[str, Any]) -> None:
    """Build Calc content.xml body."""
    body = ET.SubElement(root, _ns("office", "body"))
    spreadsheet = ET.SubElement(body, _ns("office", "spreadsheet"))

    sheets = project.get("sheets", [])
    for sheet_data in sheets:
        table = ET.SubElement(spreadsheet, _ns("table", "table"))
        table.set(_nsattr("table", "name"), sheet_data.get("name", "Sheet1"))

        cells = sheet_data.get("cells", {})
        if not cells:
            # Empty sheet with at least one row/cell
            row = ET.SubElement(table, _ns("table", "table-row"))
            cell = ET.SubElement(row, _ns("table", "table-cell"))
            continue

        # Determine the grid bounds
        max_row, max_col = _get_grid_bounds(cells)

        for r in range(1, max_row + 1):
            row_elem = ET.SubElement(table, _ns("table", "table-row"))
            for c in range(1, max_col + 1):
                cell_ref = _col_letter(c) + str(r)
                cell_elem = ET.SubElement(row_elem, _ns("table", "table-cell"))

                if cell_ref in cells:
                    cell_data = cells[cell_ref]
                    if "formula" in cell_data:
                        cell_elem.set(_nsattr("table", "formula"),
                                      f"of:{cell_data['formula']}")
                        cell_elem.set(_nsattr("office", "value-type"), "float")
                    elif cell_data.get("type") == "float":
                        cell_elem.set(_nsattr("office", "value-type"), "float")
                        cell_elem.set(_nsattr("office", "value"),
                                      str(cell_data.get("value", 0)))
                    else:
                        cell_elem.set(_nsattr("office", "value-type"), "string")

                    para = ET.SubElement(cell_elem, _ns("text", "p"))
                    para.text = str(cell_data.get("value", ""))


def _build_impress_content(root: ET.Element, auto_styles: ET.Element,
                           project: Dict[str, Any]) -> None:
    """Build Impress content.xml body."""
    body = ET.SubElement(root, _ns("office", "body"))
    pres = ET.SubElement(body, _ns("office", "presentation"))

    slides = project.get("slides", [])
    for i, slide_data in enumerate(slides):
        page = ET.SubElement(pres, _ns("draw", "page"))
        page.set(_nsattr("draw", "name"), slide_data.get("title", f"Slide {i+1}"))
        page.set(_nsattr("draw", "master-page-name"), "Default")

        # Title text box
        if slide_data.get("title"):
            frame = ET.SubElement(page, _ns("draw", "frame"))
            frame.set(_nsattr("svg", "x"), "2cm")
            frame.set(_nsattr("svg", "y"), "1cm")
            frame.set(_nsattr("svg", "width"), "22cm")
            frame.set(_nsattr("svg", "height"), "3cm")
            frame.set(_nsattr("presentation", "class"), "title")
            tb = ET.SubElement(frame, _ns("draw", "text-box"))
            para = ET.SubElement(tb, _ns("text", "p"))
            para.text = slide_data["title"]

        # Content text box
        if slide_data.get("content"):
            frame = ET.SubElement(page, _ns("draw", "frame"))
            frame.set(_nsattr("svg", "x"), "2cm")
            frame.set(_nsattr("svg", "y"), "5cm")
            frame.set(_nsattr("svg", "width"), "22cm")
            frame.set(_nsattr("svg", "height"), "13cm")
            frame.set(_nsattr("presentation", "class"), "subtitle")
            tb = ET.SubElement(frame, _ns("draw", "text-box"))
            para = ET.SubElement(tb, _ns("text", "p"))
            para.text = slide_data["content"]

        # Additional elements
        for elem in slide_data.get("elements", []):
            if elem.get("type") == "text_box":
                frame = ET.SubElement(page, _ns("draw", "frame"))
                frame.set(_nsattr("svg", "x"), elem.get("x", "2cm"))
                frame.set(_nsattr("svg", "y"), elem.get("y", "2cm"))
                frame.set(_nsattr("svg", "width"), elem.get("width", "10cm"))
                frame.set(_nsattr("svg", "height"), elem.get("height", "5cm"))
                tb = ET.SubElement(frame, _ns("draw", "text-box"))
                para = ET.SubElement(tb, _ns("text", "p"))
                para.text = elem.get("text", "")


def create_styles_xml(doc_type: str, project: Dict[str, Any]) -> str:
    """Create styles.xml for an ODF document."""
    _register_namespaces()

    root = ET.Element(_ns("office", "document-styles"))
    root.set(_nsattr("office", "version"), "1.2")

    styles = ET.SubElement(root, _ns("office", "styles"))

    # Default paragraph style
    default_style = ET.SubElement(styles, _ns("style", "default-style"))
    default_style.set(_nsattr("style", "family"), "paragraph")
    tp = ET.SubElement(default_style, _ns("style", "text-properties"))
    tp.set(_nsattr("fo", "font-size"), "12pt")
    tp.set(_nsattr("fo", "font-family"), "Liberation Serif")

    # User-defined styles
    user_styles = project.get("styles", {})
    for style_name, style_def in user_styles.items():
        family = style_def.get("family", "paragraph")
        style_el = ET.SubElement(styles, _ns("style", "style"))
        style_el.set(_nsattr("style", "name"), style_name)
        style_el.set(_nsattr("style", "family"), family)
        if "parent" in style_def:
            style_el.set(_nsattr("style", "parent-style-name"), style_def["parent"])

        props = style_def.get("properties", {})
        if family == "paragraph":
            tp = ET.SubElement(style_el, _ns("style", "text-properties"))
            _apply_text_properties(tp, props)
            pp = ET.SubElement(style_el, _ns("style", "paragraph-properties"))
            _apply_paragraph_properties(pp, props)
        elif family == "text":
            tp = ET.SubElement(style_el, _ns("style", "text-properties"))
            _apply_text_properties(tp, props)

    # Automatic styles
    auto_styles = ET.SubElement(root, _ns("office", "automatic-styles"))

    # Page layout for writer
    if doc_type == "writer":
        settings = project.get("settings", {})
        pl = ET.SubElement(auto_styles, _ns("style", "page-layout"))
        pl.set(_nsattr("style", "name"), "PM1")
        plp = ET.SubElement(pl, _ns("style", "page-layout-properties"))
        plp.set(_nsattr("fo", "page-width"), settings.get("page_width", "21cm"))
        plp.set(_nsattr("fo", "page-height"), settings.get("page_height", "29.7cm"))
        plp.set(_nsattr("fo", "margin-top"), settings.get("margin_top", "2cm"))
        plp.set(_nsattr("fo", "margin-bottom"), settings.get("margin_bottom", "2cm"))
        plp.set(_nsattr("fo", "margin-left"), settings.get("margin_left", "2cm"))
        plp.set(_nsattr("fo", "margin-right"), settings.get("margin_right", "2cm"))

    # Master styles
    master_styles = ET.SubElement(root, _ns("office", "master-styles"))
    mp = ET.SubElement(master_styles, _ns("style", "master-page"))
    mp.set(_nsattr("style", "name"), "Default")
    if doc_type == "writer":
        mp.set(_nsattr("style", "page-layout-name"), "PM1")

    return _xml_to_string(root)


def _apply_text_properties(tp: ET.Element, props: Dict) -> None:
    """Apply text properties from a style dict to an XML element."""
    if "font_size" in props:
        tp.set(_nsattr("fo", "font-size"), str(props["font_size"]))
    if "font_name" in props:
        tp.set(_nsattr("fo", "font-family"), str(props["font_name"]))
    if props.get("bold"):
        tp.set(_nsattr("fo", "font-weight"), "bold")
    if props.get("italic"):
        tp.set(_nsattr("fo", "font-style"), "italic")
    if props.get("underline"):
        tp.set(_nsattr("style", "text-underline-style"), "solid")
    if "color" in props:
        tp.set(_nsattr("fo", "color"), str(props["color"]))


def _apply_paragraph_properties(pp: ET.Element, props: Dict) -> None:
    """Apply paragraph properties from a style dict to an XML element."""
    if "alignment" in props:
        pp.set(_nsattr("fo", "text-align"), str(props["alignment"]))
    if "line_height" in props:
        pp.set(_nsattr("fo", "line-height"), str(props["line_height"]))
    if "margin_top" in props:
        pp.set(_nsattr("fo", "margin-top"), str(props["margin_top"]))
    if "margin_bottom" in props:
        pp.set(_nsattr("fo", "margin-bottom"), str(props["margin_bottom"]))


def create_meta_xml(project: Dict[str, Any]) -> str:
    """Create meta.xml for an ODF document."""
    _register_namespaces()

    root = ET.Element(_ns("office", "document-meta"))
    root.set(_nsattr("office", "version"), "1.2")

    meta = ET.SubElement(root, _ns("office", "meta"))
    metadata = project.get("metadata", {})

    # Title
    title = ET.SubElement(meta, _ns("dc", "title"))
    title.text = metadata.get("title", project.get("name", ""))

    # Author / creator
    creator = ET.SubElement(meta, _ns("meta", "initial-creator"))
    creator.text = metadata.get("author", "libreoffice-cli")

    # Description
    desc = ET.SubElement(meta, _ns("dc", "description"))
    desc.text = metadata.get("description", "")

    # Subject
    subject = ET.SubElement(meta, _ns("dc", "subject"))
    subject.text = metadata.get("subject", "")

    # Creation date
    creation = ET.SubElement(meta, _ns("meta", "creation-date"))
    creation.text = metadata.get("created", datetime.now().isoformat())

    # Generator
    gen = ET.SubElement(meta, _ns("meta", "generator"))
    gen.text = "libreoffice-cli/1.0"

    return _xml_to_string(root)


def create_manifest_xml(doc_type: str) -> str:
    """Create META-INF/manifest.xml."""
    _register_namespaces()

    root = ET.Element(_ns("manifest", "manifest"))
    # Namespace is set automatically by _register_namespaces()
    root.set(_nsattr("manifest", "version"), "1.2")

    mimetype = ODF_MIMETYPES.get(doc_type, ODF_MIMETYPES["writer"])

    # Root entry
    entry = ET.SubElement(root, _ns("manifest", "file-entry"))
    entry.set(_nsattr("manifest", "full-path"), "/")
    entry.set(_nsattr("manifest", "version"), "1.2")
    entry.set(_nsattr("manifest", "media-type"), mimetype)

    # content.xml
    entry = ET.SubElement(root, _ns("manifest", "file-entry"))
    entry.set(_nsattr("manifest", "full-path"), "content.xml")
    entry.set(_nsattr("manifest", "media-type"), "text/xml")

    # styles.xml
    entry = ET.SubElement(root, _ns("manifest", "file-entry"))
    entry.set(_nsattr("manifest", "full-path"), "styles.xml")
    entry.set(_nsattr("manifest", "media-type"), "text/xml")

    # meta.xml
    entry = ET.SubElement(root, _ns("manifest", "file-entry"))
    entry.set(_nsattr("manifest", "full-path"), "meta.xml")
    entry.set(_nsattr("manifest", "media-type"), "text/xml")

    return _xml_to_string(root)


def write_odf(path: str, doc_type: str, project: Dict[str, Any]) -> str:
    """Write a complete ODF file (ZIP archive) from a project dict.

    The mimetype entry must be stored uncompressed as the first entry
    in the ZIP (ODF specification requirement).
    """
    mimetype = ODF_MIMETYPES.get(doc_type, ODF_MIMETYPES["writer"])
    content_xml = create_content_xml(doc_type, project)
    styles_xml = create_styles_xml(doc_type, project)
    meta_xml = create_meta_xml(project)
    manifest_xml = create_manifest_xml(doc_type)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype MUST be first and MUST be stored uncompressed
        zf.writestr(
            zipfile.ZipInfo("mimetype", date_time=(2024, 1, 1, 0, 0, 0)),
            mimetype,
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("content.xml", content_xml)
        zf.writestr("styles.xml", styles_xml)
        zf.writestr("meta.xml", meta_xml)
        zf.writestr("META-INF/manifest.xml", manifest_xml)

    return os.path.abspath(path)


def parse_odf(path: str) -> Dict[str, Any]:
    """Parse an ODF file and return a dict of its XML contents."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"ODF file not found: {path}")

    result = {}
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        result["files"] = names

        if "mimetype" in names:
            result["mimetype"] = zf.read("mimetype").decode("utf-8")

        if "content.xml" in names:
            result["content_xml"] = zf.read("content.xml").decode("utf-8")

        if "styles.xml" in names:
            result["styles_xml"] = zf.read("styles.xml").decode("utf-8")

        if "meta.xml" in names:
            result["meta_xml"] = zf.read("meta.xml").decode("utf-8")

        if "META-INF/manifest.xml" in names:
            result["manifest_xml"] = zf.read("META-INF/manifest.xml").decode("utf-8")

    return result


def validate_odf(path: str) -> Dict[str, Any]:
    """Validate an ODF file structure."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    errors = []
    warnings = []
    names = []

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()

            # Check mimetype
            if "mimetype" not in names:
                errors.append("Missing 'mimetype' entry")
            else:
                # Check mimetype is first entry
                if names[0] != "mimetype":
                    warnings.append("'mimetype' is not the first entry in ZIP")

                # Check mimetype is stored uncompressed
                info = zf.getinfo("mimetype")
                if info.compress_type != zipfile.ZIP_STORED:
                    warnings.append("'mimetype' entry is compressed (should be stored)")

                mimetype = zf.read("mimetype").decode("utf-8")
                if mimetype not in ODF_MIMETYPES.values():
                    warnings.append(f"Unknown mimetype: {mimetype}")

            # Check required files
            for required in ["content.xml", "META-INF/manifest.xml"]:
                if required not in names:
                    errors.append(f"Missing required file: {required}")

            # Validate XML in content.xml
            if "content.xml" in names:
                try:
                    ET.fromstring(zf.read("content.xml"))
                except ET.ParseError as e:
                    errors.append(f"Invalid XML in content.xml: {e}")

            # Validate XML in styles.xml
            if "styles.xml" in names:
                try:
                    ET.fromstring(zf.read("styles.xml"))
                except ET.ParseError as e:
                    errors.append(f"Invalid XML in styles.xml: {e}")

            # Validate XML in meta.xml
            if "meta.xml" in names:
                try:
                    ET.fromstring(zf.read("meta.xml"))
                except ET.ParseError as e:
                    errors.append(f"Invalid XML in meta.xml: {e}")

    except zipfile.BadZipFile:
        errors.append("Not a valid ZIP file")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "file_count": len(names) if not errors else 0,
    }


def _get_grid_bounds(cells: Dict[str, Any]) -> tuple:
    """Get the maximum row and column from a cells dictionary."""
    max_row = 0
    max_col = 0
    for ref in cells:
        col_str, row_str = _split_cell_ref(ref)
        row_num = int(row_str)
        col_num = _col_number(col_str)
        if row_num > max_row:
            max_row = row_num
        if col_num > max_col:
            max_col = col_num
    return max_row, max_col


def _split_cell_ref(ref: str) -> tuple:
    """Split a cell reference like 'A1' into ('A', '1')."""
    col = ""
    row = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            row += ch
    return col.upper(), row


def _col_number(col_str: str) -> int:
    """Convert column letter(s) to number: A=1, B=2, ..., Z=26, AA=27."""
    result = 0
    for ch in col_str:
        result = result * 26 + (ord(ch.upper()) - ord('A') + 1)
    return result


def _col_letter(col_num: int) -> str:
    """Convert column number to letter(s): 1=A, 2=B, ..., 26=Z, 27=AA."""
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xml_to_string(root: ET.Element) -> str:
    """Convert an ElementTree element to a string with XML declaration."""
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode", xml_declaration=False
    )
