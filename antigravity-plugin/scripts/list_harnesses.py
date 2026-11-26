#!/usr/bin/env python3
"""Deterministic discovery of installed and generated CLI-Anything harnesses.

Implements the canonical `/cli-anything-list` contract (`commands/list.md`)
using only the Python standard library, with cross-platform UTF-8 output.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import json
import os
import re
import shutil
import sys
from importlib.metadata import distributions
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".mypy_cache",
}


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _normalize_dist_name(raw_name: str) -> str:
    """Normalize a Python distribution name per PEP 503."""
    return re.sub(r"[-_.]+", "-", raw_name.strip().lower()).strip("-")


def _extract_setup_py_metadata(text: str) -> tuple[str | None, str | None]:
    """Extract (name, version) from setup.py via AST with simple constant resolution."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None, None

    bindings: dict[str, ast.AST] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            bindings[stmt.targets[0].id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            bindings[stmt.target.id] = stmt.value

    def _resolve_str(node: ast.AST) -> str | None:
        seen: set[str] = set()
        cur = node
        while isinstance(cur, ast.Name) and cur.id in bindings and cur.id not in seen:
            seen.add(cur.id)
            cur = bindings[cur.id]
        if isinstance(cur, ast.Constant) and isinstance(cur.value, str):
            return cur.value.strip() or None
        return None

    name: str | None = None
    version: str | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fname = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if fname == "setup":
                for kw in node.keywords:
                    if kw.arg == "name" and name is None:
                        name = _resolve_str(kw.value)
                    elif kw.arg == "version" and version is None:
                        version = _resolve_str(kw.value)
    return name, version


def _extract_pyproject_metadata_fallback(text: str) -> tuple[str | None, str | None, str]:
    """Python 3.10 fallback for reading name/version/backend from pyproject.toml."""
    section = ""
    build_backend: str | None = None
    proj_name: str | None = None
    proj_version: str | None = None
    poetry_name: str | None = None
    poetry_version: str | None = None

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]") and "=" not in line:
            section = line[1:-1].strip()
            continue
        match = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*["\']([^"\']+)["\']', line)
        if not match:
            continue
        key, val = match.group(1), match.group(2).strip()
        if section == "build-system" and key == "build-backend":
            build_backend = val
        elif section == "project":
            if key == "name":
                proj_name = val
            elif key == "version":
                proj_version = val
        elif section == "tool.poetry":
            if key == "name":
                poetry_name = val
            elif key == "version":
                poetry_version = val

    backend_norm = (build_backend or "").lower()
    if not backend_norm or backend_norm == "setuptools" or backend_norm.startswith("setuptools."):
        backend_kind = "setuptools"
    elif backend_norm == "poetry" or backend_norm.startswith("poetry."):
        backend_kind = "poetry"
    else:
        backend_kind = "other"

    if backend_kind == "poetry":
        return proj_name or poetry_name, proj_version or poetry_version, backend_kind
    return proj_name, proj_version, backend_kind


def _extract_pyproject_metadata(text: str) -> tuple[str | None, str | None, str]:
    """Extract (name, version, backend_kind) from pyproject.toml."""
    try:
        import tomllib  # Python 3.11+

        data = tomllib.loads(text)
    except ImportError:
        return _extract_pyproject_metadata_fallback(text)
    except Exception:
        return None, None, "setuptools"

    if not isinstance(data, dict):
        return None, None, "setuptools"

    bs = data.get("build-system")
    raw_backend = bs.get("build-backend") if isinstance(bs, dict) else None
    backend_norm = raw_backend.strip().lower() if isinstance(raw_backend, str) else ""
    if not backend_norm or backend_norm == "setuptools" or backend_norm.startswith("setuptools."):
        backend_kind = "setuptools"
    elif backend_norm == "poetry" or backend_norm.startswith("poetry."):
        backend_kind = "poetry"
    else:
        backend_kind = "other"

    proj = data.get("project")
    proj_name = proj.get("name").strip() if isinstance(proj, dict) and isinstance(proj.get("name"), str) else None
    proj_version = proj.get("version").strip() if isinstance(proj, dict) and isinstance(proj.get("version"), str) else None

    if backend_kind == "poetry":
        tool = data.get("tool")
        poetry = tool.get("poetry") if isinstance(tool, dict) else None
        p_name = poetry.get("name").strip() if isinstance(poetry, dict) and isinstance(poetry.get("name"), str) else None
        p_ver = poetry.get("version").strip() if isinstance(poetry, dict) and isinstance(poetry.get("version"), str) else None
        return proj_name or p_name, proj_version or p_ver, backend_kind

    return proj_name, proj_version, backend_kind


