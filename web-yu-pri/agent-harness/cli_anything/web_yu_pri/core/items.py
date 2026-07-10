"""Input normalization for Web Yu-pri contents lines."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


DESCRIPTION_KEYS = ("description", "desc", "content", "contents", "item", "name", "pkg")
VALUE_KEYS = ("value", "declared_value", "cost", "price", "amount", "yen", "jpy")
QUANTITY_KEYS = ("quantity", "qty", "num", "count")
COUNTRY_KEYS = ("country", "country_code", "country_of_origin", "origin", "couCd", "cou_cd")
HS_KEYS = ("hs_code", "hs", "hscode", "hsCode")
_MISSING = object()


@dataclass(frozen=True)
class ItemLine:
    """One declared contents line for a Web Yu-pri shipment."""

    description: str
    value: int
    quantity: int = 1
    country: str | None = None
    hs_code: str | None = None

    def to_dict(self, value_mode: str = "line") -> dict[str, Any]:
        line_total = self.line_total(value_mode=value_mode)
        data = asdict(self)
        data["line_total"] = line_total
        data["value_mode"] = value_mode
        return data

    def line_total(self, value_mode: str = "line") -> int:
        if value_mode == "unit":
            return self.value * self.quantity
        if value_mode == "line":
            return self.value
        raise ValueError("value_mode must be 'line' or 'unit'")


def load_items(path: str | Path, default_country: str | None = None) -> list[ItemLine]:
    """Load contents lines from JSON, CSV, or TSV."""

    input_path = Path(path)
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        return _load_json(input_path, default_country=default_country)
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        return _load_delimited(input_path, delimiter=delimiter, default_country=default_country)
    raise ValueError("items file must be .json, .csv, or .tsv")


def build_contents_plan(
    items: Iterable[ItemLine],
    total_value: int | None = None,
    value_mode: str = "line",
) -> dict[str, Any]:
    """Build a deterministic fill plan for the contents form."""

    if value_mode not in {"line", "unit"}:
        raise ValueError("value_mode must be 'line' or 'unit'")

    item_list = list(items)
    if not item_list:
        raise ValueError("at least one item line is required")

    computed_total = sum(item.line_total(value_mode=value_mode) for item in item_list)
    declared_total = computed_total if total_value is None else _coerce_int(
        total_value, "total_value", minimum=0
    )

    warnings: list[str] = []
    if declared_total != computed_total:
        warnings.append(
            f"declared total {declared_total} does not match computed item total {computed_total}"
        )

    return {
        "item_count": len(item_list),
        "computed_total": computed_total,
        "declared_total": declared_total,
        "total_matches": declared_total == computed_total,
        "value_mode": value_mode,
        "warnings": warnings,
        "items": [item.to_dict(value_mode=value_mode) for item in item_list],
    }


def parse_item_mapping(row: dict[str, Any], default_country: str | None = None) -> ItemLine:
    """Normalize one user-provided mapping into an ItemLine."""

    description = str(_pick(row, DESCRIPTION_KEYS, "description")).strip()
    if not description:
        raise ValueError("description cannot be blank")

    value = _coerce_int(_pick(row, VALUE_KEYS, "value"), "value", minimum=0)
    quantity = _coerce_int(_pick(row, QUANTITY_KEYS, "quantity", default=1), "quantity", minimum=1)

    raw_country = _pick(row, COUNTRY_KEYS, "country", default=default_country)
    country = _normalize_country(raw_country)
    hs_code = _normalize_hs_code(_pick(row, HS_KEYS, "hs_code", default=None))

    return ItemLine(
        description=description,
        value=value,
        quantity=quantity,
        country=country,
        hs_code=hs_code,
    )


def _load_json(path: Path, default_country: str | None = None) -> list[ItemLine]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict):
        rows = payload.get("items")
        if rows is None:
            raise ValueError("JSON object must contain an 'items' array")
    else:
        rows = payload

    if not isinstance(rows, list):
        raise ValueError("items payload must be a list")

    return [parse_item_mapping(_require_mapping(row), default_country=default_country) for row in rows]


def _load_delimited(
    path: Path,
    delimiter: str,
    default_country: str | None = None,
) -> list[ItemLine]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("CSV/TSV file must include a header row")
        return [
            parse_item_mapping(dict(row), default_country=default_country)
            for row in reader
            if any(str(value or "").strip() for value in row.values())
        ]


def _pick(
    row: dict[str, Any],
    keys: tuple[str, ...],
    label: str,
    default: Any = _MISSING,
) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    if default is not _MISSING:
        return default
    raise ValueError(f"missing required field: {label}")


def _require_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("each item must be an object/mapping")
    return value


def _coerce_int(value: Any, label: str, minimum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        result = value
    else:
        text = str(value).strip()
        text = re.sub(r"[,\sJPYjpy¥￥円]", "", text)
        if not re.fullmatch(r"-?\d+", text):
            raise ValueError(f"{label} must be an integer")
        result = int(text)
    if result < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return result


def _normalize_country(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", text):
        raise ValueError("country must be a two-letter ISO code, for example KR or US")
    return text


def _normalize_hs_code(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = re.sub(r"\s+", "", str(value).strip())
    if not re.fullmatch(r"[0-9A-Za-z.\-]{2,20}", text):
        raise ValueError("hs_code may contain only letters, digits, dots, and hyphens")
    return text
