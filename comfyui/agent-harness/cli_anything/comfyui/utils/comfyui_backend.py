"""ComfyUI API backend — wraps ComfyUI REST API HTTP calls.

This module handles all HTTP communication with the ComfyUI server.
It is the only module that makes network requests.

ComfyUI runs a local HTTP server (default: http://localhost:8188).
No authentication is required by default.
"""

import requests
from typing import Any

# Default ComfyUI server URL
DEFAULT_BASE_URL = "http://localhost:8188"


def api_get(base_url: str, endpoint: str, params: dict | None = None) -> Any:
    """Perform a GET request against the ComfyUI API.

    Args:
        base_url: ComfyUI server base URL (e.g., 'http://localhost:8188').
        endpoint: API endpoint path (e.g., '/queue').
        params: Optional query parameters.

    Returns:
        Parsed JSON response as a dict or list.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to ComfyUI at {base_url}. "
            "Is ComfyUI running? Start it with: python main.py"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"ComfyUI API error {resp.status_code} on GET {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to ComfyUI timed out: GET {endpoint}"
        ) from e


def api_post(base_url: str, endpoint: str, data: dict | None = None) -> Any:
    """Perform a POST request against the ComfyUI API.

    Args:
        base_url: ComfyUI server base URL.
        endpoint: API endpoint path.
        data: JSON request body.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.post(url, json=data, timeout=30)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to ComfyUI at {base_url}. "
            "Is ComfyUI running? Start it with: python main.py"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"ComfyUI API error {resp.status_code} on POST {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to ComfyUI timed out: POST {endpoint}"
        ) from e


def api_delete(base_url: str, endpoint: str, data: dict | None = None) -> Any:
    """Perform a DELETE request against the ComfyUI API.

    Args:
        base_url: ComfyUI server base URL.
        endpoint: API endpoint path.
        data: Optional JSON request body.

    Returns:
        Parsed JSON response or status dict.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.delete(url, json=data, timeout=30)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to ComfyUI at {base_url}. "
            "Is ComfyUI running? Start it with: python main.py"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"ComfyUI API error {resp.status_code} on DELETE {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to ComfyUI timed out: DELETE {endpoint}"
        ) from e


def api_get_raw(base_url: str, endpoint: str, params: dict | None = None) -> bytes:
    """Perform a GET request and return raw bytes (for image downloads).

    Args:
        base_url: ComfyUI server base URL.
        endpoint: API endpoint path.
        params: Optional query parameters.

    Returns:
        Raw response bytes.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        return resp.content
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to ComfyUI at {base_url}. "
            "Is ComfyUI running? Start it with: python main.py"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"ComfyUI API error {resp.status_code} on GET {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to ComfyUI timed out: GET {endpoint}"
        ) from e
