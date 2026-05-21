"""ER Diagram management operations."""

from .project import _uid


def get_diagrams(data):
    """List all diagrams."""
    return data.get("diagrams", [])


def get_diagram(data, id_or_defkey):
    """Get a single diagram."""
    for d in data.get("diagrams", []):
        if d.get("id") == id_or_defkey or d.get("defKey") == id_or_defkey:
            return d
    return None


def add_diagram(data, defKey, defName="", relationType="entity", comment=""):
    """Add a new ER diagram."""
    dia = {
        "defKey": defKey,
        "defName": defName or defKey,
        "id": _uid(),
        "comment": comment,
        "relationType": relationType,
        "canvasData": {"cells": []},
    }
    data.setdefault("diagrams", []).append(dia)
    return dia


def delete_diagram(data, id_or_defkey):
    """Delete a diagram."""
    dia = get_diagram(data, id_or_defkey)
    if not dia:
        raise ValueError(f"Diagram not found: {id_or_defkey}")
    did = dia["id"]
    data["diagrams"] = [d for d in data.get("diagrams", []) if d["id"] != did]
    for vg in data.get("viewGroups", []):
        vg["refDiagrams"] = [r for r in vg.get("refDiagrams", []) if r != did]
    return dia


def add_table_to_diagram(data, diagram_id, entity_id, x=100, y=100):
    """Add an entity table node to a diagram."""
    from .entity import get_entity
    dia = get_diagram(data, diagram_id)
    if not dia:
        raise ValueError(f"Diagram not found: {diagram_id}")
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    node = {
        "id": _uid(),
        "shape": "table",
        "position": {"x": x, "y": y},
        "originKey": entity["id"],
        "count": 0,
        "size": {"width": 240, "height": 120},
        "autoSize": True,
    }
    dia["canvasData"].setdefault("cells", []).append(node)
    return node


def add_relation_to_diagram(data, diagram_id, source_entity_id, target_entity_id,
                            source_field, target_field, relation="1:n"):
    """Add an ER relation edge between two entities."""
    dia = get_diagram(data, diagram_id)
    if not dia:
        raise ValueError(f"Diagram not found: {diagram_id}")

    cells = dia["canvasData"].get("cells", [])
    source_node = next((c for c in cells if c.get("originKey") == source_entity_id
                        and c.get("shape") == "table"), None)
    target_node = next((c for c in cells if c.get("originKey") == target_entity_id
                        and c.get("shape") == "table"), None)

    if not source_node:
        raise ValueError(f"Source entity {source_entity_id} not on diagram")
    if not target_node:
        raise ValueError(f"Target entity {target_entity_id} not on diagram")

    edge = {
        "id": _uid(),
        "relation": relation,
        "shape": "erdRelation",
        "source": {
            "cell": source_node["id"],
            "port": f"{source_field}|out",
        },
        "target": {
            "cell": target_node["id"],
            "port": f"{target_field}|in",
        },
    }
    dia["canvasData"]["cells"].append(edge)
    return edge
