"""session.py — persistent sign-in state for the Gatekeeper CLI.

The session (Supabase access + refresh token) is stored in
``$GATEKEEPER_HOME/session.json`` (default ``~/.cli-anything-gatekeeper``),
mode 0600, replaced atomically; writers and refreshes serialize on
``session.lock``. ``GATEKEEPER_TOKEN`` in the
environment overrides the file — useful for CI and agents.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from cli_anything.gatekeeper.utils import gk_backend as gk

REFRESH_MARGIN_S = 120


def home() -> Path:
    p = Path(os.environ.get("GATEKEEPER_HOME", Path.home() / ".cli-anything-gatekeeper")).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def session_path() -> Path:
    return home() / "session.json"


def jwt_claims(token: str) -> dict[str, Any]:
    """Decode a JWT payload without verifying it (the server verifies)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001
        return {}


@contextlib.contextmanager
def _writer_lock():
    """Serialize writers (and refreshes) across processes via session.lock."""
    lock = home() / "session.lock"
    with open(lock, "a+") as fh:
        try:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except ImportError:  # Windows: best effort
            pass
        try:
            yield
        finally:
            try:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a 0600 temp file in the same directory, then os.replace() it.

    Readers never see a truncated or partial file: they get either the old
    session or the new one. (Truncate-in-place, even under an exclusive lock,
    exposes an empty file to readers that don't take the lock.)
    """
    # mkstemp creates the file with mode 0600.
    fd, tmp = tempfile.mkstemp(prefix=".session-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def _record(tokens: dict[str, Any], email: str | None) -> dict[str, Any]:
    access = tokens["access_token"]
    claims = jwt_claims(access)
    return {
        "base_url": gk.base_url(),
        "access_token": access,
        "refresh_token": tokens.get("refresh_token", ""),
        "expires_at": int(tokens.get("expires_at") or claims.get("exp") or 0),
        "email": email or claims.get("email") or (tokens.get("user") or {}).get("email"),
        "saved_at": int(time.time()),
    }


def save(tokens: dict[str, Any], email: str | None = None) -> dict[str, Any]:
    record = _record(tokens, email)
    with _writer_lock():
        _atomic_write_json(session_path(), record)
    return record


def load() -> dict[str, Any] | None:
    p = session_path()
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8") or "{}")
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) and data.get("access_token") else None


def clear() -> bool:
    with _writer_lock():
        p = session_path()
        if p.is_file():
            p.unlink()
            return True
    return False


def _needs_refresh(s: dict[str, Any]) -> bool:
    exp = int(s.get("expires_at") or 0)
    return bool(exp) and exp - time.time() < REFRESH_MARGIN_S


def get_token(required: bool = True) -> str | None:
    """Return a valid access token, refreshing it when close to expiry."""
    env = os.environ.get("GATEKEEPER_TOKEN", "").strip()
    if env:
        return env
    s = load()
    if not s:
        if required:
            raise gk.GatekeeperError(
                "Not signed in. Run `cli-anything-gatekeeper auth login <email>` "
                "or set GATEKEEPER_TOKEN.", 401)
        return None
    if _needs_refresh(s):
        with _writer_lock():
            # Another process may have refreshed while we waited for the lock;
            # reusing its result avoids spending the (rotating) refresh token twice.
            s = load() or s
            if _needs_refresh(s):
                if not s.get("refresh_token"):
                    raise gk.GatekeeperError("Session expired — run `auth login` again.", 401)
                fresh = gk.refresh_session(s["refresh_token"])
                s = _record(fresh, s.get("email"))
                _atomic_write_json(session_path(), s)
    return s["access_token"]


def status() -> dict[str, Any]:
    env = os.environ.get("GATEKEEPER_TOKEN", "").strip()
    if env:
        c = jwt_claims(env)
        return {"signed_in": True, "source": "GATEKEEPER_TOKEN", "email": c.get("email"),
                "expires_at": c.get("exp"), "expires_in_s": (c.get("exp") or 0) - int(time.time())}
    s = load()
    if not s:
        return {"signed_in": False, "session_file": str(session_path())}
    exp = int(s.get("expires_at") or 0)
    return {"signed_in": True, "source": str(session_path()), "email": s.get("email"),
            "expires_at": exp, "expires_in_s": exp - int(time.time()),
            "refreshable": bool(s.get("refresh_token")), "base_url": s.get("base_url")}
