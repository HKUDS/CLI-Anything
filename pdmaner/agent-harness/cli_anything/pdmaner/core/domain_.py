"""Domain (data type domain) and data type mapping operations."""

from .project import _uid


def get_domains(data):
    """List all domains."""
    return data.get("domains", [])


def get_domain(data, id_or_defkey):
    """Get a single domain."""
    for d in data.get("domains", []):
        if d.get("id") == id_or_defkey or d.get("defKey") == id_or_defkey:
            return d
    return None


def add_domain(data, defKey, defName="", applyFor="", len_="", scale="", uiHint=""):
    """Add a domain definition."""
    d = {
        "defKey": defKey,
        "defName": defName or defKey,
        "applyFor": applyFor,
        "len": str(len_) if len_ else "",
        "scale": str(scale) if scale else "",
        "uiHint": uiHint,
        "id": _uid(),
    }
    data.setdefault("domains", []).append(d)
    return d


def delete_domain(data, id_or_defkey):
    """Delete a domain."""
    d = get_domain(data, id_or_defkey)
    if not d:
        raise ValueError(f"Domain not found: {id_or_defkey}")
    did = d["id"]
    data["domains"] = [x for x in data.get("domains", []) if x["id"] != did]
    return d


def get_mappings(data):
    """List all data type mappings."""
    return data.get("dataTypeMapping", {}).get("mappings", [])


def add_mapping(data, defKey, defName="", **db_types):
    """Add a data type mapping entry."""
    m = {"defKey": defKey, "defName": defName or defKey, "id": _uid()}
    m.update(db_types)
    data.setdefault("dataTypeMapping", {}).setdefault("mappings", []).append(m)
    return m


def delete_mapping(data, id_or_defkey):
    """Delete a data type mapping."""
    mappings = data.get("dataTypeMapping", {}).get("mappings", [])
    data["dataTypeMapping"]["mappings"] = [
        m for m in mappings
        if m.get("id") != id_or_defkey and m.get("defKey") != id_or_defkey
    ]


def get_data_type_supports(data):
    """List supported database types."""
    return data.get("profile", {}).get("dataTypeSupports", [])
