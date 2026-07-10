"""Fetch, cache, and query curated CLI workflow matrices."""

import importlib.metadata
import importlib.util
import json
import os
import shutil
import time
from pathlib import Path

import requests

MATRIX_REGISTRY_URL = "https://hkuds.github.io/CLI-Anything/matrix_registry.json"
MATRIX_CACHE_FILE = Path.home() / ".cli-hub" / "matrix_registry_cache.json"
CACHE_TTL = 3600  # 1 hour

AGENT_INSTALLABLE_KINDS = {"agent-skill"}

# Provider kinds whose CLIs `matrix install` can manage via cli-hub / public registries.
INSTALLABLE_KINDS = {"harness-cli", "public-cli"}

# Harness CLI providers are named `cli-anything-<cli>`; the flat `clis[]` list uses `<cli>`.
HARNESS_PREFIX = "cli-anything-"

# Short, stable labels for provider kinds used across search / can / preflight output.
KIND_LABELS = {
    "harness-cli": "harness",
    "public-cli": "public",
    "python": "python",
    "native": "native",
    "api": "api",
    "agent-skill": "skill",
    "agent-native": "native",
    "web-search": "web",
}


def _ensure_cache_dir():
    MATRIX_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_cached_data():
    if not MATRIX_CACHE_FILE.exists():
        return None
    try:
        cached = json.loads(MATRIX_CACHE_FILE.read_text())
        return cached["data"]
    except (json.JSONDecodeError, KeyError):
        return None


def _load_local_registry():
    """Load matrix_registry.json from a source checkout when available."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "matrix_registry.json"
        if not candidate.exists():
            continue
        try:
            return json.loads(candidate.read_text())
        except json.JSONDecodeError:
            return None
    return None


def fetch_matrix_registry(force_refresh=False):
    """Fetch the matrix registry with local file caching."""
    _ensure_cache_dir()

    if not force_refresh and MATRIX_CACHE_FILE.exists():
        try:
            cached = json.loads(MATRIX_CACHE_FILE.read_text())
            if time.time() - cached.get("_cached_at", 0) < CACHE_TTL:
                return cached["data"]
        except (json.JSONDecodeError, KeyError):
            pass

    try:
        resp = requests.get(MATRIX_REGISTRY_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        cached_data = _load_cached_data()
        if cached_data is not None:
            return cached_data
        local_data = _load_local_registry()
        if local_data is not None:
            return local_data
        raise

    MATRIX_CACHE_FILE.write_text(json.dumps({"_cached_at": time.time(), "data": data}, indent=2))
    return data


def fetch_all_matrices(force_refresh=False):
    """Return all matrix entries."""
    return fetch_matrix_registry(force_refresh).get("matrices", [])


def get_matrix(name, force_refresh=False):
    """Look up a matrix entry by name (case-insensitive)."""
    name_lower = name.lower()
    for matrix_item in fetch_all_matrices(force_refresh):
        if matrix_item["name"].lower() == name_lower:
            return matrix_item
    return None


def _string_values(value):
    """Yield lowercase strings from nested matrix registry values."""
    if isinstance(value, str):
        yield value.lower()
    elif isinstance(value, dict):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_values(child)


def search_matrices(query, force_refresh=False):
    """Search matrices by name, capabilities, providers, recipes, or gaps."""
    query_lower = query.lower()
    results = []
    for matrix_item in fetch_all_matrices(force_refresh):
        haystack_values = {
            "name": matrix_item.get("name", ""),
            "display_name": matrix_item.get("display_name", ""),
            "description": matrix_item.get("description", ""),
            "category": matrix_item.get("category", ""),
            "matrix_id": matrix_item.get("matrix_id", ""),
            "capabilities": matrix_item.get("capabilities", []),
            "recipes": matrix_item.get("recipes", []),
            "known_gaps": matrix_item.get("known_gaps", []),
            "clis": matrix_item.get("clis", []),
        }
        if any(query_lower in value for value in _string_values(haystack_values)):
            results.append(matrix_item)
    return results


def _as_list(value):
    """Normalize registry requirement fields to lists."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _package_available(name):
    try:
        if importlib.util.find_spec(name) is not None:
            return True
    except Exception:
        pass
    try:
        normalized = name.replace("-", "_")
        if normalized != name and importlib.util.find_spec(normalized) is not None:
            return True
    except Exception:
        pass
    try:
        importlib.metadata.version(name)
        return True
    except Exception:
        pass
    return False


