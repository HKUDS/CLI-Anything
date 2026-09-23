"""The "Connect with OrcaRouter" login lifecycle.

One sign-in is in flight at a time. Every attempt carries a monotonically
increasing id; a late response from an abandoned attempt can never publish a
credential or move the UI state of the current one.

Flow A (loopback redirect) is the default: the client runs on the user's
machine, has a browser, and can bind a loopback port. The listener is started
*before* the browser opens, so the port is known and there is no race.

Flow B (out-of-band code) is used with ``--oob`` for headless, SSH and
container sessions where a browser cannot reach the local listener. It sends
``callback_url=oob`` and the user pastes the code back.

Both flows send S256.
"""

from __future__ import annotations

import http.server
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import credentials, pkce

LOOPBACK_HOST = "127.0.0.1"
CALLBACK_PATH = "/cb"
DEFAULT_TIMEOUT = 300

_CLOSE_PAGE = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>OrcaRouter</title></head><body style='font-family:system-ui;padding:3rem'>"
    "<h2>Connected.</h2><p>You can close this tab and return to the terminal.</p>"
    "</body></html>"
)


class LoginError(RuntimeError):
    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass
class LoginState:
    """Current login status. Only one attempt is ever in flight."""

    attempt: int = 0
    generation: int = 0
    busy: bool = False
    hint: str = ""
    authorize_url: str = ""
    flow: str = ""
    last_error: str = ""
    completed: bool = False

    def public_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "generation": self.generation,
            "busy": self.busy,
            "hint": self.hint,
            "authorize_url": self.authorize_url,
            "flow": self.flow,
            "last_error": self.last_error,
            "completed": self.completed,
        }


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args: Any, attempt: "LoginAttempt", **kwargs: Any) -> None:
        self._attempt = attempt
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_CLOSE_PAGE.encode("utf-8"))
        self._attempt.deliver(
            code=(query.get("code") or [None])[0],
            error=(query.get("error") or [None])[0],
            state=(query.get("state") or [None])[0],
        )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


@dataclass
class LoginAttempt:
    """A single authorization attempt."""

    id: int
    flow: str
    scope: str = pkce.SCOPE_API
    app_name: str = credentials.APP_NAME
    timeout: float = DEFAULT_TIMEOUT
    opener: Optional[Callable[..., Any]] = None
    open_browser: bool = True
    pkce: pkce.PkceAttempt = field(init=False)
    authorize_url: str = field(init=False, default="")
    callback_url: str = field(init=False, default="")
    state: str = field(init=False, default="")

    _code: Optional[str] = field(init=False, default=None)
    _error: Optional[str] = field(init=False, default=None)
    _delivered: threading.Event = field(init=False, default_factory=threading.Event)
    _server: Optional[http.server.HTTPServer] = field(init=False, default=None)
    _thread: Optional[threading.Thread] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.pkce = pkce.PkceAttempt(flow=self.flow, scope=self.scope)
        self.state = self.pkce.state
        self.callback_url = "oob" if self.flow == pkce.FLOW_OOB else self._start_listener()
        self.authorize_url = self.pkce.authorize_url(
            callback_url=self.callback_url, app_name=self.app_name
        )

    # ── Flow A plumbing ───────────────────────────────────────────────────────

    def _start_listener(self) -> str:
        handler = lambda *a, **kw: _CallbackHandler(*a, attempt=self, **kw)  # noqa: E731
        server = http.server.HTTPServer((LOOPBACK_HOST, 0), handler)
        server.timeout = 1.0
        self._server = server
        port = server.server_address[1]
        self._thread = threading.Thread(target=self._serve, name="orca-oauth-callback", daemon=True)
        self._thread.start()
        return f"http://{LOOPBACK_HOST}:{port}{CALLBACK_PATH}"

    def _serve(self) -> None:
        server = self._server
        if server is None:
            return
        deadline = time.monotonic() + self.timeout
        while not self._delivered.is_set() and time.monotonic() < deadline:
            server.handle_request()

    def deliver(self, *, code: Optional[str], error: Optional[str], state: Optional[str]) -> None:
        """Called by the loopback listener. Compares state before anything else."""
        if self._delivered.is_set():
            return
        if not self.pkce.state_matches(state):
            self._error = "state mismatch — the callback did not come from this sign-in attempt"
            self._delivered.set()
            return
        if error:
            self._error = error
        else:
            self._code = code
        self._delivered.set()

    def wait_for_code(self, code_provider: Optional[Callable[[str], str]] = None) -> str:
        """Block until a code arrives (Flow A) or is pasted (Flow B)."""
        if self.flow == pkce.FLOW_OOB:
            if code_provider is None:
                raise LoginError("out-of-band flow needs a code provider", kind="bad_config")
            pasted = code_provider(self.authorize_url)
            if not pasted or not pasted.strip():
                raise LoginError("No code was provided.", kind="cancelled")
            return pasted.strip()

        if not self._delivered.wait(self.timeout):
            raise LoginError(
                "Timed out waiting for the browser to return. Start the sign-in again, "
                "or use `auth login --oob` on a machine without a browser.",
                kind="timeout",
            )
        if self._error:
            if self._error == "access_denied":
                raise LoginError("Authorization was denied in the browser.", kind="denied")
            raise LoginError(f"Authorization failed: {self._error}", kind="callback_error")
        if not self._code:
            raise LoginError("The callback carried no authorization code.", kind="callback_error")
        return self._code

    def cancel(self) -> None:
        """Release the listener and any waiter. Safe to call at any time."""
        self._error = "cancelled"
        self._delivered.set()
        self.close()

    def close(self) -> None:
        server = self._server
        if server is not None:
            self._server = None
            try:
                server.server_close()
            except OSError:
                pass

    # ── exchange ──────────────────────────────────────────────────────────────

    def complete(self, code: str) -> pkce.PkceResult:
        return self.pkce.exchange(code, opener=self.opener)


