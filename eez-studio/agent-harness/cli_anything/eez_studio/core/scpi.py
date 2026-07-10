"""SCPI helpers for native EEZ project JSON."""

from __future__ import annotations

from typing import Any


def _scpi(project: dict[str, Any]) -> dict[str, Any]:
    return project.setdefault("scpi", {"subsystems": [], "enums": []})


def list_subsystems(project: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for subsystem in _scpi(project).setdefault("subsystems", []):
        rows.append(
            {
                "name": subsystem.get("name"),
                "description": subsystem.get("description", ""),
                "command_count": len(subsystem.get("commands") or []),
            }
        )
    return rows


def add_subsystem(project: dict[str, Any], name: str, description: str = "") -> dict[str, Any]:
    if not name:
        raise ValueError("subsystem name is required")
    subsystems = _scpi(project).setdefault("subsystems", [])
    if any(item.get("name") == name for item in subsystems):
        raise ValueError(f"SCPI subsystem already exists: {name}")
    entry = {"name": name, "description": description, "helpLink": "", "commands": []}
    subsystems.append(entry)
    return {"name": name, "command_count": 0}


def find_subsystem(project: dict[str, Any], name: str) -> dict[str, Any]:
    for subsystem in _scpi(project).setdefault("subsystems", []):
        if subsystem.get("name") == name:
            return subsystem
    raise ValueError(f"SCPI subsystem not found: {name}")


def list_commands(project: dict[str, Any], subsystem_name: str | None = None) -> list[dict[str, Any]]:
    rows = []
    subsystems = _scpi(project).setdefault("subsystems", [])
    for subsystem in subsystems:
        if subsystem_name and subsystem.get("name") != subsystem_name:
            continue
        for command in subsystem.get("commands") or []:
            rows.append(
                {
                    "subsystem": subsystem.get("name"),
                    "name": command.get("name"),
                    "query": str(command.get("name", "")).endswith("?"),
                    "description": command.get("description", ""),
                    "parameters": len(command.get("parameters") or []),
                    "response": command.get("response", {}).get("type", []),
                }
            )
    return rows


def add_command(
    project: dict[str, Any],
    subsystem_name: str,
    name: str,
    description: str = "",
    response_type: str | None = None,
) -> dict[str, Any]:
    if not name:
        raise ValueError("command name is required")
    subsystem = find_subsystem(project, subsystem_name)
    commands = subsystem.setdefault("commands", [])
    if any(command.get("name") == name for command in commands):
        raise ValueError(f"SCPI command already exists in {subsystem_name}: {name}")
    command: dict[str, Any] = {
        "name": name,
        "description": description,
        "helpLink": "",
        "usedIn": [],
        "parameters": [],
        "sendsBackDataBlock": False,
    }
    if name.endswith("?"):
        command["response"] = {
            "type": [{"type": response_type or "quoted-string"}],
            "description": description,
        }
    else:
        command["response"] = {}
    commands.append(command)
    return {"subsystem": subsystem_name, "name": name, "query": name.endswith("?")}


def add_parameter(
    project: dict[str, Any],
    subsystem_name: str,
    command_name: str,
    name: str,
    parameter_type: str = "nr1",
    optional: bool = False,
    description: str = "",
) -> dict[str, Any]:
    subsystem = find_subsystem(project, subsystem_name)
    for command in subsystem.get("commands") or []:
        if command.get("name") == command_name:
            parameters = command.setdefault("parameters", [])
            if any(parameter.get("name") == name for parameter in parameters):
                raise ValueError(f"SCPI parameter already exists: {name}")
            parameters.append(
                {
                    "name": name,
                    "type": [{"type": parameter_type}],
                    "isOptional": bool(optional),
                    "description": description,
                }
            )
            return {
                "subsystem": subsystem_name,
                "command": command_name,
                "name": name,
                "type": parameter_type,
            }
    raise ValueError(f"SCPI command not found: {command_name}")
