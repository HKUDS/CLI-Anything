#!/usr/bin/env python3
"""Deterministic contract verifier for CLI-Anything harnesses.

Checks a harness directory against the structural, packaging, CLI surface,
testing, skill, and code-quality requirements in `HARNESS.md`,
`commands/validate.md`, and `CONTRIBUTING.md`.

Uses Python standard library only so it runs cleanly in any environment
(Windows, macOS, Linux, CI, or offline sandboxes).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PASS = "pass"
WARN = "warn"
FAIL = "fail"


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


@dataclass
class CheckResult:
    id: str
    category: str
    status: str  # "pass" | "warn" | "fail"
    detail: str
    severity: str = "error"  # "error" | "warn"

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "category": self.category,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
        }


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _slugify(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _find_repo_root(start: Path) -> Path | None:
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "cli-anything-plugin" / "HARNESS.md").is_file():
            return candidate
        if (candidate / "registry.json").is_file() and (candidate / "skills").is_dir():
            return candidate
    return None


def _find_canonical_repl_skin(
    explicit: Path | None,
    repo_root: Path | None,
) -> Path | None:
    if explicit is not None and explicit.is_file():
        return explicit.resolve()

    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "repl_skin.py",
        script_dir.parent / "scripts" / "repl_skin.py",
    ]
    if repo_root is not None:
        candidates.append(repo_root / "cli-anything-plugin" / "repl_skin.py")

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def resolve_harness_dir(path: Path) -> tuple[Path, str]:
    """Resolve <software>/, <software>/agent-harness/, or cli_anything/<pkg>/ to (harness_dir, software_dir_name)."""
    p = path.resolve()
    if p.name == "agent-harness" and p.is_dir():
        return p, p.parent.name
    if (p / "agent-harness").is_dir():
        return (p / "agent-harness").resolve(), p.name
    if (p / "cli_anything").is_dir():
        return p, p.parent.name if p.name == "agent-harness" else p.name
    for parent in p.parents:
        if parent.name == "agent-harness":
            return parent, parent.parent.name
    return p, p.name


def _iter_python_files(root: Path) -> list[Path]:
    skip_dirs = {"__pycache__", ".pytest_cache", ".venv", "venv", "build", "dist", ".git"}
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        try:
            rel_parts = path.relative_to(root).parts[:-1]
        except ValueError:
            rel_parts = ()
        if any(part in skip_dirs or part.endswith(".egg-info") for part in rel_parts):
            continue
        files.append(path)
    return files


def _parse_frontmatter(text: str) -> dict[str, str] | None:
    norm = _normalize_lf(text)
    if not norm.startswith("---\n"):
        return None
    end = norm.find("\n---", 4)
    if end == -1:
        return None
    block = norm[4:end]
    result: dict[str, str] = {}
    current_key: str | None = None
    multiline_parts: list[str] = []

    def _flush() -> None:
        nonlocal current_key, multiline_parts
        if current_key is not None and multiline_parts:
            result[current_key] = " ".join(p.strip() for p in multiline_parts if p.strip())
        current_key = None
        multiline_parts = []

    for line in block.splitlines():
        if current_key is not None and (line.startswith(" ") or line.startswith("\t")):
            multiline_parts.append(line.strip())
            continue
        _flush()
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val in (">", ">-", "|", "|-"):
            current_key = key
            multiline_parts = []
        else:
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            result[key] = val
    _flush()
    return result


def _check_layout(harness: Path) -> tuple[list[CheckResult], Path | None]:
    checks: list[CheckResult] = []
    ns_root = harness / "cli_anything"
    if not ns_root.is_dir():
        checks.append(CheckResult("namespace-package", "layout", FAIL, "missing cli_anything/ namespace root"))
        return checks, None

    if (ns_root / "__init__.py").exists():
        checks.append(
            CheckResult(
                "namespace-package",
                "layout",
                FAIL,
                "PEP 420 violation: cli_anything/__init__.py must NOT exist",
            )
        )
    else:
        checks.append(
            CheckResult("namespace-package", "layout", PASS, "cli_anything/ is a valid PEP 420 namespace package")
        )

    candidates = [
        d for d in sorted(ns_root.iterdir())
        if d.is_dir() and not d.name.startswith((".", "_")) and not d.name.endswith(".egg-info")
    ]
    pkg_dirs = [d for d in candidates if (d / "__init__.py").is_file()]
    if not pkg_dirs:
        checks.append(
            CheckResult("module-dir", "layout", FAIL, "no sub-package with __init__.py under cli_anything/")
        )
        return checks, None

    module = pkg_dirs[0]
    checks.append(CheckResult("module-dir", "layout", PASS, f"sub-package found: cli_anything/{module.name}"))

    missing_subdirs = [sub for sub in ("core", "utils", "tests") if not (module / sub).is_dir()]
    if missing_subdirs:
        checks.append(
            CheckResult(
                "subdirs",
                "layout",
                FAIL,
                f"missing required subdirectories: {', '.join(missing_subdirs)}",
            )
        )
    else:
        checks.append(CheckResult("subdirs", "layout", PASS, "core/, utils/, and tests/ directories present"))

    cli_files = sorted(module.glob("*_cli.py"))
    if cli_files:
        checks.append(CheckResult("cli-entrypoint-file", "layout", PASS, f"CLI entry file: {cli_files[0].name}"))
    else:
        checks.append(CheckResult("cli-entrypoint-file", "layout", FAIL, "missing <software>_cli.py entry file"))

    if (module / "__main__.py").is_file():
        checks.append(CheckResult("dunder-main", "layout", PASS, "__main__.py present"))
    else:
        checks.append(
            CheckResult(
                "dunder-main",
                "layout",
                WARN,
                "missing __main__.py (recommended for python -m cli_anything.<software>)",
                severity="warn",
            )
        )

    return checks, module


def _call_func_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _const_str_list(node: ast.AST) -> list[str] | None:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out: list[str] = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
            else:
                return None
        return out
    return None


def _parse_ini_console_scripts(ini_text: str) -> list[str]:
    scripts: list[str] = []
    in_section = False
    for raw in ini_text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_section = line[1:-1].strip() == "console_scripts"
            continue
        if in_section and "=" in line:
            scripts.append(line.split("=", 1)[0].strip())
    return scripts


def _inspect_setup_py(text: str) -> dict[str, Any]:
    """Inspect setup.py via AST for PEP 420 namespace packaging and console_scripts."""
    info: dict[str, Any] = {
        "namespace_ok": False,
        "uses_regular_find_packages": False,
        "console_scripts": [],
    }
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return info

    # Collect simple module-level assignments so setup(packages=PKGS, entry_points=EPS) resolves cleanly.
    bindings: dict[str, ast.AST] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            bindings[stmt.targets[0].id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            bindings[stmt.target.id] = stmt.value

    def _resolve(node: ast.AST) -> ast.AST:
        seen: set[str] = set()
        cur = node
        while isinstance(cur, ast.Name) and cur.id in bindings and cur.id not in seen:
            seen.add(cur.id)
            cur = bindings[cur.id]
        return cur

    def _check_packages_expr(expr: ast.AST) -> None:
        node = _resolve(expr)
        if isinstance(node, ast.Call):
            fname = _call_func_name(node.func)
            if fname == "find_namespace_packages":
                inc_kw = next((kw.value for kw in node.keywords if kw.arg == "include"), None)
                if inc_kw is None:
                    info["namespace_ok"] = True
                else:
                    inc_vals = _const_str_list(_resolve(inc_kw))
                    if inc_vals is None or any(_matches_namespace_include(v) for v in inc_vals):
                        info["namespace_ok"] = True
            elif fname == "find_packages":
                info["uses_regular_find_packages"] = True
        else:
            explicit = _const_str_list(node)
            if explicit and any(re.match(r"^cli_anything\.[A-Za-z0-9_]+", pkg) for pkg in explicit):
                info["namespace_ok"] = True

    def _extract_entry_points(expr: ast.AST) -> None:
        node = _resolve(expr)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "console_scripts":
                    vals = _const_str_list(_resolve(v))
                    if vals:
                        for spec in vals:
                            if "=" in spec:
                                info["console_scripts"].append(spec.split("=", 1)[0].strip())
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            info["console_scripts"].extend(_parse_ini_console_scripts(node.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node.func) == "setup":
            for kw in node.keywords:
                if kw.arg == "packages":
                    _check_packages_expr(kw.value)
                elif kw.arg == "entry_points":
                    _extract_entry_points(kw.value)

    return info


def _matches_namespace_include(pattern: str) -> bool:
    """Return True if a setuptools find include glob covers cli_anything.* subpackages."""
    return pattern == "*" or pattern == "cli_anything*" or pattern.startswith("cli_anything.")


def _strip_toml_comment(line: str) -> str:
    """Remove an unquoted TOML `# ...` comment from a line."""
    in_quote: str | None = None
    escaped = False
    for idx, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if in_quote == '"' and ch == "\\":
            escaped = True
            continue
        if ch in {'"', "'"}:
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
        elif ch == "#" and in_quote is None:
            return line[:idx]
    return line


def _bracket_balance(line: str) -> int:
    """Return net square-bracket depth change outside quoted TOML strings."""
    in_quote: str | None = None
    escaped = False
    delta = 0
    for ch in line:
        if escaped:
            escaped = False
            continue
        if in_quote == '"' and ch == "\\":
            escaped = True
            continue
        if ch in {'"', "'"}:
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
        elif in_quote is None:
            if ch == "[":
                delta += 1
            elif ch == "]":
                delta -= 1
    return delta


def _inspect_pyproject_toml_fallback(text: str) -> dict[str, Any]:
    """Python 3.10 stdlib fallback parser for pyproject.toml without tomllib."""
    info: dict[str, Any] = {
        "namespace_ok": False,
        "namespaces_disabled": False,
        "declares_packages": False,
        "has_project_table": False,
        "scripts_dynamic": False,
        "console_scripts": [],
    }

    logical_lines: list[str] = []
    pending = ""
    depth = 0
    for raw in text.splitlines():
        cleaned = _strip_toml_comment(raw).strip()
        if not cleaned:
            continue
        if depth > 0:
            pending = f"{pending} {cleaned}"
            depth += _bracket_balance(cleaned)
            if depth <= 0:
                logical_lines.append(pending)
                pending = ""
                depth = 0
        elif cleaned.startswith("[") and cleaned.endswith("]") and "=" not in cleaned:
            logical_lines.append(cleaned)
        else:
            line_depth = _bracket_balance(cleaned)
            if line_depth > 0:
                pending = cleaned
                depth = line_depth
            else:
                logical_lines.append(cleaned)
    if pending:
        logical_lines.append(pending)

    section = ""
    saw_find = False
    find_has_include = False
    find_include_ok = False
    script_sections = {
        "project.scripts",
        "project.entry-points.console_scripts",
        'project.entry-points."console_scripts"',
        "project.entry-points.'console_scripts'",
        "tool.poetry.scripts",
    }

    for line in logical_lines:
        if line.startswith("[") and line.endswith("]") and "=" not in line:
            section = line[1:-1].strip()
            if section == "project" or section.startswith("project."):
                info["has_project_table"] = True
            if section == "tool.setuptools.packages.find":
                info["declares_packages"] = True
                saw_find = True
            continue

        if section == "project" and re.match(r"^dynamic\s*=", line):
            rhs = line.split("=", 1)[1]
            if "scripts" in re.findall(r"""["']([^"']+)["']""", rhs):
                info["scripts_dynamic"] = True
        elif section == "tool.setuptools.packages.find":
            if re.match(r"^namespaces\s*=\s*false\b", line):
                info["declares_packages"] = True
                info["namespaces_disabled"] = True
            elif re.match(r"^include\s*=", line):
                find_has_include = True
                rhs = line.split("=", 1)[1]
                vals = re.findall(r"""["']([^"']+)["']""", rhs)
                if any(_matches_namespace_include(v) for v in vals):
                    find_include_ok = True
        elif section == "tool.setuptools" and re.match(r"^packages\s*=", line):
            info["declares_packages"] = True
            rhs = line.split("=", 1)[1]
            vals = re.findall(r"""["']([^"']+)["']""", rhs)
            if any(re.match(r"^cli_anything\.[A-Za-z0-9_]+", v) for v in vals):
                info["namespace_ok"] = True
        elif section == "tool.hatch.build.targets.wheel" and re.match(r"^packages\s*=", line):
            info["declares_packages"] = True
            rhs = line.split("=", 1)[1]
            vals = re.findall(r"""["']([^"']+)["']""", rhs)
            if any("cli_anything" in v for v in vals):
                info["namespace_ok"] = True
        elif section == "tool.poetry" and re.match(r"^packages\s*=", line):
            info["declares_packages"] = True
            rhs = line.split("=", 1)[1]
            if re.search(r"""include\s*=\s*["'][^"']*cli_anything[^"']*["']""", rhs):
                info["namespace_ok"] = True
        elif section in script_sections and "=" in line:
            key = line.split("=", 1)[0].strip().strip('"').strip("'")
            if key:
                info["console_scripts"].append(key)

    if saw_find and not info["namespaces_disabled"] and (not find_has_include or find_include_ok):
        info["namespace_ok"] = True

    return info