class LoginManager:
    """Owns the single in-flight login and its generation counter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = LoginState()
        self._current: Optional[LoginAttempt] = None
        # Bumped on every terminal transition. The UI uses it to drop a status
        # response that was in flight while the login was cancelled.
        self._generation = 0

    @property
    def state(self) -> LoginState:
        with self._lock:
            return self._state

    def begin(
        self,
        *,
        flow: str = pkce.FLOW_LOOPBACK,
        scope: str = pkce.SCOPE_API,
        app_name: str = credentials.APP_NAME,
        timeout: float = DEFAULT_TIMEOUT,
        opener: Optional[Callable[..., Any]] = None,
        open_browser: bool = True,
    ) -> LoginAttempt:
        """Start a new attempt, invalidating any previous one."""
        self.cancel(reason="superseded by a new sign-in")
        attempt = LoginAttempt(
            id=self._state.attempt + 1,
            flow=flow,
            scope=scope,
            app_name=app_name,
            timeout=timeout,
            opener=opener,
            open_browser=open_browser,
        )
        with self._lock:
            self._current = attempt
            self._generation += 1
            self._state = LoginState(
                attempt=attempt.id,
                generation=self._generation,
                busy=True,
                hint="Waiting for authorization in the browser…",
                authorize_url=attempt.authorize_url,
                flow=flow,
            )
        if open_browser and flow == pkce.FLOW_LOOPBACK:
            try:
                webbrowser.open(attempt.authorize_url)
            except Exception:  # pragma: no cover - environment dependent
                pass
        return attempt

    def is_current(self, attempt: LoginAttempt) -> bool:
        with self._lock:
            return self._current is attempt

    def finish_success(self, attempt: LoginAttempt) -> Optional[credentials.Credential]:
        """Persist the result, but only if this attempt is still current."""
        with self._lock:
            if self._current is not attempt:
                return None
            self._current = None
            self._generation += 1
            self._state = LoginState(
                attempt=attempt.id,
                generation=self._generation,
                busy=False,
                hint="",
                flow=attempt.flow,
                completed=True,
            )
        return None

    def fail(self, attempt: LoginAttempt, message: str) -> bool:
        with self._lock:
            if self._current is not attempt:
                return False
            self._current = None
            self._generation += 1
            self._state = LoginState(
                attempt=attempt.id,
                generation=self._generation,
                busy=False,
                hint="",
                flow=attempt.flow,
                last_error=message,
            )
        return True

    def cancel(self, *, reason: str = "cancelled") -> bool:
        """Release the in-flight attempt, its listener and its UI state."""
        with self._lock:
            attempt = self._current
            self._current = None
            if attempt is None and not self._state.busy:
                return False
            attempt_id = attempt.id if attempt else self._state.attempt
            flow = attempt.flow if attempt else self._state.flow
            self._generation += 1
            self._state = LoginState(
                attempt=attempt_id,
                generation=self._generation,
                busy=False,
                hint="",
                flow=flow,
                last_error="" if reason == "cancelled" else reason,
            )
        if attempt is not None:
            attempt.cancel()
        return True

    def pagehide(self) -> bool:
        """Back-forward-cache safe cancellation.

        Clears busy and the authorization hint synchronously, then releases the
        listener. A guarded ``finally`` in the abandoned request would refuse to
        touch state, which would leave a restored page permanently busy.
        """
        return self.cancel(reason="page hidden")


def run_login(
    manager: LoginManager,
    *,
    flow: str = pkce.FLOW_LOOPBACK,
    scope: str = pkce.SCOPE_API,
    app_name: str = credentials.APP_NAME,
    timeout: float = DEFAULT_TIMEOUT,
    opener: Optional[Callable[..., Any]] = None,
    open_browser: bool = True,
    code_provider: Optional[Callable[[str], str]] = None,
    on_prompt: Optional[Callable[[str], None]] = None,
) -> pkce.PkceResult:
    """Drive one sign-in to completion and return the exchange result.

    The caller decides what to do with the result — this function never writes
    a credential, so an abandoned attempt cannot overwrite a newer one.
    """
    attempt = manager.begin(
        flow=flow,
        scope=scope,
        app_name=app_name,
        timeout=timeout,
        opener=opener,
        open_browser=open_browser,
    )
    if on_prompt is not None:
        on_prompt(attempt.authorize_url)
    try:
        code = attempt.wait_for_code(code_provider)
        result = attempt.complete(code)
    except (LoginError, pkce.PkceError) as exc:
        manager.fail(attempt, str(exc))
        raise
    finally:
        attempt.close()

    if not manager.is_current(attempt):
        # A newer sign-in started while this one was finishing. Drop the result.
        raise LoginError(
            "This sign-in was superseded by a newer attempt; its result was discarded.",
            kind="stale",
        )
    manager.finish_success(attempt)
    return result
