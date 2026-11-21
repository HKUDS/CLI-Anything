"""Alexa backend — the only module that talks to Amazon.

Wraps the `alexapy` library (the engine behind Home Assistant's Alexa Media
Player) to control real Echo devices through Amazon's Alexa web API.

Authentication
--------------
Amazon has no public API for controlling your own Echo devices, so login uses
alexapy's capture proxy: a local web server on 127.0.0.1 forwards your browser
to Amazon's real sign-in page (captcha, 2FA and passkeys all work), captures
the resulting OAuth tokens, and registers this CLI as a device on your account.
Your password is typed into Amazon's page only; it is never stored.

Only the refresh token, device registration and session cookies are kept, in
``~/.cli-anything-alexa`` (override with ``ALEXA_CLI_HOME``), with owner-only
permissions.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid as uuidlib
from pathlib import Path
from typing import Any, Awaitable, Callable

INSTALL_HINT = "alexapy is required: pip install 'alexapy>=1.36'"
DEFAULT_LOCALE = "en-US"

# Speech language to use for each Amazon site unless the user picks one.
DOMAIN_LOCALES = {
    "amazon.com": "en-US", "amazon.ca": "en-CA", "amazon.co.uk": "en-GB", "amazon.com.au": "en-AU",
    "amazon.in": "en-IN", "amazon.de": "de-DE", "amazon.fr": "fr-FR", "amazon.it": "it-IT",
    "amazon.es": "es-ES", "amazon.com.mx": "es-MX", "amazon.com.br": "pt-BR", "amazon.co.jp": "ja-JP",
    "amazon.nl": "nl-NL",
}


_AMAZON_DOMAIN = __import__("re").compile(r"^amazon\.(?:[a-z]{2,3}|co\.[a-z]{2}|com\.[a-z]{2})$")


def valid_domain(domain: str) -> bool:
    """True for Amazon retail domains (amazon.com, amazon.co.uk, amazon.com.au, ...)."""
    return bool(_AMAZON_DOMAIN.match((domain or "").strip().lower()))


def locale_for(domain: str) -> str:
    return DOMAIN_LOCALES.get((domain or "").lower(), DEFAULT_LOCALE)


def domain_warning(account: dict[str, Any]) -> str | None:
    """Actionable message when the account lives on another Amazon site."""
    reported = account.get("reported_domain")
    if reported and reported.lower() != (account.get("domain") or "").lower():
        return (f"Your Amazon account is on {reported}, but you signed in with {account['domain']}. "
                f"Some commands may fail. Fix: cli-anything-alexa auth logout && "
                f"cli-anything-alexa auth login --email {account['email']} --domain {reported}")
    return None


def _quiet_alexapy_logs() -> None:
    """alexapy repeats some warnings on every request; we report them once ourselves."""
    import logging
    if not os.environ.get("ALEXA_CLI_DEBUG"):
        logging.getLogger("alexapy").setLevel(logging.ERROR)


# ── Storage ──────────────────────────────────────────────────────────

def config_dir() -> Path:
    path = Path(os.environ.get("ALEXA_CLI_HOME") or Path.home() / ".cli-anything-alexa").expanduser()
    (path / ".storage").mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
        (path / ".storage").chmod(0o700)
    except OSError:
        pass
    return path


def account_file() -> Path:
    return config_dir() / "account.json"


def load_account() -> dict[str, Any] | None:
    f = account_file()
    if not f.exists():
        return None
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def save_account(account: dict[str, Any]) -> None:
    """Atomically write account.json (0600).

    Each save uses its own temp file in the same directory, so concurrent CLI
    processes (e.g. parallel agent calls rotating tokens) never share or
    delete each other's temp file; os.replace keeps the live file valid.
    """
    import tempfile
    f = account_file()
    fd, tmp = tempfile.mkstemp(prefix=".account.", suffix=".tmp", dir=f.parent)
    try:
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(account, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, f)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def delete_account() -> bool:
    """Remove stored tokens and cookies. Returns True if anything was removed."""
    removed = False
    d = config_dir()
    for p in [d / "account.json", *(d / ".storage").glob("*")]:
        if p.is_file():
            p.unlink()
            removed = True
    return removed


def _outputpath(name: str) -> str:
    return str(config_dir() / name)


# ── alexapy plumbing ─────────────────────────────────────────────────

def use_certifi_bundle() -> None:
    """Make every HTTPS connection trust certifi's CA bundle.

    alexapy builds some aiohttp sessions with Python's default trust store.
    The python.org macOS installer ships without one (until the user runs
    "Install Certificates.command"), which breaks login with
    CERTIFICATE_VERIFY_FAILED. certifi is already an alexapy dependency, so
    point OpenSSL at it unless the user chose a bundle themselves.
    """
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
    except ImportError:  # pragma: no cover - certifi ships with alexapy
        return
    os.environ["SSL_CERT_FILE"] = certifi.where()


def _alexapy():
    use_certifi_bundle()
    _quiet_alexapy_logs()
    try:
        import alexapy  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised via CLI error path
        raise RuntimeError(INSTALL_HINT) from exc
    return alexapy


CERT_HINT = (
    "Python could not verify Amazon's HTTPS certificate. On macOS with Python from python.org, run "
    "'/Applications/Python 3.x/Install Certificates.command' (use your version), or set "
    "SSL_CERT_FILE to a CA bundle, then retry."
)


def is_cert_error(exc: BaseException) -> bool:
    """True if exc (or anything it wraps) is a TLS certificate failure."""
    import ssl
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


# ── Local port helpers (login proxy) ─────────────────────────────────

def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """True if something already accepts connections on host:port.

    Checked by connecting, not binding: on macOS another app listening on
    0.0.0.0 does not stop a 127.0.0.1 bind, yet the browser reaches that app.
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def free_port(host: str = "127.0.0.1") -> int:
    import socket
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            port = s.getsockname()[1]
        if not port_in_use(port, host):
            return port
    raise RuntimeError("Could not find a free local port for the sign-in page.")


