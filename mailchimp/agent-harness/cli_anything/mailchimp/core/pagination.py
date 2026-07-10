"""Generic count/offset paginator for the Mailchimp API."""

from __future__ import annotations

from typing import Generator

_PAGE_SIZE = 1000


def paginate(
    client,
    path: str,
    result_key: str,
    params: dict | None = None,
    page_size: int = _PAGE_SIZE,
) -> Generator[dict, None, None]:
    """Yield all items from a paginated Mailchimp endpoint.

    Args:
        client: MailchimpClient instance.
        path: API path, e.g. "/lists".
        result_key: Key inside the response that holds the item array.
        params: Extra query params (count/offset will be added automatically).
        page_size: Items per page.
    """
    params = dict(params or {})
    params["count"] = page_size
    offset = 0
    total: int | None = None

    while True:
        params["offset"] = offset
        data = client.get(path, params=params)
        items: list = data.get(result_key, [])

        if total is None:
            total = data.get("total_items", None)

        yield from items

        offset += len(items)
        # Stop when we have fetched all items or got an empty page
        if not items or (total is not None and offset >= total):
            break


def collect(
    client,
    path: str,
    result_key: str,
    params: dict | None = None,
    page_size: int = _PAGE_SIZE,
) -> tuple[list[dict], int]:
    """Return (items, total_items) — fetches a single page by default.

    When the caller passes explicit count/offset in params those are respected;
    otherwise a single page of page_size is fetched.
    """
    params = dict(params or {})
    if "count" not in params:
        params["count"] = page_size
    if "offset" not in params:
        params["offset"] = 0

    data = client.get(path, params=params)
    items = data.get(result_key, [])
    total = data.get("total_items", len(items))
    return items, total
