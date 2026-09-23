"""Local settings UI for the OrcaRouter provider.

Serves a small page on loopback where the user can pick either authentication
choice (paste an API key, or sign in with OAuth 2.0 + PKCE), and pick a model
from the live OrcaRouter catalog.

The page never receives the API key: the key stays in this process, and the
browser only ever sees a masked form, the authorization URL, and model
metadata. This mirrors the repository's existing preview pattern
(``cli-hub previews`` / ``live2d snapshot``) of serving a self-contained page
from a stdlib ``ThreadingHTTPServer`` on ``127.0.0.1``.

The server is a browser front end over the same credential seam and provider
code path the CLI uses — it does not carry its own authentication logic.
"""

from __future__ import annotations

import json
import queue
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

from . import catalog as catalog_mod
from . import credentials, login_manager, pkce

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
LOOPBACK = "127.0.0.1"


class SettingsServer(ThreadingHTTPServer):
    """Loopback-only HTTP server exposing the OrcaRouter settings page."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        opener: Optional[Callable[..., Any]] = None,
        open_browser: bool = False,
    ) -> None:
        super().__init__(address, SettingsHandler)
        self.opener = opener
        self.open_browser = open_browser
        self.logins = login_manager.LoginManager()
        self._code_queue: "queue.Queue[str]" = queue.Queue()
        self._code_expected = False

    def provide_code(self, code: str) -> None:
        self._code_queue.put(code)


class SettingsHandler(SimpleHTTPRequestHandler):
    server: SettingsServer

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    # ── helpers ───────────────────────────────────────────────────────────────

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    # ── routing ───────────────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == "/api/auth/status":
            return self._send_json(self._auth_status())
        if parsed.path == "/api/auth/login":
            return self._send_json(self.server.logins.state.public_dict())
        if parsed.path == "/api/models":
            return self._send_json(self._models(parse_qs(parsed.query)))
        if parsed.path.startswith("/static/"):
            self.path = parsed.path[len("/static"):]
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        payload = self._read_json()
        try:
            if parsed.path == "/api/auth/api-key":
                return self._store_api_key(payload)
            if parsed.path == "/api/auth/clear":
                credentials.clear_credential()
                return self._send_json(self._auth_status())
            if parsed.path == "/api/auth/login":
                return self._start_login(payload)
            if parsed.path == "/api/auth/login/cancel":
                self.server.logins.cancel()
                return self._send_json(self.server.logins.state.public_dict())
            if parsed.path == "/api/auth/login/code":
                return self._submit_code(payload)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, 400)
        return self._send_json({"error": "not found"}, 404)

    # ── endpoints ─────────────────────────────────────────────────────────────

    def _auth_status(self) -> dict[str, Any]:
        credential = credentials.resolve_credential()
        payload: dict[str, Any] = {
            "authenticated": credential is not None,
            "masked_key": credentials.mask_secret(credential.api_key) if credential else "",
            "credential": credential.public_dict() if credential else {},
            "auth_origin": credentials.auth_base_url(),
            "api_origin": credentials.api_base_url(),
        }
        return payload

    def _store_api_key(self, payload: dict[str, Any]) -> None:
        raw = str(payload.get("api_key") or "")
        credentials.validate_api_key_format(raw)
        stored = credentials.store_credential(
            credentials.Credential(
                api_key=raw.strip(),
                method=credentials.METHOD_API_KEY,
                source=credentials.SOURCE_STORED,
            )
        )
        return self._send_json({"stored": True, "credential": stored.public_dict()})

    def _models(self, query: dict[str, list[str]]) -> dict[str, Any]:
        capability = (query.get("capability") or [catalog_mod.CAPABILITY_CHAT])[0]
        modalities = tuple(
            m for m in (query.get("modalities") or [""])[0].split(",") if m
        )
        credential = credentials.resolve_credential()
        catalog = catalog_mod.load_catalog(credential, capability=capability)
        filtered = catalog_mod.selectable_models(
            catalog, capability, required_modalities=modalities
        )
        payload = catalog_mod.Catalog(
            models=filtered, source=catalog.source, detail=catalog.detail
        ).to_public_dict()
        payload["capability"] = capability
        payload["required_modalities"] = list(modalities)
        payload["catalog_url"] = f"{credentials.api_base_url()}/models"
        return payload

    def _start_login(self, payload: dict[str, Any]) -> None:
        flow = str(payload.get("flow") or pkce.FLOW_LOOPBACK)
        if flow not in {pkce.FLOW_LOOPBACK, pkce.FLOW_OOB}:
            raise ValueError(f"Unsupported flow: {flow}")

        attempt = self.server.logins.begin(
            flow=flow,
            opener=self.server.opener,
            open_browser=self.server.open_browser,
        )

        def worker() -> None:
            def code_provider(url: str) -> str:
                try:
                    return self.server._code_queue.get(timeout=attempt.timeout)
                except queue.Empty:
                    raise login_manager.LoginError(
                        "Timed out waiting for the authorization code.", kind="timeout"
                    ) from None

            try:
                code = attempt.wait_for_code(code_provider)
                result = attempt.complete(code)
            except (login_manager.LoginError, pkce.PkceError) as exc:
                self.server.logins.fail(attempt, str(exc))
                return
            finally:
                attempt.close()

            if not self.server.logins.is_current(attempt):
                return
            credentials.store_credential(result.to_credential())
            self.server.logins.finish_success(attempt)

        threading.Thread(target=worker, name="orca-login", daemon=True).start()
        return self._send_json(self.server.logins.state.public_dict())

    def _submit_code(self, payload: dict[str, Any]) -> None:
        code = str(payload.get("code") or "").strip()
        if not code:
            raise ValueError("No authorization code supplied.")
        state = self.server.logins.state
        if not state.busy:
            raise ValueError("No sign-in is waiting for a code.")
        self.server.provide_code(code)
        return self._send_json(state.public_dict())


def start_server(
    *,
    port: int = 0,
    open_browser: bool = False,
    opener: Optional[Callable[..., Any]] = None,
) -> tuple[SettingsServer, str]:
    server = SettingsServer((LOOPBACK, port), opener=opener, open_browser=open_browser)
    host, bound_port = server.server_address[0], server.server_address[1]
    url = f"http://{host}:{bound_port}/"
    return server, url


def serve_forever(
    *,
    port: int = 0,
    open_browser: bool = False,
    opener: Optional[Callable[..., Any]] = None,
    on_ready: Optional[Callable[[str], None]] = None,
) -> None:
    server, url = start_server(port=port, open_browser=open_browser, opener=opener)
    if on_ready is not None:
        on_ready(url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - environment dependent
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive
        pass
    finally:
        server.server_close()
