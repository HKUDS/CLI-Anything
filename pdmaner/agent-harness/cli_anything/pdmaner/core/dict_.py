"""Data dictionary management operations."""

from .project import _uid


def get_dicts(data):
    """List all dictionaries."""
    return data.get("dicts", [])


def get_dict(data, id_or_defkey):
    """Get a single dict."""
    for d in data.get("dicts", []):
        if d.get("id") == id_or_defkey or d.get("defKey") == id_or_defkey:
            return d
    return None


def add_dict(data, defKey, defName="", sort="", intro=""):
    """Add a data dictionary."""
    d = {
        "defKey": defKey,
        "defName": defName or defKey,
        "sort": sort,
        "intro": intro,
        "id": _uid(),
        "items": [],
    }
    data.setdefault("dicts", []).append(d)
    return d


def delete_dict(data, id_or_defkey):
    """Delete a dictionary."""
    d = get_dict(data, id_or_defkey)
    if not d:
        raise ValueError(f"Dict not found: {id_or_defkey}")
    did = d["id"]
    data["dicts"] = [x for x in data.get("dicts", []) if x["id"] != did]
    return d


def add_dict_item(data, dict_id, defKey, defName="", sort="", intro="", parentKey=""):
    """Add an item to a dictionary."""
    d = get_dict(data, dict_id)
    if not d:
        raise ValueError(f"Dict not found: {dict_id}")
    item = {
        "defKey": defKey,
        "defName": defName or defKey,
        "sort": sort,
        "parentKey": parentKey,
        "intro": intro,
        "enabled": True,
        "attr1": "", "attr2": "", "attr3": "",
        "id": _uid(),
    }
    d.setdefault("items", []).append(item)
    return item


def delete_dict_item(data, dict_id, item_defkey):
    """Delete an item from a dictionary."""
    d = get_dict(data, dict_id)
    if not d:
        raise ValueError(f"Dict not found: {dict_id}")
    d["items"] = [i for i in d.get("items", [])
                  if i["defKey"] != item_defkey and i["id"] != item_defkey]
    return d
