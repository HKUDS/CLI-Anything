"""Small session event log for WaveTone CLI runs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .project import now_iso


def _new_session() -> dict[str, Any]:
    return {"schema_version": "wavetone-session/v1", "events": []}


def _assert_json_safe(value: Any, path: str = "payload") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must contain only finite numbers")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_json_safe(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _assert_json_safe(item, f"{path}[{idx}]")


def _load_session_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _new_session()

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Session file must be a JSON object")

    events = data.get("events")
    if events is None:
        data["events"] = []
    elif not isinstance(events, list):
        raise ValueError("Session file field 'events' must be a list")

    return data


def append_event(session_path: str | Path, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(session_path).expanduser().resolve()
    data = _load_session_data(path)
    _assert_json_safe(payload)
    record = {"time": now_iso(), "event": event, "payload": payload}
    data["events"].append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return record


def load_events(session_path: str | Path) -> list[dict[str, Any]]:
    path = Path(session_path).expanduser().resolve()
    if not path.exists():
        return []
    data = _load_session_data(path)
    return list(data["events"])
