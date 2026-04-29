"""Parsing helpers for Nsight Graphics CLI output."""

from __future__ import annotations

import re
from typing import Any, Optional

from cli_anything.nsight_graphics.utils.backend.shared import _dedupe

_ACTIVITY_ALIASES = {
    "frame debugger": ("Frame Debugger", "Graphics Capture"),
    "graphics capture": ("Graphics Capture", "Frame Debugger"),
}


def _extract_long_option(line: str) -> Optional[str]:
    """Extract the primary long option token from a help line."""
    match = re.search(r"(--[A-Za-z0-9-]+)", line)
    return match.group(1) if match else None


def parse_unified_help(text: str) -> dict[str, Any]:
    """Parse `ngfx --help-all` output into structured metadata."""
    activities: list[str] = []
    platforms: list[str] = []
    general_options: list[str] = []
    activity_options: dict[str, list[str]] = {}
    current_section: Optional[str] = None
    current_activity: Optional[str] = None
    collecting: Optional[str] = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        if stripped == "General Options:":
            current_section = "general"
            current_activity = None
            collecting = None
            continue

        if stripped.endswith("activity options:"):
            current_section = "activity"
            current_activity = stripped[: -len(" activity options:")]
            activity_options.setdefault(current_activity, [])
            collecting = None
            continue

        if stripped.startswith("--") or stripped.startswith("-"):
            option = _extract_long_option(stripped)
            if option and current_section == "general":
                general_options.append(option)
                if option == "--activity":
                    collecting = "activities"
                elif option == "--platform":
                    collecting = "platforms"
                else:
                    collecting = None
            elif option and current_section == "activity" and current_activity:
                activity_options.setdefault(current_activity, []).append(option)
                collecting = None
            else:
                collecting = None
            continue

        if collecting == "activities":
            lowered = stripped.lower()
            if "should be one of" not in lowered and lowered not in {"of:", "one of:"}:
                activities.append(stripped)
            continue

        if collecting == "platforms":
            lowered = stripped.lower()
            if "should be one of" not in lowered and lowered not in {"of:", "one of:"}:
                platforms.append(stripped)
            continue

    return {
        "activities": _dedupe(activities),
        "platforms": _dedupe(platforms),
        "general_options": _dedupe(general_options),
        "activity_options": {
            key: _dedupe(values) for key, values in activity_options.items()
        },
    }


def parse_option_help(text: str) -> list[str]:
    """Extract long options from arbitrary CLI help output."""
    options: list[str] = []
    for raw_line in text.splitlines():
        option = _extract_long_option(raw_line.strip())
        if option:
            options.append(option)
    return _dedupe(options)


def resolve_activity_name(report: dict[str, Any], requested: str) -> str:
    """Map a requested activity name onto the current Nsight installation."""
    supported = report.get("supported_activities") or []
    if not supported:
        return requested

    supported_lookup = {item.lower(): item for item in supported}
    direct = supported_lookup.get(requested.lower())
    if direct:
        return direct

    aliases = _ACTIVITY_ALIASES.get(requested.lower(), (requested,))
    for alias in aliases:
        resolved = supported_lookup.get(alias.lower())
        if resolved:
            return resolved
    return requested
