"""FreeCAD CLI - Spreadsheet module for parametric data tables.

Manages spreadsheet creation and cell manipulation within the JSON-based
project state.  Spreadsheets can store raw values, formulas (prefixed
with ``=``), and named aliases for parametric linking.
"""

import csv
import io
import os
import re
from typing import Any, Dict, List, Optional, Union

from cli_anything.freecad.core.document import ensure_collection


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CELL_REF_RE = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")
_ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_id(project: Dict[str, Any]) -> int:
    """Return the next available integer ID for spreadsheets."""
    items = project.get("spreadsheets", [])
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


def _unique_name(project: Dict[str, Any], base: str) -> str:
    """Return a unique spreadsheet name derived from *base*."""
    existing = {item["name"] for item in project.get("spreadsheets", [])}
    if base not in existing:
        return base
    counter = 2
    while f"{base}_{counter}" in existing:
        counter += 1
    return f"{base}_{counter}"


def _validate_cell_ref(cell_ref: str) -> str:
    """Validate and return a normalised cell reference (upper-case).

    Raises ``ValueError`` if the reference is malformed.
    """
    if not isinstance(cell_ref, str):
        raise ValueError(
            f"Cell reference must be a string, got {type(cell_ref).__name__}"
        )
    ref = cell_ref.strip().upper()
    if not _CELL_REF_RE.match(ref):
        raise ValueError(
            f"Invalid cell reference '{cell_ref}'. "
            f"Expected format like A1, B2, AA23 (1-3 uppercase letters + row number >= 1)"
        )
    return ref


def _get_sheet(project: Dict[str, Any], sheet_index: int) -> Dict[str, Any]:
    """Return the spreadsheet at *sheet_index*.

    Raises ``IndexError`` when the index is out of range.
    """
    sheets = project.get("spreadsheets", [])
    if not isinstance(sheet_index, int) or sheet_index < 0 or sheet_index >= len(sheets):
        raise IndexError(
            f"Spreadsheet index {sheet_index} out of range "
            f"(0..{len(sheets) - 1})"
        )
    return sheets[sheet_index]


def _parse_cell_ref(cell_ref: str):
    """Split a cell reference into (column_letters, row_number)."""
    match = re.match(r"^([A-Z]{1,3})([1-9][0-9]*)$", cell_ref)
    if not match:
        raise ValueError(f"Cannot parse cell reference '{cell_ref}'")
    return match.group(1), int(match.group(2))


