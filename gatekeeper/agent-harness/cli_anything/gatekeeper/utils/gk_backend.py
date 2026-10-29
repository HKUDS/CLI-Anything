"""gk_backend.py — HTTP client for the live Gatekeeper AI service.

Gatekeeper AI is a hosted procurement-evaluation engine (gatekeeper.blog).
The "real software" this harness drives is its production HTTP API:

    GET  /api/health      liveness probe (no auth)
    GET  /api/config      public Supabase URL + anon key, billing flag
    POST /api/evaluate    run an evaluation  (Bearer <Supabase access token>)

plus the Supabase project behind it, for sign-in (GoTrue) and reading the
user's saved reports (PostgREST, row-level security scoped to the user).

Only the standard library is used, so the harness installs anywhere.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "https://www.gatekeeper.blog"
USER_AGENT = "cli-anything-gatekeeper/1.0.0"

# An evaluation is one long model call: the live engine takes ~60-90 s on a
# 3-document tender. Leave generous headroom before giving up.
EVALUATE_TIMEOUT_S = float(os.environ.get("GATEKEEPER_TIMEOUT", "300"))


class GatekeeperError(RuntimeError):
    """An error from the Gatekeeper service, carrying the HTTP status."""

    def __init__(self, message: str, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def base_url() -> str:
    return os.environ.get("GATEKEEPER_URL", DEFAULT_BASE_URL).rstrip("/")


def _request(
    method: str,
    url: str,
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any, dict[str, str]]:
    """Perform an HTTP request and return (status, parsed_json_or_text, headers).

    Non-2xx responses are returned, not raised, so callers can map 401/402.
    Network failures raise GatekeeperError.
    """
    data = None
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw, rh = resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        status, raw, rh = exc.code, exc.read(), dict(exc.headers or {})
    except urllib.error.URLError as exc:
        raise GatekeeperError(f"Cannot reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise GatekeeperError(f"Timed out after {timeout:.0f}s calling {url}") from exc
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed: Any = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = text
    return status, parsed, rh


# ---------------------------------------------------------------------------
# Gatekeeper API
# ---------------------------------------------------------------------------

def health() -> dict[str, Any]:
    status, data, _ = _request("GET", f"{base_url()}/api/health", timeout=30)
    ok = status == 200 and isinstance(data, dict) and (
        data.get("ok") is True or data.get("status") == "ok"
    )
    return {"ok": ok, "http_status": status, "url": base_url(), "response": data}


_config_cache: dict[str, dict[str, Any]] = {}


def get_config() -> dict[str, Any]:
    """Public config: supabaseUrl, supabaseAnonKey, billingAvailable."""
    url = base_url()
    if url in _config_cache:
        return _config_cache[url]
    status, data, _ = _request("GET", f"{url}/api/config", timeout=30)
    if status != 200 or not isinstance(data, dict) or "supabaseUrl" not in data:
        raise GatekeeperError(f"/api/config returned HTTP {status}", status, data)
    _config_cache[url] = data
    return data


def evaluate(documents: list[dict[str, str]], token: str,
             weights: dict[str, int] | None = None,
             timeout: float | None = None) -> tuple[int, Any]:
    """POST /api/evaluate. Returns (http_status, body) — caller maps errors."""
    body: dict[str, Any] = {"documents": documents}
    if weights:
        body["weights"] = weights
    status, data, _ = _request(
        "POST", f"{base_url()}/api/evaluate", body=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout or EVALUATE_TIMEOUT_S,
    )
    return status, data


# ---------------------------------------------------------------------------
# Supabase (auth + saved reports)
# ---------------------------------------------------------------------------

def _sb_headers(token: str | None = None) -> dict[str, str]:
    cfg = get_config()
    h = {"apikey": cfg["supabaseAnonKey"]}
    h["Authorization"] = f"Bearer {token or cfg['supabaseAnonKey']}"
    return h


def _sb_error(data: Any, status: int) -> str:
    if isinstance(data, dict):
        for k in ("error_description", "msg", "message", "error"):
            if data.get(k):
                return str(data[k])
    return f"HTTP {status}"


def send_magic_link(email: str) -> dict[str, Any]:
    """Same call the website's /login page makes (signInWithOtp)."""
    cfg = get_config()
    redirect = f"{base_url()}/login?next=/evaluate"
    url = f"{cfg['supabaseUrl']}/auth/v1/otp?" + urllib.parse.urlencode({"redirect_to": redirect})
    status, data, _ = _request("POST", url, body={"email": email, "create_user": True},
                               headers=_sb_headers())
    if status >= 400:
        raise GatekeeperError(f"Could not send sign-in email: {_sb_error(data, status)}", status, data)
    return {"sent": True, "email": email}


