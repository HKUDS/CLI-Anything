"""MiniMax API backend — wraps the MiniMax OpenAI-compatible REST API and TTS API."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional, Callable

try:
    import requests
except ImportError:
    print("requests library not found. Install with: pip3 install requests", file=sys.stderr)
    sys.exit(1)

CHAT_API_BASE = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1").rstrip("/")
TTS_API_BASE = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io").rstrip("/")
CONFIG_DIR = Path.home() / ".config" / "cli-anything-minimax"
CONFIG_FILE = CONFIG_DIR / "config.json"
ENV_API_KEY = "MINIMAX_API_KEY"

CHAT_MODELS = [
    {"id": "MiniMax-M2.7", "description": "Peak Performance. Ultimate Value. Master the Complex"},
    {"id": "MiniMax-M2.7-highspeed", "description": "Same performance, faster and more agile"},
]

TTS_MODELS = [
    {"id": "speech-2.8-hd", "description": "High-definition TTS (recommended default)"},
    {"id": "speech-2.8-turbo", "description": "Fast TTS"},
]

TTS_VOICES = [
    "English_Graceful_Lady",
    "English_Insightful_Speaker",
    "English_radiant_girl",
    "English_Persuasive_Man",
    "English_Lucky_Robot",
    "English_expressive_narrator",
]


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
            "MiniMax API key not found. Provide one via:\n"
            "  1. --api-key sk-xxx\n"
            f"  2. export {ENV_API_KEY}=sk-xxx\n"
            "  3. cli-anything-minimax config set api_key sk-xxx\n"
            "Get a key at https://platform.minimax.io"
        )
    return api_key


def _make_auth_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def chat_completion(
    api_key: Optional[str] = None,
    model: str = "MiniMax-M2.7",
    messages: Optional[list] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict:
    api_key = _require_api_key(api_key)
    if messages is None:
        messages = []
    body: dict = {"model": model, "messages": messages}
    # MiniMax temperature range is (0.0, 1.0], default 1.0
    body["temperature"] = temperature if temperature is not None else 1.0
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    headers = _make_auth_headers(api_key)
    resp = None
    try:
        resp = requests.post(
            f"{CHAT_API_BASE}/chat/completions",
            json=body,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        detail = ""
        if resp is not None:
            detail = resp.text[:500]
        raise RuntimeError(f"MiniMax API error: {detail}")


def chat_completion_stream(
    api_key: Optional[str] = None,
    model: str = "MiniMax-M2.7",
    messages: Optional[list] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> str:
    api_key = _require_api_key(api_key)
    if messages is None:
        messages = []
    body: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": temperature if temperature is not None else 1.0,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    headers = _make_auth_headers(api_key)
    full_response = ""
    try:
        resp = requests.post(
            f"{CHAT_API_BASE}/chat/completions",
            json=body,
            headers=headers,
            timeout=120,
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
                    content = (
                        data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    )
                    if content:
                        full_response += content
                        if on_chunk:
                            on_chunk(content)
                except json.JSONDecodeError:
                    continue
        return full_response
    except requests.RequestException as e:
        raise RuntimeError(f"MiniMax streaming error: {e}")


def tts_synthesize(
    api_key: Optional[str] = None,
    text: str = "",
    model: str = "speech-2.8-hd",
    voice: str = "English_Graceful_Lady",
    output_path: Optional[str] = None,
) -> bytes:
    """Synthesize text to speech using MiniMax TTS API (SSE stream, hex-encoded audio)."""
    api_key = _require_api_key(api_key)
    headers = _make_auth_headers(api_key)
    body = {
        "model": model,
        "text": text,
        "stream": True,
        "voice_setting": {
            "voice_id": voice,
            "speed": 1,
            "vol": 1,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }
    try:
        resp = requests.post(
            f"{TTS_API_BASE}/v1/t2a_v2",
            json=body,
            headers=headers,
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"MiniMax TTS error: {e}")

    # Parse SSE stream — collect hex-encoded audio chunks
    audio_chunks: list[bytes] = []
    buffer = ""
    for raw in resp.iter_content(chunk_size=None):
        buffer += raw.decode("utf-8", errors="replace")
        lines = buffer.split("\n")
        buffer = lines.pop()
        for line in lines:
            if not line.startswith("data:"):
                continue
            json_str = line[5:].strip()
            if not json_str or json_str == "[DONE]":
                continue
            try:
                event = json.loads(json_str)
                # Check API-level errors
                base_resp = event.get("base_resp", {})
                if base_resp.get("status_code", 0) != 0:
                    raise RuntimeError(
                        f"MiniMax TTS API error: {base_resp.get('status_msg', 'unknown')}"
                    )
                audio_hex = event.get("data", {}).get("audio", "")
                if audio_hex:
                    audio_chunks.append(bytes.fromhex(audio_hex))
            except (json.JSONDecodeError, ValueError):
                continue

    audio_data = b"".join(audio_chunks)
    if output_path:
        with open(output_path, "wb") as f:
            f.write(audio_data)
    return audio_data


def run_full_workflow(
    api_key: Optional[str] = None,
    model: str = "MiniMax-M2.7",
    prompt: str = "",
    system_message: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> dict:
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    if on_chunk:
        response = chat_completion_stream(
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            on_chunk=on_chunk,
        )
        return {"content": response}
    else:
        result = chat_completion(
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choices = result.get("choices", [])
        if choices:
            return {
                "content": choices[0].get("message", {}).get("content", ""),
                "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": result.get("usage", {}).get("total_tokens", 0),
            }
        return {"content": ""}
