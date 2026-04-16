"""Custom column management — wraps calibredb custom_columns, add/remove/set_custom."""

from cli_anything.calibre.utils.calibre_backend import (
    run_calibredb,
    find_calibredb,
)

# Valid data types for custom columns
VALID_DATATYPES = {
    "rating", "text", "comments", "datetime", "int",
    "float", "bool", "series", "enumeration", "composite",
}


def list_custom_columns(library_path: str) -> list[dict]:
    """List all custom columns in the library."""
    find_calibredb()

    result = run_calibredb(["custom_columns"], library_path=library_path)

    columns = []
    for line in result["stdout"].strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: #label (Name) [datatype]
        columns.append({"raw": line})

    return columns


def add_custom_column(
    library_path: str,
    label: str,
    name: str,
    datatype: str,
    is_multiple: bool = False,
) -> dict:
    """Add a new custom column to the library."""
    find_calibredb()

    if datatype not in VALID_DATATYPES:
        raise ValueError(
            f"Invalid datatype '{datatype}'. "
            f"Valid types: {', '.join(sorted(VALID_DATATYPES))}"
        )

    # Ensure label starts with #
    if not label.startswith("#"):
        label = f"#{label}"

    cmd = ["add_custom_column", label, name, datatype]
    if is_multiple:
        cmd.append("--is-multiple")

    result = run_calibredb(cmd, library_path=library_path)
    return {
        "label": label,
        "name": name,
        "datatype": datatype,
        "is_multiple": is_multiple,
        "stdout": result["stdout"],
    }


def remove_custom_column(library_path: str, label: str, confirm: bool = True) -> dict:
    """Remove a custom column from the library."""
    find_calibredb()

    if not label.startswith("#"):
        label = f"#{label}"

    cmd = ["remove_custom_column", label]
    if confirm:
        cmd.append("--force")

    result = run_calibredb(cmd, library_path=library_path)
    return {
        "label": label,
        "stdout": result["stdout"],
    }


def set_custom_field(
    library_path: str,
    book_id: int,
    label: str,
    value: str,
) -> dict:
    """Set a custom field value on a book."""
    find_calibredb()

    if not label.startswith("#"):
        label = f"#{label}"

    result = run_calibredb(
        ["set_custom", label, str(book_id), value],
        library_path=library_path,
    )
    return {
        "book_id": book_id,
        "label": label,
        "value": value,
        "stdout": result["stdout"],
    }