def check_provider_requirements(provider):
    """Check whether a provider's declared requirements are available locally."""
    kind = provider.get("kind", "")
    if kind in AGENT_INSTALLABLE_KINDS:
        return {
            "name": provider.get("name", ""),
            "kind": kind,
            "available": False,
            "agent_installable": True,
            "status": "agent-installable",
            "offline": bool(provider.get("offline")),
            "cost_tier": provider.get("cost_tier", "unknown"),
            "quality_tier": provider.get("quality_tier", "unknown"),
            "requires": provider.get("requires") or {},
            "present": {"env": [], "binary": [], "package": []},
            "missing": {"env": [], "binary": [], "package": []},
            "notes": provider.get("notes", ""),
            "install_hint": provider.get("install_hint"),
        }

    requires = provider.get("requires") or {}
    env_names = _as_list(requires.get("env"))
    binary_names = _as_list(requires.get("binary"))
    package_names = _as_list(requires.get("package"))

    present = {
        "env": [name for name in env_names if os.environ.get(name)],
        "binary": [name for name in binary_names if shutil.which(name)],
        "package": [name for name in package_names if _package_available(name)],
    }
    missing = {
        "env": [name for name in env_names if name not in present["env"]],
        "binary": [name for name in binary_names if name not in present["binary"]],
        "package": [name for name in package_names if name not in present["package"]],
    }
    available = not any(missing.values())

    return {
        "name": provider.get("name", ""),
        "kind": kind,
        "available": available,
        "agent_installable": False,
        "status": "available" if available else "missing",
        "offline": bool(provider.get("offline")),
        "cost_tier": provider.get("cost_tier", "unknown"),
        "quality_tier": provider.get("quality_tier", "unknown"),
        "requires": requires,
        "present": present,
        "missing": missing,
        "notes": provider.get("notes", ""),
        "install_hint": provider.get("install_hint"),
    }


def preflight_matrix(matrix_item, capability_id=None, offline=False, capability_ids=None):
    """Return provider availability for a matrix, optionally filtered.

    ``capability_id`` filters to a single capability; ``capability_ids`` (a set or
    list, used by ``--recipe``) filters to a named subset. The two compose.
    """
    id_filter = set(capability_ids) if capability_ids is not None else None
    capability_results = []

    for capability in matrix_item.get("capabilities", []):
        if capability_id and capability.get("id") != capability_id:
            continue
        if id_filter is not None and capability.get("id") not in id_filter:
            continue

        provider_results = [
            check_provider_requirements(provider)
            for provider in capability.get("providers", [])
            if not offline or provider.get("offline")
        ]
        capability_results.append({
            "id": capability.get("id", ""),
            "intent": capability.get("intent", ""),
            "provider_count": len(provider_results),
            "available_count": sum(1 for provider in provider_results if provider["available"]),
            "agent_installable_count": sum(
                1 for provider in provider_results
                if provider.get("agent_installable")
            ),
            "providers": provider_results,
        })

    summary = {
        "capabilities": len(capability_results),
        "with_available_provider": sum(1 for cap in capability_results if cap["available_count"] > 0),
        "with_agent_installable_provider": sum(
            1 for cap in capability_results
            if cap["available_count"] == 0 and cap["agent_installable_count"] > 0
        ),
        "providers": sum(cap["provider_count"] for cap in capability_results),
        "available_providers": sum(cap["available_count"] for cap in capability_results),
        "agent_installable_providers": sum(
            cap["agent_installable_count"] for cap in capability_results
        ),
    }
    # A capability is "covered" when it has at least one available provider or an
    # agent-installable fallback; everything else is a hard gap (drives exit code 3).
    summary["covered"] = sum(
        1 for cap in capability_results
        if cap["available_count"] > 0 or cap["agent_installable_count"] > 0
    )
    summary["gaps"] = summary["capabilities"] - summary["covered"]

    return {
        "matrix": {
            "name": matrix_item.get("name", ""),
            "display_name": matrix_item.get("display_name", matrix_item.get("name", "")),
            "schema_version": matrix_item.get("schema_version", "1"),
        },
        "capability_filter": capability_id,
        "offline": offline,
        "summary": summary,
        "capabilities": capability_results,
    }


# ── Provider ↔ CLI resolution and install scoping (F2.2) ──────────────────────