def choose_port(requested: int | None) -> int:
    if requested is None:
        return free_port()
    if port_in_use(requested):
        raise RuntimeError(
            f"Port {requested} is already used by another app on this computer. "
            "Run auth login without --port to pick a free one automatically, or choose another port."
        )
    return requested


class NotLoggedIn(RuntimeError):
    """No usable Amazon session; run `auth login`."""


def run(coro_factory: Callable[[], Awaitable[Any]]) -> Any:
    """Run an async backend call from synchronous CLI code."""
    try:
        return asyncio.run(coro_factory())
    except Exception as exc:
        if is_cert_error(exc):
            raise RuntimeError(CERT_HINT) from exc
        raise


def _oauth_from(login) -> dict[str, Any]:
    return {
        "access_token": login.access_token,
        "refresh_token": login.refresh_token,
        "mac_dms": login.mac_dms,
        "expires_in": login.expires_in,
    }


async def _open_session():
    """Return a logged-in AlexaLogin built from the stored account."""
    alexapy = _alexapy()
    account = load_account()
    if not account or not (account.get("oauth") or {}).get("refresh_token"):
        raise NotLoggedIn("Not logged in to Amazon. Run: cli-anything-alexa auth login --email you@example.com")
    login = alexapy.AlexaLogin(
        url=account["domain"],
        email=account["email"],
        password="",
        outputpath=_outputpath,
        oauth=account["oauth"],
        uuid=account.get("uuid"),
    )
    await login.login(cookies=await login.load_cookie())
    if not await login.test_loggedin(rebuild_session=False):
        await login.close()
        raise NotLoggedIn("Amazon session expired or was revoked. Run: cli-anything-alexa auth login")
    # Tokens may rotate; persist the latest ones.
    account["oauth"] = _oauth_from(login)
    account["customer_id"] = login.customer_id or account.get("customer_id")
    if getattr(login, "reported_account_domain", None):
        account["reported_domain"] = login.reported_account_domain
    save_account(account)
    await login.save_cookiefile()
    return login, account


async def _with_session(fn: Callable[[Any, dict[str, Any]], Awaitable[Any]]) -> Any:
    login, account = await _open_session()
    try:
        return await fn(login, account)
    finally:
        await login.close()


# ── Login (capture proxy) ────────────────────────────────────────────

async def _login_via_proxy(email: str, domain: str, port: int, timeout: int,
                           on_url: Callable[[str], None]) -> dict[str, Any]:
    alexapy = _alexapy()
    device_uuid = uuidlib.uuid4().hex.upper()
    login = alexapy.AlexaLogin(url=domain, email=email, password="", outputpath=_outputpath, uuid=device_uuid)
    proxy = alexapy.AlexaProxy(login, f"http://127.0.0.1:{port}")
    await proxy.start_proxy(host="127.0.0.1")
    login.proxy_url = str(proxy.access_url())
    try:
        on_url(str(proxy.access_url()))
        deadline = time.monotonic() + timeout
        while not (getattr(login, "access_token", None) or getattr(login, "authorization_code", None)):
            if time.monotonic() > deadline:
                raise TimeoutError(f"No Amazon sign-in completed within {timeout}s.")
            await asyncio.sleep(1)
        # Register this CLI as a device and convert tokens into web cookies.
        if not await login.test_loggedin():
            raise NotLoggedIn("Amazon sign-in finished but the session could not be verified.")
        await login.finalize_login()
        account = {
            "email": email,
            "domain": domain,
            "uuid": login.uuid,
            "oauth": _oauth_from(login),
            "customer_id": login.customer_id,
            "locale": locale_for(domain),
            "reported_domain": getattr(login, "reported_account_domain", None),
            "logged_in_at": int(time.time()),
        }
        save_account(account)
        result = {"email": email, "domain": domain, "customer_id": login.customer_id,
                  "locale": account["locale"]}
        warning = domain_warning(account)
        if warning:
            result["warning"] = warning
        return result
    finally:
        await proxy.stop_proxy()
        await login.close()


