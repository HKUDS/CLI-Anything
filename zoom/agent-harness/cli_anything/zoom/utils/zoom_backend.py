"""Zoom API backend — wraps Zoom REST API v2 via OAuth2.

This module handles all HTTP communication with the Zoom API.
It is the only module that makes network requests.
"""

import json
import os
import platform
import subprocess
import time
import requests
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


# Zoom API base URL
API_BASE = "https://api.zoom.us/v2"

# OAuth endpoints
OAUTH_AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
OAUTH_TOKEN_URL = "https://zoom.us/oauth/token"

# Default config directory
CONFIG_DIR = Path.home() / ".cli-anything-zoom"
TOKEN_FILE = CONFIG_DIR / "tokens.json"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _restrict_path(path: Path, mode: int):
    """Set file/directory permissions, with icacls enforcement on Windows.

    On Unix, uses os.chmod directly.
    On Windows, os.chmod only controls the read-only flag, so we also
    run icacls to grant access exclusively to the current user.
    """
    try:
        path.chmod(mode)
    except OSError:
        pass

    if platform.system() == "Windows":
        try:
            username = os.environ.get("USERNAME", "")
            if username:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r",
                     "/grant:r", f"{username}:(F)"],
                    capture_output=True, timeout=10,
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # icacls not available or timed out — best effort


def get_config_dir() -> Path:
    """Get or create config directory with owner-only permissions (0o700)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _restrict_path(CONFIG_DIR, 0o700)
    return CONFIG_DIR


def load_config() -> dict:
    """Load OAuth app config (client_id, client_secret, redirect_uri)."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config: dict):
    """Save OAuth app config with owner-only permissions (0o600)."""
    get_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    _restrict_path(CONFIG_FILE, 0o600)


def load_tokens() -> dict:
    """Load saved OAuth tokens from disk."""
    if not TOKEN_FILE.exists():
        return {}
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def save_tokens(tokens: dict):
    """Save OAuth tokens to disk with owner-only permissions (0o600)."""
    get_config_dir()
    tokens["saved_at"] = time.time()
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    _restrict_path(TOKEN_FILE, 0o600)


def get_authorize_url(client_id: str, redirect_uri: str) -> str:
    """Build the OAuth2 authorization URL for browser login."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }
    return f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(client_id: str, client_secret: str,
                  code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    resp = requests.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(client_id: str, client_secret: str,
                         refresh_token: str) -> dict:
    """Refresh an expired access token."""
    resp = requests.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(client_id, client_secret),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _get_valid_token() -> str:
    """Get a valid access token, refreshing if necessary."""
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError(
            "Not authenticated. Run 'auth login' first."
        )

    access_token = tokens.get("access_token")
    saved_at = tokens.get("saved_at", 0)
    expires_in = tokens.get("expires_in", 3600)

    # Refresh if token is about to expire (within 5 minutes)
    if time.time() - saved_at > (expires_in - 300):
        config = load_config()
        if not config.get("client_id") or not config.get("client_secret"):
            raise RuntimeError(
                "OAuth config missing. Run 'auth setup' first."
            )
        new_tokens = refresh_access_token(
            config["client_id"],
            config["client_secret"],
            tokens["refresh_token"],
        )
        new_tokens["refresh_token"] = new_tokens.get(
            "refresh_token", tokens["refresh_token"]
        )
        save_tokens(new_tokens)
        access_token = new_tokens["access_token"]

    return access_token


def api_request(method: str, endpoint: str,
                params: dict | None = None,
                json_data: dict | None = None,
                stream: bool = False) -> Any:
    """Make an authenticated request to the Zoom API.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE).
        endpoint: API endpoint path (e.g., '/users/me/meetings').
        params: Query parameters.
        json_data: JSON request body.
        stream: Whether to stream the response (for downloads).

    Returns:
        Parsed JSON response, or raw Response if streaming.
    """
    token = _get_valid_token()
    url = f"{API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_data,
        stream=stream,
        timeout=60,
    )

    if stream and resp.status_code == 200:
        return resp

    resp.raise_for_status()

    if resp.status_code == 204:
        return {"status": "success"}

    return resp.json()


def api_get(endpoint: str, params: dict | None = None) -> Any:
    """Shorthand for GET request."""
    return api_request("GET", endpoint, params=params)


def api_post(endpoint: str, data: dict | None = None) -> Any:
    """Shorthand for POST request."""
    return api_request("POST", endpoint, json_data=data)


def api_patch(endpoint: str, data: dict | None = None) -> Any:
    """Shorthand for PATCH request."""
    return api_request("PATCH", endpoint, json_data=data)


def api_delete(endpoint: str) -> Any:
    """Shorthand for DELETE request."""
    return api_request("DELETE", endpoint)


def get_current_user() -> dict:
    """Get the authenticated user's profile."""
    return api_get("/users/me")
