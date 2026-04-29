"""
Client-side helpers for the persistent LLDB session daemon.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

MAX_MESSAGE_BYTES = 1024 * 1024


def resolve_session_file(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()

    env_override = os.environ.get("CLI_ANYTHING_LLDB_SESSION_FILE")
    if env_override:
        return Path(env_override).expanduser().resolve()

    scope = os.environ.get("CLI_ANYTHING_LLDB_SESSION_SCOPE") or os.getcwd()
    digest = hashlib.sha256(os.path.abspath(scope).encode("utf-8")).hexdigest()[:12]
    root = Path(tempfile.gettempdir()) / "cli-anything-lldb"
    return (root / f"session-{digest}.json").resolve()


def _validate_state_file(state_file: Path):
    stat_result = state_file.stat()
    if os.name != "nt":
        if stat_result.st_uid != os.getuid():
            raise RuntimeError(
                f"Refusing to use session state file not owned by the current user: {state_file}"
            )
        if stat_result.st_mode & 0o077:
            raise RuntimeError(f"Session state file permissions are too broad: {state_file}")


def _load_state_file(state_file: Path) -> dict[str, Any]:
    _validate_state_file(state_file)
    return json.loads(state_file.read_text(encoding="utf-8"))


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = conn.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("Unexpected EOF while reading response")
        chunks.extend(chunk)
    return bytes(chunks)


def _recv_message(conn: socket.socket) -> dict[str, Any]:
    header = _recv_exact(conn, 4)
    message_size = struct.unpack("!I", header)[0]
    if message_size <= 0 or message_size > MAX_MESSAGE_BYTES:
        raise ValueError(f"Invalid message size: {message_size}")
    payload = _recv_exact(conn, message_size)
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("Response payload must be a JSON object")
    return message


def _send_message(conn: socket.socket, payload: dict[str, Any]):
    raw = json.dumps(payload).encode("utf-8")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("Request payload is too large")
    conn.sendall(struct.pack("!I", len(raw)))
    conn.sendall(raw)


def _request(state_file: Path, method: str, *args, **kwargs):
    state = _load_state_file(state_file)
    token = state.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError(f"Session state file is missing a valid token: {state_file}")

    with socket.create_connection((state["host"], state["port"]), timeout=5.0) as conn:
        payload = {
            "token": token,
            "method": method,
            "args": list(args),
            "kwargs": kwargs,
        }
        _send_message(conn, payload)
        return _recv_message(conn)


def _spawn_server(state_file: Path):
    cmd = [
        sys.executable,
        "-m",
        "cli_anything.lldb.utils.session_server",
        "--state-file",
        str(state_file),
    ]
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **popen_kwargs)


def ensure_server(state_file: Path, timeout: float = 10.0):
    if state_file.exists():
        try:
            response = _request(state_file, "ping")
            if response.get("ok"):
                return
        except Exception:
            try:
                state_file.unlink()
            except FileNotFoundError:
                pass

    _spawn_server(state_file)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state_file.exists():
            try:
                response = _request(state_file, "ping")
                if response.get("ok"):
                    return
            except Exception:
                pass
        time.sleep(0.1)
    raise RuntimeError("Timed out starting the LLDB session daemon")


class RemoteLLDBSessionProxy:
    """Thin RPC proxy that mirrors LLDBSession methods."""

    def __init__(self, state_file: Path):
        self._state_file = state_file

    def call(self, method: str, *args, **kwargs):
        ensure_server(self._state_file)
        response = _request(self._state_file, method, *args, **kwargs)
        if response.get("ok"):
            return response.get("data")
        raise RuntimeError(response.get("error") or f"Remote call failed: {method}")

    def session_status(self):
        return self.call("session_status")

    def shutdown(self):
        try:
            return self.call("shutdown")
        finally:
            try:
                self._state_file.unlink()
            except FileNotFoundError:
                pass

    def __getattr__(self, name: str):
        return lambda *args, **kwargs: self.call(name, *args, **kwargs)
