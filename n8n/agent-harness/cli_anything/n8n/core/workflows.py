"""Workflow management — CRUD, activate/deactivate, tags, versions."""

from __future__ import annotations

from typing import Any

from cli_anything.n8n.utils.n8n_backend import (
    api_delete,
    api_get,
    api_post,
    api_put,
)


def list_workflows(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    active: bool | None = None,
    tags: str | None = None,
    name: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> Any:
    params: dict[str, Any] = {"limit": limit}
    if active is not None:
        params["active"] = str(active).lower()
    if tags:
        params["tags"] = tags
    if name:
        params["name"] = name
    if cursor:
        params["cursor"] = cursor
    return api_get("/workflows", base_url=base_url, api_key=api_key, params=params)


def get_workflow(workflow_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_get(f"/workflows/{workflow_id}", base_url=base_url, api_key=api_key)


def create_workflow(data: dict[str, Any], *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_post("/workflows", data, base_url=base_url, api_key=api_key)


def update_workflow(workflow_id: str, data: dict[str, Any], *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_put(f"/workflows/{workflow_id}", data, base_url=base_url, api_key=api_key)


def delete_workflow(workflow_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_delete(f"/workflows/{workflow_id}", base_url=base_url, api_key=api_key)


def activate_workflow(workflow_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_post(f"/workflows/{workflow_id}/activate", base_url=base_url, api_key=api_key)


def deactivate_workflow(workflow_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_post(f"/workflows/{workflow_id}/deactivate", base_url=base_url, api_key=api_key)


def get_workflow_tags(workflow_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_get(f"/workflows/{workflow_id}/tags", base_url=base_url, api_key=api_key)


def update_workflow_tags(workflow_id: str, tag_ids: list[dict[str, str]], *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_put(f"/workflows/{workflow_id}/tags", tag_ids, base_url=base_url, api_key=api_key)


def transfer_workflow(workflow_id: str, project_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_put(f"/workflows/{workflow_id}/transfer", {"destinationProjectId": project_id}, base_url=base_url, api_key=api_key)
