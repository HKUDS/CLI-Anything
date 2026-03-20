"""Ollama REST API wrapper — the single module that makes network requests.

Ollama runs a local HTTP server (default: http://localhost:11434).
No authentication is required by default.
"""

import requests
from typing import Any, Generator

# Default Ollama server URL
DEFAULT_BASE_URL = "http://localhost:11434"


def api_get(base_url: str, endpoint: str, params: dict | None = None,
            timeout: int = 30) -> Any:
    """Perform a GET request against the Ollama API.

    Args:
        base_url: Ollama server base URL (e.g., 'http://localhost:11434').
        endpoint: API endpoint path (e.g., '/api/tags').
        params: Optional query parameters.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response as a dict or list.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        # Some endpoints (like /) return plain text
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return {"status": "ok", "message": resp.text.strip()}
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Ollama at {base_url}. "
            "Is Ollama running? Start it with: ollama serve"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Ollama API error {resp.status_code} on GET {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Ollama timed out: GET {endpoint}"
        ) from e


def api_post(base_url: str, endpoint: str, data: dict | None = None,
             timeout: int = 30) -> Any:
    """Perform a POST request against the Ollama API.

    Args:
        base_url: Ollama server base URL.
        endpoint: API endpoint path.
        data: JSON request body.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.post(url, json=data, timeout=timeout)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Ollama at {base_url}. "
            "Is Ollama running? Start it with: ollama serve"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Ollama API error {resp.status_code} on POST {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Ollama timed out: POST {endpoint}"
        ) from e


def api_delete(base_url: str, endpoint: str, data: dict | None = None,
               timeout: int = 30) -> Any:
    """Perform a DELETE request against the Ollama API.

    Args:
        base_url: Ollama server base URL.
        endpoint: API endpoint path.
        data: Optional JSON request body.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response or status dict.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.delete(url, json=data, timeout=timeout)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {"status": "ok"}
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Ollama at {base_url}. "
            "Is Ollama running? Start it with: ollama serve"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Ollama API error {resp.status_code} on DELETE {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Ollama timed out: DELETE {endpoint}"
        ) from e


def api_post_stream(base_url: str, endpoint: str, data: dict | None = None,
                    timeout: int = 300) -> Generator[dict, None, None]:
    """Perform a POST request with streaming NDJSON response.

    Used for generate, chat, and pull endpoints that stream progress.

    Args:
        base_url: Ollama server base URL.
        endpoint: API endpoint path.
        data: JSON request body.
        timeout: Request timeout in seconds (longer default for generation).

    Yields:
        Parsed JSON objects from the NDJSON stream.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    import json as json_mod

    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        resp = requests.post(url, json=data, stream=True, timeout=timeout)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                yield json_mod.loads(line)
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Ollama at {base_url}. "
            "Is Ollama running? Start it with: ollama serve"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"Ollama API error {resp.status_code} on POST {endpoint}: {resp.text}"
        ) from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"Request to Ollama timed out: POST {endpoint}"
        ) from e


def is_available(base_url: str = DEFAULT_BASE_URL) -> bool:
    """Check if Ollama server is reachable.

    Args:
        base_url: Ollama server base URL.

    Returns:
        True if the server responds, False otherwise.
    """
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/", timeout=5)
        return resp.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False
