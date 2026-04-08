"""RMS API backend — wraps the Teltonika RMS REST API."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("requests library not found. Install with: pip3 install requests", file=sys.stderr)
    sys.exit(1)

API_BASE = os.environ.get("RMS_API_BASE", "https://api.rms.teltonika-networks.com").rstrip("/")
ENV_API_TOKEN = "RMS_API_TOKEN"
CONFIG_DIR = Path.home() / ".config" / "cli-anything-rms"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_config(config: dict) -> None:
    get_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    CONFIG_FILE.chmod(0o600)


def get_api_token(cli_token: Optional[str] = None) -> Optional[str]:
    if cli_token:
        return cli_token
    env_token = os.environ.get(ENV_API_TOKEN)
    if env_token:
        return env_token
    return load_config().get("api_token")


def _require_api_token(token: Optional[str]) -> str:
    if not token:
        raise RuntimeError(
            "RMS API token not found. Provide one via:\n"
            "  1. --token <token>\n"
            f"  2. export {ENV_API_TOKEN}=<token>\n"
            "  3. cli-anything-rms config set api_token <token>\n"
            "Get a token at https://rms.teltonika-networks.com (Settings > Applications > Personal Access Tokens)\n"
            "Note: 2FA must be enabled on your account."
        )
    return token


def _make_auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _handle_response(resp) -> dict:
    """Handle API response, raising on errors."""
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "unknown")
        raise RuntimeError(
            f"Rate limit exceeded. Retry after {retry_after} seconds. "
            "RMS allows 100,000 requests/month per application."
        )
    try:
        resp.raise_for_status()
    except requests.RequestException:
        detail = ""
        try:
            err_data = resp.json()
            errors = err_data.get("errors", [])
            if errors:
                detail = "; ".join(
                    e.get("message", str(e)) if isinstance(e, dict) else str(e)
                    for e in errors
                )
        except (json.JSONDecodeError, ValueError):
            detail = resp.text[:500] if resp.text else ""
        raise RuntimeError(f"RMS API error ({resp.status_code}): {detail}")
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        return {"success": True, "data": resp.text}


def api_get(path: str, params: Optional[dict] = None, token: Optional[str] = None) -> dict:
    token = _require_api_token(token or get_api_token())
    headers = _make_auth_headers(token)
    resp = requests.get(f"{API_BASE}{path}", params=params, headers=headers, timeout=30)
    return _handle_response(resp)


def api_post(path: str, data: Optional[dict] = None, token: Optional[str] = None) -> dict:
    token = _require_api_token(token or get_api_token())
    headers = _make_auth_headers(token)
    resp = requests.post(f"{API_BASE}{path}", json=data, headers=headers, timeout=30)
    return _handle_response(resp)


def api_put(path: str, data: Optional[dict] = None, token: Optional[str] = None) -> dict:
    token = _require_api_token(token or get_api_token())
    headers = _make_auth_headers(token)
    resp = requests.put(f"{API_BASE}{path}", json=data, headers=headers, timeout=30)
    return _handle_response(resp)


def api_delete(path: str, token: Optional[str] = None) -> dict:
    token = _require_api_token(token or get_api_token())
    headers = _make_auth_headers(token)
    resp = requests.delete(f"{API_BASE}{path}", headers=headers, timeout=30)
    return _handle_response(resp)