def _col_to_index(col: str) -> int:
    """Convert column letters to a zero-based index (A=0, B=1, ..., Z=25, AA=26)."""
    result = 0
    for ch in col:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def _index_to_col(index: int) -> str:
    """Convert a zero-based column index back to letters."""
    result = []
    index += 1  # 1-based
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result.append(chr(ord("A") + remainder))
    return "".join(reversed(result))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_spreadsheet(
    project: Dict[str, Any], name: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new spreadsheet and append it to the project.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    name : str or None
        Label for the spreadsheet.  Auto-generated when *None*.

    Returns
    -------
    dict
        The newly created spreadsheet dictionary.
    """
    sheets = ensure_collection(project, "spreadsheets")

    if name is None:
        name = _unique_name(project, "Spreadsheet")
    elif not isinstance(name, str) or not name.strip():
        raise ValueError("Spreadsheet name must be a non-empty string")
    else:
        name = name.strip()

    sheet: Dict[str, Any] = {
        "id": _next_id(project),
        "name": name,
        "cells": {},
        "aliases": {},
    }

    sheets.append(sheet)
    return sheet


def set_cell(
    project: Dict[str, Any],
    sheet_index: int,
    cell_ref: str,
    value: Union[str, int, float],
) -> Dict[str, Any]:
    """Set a cell value in a spreadsheet.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    sheet_index : int
        Index of the spreadsheet in ``project["spreadsheets"]``.
    cell_ref : str
        Cell reference such as ``"A1"``, ``"B2"``, ``"AA23"``.
    value : str, int, or float
        The value to store.  Strings starting with ``"="`` are treated as
        formulas.

    Returns
    -------
    dict
        A summary containing the cell reference and stored value.

    Raises
    ------
    IndexError
        If *sheet_index* is out of range.
    ValueError
        If *cell_ref* is invalid.
    """
    ref = _validate_cell_ref(cell_ref)
    sheet = _get_sheet(project, sheet_index)

    # Determine cell content type
    if isinstance(value, str) and value.startswith("="):
        cell_data = {"value": value, "type": "formula"}
    elif isinstance(value, (int, float)):
        cell_data = {"value": value, "type": "number"}
    else:
        cell_data = {"value": str(value), "type": "string"}

    sheet["cells"][ref] = cell_data

    return {
        "sheet_index": sheet_index,
        "cell_ref": ref,
        "value": cell_data["value"],
        "type": cell_data["type"],
    }


def get_cell(
    project: Dict[str, Any], sheet_index: int, cell_ref: str
) -> Dict[str, Any]:
    """Retrieve a cell value from a spreadsheet.

    Parameters
    ----------
    project : dict
        The project state dictionary.
    sheet_index : int
        Index of the spreadsheet.
    cell_ref : str
        Cell reference such as ``"A1"``.

    Returns
    -------
    dict
        Cell data including ``value`` and ``type``, or ``None`` values if
        the cell is empty.

    Raises
    ------
    IndexError
        If *sheet_index* is out of range.
    ValueError
        If *cell_ref* is invalid.
    """
    ref = _validate_cell_ref(cell_ref)
    sheet = _get_sheet(project, sheet_index)

    cell_data = sheet["cells"].get(ref)
    if cell_data is None:
        return {
            "sheet_index": sheet_index,
            "cell_ref": ref,
            "value": None,
            "type": None,
        }

    return {
        "sheet_index": sheet_index,
        "cell_ref": ref,
        "value": cell_data["value"],
        "type": cell_data["type"],
    }


def set_alias(
    project: Dict[str, Any],
    sheet_index: int,
    cell_ref: str,
    alias: str,
) -> Dict[str, Any]:
    """Assign an alias name to a cell.

    Aliases allow cells to be referenced by name in formulas and
    parametric expressions.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    sheet_index : int
        Index of the spreadsheet.
    cell_ref : str
        Cell reference to alias.
    alias : str
        Alias name.  Must start with a letter or underscore and contain
        only alphanumeric characters and underscores.

    Returns
    -------
    dict
        Summary with ``cell_ref`` and ``alias``.

    Raises
    ------
    IndexError
        If *sheet_index* is out of range.
    ValueError
        If *cell_ref* or *alias* is invalid, or the alias is already in use.
    """
    ref = _validate_cell_ref(cell_ref)
    sheet = _get_sheet(project, sheet_index)

    if not isinstance(alias, str) or not alias.strip():
        raise ValueError("Alias must be a non-empty string")
    alias = alias.strip()

    if not _ALIAS_RE.match(alias):
        raise ValueError(
            f"Invalid alias '{alias}'. Must start with a letter or underscore "
            f"and contain only alphanumeric characters and underscores."
        )

    # Check alias uniqueness (allow re-aliasing the same cell)
    for existing_ref, existing_alias in sheet["aliases"].items():
        if existing_alias == alias and existing_ref != ref:
            raise ValueError(
                f"Alias '{alias}' is already assigned to cell {existing_ref}"
            )

    sheet["aliases"][ref] = alias

    return {
        "sheet_index": sheet_index,
        "cell_ref": ref,
        "alias": alias,
    }


def import_csv(
    project: Dict[str, Any],
    sheet_index: int,
    path: str,
    start_cell: str = "A1",
) -> Dict[str, Any]:
    """Import CSV data into a spreadsheet.

    Each CSV value is stored as a cell starting from *start_cell*.
    Numeric strings are converted to floats automatically.

    Parameters
    ----------
    project : dict
        The mutable project state dictionary.
    sheet_index : int
        Index of the target spreadsheet.
    path : str
        Path to the CSV file.
    start_cell : str
        Top-left cell for the imported data.  Defaults to ``"A1"``.

    Returns
    -------
    dict
        Summary with number of rows and columns imported.

    Raises
    ------
    IndexError
        If *sheet_index* is out of range.
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If *start_cell* is invalid.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    start_ref = _validate_cell_ref(start_cell)
    start_col_letters, start_row = _parse_cell_ref(start_ref)
    start_col = _col_to_index(start_col_letters)

    sheet = _get_sheet(project, sheet_index)

    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        rows_imported = 0
        max_cols = 0

        for row_offset, row in enumerate(reader):
            for col_offset, raw_value in enumerate(row):
                col_letters = _index_to_col(start_col + col_offset)
                row_num = start_row + row_offset
                ref = f"{col_letters}{row_num}"

                # Try to parse as number
                value: Union[str, float]
                try:
                    value = float(raw_value)
                    # Keep as int if no decimal part
                    if value == int(value):
                        value = int(value)
                    cell_type = "number"
                except (ValueError, OverflowError):
                    value = raw_value
                    cell_type = "string"

                sheet["cells"][ref] = {"value": value, "type": cell_type}

            rows_imported += 1
            if len(row) > max_cols:
                max_cols = len(row)

    return {
        "sheet_index": sheet_index,
        "rows_imported": rows_imported,
        "columns_imported": max_cols,
        "start_cell": start_ref,
    }


def export_csv(
    project: Dict[str, Any], sheet_index: int, path: str
) -> Dict[str, Any]:
    """Export a spreadsheet to a CSV file.

    Cells are written in row-major order.  Empty cells produce empty
    strings in the output.

    Parameters
    ----------
    project : dict
        The project state dictionary.
    sheet_index : int
        Index of the spreadsheet.
    path : str
        Destination file path.

    Returns
    -------
    dict
        Summary with the absolute path and dimensions.

    Raises
    ------
    IndexError
        If *sheet_index* is out of range.
    ValueError
        If *path* is invalid.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    sheet = _get_sheet(project, sheet_index)
    cells = sheet["cells"]

    if not cells:
        # Write an empty file
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            pass
        return {
            "sheet_index": sheet_index,
            "path": os.path.abspath(path),
            "rows": 0,
            "columns": 0,
        }

    # Determine grid bounds
    min_col, max_col = float("inf"), 0
    min_row, max_row = float("inf"), 0

    for ref in cells:
        col_letters, row_num = _parse_cell_ref(ref)
        col_idx = _col_to_index(col_letters)
        min_col = min(min_col, col_idx)
        max_col = max(max_col, col_idx)
        min_row = min(min_row, row_num)
        max_row = max(max_row, row_num)

    min_col = int(min_col)
    min_row = int(min_row)

    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    num_rows = max_row - min_row + 1
    num_cols = max_col - min_col + 1

    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for row_num in range(min_row, max_row + 1):
            row_data: List[str] = []
            for col_idx in range(min_col, max_col + 1):
                ref = f"{_index_to_col(col_idx)}{row_num}"
                cell = cells.get(ref)
                if cell is not None:
                    row_data.append(str(cell["value"]))
                else:
                    row_data.append("")
            writer.writerow(row_data)

    return {
        "sheet_index": sheet_index,
        "path": os.path.abspath(path),
        "rows": num_rows,
        "columns": num_cols,
    }


def list_spreadsheets(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a summary of all spreadsheets in the project.

    Returns
    -------
    list[dict]
        Each entry has ``id``, ``name``, ``cell_count``, and ``alias_count``.
    """
    sheets = project.get("spreadsheets", [])
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "cell_count": len(s.get("cells", {})),
            "alias_count": len(s.get("aliases", {})),
        }
        for s in sheets
    ]
