"""n8n REST API client — single module that handles all HTTP communication."""

from __future__ import annotations

import json
import os
from typing import Any

import requests


try:
    DEFAULT_TIMEOUT = int(os.environ.get("N8N_TIMEOUT", "30"))
except (TypeError, ValueError):
    DEFAULT_TIMEOUT = 30

# n8n Public API version supported
MIN_N8N_VERSION = "1.0.0"
API_VERSION = "v1"


def _get_base_url() -> str:
    return os.environ.get("N8N_BASE_URL", "").rstrip("/")


def _get_api_key() -> str:
    return os.environ.get("N8N_API_KEY", "")


def _headers(api_key: str | None = None) -> dict[str, str]:
    key = api_key or _get_api_key()
    h: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        h["X-N8N-API-KEY"] = key
    return h


def _url(base_url: str | None, path: str) -> str:
    base = (base_url or _get_base_url()).rstrip("/")
    if not base:
        raise ValueError(
            "n8n base URL not configured. Set N8N_BASE_URL env var or pass --url."
        )
    api_prefix = f"/api/{API_VERSION}"
    if path.startswith("/api/"):
        return f"{base}{path}"
    return f"{base}{api_prefix}{path}"


def _handle_response(resp: requests.Response) -> Any:
    if resp.status_code == 204:
        return {}
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        return {"raw": resp.text}


def api_request(
    method: str,
    endpoint: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    params: dict[str, Any] | None = None,
    json_data: Any | None = None,
    timeout: int | None = None,
) -> Any:
    """Execute an HTTP request against the n8n API."""
    url = _url(base_url, endpoint)
    headers = _headers(api_key)
    resp = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_data,
        timeout=timeout or DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return _handle_response(resp)


def api_get(endpoint: str, *, base_url: str | None = None, api_key: str | None = None, params: dict[str, Any] | None = None) -> Any:
    return api_request("GET", endpoint, base_url=base_url, api_key=api_key, params=params)


def api_post(endpoint: str, data: Any | None = None, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_request("POST", endpoint, base_url=base_url, api_key=api_key, json_data=data)


def api_put(endpoint: str, data: Any | None = None, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_request("PUT", endpoint, base_url=base_url, api_key=api_key, json_data=data)


def api_patch(endpoint: str, data: Any | None = None, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_request("PATCH", endpoint, base_url=base_url, api_key=api_key, json_data=data)


def api_delete(endpoint: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_request("DELETE", endpoint, base_url=base_url, api_key=api_key)
