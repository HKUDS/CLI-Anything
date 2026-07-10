from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_operations(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Operation history must be a JSON list")
    for index, operation in enumerate(data):
        if not isinstance(operation, dict):
            raise ValueError(f"Operation {index} must be an object")
    return data


def save_operations(operations: list[dict[str, Any]], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(operations, indent=2, sort_keys=True), encoding="utf-8")
    return target


def text_transform(column: str, expression: str, on_error: str = "keep-original") -> dict[str, Any]:
    _require_text("column", column)
    _require_text("expression", expression)
    return {
        "op": "core/text-transform",
        "engineConfig": {"mode": "row-based", "facets": []},
        "columnName": column,
        "expression": expression,
        "onError": on_error,
        "repeat": False,
        "repeatCount": 10,
        "description": f"Text transform on {column} using expression {expression}",
    }


def mass_edit(column: str, edits: dict[str, str]) -> dict[str, Any]:
    _require_text("column", column)
    if not edits:
        raise ValueError("edits must not be empty")
    normalized = [{"from": [str(src)], "fromBlank": False, "fromError": False, "to": str(dst)} for src, dst in edits.items()]
    return {
        "op": "core/mass-edit",
        "engineConfig": {"mode": "row-based", "facets": []},
        "columnName": column,
        "expression": "value",
        "edits": normalized,
        "description": f"Mass edit {len(edits)} value(s) in {column}",
    }


def column_addition(name: str, source_column: str, expression: str) -> dict[str, Any]:
    _require_text("name", name)
    _require_text("source_column", source_column)
    _require_text("expression", expression)
    return {
        "op": "core/column-addition",
        "engineConfig": {"mode": "row-based", "facets": []},
        "baseColumnName": source_column,
        "expression": expression,
        "onError": "set-to-blank",
        "newColumnName": name,
        "columnInsertIndex": 1,
        "description": f"Create column {name} from {source_column}",
    }


def column_removal(column: str) -> dict[str, Any]:
    _require_text("column", column)
    return {"op": "core/column-removal", "columnName": column, "description": f"Remove column {column}"}


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