def login(email: str, domain: str = "amazon.com", port: int | None = None, timeout: int = 600,
          on_url: Callable[[str], None] = print) -> dict[str, Any]:
    port = choose_port(port)
    return run(lambda: _login_via_proxy(email, domain, port, timeout, on_url))


def verify() -> dict[str, Any]:
    """Confirm the stored session works against Amazon."""
    async def _go(login, account):
        return {"email": account["email"], "domain": account["domain"],
                "customer_id": login.customer_id, "logged_in": True}
    return run(lambda: _with_session(_go))


# ── Devices ──────────────────────────────────────────────────────────

def fetch_devices() -> list[dict[str, Any]]:
    """Raw device records from Amazon."""
    alexapy = _alexapy()

    async def _go(login, account):
        return await alexapy.AlexaAPI.get_devices(login) or []
    return run(lambda: _with_session(_go))


def fetch_routines() -> list[dict[str, Any]]:
    alexapy = _alexapy()

    async def _go(login, account):
        return await alexapy.AlexaAPI.get_automations(login) or []
    return run(lambda: _with_session(_go))


def fetch_network() -> Any:
    alexapy = _alexapy()

    async def _go(login, account):
        return await alexapy.AlexaAPI.get_network_details(login) or []
    return run(lambda: _with_session(_go))


def cache_devices(devices: list[dict[str, Any]]) -> None:
    f = config_dir() / "devices.json"
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(devices, fh, indent=2)


def cached_devices() -> list[dict[str, Any]]:
    f = config_dir() / "devices.json"
    if not f.exists():
        return []
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


class _DeviceAdapter:
    """The attributes AlexaAPI reads from a device object."""

    def __init__(self, device: dict[str, Any], locale: str):
        self.device_serial_number = device["serial"]
        self._device_type = device["type"]
        self._device_family = device.get("family")
        self._cluster_members = device.get("cluster_members") or []
        self._locale = locale


# ── Execution ────────────────────────────────────────────────────────

async def _execute(login, account, action: dict[str, Any]) -> dict[str, Any]:
    alexapy = _alexapy()
    op = action["op"]
    locale = account.get("locale") or DEFAULT_LOCALE

    if op == "light":
        result = await alexapy.AlexaAPI.set_light_state(
            login, action["entity_id"], power_on=action["on"],
            brightness=action.get("brightness"), color_name=action.get("color"))
        return {"sent": True, "response": result}

    if op == "announce":
        first = action["devices"][0]
        api = alexapy.AlexaAPI(_DeviceAdapter(first, locale), login)
        await api.send_announcement(action["text"], title=action["title"],
                                    targets=[d["serial"] for d in action["devices"]], queue_delay=0)
        return {"sent": True}

    api = alexapy.AlexaAPI(_DeviceAdapter(action["device"], locale), login)
    if op == "speak":
        await api.send_tts(action["text"], queue_delay=0)
    elif op == "command":
        await api.run_custom(action["text"], queue_delay=0)
    elif op == "routine":
        await api.run_routine(action["utterance"], queue_delay=0)
    elif op == "sequence":
        await api.send_sequence(action["sequence"], queue_delay=0)
    elif op == "music":
        await api.play_music(action["provider"], action["query"], timer=action.get("timer"), queue_delay=0)
    elif op == "volume":
        await api.set_volume(action["level"] / 100.0, queue_delay=0)
    elif op == "media":
        mop = action["media_op"]
        if mop == "stop":
            await api.stop(queue_delay=0)
        else:
            await getattr(api, mop)()
    else:
        raise ValueError(f"Unknown action op: {op}")
    return {"sent": True}


def execute(action: dict[str, Any]) -> dict[str, Any]:
    """Send an action (from core.actions) to Amazon."""
    return run(lambda: _with_session(lambda login, account: _execute(login, account, action)))