def _inspect_pyproject_toml(text: str) -> dict[str, Any]:
    """Inspect pyproject.toml for PEP 420 namespace packaging and console scripts."""
    info: dict[str, Any] = {
        "namespace_ok": False,
        "namespaces_disabled": False,
        "declares_packages": False,
        "has_project_table": False,
        "scripts_dynamic": False,
        "console_scripts": [],
    }
    try:
        import tomllib  # Python 3.11+

        data = tomllib.loads(text)
    except ImportError:
        return _inspect_pyproject_toml_fallback(text)
    except Exception:
        return info

    tool = data.get("tool") if isinstance(data, dict) else None
    tool_dict = tool if isinstance(tool, dict) else {}

    setuptools_cfg = tool_dict.get("setuptools")
    if isinstance(setuptools_cfg, dict):
        pkgs = setuptools_cfg.get("packages")
        if isinstance(pkgs, dict) and isinstance(pkgs.get("find"), dict):
            info["declares_packages"] = True
            find_cfg = pkgs["find"]
            if find_cfg.get("namespaces") is False:
                info["namespaces_disabled"] = True
            elif "include" not in find_cfg:
                info["namespace_ok"] = True
            else:
                includes = find_cfg["include"]
                if isinstance(includes, list) and any(
                    isinstance(v, str) and _matches_namespace_include(v)
                    for v in includes
                ):
                    info["namespace_ok"] = True
        elif isinstance(pkgs, list):
            info["declares_packages"] = True
            if any(
                isinstance(p, str) and re.match(r"^cli_anything\.[A-Za-z0-9_]+", p)
                for p in pkgs
            ):
                info["namespace_ok"] = True

    hatch_cfg = tool_dict.get("hatch")
    hatch_build = hatch_cfg.get("build") if isinstance(hatch_cfg, dict) else None
    hatch_targets = hatch_build.get("targets") if isinstance(hatch_build, dict) else None
    hatch_wheel = hatch_targets.get("wheel") if isinstance(hatch_targets, dict) else None
    hatch_pkgs = hatch_wheel.get("packages") if isinstance(hatch_wheel, dict) else None
    if isinstance(hatch_pkgs, list):
        info["declares_packages"] = True
        if any(isinstance(p, str) and "cli_anything" in p for p in hatch_pkgs):
            info["namespace_ok"] = True

    poetry_cfg = tool_dict.get("poetry")
    poetry_pkgs = poetry_cfg.get("packages") if isinstance(poetry_cfg, dict) else None
    if isinstance(poetry_pkgs, list):
        info["declares_packages"] = True
        if any(
            isinstance(p, dict) and "cli_anything" in str(p.get("include", ""))
            for p in poetry_pkgs
        ):
            info["namespace_ok"] = True

    project_cfg = data.get("project") if isinstance(data, dict) else None
    if isinstance(project_cfg, dict):
        info["has_project_table"] = True
        dynamic = project_cfg.get("dynamic")
        if isinstance(dynamic, list) and "scripts" in dynamic:
            info["scripts_dynamic"] = True
        scripts = project_cfg.get("scripts")
        if isinstance(scripts, dict):
            info["console_scripts"].extend(str(k) for k in scripts.keys())
        ep = project_cfg.get("entry-points")
        if isinstance(ep, dict) and isinstance(ep.get("console_scripts"), dict):
            info["console_scripts"].extend(str(k) for k in ep["console_scripts"].keys())

    poetry_scripts = poetry_cfg.get("scripts") if isinstance(poetry_cfg, dict) else None
    if isinstance(poetry_scripts, dict):
        info["console_scripts"].extend(str(k) for k in poetry_scripts.keys())

    return info


