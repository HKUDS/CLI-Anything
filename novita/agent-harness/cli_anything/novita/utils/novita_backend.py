"""Novita API backend — wraps the Novita OpenAI-compatible REST API."""
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

API_BASE = os.environ.get("NOVITA_API_BASE", "https://api.novita.ai/openai").rstrip("/")
CONFIG_DIR = Path.home() / ".config" / "cli-anything-novita"
CONFIG_FILE = CONFIG_DIR / "config.json"
ENV_API_KEY = "NOVITA_API_KEY"


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


def get_api_key(cli_key: Optional[str] = None) -> Optional[str]:
    if cli_key:
        return cli_key
    env_key = os.environ.get(ENV_API_KEY)
    if env_key:
        return env_key
    return load_config().get("api_key")


def _require_api_key(api_key: Optional[str]) -> str:
    if not api_key:
        raise RuntimeError(
            "Novita API key not found. Provide one via:\n"
            "  1. --api-key sk-xxx\n"
            f"  2. export {ENV_API_KEY}=sk-xxx\n"
            "  3. cli-anything-novita config set api_key sk-xxx\n"
            "Get a key at https://novita.ai/settings/api-keys"
        )
    return api_key


def _make_auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


def list_models(api_key: Optional[str] = None) -> list:
    api_key = _require_api_key(api_key)
    headers = _make_auth_headers(api_key)
    try:
        resp = requests.get(f"{API_BASE}/models", headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to list models: {e}")


def chat_completion(
    api_key: Optional[str] = None,
    model: str = "deepseek/deepseek-v3.2",
    messages: Optional[list] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = False,
    extra_headers: Optional[dict] = None,
) -> dict:
    api_key = _require_api_key(api_key)
    if messages is None:
        messages = []
    body = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if stream:
        body["stream"] = True
    headers = _make_auth_headers(api_key)
    if extra_headers:
        headers.update(extra_headers)
    resp = None
    try:
        resp = requests.post(
            f"{API_BASE}/chat/completions",
            json=body,
            headers=headers,
            timeout=60 if not stream else None,
            stream=stream,
        )
        resp.raise_for_status()
        if stream:
            return {"stream_response": resp}
        data = resp.json()
        return data
    except requests.RequestException:
        detail = ""
        if resp is not None:
            detail = resp.text[:500]
        raise RuntimeError(f"Novita API error: {detail}")


def chat_completion_stream(
    api_key: Optional[str] = None,
    model: str = "deepseek/deepseek-v3.2",
    messages: Optional[list] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    on_chunk=None,
) -> str:
    api_key = _require_api_key(api_key)
    if messages is None:
        messages = []
    body = {"model": model, "messages": messages, "stream": True}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    headers = _make_auth_headers(api_key)
    full_response = ""
    try:
        resp = requests.post(
            f"{API_BASE}/chat/completions",
            json=body,
            headers=headers,
            timeout=60,
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        full_response += content
                        if on_chunk:
                            on_chunk(content)
                except json.JSONDecodeError:
                    continue
        return full_response
    except requests.RequestException as e:
        raise RuntimeError(f"Streaming Novita API error: {e}")


def count_tokens(api_key: Optional[str] = None, model: str = "deepseek/deepseek-v3.2", text: str = "") -> int:
    api_key = _require_api_key(api_key)
    return len(text) // 4 + (1 if len(text) % 4 else 0)


def format_message(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def run_full_workflow(
    api_key: Optional[str] = None,
    model: str = "deepseek/deepseek-v3.2",
    prompt: str = "",
    system_message: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    on_chunk=None,
) -> dict:
    messages = []
    if system_message:
        messages.append(format_message("system", system_message))
    messages.append(format_message("user", prompt))
    if on_chunk:
        response = chat_completion_stream(
            api_key=api_key, model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, on_chunk=on_chunk
        )
        return {"content": response}
    else:
        result = chat_completion(api_key=api_key, model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        choices = result.get("choices", [])
        if choices:
            return {
                "content": choices[0].get("message", {}).get("content", ""),
                "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": result.get("usage", {}).get("total_tokens", 0),
            }
        return {"content": ""}
