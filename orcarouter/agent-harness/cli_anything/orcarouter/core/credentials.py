"""OrcaRouter credential seam.

Both user-facing authentication choices end here: a pasted API key and the
OAuth 2.0 + PKCE connect flow both produce the same kind of OrcaRouter API key,
so the provider, the model catalog and the CLI never need to know which one was
used.

Credential sources, in priority order:

1. ``--api-key`` on the command line (never persisted)
2. ``ORCAROUTER_API_KEY`` environment variable (never persisted)
3. ``~/.config/cli-anything-orcarouter/config.json`` (mode 0600)

The stored key is a durable OrcaRouter API key, not an access/refresh token
pair. It is reused until OrcaRouter revokes it; there is no refresh grant to
call and none is attempted. A ``401`` from the inference relay marks exactly
the stored account generation that made the rejected request as needing
re-authentication.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional

ENV_API_KEY = "ORCAROUTER_API_KEY"
CONFIG_DIR = Path(
    os.environ.get("ORCAROUTER_CONFIG_DIR", str(Path.home() / ".config" / "cli-anything-orcarouter"))
)
CONFIG_FILE = CONFIG_DIR / "config.json"

SOURCE_CLI = "cli"
SOURCE_ENV = "env"
SOURCE_STORED = "stored"

METHOD_API_KEY = "api_key"
METHOD_OAUTH_PKCE = "oauth_pkce"

STATUS_OK = "ok"
STATUS_NEEDS_REAUTH = "needs_reauth"

DEFAULT_AUTH_BASE = "https://www.orcarouter.ai"
DEFAULT_API_BASE = "https://api.orcarouter.ai/v1"
DEFAULT_SCOPE = "api"
APP_NAME = "CLI-Anything"


@dataclass(frozen=True)
class Credential:
    """One OrcaRouter credential, whichever way the user obtained it."""

    api_key: str
    method: str
    source: str
    account_id: str = ""
    scope: str = ""
    generation: int = 1
    status: str = STATUS_OK
    created_at: str = ""

    def public_dict(self) -> dict[str, Any]:
        """JSON-safe view. The key itself is never included."""
        return {
            "method": self.method,
            "source": self.source,
            "account_id": self.account_id,
            "scope": self.scope,
            "generation": self.generation,
            "status": self.status,
            "created_at": self.created_at,
        }


class AuthRequiredError(RuntimeError):
    """No credential is available for an inference call."""


def mask_secret(value: str) -> str:
    """Return a display form that never reveals the whole secret."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:7]}...{value[-4:]}"


def validate_api_key_format(api_key: str) -> None:
    """Lightweight shape check only.

    The ``sk-orca-`` prefix catches obvious paste mistakes. It is not proof
    that the credential is valid, and no paid request is sent to find out.
    """
    if not api_key or not api_key.strip():
        raise ValueError("API key is empty.")
    key = api_key.strip()
    if not key.startswith("sk-orca-"):
        raise ValueError(
            "That does not look like an OrcaRouter API key (expected the 'sk-orca-' prefix). "
            "Create one at https://www.orcarouter.ai"
        )
    if len(key) < 20:
        raise ValueError("That OrcaRouter API key looks truncated.")


# ── config file ───────────────────────────────────────────────────────────────


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.is_file():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


def _stored_credential(config: dict[str, Any]) -> Optional[Credential]:
    entry = config.get("credential")
    if not isinstance(entry, dict):
        return None
    api_key = entry.get("api_key")
    if not isinstance(api_key, str) or not api_key:
        return None
    return Credential(
        api_key=api_key,
        method=str(entry.get("method") or METHOD_API_KEY),
        source=SOURCE_STORED,
        account_id=str(entry.get("account_id") or ""),
        scope=str(entry.get("scope") or ""),
        generation=int(entry.get("generation") or 1),
        status=str(entry.get("status") or STATUS_OK),
        created_at=str(entry.get("created_at") or ""),
    )


