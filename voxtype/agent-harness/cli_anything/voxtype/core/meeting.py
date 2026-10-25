"""Meeting domain.

Reads voxtype's meeting index (``index.db``) directly for structured listing
(``voxtype meeting list`` has no JSON mode); every export, label, delete and
summary goes through the voxtype binary. ``import_meeting`` builds a native
meeting from pre-recorded audio: each file is transcribed by voxtype, then
written using exactly the schema voxtype's own storage layer creates, so the
result is indistinguishable from a live meeting for voxtype's exporters.
"""

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from cli_anything.voxtype.core import config as config_mod
from cli_anything.voxtype.core import transcribe as transcribe_mod
from cli_anything.voxtype.utils import voxtype_backend as backend

EXPORT_FORMATS = ("text", "markdown", "json", "srt", "vtt")
_EXT = {"text": "txt", "markdown": "md", "json": "json", "srt": "srt", "vtt": "vtt"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT,
    started_at INTEGER NOT NULL,
    ended_at INTEGER,
    duration_secs INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    storage_path TEXT,
    audio_retained INTEGER NOT NULL DEFAULT 0,
    model TEXT,
    synced_at INTEGER,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_meetings_started_at ON meetings(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings(status);
CREATE TABLE IF NOT EXISTS speaker_labels (
    meeting_id TEXT NOT NULL,
    speaker_num INTEGER NOT NULL,
    label TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (meeting_id, speaker_num),
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);
"""


def default_data_dir() -> str:
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg and os.path.isabs(xdg):
        return os.path.join(xdg, "voxtype")
    return os.path.join(os.path.expanduser("~"), ".local", "share", "voxtype")


def storage_dir(config_path: Optional[str] = None) -> str:
    """Resolve meeting.storage_path the way voxtype does ("auto" = data dir)."""
    value = config_mod.get_key("meeting.storage_path", config_path).get("value") or "auto"
    if value == "auto":
        return os.path.join(default_data_dir(), "meetings")
    return os.path.expanduser(value)


def _connect(storage: str, create: bool = False) -> Optional[sqlite3.Connection]:
    db = os.path.join(storage, "index.db")
    if not os.path.exists(db):
        if not create:
            return None
        os.makedirs(storage, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    if create:
        conn.executescript(_SCHEMA)
    return conn


def _iso(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def list_meetings(config_path: Optional[str] = None, limit: int = 20,
                  status: Optional[str] = None) -> dict:
    storage = storage_dir(config_path)
    conn = _connect(storage)
    if conn is None:
        return {"storage_path": storage, "count": 0, "meetings": []}
    with conn:
        q = "SELECT * FROM meetings"
        params: list = []
        if status:
            q += " WHERE status = ?"
            params.append(status)
        q += " ORDER BY started_at DESC LIMIT ?"
        params.append(int(limit))
        rows = conn.execute(q, params).fetchall()
        labels = {}
        for r in conn.execute("SELECT meeting_id, speaker_num, label FROM speaker_labels"):
            labels.setdefault(r["meeting_id"], {})[f"SPEAKER_{r['speaker_num']:02d}"] = r["label"]
    conn.close()
    meetings = []
    for r in rows:
        meetings.append({
            "id": r["id"],
            "title": r["title"],
            "started_at": _iso(r["started_at"]),
            "ended_at": _iso(r["ended_at"]),
            "duration_secs": r["duration_secs"],
            "status": r["status"],
            "chunk_count": r["chunk_count"],
            "storage_path": r["storage_path"],
            "model": r["model"],
            "speaker_labels": labels.get(r["id"], {}),
        })
    return {"storage_path": storage, "count": len(meetings), "meetings": meetings}


def resolve_id(meeting_id: str, config_path: Optional[str] = None) -> str:
    """Accept a full UUID, a unique prefix, or 'latest'."""
    listing = list_meetings(config_path, limit=100000)["meetings"]
    if meeting_id == "latest":
        if not listing:
            raise ValueError("No meetings found.")
        return listing[0]["id"]
    matches = [m["id"] for m in listing if m["id"].startswith(meeting_id)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"Meeting not found: {meeting_id}")
    raise ValueError(f"Ambiguous meeting id prefix '{meeting_id}' matches {len(matches)} meetings")


def get_meeting_json(meeting_id: str, config_path: Optional[str] = None) -> dict:
    """Full meeting data as rendered by voxtype's JSON exporter."""
    mid = resolve_id(meeting_id, config_path)
    proc = backend.run(["meeting", "export", mid, "--format", "json", "--timestamps",
                        "--speakers", "--metadata"], config_path)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise backend.VoxtypeError(f"voxtype meeting export returned non-JSON: {proc.stdout[:200]!r}") from e


def show(meeting_id: str, config_path: Optional[str] = None) -> dict:
    mid = resolve_id(meeting_id, config_path)
    proc = backend.run(["meeting", "show", mid], config_path)
    return {"id": mid, "report": proc.stdout.strip()}


def export(meeting_id: str, output: Optional[str] = None, fmt: str = "markdown",
           timestamps: bool = False, speakers: bool = False, metadata: bool = False,
           config_path: Optional[str] = None, overwrite: bool = False) -> dict:
    fmt = {"txt": "text", "md": "markdown"}.get(fmt.lower(), fmt.lower())
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unknown meeting export format '{fmt}'. Valid: {', '.join(EXPORT_FORMATS)}")
    mid = resolve_id(meeting_id, config_path)
    args = ["meeting", "export", mid, "--format", fmt]
    if timestamps:
        args.append("--timestamps")
    if speakers:
        args.append("--speakers")
    if metadata:
        args.append("--metadata")
    if output:
        if os.path.exists(output) and not overwrite:
            raise FileExistsError(f"{output} exists; pass --overwrite")
        os.makedirs(os.path.dirname(os.path.abspath(output)) or ".", exist_ok=True)
        args += ["--output", output]
    proc = backend.run(args, config_path)
    result = {"id": mid, "format": fmt, "method": "voxtype meeting export"}
    if output:
        if not os.path.exists(output):
            raise RuntimeError(f"voxtype reported success but {output} was not written")
        result.update({"output": os.path.abspath(output), "file_size": os.path.getsize(output)})
    else:
        result["content"] = proc.stdout
    return result


def delete(meeting_id: str, config_path: Optional[str] = None) -> dict:
    mid = resolve_id(meeting_id, config_path)
    proc = backend.run(["meeting", "delete", mid, "--force"], config_path)
    return {"id": mid, "deleted": True, "message": proc.stdout.strip()}


def label(meeting_id: str, speaker_id: str, name: str, config_path: Optional[str] = None) -> dict:
    mid = resolve_id(meeting_id, config_path)
    proc = backend.run(["meeting", "label", mid, str(speaker_id), name], config_path)
    return {"id": mid, "speaker_id": speaker_id, "label": name, "message": proc.stdout.strip()}


def summarize(meeting_id: str, fmt: str = "markdown", output: Optional[str] = None,
              config_path: Optional[str] = None) -> dict:
    mid = resolve_id(meeting_id, config_path)
    args = ["meeting", "summarize", mid, "--format", fmt]
    if output:
        args += ["--output", output]
    proc = backend.run(args, config_path, timeout=1800)
    result = {"id": mid, "format": fmt}
    if output:
        result.update({"output": os.path.abspath(output), "file_size": os.path.getsize(output)})
    else:
        result["content"] = proc.stdout
    return result


# ── live meeting control (requires the running daemon) ────────────────

def control(action: str, config_path: Optional[str] = None, title: Optional[str] = None,
            diarization: Optional[str] = None) -> dict:
    if action not in ("start", "stop", "pause", "resume", "status"):
        raise ValueError(f"Unknown meeting action '{action}'")
    args = ["meeting", action]
    if action == "start":
        if title:
            args += ["--title", title]
        if diarization:
            args += ["--diarization", diarization]
    proc = backend.run(args, config_path)
    return {"action": action, "message": proc.stdout.strip() or proc.stderr.strip()}


# ── import pre-recorded audio as a native meeting ──────────────────────

def _storage_dir_name(title: Optional[str], started: datetime, mid: str) -> str:
    """Mirror MeetingMetadata::storage_dir_name (src/meeting/data.rs)."""
    date = started.strftime("%Y-%m-%d")
    if title:
        safe = "".join(c if (c.isalnum() or c in "-_") else ("-" if c.isspace() else "_") for c in title)
        return f"{date}-{safe.lower()}"
    return f"{date}-{mid.split('-')[0]}"


def build_transcript(results: list[dict], speakers: Optional[list[int]] = None,
                     gap_ms: int = 0) -> dict:
    """Lay transcription results end to end as voxtype transcript segments."""
    segments = []
    cursor = 0
    for i, r in enumerate(results):
        dur_ms = int(round((r.get("duration_secs") or 0) * 1000))
        seg = {
            "id": i,
            "start_ms": cursor,
            "end_ms": cursor + dur_ms,
            "text": r.get("text", ""),
            "source": "unknown",
            "chunk_id": i,
        }
        if speakers:
            seg["speaker_id"] = f"SPEAKER_{int(speakers[i % len(speakers)]):02d}"
        segments.append(seg)
        cursor += dur_ms + gap_ms
    return {"segments": segments, "total_chunks": len(results)}


def import_meeting(files: list[str], title: Optional[str] = None,
                   speakers: Optional[list[int]] = None, gap_ms: int = 0,
                   config_path: Optional[str] = None, overrides: Optional[dict] = None,
                   engine: Optional[str] = None, progress=None) -> dict:
    """Transcribe audio files with voxtype and store them as one meeting."""
    inputs = transcribe_mod.collect_inputs(files)
    if not inputs:
        raise ValueError("No audio files to import.")
    results = []
    for i, f in enumerate(inputs, 1):
        if progress:
            progress(i, len(inputs), os.path.basename(f))
        results.append(transcribe_mod.transcribe_file(f, config_path, overrides, engine))

    transcript = build_transcript(results, speakers, gap_ms)
    total_ms = transcript["segments"][-1]["end_ms"] if transcript["segments"] else 0
    duration = int(round(total_ms / 1000))

    mid = str(uuid.uuid4())
    started = datetime.now(timezone.utc).replace(microsecond=0)
    ended_ts = int(started.timestamp()) + duration
    storage = storage_dir(config_path)
    meeting_dir = os.path.join(storage, _storage_dir_name(title, started, mid))
    os.makedirs(meeting_dir, exist_ok=True)

    model = (overrides or {}).get("model") or config_mod.get_key("whisper.model", config_path).get("value")
    metadata = {
        "id": mid,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "ended_at": _iso(ended_ts),
        "duration_secs": duration,
        "status": "completed",
        "chunk_count": len(results),
        "storage_path": meeting_dir,
        "audio_retained": False,
        "model": model,
    }
    if title:
        metadata["title"] = title
    with open(os.path.join(meeting_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(meeting_dir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2)

    conn = _connect(storage, create=True)
    with conn:
        conn.execute(
            "INSERT INTO meetings (id, title, started_at, ended_at, duration_secs, status, "
            "chunk_count, storage_path, audio_retained, model) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (mid, title, int(started.timestamp()), ended_ts, duration, "completed",
             len(results), meeting_dir, 0, model),
        )
    conn.close()
    return {
        "id": mid,
        "title": title,
        "storage_path": meeting_dir,
        "segments": len(transcript["segments"]),
        "duration_secs": duration,
        "words": sum(r["words"] for r in results),
        "files": [r["file"] for r in results],
        "imported_at": time.time(),
    }
