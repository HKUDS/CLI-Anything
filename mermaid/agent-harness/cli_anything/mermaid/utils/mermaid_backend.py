"""Backend helpers for Mermaid Live Editor render/share state."""

from __future__ import annotations

import base64
import json
import os
import urllib.request
import zlib


RENDER_BASE = os.environ.get("MERMAID_RENDERER_URL", "https://mermaid.ink").rstrip("/")
LIVE_BASE = os.environ.get("MERMAID_LIVE_URL", "https://mermaid.live").rstrip("/")


def serialize_state(state: dict) -> str:
    payload = json.dumps(state, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(payload, level=9)
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    return f"pako:{encoded}"


def build_render_url(serialized: str, fmt: str) -> str:
    if fmt == "svg":
        return f"{RENDER_BASE}/svg/{serialized}"
    if fmt == "png":
        return f"{RENDER_BASE}/img/{serialized}?type=png"
    raise ValueError(f"Unsupported format: {fmt}")


def build_live_url(serialized: str, mode: str) -> str:
    if mode not in {"edit", "view"}:
        raise ValueError(f"Unsupported share mode: {mode}")
    return f"{LIVE_BASE}/{mode}#{serialized}"


def render_to_file(serialized: str, output_path: str, fmt: str) -> dict:
    url = build_render_url(serialized, fmt)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "wb") as fh:
        fh.write(data)
    return {
        "output": os.path.abspath(output_path),
        "format": fmt,
        "method": "mermaid-renderer",
        "file_size": os.path.getsize(output_path),
        "url": url,
    }
