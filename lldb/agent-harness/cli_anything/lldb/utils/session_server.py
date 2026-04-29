"""
Background LLDB session server for persistent non-REPL workflows.
"""

from __future__ import annotations

import argparse
import base64
import hmac
import json
import os
import socket
import struct
import sys
import time
from pathlib import Path
from typing import Any

from cli_anything.lldb.core.session import LLDBSession

MAX_MESSAGE_BYTES = 1024 * 1024


def _encode_token(token: bytes) -> str:
    return base64.b64encode(token).decode("ascii")


def _prepare_state_dir(state_dir: Path):
    state_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(state_dir, 0o700)
        except OSError:
            pass


def _write_state_file(state_file: Path, address: tuple[str, int], token: bytes):
    _prepare_state_dir(state_file.parent)
    payload = {
        "host": address[0],
        "port": address[1],
        "token": _encode_token(token),
        "pid": os.getpid(),
    }

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_BINARY", 0)
    if os.name != "nt":
        flags |= getattr(os, "O_NOFOLLOW", 0)

    fd = os.open(str(state_file), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as state_fp:
        json.dump(payload, state_fp)

    if os.name != "nt":
        try:
            os.chmod(state_file, 0o600)
        except OSError:
            pass


def _remove_state_file(state_file: Path):
    try:
        state_file.unlink()
    except FileNotFoundError:
        pass


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = conn.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("Unexpected EOF while reading request")
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
        raise ValueError("Request payload must be a JSON object")
    return message


def _send_message(conn: socket.socket, payload: dict[str, Any]):
    raw = json.dumps(payload).encode("utf-8")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("Response payload is too large")
    conn.sendall(struct.pack("!I", len(raw)))
    conn.sendall(raw)


def _validate_request(request: dict[str, Any]):
    method = request.get("method")
    args = request.get("args", [])
    kwargs = request.get("kwargs", {})
    if not isinstance(method, str) or not method:
        raise ValueError("Request is missing a valid method name")
    if not isinstance(args, list):
        raise ValueError("Request args must be a list")
    if not isinstance(kwargs, dict):
        raise ValueError("Request kwargs must be an object")


class SessionServer:
    """Owns one persistent LLDBSession inside a lightweight RPC daemon."""

    def __init__(self):
        self._session: LLDBSession | None = None

    def handle(self, request: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        _validate_request(request)
        method = request["method"]
        args = request.get("args", [])
        kwargs = request.get("kwargs", {})

        if method == "ping":
            return {"ok": True, "data": {"status": "ok"}}, False

        if method == "session_status":
            status = self._session.session_status() if self._session is not None else {
                "has_target": False,
                "has_process": False,
                "process_origin": None,
            }
            return {"ok": True, "data": status}, False

        if method == "shutdown":
            self.close()
            return {"ok": True, "data": {"status": "closed"}}, True

        if method == "target_create" and self._session is not None:
            self.close()

        try:
            if self._session is None:
                self._session = LLDBSession()

            handler = getattr(self._session, method)
            data = handler(*args, **kwargs)
            return {"ok": True, "data": data}, False
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "type": exc.__class__.__name__,
            }, False

    def close(self):
        if self._session is not None:
            self._session.destroy()
            self._session = None


def serve(state_file: Path, idle_timeout: int = 300):
    token = os.urandom(32)
    encoded_token = _encode_token(token)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen()
    server_socket.settimeout(1.0)
    _write_state_file(state_file, server_socket.getsockname(), token)

    server = SessionServer()
    last_activity = time.time()

    try:
        while True:
            try:
                conn, _address = server_socket.accept()
            except socket.timeout:
                if time.time() - last_activity >= idle_timeout:
                    break
                continue

            last_activity = time.time()
            should_stop = False
            with conn:
                try:
                    request = _recv_message(conn)
                    request_token = request.get("token")
                    if not isinstance(request_token, str) or not hmac.compare_digest(
                        request_token, encoded_token
                    ):
                        response = {
                            "ok": False,
                            "error": "Unauthorized session client",
                            "type": "PermissionError",
                        }
                    else:
                        sanitized = {
                            "method": request.get("method"),
                            "args": request.get("args", []),
                            "kwargs": request.get("kwargs", {}),
                        }
                        response, should_stop = server.handle(sanitized)
                except Exception as exc:
                    response = {
                        "ok": False,
                        "error": str(exc),
                        "type": exc.__class__.__name__,
                    }
                _send_message(conn, response)

            if should_stop:
                break
    finally:
        server.close()
        server_socket.close()
        _remove_state_file(state_file)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Internal LLDB session daemon")
    parser.add_argument("--state-file", required=True, help="Session state file path")
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=int(os.environ.get("CLI_ANYTHING_LLDB_IDLE_TIMEOUT", "300")),
        help="Seconds of inactivity before daemon exits",
    )
    args = parser.parse_args(argv)
    serve(Path(args.state_file), idle_timeout=args.idle_timeout)


if __name__ == "__main__":
    main(sys.argv[1:])
