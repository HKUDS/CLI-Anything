"""View management operations."""

from .project import _uid


def get_views(data):
    """List all views in the project."""
    return data.get("views", [])


def get_view(data, id_or_defkey):
    """Get a single view by id or defKey."""
    for v in data.get("views", []):
        if v.get("id") == id_or_defkey or v.get("defKey") == id_or_defkey:
            return v
    return None


def add_view(data, defKey, defName="", comment=""):
    """Add a new view to the project."""
    view = {
        "id": _uid(),
        "env": {"base": {"nameSpace": "", "codeRoot": ""}},
        "defKey": defKey,
        "defName": defName or defKey,
        "comment": comment,
        "properties": {},
        "sysProps": {"nameTemplate": "{defKey}[{defName}]"},
        "notes": {},
        "headers": [
            {"refKey": "refEntity", "hideInGraph": True},
            {"refKey": "defKey", "hideInGraph": False, "freeze": True},
            {"refKey": "defName", "hideInGraph": False, "freeze": True},
            {"refKey": "primaryKey", "hideInGraph": False},
            {"refKey": "notNull", "hideInGraph": True},
            {"refKey": "autoIncrement", "hideInGraph": True},
            {"refKey": "domain", "hideInGraph": True},
            {"refKey": "type", "hideInGraph": False},
            {"refKey": "len", "hideInGraph": False},
            {"refKey": "scale", "hideInGraph": False},
            {"refKey": "comment", "hideInGraph": True},
            {"refKey": "refDict", "hideInGraph": True},
            {"refKey": "defaultValue", "hideInGraph": True},
            {"refKey": "hideInGraph", "hideInGraph": True},
            {"refKey": "uiHint", "hideInGraph": True},
        ],
        "fields": [],
        "refEntities": [],
        "indexes": [],
        "correlations": [],
    }
    data.setdefault("views", []).append(view)
    return view


def delete_view(data, id_or_defkey):
    """Delete a view from the project."""
    view = get_view(data, id_or_defkey)
    if not view:
        raise ValueError(f"View not found: {id_or_defkey}")
    vid = view["id"]
    data["views"] = [v for v in data.get("views", []) if v["id"] != vid]
    for vg in data.get("viewGroups", []):
        vg["refViews"] = [r for r in vg.get("refViews", []) if r != vid]
    return view


def add_view_field(data, view_id, defKey, defName="", field_type="",
                   source_entity_id=None, source_field_id=None):
    """Add a field to a view, optionally referencing a source entity field."""
    return __import__("cli_anything.pdmaner.core.entity", fromlist=["add_field"]).add_field(
        data, view_id, defKey, defName, field_type
    )
