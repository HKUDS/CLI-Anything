"""Fetch, cache, and merge the CLI-Anything registries (harness + public)."""

import json
import time
from pathlib import Path

import requests

REGISTRY_URL = "https://hkuds.github.io/CLI-Anything/registry.json"
PUBLIC_REGISTRY_URL = "https://hkuds.github.io/CLI-Anything/public_registry.json"
CACHE_DIR = Path.home() / ".cli-hub"
CACHE_FILE = CACHE_DIR / "registry_cache.json"
PUBLIC_CACHE_FILE = CACHE_DIR / "public_registry_cache.json"
CACHE_TTL = 3600  # 1 hour


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_cached_data(cache_file):
    """Return cached registry data if the cache file is valid."""
    if not cache_file.exists():
        return None
    try:
        cached = json.loads(cache_file.read_text())
        return cached["data"]
    except (json.JSONDecodeError, KeyError):
        return None


def _fetch_json(url, cache_file, force_refresh=False):
    """Fetch a JSON URL with local file caching."""
    _ensure_cache_dir()

    if not force_refresh and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if time.time() - cached.get("_cached_at", 0) < CACHE_TTL:
                return cached["data"]
        except (json.JSONDecodeError, KeyError):
            pass

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        cached_data = _load_cached_data(cache_file)
        if cached_data is not None:
            return cached_data
        raise

    cache_payload = {"_cached_at": time.time(), "data": data}
    cache_file.write_text(json.dumps(cache_payload, indent=2))

    return data


def fetch_registry(force_refresh=False):
    """Fetch the harness registry.json."""
    return _fetch_json(REGISTRY_URL, CACHE_FILE, force_refresh)


def fetch_public_registry(force_refresh=False):
    """Fetch the public CLI registry. Returns None on failure."""
    try:
        return _fetch_json(PUBLIC_REGISTRY_URL, PUBLIC_CACHE_FILE, force_refresh)
    except Exception:
        return None


def fetch_all_clis(force_refresh=False):
    """Fetch and merge both registries. Each CLI is tagged with _source."""
    registry = fetch_registry(force_refresh)
    all_clis = []

    for cli in registry["clis"]:
        entry = dict(cli)
        entry["_source"] = "harness"
        all_clis.append(entry)

    public = fetch_public_registry(force_refresh)
    if public:
        for cli in public["clis"]:
            entry = dict(cli)
            entry["_source"] = "public"
            all_clis.append(entry)

    return all_clis


def get_cli(name, force_refresh=False):
    """Look up a CLI entry by name (case-insensitive) across both registries."""
    name_lower = name.lower()
    for cli in fetch_all_clis(force_refresh):
        if cli["name"].lower() == name_lower:
            return cli
    return None


def search_clis(query, force_refresh=False):
    """Search CLIs by name, description, or category across both registries."""
    query_lower = query.lower()
    results = []
    for cli in fetch_all_clis(force_refresh):
        if (query_lower in cli["name"].lower()
                or query_lower in cli["description"].lower()
                or query_lower in cli.get("category", "").lower()
                or query_lower in cli.get("display_name", "").lower()):
            results.append(cli)
    return results


def list_categories(force_refresh=False):
    """Return sorted list of unique categories across both registries."""
    return sorted(set(cli.get("category", "uncategorized") for cli in fetch_all_clis(force_refresh)))
