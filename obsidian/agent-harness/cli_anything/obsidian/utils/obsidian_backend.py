"""Obsidian Local REST API wrapper — the single module that makes network requests.

Obsidian Local REST API plugin runs an HTTPS server (default: https://localhost:27124).
Authentication is via Bearer token configured in the plugin settings.
Uses self-signed certificate by default (verify=False).
"""

import requests
import urllib3
from typing import Any

# Suppress InsecureRequestWarning for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default Obsidian Local REST API URL
DEFAULT_BASE_URL = "https://localhost:27124"


def _headers(api_key: str, accept: str = "application/json",
             content_type: str | None = None) -> dict:
    """Build request headers with Bearer auth."""
    h = {"Authorization": f"Bearer {api_key}", "Accept": accept}
    if content_type:
        h["Content-Type"] = content_type
    return h


def api_get(base_url: str, endpoint: str, api_key: str,
            params: dict | None = None, timeout: int = 30) -> Any:
    """Perform a GET request against the Obsidian REST API."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.get(url, headers=_headers(api_key),
                           params=params, timeout=timeout, verify=False)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return {"content": resp.text}
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Obsidian REST API at {base_url}. "
            "Is Obsidian running with the Local REST API plugin enabled?"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Obsidian API error {resp.status_code} on GET {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Obsidian timed out: GET {endpoint}"
        ) from e


def api_post(base_url: str, endpoint: str, api_key: str,
             data: dict | None = None, params: dict | None = None,
             timeout: int = 30) -> Any:
    """Perform a POST request against the Obsidian REST API."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.post(url, headers=_headers(api_key),
                            json=data, params=params,
                            timeout=timeout, verify=False)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return {"content": resp.text}
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Obsidian REST API at {base_url}. "
            "Is Obsidian running with the Local REST API plugin enabled?"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Obsidian API error {resp.status_code} on POST {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Obsidian timed out: POST {endpoint}"
        ) from e


def api_post_raw(base_url: str, endpoint: str, api_key: str,
                 body: str, content_type: str,
                 params: dict | None = None, timeout: int = 30) -> Any:
    """POST a raw body with a caller-provided Content-Type.

    Used for Obsidian endpoints that require vendor-specific media types
    (e.g. ``application/vnd.olrapi.dataview.dql+txt`` for the search endpoint),
    where the standard ``api_post`` JSON path would be rejected with
    ``40012 Unknown or invalid Content-Type``.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        headers = _headers(api_key, content_type=content_type)
        resp = requests.post(url, headers=headers,
                             data=body.encode("utf-8"), params=params,
                             timeout=timeout, verify=False)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        resp_ct = resp.headers.get("content-type", "")
        if "application/json" in resp_ct:
            return resp.json()
        return {"content": resp.text}
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Obsidian REST API at {base_url}. "
            "Is Obsidian running with the Local REST API plugin enabled?"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Obsidian API error {resp.status_code} on POST {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Obsidian timed out: POST {endpoint}"
        ) from e


def api_put(base_url: str, endpoint: str, api_key: str,
            content: str = "", content_type: str = "text/markdown",
            timeout: int = 30) -> Any:
    """Perform a PUT request (sends raw text, not JSON)."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        headers = _headers(api_key, content_type=content_type)
        resp = requests.put(url, headers=headers, data=content.encode("utf-8"),
                           timeout=timeout, verify=False)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            return resp.json()
        return {"status": "ok"}
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Obsidian REST API at {base_url}. "
            "Is Obsidian running with the Local REST API plugin enabled?"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Obsidian API error {resp.status_code} on PUT {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Obsidian timed out: PUT {endpoint}"
        ) from e


def api_delete(base_url: str, endpoint: str, api_key: str,
               timeout: int = 30) -> Any:
    """Perform a DELETE request."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.delete(url, headers=_headers(api_key),
                              timeout=timeout, verify=False)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            return resp.json()
        return {"status": "ok"}
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Obsidian REST API at {base_url}. "
            "Is Obsidian running with the Local REST API plugin enabled?"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Obsidian API error {resp.status_code} on DELETE {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Obsidian timed out: DELETE {endpoint}"
        ) from e


def is_available(api_key: str, base_url: str = DEFAULT_BASE_URL) -> bool:
    """Check if Obsidian REST API is reachable."""
    try:
        resp = requests.get(
            f"{base_url.rstrip('/')}/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
            verify=False,
        )
        return resp.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False
