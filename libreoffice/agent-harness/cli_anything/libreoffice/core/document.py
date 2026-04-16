"""LibreOffice CLI - Core document management module."""

import json
import os
import copy
from datetime import datetime
from typing import Optional, Dict, Any, List


# Document profiles (page size presets)
PROFILES = {
    "a4_portrait": {
        "page_width": "21cm", "page_height": "29.7cm",
        "margin_top": "2cm", "margin_bottom": "2cm",
        "margin_left": "2cm", "margin_right": "2cm",
    },
    "a4_landscape": {
        "page_width": "29.7cm", "page_height": "21cm",
        "margin_top": "2cm", "margin_bottom": "2cm",
        "margin_left": "2cm", "margin_right": "2cm",
    },
    "letter_portrait": {
        "page_width": "21.59cm", "page_height": "27.94cm",
        "margin_top": "2.54cm", "margin_bottom": "2.54cm",
        "margin_left": "2.54cm", "margin_right": "2.54cm",
    },
    "letter_landscape": {
        "page_width": "27.94cm", "page_height": "21.59cm",
        "margin_top": "2.54cm", "margin_bottom": "2.54cm",
        "margin_left": "2.54cm", "margin_right": "2.54cm",
    },
    "legal_portrait": {
        "page_width": "21.59cm", "page_height": "35.56cm",
        "margin_top": "2.54cm", "margin_bottom": "2.54cm",
        "margin_left": "2.54cm", "margin_right": "2.54cm",
    },
    "presentation_16_9": {
        "page_width": "33.867cm", "page_height": "19.05cm",
        "margin_top": "0cm", "margin_bottom": "0cm",
        "margin_left": "0cm", "margin_right": "0cm",
    },
    "presentation_4_3": {
        "page_width": "25.4cm", "page_height": "19.05cm",
        "margin_top": "0cm", "margin_bottom": "0cm",
        "margin_left": "0cm", "margin_right": "0cm",
    },
}

PROJECT_VERSION = "1.0"

VALID_DOC_TYPES = ("writer", "calc", "impress")


def create_document(
    doc_type: str = "writer",
    name: str = "untitled",
    profile: Optional[str] = None,
    settings: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a new LibreOffice CLI document project."""
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError(
            f"Invalid document type: {doc_type}. "
            f"Must be one of: {', '.join(VALID_DOC_TYPES)}"
        )

    # Start with default settings
    doc_settings = {
        "page_width": "21cm",
        "page_height": "29.7cm",
        "margin_top": "2cm",
        "margin_bottom": "2cm",
        "margin_left": "2cm",
        "margin_right": "2cm",
    }

    # Apply profile if specified
    if profile:
        if profile not in PROFILES:
            raise ValueError(
                f"Unknown profile: {profile}. "
                f"Available: {', '.join(PROFILES.keys())}"
            )
        doc_settings.update(PROFILES[profile])

    # Apply explicit settings overrides
    if settings:
        doc_settings.update(settings)

    project = {
        "version": PROJECT_VERSION,
        "name": name,
        "type": doc_type,
        "settings": doc_settings,
        "styles": {},
        "metadata": {
            "title": "",
            "author": "",
            "description": "",
            "subject": "",
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "software": "libreoffice-cli 1.0",
        },
    }

    # Add type-specific content structures
    if doc_type == "writer":
        project["content"] = []
    elif doc_type == "calc":
        project["sheets"] = [{"name": "Sheet1", "cells": {}}]
    elif doc_type == "impress":
        project["slides"] = []

    return project


def open_document(path: str) -> Dict[str, Any]:
    """Open a .lo-cli.json project file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Document file not found: {path}")
    with open(path, "r") as f:
        project = json.load(f)
    if "version" not in project or "type" not in project:
        raise ValueError(f"Invalid project file: {path}")
    if project["type"] not in VALID_DOC_TYPES:
        raise ValueError(
            f"Invalid document type in file: {project['type']}"
        )
    return project


def save_document(project: Dict[str, Any], path: str) -> str:
    """Save project to a .lo-cli.json file."""
    project["metadata"]["modified"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(project, f, indent=2, default=str)
    return path


def get_document_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get summary information about the document."""
    doc_type = project.get("type", "writer")
    info = {
        "name": project.get("name", "untitled"),
        "version": project.get("version", "unknown"),
        "type": doc_type,
        "settings": project.get("settings", {}),
        "metadata": project.get("metadata", {}),
        "style_count": len(project.get("styles", {})),
    }

    if doc_type == "writer":
        info["content_count"] = len(project.get("content", []))
    elif doc_type == "calc":
        sheets = project.get("sheets", [])
        info["sheet_count"] = len(sheets)
        info["sheets"] = [
            {"name": s.get("name", "Sheet"), "cell_count": len(s.get("cells", {}))}
            for s in sheets
        ]
    elif doc_type == "impress":
        info["slide_count"] = len(project.get("slides", []))

    return info


def list_profiles() -> List[Dict[str, Any]]:
    """List all available document profiles."""
    result = []
    for name, settings in PROFILES.items():
        result.append({"name": name, **settings})
    return result
