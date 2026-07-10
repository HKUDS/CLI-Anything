"""Obsidian search operations — query and simple text search."""

from cli_anything.obsidian.utils.obsidian_backend import api_post, api_post_raw

# Content types accepted by Obsidian Local REST API on POST /search/.
# See https://coddingtonbear.github.io/obsidian-local-rest-api/#/Search
SEARCH_CONTENT_TYPES = {
    "dql": "application/vnd.olrapi.dataview.dql+txt",
    "jsonlogic": "application/vnd.olrapi.jsonlogic+json",
}


def search_query(base_url: str, api_key: str, query: str,
                 query_type: str = "dql") -> dict:
    """Search vault using Obsidian's structured search engine.

    Obsidian's ``/search/`` endpoint expects a vendor-specific Content-Type and
    a raw body (not a JSON-wrapped ``{"query": ...}`` payload). Sending
    ``application/json`` results in ``40012 Unknown or invalid Content-Type``.

    Args:
        base_url: API base URL.
        api_key: Bearer token.
        query: Search query body. For ``dql``, raw Dataview DQL text. For
            ``jsonlogic``, a JsonLogic expression as a JSON string.
        query_type: ``"dql"`` (default) or ``"jsonlogic"``.

    Returns:
        Search results from Obsidian.

    Raises:
        ValueError: If ``query_type`` is not a supported value.
    """
    try:
        content_type = SEARCH_CONTENT_TYPES[query_type]
    except KeyError as e:
        valid = ", ".join(sorted(SEARCH_CONTENT_TYPES))
        raise ValueError(
            f"Unsupported search query_type {query_type!r}. Valid: {valid}."
        ) from e
    return api_post_raw(base_url, "/search/", api_key,
                        body=query, content_type=content_type)


def search_simple(base_url: str, api_key: str, query: str,
                  context_length: int = 100) -> dict:
    """Simple text search across the vault.

    Args:
        base_url: API base URL.
        api_key: Bearer token.
        query: Plain text to search for.
        context_length: Number of context characters around matches.

    Returns:
        List of search results with filename and matches.
    """
    return api_post(base_url, "/search/simple/", api_key,
                    params={"query": query, "contextLength": context_length})
