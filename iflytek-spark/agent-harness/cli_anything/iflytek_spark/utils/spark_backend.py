"""Spark-X2.5 backend — talks to any OpenAI-compatible server hosting the model.

Spark-X2.5 (https://github.com/XHToken/Spark-X2.5) is usually served one of
these ways, all of which expose ``/v1/chat/completions`` and ``/v1/models``:

* SGLang   (``--served-model-name spark2.5``, port 30000)
* vLLM     (``--served-model-name spark25``, port 30000)
* Ollama   (``ollama run SparkLLM/Spark-X2.5-1.7B``, port 11434)
* llama.cpp ``llama-server`` with the official GGUF files (port 8080)
* iFlytek Astron MaaS (hosted, Bearer API key, model id from the model card)

Spark-X2.5 is a thinking model. Its chat template pre-fills ``<think>`` into
the generation prompt, so a server started without a reasoning parser returns
``reasoning...</think>answer`` in ``content``. Servers with a parser return the
reasoning in a separate ``reasoning_content`` (or ``reasoning``) field. This
module normalises both shapes into ``(reasoning, content)``.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable, Optional

try:
    import requests
except ImportError:
    print("requests library not found. Install with: pip3 install requests", file=sys.stderr)
    sys.exit(1)

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"

BACKENDS = {
    "sglang": {
        "base_url": "http://localhost:30000/v1",
        "model": "spark2.5",
        "description": "Self-hosted SGLang server (official Spark-X2.5 launch command)",
    },
    "vllm": {
        "base_url": "http://localhost:30000/v1",
        "model": "spark25",
        "description": "Self-hosted vLLM server (official Spark-X2.5 launch command)",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "SparkLLM/Spark-X2.5-1.7B",
        "description": "Local Ollama (v0.34.1+), OpenAI-compatible endpoint",
    },
    "llamacpp": {
        "base_url": "http://localhost:8080/v1",
        "model": None,
        "description": "llama.cpp llama-server with the official Spark-X2.5 GGUF",
    },
    "maas": {
        "base_url": "https://maas-api.cn-huabei-1.xf-yun.com/v2",
        "model": None,
        "description": "iFlytek Astron MaaS (hosted, needs API key and model id)",
    },
}
DEFAULT_BACKEND = "sglang"

ENV_BACKEND = "IFLYTEK_SPARK_BACKEND"
ENV_BASE_URL = "IFLYTEK_SPARK_BASE_URL"
ENV_API_KEY = "IFLYTEK_SPARK_API_KEY"
ENV_MODEL = "IFLYTEK_SPARK_MODEL"
ENV_HOME = "IFLYTEK_SPARK_HOME"

CONFIG_KEYS = ("backend", "base_url", "api_key", "default_model")


def get_home_dir() -> Path:
    """Directory holding config.json and session.json."""
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cli-anything-iflytek-spark"


def get_config_file() -> Path:
    return get_home_dir() / "config.json"


def load_config() -> dict:
    config_file = get_config_file()
    if not config_file.exists():
        return {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_config(config: dict) -> None:
    config_file = get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    try:
        config_file.chmod(0o600)
    except OSError:
        pass


def mask_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    return value[:6] + "..." if len(value) > 10 else "***"


def resolve_settings(
    backend: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Resolve connection settings.

    Precedence for each field: explicit argument > environment variable >
    config file > backend preset.
    """
    cfg = load_config()
    backend = backend or os.environ.get(ENV_BACKEND) or cfg.get("backend") or DEFAULT_BACKEND
    if backend not in BACKENDS:
        raise ValueError(
            f"Unknown backend '{backend}'. Choose one of: {', '.join(BACKENDS)}"
        )
    preset = BACKENDS[backend]
    base_url = base_url or os.environ.get(ENV_BASE_URL) or cfg.get("base_url") or preset["base_url"]
    api_key = api_key or os.environ.get(ENV_API_KEY) or cfg.get("api_key")
    model = model or os.environ.get(ENV_MODEL) or cfg.get("default_model") or preset["model"]
    return {
        "backend": backend,
        "base_url": base_url.rstrip("/"),
        "api_key": api_key,
        "model": model,
    }


def _headers(api_key: Optional[str]) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _connection_error(base_url: str, exc: Exception) -> RuntimeError:
    return RuntimeError(
        f"Cannot reach Spark-X2.5 server at {base_url}: {exc}\n"
        "Start a server first (see https://github.com/XHToken/Spark-X2.5#quickstart),\n"
        "or point the CLI at one with --backend / --base-url."
    )


def _http_error(resp, exc: Exception) -> RuntimeError:
    detail = ""
    if resp is not None:
        detail = resp.text[:500]
    return RuntimeError(f"Spark API error: {exc} {detail}".strip())


