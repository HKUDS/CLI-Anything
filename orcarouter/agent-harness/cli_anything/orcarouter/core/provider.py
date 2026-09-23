"""The OrcaRouter provider: one inference path for every authentication choice.

Inference and model discovery always go to the configured inference origin
(``https://api.orcarouter.ai/v1`` by default) with ``Authorization: Bearer``.
Authorization and code exchange always go to the configured auth origin
(``https://www.orcarouter.ai`` by default). Neither origin is ever derived from
the other by rewriting a hostname or appending ``/v1``.

The provider never inspects where a credential came from. A pasted key and a
PKCE-issued key are the same object on the same code path.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

from . import catalog as catalog_mod
from . import credentials

REQUEST_TIMEOUT = 120
STREAM_TIMEOUT = 300
MAX_ERROR_BODY = 500


class ProviderError(RuntimeError):
    """A terminal inference failure with a user-actionable message."""

    def __init__(self, message: str, *, kind: str, status: int = 0) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


@dataclass
class ChatResult:
    model: str
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    response_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request_for(
    credential: credentials.Credential,
    path: str,
    body: bytes,
    *,
    api_base: Optional[str] = None,
) -> urllib.request.Request:
    """Build an inference request. Only the credential's secret is used."""
    base = api_base or credentials.api_base_url()
    return urllib.request.Request(
        f"{base}{path}",
        data=body,
        headers=_auth_headers(credential.api_key),
        method="POST",
    )


def _raise_for_status(status: int, raw_body: bytes, credential: credentials.Credential) -> None:
    detail = raw_body.decode("utf-8", errors="replace")[:MAX_ERROR_BODY] if raw_body else ""
    if status == 401:
        # A durable OrcaRouter key cannot be refreshed. Mark exactly the account
        # generation that made this request and tell the user to sign in again.
        credentials.mark_needs_reauth(credential)
        raise ProviderError(
            "OrcaRouter rejected this credential (HTTP 401). It may have been revoked at "
            "https://www.orcarouter.ai/console/authorized-apps. "
            "Run `cli-anything-orcarouter auth login` or store a new API key.",
            kind="needs_reauth",
            status=status,
        )
    if status == 403:
        raise ProviderError(
            "OrcaRouter refused this request (HTTP 403). The key may lack access to this model.",
            kind="forbidden",
            status=status,
        )
    if status == 429:
        raise ProviderError(
            "OrcaRouter rate-limited this request (HTTP 429). Retry after a short wait.",
            kind="rate_limited",
            status=status,
        )
    raise ProviderError(
        f"OrcaRouter returned HTTP {status}. {detail}".strip(),
        kind="request_failed",
        status=status,
    )


