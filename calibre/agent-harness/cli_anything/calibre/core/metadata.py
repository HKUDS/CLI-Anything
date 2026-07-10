"""Metadata operations — wraps calibredb set_metadata, show_metadata, embed_metadata."""

from cli_anything.calibre.utils.calibre_backend import (
    run_calibredb,
    find_calibredb,
)

# Fields that calibredb set_metadata --field supports
SETTABLE_FIELDS = {
    "title", "authors", "tags", "series", "series_index",
    "rating", "publisher", "pubdate", "comments", "languages",
    "cover", "identifiers",
}


def get_metadata(library_path: str, book_id: int) -> dict:
    """Retrieve all metadata for a book as a dict."""
    find_calibredb()

    result = run_calibredb(
        ["show_metadata", "--as-opf", str(book_id)],
        library_path=library_path,
    )

    # Parse the OPF XML output into a simple dict
    return _parse_opf_to_dict(result["stdout"], book_id)


def set_metadata(
    library_path: str,
    book_id: int,
    field: str,
    value: str,
) -> dict:
    """Set a single metadata field on a book."""
    find_calibredb()

    result = run_calibredb(
        ["set_metadata", str(book_id), f"--field={field}:{value}"],
        library_path=library_path,
    )
    return {
        "book_id": book_id,
        "field": field,
        "value": value,
        "stdout": result["stdout"],
    }


def set_metadata_batch(
    library_path: str,
    book_id: int,
    fields: dict[str, str],
) -> dict:
    """Set multiple metadata fields on a book in a single calibredb call."""
    find_calibredb()

    field_args = []
    for field, value in fields.items():
        field_args.extend([f"--field={field}:{value}"])

    result = run_calibredb(
        ["set_metadata", str(book_id)] + field_args,
        library_path=library_path,
    )
    return {
        "book_id": book_id,
        "fields": fields,
        "stdout": result["stdout"],
    }


def embed_metadata(library_path: str, book_ids: list[int]) -> dict:
    """Embed library metadata into the actual book files (EPUB, etc.)."""
    find_calibredb()

    ids_str = ",".join(str(i) for i in book_ids)
    result = run_calibredb(
        ["embed_metadata", ids_str],
        library_path=library_path,
    )
    return {
        "book_ids": book_ids,
        "count": len(book_ids),
        "stdout": result["stdout"],
    }


def _parse_opf_to_dict(opf_xml: str, book_id: int) -> dict:
    """Parse OPF XML into a flat metadata dict."""
    import xml.etree.ElementTree as ET

    meta: dict = {"id": book_id, "raw_opf": opf_xml}

    try:
        # OPF uses namespaces
        ns = {
            "opf": "http://www.idpf.org/2007/opf",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        root = ET.fromstring(opf_xml)
        metadata_el = root.find("opf:metadata", ns)
        if metadata_el is None:
            metadata_el = root.find("metadata")
        if metadata_el is None:
            return meta

        def _text(tag: str, namespace: str = "dc") -> str:
            el = metadata_el.find(f"{namespace}:{tag}", ns)
            return el.text.strip() if el is not None and el.text else ""

        meta["title"] = _text("title")
        meta["publisher"] = _text("publisher")
        meta["language"] = _text("language")
        meta["description"] = _text("description")

        authors = [
            el.text.strip()
            for el in metadata_el.findall("dc:creator", ns)
            if el.text
        ]
        meta["authors"] = authors

        tags = [
            el.text.strip()
            for el in metadata_el.findall("dc:subject", ns)
            if el.text
        ]
        meta["tags"] = tags

        identifiers = {}
        for el in metadata_el.findall("dc:identifier", ns):
            scheme = el.get("{http://www.idpf.org/2007/opf}scheme", "")
            if scheme and el.text:
                identifiers[scheme.lower()] = el.text.strip()
        meta["identifiers"] = identifiers

        # Calibre-specific meta tags
        for el in metadata_el.findall("opf:meta", ns):
            name = el.get("name", "")
            content = el.get("content", "")
            if name == "calibre:series":
                meta["series"] = content
            elif name == "calibre:series_index":
                try:
                    meta["series_index"] = float(content)
                except ValueError:
                    pass
            elif name == "calibre:rating":
                try:
                    meta["rating"] = float(content)
                except ValueError:
                    pass

    except ET.ParseError:
        pass

    return meta