def verify_code(email: str, code: str) -> dict[str, Any]:
    """Exchange the 6-digit code from the sign-in email for a session."""
    cfg = get_config()
    last = None
    for typ in ("email", "magiclink"):
        status, data, _ = _request("POST", f"{cfg['supabaseUrl']}/auth/v1/verify",
                                   body={"type": typ, "email": email, "token": code},
                                   headers=_sb_headers())
        if status < 400 and isinstance(data, dict) and data.get("access_token"):
            return data
        last = (status, data)
    raise GatekeeperError(f"Code rejected: {_sb_error(last[1], last[0])}", 401, last[1])


def resolve_magic_link(link: str) -> dict[str, Any]:
    """Turn a magic link into session tokens.

    Accepts either the link copied from the email (…/auth/v1/verify?token=…)
    — we request it without following the redirect and read the tokens from
    the Location header — or the URL the browser landed on (…#access_token=…).
    """
    frag = urllib.parse.urlparse(link).fragment
    if "access_token=" in frag:
        return _tokens_from_fragment(frag)

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: D401
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(link, headers={"User-Agent": USER_AGENT})
    try:
        resp = opener.open(req, timeout=30)
        location, status = resp.headers.get("Location", ""), resp.status
    except urllib.error.HTTPError as exc:
        location, status = (exc.headers or {}).get("Location", ""), exc.code
    except urllib.error.URLError as exc:
        raise GatekeeperError(f"Cannot open link: {exc.reason}") from exc
    frag = urllib.parse.urlparse(location).fragment
    if "access_token=" in frag:
        return _tokens_from_fragment(frag)
    params = dict(urllib.parse.parse_qsl(frag or urllib.parse.urlparse(location).query))
    reason = params.get("error_description") or params.get("error") or f"HTTP {status}, no tokens"
    raise GatekeeperError(
        f"Link did not yield a session ({reason}). Links are single-use and expire; "
        "request a new one with `auth login`.", 401)


def _tokens_from_fragment(frag: str) -> dict[str, Any]:
    p = dict(urllib.parse.parse_qsl(frag))
    out: dict[str, Any] = {"access_token": p["access_token"],
                           "refresh_token": p.get("refresh_token", "")}
    if p.get("expires_at"):
        out["expires_at"] = int(p["expires_at"])
    return out


def refresh_session(refresh_token: str) -> dict[str, Any]:
    cfg = get_config()
    status, data, _ = _request(
        "POST", f"{cfg['supabaseUrl']}/auth/v1/token?grant_type=refresh_token",
        body={"refresh_token": refresh_token}, headers=_sb_headers())
    if status in (400, 401, 403):
        # Refresh token revoked, expired or already used: a genuine sign-in problem.
        raise GatekeeperError(
            f"Session refresh rejected ({_sb_error(data, status)}) — run `auth login` again.", 401, data)
    if status >= 400 or not isinstance(data, dict) or not data.get("access_token"):
        # 429 / 5xx / malformed: transient. Keep the real status so callers
        # (and agents reading the exit code) retry instead of re-authenticating.
        raise GatekeeperError(
            f"Session refresh failed temporarily ({_sb_error(data, status)}); retry shortly.",
            status if status >= 400 else 502, data)
    return data


def get_user(access_token: str) -> dict[str, Any]:
    cfg = get_config()
    status, data, _ = _request("GET", f"{cfg['supabaseUrl']}/auth/v1/user",
                               headers=_sb_headers(access_token))
    if status >= 400:
        raise GatekeeperError(f"Token rejected: {_sb_error(data, status)}", 401, data)
    return data


def select_evaluations(token: str, params: dict[str, str]) -> list[dict[str, Any]]:
    """Read rows from the `evaluations` table as the signed-in user (RLS)."""
    cfg = get_config()
    url = f"{cfg['supabaseUrl']}/rest/v1/evaluations?" + urllib.parse.urlencode(params, safe=",.()*")
    status, data, _ = _request("GET", url, headers=_sb_headers(token))
    if status == 401:
        raise GatekeeperError("Session expired — run `auth login` again.", 401, data)
    if status >= 400 or not isinstance(data, list):
        raise GatekeeperError(f"Could not read reports: {_sb_error(data, status)}", status, data)
    return data
