"""
core/search.py — Web search and get-contents operations.
"""

from __future__ import annotations

from typing import Any

from cli_anything.exa.utils.exa_backend import (
    build_contents_param,
    get_client,
    CATEGORY_SLUG_MAP,
)


def web_search(
    query: str,
    *,
    num_results: int = 10,
    search_type: str = "auto",
    category: str | None = None,
    include_domains: tuple[str, ...] = (),
    exclude_domains: tuple[str, ...] = (),
    start_date: str | None = None,
    end_date: str | None = None,
    location: str | None = None,
    content_mode: str = "highlights",
    freshness: str = "smart",
) -> dict[str, Any]:
    """Execute a web search via the Exa API.

    Returns the raw SearchResponse as a dict.
    """
    client = get_client()

    api_category = CATEGORY_SLUG_MAP.get(category) if category else None
    contents = build_contents_param(content_mode, freshness)

    kwargs: dict[str, Any] = {
        "num_results": num_results,
        "type": search_type,
    }
    if api_category:
        kwargs["category"] = api_category
    if include_domains:
        kwargs["include_domains"] = list(include_domains)
    if exclude_domains:
        kwargs["exclude_domains"] = list(exclude_domains)
    if start_date:
        kwargs["start_published_date"] = start_date
    if end_date:
        kwargs["end_published_date"] = end_date
    if location:
        kwargs["user_location"] = location
    if contents:
        kwargs["contents"] = contents

    response = client.search(query, **kwargs)
    return _response_to_dict(response)


def get_contents(
    urls: list[str],
    *,
    content_mode: str = "text",
    freshness: str = "smart",
) -> dict[str, Any]:
    """Fetch full page contents for one or more URLs."""
    client = get_client()

    # NOTE: exa-py's get_contents() accepts content keys (text, highlights, ...)
    # as top-level kwargs, unlike search() which wraps them in a `contents=` param.
    kwargs = build_contents_param(content_mode, freshness) or {}

    response = client.get_contents(urls, **kwargs)
    return _response_to_dict(response)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response_to_dict(response: Any) -> dict[str, Any]:
    """Convert an exa-py response object to a plain dict."""
    if hasattr(response, "__dict__"):
        raw = response.__dict__
    else:
        return {"results": []}

    results = []
    for r in raw.get("results", []):
        item: dict[str, Any] = {}
        for attr in (
            "title", "url", "id", "published_date", "author",
            "text", "highlights", "highlight_scores", "summary",
        ):
            val = getattr(r, attr, None)
            if val is not None:
                item[attr] = val
        results.append(item)

    out: dict[str, Any] = {"results": results}

    cost = getattr(response, "cost_dollars", None)
    if cost is not None:
        out["cost_dollars"] = cost

    return out
