"""Compose parsing for ControlPlane-style infrastructure repositories.

The repo layout this targets (the common homelab/VPS pattern) is:

    docker-compose.yml          # root file that only `include:`s the stacks
    <stack>/docker-compose.yml  # one directory per stack

Nothing here talks to Docker. Everything is static analysis of the files on
disk, so the CLI stays deterministic and safe to run on a laptop or an agent
sandbox without a daemon.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "PyYAML is required: pip install pyyaml"
    ) from exc


COMPOSE_FILENAMES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)


class ComposeError(Exception):
    """Raised when a compose file cannot be read or parsed."""


@dataclass
class PortBinding:
    host: str
    container: str
    protocol: str = "tcp"

    def as_dict(self) -> dict[str, str]:
        return {"host": self.host, "container": self.container, "protocol": self.protocol}


@dataclass
class Service:
    name: str
    image: str = ""
    build: bool = False
    container_name: str = ""
    restart: str = ""
    ports: list[PortBinding] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    environment: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "image": self.image,
            "build": self.build,
            "container_name": self.container_name,
            "restart": self.restart,
            "ports": [p.as_dict() for p in self.ports],
            "volumes": self.volumes,
            "depends_on": self.depends_on,
            "environment": self.environment,
        }


@dataclass
class Stack:
    name: str
    path: Path
    compose_file: Path
    services: list[Service] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "compose_file": str(self.compose_file),
            "includes": self.includes,
            "networks": self.networks,
            "volumes": self.volumes,
            "services": [s.as_dict() for s in self.services],
        }


def find_compose_file(directory: Path) -> Path | None:
    for name in COMPOSE_FILENAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ComposeError(f"cannot read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ComposeError(f"invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ComposeError(f"{path}: expected a mapping at the top level")
    return data


def _parse_ports(raw_ports: Any) -> list[PortBinding]:
    bindings: list[PortBinding] = []
    if not isinstance(raw_ports, list):
        return bindings
    for entry in raw_ports:
        if isinstance(entry, dict):
            host = str(entry.get("published", entry.get("host", "")))
            container = str(entry.get("target", entry.get("container", "")))
            protocol = str(entry.get("protocol", "tcp"))
            bindings.append(PortBinding(host=host, container=container, protocol=protocol))
            continue
        text = str(entry).strip()
        protocol = "tcp"
        if "/" in text:
            text, protocol = text.rsplit("/", 1)
        # Accept "8080:80", "127.0.0.1:8080:80", "80"
        parts = text.split(":")
        if len(parts) == 3:
            host, container = parts[1], parts[2]
        elif len(parts) == 2:
            host, container = parts[0], parts[1]
        else:
            host, container = "", parts[0]
        bindings.append(PortBinding(host=host, container=container, protocol=protocol))
    return bindings


def _parse_service(name: str, raw: dict[str, Any]) -> Service:
    depends = raw.get("depends_on") or []
    if isinstance(depends, dict):
        depends = list(depends.keys())
    env = raw.get("environment") or []
    if isinstance(env, dict):
        env = [str(k) for k in env.keys()]

    return Service(
        name=name,
        image=str(raw.get("image", "")),
        build=bool(raw.get("build")),
        container_name=str(raw.get("container_name", "")),
        restart=str(raw.get("restart", "")),
        ports=_parse_ports(raw.get("ports")),
        volumes=[str(v) for v in (raw.get("volumes") or [])],
        depends_on=[str(d) for d in depends],
        environment=[str(e).split("=", 1)[0] for e in env],
    )


def load_stack(path: Path) -> Stack:
    """Load a single stack directory (no include expansion)."""
    compose_file = find_compose_file(path)
    if compose_file is None:
        raise ComposeError(f"no compose file in {path}")
    data = read_yaml(compose_file)

    services_raw = data.get("services") or {}
    if not isinstance(services_raw, dict):
        raise ComposeError(f"{compose_file}: 'services' must be a mapping")

    services = [
        _parse_service(name, raw or {})
        for name, raw in services_raw.items()
    ]

    includes_raw = data.get("include") or []
    includes: list[str] = []
    if isinstance(includes_raw, list):
        for entry in includes_raw:
            if isinstance(entry, str):
                includes.append(entry)
            elif isinstance(entry, dict) and "path" in entry:
                includes.append(str(entry["path"]))

    return Stack(
        name=data.get("name") or path.name,
        path=path,
        compose_file=compose_file,
        services=services,
        includes=includes,
        networks=sorted((data.get("networks") or {}) if isinstance(data.get("networks"), dict) else []),
        volumes=sorted((data.get("volumes") or {}) if isinstance(data.get("volumes"), dict) else []),
    )


def repo_root(start: Path | None = None) -> Path:
    """Find the repo root: the directory holding the root compose file."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        compose = find_compose_file(candidate)
        if compose is not None:
            data = read_yaml(compose)
            if "include" in data:
                return candidate
    return current


