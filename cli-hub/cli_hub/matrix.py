"""Fetch, cache, and query curated CLI workflow matrices."""

import json
import time
from pathlib import Path

import requests

MATRIX_REGISTRY_URL = "https://hkuds.github.io/CLI-Anything/matrix_registry.json"
MATRIX_CACHE_FILE = Path.home() / ".cli-hub" / "matrix_registry_cache.json"
CACHE_TTL = 3600  # 1 hour


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


def search_matrices(query, force_refresh=False):
    """Search matrices by name, display name, description, or category."""
    query_lower = query.lower()
    results = []
    for matrix_item in fetch_all_matrices(force_refresh):
        haystack_values = [
            matrix_item["name"],
            matrix_item.get("display_name", ""),
            matrix_item.get("description", ""),
            matrix_item.get("category", ""),
            matrix_item.get("matrix_id", ""),
        ]
        if any(query_lower in value.lower() for value in haystack_values):
            results.append(matrix_item)
    return results
