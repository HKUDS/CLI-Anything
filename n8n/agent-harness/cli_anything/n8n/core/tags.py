"""Tag management — CRUD."""

from __future__ import annotations

from typing import Any

from cli_anything.n8n.utils.n8n_backend import (
    api_delete,
    api_get,
    api_post,
    api_put,
)


def list_tags(*, base_url: str | None = None, api_key: str | None = None, limit: int = 50) -> Any:
    return api_get("/tags", base_url=base_url, api_key=api_key, params={"limit": limit})


def get_tag(tag_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_get(f"/tags/{tag_id}", base_url=base_url, api_key=api_key)


def create_tag(name: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_post("/tags", {"name": name}, base_url=base_url, api_key=api_key)


def update_tag(tag_id: str, name: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_put(f"/tags/{tag_id}", {"name": name}, base_url=base_url, api_key=api_key)


def delete_tag(tag_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_delete(f"/tags/{tag_id}", base_url=base_url, api_key=api_key)
