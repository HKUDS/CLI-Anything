"""OAuth 2.0 + PKCE helpers for the OrcaRouter connect flow.

The verifier is generated fresh from a cryptographic RNG for every attempt and
never leaves this process until the code exchange. Only its S256 challenge is
put on the authorize URL. No client secret is involved, and there is no
redirect URI to pre-register.

Both supported flows send S256. Flow A is the loopback redirect; Flow B is the
out-of-band code the user copies back, which is mandatory for headless clients
and is also what a user gets if they pick "Show me a code" on the consent
screen even when a callback URL was supplied.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from . import credentials

FLOW_LOOPBACK = "loopback"
FLOW_OOB = "oob"

SCOPE_API = "api"
SCOPE_CONNECTOR = "connector"

EXCHANGE_TIMEOUT = 30


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def new_verifier() -> str:
    """A fresh high-entropy verifier from a cryptographic RNG."""
    return b64url(secrets.token_bytes(32))


def new_state() -> str:
    return b64url(secrets.token_bytes(16))


def challenge_for(verifier: str) -> str:
    """``base64url(sha256(verifier))`` with no padding."""
    return b64url(hashlib.sha256(verifier.encode("ascii")).digest())


@dataclass
class PkceAttempt:
    """One authorization attempt. A new instance is created per attempt."""

    flow: str = FLOW_LOOPBACK
    scope: str = SCOPE_API
    verifier: str = field(default_factory=new_verifier)
    state: str = field(default_factory=new_state)

    def __post_init__(self) -> None:
        self.challenge = challenge_for(self.verifier)

    def authorize_url(self, *, callback_url: str, app_name: str = credentials.APP_NAME) -> str:
        params = {
            "callback_url": callback_url,
            "code_challenge": self.challenge,
            "code_challenge_method": "S256",
            "state": self.state,
            "app_name": app_name,
            "scope": self.scope,
        }
        return f"{credentials.authorize_url()}?{urllib.parse.urlencode(params)}"

    def state_matches(self, received: Optional[str]) -> bool:
        """Constant-time comparison of the CSRF token."""
        if not received:
            return False
        return hmac.compare_digest(self.state, received)

    def exchange(self, code: str, *, opener: Any = None) -> "PkceResult":
        """Redeem the auth code. The verifier is sent here and nowhere else."""
        body = json.dumps(
            {
                "code": code,
                "code_verifier": self.verifier,
                "code_challenge_method": "S256",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            credentials.exchange_url(),
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        send = opener or urllib.request.urlopen
        try:
            with send(request, timeout=EXCHANGE_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise _exchange_error(exc.code, exc.read()) from None
        except urllib.error.URLError as exc:
            raise PkceError(
                "Could not reach the OrcaRouter authorization service. Check your network and retry.",
                kind="network",
            ) from exc

        key = payload.get("key")
        if not isinstance(key, str) or not key:
            raise PkceError(
                "The authorization service returned no key.", kind="malformed_response"
            )
        granted_scope = str(payload.get("scope") or "")
        return PkceResult(
            api_key=key,
            account_id=str(payload.get("user_id") or ""),
            granted_scope=granted_scope,
            requested_scope=self.scope,
        )


class PkceError(RuntimeError):
    """A terminal authorization failure with an actionable message."""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


def _exchange_error(status: int, raw_body: bytes) -> PkceError:
    if status == 400:
        return PkceError(
            "The authorization service rejected the PKCE challenge method. "
            "Start the sign-in again.",
            kind="bad_challenge_method",
        )
    if status == 403:
        return PkceError(
            "That authorization code is unknown, expired, or already used. "
            "Authorization codes are single-use and last 10 minutes — start the sign-in again.",
            kind="code_rejected",
        )
    if status == 429:
        return PkceError(
            "OrcaRouter is rate-limiting key issuance for this account "
            "(at most 10 sign-ins per 24 hours). Reuse the stored key or wait before retrying.",
            kind="rate_limited",
        )
    detail = raw_body.decode("utf-8", errors="replace")[:300] if raw_body else ""
    return PkceError(
        f"The authorization service returned HTTP {status}. {detail}".strip(),
        kind="exchange_failed",
    )


@dataclass
class PkceResult:
    """What the exchange produced: a normal, durable OrcaRouter API key."""

    api_key: str
    account_id: str = ""
    granted_scope: str = ""
    requested_scope: str = SCOPE_API

    def scope_warning(self) -> Optional[str]:
        """Warn when the granted scope is narrower than the requested one."""
        if self.granted_scope and self.requested_scope and self.granted_scope != self.requested_scope:
            return (
                f'Granted scope is "{self.granted_scope}", not the requested '
                f'"{self.requested_scope}" — this account may not hold the wider grant.'
            )
        return None

    def scope_allows_api(self) -> bool:
        return self.granted_scope in {"", SCOPE_API, SCOPE_CONNECTOR}

    def to_credential(self) -> credentials.Credential:
        return credentials.Credential(
            api_key=self.api_key,
            method=credentials.METHOD_OAUTH_PKCE,
            source=credentials.SOURCE_STORED,
            account_id=self.account_id,
            scope=self.granted_scope,
        )