def resolve_credential(cli_key: Optional[str] = None) -> Optional[Credential]:
    """Resolve the credential to use for this process.

    A CLI flag or environment variable is a deliberate per-invocation override
    and is never written to disk.
    """
    if cli_key and cli_key.strip():
        key = cli_key.strip()
        return Credential(api_key=key, method=METHOD_API_KEY, source=SOURCE_CLI)

    env_key = os.environ.get(ENV_API_KEY, "").strip()
    if env_key:
        return Credential(api_key=env_key, method=METHOD_API_KEY, source=SOURCE_ENV)

    return _stored_credential(load_config())


def require_credential(cli_key: Optional[str] = None) -> Credential:
    credential = resolve_credential(cli_key)
    if credential is None:
        raise AuthRequiredError(
            "No OrcaRouter credential found. Authenticate with either:\n"
            "  1. cli-anything-orcarouter auth api-key --api-key sk-orca-...\n"
            f"  2. export {ENV_API_KEY}=sk-orca-...\n"
            "  3. cli-anything-orcarouter auth login        (browser sign-in, OAuth 2.0 + PKCE)\n"
            "Create a key at https://www.orcarouter.ai"
        )
    return credential


def store_credential(credential: Credential) -> Credential:
    """Persist a credential in the project's existing config file.

    Replacing an existing entry bumps the generation so that a late failure
    from an older request cannot mark the new credential as broken.
    """
    config = load_config()
    previous = _stored_credential(config)
    generation = 1 if previous is None else previous.generation + 1
    stored = replace(
        credential,
        source=SOURCE_STORED,
        generation=generation,
        status=STATUS_OK,
    )
    config["credential"] = {
        "api_key": stored.api_key,
        "method": stored.method,
        "account_id": stored.account_id,
        "scope": stored.scope,
        "generation": stored.generation,
        "status": stored.status,
        "created_at": stored.created_at,
    }
    save_config(config)
    return stored


def clear_credential() -> bool:
    """Remove the stored credential. Returns True when one was removed."""
    config = load_config()
    if "credential" not in config:
        return False
    del config["credential"]
    save_config(config)
    return True


def mark_needs_reauth(
    credential: Credential,
    *,
    reason: str = "upstream rejected this credential",
) -> bool:
    """Mark the exact account generation that made a rejected request.

    Returns True when the stored credential was updated. A credential that
    came from a CLI flag or the environment is not persisted, and a stored
    credential whose generation has already moved on (the user re-authenticated
    while the request was in flight) is left alone.
    """
    config = load_config()
    stored = _stored_credential(config)
    if stored is None or credential.source != SOURCE_STORED:
        return False
    if stored.generation != credential.generation:
        return False
    if stored.status == STATUS_NEEDS_REAUTH:
        return False
    entry = config["credential"]
    entry["status"] = STATUS_NEEDS_REAUTH
    entry["needs_reauth_reason"] = reason
    save_config(config)
    return True


# ── origins ───────────────────────────────────────────────────────────────────


def _require_https(url: str, what: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme == "https":
        return url
    if parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "[::1]", "::1"}:
        return url
    raise ValueError(
        f"{what} must use https:// (http:// is allowed only for loopback development hosts), got: {url}"
    )


def auth_base_url() -> str:
    """Where authorization and code exchange happen."""
    explicit = os.environ.get("ORCA_AUTH_BASE_URL", "").strip()
    if explicit:
        return _require_https(explicit.rstrip("/"), "ORCA_AUTH_BASE_URL")
    shared = os.environ.get("ORCA_BASE_URL", "").strip()
    if shared:
        return _require_https(shared.rstrip("/"), "ORCA_BASE_URL")
    return DEFAULT_AUTH_BASE


def api_base_url() -> str:
    """Where inference and model discovery happen."""
    explicit = os.environ.get("ORCA_API_BASE_URL", "").strip()
    if explicit:
        return _require_https(explicit.rstrip("/"), "ORCA_API_BASE_URL")
    shared = os.environ.get("ORCA_BASE_URL", "").strip()
    if shared:
        return _require_https(shared.rstrip("/") + "/v1", "ORCA_BASE_URL")
    return DEFAULT_API_BASE


AUTHORIZE_PATH = "/auth"
EXCHANGE_PATH = "/api/v1/auth/keys"


def authorize_url() -> str:
    return auth_base_url() + AUTHORIZE_PATH


def exchange_url() -> str:
    return auth_base_url() + EXCHANGE_PATH