def provider_cli_name(provider, cli_names):
    """Resolve a provider to the ``clis[]`` member that ``matrix install`` manages.

    Returns the registry CLI name, or ``None`` when the provider is not installable
    through cli-hub (Python libs, native binaries, cloud APIs, agent skills, or
    third-party public CLIs that live outside the matrix's ``clis[]`` list).
    """
    if provider.get("kind") not in INSTALLABLE_KINDS:
        return None
    cli_set = set(cli_names)
    explicit = provider.get("cli")  # forward-compatible with schema v2.1 (F4.2)
    if explicit and explicit in cli_set:
        return explicit
    name = provider.get("name", "")
    if name in cli_set:
        return name
    if name.startswith(HARNESS_PREFIX):
        stripped = name[len(HARNESS_PREFIX):]
        if stripped in cli_set:
            return stripped
    return None


def provider_install_hint(provider, cli_names):
    """Return a human-readable install command for a provider, or ``None``.

    Prefers the registry's explicit ``install_hint`` (F2.4); otherwise derives
    ``cli-hub install <cli>`` for providers that map into the matrix's ``clis[]``.
    """
    hint = provider.get("install_hint")
    if hint:
        return hint
    cli = provider_cli_name(provider, cli_names)
    if cli:
        return f"cli-hub install {cli}"
    return None


def get_recipe(matrix_item, recipe_id):
    """Look up a recipe entry by id (case-insensitive)."""
    recipe_lower = recipe_id.lower()
    for recipe in matrix_item.get("recipes", []):
        if recipe.get("id", "").lower() == recipe_lower:
            return recipe
    return None


def _scope_clis_for_capabilities(matrix_item, capabilities):
    """Return the ``clis[]`` members backing the given capabilities, in registry order."""
    cli_names = matrix_item.get("clis", [])
    wanted = set()
    for capability in capabilities:
        for provider in capability.get("providers", []):
            cli = provider_cli_name(provider, cli_names)
            if cli:
                wanted.add(cli)
    return [name for name in cli_names if name in wanted]


def resolve_install_scope(matrix_item, capability=None, recipe=None, only=None):
    """Resolve install scope flags to a concrete subset of the matrix's ``clis[]``.

    Returns a dict with ``cli_names`` (ordered subset), ``scope`` (type/value),
    ``capabilities`` (capability ids in scope, when applicable), and ``error``
    (a usage message when the selectors are invalid or mutually exclusive).
    """
    cli_names = matrix_item.get("clis", [])
    selectors = [(kind, value) for kind, value in
                 (("capability", capability), ("recipe", recipe), ("only", only)) if value]

    if len(selectors) > 1:
        return {"error": "Use only one of --capability, --recipe, or --only.",
                "scope": {"type": "invalid"}, "cli_names": [], "capabilities": []}

    if not selectors:
        return {"error": None, "scope": {"type": "all"}, "cli_names": list(cli_names),
                "capabilities": [c.get("id") for c in matrix_item.get("capabilities", [])]}

    sel_type, sel_value = selectors[0]

    if sel_type == "only":
        requested = [name.strip() for name in only.split(",") if name.strip()]
        unknown = [name for name in requested if name not in set(cli_names)]
        if unknown:
            return {"error": (f"Not in matrix '{matrix_item.get('name')}' clis[]: "
                              f"{', '.join(unknown)}. Valid: {', '.join(cli_names) or '(none)'}"),
                    "scope": {"type": "only"}, "cli_names": [], "capabilities": []}
        chosen = [name for name in cli_names if name in set(requested)]
        return {"error": None, "scope": {"type": "only", "value": requested},
                "cli_names": chosen, "capabilities": []}

    if sel_type == "capability":
        capability_item = next(
            (c for c in matrix_item.get("capabilities", []) if c.get("id") == capability), None)
        if capability_item is None:
            valid = ", ".join(c.get("id", "") for c in matrix_item.get("capabilities", []))
            return {"error": (f"Capability '{capability}' not found in "
                              f"'{matrix_item.get('name')}'. Valid: {valid or '(none)'}"),
                    "scope": {"type": "capability"}, "cli_names": [], "capabilities": []}
        return {"error": None, "scope": {"type": "capability", "value": capability},
                "cli_names": _scope_clis_for_capabilities(matrix_item, [capability_item]),
                "capabilities": [capability]}

    # sel_type == "recipe"
    recipe_item = get_recipe(matrix_item, recipe)
    if recipe_item is None:
        valid = ", ".join(r.get("id", "") for r in matrix_item.get("recipes", []))
        return {"error": (f"Recipe '{recipe}' not found in '{matrix_item.get('name')}'. "
                          f"Valid: {valid or '(none)'}"),
                "scope": {"type": "recipe"}, "cli_names": [], "capabilities": []}
    used = recipe_item.get("capabilities_used", [])
    used_set = set(used)
    capabilities = [c for c in matrix_item.get("capabilities", []) if c.get("id") in used_set]
    return {"error": None, "scope": {"type": "recipe", "value": recipe},
            "cli_names": _scope_clis_for_capabilities(matrix_item, capabilities),
            "capabilities": list(used)}


