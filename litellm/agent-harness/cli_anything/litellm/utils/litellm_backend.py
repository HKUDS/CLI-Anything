"""LiteLLM proxy client and config helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

DEFAULT_HOST = "https://litellm.nuriy.com/v1"
DEFAULT_TIMEOUT = 60
DEFAULT_MODEL = "gpt-5.4"
ENV_HOST = "LITELLM_BASE_URL"
ENV_API_KEY = "LITELLM_API_KEY"
ENV_MODEL = "LITELLM_MODEL"
CONFIG_DIR = Path.home() / ".cli-anything-litellm"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict[str, Any]) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
    return CONFIG_FILE


def workspace_config_file(workspace: str | Path) -> Path:
    return Path(workspace).resolve() / ".litellm" / "config.json"


def load_workspace_config(workspace: str | Path) -> dict[str, Any]:
    path = workspace_config_file(workspace)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_workspace_config(workspace: str | Path, cfg: dict[str, Any]) -> Path:
    path = workspace_config_file(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
    return path


def bootstrap_workspace(workspace: str | Path, *, host: str, model: str) -> dict[str, str]:
    root = Path(workspace).resolve()
    litellm_dir = root / ".litellm"
    tasks_dir = litellm_dir / "tasks"
    litellm_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    save_workspace_config(root, {"host": host, "model": model})
    ignore_file = litellm_dir / ".gitignore"
    if not ignore_file.exists():
        ignore_file.write_text("local.env\nsession.json\n", encoding="utf-8")
    env_example = litellm_dir / "local.env.example"
    if not env_example.exists():
        env_example.write_text(
            f"{ENV_API_KEY}=replace-me\n{ENV_HOST}={host}\n{ENV_MODEL}={model}\n",
            encoding="utf-8",
        )
    return {
        "config": str(workspace_config_file(root)),
        "ignore": str(ignore_file),
        "env_example": str(env_example),
        "tasks_dir": str(tasks_dir),
    }


def resolve_host(host: str | None, workspace: str | Path | None = None) -> str:
    cfg = load_config()
    workspace_cfg = load_workspace_config(workspace) if workspace else {}
    return (host or os.environ.get(ENV_HOST) or workspace_cfg.get("host") or cfg.get("host") or DEFAULT_HOST).rstrip("/")


def resolve_api_key(api_key: str | None, workspace: str | Path | None = None) -> str | None:
    cfg = load_config()
    workspace_cfg = load_workspace_config(workspace) if workspace else {}
    return api_key or os.environ.get(ENV_API_KEY) or workspace_cfg.get("api_key") or cfg.get("api_key")


def resolve_model(model: str | None, workspace: str | Path | None = None) -> str | None:
    cfg = load_config()
    workspace_cfg = load_workspace_config(workspace) if workspace else {}
    return model or os.environ.get(ENV_MODEL) or workspace_cfg.get("model") or cfg.get("model") or DEFAULT_MODEL


def _headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key.removeprefix('Bearer ').strip()}"
    return headers


def _raise_response_error(prefix: str, response: requests.Response) -> None:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    raise RuntimeError(f"{prefix}: HTTP {response.status_code}: {payload}")


def api_get(host: str, path: str, *, api_key: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{host.rstrip('/')}{path}",
            headers=_headers(api_key),
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"LiteLLM request timed out after {timeout}s") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Cannot connect to LiteLLM at {host}") from exc
    if response.status_code >= 400:
        _raise_response_error("LiteLLM GET failed", response)
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("LiteLLM returned non-JSON response") from exc


def api_post(
    host: str,
    path: str,
    body: dict[str, Any],
    *,
    api_key: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{host.rstrip('/')}{path}",
            headers=_headers(api_key),
            json=body,
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"LiteLLM request timed out after {timeout}s") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Cannot connect to LiteLLM at {host}") from exc
    if response.status_code >= 400:
        _raise_response_error("LiteLLM POST failed", response)
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("LiteLLM returned non-JSON response") from exc


def health(host: str, *, api_key: str | None = None) -> dict[str, Any]:
    try:
        result = api_get(_api_root(host), "/health", api_key=api_key, timeout=10)
    except RuntimeError:
        result = api_get(_v1_host(host), "/models", api_key=api_key, timeout=10)
        return {"status": "ok", "fallback": "v1/models", "model_count": len(result.get("data", []))}
    if isinstance(result, dict):
        result.setdefault("status", "ok")
    return result


def list_models(host: str, *, api_key: str | None = None) -> dict[str, Any]:
    result = api_get(_v1_host(host), "/models", api_key=api_key)
    result.setdefault("data", [])
    return result


def chat_completion(
    host: str,
    *,
    api_key: str | None,
    model: str,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if response_format is not None:
        body["response_format"] = response_format
    return api_post(_v1_host(host), "/chat/completions", body, api_key=api_key)


def _api_root(host: str) -> str:
    trimmed = host.rstrip("/")
    return trimmed[:-3] if trimmed.endswith("/v1") else trimmed


def _v1_host(host: str) -> str:
    trimmed = host.rstrip("/")
    return trimmed if trimmed.endswith("/v1") else f"{trimmed}/v1"
