"""Execution management — list, get, delete, retry.

Note: n8n Public API v1.1.1 does NOT support stop or tags on executions.
Available: GET list, GET detail, DELETE, POST retry.
"""

from __future__ import annotations

from typing import Any

from cli_anything.n8n.utils.n8n_backend import (
    api_delete,
    api_get,
    api_post,
)


def list_executions(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    status: str | None = None,
    workflow_id: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    include_data: bool = False,
) -> Any:
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    if workflow_id:
        params["workflowId"] = workflow_id
    if cursor:
        params["cursor"] = cursor
    if include_data:
        params["includeData"] = "true"
    return api_get("/executions", base_url=base_url, api_key=api_key, params=params)


def get_execution(execution_id: str, *, base_url: str | None = None, api_key: str | None = None, include_data: bool = True) -> Any:
    params: dict[str, Any] = {}
    if include_data:
        params["includeData"] = "true"
    return api_get(f"/executions/{execution_id}", base_url=base_url, api_key=api_key, params=params)


def delete_execution(execution_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_delete(f"/executions/{execution_id}", base_url=base_url, api_key=api_key)


def retry_execution(execution_id: str, *, base_url: str | None = None, api_key: str | None = None) -> Any:
    return api_post(f"/executions/{execution_id}/retry", base_url=base_url, api_key=api_key)
