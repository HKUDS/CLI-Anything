"""Fetch and cache the CLI-Anything registry."""

import json
import os
import time
from pathlib import Path

import requests

REGISTRY_URL = "https://hkuds.github.io/CLI-Anything/registry.json"
CACHE_DIR = Path.home() / ".cli-hub"
CACHE_FILE = CACHE_DIR / "registry_cache.json"
CACHE_TTL = 3600  # 1 hour


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_registry(force_refresh=False):
    """Fetch registry.json, using a local cache with TTL."""
    _ensure_cache_dir()

    if not force_refresh and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            if time.time() - cached.get("_cached_at", 0) < CACHE_TTL:
                return cached["data"]
        except (json.JSONDecodeError, KeyError):
            pass

    resp = requests.get(REGISTRY_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    cache_payload = {"_cached_at": time.time(), "data": data}
    CACHE_FILE.write_text(json.dumps(cache_payload, indent=2))

    return data


def get_cli(name, registry=None):
    """Look up a CLI entry by name (case-insensitive)."""
    if registry is None:
        registry = fetch_registry()
    name_lower = name.lower()
    for cli in registry["clis"]:
        if cli["name"].lower() == name_lower:
            return cli
    return None


def search_clis(query, registry=None):
    """Search CLIs by name, description, or category."""
    if registry is None:
        registry = fetch_registry()
    query_lower = query.lower()
    results = []
    for cli in registry["clis"]:
        if (query_lower in cli["name"].lower()
                or query_lower in cli["description"].lower()
                or query_lower in cli.get("category", "").lower()
                or query_lower in cli.get("display_name", "").lower()):
            results.append(cli)
    return results


def list_categories(registry=None):
    """Return sorted list of unique categories."""
    if registry is None:
        registry = fetch_registry()
    return sorted(set(cli.get("category", "uncategorized") for cli in registry["clis"]))
