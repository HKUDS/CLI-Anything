"""System-level queries: version, identity, liveness."""

from __future__ import annotations

from typing import Any, Dict, Optional

from cli_anything.opencti.utils.opencti_backend import (
    graphql_request,
    health_check,
)

ABOUT_QUERY = "query { about { version } }"
ME_QUERY = "query { me { name user_email firstname lastname } }"


def about(**kw) -> Dict[str, Any]:
    return graphql_request(ABOUT_QUERY, **kw)["about"]


def me(**kw) -> Dict[str, Any]:
    return graphql_request(ME_QUERY, **kw)["me"]


def status(base_url: str, **kw) -> Dict[str, Any]:
    data = {}
    data["version"] = graphql_request(ABOUT_QUERY, base_url=base_url, **kw)["about"]["version"]
    try:
        me_data = graphql_request(ME_QUERY, base_url=base_url, api_key=kw.get("api_key"))
        data["authenticated_as"] = me_data["me"].get("user_email")
    except Exception:
        data["authenticated_as"] = None
    data["reachable"] = health_check(base_url=base_url)
    return data
