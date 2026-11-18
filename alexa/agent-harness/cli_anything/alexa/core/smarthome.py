"""Flatten Amazon's smart-home network details into a list of appliances."""

from __future__ import annotations

from typing import Any


def flatten_network(details: Any) -> list[dict[str, Any]]:
    """Walk the nested ``get_network_details`` payload and collect appliances.

    Amazon nests appliances under locations → amazonBridgeDetails → ... →
    applianceDetails. The exact nesting changes over time, so this walks the
    structure generically and keeps any dict that looks like an appliance.
    """
    found: dict[str, dict[str, Any]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "applianceId" in node and ("friendlyName" in node or "applianceTypes" in node):
                aid = node["applianceId"]
                reachable = node.get("isReachable")
                conn = node.get("connectivity")
                if reachable is None and isinstance(conn, dict):
                    reachable = conn.get("value") == "OK"
                found[aid] = {
                    "name": node.get("friendlyName") or aid,
                    "appliance_id": aid,
                    "entity_id": node.get("entityId") or "",
                    "types": list(node.get("applianceTypes") or []),
                    "manufacturer": node.get("manufacturerName") or "",
                    "reachable": reachable,
                }
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(details)
    return sorted(found.values(), key=lambda a: a["name"].lower())