def _check_packaging(harness: Path, software_slug: str, module: Path | None) -> list[CheckResult]:
    checks: list[CheckResult] = []
    setup_py = harness / "setup.py"
    pyproject = harness / "pyproject.toml"
    has_setup = setup_py.is_file()
    has_pyproject = pyproject.is_file()
    pkg_file = setup_py if has_setup else (pyproject if has_pyproject else None)
    if pkg_file is None:
        return [CheckResult("packaging-file", "packaging", FAIL, "missing setup.py (or pyproject.toml)")]

    checks.append(CheckResult("packaging-file", "packaging", PASS, f"{pkg_file.name} present"))
    setup_text = _read_text(setup_py) if has_setup else ""
    pyproject_text = _read_text(pyproject) if has_pyproject else ""
    combined_text = setup_text + "\n" + pyproject_text

    setup_info = _inspect_setup_py(setup_text) if has_setup else {
        "namespace_ok": False,
        "uses_regular_find_packages": False,
        "console_scripts": [],
    }
    pyproj_info = _inspect_pyproject_toml(pyproject_text) if has_pyproject else {
        "namespace_ok": False,
        "namespaces_disabled": False,
        "declares_packages": False,
        "has_project_table": False,
        "scripts_dynamic": False,
        "console_scripts": [],
    }

    # In setuptools >= 61, pyproject.toml [tool.setuptools.packages*] takes precedence over setup.py.
    if pyproj_info["namespaces_disabled"]:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                "pyproject.toml sets [tool.setuptools.packages.find] namespaces = false (overrides setup.py and breaks PEP 420 discovery)",
            )
        )
    elif pyproj_info["declares_packages"]:
        if pyproj_info["namespace_ok"]:
            checks.append(CheckResult("namespace-packages", "packaging", PASS, "namespace package discovery configured in pyproject.toml"))
        else:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    "pyproject.toml declares package discovery/packages without cli_anything.* namespace coverage",
                )
            )
    elif setup_info["uses_regular_find_packages"] and not setup_info["namespace_ok"]:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                "setup.py uses find_packages() instead of find_namespace_packages() (PEP 420 cli_anything/ has no __init__.py)",
            )
        )
    elif setup_info["namespace_ok"]:
        checks.append(CheckResult("namespace-packages", "packaging", PASS, "namespace package discovery configured"))
    else:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                f"{pkg_file.name} does not declare namespace packaging for cli_anything.*",
            )
        )

    expected_prefixes = {f"cli-anything-{software_slug}"}
    if module is not None:
        expected_prefixes.add(f"cli-anything-{_slugify(module.name)}")
    # Under PEP 621 / setuptools >= 61, a [project] table supersedes setup.py entry_points
    # unless "scripts" is explicitly listed in project.dynamic.
    if pyproj_info["has_project_table"] and not pyproj_info["scripts_dynamic"]:
        declared_scripts = list(pyproj_info["console_scripts"])
    else:
        declared_scripts = list(pyproj_info["console_scripts"]) + list(setup_info["console_scripts"])
    matching_scripts = [
        s
        for s in declared_scripts
        if s in expected_prefixes or re.match(r"^cli-anything-[a-z0-9_-]+$", s)
    ]
    if matching_scripts:
        checks.append(
            CheckResult(
                "console-script",
                "packaging",
                PASS,
                f"console_scripts entry point declared: {matching_scripts[0]}",
            )
        )
    else:
        if pyproj_info["has_project_table"] and not pyproj_info["scripts_dynamic"] and setup_info["console_scripts"]:
            detail = (
                "pyproject.toml defines [project] without scripts (and without 'scripts' in project.dynamic), "
                "so setup.py console_scripts are ignored by setuptools"
            )
        else:
            detail = f"{pkg_file.name} does not declare console_scripts entry point cli-anything-{software_slug}"
        checks.append(
            CheckResult(
                "console-script",
                "packaging",
                FAIL,
                detail,
            )
        )

    if "skills/*.md" in combined_text or ("skills" in combined_text and ("package_data" in combined_text or "include_package_data" in combined_text or "package-data" in combined_text)):
        checks.append(CheckResult("package-data-skills", "packaging", PASS, "packaged SKILL.md included in package data"))
    else:
        checks.append(
            CheckResult(
                "package-data-skills",
                "packaging",
                WARN,
                f"{pkg_file.name} may not ship skills/*.md in package_data",
                severity="warn",
            )
        )

    if "python_requires" in combined_text or "requires-python" in combined_text:
        checks.append(CheckResult("python-requires", "packaging", PASS, "Python version requirement specified"))
    else:
        checks.append(
            CheckResult("python-requires", "packaging", WARN, "python_requires not declared", severity="warn")
        )

    return checks


