"""HTTP/GraphQL transport for the OpenCTI CLI harness.

All functions accept explicit ``base_url`` / ``api_key`` overrides and fall
back to environment variables:

- ``OPENCTI_BASE_URL`` or ``OPENCTI_URL``  e.g. ``https://opencti.example.com``
- ``OPENCTI_API_KEY``  or ``OPENCTI_TOKEN``  bearer token
- ``OPENCTI_TIMEOUT``  request timeout in seconds (default 30)

OpenCTI exposes a single GraphQL endpoint at ``{base}/graphql``. Every call is
a POST; auth uses ``Authorization: Bearer <token>``.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

GRAPHQL_PATH = "/graphql"
DEFAULT_TIMEOUT = 30
MAX_ATTEMPTS = 4
RETRY_STATUSES = {429, 500, 502, 503, 504}
CONFIG_DIR = Path.home() / ".cli-anything" / "opencti"
CONFIG_FILE = CONFIG_DIR / "config.json"


class OpenCTIError(Exception):
    """Raised for configuration problems before any HTTP traffic."""


def _env(name: str, *aliases: str) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value
    for alias in aliases:
        value = os.environ.get(alias)
        if value:
            return value
    return None


def resolve_connection(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Resolve connection settings: args > env > ~/.cli-anything/opencti/config.json."""
    if not base_url or not api_key:
        file_cfg = _load_config_file()
        base_url = base_url or _env("OPENCTI_BASE_URL", "OPENCTI_URL") or file_cfg.get("base_url")
        api_key = api_key or _env("OPENCTI_API_KEY", "OPENCTI_TOKEN") or file_cfg.get("api_key")
    if not base_url:
        raise OpenCTIError(
            "OpenCTI base URL not configured. Set OPENCTI_BASE_URL, pass --url, "
            f"or create {CONFIG_FILE} with {{\"base_url\": ...}}"
        )
    return {"base_url": base_url.rstrip("/"), "api_key": api_key}


def _load_config_file() -> Dict[str, Any]:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(base_url: str, api_key: Optional[str] = None) -> Path:
    """Persist connection settings for future invocations."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg: Dict[str, Any] = {"base_url": base_url.rstrip("/")}
    if api_key:
        cfg["api_key"] = api_key
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return CONFIG_FILE


def graphql_request(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """POST a GraphQL query and return the ``data`` payload.

    Retries transient failures (429/5xx/connection errors) with exponential
    backoff + jitter. Raises ValueError carrying the server-side message when
    GraphQL returns an ``errors`` array.
    """
    conn = resolve_connection(base_url, api_key)
    url = conn["base_url"] + GRAPHQL_PATH
    timeout = timeout or int(_env("OPENCTI_TIMEOUT") or DEFAULT_TIMEOUT)
    headers = {"Content-Type": "application/json"}
    if conn["api_key"]:
        headers["Authorization"] = f"Bearer {conn['api_key']}"
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                last_error = requests.HTTPError(f"{resp.status_code}", response=resp)
                _sleep_backoff(attempt, resp)
                continue
            if resp.status_code >= 400:
                snippet = resp.text[:300] if resp.text else ""
                raise OpenCTIError(
                    f"OpenCTI API returned HTTP {resp.status_code}: {snippet}"
                )
        except requests.ConnectionError as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                _sleep_backoff(attempt)
                continue
            raise ConnectionError(f"cannot reach OpenCTI at {url}: {exc}") from exc
        except requests.Timeout as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                _sleep_backoff(attempt)
                continue
            raise TimeoutError(f"OpenCTI request timed out after {timeout}s: {url}") from exc

        body = resp.json() if resp.content else {}
        errors = body.get("errors")
        if errors:
            messages = []
            for err in errors[:5]:
                msg = err.get("message", json.dumps(err)[:200])
                messages.append(msg)
            raise ValueError("; ".join(messages))
        data = body.get("data")
        if data is None:
            raise ValueError("GraphQL response contained no data")
        return data

    if isinstance(last_error, requests.HTTPError):
        raise OpenCTIError(
            f"OpenCTI API returned HTTP {last_error.response.status_code} "
            "after retries"
        ) from last_error
    raise ConnectionError("exhausted retries contacting OpenCTI")


def _sleep_backoff(attempt: int, resp: Optional[requests.Response] = None) -> None:
    retry_after = resp.headers.get("Retry-After") if resp is not None else None
    if retry_after:
        try:
            time.sleep(min(float(retry_after), 30.0))
            return
        except ValueError:
            pass
    time.sleep(min(2 ** attempt, 30) * 0.5 * (1 + random.random()))


def health_check(*, base_url: str) -> bool:
    """Unauthenticated liveness probe against ``{base}/health``."""
    try:
        resp = requests.get(base_url.rstrip("/") + "/health", timeout=10,
                            allow_redirects=False)
        # Some deployments answer 200, others 401 once auth is enforced;
        # both prove the platform is up.
        return resp.status_code in (200, 401, 403)
    except (requests.ConnectionError, requests.Timeout):
        return False


def paginated(
    fetch_page,
    *,
    first: int = 25,
    max_pages: int = 100,
    after: Optional[str] = None,
) -> list:
    """Walk Relay-style ``edges`` pages.

    ``fetch_page(after)`` must return a dict with either ``edges`` plus
    ``pageInfo`` or a bare list of nodes. Stops when ``hasNextPage`` is false
    or the cursor repeats.
    """
    items: list = []
    seen_cursors: set = set()
    cursor = after
    pages = 0
    while pages < max_pages:
        if cursor is not None and cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
        page = fetch_page(cursor)
        edges = page.get("edges") if isinstance(page, dict) else None
        if edges is not None:
            items.extend(e["node"] for e in edges)
            info = page.get("pageInfo", {})
            next_cursor = info.get("endCursor")
            has_next = bool(info.get("hasNextPage"))
        else:
            nodes = page if isinstance(page, list) else page.get("nodes", [])
            items.extend(nodes)
            next_cursor, has_next = None, False
        pages += 1
        if not has_next or not next_cursor:
            break
        cursor = next_cursor
    return items