def _extract_setup_cfg_metadata(text: str) -> tuple[str | None, str | None]:
    """Extract (name, version) from setup.cfg [metadata]."""
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # type: ignore[assignment]
    try:
        cp.read_string(text)
    except configparser.Error:
        return None, None
    if not cp.has_section("metadata"):
        return None, None
    name = cp.get("metadata", "name", fallback="").strip() or None
    ver = cp.get("metadata", "version", fallback="").strip() or None
    if ver and ver.startswith(("attr:", "file:")):
        ver = None
    return name, ver


def _extract_packaging_metadata(harness_dir: Path) -> tuple[str | None, str | None]:
    """Return (public_dist_name, version) from pyproject.toml, setup.py, and/or setup.cfg."""
    dist_name: str | None = None
    version: str | None = None
    backend_kind = "setuptools"

    pyproj = harness_dir / "pyproject.toml"
    if pyproj.is_file():
        try:
            pyproj_text = pyproj.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            pyproj_text = ""
        if pyproj_text:
            dist_name, version, backend_kind = _extract_pyproject_metadata(pyproj_text)

    setup_py = harness_dir / "setup.py"
    if backend_kind == "setuptools" and (dist_name is None or version is None) and setup_py.is_file():
        try:
            setup_text = setup_py.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            setup_text = ""
        if setup_text:
            s_name, s_ver = _extract_setup_py_metadata(setup_text)
            if dist_name is None:
                dist_name = s_name
            if version is None:
                version = s_ver
            if version is None:
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', setup_text)
                if match:
                    version = match.group(1)

    setup_cfg = harness_dir / "setup.cfg"
    if backend_kind == "setuptools" and (dist_name is None or version is None) and setup_cfg.is_file():
        try:
            cfg_text = setup_cfg.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            cfg_text = ""
        if cfg_text:
            c_name, c_ver = _extract_setup_cfg_metadata(cfg_text)
            if dist_name is None:
                dist_name = c_name
            if version is None:
                version = c_ver

    return dist_name, version


def _extract_version(harness_dir: Path) -> str | None:
    return _extract_packaging_metadata(harness_dir)[1]


def scan_installed(*, include_hub: bool = False) -> dict[str, dict[str, object]]:
    installed: dict[str, dict[str, object]] = {}
    for dist in distributions():
        raw_name = (dist.metadata.get("Name") or "").strip()
        norm_name = _normalize_dist_name(raw_name)
        if not norm_name.startswith("cli-anything-"):
            continue
        if not include_hub and norm_name == "cli-anything-hub":
            continue
        software = norm_name[len("cli-anything-"):]
        exe = shutil.which(norm_name)
        installed[software] = {
            "name": software,
            "status": "installed",
            "version": dist.version,
            "executable": exe,
            "source": None,
        }
    return installed