def is_available(base_url: str, api_key: Optional[str] = None, timeout: float = 3) -> bool:
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/models", headers=_headers(api_key), timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def list_models(base_url: str, api_key: Optional[str] = None) -> list:
    resp = None
    try:
        resp = requests.get(f"{base_url}/models", headers=_headers(api_key), timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except requests.ConnectionError as e:
        raise _connection_error(base_url, e)
    except requests.RequestException as e:
        raise _http_error(resp, e)


def resolve_model(settings: dict) -> str:
    """Return the configured model, or the first model the server serves."""
    if settings.get("model"):
        return settings["model"]
    models = list_models(settings["base_url"], settings.get("api_key"))
    if not models:
        raise RuntimeError(
            f"No model configured and {settings['base_url']}/models returned none.\n"
            "Pass --model, or run: cli-anything-iflytek-spark config set default_model <id>"
        )
    return models[0].get("id", "")


def split_reasoning(message: dict) -> tuple[str, str]:
    """Split an assistant message into ``(reasoning, content)``."""
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    if reasoning:
        return reasoning.strip(), content.strip()
    idx = content.find(THINK_CLOSE)
    if idx == -1:
        return "", content.strip()
    head = content[:idx].lstrip()
    if head.startswith(THINK_OPEN):
        head = head[len(THINK_OPEN):]
    return head.strip(), content[idx + len(THINK_CLOSE):].strip()


class ThinkStreamSplitter:
    """Incrementally route streamed text into reasoning and content.

    With a pre-filled ``<think>`` the stream carries reasoning until the first
    ``</think>``, so content is buffered until that marker shows up. If the
    stream ends without one, the buffer is emitted as content.
    """

    def __init__(self, passthrough: bool = False):
        self.passthrough = passthrough
        self._buffer = ""
        self._strip_leading = False

    def feed(self, text: str) -> list[tuple[str, str]]:
        if self.passthrough:
            return self._content(text)
        self._buffer += text
        idx = self._buffer.find(THINK_CLOSE)
        if idx == -1:
            return []
        head = self._buffer[:idx].lstrip()
        if head.startswith(THINK_OPEN):
            head = head[len(THINK_OPEN):]
        tail = self._buffer[idx + len(THINK_CLOSE):]
        self._buffer = ""
        self.passthrough = True
        self._strip_leading = True
        events = []
        if head.strip():
            events.append(("reasoning", head.strip()))
        events.extend(self._content(tail))
        return events

    def reasoning_seen(self) -> list[tuple[str, str]]:
        """The server split reasoning itself; stop scanning content."""
        if self.passthrough:
            return []
        self.passthrough = True
        self._strip_leading = True
        pending, self._buffer = self._buffer, ""
        return self._content(pending)

    def flush(self) -> list[tuple[str, str]]:
        if self.passthrough:
            return []
        pending, self._buffer = self._buffer, ""
        self.passthrough = True
        return self._content(pending)

    def _content(self, text: str) -> list[tuple[str, str]]:
        if self._strip_leading:
            text = text.lstrip()
            if not text:
                return []
            self._strip_leading = False
        return [("content", text)] if text else []


def build_request(
    model: str,
    messages: list,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    thinking: bool = True,
    stream: bool = False,
) -> dict:
    body = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if top_p is not None:
        body["top_p"] = top_p
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if not thinking:
        # Honoured by SGLang/vLLM/llama.cpp through the chat template.
        body["chat_template_kwargs"] = {"enable_thinking": False}
    if stream:
        body["stream"] = True
    return body


def chat_completion(
    settings: dict,
    messages: list,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    thinking: bool = True,
    timeout: float = 600,
) -> dict:
    """Non-streaming chat. Returns model, reasoning, content and usage."""
    model = resolve_model(settings)
    body = build_request(model, messages, temperature, top_p, max_tokens, thinking)
    resp = None
    try:
        resp = requests.post(
            f"{settings['base_url']}/chat/completions",
            json=body,
            headers=_headers(settings.get("api_key")),
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.ConnectionError as e:
        raise _connection_error(settings["base_url"], e)
    except requests.RequestException as e:
        raise _http_error(resp, e)

    choices = data.get("choices") or [{}]
    reasoning, content = split_reasoning(choices[0].get("message", {}))
    return {
        "model": data.get("model", model),
        "reasoning": reasoning,
        "content": content,
        "finish_reason": choices[0].get("finish_reason"),
        "usage": data.get("usage", {}),
    }


def chat_completion_stream(
    settings: dict,
    messages: list,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    thinking: bool = True,
    on_content: Optional[Callable[[str], None]] = None,
    on_reasoning: Optional[Callable[[str], None]] = None,
    timeout: float = 600,
) -> dict:
    """Streaming chat. Calls the callbacks as text arrives."""
    model = resolve_model(settings)
    body = build_request(model, messages, temperature, top_p, max_tokens, thinking, stream=True)
    splitter = ThinkStreamSplitter(passthrough=not thinking)
    reasoning_parts: list[str] = []
    content_parts: list[str] = []

    def dispatch(events):
        for kind, text in events:
            if kind == "reasoning":
                reasoning_parts.append(text)
                if on_reasoning:
                    on_reasoning(text)
            else:
                content_parts.append(text)
                if on_content:
                    on_content(text)

    resp = None
    try:
        resp = requests.post(
            f"{settings['base_url']}/chat/completions",
            json=body,
            headers=_headers(settings.get("api_key")),
            timeout=timeout,
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or [{}]
            delta = choices[0].get("delta", {})
            think = delta.get("reasoning_content") or delta.get("reasoning")
            if think:
                dispatch(splitter.reasoning_seen())
                dispatch([("reasoning", think)])
            if delta.get("content"):
                dispatch(splitter.feed(delta["content"]))
        dispatch(splitter.flush())
    except requests.ConnectionError as e:
        raise _connection_error(settings["base_url"], e)
    except requests.RequestException as e:
        raise _http_error(resp, e)

    return {
        "model": model,
        "reasoning": "".join(reasoning_parts).strip(),
        "content": "".join(content_parts).strip(),
    }
