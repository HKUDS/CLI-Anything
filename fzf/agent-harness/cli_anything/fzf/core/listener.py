"""Owned fzf listener lifecycle with Unix-socket-first containment."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from cli_anything.fzf.core.errors import BackendError, PolicyError, ValidationError
from cli_anything.fzf.core.planner import ExecutionPlan, assert_executable
from cli_anything.fzf.core.results import exit_semantics, parse_output
from cli_anything.fzf.core.validation import (
    Policy,
    binding_is_hazardous,
    ensure_contained,
    pid_matches,
    process_start_time,
    validate_listen_address,
)


STATE_SCHEMA = "cli-anything-fzf-listener/v1"
MAX_HTTP_RESPONSE = 4 * 1024 * 1024
MAX_SELECTION_BYTES = 128 * 1024 * 1024


@contextmanager
def _state_lock(state_dir: Path) -> Iterator[None]:
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = state_dir / ".listener.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        os.chmod(lock_path, 0o600)
        try:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _safe_state_dir(value: str, *, create: bool = True) -> Path:
    path = Path(value).expanduser()
    if path.is_symlink():
        raise PolicyError("listener_state_unsafe", "Listener state directory cannot be a symlink")
    resolved = path.resolve(strict=False)
    if resolved == Path("/") or resolved == Path.home().resolve():
        raise PolicyError("listener_state_unsafe", "Listener state directory is too broad")
    if create:
        resolved.mkdir(mode=0o700, parents=True, exist_ok=True)
    elif not resolved.is_dir():
        raise ValidationError("listener_not_found", f"Listener state directory does not exist: {resolved}")
    if resolved.is_symlink() or not resolved.is_dir():
        raise PolicyError("listener_state_unsafe", f"Invalid listener state directory: {resolved}")
    os.chmod(resolved, 0o700)
    return resolved


def _load_state(state_dir_value: str) -> tuple[Path, dict[str, Any]]:
    state_dir = _safe_state_dir(state_dir_value, create=False)
    path = state_dir / "state.json"
    if not path.is_file():
        raise ValidationError("listener_not_found", f"No listener state at {path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("listener_state_invalid", f"Could not read listener state: {exc}") from exc
    if state.get("schema_version") != STATE_SCHEMA:
        raise ValidationError("listener_state_invalid", "Unsupported listener state schema")
    return state_dir, state


def _api_key(path_value: str | None) -> tuple[str | None, str | None]:
    if path_value is None:
        return None, None
    path = Path(path_value).expanduser().resolve(strict=True)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise PolicyError("api_key_file_unsafe", "API key path must be a regular file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PolicyError("api_key_file_unsafe", "API key file must not be accessible by group or others")
    if info.st_size > 4096:
        raise ValidationError("api_key_file_invalid", "API key file exceeds 4096 bytes")
    value = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not value or "\x00" in value or "\r" in value or "\n" in value:
        raise ValidationError("api_key_file_invalid", "API key file must contain one non-empty line")
    return value, hashlib.sha256(value.encode("utf-8")).hexdigest()


def _address_for_request(address: dict[str, Any], timeout: float) -> tuple[socket.socket, str]:
    if address["kind"] == "unix":
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(timeout)
        client.connect(address["path"])
        return client, "localhost"
    client = socket.create_connection((address["host"], int(address["port"])), timeout=timeout)
    return client, address["host"]


def _http_request(
    address: dict[str, Any],
    *,
    method: str,
    path: str = "/",
    body: bytes = b"",
    api_key: str | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    client, host = _address_for_request(address, timeout)
    with client:
        client.settimeout(timeout)
        headers = [
            f"{method} {path} HTTP/1.1",
            f"Host: {host}",
            "Connection: close",
        ]
        if body:
            headers.append(f"Content-Length: {len(body)}")
        if api_key is not None:
            headers.append(f"X-API-Key: {api_key}")
        request = ("\r\n".join(headers) + "\r\n\r\n").encode("ascii") + body
        client.sendall(request)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = client.recv(65_536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_HTTP_RESPONSE:
                raise BackendError("listener_response_too_large", "Listener response exceeded 4 MiB")
            chunks.append(chunk)
    raw = b"".join(chunks)
    head, marker, response_body = raw.partition(b"\r\n\r\n")
    if not marker:
        raise BackendError("listener_protocol_error", "Listener returned a malformed HTTP response")
    lines = head.split(b"\r\n")
    match = lines[0].decode("ascii", "replace").split(" ", 2)
    if len(match) < 2 or not match[1].isdigit():
        raise BackendError("listener_protocol_error", "Listener returned a malformed status line")
    status_code = int(match[1])
    content_type = ""
    for line in lines[1:]:
        name, separator, value = line.partition(b":")
        if separator and name.lower() == b"content-type":
            content_type = value.decode("ascii", "replace").strip()
    parsed: Any = None
    if "json" in content_type or response_body.lstrip().startswith((b"{", b"[")):
        try:
            parsed = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
    return {
        "status_code": status_code,
        "content_type": content_type,
        "body": response_body,
        "json": parsed,
    }


def _remove_owned_socket(address: dict[str, Any], state_dir: Path) -> bool:
    if address.get("kind") != "unix":
        return False
    path = ensure_contained(Path(address["path"]), state_dir)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISSOCK(mode):
        raise PolicyError("socket_collision", f"Refusing to remove non-socket path: {path}")
    path.unlink()
    return True


def start_listener(
    plan: ExecutionPlan,
    *,
    state_dir_value: str,
    address_value: str | None,
    unsafe: bool,
    api_key_file: str | None,
    policy: Policy,
    startup_timeout: float = 5.0,
) -> dict[str, Any]:
    """Start an owned listener worker and wait for an authenticated GET probe."""

    assert_executable(plan)
    state_dir = _safe_state_dir(state_dir_value)
    state_path = state_dir / "state.json"
    config_path = state_dir / "worker.json"
    input_path = state_dir / "input.bin"
    selection_path = state_dir / "selection.bin"
    address_value = address_value or str(state_dir / "fzf.sock")
    address = validate_listen_address(address_value)
    if address["kind"] == "unix":
        lexical_socket_path = Path(str(address["path"]))
        if lexical_socket_path.exists() or lexical_socket_path.is_symlink():
            raise PolicyError(
                "socket_collision", f"Listener socket path already exists: {lexical_socket_path}"
            )
        socket_path = ensure_contained(lexical_socket_path, state_dir)
        address["path"] = str(socket_path)
        if socket_path.exists() or socket_path.is_symlink():
            raise PolicyError("socket_collision", f"Listener socket path already exists: {socket_path}")
    else:
        if not policy.allow_network_listener:
            raise PolicyError("network_listener_denied", "TCP listeners require --allow-network-listener")
        if int(address["port"]) == 0:
            raise ValidationError(
                "listener_address_invalid",
                "Managed TCP listeners require an explicit non-zero port for deterministic ownership",
            )
    key, key_fingerprint = _api_key(api_key_file)
    if address["kind"] == "tcp" and not address["loopback"] and key is None:
        raise PolicyError("listener_auth_required", "Non-loopback listeners require --api-key-file")
    if unsafe:
        if not (policy.allow_unsafe_listener and policy.allow_command_actions):
            raise PolicyError(
                "unsafe_listener_denied",
                "--listen-unsafe requires --allow-unsafe-listener and --allow-command-actions",
            )
        if key is None:
            raise PolicyError("listener_auth_required", "Unsafe listeners require --api-key-file")
    if not 0.1 <= startup_timeout <= 60:
        raise ValidationError("timeout_invalid", "Listener startup timeout must be 0.1 to 60 seconds")

    with _state_lock(state_dir):
        if state_path.exists():
            _, existing = _load_state(str(state_dir))
            running = pid_matches(int(existing.get("worker_pid", 0)), existing.get("worker_start_time"))
            raise PolicyError(
                "listener_state_exists",
                "Listener state already exists; stop it or remove proven-stale state explicitly",
                details={"running": running, "state_path": str(state_path)},
            )
        data = plan.input_bytes or b""
        input_path.write_bytes(data)
        os.chmod(input_path, 0o600)
        selection_path.write_bytes(b"")
        os.chmod(selection_path, 0o600)
        argv = list(plan.public["argv"])
        config = {
            "schema_version": STATE_SCHEMA,
            "argv": argv,
            "input_path": str(input_path),
            "selection_path": str(selection_path),
            "state_path": str(state_path),
            "state_dir": str(state_dir),
            "address": address,
        }
        _atomic_json(config_path, config)
        state = {
            "schema_version": STATE_SCHEMA,
            "owner_id": str(uuid.uuid4()),
            "status": "starting",
            "state_dir": str(state_dir),
            "state_path": str(state_path),
            "address": address,
            "unsafe": unsafe,
            "authenticated": key is not None,
            "api_key_fingerprint": key_fingerprint,
            "plan_id": plan.public["plan_id"],
            "backend": plan.public["backend"],
            "argv": argv,
            "selection_path": str(selection_path),
            "output_format": plan.public.get("listener", {}).get(
                "output_format",
                {"print0": False, "print_query": False, "expect": False},
            ),
            "worker_pid": None,
            "worker_start_time": None,
            "backend_pid": None,
            "backend_start_time": None,
            "started_at": time.time(),
            "owned_paths": [str(config_path), str(input_path), str(selection_path)],
        }
        _atomic_json(state_path, state)
        worker_env = dict(plan.environment)
        if key is not None:
            worker_env["FZF_API_KEY"] = key
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "cli_anything.fzf.listener_worker", str(config_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=worker_env,
                start_new_session=True,
            )
        except OSError as exc:
            for path in (config_path, input_path, selection_path):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            state.update(
                {
                    "status": "failed",
                    "failure": f"could not start listener worker: {exc}",
                    "worker_pid": None,
                    "backend_pid": None,
                }
            )
            _atomic_json(state_path, state)
            raise BackendError(
                "listener_start_failed",
                f"Could not start listener worker: {exc}",
                details={"state_path": str(state_path)},
            ) from exc
        current = json.loads(state_path.read_text(encoding="utf-8"))
        current["worker_pid"] = process.pid
        current["worker_start_time"] = process_start_time(process.pid)
        state = current
        _atomic_json(state_path, state)

    deadline = time.monotonic() + startup_timeout
    last_error = "listener did not become ready"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            last_error = f"listener worker exited with status {process.returncode}"
            break
        try:
            response = _http_request(address, method="GET", api_key=key, timeout=0.25)
            if response["status_code"] == 200:
                _, ready = _load_state(str(state_dir))
                ready["status"] = "running"
                _atomic_json(state_path, ready)
                return listener_status(str(state_dir), api_key_file=api_key_file, probe=True)
            last_error = f"listener readiness returned HTTP {response['status_code']}"
        except (OSError, BackendError) as exc:
            last_error = str(exc)
        time.sleep(0.05)

    # Re-read state because the worker may have published the backend identity
    # after the parent wrote its own PID. Both are session leaders, so terminate
    # only groups whose PID/start-time pair still proves ownership.
    try:
        failed_state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        failed_state = state
    owned = [
        (int(failed_state.get("worker_pid") or process.pid), failed_state.get("worker_start_time")),
        (int(failed_state.get("backend_pid") or 0), failed_state.get("backend_start_time")),
    ]
    for pid, start_time in owned:
        if pid_matches(pid, start_time):
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    cleanup_deadline = time.monotonic() + 1.0
    while time.monotonic() < cleanup_deadline and any(
        pid_matches(pid, start_time) for pid, start_time in owned
    ):
        time.sleep(0.02)
    for pid, start_time in reversed(owned):
        if pid_matches(pid, start_time):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        pass
    try:
        _remove_owned_socket(address, state_dir)
    except PolicyError:
        pass
    for path in (config_path, input_path, selection_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    failed_state["status"] = "failed"
    failed_state["failure"] = last_error
    failed_state["last_worker_pid"] = int(failed_state.get("worker_pid") or process.pid)
    failed_state["last_backend_pid"] = failed_state.get("backend_pid")
    failed_state["worker_pid"] = None
    failed_state["backend_pid"] = None
    _atomic_json(state_path, failed_state)
    raise BackendError("listener_start_failed", last_error, details={"state_path": str(state_path)})


def listener_status(
    state_dir_value: str,
    *,
    api_key_file: str | None = None,
    probe: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Return ownership/liveness and optional real-backend GET state."""

    if not 1 <= limit <= 10_000 or offset < 0:
        raise ValidationError("listener_query_invalid", "limit must be 1..10000 and offset non-negative")
    state_dir, state = _load_state(state_dir_value)
    worker_alive = pid_matches(int(state.get("worker_pid") or 0), state.get("worker_start_time"))
    backend_alive = pid_matches(int(state.get("backend_pid") or 0), state.get("backend_start_time"))
    result = {
        key: value
        for key, value in state.items()
        if key not in {"api_key", "environment"}
    }
    result.update(
        {
            "worker_alive": worker_alive,
            "backend_alive": backend_alive,
            "owned": worker_alive or backend_alive,
            "socket_exists": (
                Path(state["address"]["path"]).exists() if state["address"]["kind"] == "unix" else None
            ),
        }
    )
    if probe and backend_alive:
        key, fingerprint = _api_key(api_key_file)
        expected = state.get("api_key_fingerprint")
        if expected and fingerprint != expected:
            raise PolicyError("listener_auth_required", "Matching --api-key-file is required for this listener")
        response = _http_request(
            state["address"],
            method="GET",
            path=f"/?limit={limit}&offset={offset}",
            api_key=key,
        )
        result["http_status"] = response["status_code"]
        result["backend_state"] = response["json"]
    return result


