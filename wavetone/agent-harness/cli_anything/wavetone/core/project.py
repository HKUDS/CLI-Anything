"""Project manifest helpers for the WaveTone harness."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "wavetone-project/v1"
SOFTWARE_VERSION = "2.61"
SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".wave",
    ".aif",
    ".aiff",
    ".mp3",
    ".wma",
    ".aac",
    ".ogg",
    ".oga",
    ".flac",
    ".wv",
    ".ape",
    ".alac",
    ".tta",
}

DEFAULT_ANALYSIS_SETTINGS: dict[str, Any] = {
    "blocks_per_second": 12,
    "blocks_per_semitone": 5,
    "note_range": "C1-B7",
    "reference_frequency_hz": 440.0,
    "analyze_fundamental_frequency": True,
    "channel": "Stereo",
    "skip_analysis_dialog": False,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_audio_path(audio_path: str | Path) -> Path:
    path = Path(audio_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Audio path is not a file: {path}")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(f"Unsupported audio extension {path.suffix!r}. Supported: {supported}")
    return path


def _finite_float(value: float, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def create_project(
    audio_path: str | Path,
    name: str | None = None,
    analysis_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audio = normalize_audio_path(audio_path)
    created_at = now_iso()
    settings = deepcopy(DEFAULT_ANALYSIS_SETTINGS)
    if analysis_settings:
        settings.update(analysis_settings)

    return {
        "schema_version": SCHEMA_VERSION,
        "software": {"name": "WaveTone", "version": SOFTWARE_VERSION, "backend": "wavetone.exe"},
        "project": {"name": name or audio.stem, "created_at": created_at, "modified_at": created_at},
        "audio": {
            "path": str(audio),
            "filename": audio.name,
            "extension": audio.suffix.lower(),
            "size_bytes": audio.stat().st_size,
        },
        "analysis": settings,
        "tempo": {"bpm": None, "first_bar_time_seconds": 0.0, "meter": "4/4"},
        "labels": [],
        "notes": [],
        "wfd_path": None,
        "limitations": [
            "WaveTone 2.61 exposes analysis, MIDI/text export, and WAVE export through GUI menus.",
            "This manifest is an agent-facing plan; WFD analysis data must be saved by WaveTone itself.",
        ],
    }


def touch(project: dict[str, Any]) -> dict[str, Any]:
    project.setdefault("project", {})["modified_at"] = now_iso()
    return project


def save_project(project: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    touch(project)
    path.write_text(json.dumps(project, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return path


def load_project(project_path: str | Path) -> dict[str, Any]:
    path = Path(project_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Project file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Project file must be a JSON object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported WaveTone project schema: {data.get('schema_version')!r}")
    return data


def add_label(
    project: dict[str, Any],
    name: str,
    time_seconds: float,
    note: str | None = None,
) -> dict[str, Any]:
    time_value = _finite_float(time_seconds, "Label time")
    if time_value < 0:
        raise ValueError("Label time must be >= 0")
    label: dict[str, Any] = {"name": name, "time_seconds": round(time_value, 6)}
    if note:
        label["note"] = note
    project.setdefault("labels", []).append(label)
    project["labels"].sort(key=lambda item: item["time_seconds"])
    return touch(project)


def set_tempo(
    project: dict[str, Any],
    bpm: float,
    first_bar_time_seconds: float = 0.0,
    meter: str = "4/4",
) -> dict[str, Any]:
    bpm_value = _finite_float(bpm, "BPM")
    first_bar_value = _finite_float(first_bar_time_seconds, "First bar time")
    if bpm_value <= 0:
        raise ValueError("BPM must be > 0")
    if first_bar_value < 0:
        raise ValueError("First bar time must be >= 0")
    project["tempo"] = {
        "bpm": round(bpm_value, 6),
        "first_bar_time_seconds": round(first_bar_value, 6),
        "meter": meter,
    }
    return touch(project)


def update_analysis(project: dict[str, Any], **settings: Any) -> dict[str, Any]:
    analysis = project.setdefault("analysis", deepcopy(DEFAULT_ANALYSIS_SETTINGS))
    for key, value in settings.items():
        if value is not None:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
            analysis[key] = value
    return touch(project)


def set_wfd_path(project: dict[str, Any], wfd_path: str | Path | None) -> dict[str, Any]:
    project["wfd_path"] = None if wfd_path is None else str(Path(wfd_path).expanduser().resolve())
    return touch(project)


def project_summary(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": project.get("schema_version"),
        "name": project.get("project", {}).get("name"),
        "audio": project.get("audio"),
        "tempo": project.get("tempo"),
        "label_count": len(project.get("labels", [])),
        "labels": project.get("labels", []),
        "analysis": project.get("analysis"),
        "wfd_path": project.get("wfd_path"),
        "limitations": project.get("limitations", []),
    }
