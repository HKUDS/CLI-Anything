"""Project CRUD operations for PDManer .chnr.json files."""

import copy
import json
import os
import uuid
import datetime

EMPTY_PROJECT = {
    "name": "empty",
    "describe": "",
    "avatar": "",
    "version": "4.9.4",
    "createdTime": "",
    "updatedTime": "",
    "dbConns": [],
    "profile": {
        "default": {
            "db": "",
            "dbConn": "",
            "entityInitFields": [],
        },
        "dataTypeSupports": [],
        "codeTemplates": [],
        "uiHint": [],
        "headers": [
            {"refKey": "defKey", "enable": True},
            {"refKey": "defName", "enable": True},
            {"refKey": "primaryKey", "enable": True},
            {"refKey": "notNull", "enable": True},
            {"refKey": "autoIncrement", "enable": True},
            {"refKey": "domain", "enable": True},
            {"refKey": "type", "enable": True},
            {"refKey": "len", "enable": True},
            {"refKey": "scale", "enable": True},
            {"refKey": "comment", "enable": True},
            {"refKey": "refDict", "enable": True},
            {"refKey": "defaultValue", "enable": True},
            {"refKey": "hideInGraph", "enable": True},
            {"refKey": "uiHint", "enable": True},
        ],
        "extAttrProps": {},
        "namingRules": {
            "entityDefKey": {"rule": "", "case": ""},
            "fieldDefKey": {"rule": "", "case": ""},
            "indexDefKey": {"rule": "", "case": ""},
        },
    },
    "entities": [],
    "views": [],
    "diagrams": [],
    "dicts": [],
    "domains": [],
    "dataTypeMapping": {
        "referURL": "",
        "mappings": [],
    },
    "viewGroups": [],
    "standardFields": [],
    "logicEntities": [],
    "namingRules": {
        "entityDefKey": {"rule": "", "case": ""},
        "fieldDefKey": {"rule": "", "case": ""},
        "indexDefKey": {"rule": "", "case": ""},
    },
}


def _uid():
    return str(uuid.uuid4()).upper()


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_project(name, describe="", path=None):
    """Create a new PDManer project and return its data dict."""
    data = copy.deepcopy(EMPTY_PROJECT)
    data["name"] = name
    data["describe"] = describe or name
    data["createdTime"] = _now()
    data["updatedTime"] = data["createdTime"]
    data["id"] = _uid()

    if path:
        _save_json(path, data)
        data["_path"] = path
        data["_modified"] = False

    return data


def open_project(path):
    """Read an existing PDManer project file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.loads(f.read().replace("﻿", ""))
    data["_path"] = path
    data["_modified"] = False
    return data


def save_project(data, path=None):
    """Save project data to file."""
    target = path or data.get("_path")
    if not target:
        raise RuntimeError("No save path specified")
    save_data = {k: v for k, v in data.items() if not k.startswith("_")}
    save_data["updatedTime"] = _now()
    _save_json(target, save_data)
    data["_path"] = target
    data["_modified"] = False
    return target


def save_project_as(data, path):
    """Save project to a new file path."""
    return save_project(data, path)


def get_project_info(data, as_dict=False):
    """Return project summary info."""
    entities = data.get("entities", [])
    views = data.get("views", [])
    diagrams = data.get("diagrams", [])
    dicts = data.get("dicts", [])
    info = {
        "name": data.get("name", ""),
        "describe": data.get("describe", ""),
        "version": data.get("version", ""),
        "createdTime": data.get("createdTime", ""),
        "updatedTime": data.get("updatedTime", ""),
        "entityCount": len(entities),
        "viewCount": len(views),
        "diagramCount": len(diagrams),
        "dictCount": len(dicts),
        "defaultDb": _get_default_db(data),
    }
    if as_dict:
        return info
    return info


def _get_default_db(data):
    """Get the default database defKey."""
    db_id = data.get("profile", {}).get("default", {}).get("db", "")
    supports = data.get("profile", {}).get("dataTypeSupports", [])
    for s in supports:
        if s.get("id") == db_id:
            return s.get("defKey", "")
    return ""


def _save_json(path, data):
    """Write JSON to file, ensuring directory exists."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
