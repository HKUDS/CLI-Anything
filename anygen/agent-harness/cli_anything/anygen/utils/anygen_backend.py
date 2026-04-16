"""AnyGen API backend — wraps the AnyGen OpenAPI for task lifecycle management.

This module handles all HTTP communication with the AnyGen cloud service:
create tasks, poll status, upload files, download results.
"""

from __future__ import annotations

import json
import os
import sys
import time
import base64
from datetime import datetime
from pathlib import Path
from typing import Callable

try:
    import requests
except ImportError:
    print(
        "requests library not found. Install with: pip3 install requests",
        file=sys.stderr,
    )
    sys.exit(1)

API_BASE = "https://www.anygen.io"
POLL_INTERVAL = 3
MAX_POLL_TIME = 1200  # 20 minutes
CONFIG_DIR = Path.home() / ".config" / "anygen"
CONFIG_FILE = CONFIG_DIR / "config.json"
ENV_API_KEY = "ANYGEN_API_KEY"

VALID_OPERATIONS = [
    "chat", "slide", "doc", "storybook",
    "data_analysis", "website", "smart_draw",
]

DOWNLOADABLE_OPERATIONS = {"slide", "doc", "smart_draw"}


# ── Config ────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load configuration from ~/.config/anygen/config.json."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_config(config: dict):
    """Save configuration to ~/.config/anygen/config.json (mode 600)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    CONFIG_FILE.chmod(0o600)


def get_api_key(cli_key: str | None = None) -> str | None:
    """Resolve API key: CLI arg → env var → config file."""
    if cli_key:
        return cli_key
    env_key = os.environ.get(ENV_API_KEY)
    if env_key:
        return env_key
    return load_config().get("api_key")


def _make_auth_token(api_key: str) -> str:
    return api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}"


def _require_api_key(api_key: str | None) -> str:
    if not api_key:
        raise RuntimeError(
            "AnyGen API key not found. Provide one via:\n"
            "  1. --api-key sk-xxx\n"
            f"  2. export {ENV_API_KEY}=sk-xxx\n"
            "  3. cli-anything-anygen config set api_key sk-xxx\n"
            "Get a key at https://www.anygen.io/home → Setting → Integration"
        )
    return api_key


# ── File Upload ───────────────────────────────────────────────────────

def upload_file(api_key: str, file_path: str, extra_headers: dict | None = None) -> dict:
    """Upload a file and return {"file_token": ..., "filename": ..., "file_size": ...}."""
    api_key = _require_api_key(api_key)
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    headers = {"Authorization": _make_auth_token(api_key)}
    if extra_headers:
        headers.update(extra_headers)

    with open(path, "rb") as f:
        files = {"file": (path.name, f)}
        data = {"filename": path.name}
        resp = requests.post(
            f"{API_BASE}/v1/openapi/files/upload",
            files=files, data=data, headers=headers, timeout=60,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Upload failed (HTTP {resp.status_code}): {resp.text[:300]}")

    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"Upload failed: {result.get('error', 'Unknown error')}")

    return {
        "file_token": result.get("file_token"),
        "filename": result.get("filename"),
        "file_size": result.get("file_size"),
    }


# ── Encode file (legacy base64) ──────────────────────────────────────

def encode_file(file_path: str) -> dict:
    """Encode a file to base64 for legacy attachment in create_task."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "rb") as f:
        content = f.read()

    mime_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".txt": "text/plain",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    mime_type = mime_types.get(path.suffix.lower(), "application/octet-stream")

    return {
        "file_name": path.name,
        "file_type": mime_type,
        "file_data": base64.b64encode(content).decode("utf-8"),
    }


# ── Prepare (multi-turn) ─────────────────────────────────────────────

def prepare_task(
    api_key: str,
    messages: list[dict],
    file_tokens: list[str] | None = None,
    extra_headers: dict | None = None,
) -> dict:
    """Call the prepare API for multi-turn requirement analysis.

    Returns the full response dict including 'reply', 'status',
    'suggested_task_params', and 'messages'.
    """
    api_key = _require_api_key(api_key)
    auth_token = _make_auth_token(api_key)

    body: dict = {"auth_token": auth_token, "messages": messages}
    if file_tokens:
        body["file_tokens"] = file_tokens

    headers: dict = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    resp = requests.post(
        f"{API_BASE}/v1/openapi/tasks/prepare",
        json=body, headers=headers, timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Prepare failed (HTTP {resp.status_code}): {resp.text[:300]}")

    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"Prepare failed: {result.get('error', 'Unknown error')}")
    return result


# ── Create Task ───────────────────────────────────────────────────────

def create_task(
    api_key: str,
    operation: str,
    prompt: str,
    *,
    language: str | None = None,
    slide_count: int | None = None,
    template: str | None = None,
    ratio: str | None = None,
    export_format: str | None = None,
    file_tokens: list[str] | None = None,
    files: list[str] | None = None,
    style: str | None = None,
    extra_headers: dict | None = None,
) -> dict:
    """Create an async generation task.

    Returns {"task_id": ..., "task_url": ...}.
    """
    api_key = _require_api_key(api_key)
    if operation not in VALID_OPERATIONS:
        raise ValueError(
            f"Invalid operation '{operation}'. "
            f"Valid: {', '.join(VALID_OPERATIONS)}"
        )

    final_prompt = prompt
    if style:
        final_prompt = f"{prompt}\n\nStyle requirement: {style}"

    body: dict = {
        "auth_token": _make_auth_token(api_key),
        "operation": operation,
        "prompt": final_prompt,
    }
    if language:
        body["language"] = language
    if operation == "slide":
        if slide_count:
            body["slide_count"] = slide_count
        if template:
            body["template"] = template
        if ratio:
            body["ratio"] = ratio
    if export_format:
        body["export_format"] = export_format
    if file_tokens:
        body["file_tokens"] = file_tokens

    if files:
        encoded = []
        for fp in files:
            encoded.append(encode_file(fp))
        body["files"] = encoded

    headers: dict = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    resp = requests.post(
        f"{API_BASE}/v1/openapi/tasks",
        json=body, headers=headers, timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Create task failed (HTTP {resp.status_code}): {resp.text[:300]}")

    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"Task creation failed: {result.get('error', 'Unknown error')}")

    return {
        "task_id": result.get("task_id"),
        "task_url": result.get("task_url"),
    }


