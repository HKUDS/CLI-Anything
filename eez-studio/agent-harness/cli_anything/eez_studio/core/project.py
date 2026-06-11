"""Native .eez-project JSON helpers.

EEZ Studio stores projects as JSON in files ending with ``.eez-project``.
This module edits that native format directly and keeps the generated shape
close to the upstream project editor model: settings, build templates, pages,
LVGL widgets, SCPI subsystems, and optional feature collections.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any


DEFAULT_LVGL_VERSION = "9.2.2"
DEFAULT_DESTINATION = "src/ui"
PROJECT_EXTENSION = ".eez-project"


def new_obj_id() -> str:
    return uuid.uuid4().hex


def _locked_save_json(path: str | os.PathLike[str], data: Any, **dump_kwargs: Any) -> None:
    path = os.fspath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    try:
        handle = open(path, "r+", encoding="utf-8")
    except FileNotFoundError:
        handle = open(path, "w", encoding="utf-8")
    with handle:
        locked = False
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        except (ImportError, OSError):
            pass
        try:
            handle.seek(0)
            handle.truncate()
            json.dump(data, handle, **dump_kwargs)
            handle.write("\n")
            handle.flush()
        finally:
            if locked:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sanitize_identifier(name: str, fallback: str = "screen") -> str:
    identifier = re.sub(r"[^0-9a-zA-Z_]+", "_", name.strip()).strip("_").lower()
    if not identifier:
        identifier = fallback
    if identifier[0].isdigit():
        identifier = f"{fallback}_{identifier}"
    return identifier


def _build_templates() -> list[dict[str, Any]]:
    """Return conservative EEZ Studio build templates using upstream markers."""
    return [
        {
            "fileName": "ui.h",
            "description": "Main LVGL UI declarations",
            "template": "\n".join(
                [
                    "#pragma once",
                    '#include "lvgl/lvgl.h"',
                    "//${eez-studio LVGL_INCLUDE}",
                    "//${eez-studio EEZ_FOR_LVGL_CHECK}",
                    "#ifdef __cplusplus",
                    'extern "C" {',
                    "#endif",
                    "//${eez-studio GUI_ASSETS_DECL}",
                    "//${eez-studio LVGL_SCREENS_DECL}",
                    "//${eez-studio LVGL_STYLES_DECL}",
                    "//${eez-studio LVGL_IMAGES_DECL}",
                    "//${eez-studio LVGL_FONTS_DECL}",
                    "//${eez-studio LVGL_ACTIONS_DECL}",
                    "//${eez-studio LVGL_VARS_DECL}",
                    "void ui_init(void);",
                    "void ui_tick(void);",
                    "#ifdef __cplusplus",
                    "}",
                    "#endif",
                    "",
                ]
            ),
        },
        {
            "fileName": "ui.c",
            "description": "Main LVGL UI definitions",
            "template": "\n".join(
                [
                    '#include "ui.h"',
                    "",
                    "//${eez-studio GUI_ASSETS_DEF}",
                    "//${eez-studio LVGL_STYLES_DEF}",
                    "//${eez-studio LVGL_IMAGES_DEF}",
                    "//${eez-studio LVGL_ACTIONS_ARRAY_DEF}",
                    "//${eez-studio LVGL_NATIVE_VARS_TABLE_DEF}",
                    "",
                    "void ui_init(void) {",
                    "    //${eez-studio LVGL_LOAD_FIRST_SCREEN}",
                    "}",
                    "",
                    "void ui_tick(void) {",
                    "}",
                    "",
                ]
            ),
        },
        {
            "fileName": "screens.c",
            "description": "LVGL screen construction",
            "template": "\n".join(
                [
                    '#include "ui.h"',
                    "",
                    "//${eez-studio LVGL_SCREENS_DEF}",
                    "//${eez-studio LVGL_SCREENS_DEF_EXT}",
                    "",
                ]
            ),
        },
        {
            "fileName": "screens.h",
            "description": "LVGL screen declarations",
            "template": "\n".join(
                [
                    "#pragma once",
                    '#include "ui.h"',
                    "",
                    "//${eez-studio LVGL_SCREENS_DECL}",
                    "//${eez-studio LVGL_SCREENS_DECL_EXT}",
                    "",
                ]
            ),
        },
        {
            "fileName": "vars.h",
            "description": "Native LVGL variable declarations",
            "template": "\n".join(["#pragma once", "//${eez-studio LVGL_VARS_DECL}", ""]),
        },
        {
            "fileName": "actions.h",
            "description": "LVGL action declarations",
            "template": "\n".join(["#pragma once", "//${eez-studio LVGL_ACTIONS_DECL}", ""]),
        },
    ]


def _base_widget(widget_type: str, name: str, **props: Any) -> dict[str, Any]:
    widget = {
        "objID": new_obj_id(),
        "type": widget_type,
        "name": name,
        "left": props.pop("x", props.pop("left", 0)),
        "top": props.pop("y", props.pop("top", 0)),
        "width": props.pop("width", 120),
        "height": props.pop("height", 40),
        "hidden": False,
        "clickableFlag": True,
        "checkedFlag": False,
        "disabledFlag": False,
        "children": [],
    }
    widget.update(props)
    return widget


def _screen_widget(name: str, width: int, height: int) -> dict[str, Any]:
    return _base_widget(
        "LVGLScreenWidget",
        f"{name}_root",
        left=0,
        top=0,
        width=width,
        height=height,
        clickableFlag=False,
        children=[],
    )


def _page(name: str, width: int, height: int, page_id: int) -> dict[str, Any]:
    identifier = sanitize_identifier(name)
    return {
        "objID": new_obj_id(),
        "name": name,
        "id": page_id,
        "identifier": identifier,
        "description": "",
        "width": width,
        "height": height,
        "components": [_screen_widget(name, width, height)],
        "connectionLines": [],
    }


def create_project(
    name: str = "Untitled",
    display_width: int = 800,
    display_height: int = 480,
    lvgl_version: str = DEFAULT_LVGL_VERSION,
    destination: str = DEFAULT_DESTINATION,
    flow_support: bool = False,
) -> dict[str, Any]:
    if display_width <= 0 or display_height <= 0:
        raise ValueError("display dimensions must be positive")
    if not lvgl_version:
        raise ValueError("lvgl_version is required")

    now = int(time.time())
    return {
        "objID": new_obj_id(),
        "settings": {
            "objID": new_obj_id(),
            "general": {
                "projectName": name,
                "projectType": "lvgl",
                "projectVersion": "v3",
                "lvglVersion": lvgl_version,
                "flowSupport": bool(flow_support),
                "displayWidth": display_width,
                "displayHeight": display_height,
                "colorBpp": "32",
                "imports": [],
                "extensions": [],
                "masterProject": "",
            },
            "build": {
                "configurations": [],
                "files": _build_templates(),
                "destinationFolder": destination,
                "separateFolderForImagesAndFonts": False,
                "lvglInclude": "lvgl/lvgl.h",
                "screensLifetimeSupport": False,
                "generateSourceCodeForEezFramework": False,
                "compressFlowDefinition": False,
                "executionQueueSize": 1000,
                "expressionEvaluatorStackSize": 20,
                "imageExportMode": "source",
                "fontExportMode": "source",
                "fileSystemPath": "",
                "useDockerDesktop": True,
            },
        },
        "variables": {"globalVariables": []},
        "actions": [],
        "userPages": [_page("Main", display_width, display_height, 1)],
        "userWidgets": [],
        "styles": [],
        "lvglStyles": {"styles": []},
        "lvglGroups": {
            "groups": [],
            "defaultGroupForEncoderInSimulator": "",
            "defaultGroupForKeyboardInSimulator": "",
        },
        "fonts": [],
        "bitmaps": [],
        "texts": {"languages": [], "resources": []},
        "scpi": {"subsystems": [], "enums": []},
        "instrumentCommands": {"commands": []},
        "shortcuts": {"shortcuts": []},
        "micropython": {"code": ""},
        "extensionDefinitions": [],
        "changes": {"changes": []},
        "readme": {"text": ""},
        "colors": [],
        "themes": [],
        "themesVersion": 1,
        "cliAnything": {
            "harness": "cli-anything-eez-studio",
            "createdAt": now,
            "format": "eez-project-json",
        },
    }


def load_project(path: str | os.PathLike[str]) -> dict[str, Any]:
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"EEZ project file not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    validate_project(data)
    return data


def save_project(project: dict[str, Any], path: str | os.PathLike[str]) -> dict[str, Any]:
    validate_project(project)
    _locked_save_json(path, project, indent=2, sort_keys=False)
    return {"path": os.path.abspath(os.fspath(path)), "bytes": os.path.getsize(path)}


def clone_project(project: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(project)


def validate_project(project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(project, dict):
        raise ValueError("EEZ project must be a JSON object")
    settings = project.get("settings")
    if not isinstance(settings, dict):
        errors.append("missing settings object")
    general = settings.get("general") if isinstance(settings, dict) else None
    if not isinstance(general, dict):
        errors.append("missing settings.general object")
    else:
        if general.get("projectType") not in {"lvgl", "dashboard", "firmware", "resource"}:
            errors.append("settings.general.projectType is missing or unsupported")
        if not general.get("lvglVersion") and general.get("projectType") == "lvgl":
            errors.append("settings.general.lvglVersion is required for LVGL projects")
        if int(general.get("displayWidth", 0) or 0) <= 0:
            errors.append("settings.general.displayWidth must be positive")
        if int(general.get("displayHeight", 0) or 0) <= 0:
            errors.append("settings.general.displayHeight must be positive")
    if not isinstance(project.get("userPages", []), list):
        errors.append("userPages must be an array")
    if not isinstance(project.get("scpi", {}), dict):
        errors.append("scpi must be an object")
    if errors:
        raise ValueError("; ".join(errors))
    return errors


def get_general(project: dict[str, Any]) -> dict[str, Any]:
    return project.setdefault("settings", {}).setdefault("general", {})


def get_build(project: dict[str, Any]) -> dict[str, Any]:
    return project.setdefault("settings", {}).setdefault("build", {})


def set_general(project: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    allowed = {
        "projectName",
        "lvglVersion",
        "flowSupport",
        "displayWidth",
        "displayHeight",
        "colorBpp",
    }
    if key not in allowed:
        raise ValueError(f"unsupported settings.general key: {key}")
    if key in {"displayWidth", "displayHeight"}:
        value = int(value)
        if value <= 0:
            raise ValueError(f"{key} must be positive")
    if key == "flowSupport":
        value = _coerce_bool(value)
    get_general(project)[key] = value
    return project_info(project)


def set_build_destination(project: dict[str, Any], destination: str) -> dict[str, Any]:
    if not destination:
        raise ValueError("destination must not be empty")
    get_build(project)["destinationFolder"] = destination.replace("\\", "/")
    return project_info(project)


def add_build_file(
    project: dict[str, Any],
    file_name: str,
    template: str,
    description: str = "",
    replace: bool = False,
) -> dict[str, Any]:
    if not file_name:
        raise ValueError("file_name is required")
    files = get_build(project).setdefault("files", [])
    existing = next((entry for entry in files if entry.get("fileName") == file_name), None)
    if existing and not replace:
        raise ValueError(f"build file already exists: {file_name}")
    entry = {"fileName": file_name, "description": description, "template": template}
    if existing:
        existing.update(entry)
    else:
        files.append(entry)
    return {"fileName": file_name, "count": len(files)}


def project_info(project: dict[str, Any]) -> dict[str, Any]:
    general = get_general(project)
    build = get_build(project)
    pages = project.get("userPages") or []
    widgets = list_widgets(project)
    scpi = project.get("scpi") or {}
    subsystems = scpi.get("subsystems") or []
    command_count = sum(len(s.get("commands") or []) for s in subsystems)
    return {
        "project_name": general.get("projectName") or "<unnamed>",
        "project_type": general.get("projectType"),
        "project_version": general.get("projectVersion"),
        "lvgl_version": general.get("lvglVersion"),
        "flow_support": bool(general.get("flowSupport")),
        "display": {
            "width": general.get("displayWidth"),
            "height": general.get("displayHeight"),
            "color_bpp": general.get("colorBpp"),
        },
        "destination_folder": build.get("destinationFolder"),
        "build_file_count": len(build.get("files") or []),
        "page_count": len(pages),
        "widget_count": len(widgets),
        "scpi_subsystems": len(subsystems),
        "scpi_commands": command_count,
    }


def list_pages(project: dict[str, Any]) -> list[dict[str, Any]]:
    pages = []
    for index, page in enumerate(project.get("userPages") or []):
        widgets = _page_widgets(page)
        pages.append(
            {
                "index": index,
                "id": page.get("id"),
                "name": page.get("name"),
                "identifier": page.get("identifier"),
                "width": page.get("width"),
                "height": page.get("height"),
                "widget_count": len(widgets),
            }
        )
    return pages


def add_page(project: dict[str, Any], name: str, width: int | None = None, height: int | None = None) -> dict[str, Any]:
    pages = project.setdefault("userPages", [])
    general = get_general(project)
    page = _page(
        name,
        int(width or general.get("displayWidth") or 800),
        int(height or general.get("displayHeight") or 480),
        len(pages) + 1,
    )
    pages.append(page)
    return {"page": page.get("name"), "index": len(pages) - 1, "id": page.get("id")}


def _page_widgets(page: dict[str, Any]) -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []

    def walk(widget: dict[str, Any], parent: str | None = None) -> None:
        item = dict(widget)
        item["_parent"] = parent
        widgets.append(item)
        for child in widget.get("children") or []:
            if isinstance(child, dict):
                walk(child, widget.get("objID"))

    for component in page.get("components") or []:
        if isinstance(component, dict):
            walk(component)
    return widgets


def list_widgets(project: dict[str, Any], page_name: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in project.get("userPages") or []:
        if page_name and page.get("name") != page_name:
            continue
        for widget in _page_widgets(page):
            rows.append(
                {
                    "page": page.get("name"),
                    "objID": widget.get("objID"),
                    "type": widget.get("type"),
                    "name": widget.get("name"),
                    "left": widget.get("left"),
                    "top": widget.get("top"),
                    "width": widget.get("width"),
                    "height": widget.get("height"),
                    "text": widget.get("text"),
                    "parent": widget.get("_parent"),
                }
            )
    return rows


def find_page(project: dict[str, Any], page_name: str) -> dict[str, Any]:
    for page in project.get("userPages") or []:
        if page.get("name") == page_name:
            return page
    raise ValueError(f"page not found: {page_name}")


def _screen_root(page: dict[str, Any]) -> dict[str, Any]:
    components = page.setdefault("components", [])
    if not components:
        components.append(_screen_widget(page.get("name", "Main"), page.get("width", 800), page.get("height", 480)))
    return components[0]


def add_label(
    project: dict[str, Any],
    page_name: str,
    text: str,
    name: str | None = None,
    x: int = 20,
    y: int = 20,
    width: int = 160,
    height: int = 32,
) -> dict[str, Any]:
    page = find_page(project, page_name)
    widget = _base_widget(
        "LVGLLabelWidget",
        name or sanitize_identifier(text, "label"),
        x=x,
        y=y,
        width=width,
        height=height,
        text=text,
        clickableFlag=False,
    )
    _screen_root(page).setdefault("children", []).append(widget)
    return {"page": page_name, "objID": widget["objID"], "type": widget["type"], "name": widget["name"]}


def add_button(
    project: dict[str, Any],
    page_name: str,
    text: str,
    name: str | None = None,
    x: int = 20,
    y: int = 72,
    width: int = 140,
    height: int = 48,
) -> dict[str, Any]:
    page = find_page(project, page_name)
    button_name = name or sanitize_identifier(text, "button")
    label = _base_widget(
        "LVGLLabelWidget",
        f"{button_name}_label",
        x=0,
        y=0,
        width=width,
        height=height,
        text=text,
        clickableFlag=False,
    )
    button = _base_widget(
        "LVGLButtonWidget",
        button_name,
        x=x,
        y=y,
        width=width,
        height=height,
        children=[label],
    )
    _screen_root(page).setdefault("children", []).append(button)
    return {"page": page_name, "objID": button["objID"], "type": button["type"], "name": button["name"]}


def ensure_destination_dir(project_path: str | os.PathLike[str], project: dict[str, Any]) -> dict[str, Any]:
    destination = get_build(project).get("destinationFolder") or DEFAULT_DESTINATION
    absolute = Path(project_path).resolve().parent / destination
    absolute.mkdir(parents=True, exist_ok=True)
    return {"destination": str(absolute), "exists": absolute.is_dir()}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"1", "true", "yes", "on"}:
            return True
        if value.lower() in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def write_template_project(path: str | os.PathLike[str], **kwargs: Any) -> dict[str, Any]:
    project = create_project(**kwargs)
    result = save_project(project, path)
    result.update(project_info(project))
    return result