def list_stacks(repo: Path) -> list[Stack]:
    """Every directory in the repo that holds a compose file."""
    stacks: list[Stack] = []
    for entry in sorted(repo.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if find_compose_file(entry) is None:
            continue
        try:
            stacks.append(load_stack(entry))
        except ComposeError:
            continue
    return stacks


def resolve_include_target(repo: Path, include: str) -> Path:
    target = Path(include)
    if not target.is_absolute():
        target = repo / target
    return target


def merged_services(repo: Path) -> dict[str, Service]:
    """Services from the root compose file plus everything it includes."""
    root_compose = find_compose_file(repo)
    if root_compose is None:
        raise ComposeError(f"no root compose file in {repo}")
    root = load_stack(repo)
    services: dict[str, Service] = {s.name: s for s in root.services}

    for include in root.includes:
        target = resolve_include_target(repo, include)
        directory = target if target.is_dir() else target.parent
        stack = load_stack(directory)
        for service in stack.services:
            services.setdefault(service.name, service)

    return services


def validate(repo: Path) -> list[dict[str, str]]:
    """Static checks across the whole repo. Returns issue dicts."""
    issues: list[dict[str, str]] = []
    stacks = list_stacks(repo)

    root_stack: Stack | None = None
    if find_compose_file(repo) is not None:
        try:
            root_stack = load_stack(repo)
        except ComposeError as exc:
            issues.append({
                "level": "error",
                "file": str(find_compose_file(repo)),
                "message": str(exc),
            })

    if not stacks and root_stack is None:
        issues.append({
            "level": "error",
            "file": str(repo),
            "message": "no stacks found (no directory with a compose file)",
        })
        return issues

    checked = ([root_stack] if root_stack is not None else []) + stacks

    container_names: dict[str, str] = {}
    published_ports: dict[tuple[str, str], str] = {}

    for stack in checked:
        try:
            data = read_yaml(stack.compose_file)
        except ComposeError as exc:
            issues.append({"level": "error", "file": str(stack.compose_file), "message": str(exc)})
            continue

        for include in stack.includes:
            target = resolve_include_target(repo, include)
            if not target.exists():
                issues.append({
                    "level": "error",
                    "file": str(stack.compose_file),
                    "message": f"include target missing: {include}",
                })

        if not data.get("services") and not stack.includes:
            issues.append({
                "level": "warn",
                "file": str(stack.compose_file),
                "message": "no services defined",
            })

        for service in stack.services:
            where = f"{stack.name}/{service.name}"
            if not service.image and not service.build:
                issues.append({
                    "level": "error",
                    "file": str(stack.compose_file),
                    "message": f"{where}: needs 'image' or 'build'",
                })
            if service.container_name:
                key = service.container_name
                if key in container_names:
                    issues.append({
                        "level": "error",
                        "file": str(stack.compose_file),
                        "message": (
                            f"{where}: container_name '{key}' also used in "
                            f"{container_names[key]}"
                        ),
                    })
                else:
                    container_names[key] = where
            for port in service.ports:
                if not port.host:
                    continue
                key = (port.host, port.protocol)
                if key in published_ports:
                    issues.append({
                        "level": "warn",
                        "file": str(stack.compose_file),
                        "message": (
                            f"{where}: host port {port.host}/{port.protocol} also "
                            f"published by {published_ports[key]}"
                        ),
                    })
                else:
                    published_ports[key] = where

    return issues