def scan_generated(base_path: Path, max_depth: int | None = None) -> dict[str, dict[str, object]]:
    """Walk base_path finding <...>/agent-harness/cli_anything/<software>/__init__.py."""
    base = base_path.resolve()
    generated: dict[str, dict[str, object]] = {}

    def _on_walk_error(exc: OSError) -> None:
        print(f"Warning: skipping unreadable directory {getattr(exc, 'filename', '')}: {exc}", file=sys.stderr)

    for root, dirs, _files in os.walk(base, followlinks=False, onerror=_on_walk_error):
        root_path = Path(root)
        try:
            rel_parts = root_path.relative_to(base).parts
        except ValueError:
            rel_parts = ()
        depth = len(rel_parts)

        # Prune irrelevant directories to keep scans fast.
        dirs[:] = [
            d for d in sorted(dirs)
            if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]

        if root_path.name == "agent-harness" and (root_path / "cli_anything").is_dir():
            ns_dir = root_path / "cli_anything"
            try:
                entries = sorted(ns_dir.iterdir())
            except OSError as exc:
                print(f"Warning: skipping unreadable namespace directory {ns_dir}: {exc}", file=sys.stderr)
                dirs[:] = []
                continue
            valid_pkgs: list[Path] = []
            for pkg in entries:
                try:
                    is_valid_pkg = pkg.is_dir() and (pkg / "__init__.py").is_file()
                except OSError as exc:
                    print(f"Warning: skipping unreadable package directory {pkg}: {exc}", file=sys.stderr)
                    continue
                if is_valid_pkg:
                    valid_pkgs.append(pkg)

            if valid_pkgs:
                dist_name, version = _extract_packaging_metadata(root_path)
                public_software: str | None = None
                if dist_name:
                    norm_dist = _normalize_dist_name(dist_name)
                    if norm_dist.startswith("cli-anything-"):
                        public_software = norm_dist[len("cli-anything-"):]
                try:
                    display_src = str(root_path.relative_to(base)).replace("\\", "/")
                    if not display_src.startswith("."):
                        display_src = "./" + display_src
                except ValueError:
                    display_src = str(root_path)

                for pkg in valid_pkgs:
                    if len(valid_pkgs) == 1 and public_software:
                        software = public_software
                    else:
                        software = _normalize_dist_name(pkg.name)
                    generated[software] = {
                        "name": software,
                        "status": "generated",
                        "version": version,
                        "executable": None,
                        "source": display_src,
                    }
            # No need to descend further into an already-matched agent-harness.
            dirs[:] = []
            continue

        if max_depth is not None and depth >= max_depth:
            # Allow checking an immediate `agent-harness` child at max_depth.
            dirs[:] = [d for d in dirs if d == "agent-harness"]

    return generated


def collect_tools(
    base_path: Path,
    *,
    max_depth: int | None = None,
    include_hub: bool = False,
) -> dict[str, object]:
    installed = scan_installed(include_hub=include_hub)
    generated = scan_generated(base_path, max_depth=max_depth)

    merged: dict[str, dict[str, object]] = {}
    for name in sorted(set(installed) | set(generated)):
        if name in installed:
            entry = dict(installed[name])
            if name in generated:
                entry["source"] = generated[name]["source"]
            merged[name] = entry
        else:
            merged[name] = dict(generated[name])

    tools = list(merged.values())
    installed_count = sum(1 for t in tools if t["status"] == "installed")
    generated_only = sum(1 for t in tools if t["status"] == "generated")
    return {
        "tools": tools,
        "total": len(tools),
        "installed": installed_count,
        "generated_only": generated_only,
    }


def _print_table(payload: dict[str, object]) -> None:
    tools: list[dict[str, object]] = payload["tools"]  # type: ignore[assignment]
    if not tools:
        print("No CLI-Anything tools found.")
        return

    print(f"CLI-Anything Tools (found {payload['total']})\n")
    print(f"{'Name':<20} {'Status':<11} {'Version':<10} Source / Executable")
    print("-" * 74)
    for t in tools:
        loc = t.get("source") or t.get("executable") or "-"
        ver = t.get("version") or "-"
        print(f"{str(t['name']):<20} {str(t['status']):<11} {str(ver):<10} {loc}")


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="List installed and locally generated CLI-Anything tools."
    )
    parser.add_argument("--path", default=".", help="Directory to scan for generated harnesses (default: .)")
    parser.add_argument("--depth", type=int, default=None, help="Maximum directory recursion depth")
    parser.add_argument("--json", dest="use_json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--include-hub",
        action="store_true",
        help="Include cli-anything-hub package manager alongside harnesses",
    )
    args = parser.parse_args(argv)

    base = Path(args.path)
    if not base.exists() or not base.is_dir():
        msg = f"Path not found: {args.path}"
        if args.use_json:
            print(json.dumps({"error": msg}))
        else:
            print(f"Error: {msg}", file=sys.stderr)
        return 1

    payload = collect_tools(base, max_depth=args.depth, include_hub=args.include_hub)
    if args.use_json:
        print(json.dumps(payload, indent=2))
    else:
        _print_table(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
