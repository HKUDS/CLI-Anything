"""A local stand-in for the OrcaRouter service, used by the test suite.

It implements the three surfaces the harness talks to:

* ``/auth`` — the consent screen. A real one needs a human; this one either
  redirects straight back to ``callback_url`` with a code (approve) or with
  ``error=access_denied`` (deny), and it renders the code when the flow is
  out-of-band.
* ``/api/v1/auth/keys`` — the PKCE exchange. It verifies the challenge, the
  single-use rule and the 10-minute TTL exactly like the real service.
* ``/v1/models`` and ``/v1/chat/completions`` — the relay.

Only fake credentials are used anywhere in the tests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

FAKE_KEY = "sk-orca-test-0000000000000000000000000000000000000000"
FAKE_ACCOUNT = "12345"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def challenge_for(verifier: str) -> str:
    return b64url(hashlib.sha256(verifier.encode("ascii")).digest())


class FakeOrcaRouter:
    """Runs the fake service on loopback, with separate auth and API origins."""

    def __init__(self, *, scope: str = "api", issue_key: str = FAKE_KEY) -> None:
        self.scope = scope
        self.issue_key = issue_key
        self.pending: dict[str, dict[str, Any]] = {}
        self.issued: list[str] = []
        self.requests: list[tuple[str, str, bytes]] = []
        self.lock = threading.Lock()
        self.auth_server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class("auth"))
        self.api_server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class("api"))
        self._threads = [
            threading.Thread(target=self.auth_server.serve_forever, daemon=True),
            threading.Thread(target=self.api_server.serve_forever, daemon=True),
        ]

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @property
    def auth_base(self) -> str:
        host, port = self.auth_server.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def api_base(self) -> str:
        host, port = self.api_server.server_address[:2]
        return f"http://{host}:{port}/v1"

    def __enter__(self) -> "FakeOrcaRouter":
        for thread in self._threads:
            thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.auth_server.shutdown()
        self.api_server.shutdown()
        self.auth_server.server_close()
        self.api_server.server_close()

    # ── requests seen ─────────────────────────────────────────────────────────

    def paths(self) -> list[str]:
        return [path for _, path, _ in self.requests]

    def requests_for(self, origin: str) -> list[str]:
        return [path for base, path, _ in self.requests if base == origin]

    def body_for(self, path: str) -> Optional[bytes]:
        for _, seen_path, body in self.requests:
            if seen_path == path:
                return body
        return None

    # ── handlers ──────────────────────────────────────────────────────────────

    def _handler_class(self, kind: str) -> type:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass

            def _json(self, payload: dict, status: int = 200) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _html(self, html: str, status: int = 200) -> None:
                body = html.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                if not length:
                    return {}
                raw = self.rfile.read(length)
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return {}
                return parsed if isinstance(parsed, dict) else {}

            def do_GET(self) -> None:  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                outer.requests.append((kind, parsed.path, b""))
                if kind == "api" and parsed.path == "/v1/models":
                    return self._json(outer.models_payload(parsed.query))
                if kind == "api" and parsed.path == "/v1/chat/completions":
                    return self._json({"error": "use POST"}, 405)
                if parsed.path == "/.well-known/openid-configuration":
                    return self._json({"authorization_endpoint": outer.auth_base + "/auth"})
                return self._json({"error": "not found"}, 404)

            def do_POST(self) -> None:  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                body = self._body()
                outer.requests.append((kind, parsed.path, json.dumps(body).encode("utf-8")))
                if kind == "auth" and parsed.path == "/api/v1/auth/keys":
                    return self._exchange(body)
                if kind == "api" and parsed.path == "/v1/chat/completions":
                    return self._chat(body)
                return self._json({"error": "not found"}, 404)

            # -- auth origin -------------------------------------------------

            def _exchange(self, body: dict) -> None:
                code = str(body.get("code") or "")
                verifier = str(body.get("code_verifier") or "")
                method = str(body.get("code_challenge_method") or "")
                with outer.lock:
                    record = outer.pending.get(code)
                if record is None:
                    return self._json(
                        {"error": "invalid_grant", "error_description": "unknown code"}, 403
                    )
                if record["used"]:
                    return self._json(
                        {"error": "invalid_grant", "error_description": "code already used"}, 403
                    )
                if record["expires_at"] < time.time():
                    return self._json(
                        {"error": "invalid_grant", "error_description": "code expired"}, 403
                    )
                if method != record["method"]:
                    return self._json(
                        {"error": "invalid_request", "error_description": "challenge method changed"}, 400
                    )
                if challenge_for(verifier) != record["challenge"]:
                    return self._json(
                        {"error": "invalid_grant", "error_description": "verifier mismatch"}, 403
                    )
                with outer.lock:
                    record["used"] = True
                    outer.issued.append(code)
                return self._json(
                    {"key": outer.issue_key, "user_id": FAKE_ACCOUNT, "scope": outer.scope}
                )

            # -- api origin --------------------------------------------------

            def _chat(self, body: dict) -> None:
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {outer.issue_key}":
                    return self._json({"error": {"message": "invalid key"}}, 401)
                model = str(body.get("model") or "")
                return self._json(
                    {
                        "id": "chatcmpl-fake",
                        "model": model,
                        "choices": [
                            {"index": 0, "message": {"role": "assistant", "content": "ok"}}
                        ],
                        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
                    }
                )

        return Handler

    # ── consent screen ────────────────────────────────────────────────────────

    def consent(self, url: str, *, approve: bool = True, follow: bool = True) -> dict[str, Any]:
        """Simulate the user's browser hitting the consent screen.

        Returns what the browser would end up at: the callback URL with a code,
        or the out-of-band code the screen displayed.
        """
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        callback = (params.get("callback_url") or [""])[0]
        challenge = (params.get("code_challenge") or [""])[0]
        method = (params.get("code_challenge_method") or [""])[0]
        state = (params.get("state") or [""])[0]

        if not approve:
            if callback == "oob":
                return {"error": "access_denied", "state": state}
            target = f"{callback}?error=access_denied&state={urllib.parse.quote(state)}"
            return {"callback_url": target, "state": state} if follow else {"state": state}

        code = f"code-{len(self.pending) + 1}-{b64url(hashlib.sha256(state.encode()).digest())[:8]}"
        with self.lock:
            self.pending[code] = {
                "challenge": challenge,
                "method": method,
                "used": False,
                "expires_at": time.time() + 600,
            }

        if callback == "oob":
            return {"code": code, "state": state}
        target = f"{callback}?code={urllib.parse.quote(code)}&state={urllib.parse.quote(state)}"
        return {"callback_url": target, "code": code, "state": state}

    def expire(self, code: str) -> None:
        with self.lock:
            if code in self.pending:
                self.pending[code]["expires_at"] = time.time() - 1

    # ── catalog ───────────────────────────────────────────────────────────────

    def models_payload(self, query: str = "") -> dict[str, Any]:
        params = urllib.parse.parse_qs(query)
        capability = (params.get("capability") or [""])[0]
        models = list(CATALOG_FIXTURE)
        if capability == "embedding":
            models = [m for m in models if "embeddings" in m["supported_endpoint_types"]]
        elif capability == "image":
            models = [m for m in models if "image-generation" in m["supported_endpoint_types"]]
        elif capability == "video":
            models = [m for m in models if "openai-video" in m["supported_endpoint_types"]]
        elif capability == "rerank":
            models = [m for m in models if "jina-rerank" in m["supported_endpoint_types"]]
        elif capability == "chat":
            chat_types = {"openai", "anthropic", "gemini", "openai-response"}
            models = [m for m in models if chat_types & set(m["supported_endpoint_types"])]
        return {"object": "list", "data": models}


# Fixture covering every capability the filters must separate.
CATALOG_FIXTURE: list[dict[str, Any]] = [
    {
        "id": "openai/gpt-5.5",
        "name": "OpenAI: GPT-5.5",
        "context_length": 400000,
        "supported_endpoint_types": ["openai", "openai-response"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "reasoning": {"efforts": ["low", "medium", "high", "xhigh"]},
    },
    {
        "id": "anthropic/claude-opus-4.8",
        "name": "Anthropic: Claude Opus 4.8",
        "context_length": 200000,
        "supported_endpoint_types": ["anthropic", "openai"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
    },
    {
        "id": "google/gemini-3.5-flash",
        "name": "Google: Gemini 3.5 Flash",
        "context_length": 1000000,
        "supported_endpoint_types": ["gemini", "openai"],
        "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
    },
    {
        "id": "deepseek/deepseek-v4-pro",
        "name": "DeepSeek: V4 Pro",
        "context_length": 128000,
        "supported_endpoint_types": ["openai"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
    },
    {
        "id": "orcarouter/auto",
        "name": "OrcaRouter: Auto",
        "context_length": 128000,
        "supported_endpoint_types": ["openai", "anthropic", "gemini", "openai-response"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
    },
    {
        "id": "openai/gpt-image-1",
        "name": "OpenAI: GPT Image 1",
        "context_length": 0,
        "supported_endpoint_types": ["image-generation"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
    },
    {
        "id": "orcarouter/video-preview",
        "name": "OrcaRouter: Video Preview",
        "context_length": 0,
        "supported_endpoint_types": ["openai-video"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["video"]},
    },
    {
        "id": "jina/jina-reranker-v3",
        "name": "Jina: Reranker v3",
        "context_length": 8192,
        "supported_endpoint_types": ["jina-rerank"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
    },
    {
        "id": "openai/text-embedding-3-large",
        "name": "OpenAI: Text Embedding 3 Large",
        "context_length": 8191,
        "supported_endpoint_types": ["embeddings"],
        "architecture": {"input_modalities": ["text"], "output_modalities": ["embedding"]},
    },
    {
        "id": "audio/whisper-large-v3",
        "name": "Whisper Large v3",
        "context_length": 0,
        "supported_endpoint_types": ["openai-audio"],
        "architecture": {"input_modalities": ["audio"], "output_modalities": ["text"]},
    },
]