def _check_cli_surface(
    module: Path,
    canonical_repl_skin: Path | None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    cli_files = sorted(module.glob("*_cli.py"))
    cli_text = "\n".join(_read_text(p) for p in cli_files)

    if cli_files:
        if "click" in cli_text and ("@click.group" in cli_text or "click.group" in cli_text):
            checks.append(CheckResult("click-groups", "cli", PASS, "uses Click command groups"))
        else:
            checks.append(CheckResult("click-groups", "cli", FAIL, "CLI does not declare a Click command group"))

        if '"--json"' in cli_text or "'--json'" in cli_text:
            checks.append(CheckResult("json-flag", "cli", PASS, "--json output flag declared"))
        else:
            checks.append(CheckResult("json-flag", "cli", FAIL, "missing --json flag in CLI entry point"))

        if "invoke_without_command=True" in cli_text:
            checks.append(CheckResult("repl-default", "cli", PASS, "default REPL mode configured (invoke_without_command=True)"))
        else:
            checks.append(
                CheckResult(
                    "repl-default",
                    "cli",
                    WARN,
                    "invoke_without_command=True not found in CLI entry point",
                    severity="warn",
                )
            )

        has_session = (module / "core" / "session.py").is_file()
        has_project_flag = '"--project"' in cli_text or "'--project'" in cli_text
        if has_session and has_project_flag:
            has_dry_run = '"--dry-run"' in cli_text or "'--dry-run'" in cli_text
            has_autosave = "result_callback" in cli_text or "call_on_close" in cli_text
            if has_dry_run and has_autosave:
                checks.append(CheckResult("auto-save-dry-run", "cli", PASS, "auto-save and --dry-run implemented"))
            else:
                checks.append(
                    CheckResult(
                        "auto-save-dry-run",
                        "cli",
                        WARN,
                        "session-based CLI should implement auto-save callback and --dry-run (see guides/auto-save-dry-run.md)",
                        severity="warn",
                    )
                )

    repl_skin = module / "utils" / "repl_skin.py"
    if not repl_skin.is_file():
        checks.append(CheckResult("repl-skin", "cli", FAIL, "missing utils/repl_skin.py"))
    elif canonical_repl_skin is None:
        checks.append(
            CheckResult(
                "repl-skin",
                "cli",
                WARN,
                "utils/repl_skin.py present; canonical repl_skin.py not located for byte comparison",
                severity="warn",
            )
        )
    else:
        if _normalize_lf(_read_text(repl_skin)) == _normalize_lf(_read_text(canonical_repl_skin)):
            checks.append(CheckResult("repl-skin", "cli", PASS, "utils/repl_skin.py matches canonical copy"))
        else:
            checks.append(
                CheckResult(
                    "repl-skin",
                    "cli",
                    WARN,
                    "utils/repl_skin.py differs from canonical cli-anything-plugin/repl_skin.py",
                    severity="warn",
                )
            )

    utils_dir = module / "utils"
    backends = sorted(utils_dir.glob("*_backend.py")) if utils_dir.is_dir() else []
    if backends:
        checks.append(CheckResult("backend-wrapper", "cli", PASS, f"backend wrapper present: {backends[0].name}"))
    else:
        checks.append(
            CheckResult(
                "backend-wrapper",
                "cli",
                WARN,
                "no utils/*_backend.py found (verify real software backend integration)",
                severity="warn",
            )
        )

    return checks


def _check_docs_and_tests(
    harness: Path,
    software_dir_name: str,
    module: Path,
    repo_root: Path | None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    if (module / "README.md").is_file():
        checks.append(CheckResult("readme-md", "docs", PASS, "package README.md present"))
    else:
        checks.append(CheckResult("readme-md", "docs", FAIL, "missing cli_anything/<software>/README.md"))

    sop_files = [
        p for p in sorted(harness.glob("*.md"))
        if p.name.upper() not in ("HARNESS.MD", "README.MD")
    ]
    if sop_files:
        checks.append(CheckResult("software-sop", "docs", PASS, f"SOP document present: {sop_files[0].name}"))
    else:
        checks.append(CheckResult("software-sop", "docs", FAIL, "missing agent-harness/<SOFTWARE>.md SOP document"))

    if (harness / "HARNESS.md").is_file():
        checks.append(
            CheckResult(
                "no-duplicate-harness",
                "docs",
                WARN,
                "duplicate HARNESS.md inside agent-harness/ (should reference plugin's HARNESS.md)",
                severity="warn",
            )
        )
    else:
        checks.append(CheckResult("no-duplicate-harness", "docs", PASS, "no duplicate HARNESS.md in agent-harness/"))

    tests_dir = module / "tests"
    test_md = tests_dir / "TEST.md"
    if test_md.is_file() and _read_text(test_md).strip():
        test_md_text = _read_text(test_md)
        checks.append(CheckResult("test-md", "tests", PASS, "tests/TEST.md present"))
        if re.search(r"(test results|\d+\s+passed)", test_md_text, re.IGNORECASE):
            checks.append(CheckResult("test-md-results", "tests", PASS, "TEST.md includes recorded test results"))
        else:
            checks.append(
                CheckResult(
                    "test-md-results",
                    "tests",
                    WARN,
                    "TEST.md does not appear to contain appended pytest results yet",
                    severity="warn",
                )
            )
    else:
        checks.append(CheckResult("test-md", "tests", FAIL, "missing or empty tests/TEST.md"))

    test_core = tests_dir / "test_core.py"
    if test_core.is_file() and "def test_" in _read_text(test_core):
        checks.append(CheckResult("unit-tests", "tests", PASS, "tests/test_core.py present with unit tests"))
    else:
        checks.append(CheckResult("unit-tests", "tests", FAIL, "missing tests/test_core.py with test functions"))

    test_e2e = tests_dir / "test_full_e2e.py"
    if test_e2e.is_file():
        e2e_text = _read_text(test_e2e)
        checks.append(CheckResult("e2e-tests", "tests", PASS, "tests/test_full_e2e.py present"))
        if "_resolve_cli" in e2e_text and "CLI_ANYTHING_FORCE_INSTALLED" in e2e_text:
            checks.append(
                CheckResult(
                    "subprocess-resolve-cli",
                    "tests",
                    PASS,
                    "E2E tests use _resolve_cli() with CLI_ANYTHING_FORCE_INSTALLED",
                )
            )
        else:
            checks.append(
                CheckResult(
                    "subprocess-resolve-cli",
                    "tests",
                    WARN,
                    "test_full_e2e.py missing _resolve_cli() / CLI_ANYTHING_FORCE_INSTALLED subprocess pattern",
                    severity="warn",
                )
            )
    else:
        checks.append(CheckResult("e2e-tests", "tests", FAIL, "missing tests/test_full_e2e.py"))

    pkg_skill = module / "skills" / "SKILL.md"
    if pkg_skill.is_file():
        checks.append(CheckResult("packaged-skill", "skills", PASS, "packaged cli_anything/<software>/skills/SKILL.md present"))
        fm = _parse_frontmatter(_read_text(pkg_skill))
        if fm and fm.get("name") and fm.get("description"):
            if fm["description"].rstrip().endswith("..."):
                checks.append(
                    CheckResult(
                        "skill-frontmatter",
                        "skills",
                        WARN,
                        "packaged SKILL.md description ends with truncated '...' (consider rewriting cleanly)",
                        severity="warn",
                    )
                )
            else:
                checks.append(CheckResult("skill-frontmatter", "skills", PASS, f"SKILL.md frontmatter valid (name={fm['name']})"))
        else:
            checks.append(
                CheckResult("skill-frontmatter", "skills", FAIL, "packaged SKILL.md missing YAML frontmatter name/description")
            )
    else:
        checks.append(
            CheckResult(
                "packaged-skill",
                "skills",
                WARN,
                "missing packaged cli_anything/<software>/skills/SKILL.md (run Phase 6.5 skill_generator.py)",
                severity="warn",
            )
        )

    skills_base = repo_root if repo_root is not None else harness.parent.parent
    slug_candidates = [
        f"cli-anything-{_slugify(software_dir_name)}",
        f"cli-anything-{_slugify(module.name)}",
    ]
    found_root_skill = None
    for slug in slug_candidates:
        cand = skills_base / "skills" / slug / "SKILL.md"
        if cand.is_file():
            found_root_skill = cand
            break
    if found_root_skill is not None:
        rel_skill = found_root_skill.relative_to(skills_base)
        if pkg_skill.is_file() and _normalize_lf(_read_text(found_root_skill)) != _normalize_lf(_read_text(pkg_skill)):
            checks.append(
                CheckResult(
                    "root-skill-mirror",
                    "skills",
                    WARN,
                    f"canonical skill ({rel_skill}) differs from packaged cli_anything/{module.name}/skills/SKILL.md",
                    severity="warn",
                )
            )
        else:
            checks.append(CheckResult("root-skill-mirror", "skills", PASS, f"canonical skill synced: {rel_skill}"))
    elif repo_root is not None:
        checks.append(
            CheckResult(
                "root-skill-mirror",
                "skills",
                WARN,
                f"canonical repo-root skill missing (expected skills/{slug_candidates[0]}/SKILL.md)",
                severity="warn",
            )
        )

    return checks


def _check_code_quality(harness: Path) -> list[CheckResult]:
    checks: list[CheckResult] = []
    py_files = _iter_python_files(harness)
    syntax_errors: list[str] = []
    bare_excepts: list[str] = []
    hardcoded_roots: list[str] = []

    for py_file in py_files:
        text = _read_text(py_file)
        rel = str(py_file.relative_to(harness))
        if "/root/cli-anything/" in text:
            hardcoded_roots.append(rel)
        try:
            tree = ast.parse(text, filename=str(py_file))
        except SyntaxError as exc:
            syntax_errors.append(f"{rel}:{exc.lineno}: {exc.msg}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare_excepts.append(f"{rel}:{node.lineno}")

    if syntax_errors:
        checks.append(CheckResult("python-syntax", "quality", FAIL, f"syntax errors: {'; '.join(syntax_errors[:3])}"))
    else:
        checks.append(CheckResult("python-syntax", "quality", PASS, f"all {len(py_files)} Python files parse cleanly"))

    if bare_excepts:
        checks.append(
            CheckResult(
                "no-bare-except",
                "quality",
                WARN,
                f"bare except: found at {', '.join(bare_excepts[:5])}",
                severity="warn",
            )
        )
    else:
        checks.append(CheckResult("no-bare-except", "quality", PASS, "no bare except: clauses"))

    if hardcoded_roots:
        checks.append(
            CheckResult(
                "no-hardcoded-root",
                "quality",
                WARN,
                f"hardcoded '/root/cli-anything/' found in {', '.join(hardcoded_roots[:3])}",
                severity="warn",
            )
        )
    else:
        checks.append(CheckResult("no-hardcoded-root", "quality", PASS, "no hardcoded /root/cli-anything/ paths"))

    return checks


def verify_harness(
    target_path: Path,
    *,
    strict: bool = False,
    canonical_repl_skin: Path | None = None,
) -> dict[str, object]:
    harness, software_dir_name = resolve_harness_dir(target_path)
    repo_root = _find_repo_root(harness)
    repl_skin_ref = _find_canonical_repl_skin(canonical_repl_skin, repo_root)

    checks, module = _check_layout(harness)
    checks.extend(_check_packaging(harness, _slugify(software_dir_name), module))
    if module is not None:
        checks.extend(_check_cli_surface(module, repl_skin_ref))
        checks.extend(_check_docs_and_tests(harness, software_dir_name, module, repo_root))
    checks.extend(_check_code_quality(harness))

    errors = [c for c in checks if c.status == FAIL and c.severity == "error"]
    warnings = [c for c in checks if c.status in (FAIL, WARN) and c.severity == "warn"]
    passed = [c for c in checks if c.status == PASS]
    ok = (len(errors) == 0) and (not strict or len(warnings) == 0)

    return {
        "software": software_dir_name,
        "harness_path": str(harness),
        "module": module.name if module is not None else None,
        "ok": ok,
        "passed": len(passed),
        "warnings": len(warnings),
        "errors": len(errors),
        "total": len(checks),
        "checks": [c.as_dict() for c in checks],
    }


def discover_harnesses(root: Path) -> list[Path]:
    found: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        candidate = child / "agent-harness"
        if candidate.is_dir() and (candidate / "cli_anything").is_dir():
            found.append(candidate)
    return found


def _print_human(results: Iterable[dict[str, object]]) -> None:
    items = list(results)
    for res in items:
        status_label = "PASS" if res["ok"] else "FAIL"
        print(
            f"\n[{status_label}] {res['software']} ({res['harness_path']}) "
            f"— {res['passed']}/{res['total']} passed, {res['warnings']} warn, {res['errors']} error"
        )
        for check in res["checks"]:  # type: ignore[index]
            marker = {"pass": "  ok  ", "warn": " warn ", "fail": " fail "}[check["status"]]
            print(f"  {marker} {check['id']:<24} {check['detail']}")
    if len(items) > 1:
        ok_count = sum(1 for r in items if r["ok"])
        print(f"\nSummary: {ok_count}/{len(items)} harnesses passed.")


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Deterministically verify CLI-Anything harness contract compliance."
    )
    parser.add_argument("paths", nargs="*", help="Path(s) to <software>/ or <software>/agent-harness/")
    parser.add_argument("--all", action="store_true", help="Discover and verify all harnesses under CWD or repo root")
    parser.add_argument("--json", dest="use_json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument(
        "--canonical-repl-skin",
        type=Path,
        default=None,
        help="Optional explicit path to canonical repl_skin.py",
    )
    args = parser.parse_args(argv)

    targets: list[Path] = []
    if args.all:
        base = Path(args.paths[0]).resolve() if args.paths else (_find_repo_root(Path.cwd()) or Path.cwd())
        targets = discover_harnesses(base)
    elif args.paths:
        targets = [Path(p) for p in args.paths]
    else:
        parser.error("provide at least one harness path or pass --all")

    results = [
        verify_harness(t, strict=args.strict, canonical_repl_skin=args.canonical_repl_skin)
        for t in targets
    ]
    overall_ok = all(r["ok"] for r in results) if results else False

    if args.use_json:
        print(json.dumps({"ok": overall_ok, "count": len(results), "harnesses": results}, indent=2))
    else:
        if not results:
            print("No CLI-Anything harnesses found.")
        else:
            _print_human(results)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
