"""Variable management — CRUD."""

from __future__ import annotations

from typing import Any

from cli_anything.n8n.utils.n8n_backend import (
    api_delete,
    api_get,
    api_post,
    api_put,
)


def list_variables(*, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_get("/variables", base_url=base_url, api_key=api_key)


def create_variable(key: str, value: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_post("/variables", {"key": key, "value": value}, base_url=base_url, api_key=api_key)


def update_variable(variable_id: str, key: str, value: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_put(f"/variables/{variable_id}", {"key": key, "value": value}, base_url=base_url, api_key=api_key)


def delete_variable(variable_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_delete(f"/variables/{variable_id}", base_url=base_url, api_key=api_key)