def _listener_action_preflight(
    state_dir_value: str,
    action: str,
    *,
    policy: Policy,
    api_key_file: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    """Validate one action without contacting the backend or exposing a key."""

    hazardous = binding_is_hazardous(f"enter:{action}")
    _, state = _load_state(state_dir_value)
    key, fingerprint = _api_key(api_key_file)
    backend_alive = pid_matches(
        int(state.get("backend_pid") or 0), state.get("backend_start_time")
    )
    refusals: list[dict[str, str]] = []
    if hazardous and not policy.allow_command_actions:
        refusals.append(
            {
                "code": "command_actions_denied",
                "reason": "Command-capable listener actions require --allow-command-actions",
            }
        )
    if hazardous and not state.get("unsafe", False):
        refusals.append(
            {
                "code": "unsafe_listener_required",
                "reason": "Command-capable actions can be sent only to a listener started with --unsafe",
            }
        )
    expected = state.get("api_key_fingerprint")
    if expected and fingerprint != expected:
        refusals.append(
            {
                "code": "listener_auth_required",
                "reason": "Matching --api-key-file is required for this listener",
            }
        )
    if not backend_alive:
        refusals.append(
            {"code": "listener_not_running", "reason": "The recorded fzf listener is not running"}
        )
    public = {
        "state_dir": str(Path(state_dir_value).expanduser().resolve(strict=False)),
        "action": action,
        "hazardous": hazardous,
        "listener_unsafe": bool(state.get("unsafe", False)),
        "authenticated": bool(expected),
        "backend_alive": backend_alive,
        "refused": bool(refusals),
        "refusal_reasons": refusals,
    }
    return public, state, key


def listener_action_plan(
    state_dir_value: str,
    action: str,
    *,
    policy: Policy,
    api_key_file: str | None = None,
) -> dict[str, Any]:
    """Return non-executing listener action evidence and all refusal reasons."""

    public, _, _ = _listener_action_preflight(
        state_dir_value, action, policy=policy, api_key_file=api_key_file
    )
    return {"dry_run": True, "executed": False, **public}


def listener_action(
    state_dir_value: str,
    action: str,
    *,
    policy: Policy,
    api_key_file: str | None = None,
) -> dict[str, Any]:
    """POST one validated fzf action to an owned listener."""

    preflight, state, key = _listener_action_preflight(
        state_dir_value, action, policy=policy, api_key_file=api_key_file
    )
    if preflight["refusal_reasons"]:
        first = preflight["refusal_reasons"][0]
        error_type = BackendError if first["code"] == "listener_not_running" else PolicyError
        raise error_type(first["code"], first["reason"])
    response = _http_request(
        state["address"],
        method="POST",
        body=action.encode("utf-8"),
        api_key=key,
    )
    if not 200 <= response["status_code"] < 300:
        raise BackendError(
            "listener_action_failed",
            f"fzf listener returned HTTP {response['status_code']}",
            details={"status_code": response["status_code"]},
        )
    return {
        "action": action,
        "hazardous": preflight["hazardous"],
        "status_code": response["status_code"],
        "listener": str(Path(state_dir_value).expanduser().resolve(strict=False)),
    }


def listener_result(state_dir_value: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Read one bounded snapshot of an owned listener's exact output file."""

    state_dir, state = _load_state(state_dir_value)
    lexical_selection_path = Path(state.get("selection_path") or state_dir / "selection.bin")
    if lexical_selection_path.is_symlink():
        raise PolicyError(
            "listener_result_unsafe", "The listener selection artifact cannot be a symlink"
        )
    selection_path = ensure_contained(lexical_selection_path, state_dir)
    try:
        selection_stat = selection_path.stat()
    except FileNotFoundError as exc:
        raise ValidationError(
            "listener_result_not_found", "The listener selection artifact is no longer available"
        ) from exc
    if not stat.S_ISREG(selection_stat.st_mode):
        raise PolicyError(
            "listener_result_unsafe", "The listener selection artifact must be a regular file"
        )
    size = selection_stat.st_size
    if size > MAX_SELECTION_BYTES:
        raise BackendError(
            "listener_result_too_large",
            f"Listener output exceeds the {MAX_SELECTION_BYTES}-byte limit",
        )
    output_format = state.get("output_format") or {}
    public = {
        "state_dir": str(state_dir),
        "selection_path": str(selection_path),
        "status": state.get("status"),
        "backend_alive": pid_matches(
            int(state.get("backend_pid") or 0), state.get("backend_start_time")
        ),
        "output_format": {
            "print0": bool(output_format.get("print0", False)),
            "print_query": bool(output_format.get("print_query", False)),
            "expect": bool(output_format.get("expect", False)),
        },
        "byte_count": size,
        "content_read": not dry_run,
    }
    if dry_run:
        return {"dry_run": True, "executed": False, **public, "result": None}
    with selection_path.open("rb") as handle:
        data = handle.read(MAX_SELECTION_BYTES + 1)
    if len(data) > MAX_SELECTION_BYTES:
        raise BackendError(
            "listener_result_too_large",
            f"Listener output exceeds the {MAX_SELECTION_BYTES}-byte limit",
        )
    public["byte_count"] = len(data)
    parsed = parse_output(
        data,
        print0=public["output_format"]["print0"],
        print_query=public["output_format"]["print_query"],
        expect=public["output_format"]["expect"],
    )
    exit_code = state.get("backend_exit_code")
    semantics = (
        exit_semantics(exit_code)
        if isinstance(exit_code, int)
        else {
            "process_exit_code": None,
            "meaning": "running-or-not-recorded",
            "backend_completed": False,
            "semantic_success": False,
            "no_match": False,
            "interrupted": False,
        }
    )
    return {
        "dry_run": False,
        "executed": True,
        **public,
        "completion_observed": isinstance(exit_code, int),
        "result": {**semantics, **parsed},
    }


def stop_listener(state_dir_value: str, *, timeout: float = 3.0, remove_state: bool = False) -> dict[str, Any]:
    """Stop only PIDs whose start times match the owned listener record."""

    if not 0.1 <= timeout <= 30:
        raise ValidationError("timeout_invalid", "Stop timeout must be 0.1 to 30 seconds")
    state_dir, state = _load_state(state_dir_value)
    worker_pid = int(state.get("worker_pid") or 0)
    backend_pid = int(state.get("backend_pid") or 0)
    signalled: list[int] = []
    if pid_matches(worker_pid, state.get("worker_start_time")):
        os.kill(worker_pid, signal.SIGTERM)
        signalled.append(worker_pid)
    elif pid_matches(backend_pid, state.get("backend_start_time")):
        os.killpg(backend_pid, signal.SIGTERM)
        signalled.append(backend_pid)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_matches(worker_pid, state.get("worker_start_time")) and not pid_matches(
            backend_pid, state.get("backend_start_time")
        ):
            break
        time.sleep(0.05)
    killed: list[int] = []
    for pid, start_time in (
        (backend_pid, state.get("backend_start_time")),
        (worker_pid, state.get("worker_start_time")),
    ):
        if pid_matches(pid, start_time):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            killed.append(pid)
    cleanup_deadline = time.monotonic() + 1.0
    while time.monotonic() < cleanup_deadline:
        if not pid_matches(worker_pid, state.get("worker_start_time")) and not pid_matches(
            backend_pid, state.get("backend_start_time")
        ):
            break
        time.sleep(0.02)
    surviving = [
        pid
        for pid, start_time in (
            (worker_pid, state.get("worker_start_time")),
            (backend_pid, state.get("backend_start_time")),
        )
        if pid_matches(pid, start_time)
    ]
    if surviving:
        raise BackendError(
            "listener_stop_failed",
            "Owned listener processes survived TERM/KILL cleanup",
            details={"pids": surviving},
        )
    socket_removed = _remove_owned_socket(state["address"], state_dir)
    for item in state.get("owned_paths", []):
        path = ensure_contained(Path(item), state_dir)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    state.update(
        {
            "status": "stopped",
            "stopped_at": time.time(),
            "last_worker_pid": worker_pid or state.get("last_worker_pid"),
            "last_backend_pid": backend_pid or state.get("last_backend_pid"),
            "worker_pid": None,
            "backend_pid": None,
        }
    )
    _atomic_json(state_dir / "state.json", state)
    state_removed = False
    if remove_state:
        (state_dir / "state.json").unlink()
        state_removed = True
    return {
        "stopped": True,
        "signalled_pids": signalled,
        "killed_pids": killed,
        "socket_removed": socket_removed,
        "cleanup_verified": True,
        "state_removed": state_removed,
        "state_dir": str(state_dir),
    }


def remove_stale_state(state_dir_value: str) -> dict[str, Any]:
    """Remove state only after both recorded process identities are dead."""

    state_dir, state = _load_state(state_dir_value)
    if pid_matches(int(state.get("worker_pid") or 0), state.get("worker_start_time")) or pid_matches(
        int(state.get("backend_pid") or 0), state.get("backend_start_time")
    ):
        raise PolicyError("listener_still_running", "Cannot remove state for a running owned listener")
    socket_removed = _remove_owned_socket(state["address"], state_dir)
    removed: list[str] = []
    for item in [*state.get("owned_paths", []), str(state_dir / "state.json")]:
        path = ensure_contained(Path(item), state_dir)
        try:
            path.unlink()
            removed.append(str(path))
        except FileNotFoundError:
            pass
    return {"removed": removed, "socket_removed": socket_removed, "state_dir": str(state_dir)}