# ── Query Task ────────────────────────────────────────────────────────

def query_task(api_key: str, task_id: str, extra_headers: dict | None = None) -> dict:
    """Single non-blocking query of task status. Returns full task dict."""
    api_key = _require_api_key(api_key)
    headers = {"Authorization": _make_auth_token(api_key)}
    if extra_headers:
        headers.update(extra_headers)

    resp = requests.get(
        f"{API_BASE}/v1/openapi/tasks/{task_id}",
        headers=headers, timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Query failed (HTTP {resp.status_code}): {resp.text[:300]}")
    return resp.json()


# ── Poll Task ─────────────────────────────────────────────────────────

def poll_task(
    api_key: str,
    task_id: str,
    *,
    max_time: int = MAX_POLL_TIME,
    interval: int = POLL_INTERVAL,
    extra_headers: dict | None = None,
    on_progress: Callable | None = None,
) -> dict:
    """Poll task until completed/failed. Returns final task dict.

    Args:
        on_progress: optional callback(status, progress_pct) called on each poll.
    """
    api_key = _require_api_key(api_key)
    start = time.time()
    last_progress = -1

    while True:
        elapsed = time.time() - start
        if elapsed > max_time:
            raise TimeoutError(f"Polling timeout after {max_time}s for task {task_id}")

        task = query_task(api_key, task_id, extra_headers)
        status = task.get("status")
        progress = task.get("progress", 0)

        if progress != last_progress and on_progress:
            on_progress(status, progress)
            last_progress = progress

        if status == "completed":
            return task
        if status == "failed":
            error = task.get("error", "Unknown error")
            raise RuntimeError(f"Task {task_id} failed: {error}")

        time.sleep(interval)


# ── Download ──────────────────────────────────────────────────────────

def download_file(
    api_key: str,
    task_id: str,
    output_dir: str,
    extra_headers: dict | None = None,
) -> dict:
    """Download the generated file for a completed task.

    Returns {"local_path": ..., "file_name": ..., "file_size": ..., "task_url": ...}.
    """
    task = query_task(api_key, task_id, extra_headers)
    if task.get("status") != "completed":
        raise RuntimeError(f"Task not completed (status={task.get('status')})")

    output = task.get("output", {})
    file_url = output.get("file_url")
    file_name = output.get("file_name")
    task_url = output.get("task_url", f"{API_BASE}/task/{task_id}")

    if not file_url:
        raise RuntimeError("No download URL available for this task")

    resp = requests.get(file_url, timeout=120)
    resp.raise_for_status()

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / (file_name or "output")

    if file_path.exists():
        stem, suffix = file_path.stem, file_path.suffix
        counter = 1
        while file_path.exists():
            file_path = out_path / f"{stem}_{counter}{suffix}"
            counter += 1

    with open(file_path, "wb") as f:
        f.write(resp.content)

    return {
        "local_path": str(file_path),
        "file_name": file_name,
        "file_size": len(resp.content),
        "task_url": task_url,
    }


def download_thumbnail(
    api_key: str,
    task_id: str,
    output_dir: str,
    extra_headers: dict | None = None,
) -> dict:
    """Download only the thumbnail image for a completed task."""
    task = query_task(api_key, task_id, extra_headers)
    if task.get("status") != "completed":
        raise RuntimeError(f"Task not completed (status={task.get('status')})")

    output = task.get("output", {})
    thumbnail_url = output.get("thumbnail_url")
    if not thumbnail_url:
        raise RuntimeError("No thumbnail available for this task")

    resp = requests.get(thumbnail_url, timeout=120)
    resp.raise_for_status()

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"thumbnail_{task_id}.png"

    with open(file_path, "wb") as f:
        f.write(resp.content)

    return {
        "local_path": str(file_path),
        "file_size": len(resp.content),
    }


# ── Full Workflow ─────────────────────────────────────────────────────

def run_full_workflow(
    api_key: str,
    operation: str,
    prompt: str,
    output_dir: str | None = None,
    *,
    on_progress: Callable | None = None,
    **create_kwargs,
) -> dict:
    """Full workflow: create → poll → download.

    Returns dict with task info and local_path (if output_dir given).
    """
    result = create_task(api_key, operation, prompt, **create_kwargs)
    task_id = result["task_id"]

    task = poll_task(api_key, task_id, on_progress=on_progress)

    dl_info = {}
    if output_dir and operation in DOWNLOADABLE_OPERATIONS:
        dl_info = download_file(api_key, task_id, output_dir)

    return {
        "task_id": task_id,
        "task_url": result.get("task_url"),
        "status": task.get("status"),
        "output": task.get("output", {}),
        **dl_info,
    }