def unmanaged_providers(matrix_item, capabilities=None):
    """Group providers that ``matrix install`` does NOT install, by category.

    Used by ``install --dry-run`` to show what still needs manual setup
    (Python libs, native binaries, cloud APIs, agent skills, and third-party
    public CLIs outside ``clis[]``).
    """
    cli_names = matrix_item.get("clis", [])
    caps = capabilities if capabilities is not None else matrix_item.get("capabilities", [])
    buckets = {"python": [], "native": [], "api": [], "agent-skill": [], "public-unmanaged": []}
    seen = set()
    for capability in caps:
        for provider in capability.get("providers", []):
            kind = provider.get("kind")
            name = provider.get("name", "")
            key = (kind, name)
            if key in seen:
                continue
            if kind in INSTALLABLE_KINDS:
                if kind == "public-cli" and provider_cli_name(provider, cli_names) is None:
                    buckets["public-unmanaged"].append(name)
                    seen.add(key)
                continue
            if kind in buckets:
                buckets[kind].append(name)
                seen.add(key)
    return {category: names for category, names in buckets.items() if names}


# ── Capability-level search (F1.1 / F1.4) ─────────────────────────────────────


def providers_summary(capability, limit=4):
    """Render a compact 'name (kind) · …' summary of a capability's providers."""
    providers = capability.get("providers", [])
    parts = [
        f"{p.get('name', '')} ({KIND_LABELS.get(p.get('kind'), p.get('kind', '?'))})"
        for p in providers[:limit]
    ]
    summary = " · ".join(parts)
    extra = len(providers) - limit
    if extra > 0:
        summary += f" · +{extra} more"
    return summary


def _capability_match_field(capability, query_lower):
    """Return which field of a capability matched the query, or ``None``."""
    if query_lower in capability.get("id", "").lower():
        return "id"
    if query_lower in capability.get("intent", "").lower():
        return "intent"
    if any(query_lower in hint.lower() for hint in capability.get("skill_search_hints", [])):
        return "hint"
    for provider in capability.get("providers", []):
        if query_lower in provider.get("name", "").lower():
            return "provider"
    return None


def capability_matches(matrix_item, query_lower):
    """Return per-capability match attribution for a single matrix (F1.1 matched_in)."""
    matches = []
    for capability in matrix_item.get("capabilities", []):
        field = _capability_match_field(capability, query_lower)
        if not field:
            continue
        matches.append({
            "matrix": matrix_item.get("name", ""),
            "matrix_id": matrix_item.get("matrix_id", ""),
            "capability_id": capability.get("id", ""),
            "intent": capability.get("intent", ""),
            "match_field": field,
            "providers_summary": providers_summary(capability),
        })
    return matches


def search_capabilities(query, force_refresh=False):
    """Search every matrix at capability granularity (powers ``cli-hub can``).

    Each hit carries local provider availability so callers can show what is
    usable on this machine right now.
    """
    query_lower = query.lower()
    hits = []
    for matrix_item in fetch_all_matrices(force_refresh):
        for capability in matrix_item.get("capabilities", []):
            field = _capability_match_field(capability, query_lower)
            if not field:
                continue
            hits.append({
                "matrix": matrix_item.get("name", ""),
                "matrix_id": matrix_item.get("matrix_id", ""),
                "capability_id": capability.get("id", ""),
                "intent": capability.get("intent", ""),
                "match_field": field,
                "providers": [
                    check_provider_requirements(provider)
                    for provider in capability.get("providers", [])
                ],
            })
    return hits


def all_recipes(query=None, force_refresh=False):
    """Return recipes across all matrices, optionally filtered by a query (F1.4)."""
    query_lower = query.lower() if query else None
    out = []
    for matrix_item in fetch_all_matrices(force_refresh):
        for recipe in matrix_item.get("recipes", []):
            if query_lower:
                haystack = " ".join([
                    recipe.get("id", ""),
                    recipe.get("description", ""),
                    " ".join(recipe.get("capabilities_used", [])),
                ]).lower()
                if query_lower not in haystack:
                    continue
            out.append({
                "matrix": matrix_item.get("name", ""),
                "matrix_id": matrix_item.get("matrix_id", ""),
                "id": recipe.get("id", ""),
                "description": recipe.get("description", ""),
                "capabilities_used": recipe.get("capabilities_used", []),
            })
    return out
