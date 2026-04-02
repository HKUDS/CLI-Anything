"""Workflow auto-fixer — detect and repair common workflow issues.

Inspired by n8n-mcp's WorkflowAutoFixer. Operates purely on workflow JSON.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class Fix:
    """A single fix that can be applied to a workflow."""

    fix_type: str
    description: str
    confidence: str  # HIGH, MEDIUM, LOW
    node_name: str | None = None


def autofix(workflow: dict[str, Any], *, apply: bool = False) -> tuple[dict[str, Any], list[Fix]]:
    """Detect and optionally fix common workflow issues.

    Returns (possibly modified workflow, list of fixes detected).
    """
    fixes: list[Fix] = []
    nodes = workflow.get("nodes") or []
    connections = workflow.get("connections") or {}

    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(connections, dict):
        connections = {}

    node_names = {n.get("name") for n in nodes if isinstance(n, dict)}

    # 1. Expression format: missing = prefix
    for node in nodes:
        if not isinstance(node, dict):
            continue
        params = node.get("parameters")
        if not isinstance(params, dict):
            continue
        for key, val in _iter_params(params):
            if isinstance(val, str) and "{{" in val and not val.startswith("="):
                fixes.append(Fix(
                    "expression-format",
                    f"Expression missing '=' prefix in {node.get('name', '?')}.{key}: {val[:50]}",
                    "HIGH", node.get("name"),
                ))
                if apply:
                    _set_nested(params, key, f"={val}")

    # 2. Webhook missing path
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type", "").lower()
        if "webhook" in node_type:
            params = node.get("parameters") or {}
            if not params.get("path"):
                new_path = uuid.uuid4().hex[:12]
                fixes.append(Fix(
                    "webhook-missing-path",
                    f"Webhook node '{node.get('name', '?')}' has no path, generating: {new_path}",
                    "HIGH", node.get("name"),
                ))
                if apply:
                    node.setdefault("parameters", {})["path"] = new_path
                    node["webhookId"] = str(uuid.uuid4())

    # 3. Connections to non-existent nodes
    nodes_to_check = list(connections.keys())
    for source_name in nodes_to_check:
        if source_name not in node_names:
            fixes.append(Fix("connection-orphan-source", f"Connection from non-existent node: '{source_name}'", "HIGH"))
            if apply:
                del connections[source_name]
            continue
        conns = connections[source_name]
        if isinstance(conns, dict):
            for conn_type, outputs in conns.items():
                if isinstance(outputs, list):
                    for output_list in outputs:
                        if isinstance(output_list, list):
                            for i, target in enumerate(output_list):
                                if isinstance(target, dict):
                                    target_name = target.get("node", "")
                                    if target_name and target_name not in node_names:
                                        fixes.append(Fix("connection-orphan-target", f"Connection to non-existent node: '{target_name}' (from '{source_name}')", "HIGH"))
                                        if apply:
                                            output_list[i] = None
                            if apply:
                                output_list[:] = [t for t in output_list if t is not None]

    # 4. Duplicate node names
    seen: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = node.get("name", "")
        if name in seen:
            new_name = f"{name}_{seen[name]}"
            fixes.append(Fix("duplicate-node-name", f"Duplicate name '{name}' renamed to '{new_name}'", "MEDIUM", name))
            if apply:
                if name in connections:
                    connections[new_name] = connections.pop(name)
                for src_conns in connections.values():
                    if isinstance(src_conns, dict):
                        for outputs in src_conns.values():
                            if isinstance(outputs, list):
                                for output_list in outputs:
                                    if isinstance(output_list, list):
                                        for target in output_list:
                                            if isinstance(target, dict) and target.get("node") == name:
                                                target["node"] = new_name
                node["name"] = new_name
            seen[name] += 1
        else:
            seen[name] = 1

    # 5. Connection type corrections (numeric keys like "0" -> "main")
    for source_name, conns in connections.items():
        if isinstance(conns, dict):
            bad_keys = [k for k in conns if k.isdigit()]
            for bk in bad_keys:
                fixes.append(Fix("connection-numeric-key", f"Connection type '{bk}' should be 'main' (from '{source_name}')", "HIGH"))
                if apply:
                    moved = conns.pop(bk)
                    if "main" in conns:
                        conns["main"].extend(moved)  # Merge, don't overwrite
                    else:
                        conns["main"] = moved

    # 6. Error output without error connections
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("onError") == "continueErrorOutput":
            has_error_conn = False
            name = node.get("name", "")
            conns = connections.get(name, {})
            if isinstance(conns, dict):
                for conn_type, outputs in conns.items():
                    if isinstance(outputs, list) and len(outputs) > 1:
                        has_error_conn = True
            if not has_error_conn:
                fixes.append(Fix("error-output-unused", f"Node '{name}' has continueErrorOutput but no error branch", "MEDIUM", name))
                if apply:
                    del node["onError"]

    return workflow, fixes


def _iter_params(params: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Recursively iterate parameter key-value pairs.

    Returns (dotted_key, string_value) tuples. Keys with list indices use
    bracket notation: 'assignments[0].value'.
    Note: _set_nested handles these bracket keys correctly.
    """
    result = []
    for k, v in params.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.extend(_iter_params(v, full_key))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    result.extend(_iter_params(item, f"{full_key}[{i}]"))
                elif isinstance(item, str):
                    result.append((f"{full_key}[{i}]", item))
        elif isinstance(v, str):
            result.append((full_key, v))
    return result


# Regex to split keys like "assignments[0].value" into parts
_KEY_PART_RE = re.compile(r'([^\[.\]]+)|\[(\d+)\]')


def _set_nested(d: dict[str, Any], key: str, value: Any) -> None:
    """Set a nested value using dot/bracket notation.

    Handles keys like 'a.b', 'a[0].b', 'a.b[1].c' correctly,
    navigating into both dicts and lists.
    """
    parts: list[str | int] = []
    for match in _KEY_PART_RE.finditer(key):
        if match.group(1) is not None:
            parts.append(match.group(1))
        elif match.group(2) is not None:
            parts.append(int(match.group(2)))

    current: Any = d
    for part in parts[:-1]:
        if isinstance(part, int):
            if isinstance(current, list) and 0 <= part < len(current):
                current = current[part]
            else:
                return  # Index out of range — skip safely
        else:
            if isinstance(current, dict):
                current = current.setdefault(part, {})
            else:
                return  # Type mismatch — skip safely

    last = parts[-1]
    if isinstance(last, int):
        if isinstance(current, list) and 0 <= last < len(current):
            current[last] = value
    elif isinstance(current, dict):
        current[last] = value