def _send(
    request: urllib.request.Request,
    *,
    timeout: int,
    opener: Optional[Callable[..., Any]],
) -> Any:
    send = opener or urllib.request.urlopen
    try:
        return send(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise exc
    except urllib.error.URLError as exc:
        raise ProviderError(
            f"Could not reach OrcaRouter at {credentials.api_base_url()}: {exc.reason}",
            kind="network",
        ) from exc


def chat_completion(
    credential: credentials.Credential,
    *,
    model: str,
    messages: list[dict[str, Any]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    api_base: Optional[str] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> ChatResult:
    """One OpenAI-compatible chat completion against the OrcaRouter relay."""
    body: dict[str, Any] = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    request = _request_for(
        credential, "/chat/completions", json.dumps(body).encode("utf-8"), api_base=api_base
    )
    try:
        with _send(request, timeout=REQUEST_TIMEOUT, opener=opener) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        _raise_for_status(exc.code, exc.read(), credential)
        raise  # pragma: no cover - _raise_for_status always raises

    choices = payload.get("choices") or []
    content = ""
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
    return ChatResult(
        model=str(payload.get("model") or model),
        content=content,
        usage=payload.get("usage") or {},
        response_id=str(payload.get("id") or ""),
        raw=payload,
    )


def chat_completion_stream(
    credential: credentials.Credential,
    *,
    model: str,
    messages: list[dict[str, Any]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    api_base: Optional[str] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> Iterator[str]:
    """Yield content deltas from a streamed completion."""
    body: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    request = _request_for(
        credential, "/chat/completions", json.dumps(body).encode("utf-8"), api_base=api_base
    )
    try:
        response = _send(request, timeout=STREAM_TIMEOUT, opener=opener)
    except urllib.error.HTTPError as exc:
        _raise_for_status(exc.code, exc.read(), credential)
        raise  # pragma: no cover

    with response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if not choices or not isinstance(choices[0], dict):
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content


def list_models(
    credential: credentials.Credential,
    *,
    capability: Optional[str] = None,
    api_base: Optional[str] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> list[dict[str, Any]]:
    """Live model list from the configured inference origin."""
    live = catalog_mod.fetch_live_catalog(
        credential, capability=capability, api_base=api_base, opener=opener
    )
    return [m.to_public_dict() for m in live.models]


def discover_selectable(
    credential: Optional[credentials.Credential],
    *,
    capability: str = catalog_mod.CAPABILITY_CHAT,
    required_modalities: tuple[str, ...] = (),
) -> catalog_mod.Catalog:
    """The catalog an entry point should bind its selector to."""
    live_or_seed = catalog_mod.load_catalog(credential, capability=capability)
    return catalog_mod.Catalog(
        models=catalog_mod.selectable_models(
            live_or_seed, capability, required_modalities=required_modalities
        ),
        source=live_or_seed.source,
        detail=live_or_seed.detail,
    )


def build_messages(
    *,
    prompt: str,
    system: Optional[str] = None,
    image_paths: Optional[list[str]] = None,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Build chat messages, and report the non-text modalities they upload."""
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})

    paths = list(image_paths or [])
    if not paths:
        messages.append({"role": "user", "content": prompt})
        return messages, ()

    import base64
    from pathlib import Path

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise ProviderError(f"Attachment not found: {raw_path}", kind="bad_attachment")
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        suffix = path.suffix.lower().lstrip(".") or "png"
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(
            suffix, f"image/{suffix}"
        )
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
    messages.append({"role": "user", "content": content})
    return messages, ("image",)


def guard_model_for_modalities(
    catalog: catalog_mod.Catalog,
    model_id: str,
    required_modalities: tuple[str, ...],
) -> None:
    """Second line of defence: refuse to send an attachment a model cannot read.

    The model selector is already filtered by capability, so this only fires
    when a model id was supplied out of band (a script, a stale session, or a
    hand-written ``--model``).
    """
    if not required_modalities:
        return
    model = catalog.get(model_id)
    if model is None:
        raise ProviderError(
            f"Model {model_id} is not in the OrcaRouter catalog for this capability.",
            kind="model_not_in_catalog",
        )
    missing = [m for m in required_modalities if m not in model.input_modalities]
    if missing:
        raise ProviderError(
            f"Model {model_id} does not declare {', '.join(missing)} input. "
            "Pick a model whose declared input modalities cover the attachment.",
            kind="unsupported_modality",
        )


def guard_for_entry_point(
    credential: Optional[credentials.Credential],
    model_id: str,
    required_modalities: tuple[str, ...],
    *,
    capability: str = catalog_mod.CAPABILITY_CHAT,
) -> None:
    """Validate a model id against the unfiltered catalog for this capability.

    Checking against the capability-only list (rather than the modality-filtered
    selector options) keeps the two failure modes distinct and actionable: a
    model that exists but cannot read the attachment is reported as such, while
    a model outside the catalog is reported as unknown.
    """
    if not model_id:
        return
    full = catalog_mod.load_catalog(credential, capability=capability)
    if not any(m.id == model_id for m in catalog_mod.selectable_models(full, capability)):
        raise ProviderError(
            f"Model {model_id} is not offered for the {capability} capability in the "
            "OrcaRouter catalog. Run `models` to see the compatible options.",
            kind="model_not_in_catalog",
        )
    guard_model_for_modalities(full, model_id, required_modalities)
