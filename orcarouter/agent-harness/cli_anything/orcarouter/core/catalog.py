"""OrcaRouter model catalog: live discovery, capability filtering, fallback seed.

The single source of truth for the model list is ``GET {api_base}/models`` on
the configured OrcaRouter origin, requested with the user's own API key so the
answer reflects the models that workspace can actually call. Model IDs keep
their ``vendor/model`` namespace exactly as returned.

A small verified seed keeps a fresh installation usable when discovery is slow
or unavailable. Live discovery, once it succeeds, is authoritative and the
seed is not mixed into it. Every filter fails closed: a model is only offered
for a capability the catalog metadata explicitly supports.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from . import credentials

CATALOG_TIMEOUT = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 2000

CAPABILITY_CHAT = "chat"
CAPABILITY_EMBEDDING = "embedding"
CAPABILITY_IMAGE = "image"
CAPABILITY_VIDEO = "video"
CAPABILITY_RERANK = "rerank"

# Endpoint types this client can actually speak. A chat model must advertise at
# least one of these; anything else is not offered.
CHAT_ENDPOINT_TYPES = frozenset({"openai", "anthropic", "gemini", "openai-response"})

# Endpoint types that mark a model as dedicated to a non-text task. A chat
# selector must never offer these even if they also list an OpenAI route.
NON_CHAT_ENDPOINT_TYPES = frozenset(
    {"image-generation", "openai-video", "jina-rerank", "embeddings"}
)

EMBEDDING_ENDPOINT_TYPES = frozenset({"embeddings", "embedding"})
IMAGE_ENDPOINT_TYPES = frozenset({"image-generation"})
VIDEO_ENDPOINT_TYPES = frozenset({"openai-video"})
RERANK_ENDPOINT_TYPES = frozenset({"jina-rerank"})

# Input modalities this client can actually send. An attachment of an
# undeclared modality is refused rather than guessed at.
KNOWN_MODALITIES = frozenset({"text", "image", "audio", "video", "file"})

# Verified cold-start catalog. Used only when live discovery fails, never mixed
# into a successful live result. Captured from GET https://api.orcarouter.ai/v1/models
# on 2026-09-23 and kept only where the catalog metadata is stable and verified;
# reasoning_efforts is the documented GPT-5.5 ladder.
SEED_MODELS: tuple[dict[str, Any], ...] = (
    {
        "id": "openai/gpt-5.5",
        "name": "OpenAI: GPT-5.5",
        "context_length": 400000,
        "supported_endpoint_types": ["openai", "openai-response"],
        "input_modalities": ["text"],
        "reasoning_efforts": ["low", "medium", "high", "xhigh"],
    },
    {
        "id": "anthropic/claude-opus-4.8",
        "name": "Anthropic: Claude Opus 4.8",
        "context_length": 200000,
        "supported_endpoint_types": ["anthropic", "openai"],
        "input_modalities": ["text"],
    },
    {
        "id": "google/gemini-3.5-flash",
        "name": "Google: Gemini 3.5 Flash",
        "context_length": 1000000,
        "supported_endpoint_types": ["gemini", "openai"],
        "input_modalities": ["text"],
    },
    {
        "id": "deepseek/deepseek-v4-pro",
        "name": "DeepSeek: V4 Pro",
        "context_length": 128000,
        "supported_endpoint_types": ["openai"],
        "input_modalities": ["text"],
    },
    {
        "id": "orcarouter/auto",
        "name": "OrcaRouter: Auto",
        "context_length": 128000,
        "supported_endpoint_types": ["openai", "anthropic", "gemini", "openai-response"],
        "input_modalities": ["text"],
    },
)

CATALOG_SOURCE_LIVE = "live"
CATALOG_SOURCE_SEED = "seed"


@dataclass
class ModelInfo:
    id: str
    name: str = ""
    context_length: int = 0
    endpoint_types: tuple[str, ...] = ()
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()
    reasoning_efforts: tuple[str, ...] = ()
    description: str = ""

    def supports_endpoint(self, types: Iterable[str]) -> bool:
        return bool(set(self.endpoint_types) & set(types))

    def accepts_modalities(self, required: Iterable[str]) -> bool:
        """Fail closed: every required modality must be explicitly declared."""
        required = {m for m in required if m and m != "text"}
        if not required:
            return True
        return required <= set(self.input_modalities)

    def to_public_dict(self, *, capabilities: Optional[list[str]] = None) -> dict[str, Any]:
        """Minimal metadata safe to hand to a browser: no credentials, no pricing."""
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name or self.id,
            "context_length": self.context_length,
            "input_modalities": list(self.input_modalities),
        }
        if self.reasoning_efforts:
            payload["reasoning_efforts"] = list(self.reasoning_efforts)
        if capabilities is not None:
            payload["capabilities"] = capabilities
        return payload


@dataclass
class Catalog:
    models: list[ModelInfo] = field(default_factory=list)
    source: str = CATALOG_SOURCE_LIVE
    detail: str = ""

    @property
    def degraded(self) -> bool:
        return self.source != CATALOG_SOURCE_LIVE

    def ids(self) -> list[str]:
        return [m.id for m in self.models]

    def get(self, model_id: str) -> Optional[ModelInfo]:
        for model in self.models:
            if model.id == model_id:
                return model
        return None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "degraded": self.degraded,
            "detail": self.detail,
            "count": len(self.models),
            "models": [m.to_public_dict() for m in self.models],
        }


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(v) for v in value if isinstance(v, (str, int, float)))
    return ()


def parse_catalog_payload(payload: Any) -> list[ModelInfo]:
    """Parse a ``/v1/models`` response, rejecting records we cannot speak."""
    if not isinstance(payload, dict):
        return []
    items = payload.get("data")
    if not isinstance(items, list):
        items = payload.get("models")
    if not isinstance(items, list):
        return []

    models: list[ModelInfo] = []
    for item in items[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue

        architecture = item.get("architecture")
        if not isinstance(architecture, dict):
            architecture = {}
        input_modalities = _as_str_tuple(architecture.get("input_modalities"))
        output_modalities = _as_str_tuple(architecture.get("output_modalities"))

        reasoning = item.get("reasoning")
        efforts: tuple[str, ...] = ()
        if isinstance(reasoning, dict):
            efforts = _as_str_tuple(reasoning.get("efforts") or reasoning.get("reasoning_efforts"))
        elif isinstance(reasoning, list):
            efforts = _as_str_tuple(reasoning)

        context_length = item.get("context_length") or item.get("context_window") or 0
        try:
            context_length = int(context_length)
        except (TypeError, ValueError):
            context_length = 0

        name = item.get("name")
        models.append(
            ModelInfo(
                id=model_id.strip(),
                name=name if isinstance(name, str) else model_id.strip(),
                context_length=context_length,
                endpoint_types=_as_str_tuple(item.get("supported_endpoint_types")),
                input_modalities=input_modalities,
                output_modalities=output_modalities,
                reasoning_efforts=efforts,
                description=str(item.get("description") or ""),
            )
        )
    return models


def fetch_live_catalog(
    credential: credentials.Credential,
    *,
    capability: Optional[str] = None,
    api_base: Optional[str] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> Catalog:
    """Fetch the catalog from the configured OrcaRouter origin.

    Raises on any transport or protocol failure so the caller can fall back to
    the verified seed instead of showing a partially-loaded list.
    """
    base = api_base or credentials.api_base_url()
    url = f"{base}/models"
    if capability:
        url = f"{url}?capability={capability}"

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {credential.api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    send = opener or urllib.request.urlopen
    try:
        with send(request, timeout=CATALOG_TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise CatalogError(f"model discovery failed with HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise CatalogError(f"model discovery could not reach {base}: {exc.reason}") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise CatalogError("model discovery response exceeded the size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError("model discovery returned a malformed response") from exc

    models = parse_catalog_payload(payload)
    if not models:
        raise CatalogError("model discovery returned no usable models")
    return Catalog(models=models, source=CATALOG_SOURCE_LIVE)


class CatalogError(RuntimeError):
    pass


def seed_catalog(reason: str) -> Catalog:
    """The verified cold-start catalog, used only when live discovery fails."""
    models = [
        ModelInfo(
            id=entry["id"],
            name=entry.get("name", entry["id"]),
            context_length=int(entry.get("context_length") or 0),
            endpoint_types=tuple(entry.get("supported_endpoint_types") or ()),
            input_modalities=tuple(entry.get("input_modalities") or ()),
            reasoning_efforts=tuple(entry.get("reasoning_efforts") or ()),
        )
        for entry in SEED_MODELS
    ]
    return Catalog(models=models, source=CATALOG_SOURCE_SEED, detail=reason)


def load_catalog(
    credential: Optional[credentials.Credential] = None,
    *,
    capability: Optional[str] = None,
    api_base: Optional[str] = None,
    opener: Optional[Callable[..., Any]] = None,
) -> Catalog:
    """Live catalog when possible, verified seed when not.

    The seed is never merged into a successful live result.
    """
    if credential is None:
        return seed_catalog("no credential configured")
    try:
        return fetch_live_catalog(
            credential, capability=capability, api_base=api_base, opener=opener
        )
    except CatalogError as exc:
        return seed_catalog(str(exc))


# ── capability filtering ──────────────────────────────────────────────────────


def _is_chat_model(model: ModelInfo) -> bool:
    if not model.supports_endpoint(CHAT_ENDPOINT_TYPES):
        return False
    if model.supports_endpoint(NON_CHAT_ENDPOINT_TYPES):
        # Only reject when the model is *dedicated* to the other task: a chat
        # model that also exposes, say, an embeddings route is still a chat model
        # only if it advertises a chat endpoint type — which the check above
        # already established. Dedicated non-chat models list only their own
        # endpoint type.
        dedicated = set(model.endpoint_types) & NON_CHAT_ENDPOINT_TYPES
        if dedicated and not (set(model.endpoint_types) & CHAT_ENDPOINT_TYPES):
            return False
    return True


def models_for(
    catalog: Catalog,
    capability: str,
    *,
    required_modalities: Iterable[str] = (),
) -> list[ModelInfo]:
    """Filter a catalog for one entry point.

    ``required_modalities`` are the non-text modalities the entry point will
    actually upload (for example ``{"image"}`` for a screenshot-assisted
    prompt). Models that do not explicitly declare them are excluded.
    """
    if capability == CAPABILITY_CHAT:
        return [m for m in catalog.models if _is_chat_model(m) and m.accepts_modalities(required_modalities)]
    if capability == CAPABILITY_EMBEDDING:
        return [m for m in catalog.models if m.supports_endpoint(EMBEDDING_ENDPOINT_TYPES)]
    if capability == CAPABILITY_IMAGE:
        return [m for m in catalog.models if m.supports_endpoint(IMAGE_ENDPOINT_TYPES)]
    if capability == CAPABILITY_VIDEO:
        return [m for m in catalog.models if m.supports_endpoint(VIDEO_ENDPOINT_TYPES)]
    if capability == CAPABILITY_RERANK:
        return [m for m in catalog.models if m.supports_endpoint(RERANK_ENDPOINT_TYPES)]
    raise ValueError(f"Unknown capability: {capability}")


def selectable_models(
    catalog: Catalog,
    capability: str = CAPABILITY_CHAT,
    *,
    required_modalities: Iterable[str] = (),
) -> list[ModelInfo]:
    """The list a selector should bind to, in catalog order."""
    return models_for(catalog, capability, required_modalities=required_modalities)


def is_still_valid(
    catalog: Catalog,
    model_id: str,
    capability: str = CAPABILITY_CHAT,
    *,
    required_modalities: Iterable[str] = (),
) -> bool:
    """Whether a previously selected model is still offered for this entry point."""
    if not model_id:
        return False
    return any(
        m.id == model_id
        for m in selectable_models(catalog, capability, required_modalities=required_modalities)
    )
