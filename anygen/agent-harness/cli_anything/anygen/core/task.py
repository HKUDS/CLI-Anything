"""Task management — create, query, poll, download AnyGen tasks.

Thin wrappers around the backend that add local task history persistence.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cli_anything.anygen.utils.anygen_backend import (
    DOWNLOADABLE_OPERATIONS,
    VALID_OPERATIONS,
    create_task as _api_create,
    download_file as _api_download,
    download_thumbnail as _api_thumbnail,
    poll_task as _api_poll,
    query_task as _api_query,
    run_full_workflow as _api_run,
    upload_file as _api_upload,
    prepare_task as _api_prepare,
)

TASK_HISTORY_DIR = Path.home() / ".cli-anything-anygen" / "tasks"


def _save_task_record(task_id: str, record: dict):
    TASK_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = TASK_HISTORY_DIR / f"{task_id}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2, default=str)


def _load_task_record(task_id: str) -> dict | None:
    path = TASK_HISTORY_DIR / f"{task_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def list_task_records(limit: int = 20, status_filter: str | None = None) -> list[dict]:
    """List locally cached task records, newest first."""
    if not TASK_HISTORY_DIR.exists():
        return []
    records = []
    for p in sorted(TASK_HISTORY_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p) as f:
                rec = json.load(f)
            if status_filter and rec.get("status") != status_filter:
                continue
            records.append(rec)
            if len(records) >= limit:
                break
        except (json.JSONDecodeError, IOError):
            continue
    return records


def create_task(
    api_key: str,
    operation: str,
    prompt: str,
    **kwargs,
) -> dict:
    """Create task and persist a local record. Returns {"task_id", "task_url"}."""
    result = _api_create(api_key, operation, prompt, **kwargs)
    record = {
        "version": "1.0",
        "task_id": result["task_id"],
        "operation": operation,
        "prompt": prompt,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_url": result.get("task_url"),
    }
    _save_task_record(result["task_id"], record)
    return result


def query_task(api_key: str, task_id: str, **kwargs) -> dict:
    """Query task status and update local record."""
    task = _api_query(api_key, task_id, **kwargs)
    rec = _load_task_record(task_id) or {"task_id": task_id}
    rec["status"] = task.get("status")
    rec["progress"] = task.get("progress", 0)
    if task.get("output"):
        rec["output"] = task["output"]
    _save_task_record(task_id, rec)
    return task


def poll_task(api_key: str, task_id: str, on_progress=None, **kwargs) -> dict:
    """Poll until completion and update local record."""
    task = _api_poll(api_key, task_id, on_progress=on_progress, **kwargs)
    rec = _load_task_record(task_id) or {"task_id": task_id}
    rec["status"] = task.get("status")
    rec["completed_at"] = datetime.now(timezone.utc).isoformat()
    if task.get("output"):
        rec["output"] = task["output"]
    _save_task_record(task_id, rec)
    return task


def download_file(api_key: str, task_id: str, output_dir: str, **kwargs) -> dict:
    """Download file and update local record with path."""
    dl = _api_download(api_key, task_id, output_dir, **kwargs)
    rec = _load_task_record(task_id) or {"task_id": task_id}
    rec["local_file"] = dl["local_path"]
    rec["metadata"] = {"file_size": dl["file_size"]}
    _save_task_record(task_id, rec)
    return dl


def download_thumbnail(api_key: str, task_id: str, output_dir: str, **kwargs) -> dict:
    """Download thumbnail and return path info."""
    return _api_thumbnail(api_key, task_id, output_dir, **kwargs)


def upload_file(api_key: str, file_path: str, **kwargs) -> dict:
    """Upload a reference file. Returns {"file_token", "filename", "file_size"}."""
    return _api_upload(api_key, file_path, **kwargs)


def prepare_task(api_key: str, messages: list[dict], **kwargs) -> dict:
    """Multi-turn requirement analysis. Returns prepare API response."""
    return _api_prepare(api_key, messages, **kwargs)


def run_full_workflow(
    api_key: str,
    operation: str,
    prompt: str,
    output_dir: str | None = None,
    on_progress=None,
    **kwargs,
) -> dict:
    """Full workflow: create → poll → download. Returns combined result dict."""
    result = _api_run(
        api_key, operation, prompt, output_dir,
        on_progress=on_progress, **kwargs,
    )
    rec = {
        "version": "1.0",
        "task_id": result["task_id"],
        "operation": operation,
        "prompt": prompt,
        "status": result.get("status", "completed"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "task_url": result.get("task_url"),
        "output": result.get("output", {}),
    }
    if result.get("local_path"):
        rec["local_file"] = result["local_path"]
        rec["metadata"] = {"file_size": result.get("file_size", 0)}
    _save_task_record(result["task_id"], rec)
    return result
