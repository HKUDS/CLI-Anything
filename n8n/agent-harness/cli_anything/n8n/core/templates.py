"""n8n.io template search and fetch — uses the public n8n.io API (no auth needed)."""

from __future__ import annotations

from typing import Any

import requests

TEMPLATES_API = "https://api.n8n.io/api/templates"


def search_templates(query: str, *, limit: int = 10) -> dict[str, Any]:
    """Search templates on n8n.io by keyword."""
    resp = requests.get(
        f"{TEMPLATES_API}/search",
        params={"search": query, "rows": limit},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_template(template_id: int) -> dict[str, Any]:
    """Fetch a template's full workflow JSON from n8n.io."""
    resp = requests.get(f"{TEMPLATES_API}/workflows/{template_id}", timeout=15)
    resp.raise_for_status()
    return resp.json()
