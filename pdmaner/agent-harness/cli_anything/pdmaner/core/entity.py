"""Entity (data table) CRUD operations."""

import uuid
from .project import _uid

ENTITY_HEADERS = [
    {"refKey": "defKey", "hideInGraph": False, "freeze": True},
    {"refKey": "defName", "hideInGraph": False, "freeze": True},
    {"refKey": "primaryKey", "hideInGraph": False, "freeze": False},
    {"refKey": "notNull", "hideInGraph": True, "freeze": False},
    {"refKey": "autoIncrement", "hideInGraph": True, "freeze": False},
    {"refKey": "domain", "hideInGraph": True, "freeze": False},
    {"refKey": "type", "hideInGraph": False, "freeze": False},
    {"refKey": "len", "hideInGraph": False, "freeze": False},
    {"refKey": "scale", "hideInGraph": False, "freeze": False},
    {"refKey": "comment", "hideInGraph": True, "freeze": False},
    {"refKey": "refDict", "hideInGraph": True, "freeze": False},
    {"refKey": "defaultValue", "hideInGraph": True, "freeze": False},
    {"refKey": "hideInGraph", "hideInGraph": True, "freeze": False},
    {"refKey": "uiHint", "hideInGraph": True, "freeze": False},
    {"refKey": "extProps", "hideInGraph": True, "freeze": False},
]


def get_entities(data):
    """List all entities in the project."""
    return data.get("entities", [])


def get_entity(data, id_or_defkey):
    """Get a single entity by id or defKey."""
    entities = data.get("entities", [])
    for e in entities:
        if e.get("id") == id_or_defkey or e.get("defKey") == id_or_defkey:
            return e
    return None


def add_entity(data, defKey, defName="", comment="", entity_type="P"):
    """Add a new entity to the project."""
    entity = {
        "id": _uid(),
        "env": {"base": {"nameSpace": "", "codeRoot": ""}},
        "defKey": defKey,
        "defName": defName or defKey,
        "comment": comment,
        "properties": {},
        "sysProps": {"nameTemplate": "{defKey}[{defName}]"},
        "notes": {},
        "headers": [dict(h) for h in ENTITY_HEADERS],
        "fields": [],
        "correlations": [],
        "indexes": [],
        "type": entity_type,
    }
    data.setdefault("entities", []).append(entity)
    return entity


def update_entity(data, id_or_defkey, **kwargs):
    """Update entity metadata (defKey, defName, comment)."""
    entity = get_entity(data, id_or_defkey)
    if not entity:
        raise ValueError(f"Entity not found: {id_or_defkey}")
    for k, v in kwargs.items():
        if k in ("defKey", "defName", "comment", "type"):
            entity[k] = v
    return entity


def delete_entity(data, id_or_defkey):
    """Delete an entity and its references from diagrams."""
    entity = get_entity(data, id_or_defkey)
    if not entity:
        raise ValueError(f"Entity not found: {id_or_defkey}")
    eid = entity["id"]
    data["entities"] = [e for e in data.get("entities", []) if e["id"] != eid]
    # Remove from diagrams
    for dia in data.get("diagrams", []):
        cells = dia.get("canvasData", {}).get("cells", [])
        dia["canvasData"]["cells"] = [
            c for c in cells
            if not (c.get("shape") == "table" and c.get("originKey") == eid)
        ]
    # Remove from viewGroups
    for vg in data.get("viewGroups", []):
        vg["refEntities"] = [r for r in vg.get("refEntities", []) if r != eid]
    return entity


def add_field(data, entity_id, defKey, defName="", field_type="", domain="",
              len_="", scale="", primaryKey=False, notNull=False,
              autoIncrement=False, comment="", defaultValue="", refDict="",
              hideInGraph=False):
    """Add a field to an entity."""
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    field = {
        "id": _uid(),
        "defKey": defKey,
        "defName": defName or defKey,
        "comment": comment,
        "type": field_type,
        "len": str(len_) if len_ else "",
        "scale": str(scale) if scale else "",
        "primaryKey": primaryKey,
        "notNull": notNull,
        "autoIncrement": autoIncrement,
        "defaultValue": defaultValue,
        "hideInGraph": hideInGraph,
        "domain": domain,
        "refDict": refDict,
        "uiHint": "",
        "extProps": {},
        "notes": {},
        "baseType": "",
    }
    entity.setdefault("fields", []).append(field)
    return field


def update_field(data, entity_id, field_id, **kwargs):
    """Update a field's properties."""
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    for f in entity.get("fields", []):
        if f["id"] == field_id or f.get("defKey") == field_id:
            for k, v in kwargs.items():
                if k == "len_":
                    f["len"] = str(v) if v else ""
                elif k == "scale":
                    f["scale"] = str(v) if v else ""
                elif k == "field_type":
                    f["type"] = v
                elif k in ("defKey", "defName", "comment", "primaryKey",
                           "notNull", "autoIncrement", "defaultValue",
                           "hideInGraph", "domain", "refDict"):
                    f[k] = v
            return f
    raise ValueError(f"Field not found: {field_id}")


def delete_field(data, entity_id, field_id):
    """Delete a field from an entity."""
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    entity["fields"] = [f for f in entity.get("fields", [])
                        if f["id"] != field_id and f.get("defKey") != field_id]
    return entity


def add_index(data, entity_id, defKey, fields=None, unique=False, comment=""):
    """Add an index to an entity."""
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    index_fields = []
    if fields:
        for fdef in fields:
            match = next((ef for ef in entity.get("fields", [])
                         if ef["defKey"] == fdef or ef["id"] == fdef), None)
            if match:
                index_fields.append({
                    "fieldDefKey": match["id"],
                    "ascOrDesc": "A",
                })
    idx = {
        "defKey": defKey,
        "defName": None,
        "unique": unique,
        "comment": comment,
        "fields": index_fields,
        "id": _uid(),
    }
    entity.setdefault("indexes", []).append(idx)
    return idx


def delete_index(data, entity_id, index_defkey):
    """Delete an index from an entity."""
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    entity["indexes"] = [i for i in entity.get("indexes", [])
                         if i["defKey"] != index_defkey and i["id"] != index_defkey]
    return entity


def get_fields(data, entity_id):
    """List fields of an entity."""
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    return entity.get("fields", [])
