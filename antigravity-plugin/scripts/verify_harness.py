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
import configparser
import fnmatch
import importlib.util
import json
import keyword
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

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


def _parse_ini_console_scripts(ini_text: str) -> list[tuple[str, str]]:
    scripts: list[tuple[str, str]] = []
    in_section = False
    for raw in ini_text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_section = line[1:-1].strip() == "console_scripts"
            continue
        if in_section and "=" in line:
            name, target = line.split("=", 1)
            scripts.append((name.strip(), target.strip()))
    return scripts


def _collect_target_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            names.update(_collect_target_names(elt))
    elif isinstance(node, ast.Starred):
        names.update(_collect_target_names(node.value))
    return names


def _module_defines_symbol(py_file: Path, symbol: str) -> tuple[bool, str | None]:
    """Check statically whether py_file defines or imports `symbol` at module scope."""
    try:
        tree = ast.parse(_read_text(py_file), filename=str(py_file))
    except SyntaxError as exc:
        return False, f"syntax error in {py_file.name}: {exc.msg}"

    try_star = getattr(ast, "TryStar", ())
    match_cls = getattr(ast, "Match", ())

    def _is_dunder_main_guard(test: ast.AST) -> bool:
        if (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
        ):
            left, right = test.left, test.comparators[0]
            return (
                isinstance(left, ast.Name)
                and left.id == "__name__"
                and isinstance(right, ast.Constant)
                and right.value == "__main__"
            ) or (
                isinstance(right, ast.Name)
                and right.id == "__name__"
                and isinstance(left, ast.Constant)
                and left.value == "__main__"
            )
        return False

    def _scan_stmts(stmts: list[ast.stmt]) -> bool:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if stmt.name == symbol:
                    return True
            elif isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if symbol in _collect_target_names(tgt):
                        return True
            elif isinstance(stmt, ast.AnnAssign):
                if stmt.value is not None and symbol in _collect_target_names(stmt.target):
                    return True
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    if bound == symbol:
                        return True
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    if alias.name == "*":
                        return True
                    bound = alias.asname or alias.name
                    if bound == symbol:
                        return True
            elif isinstance(stmt, ast.If):
                if _is_dunder_main_guard(stmt.test):
                    if _scan_stmts(stmt.orelse):
                        return True
                elif _scan_stmts(stmt.body) or _scan_stmts(stmt.orelse):
                    return True
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                if symbol in _collect_target_names(stmt.target):
                    return True
                if _scan_stmts(stmt.body) or _scan_stmts(stmt.orelse):
                    return True
            elif isinstance(stmt, ast.While):
                if _scan_stmts(stmt.body) or _scan_stmts(stmt.orelse):
                    return True
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    if item.optional_vars is not None and symbol in _collect_target_names(item.optional_vars):
                        return True
                if _scan_stmts(stmt.body):
                    return True
            elif isinstance(stmt, ast.Try) or (try_star and isinstance(stmt, try_star)):
                if _scan_stmts(stmt.body) or _scan_stmts(stmt.orelse) or _scan_stmts(stmt.finalbody):
                    return True
                for handler in stmt.handlers:
                    if handler.name == symbol or _scan_stmts(handler.body):
                        return True
            elif match_cls and isinstance(stmt, match_cls):
                for case in stmt.cases:
                    if _scan_stmts(case.body):
                        return True
        return False

    if _scan_stmts(tree.body):
        return True, None
    return False, f"attribute '{symbol}' not defined or imported in {py_file.name}"


def _is_windows_path_semantics() -> bool:
    """Return True when the host treats backslash as a path separator (Windows)."""
    return os.sep == "\\"


def _normalize_platform_seps(raw: str) -> str:
    """Convert backslashes to '/' only on Windows, preserving literal '\\' on POSIX."""
    return raw.replace("\\", "/") if _is_windows_path_semantics() else raw


def _norm_pkg_dir_value(raw: str) -> str:
    """Normalize a package_dir / where path like setuptools convert_path() (preserving bare '.' and spaces)."""
    cleaned = _normalize_platform_seps(raw)
    if not cleaned:
        return ""
    return PurePosixPath(cleaned).as_posix()


def _get_package_dir_rel(package: str, package_dir: dict[str, str]) -> str:
    """Mirror distutils.command.build_py.get_package_dir() returning a POSIX relative path."""
    parts = [p for p in package.split(".") if p]
    if not package_dir:
        return "/".join(parts)
    tail: list[str] = []
    while parts:
        key = ".".join(parts)
        if key in package_dir:
            pdir = _norm_pkg_dir_value(package_dir[key])
            return "/".join([pdir, *tail]) if pdir else "/".join(tail)
        tail.insert(0, parts.pop())
    root_dir = package_dir.get("")
    if root_dir is not None:
        pdir = _norm_pkg_dir_value(root_dir)
        return "/".join([pdir, *tail]) if pdir else "/".join(tail)
    return "/".join(tail)


def _find_discovered_packages(
    root: Path,
    includes: list[str] | None,
    excludes: list[str] | None,
) -> list[str]:
    """Mirror setuptools.discovery.PEP420PackageFinder.find()."""
    if not root.is_dir():
        return []
    inc_patterns = ["*"] if includes is None else includes
    exc_patterns = ["ez_setup", "*__pycache__"] + (list(excludes) if excludes else [])
    found: list[str] = []

    for cur_root, dirs, _ in os.walk(str(root), followlinks=True):
        all_dirs = sorted(dirs)
        dirs[:] = []
        for d in all_dirs:
            if "." in d:
                continue
            full_path = os.path.join(cur_root, d)
            rel_path = os.path.relpath(full_path, str(root))
            package = rel_path.replace(os.path.sep, ".")
            is_excluded = any(fnmatch.fnmatchcase(package, pat) for pat in exc_patterns)
            is_included = any(fnmatch.fnmatchcase(package, pat) for pat in inc_patterns)
            if is_included and not is_excluded:
                found.append(package)
            if f"{package}*" in exc_patterns or f"{package}.*" in exc_patterns:
                continue
            dirs.append(d)
    return found


def _remove_nested_packages(packages: list[str]) -> list[str]:
    """Mirror setuptools.discovery.remove_nested_packages()."""
    pkgs = sorted(packages, key=len)
    top_level = pkgs[:]
    size = len(pkgs)
    for i, name in enumerate(reversed(pkgs)):
        if any(name.startswith(f"{other}.") for other in top_level):
            top_level.pop(size - i - 1)
    return top_level


def _apply_find_package_dir(
    harness: Path | None,
    base_pkg_dir: dict[str, str],
    pkg_spec: dict[str, Any] | None,
) -> dict[str, str]:
    """Mirror setuptools.config.expand.find_packages() + construct_package_dir().

    For each non-root `where` entry not already covered by `package_dir[""]`, discovers
    selected packages via PEP 420 finder semantics, collapses nested descendants to their
    top-most selected ancestors (`remove_nested_packages`), and updates `package_dir` so
    later roots override ancestor mappings identically to setuptools.
    """
    out = dict(base_pkg_dir)
    if not pkg_spec or pkg_spec.get("kind") != "find" or not pkg_spec.get("fills_package_dir"):
        return out
    wheres = pkg_spec.get("wheres")
    if not wheres:
        return out

    search: list[str] = []
    for raw_w in wheres:
        norm_w = _norm_pkg_dir_value(raw_w) or "."
        if norm_w not in search:
            search.append(norm_w)

    def _is_harness_root(rel: str) -> bool:
        if rel in {"", "."}:
            return True
        if harness is not None:
            try:
                return (harness / rel).resolve() == harness.resolve()
            except OSError:
                return False
        return False

    if len(search) == 1 and not _is_harness_root(search[0]):
        out.setdefault("", search[0])

    if harness is None:
        return out

    includes = pkg_spec.get("includes")
    excludes = pkg_spec.get("excludes")

    for path in search:
        if _norm_pkg_dir_value(out.get("", "")) == path or _is_harness_root(path):
            continue
        pkgs = _find_discovered_packages(harness / path, includes, excludes)
        if pkgs:
            for top_pkg in _remove_nested_packages(pkgs):
                pkg_sub = top_pkg.replace(".", "/")
                out[top_pkg] = f"{path}/{pkg_sub}" if path not in {"", "."} else pkg_sub
    return out


def _collect_runtime_subpackages(pkg_dir: Path, target_pkg: str) -> list[str]:
    """Collect runtime subpackage dotted names under pkg_dir (excluding tests/ and skills/)."""
    skip_top = {"tests", "skills"}
    skip_dirs = {"__pycache__", ".pytest_cache", ".venv", "venv", "build", "dist", ".git"}
    found: list[str] = []

    def _walk(cur: Path, prefix: str, depth: int) -> None:
        try:
            entries = sorted(cur.iterdir())
        except OSError:
            return
        for child in entries:
            if not child.is_dir():
                continue
            name = child.name
            if name.startswith(".") or name in skip_dirs or name.endswith(".egg-info"):
                continue
            if depth == 0 and name in skip_top:
                continue
            if not name.isidentifier() or keyword.iskeyword(name):
                continue
            sub_pkg = f"{prefix}.{name}"
            has_py = any(p.is_file() for p in child.glob("*.py"))
            if (depth == 0 and name in {"core", "utils"}) or has_py:
                found.append(sub_pkg)
            _walk(child, sub_pkg, depth + 1)

    _walk(pkg_dir, target_pkg, 0)
    return found


def _validate_console_script_target(
    target_spec: str,
    harness: Path,
    target_pkg: str | None,
    *,
    parent_selected: bool = False,
    pkg_spec: dict[str, Any] | None = None,
    base_package_dir: dict[str, str] | None = None,
) -> tuple[bool, str, Path | None]:
    """Validate that a console_scripts target resolves to an importable harness callable."""
    spec = target_spec.strip()
    m = re.match(r"^(?P<module>[^:\s\[]+)\s*:\s*(?P<attr>[^:\s\[]+)(?:\s*\[[^\]]*\])?\s*$", spec)
    if not m:
        return False, "expected 'module.path:callable'", None

    module_path = m.group("module")
    attr_path = m.group("attr")
    mod_parts = module_path.split(".")
    attr_parts = attr_path.split(".")
    if not all(p.isidentifier() and not keyword.iskeyword(p) for p in mod_parts):
        return False, f"invalid module path '{module_path}'", None
    if not all(p.isidentifier() and not keyword.iskeyword(p) for p in attr_parts):
        return False, f"invalid callable path '{attr_path}'", None

    if target_pkg and module_path != target_pkg and not module_path.startswith(f"{target_pkg}."):
        return False, f"module '{module_path}' is outside harness package '{target_pkg}'", None

    parent_pkg = ".".join(mod_parts[:-1])
    eff_pkg_dir = _apply_find_package_dir(
        harness,
        base_package_dir or {},
        pkg_spec,
    )

    pkg_dir_rel = _get_package_dir_rel(module_path, eff_pkg_dir)
    pkg_init = (harness / pkg_dir_rel / "__init__.py") if pkg_dir_rel else (harness / "__init__.py")

    parent_dir_rel = _get_package_dir_rel(parent_pkg, eff_pkg_dir) if parent_pkg else ""
    mod_py = (harness / parent_dir_rel / f"{mod_parts[-1]}.py") if parent_dir_rel else (harness / f"{mod_parts[-1]}.py")

    if pkg_init.is_file():
        mod_file = pkg_init
        owner_pkg = module_path
    elif mod_py.is_file():
        mod_file = mod_py
        owner_pkg = parent_pkg
    else:
        src_hint = parent_dir_rel or "."
        return False, f"module '{module_path}' not found in effective package source directory '{src_hint}'", None

    if target_pkg and parent_selected and owner_pkg != target_pkg and pkg_spec is not None:
        if pkg_spec["kind"] == "find":
            if not _find_selects_package(
                owner_pkg,
                pkg_spec["includes"],
                pkg_spec["excludes"],
                harness=harness,
                wheres=pkg_spec["wheres"],
                require_init=False,
            ):
                return False, f"package '{owner_pkg}' is not selected by packaging discovery", None
        elif pkg_spec["kind"] == "explicit":
            if owner_pkg not in pkg_spec["packages"]:
                return False, f"package '{owner_pkg}' is not listed in packaging packages", None

    ok_sym, sym_err = _module_defines_symbol(mod_file, attr_parts[0])
    if not ok_sym:
        return False, sym_err or f"callable '{attr_parts[0]}' not found in '{module_path}'", None
    return True, "", mod_file


def _package_exists_under(root: Path, target_pkg: str, *, require_init: bool = True) -> bool:
    """Return True if `root/<pkg_parts>` exists on disk (requiring `__init__.py` unless PEP 420 dir)."""
    pkg_dir = root.joinpath(*target_pkg.split("."))
    if not pkg_dir.is_dir():
        return False
    return (pkg_dir / "__init__.py").is_file() if require_init else True


def _find_selects_package(
    target_pkg: str | None,
    includes: list[str] | None,
    excludes: list[str] | None,
    *,
    harness: Path | None = None,
    wheres: list[str] | None = None,
    require_init: bool = True,
) -> bool:
    """Mirror setuptools PEP420PackageFinder where/include/exclude semantics."""
    pkg = target_pkg or "cli_anything._harness"
    included = True if includes is None else any(
        fnmatch.fnmatchcase(pkg, pat) for pat in includes
    )
    if not included:
        return False
    if excludes is not None and any(fnmatch.fnmatchcase(pkg, pat) for pat in excludes):
        return False
    if wheres is not None:
        if not wheres:
            return False
        if harness is not None and target_pkg:
            return any(
                _package_exists_under(harness / root_rel, target_pkg, require_init=require_init)
                for root_rel in wheres
            )
    elif harness is not None and target_pkg:
        return _package_exists_under(harness, target_pkg, require_init=require_init)
    return True


def _explicit_packages_cover(target_pkg: str | None, packages: list[str]) -> bool:
    if target_pkg:
        return target_pkg in packages
    return any(re.match(r"^cli_anything\.[A-Za-z0-9_]+", p) for p in packages)


def _hatch_packages_dir(
    target_pkg: str | None,
    packages: list[str],
    harness: Path | None = None,
) -> dict[str, str] | None:
    """Return effective package_dir mapping if Hatch wheel packages cover target_pkg, else None."""
    mod = target_pkg.split(".", 1)[1] if (target_pkg and "." in target_pkg) else None
    for raw in packages:
        norm = _normalize_platform_seps(raw).strip("/")
        if not norm:
            continue
        if norm == "cli_anything" or norm.endswith("/cli_anything"):
            if harness is None or not mod:
                return {} if norm == "cli_anything" else {"cli_anything": norm}
            if (harness / norm / mod / "__init__.py").is_file():
                return {} if norm == "cli_anything" else {"cli_anything": norm}
        elif mod and (norm == f"cli_anything/{mod}" or norm.endswith(f"/cli_anything/{mod}")):
            if harness is None or (harness / norm / "__init__.py").is_file():
                return {} if norm == f"cli_anything/{mod}" else {target_pkg: norm}  # type: ignore[dict-item]
        elif not mod and ("cli_anything/" in norm):
            return {}
    return None


def _poetry_packages_dir(
    target_pkg: str | None,
    entries: list[tuple[str, str]],
    harness: Path | None = None,
) -> dict[str, str] | None:
    """Return effective package_dir mapping if Poetry packages cover target_pkg, else None."""
    mod = target_pkg.split(".", 1)[1] if (target_pkg and "." in target_pkg) else None
    for raw_inc, raw_from in entries:
        norm = _normalize_platform_seps(raw_inc).strip("/")
        norm_from = _norm_pkg_dir_value(raw_from)
        base_root = (harness / norm_from) if (harness is not None and norm_from not in {"", "."}) else harness
        pkg_dir = {"": norm_from} if norm_from not in {"", "."} else {}
        if norm == "cli_anything":
            if base_root is None or not target_pkg:
                return pkg_dir
            if _package_exists_under(base_root, target_pkg):
                return pkg_dir
        elif mod and norm in {f"cli_anything/{mod}", f"cli_anything.{mod}"}:
            if base_root is None or not target_pkg:
                return pkg_dir
            if _package_exists_under(base_root, target_pkg):
                return pkg_dir
        elif not mod and (norm.startswith("cli_anything/") or norm.startswith("cli_anything.")):
            return pkg_dir
    return None


def _is_absolute_pattern(pattern: str) -> bool:
    """Return True if a glob/path pattern is rooted on the current platform."""
    s = _normalize_platform_seps(pattern)
    if s.startswith("/"):
        return True
    return _is_windows_path_semantics() and bool(re.match(r"^[A-Za-z]:", s))


def _glob_matches_relpath(
    rel_path: str,
    pattern: str,
    *,
    recursive: bool = True,
    platform_case: bool = False,
) -> bool:
    """Match a relative path against a relative glob pattern (`**` matches 0+ dirs when recursive=True).

    Preserves platform separator semantics (`\\` is a separator only on Windows, literal on POSIX)
    and preserves literal leading/trailing whitespace just like setuptools convert_path() + glob().
    """
    if not rel_path or not pattern or _is_absolute_pattern(pattern):
        return False
    rel_raw = _normalize_platform_seps(rel_path)
    pat_raw = _normalize_platform_seps(pattern)
    if pat_raw.endswith("/"):
        return False
    rel_norm = PurePosixPath(rel_raw).as_posix()
    pat_norm = PurePosixPath(pat_raw).as_posix()
    rel_parts = [p for p in rel_norm.split("/") if p]
    pat_parts = [p for p in pat_norm.split("/") if p]
    if not rel_parts or not pat_parts:
        return False

    seg_match = (
        fnmatch.fnmatch
        if (platform_case and _is_windows_path_semantics())
        else fnmatch.fnmatchcase
    )

    if not recursive:
        if len(rel_parts) != len(pat_parts):
            return False
        return all(seg_match(rp, pp) for rp, pp in zip(rel_parts, pat_parts))

    memo: dict[tuple[int, int], bool] = {}

    def _match(ri: int, pi: int) -> bool:
        key = (ri, pi)
        if key in memo:
            return memo[key]
        if pi == len(pat_parts):
            res = ri == len(rel_parts)
        elif pat_parts[pi] == "**":
            # In Python glob(..., recursive=True), `**` matches zero or more path segments.
            res = _match(ri, pi + 1) or (ri < len(rel_parts) and _match(ri + 1, pi))
        elif ri < len(rel_parts) and seg_match(rel_parts[ri], pat_parts[pi]):
            res = _match(ri + 1, pi + 1)
        else:
            res = False
        memo[key] = res
        return res

    return _match(0, 0)


def _pkg_data_matches_file(
    mapping: dict[str, list[str]],
    pkg_name: str,
    rel_path: str,
    *,
    allow_star_wildcard: bool,
    exclusion: bool = False,
) -> bool:
    """Return True if package_data or exclude_package_data rules for pkg_name match rel_path.

    In setuptools:
    - `package_data` expands via `glob(..., recursive=True)` (segment-wise, `**` matches 0+ dirs).
    - `exclude_package_data` filters via `fnmatch.filter()` (platform `normcase`, `*` matches `/`).
    - In `setup.py`, only `""` is the all-packages wildcard; TOML normalizes `"*"` to `""`.
    """
    applicable_keys = {pkg_name, "", "*"} if allow_star_wildcard else {pkg_name, ""}

    def _matches(raw_pat: str) -> bool:
        if not raw_pat or _is_absolute_pattern(raw_pat):
            return False
        pat_raw = _normalize_platform_seps(raw_pat)
        if not pat_raw or pat_raw.endswith("/"):
            return False
        pat = PurePosixPath(pat_raw).as_posix()
        if not pat or pat == ".":
            return False
        if exclusion:
            if _is_windows_path_semantics():
                return fnmatch.fnmatch(rel_path, pat)
            return fnmatch.fnmatchcase(rel_path, pat)
        return _glob_matches_relpath(rel_path, pat, recursive=True, platform_case=True)

    for pkg_key, patterns in mapping.items():
        if pkg_key in applicable_keys and any(_matches(p) for p in patterns):
            return True
    return False


def _normalize_manifest_path(token: str) -> str | None:
    """Mirror distutils.util.convert_path with platform separator semantics, rejecting absolute patterns."""
    if not token or _is_absolute_pattern(token):
        return None
    norm = _normalize_platform_seps(token)
    if not norm:
        return None
    return PurePosixPath(norm).as_posix()


def _setuptools_translate_pattern(glob_pat: str) -> re.Pattern[str]:
    """Mirror setuptools.command.egg_info.translate_pattern() on POSIX-normalized paths.

    Unlike fnmatch/glob, setuptools escapes '-' inside character classes so '[A-Z]'
    matches literal 'A', '-', or 'Z' rather than a character range, and matching is
    always case-sensitive across platforms.
    """
    pat = ""
    chunks = glob_pat.split("/")
    sep = "/"
    valid_char = "[^/]"

    for c, chunk in enumerate(chunks):
        last_chunk = c == len(chunks) - 1
        if chunk == "**":
            if last_chunk:
                pat += ".*"
            else:
                pat += f"(?:{valid_char}+{sep})*"
            continue

        i = 0
        chunk_len = len(chunk)
        while i < chunk_len:
            char = chunk[i]
            if char == "*":
                pat += valid_char + "*"
            elif char == "?":
                pat += valid_char
            elif char == "[":
                inner_i = i + 1
                if inner_i < chunk_len and chunk[inner_i] == "!":
                    inner_i += 1
                if inner_i < chunk_len and chunk[inner_i] == "]":
                    inner_i += 1
                while inner_i < chunk_len and chunk[inner_i] != "]":
                    inner_i += 1
                if inner_i >= chunk_len:
                    pat += re.escape(char)
                else:
                    inner = chunk[i + 1 : inner_i]
                    char_class = ""
                    if inner[0] == "!":
                        char_class = "^"
                        inner = inner[1:]
                    char_class += re.escape(inner)
                    pat += f"[{char_class}]"
                    i = inner_i
            else:
                pat += re.escape(char)
            i += 1

        if not last_chunk:
            pat += sep

    pat += r"\Z"
    return re.compile(pat, flags=re.MULTILINE | re.DOTALL)


def _manifest_covers_skill(
    harness: Path | None,
    expected_manifest_rel: str | None,
) -> bool:
    """Evaluate MANIFEST.in directives in order (mirroring setuptools egg_info.FileList + build_py).

    Tracks the exact relative paths emitted by inclusion directives (e.g. `./...` from
    `recursive-include . <pat>` vs prefix-free paths from `include`/`global-include`/`graft`)
    so regex-backed exclusions and `build_py.analyze_manifest()` path matching mirror setuptools.
    """
    if harness is None or not expected_manifest_rel:
        return False
    manifest = harness / "MANIFEST.in"
    if not manifest.is_file():
        return False

    expected_norm = _normalize_platform_seps(expected_manifest_rel)
    canonical_rel = PurePosixPath(expected_norm).as_posix()
    target_dir_parts = canonical_rel.split("/")[:-1]
    ancestor_dirs = ["/".join(target_dir_parts[: i + 1]) for i in range(len(target_dir_parts))]

    # Join backslash-continued lines and strip `#` comments.
    logical_lines: list[str] = []
    pending = ""
    for raw in _read_text(manifest).splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if pending:
            line = pending + " " + line.lstrip()
            pending = ""
        if line.endswith("\\"):
            pending = line[:-1].rstrip()
            continue
        stripped = line.strip()
        if stripped:
            logical_lines.append(stripped)
    if pending:
        logical_lines.append(pending.strip())

    selected_paths: set[str] = set()
    for line in logical_lines:
        tokens = line.split()
        if len(tokens) < 2:
            continue
        action = tokens[0]
        if action == "include":
            for pat in tokens[1:]:
                p = _normalize_manifest_path(pat)
                if p is not None and p != "." and _glob_matches_relpath(
                    canonical_rel, p, recursive=False, platform_case=True
                ):
                    selected_paths.add(canonical_rel)
                    break
        elif action == "exclude":
            for pat in tokens[1:]:
                p = _normalize_manifest_path(pat)
                if p is not None and selected_paths:
                    rx = _setuptools_translate_pattern(p)
                    selected_paths = {fp for fp in selected_paths if not rx.match(fp)}
        elif action == "global-include":
            for pat in tokens[1:]:
                p = _normalize_manifest_path(pat)
                if p is not None and _setuptools_translate_pattern(f"**/{p}").match(canonical_rel):
                    selected_paths.add(canonical_rel)
                    break
        elif action == "global-exclude":
            for pat in tokens[1:]:
                p = _normalize_manifest_path(pat)
                if p is not None and selected_paths:
                    rx = _setuptools_translate_pattern(f"**/{p}")
                    selected_paths = {fp for fp in selected_paths if not rx.match(fp)}
        elif action == "recursive-include":
            if len(tokens) < 3:
                continue
            d = _normalize_manifest_path(tokens[1])
            if d is None:
                continue
            # glob(os.path.join('.', '**', pat), recursive=True) preserves the leading './' prefix,
            # whereas non-dot directories emit prefix-free paths.
            emitted = f"./{canonical_rel}" if d == "." else canonical_rel
            prefix = "**/" if d == "." else f"{d}/**/"
            for pat in tokens[2:]:
                p = _normalize_manifest_path(pat)
                if p is not None and _glob_matches_relpath(
                    canonical_rel, f"{prefix}{p}", recursive=True, platform_case=True
                ):
                    selected_paths.add(emitted)
                    break
        elif action == "recursive-exclude":
            if len(tokens) < 3:
                continue
            d = _normalize_manifest_path(tokens[1])
            if d is None:
                continue
            for pat in tokens[2:]:
                p = _normalize_manifest_path(pat)
                if p is not None and selected_paths:
                    rx = _setuptools_translate_pattern(f"{d}/**/{p}")
                    selected_paths = {fp for fp in selected_paths if not rx.match(fp)}
        elif action == "graft":
            if len(tokens) != 2:
                continue
            d = _normalize_manifest_path(tokens[1])
            if d is None:
                continue
            # setuptools FileList.graft() calls glob(dir) WITHOUT recursive=True, then
            # distutils.filelist.findall(match_dir) (which strips './' when match_dir == '.').
            if d == "." or any(
                _glob_matches_relpath(anc, d, recursive=False, platform_case=True) for anc in ancestor_dirs
            ):
                selected_paths.add(canonical_rel)
        elif action == "prune":
            if len(tokens) != 2:
                continue
            d = _normalize_manifest_path(tokens[1])
            if d is None:
                continue
            if selected_paths:
                rx = _setuptools_translate_pattern(f"{d}/**")
                selected_paths = {fp for fp in selected_paths if not rx.match(fp)}

    return expected_norm in selected_paths


def _classify_build_backend(build_backend: str | None) -> str:
    if not build_backend:
        return "setuptools"  # PEP 517 default when [build-system].build-backend is omitted
    norm = build_backend.strip().lower()
    if norm == "setuptools" or norm.startswith("setuptools."):
        return "setuptools"
    if norm == "hatchling" or norm.startswith("hatchling."):
        return "hatch"
    if norm == "poetry" or norm.startswith("poetry."):
        return "poetry"
    return "other"


def _inspect_setup_py(
    text: str,
    target_pkg: str | None = None,
    harness: Path | None = None,
) -> dict[str, Any]:
    """Inspect setup.py via AST for PEP 420 namespace packaging and console_scripts."""
    info: dict[str, Any] = {
        "namespace_ok": False,
        "skills_subpkg_ok": False,
        "uses_regular_find_packages": False,
        "declares_packages": False,
        "pkg_spec": None,
        "package_dir": {},
        "has_entry_points": False,
        "console_scripts": [],
        "package_data": {},
        "exclude_package_data": {},
        "include_package_data": None,
        "has_python_requires": False,
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
                where_kw = next((kw.value for kw in node.keywords if kw.arg == "where"), None)
                exc_kw = next((kw.value for kw in node.keywords if kw.arg == "exclude"), None)
                inc_kw = next((kw.value for kw in node.keywords if kw.arg == "include"), None)
                if where_kw is None and len(node.args) >= 1:
                    where_kw = node.args[0]
                if exc_kw is None and len(node.args) >= 2:
                    exc_kw = node.args[1]
                if inc_kw is None and len(node.args) >= 3:
                    inc_kw = node.args[2]

                wheres: list[str] | None = ["."]
                dynamic_where = False
                if where_kw is not None:
                    resolved_where = _resolve(where_kw)
                    if isinstance(resolved_where, ast.Constant) and isinstance(resolved_where.value, str):
                        wheres = [resolved_where.value]
                    else:
                        # Dynamic where expression (e.g., os.path.dirname(__file__)); avoid false failures.
                        wheres = None
                        dynamic_where = True

                includes: list[str] | None = None
                if inc_kw is not None:
                    inc_vals = _const_str_list(_resolve(inc_kw))
                    if inc_vals is not None:
                        includes = inc_vals

                excludes: list[str] | None = None
                if exc_kw is not None:
                    exc_vals = _const_str_list(_resolve(exc_kw))
                    if exc_vals is not None:
                        excludes = exc_vals

                info["declares_packages"] = True
                info["pkg_spec"] = {
                    "kind": "find",
                    "includes": includes,
                    "excludes": excludes,
                    "wheres": wheres,
                    "dynamic_where": dynamic_where,
                    "fills_package_dir": False,
                }
                if _find_selects_package(
                    target_pkg,
                    includes,
                    excludes,
                    harness=harness,
                    wheres=wheres,
                ):
                    info["namespace_ok"] = True
                if target_pkg and _find_selects_package(
                    f"{target_pkg}.skills",
                    includes,
                    excludes,
                    harness=harness,
                    wheres=wheres,
                    require_init=False,
                ):
                    info["skills_subpkg_ok"] = True
            elif fname == "find_packages":
                info["declares_packages"] = True
                info["uses_regular_find_packages"] = True
        else:
            explicit = _const_str_list(node)
            if explicit is not None:
                info["declares_packages"] = bool(explicit)
                info["pkg_spec"] = {"kind": "explicit", "packages": explicit}
            if explicit and _explicit_packages_cover(target_pkg, explicit):
                info["namespace_ok"] = True
            if explicit and target_pkg and f"{target_pkg}.skills" in explicit:
                info["skills_subpkg_ok"] = True

    def _extract_entry_points(expr: ast.AST) -> None:
        node = _resolve(expr)
        if isinstance(node, ast.Dict):
            if node.keys:
                info["has_entry_points"] = True
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "console_scripts":
                    vals = _const_str_list(_resolve(v))
                    if vals:
                        for spec in vals:
                            if "=" in spec:
                                name, target = spec.split("=", 1)
                                info["console_scripts"].append((name.strip(), target.strip()))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value:
                info["has_entry_points"] = True
            info["console_scripts"].extend(_parse_ini_console_scripts(node.value))

    def _extract_pkg_data_mapping(expr: ast.AST, dest: dict[str, list[str]]) -> None:
        node = _resolve(expr)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    vals = _const_str_list(_resolve(v))
                    if vals is not None:
                        dest[k.value] = vals

    def _extract_str_mapping(expr: ast.AST, dest: dict[str, str]) -> None:
        node = _resolve(expr)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    val = _resolve(v)
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        dest[k.value] = val.value

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node.func) == "setup":
            for kw in node.keywords:
                if kw.arg == "packages":
                    _check_packages_expr(kw.value)
                elif kw.arg == "package_dir":
                    _extract_str_mapping(kw.value, info["package_dir"])
                elif kw.arg == "entry_points":
                    _extract_entry_points(kw.value)
                elif kw.arg == "package_data":
                    _extract_pkg_data_mapping(kw.value, info["package_data"])
                elif kw.arg == "exclude_package_data":
                    _extract_pkg_data_mapping(kw.value, info["exclude_package_data"])
                elif kw.arg == "include_package_data":
                    val = _resolve(kw.value)
                    if isinstance(val, ast.Constant) and isinstance(val.value, bool):
                        info["include_package_data"] = val.value
                elif kw.arg == "python_requires":
                    val = _resolve(kw.value)
                    if isinstance(val, ast.Constant) and isinstance(val.value, str) and val.value.strip():
                        info["has_python_requires"] = True

    return info


def _load_toml_fallback_module() -> Any:
    mod = sys.modules.get("_cli_anything_toml_fallback")
    if mod is None:
        mod_path = Path(__file__).resolve().parent / "_toml_fallback.py"
        spec = importlib.util.spec_from_file_location("_cli_anything_toml_fallback", mod_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load TOML fallback parser at {mod_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_cli_anything_toml_fallback"] = mod
        spec.loader.exec_module(mod)
    return mod


_TOML_FALLBACK_MOD = _load_toml_fallback_module()
_TomlFallbackParser = _TOML_FALLBACK_MOD._TomlFallbackParser


def _loads_toml_fallback(text: str) -> dict[str, Any]:
    """Parse TOML text into Python dicts/lists without tomllib (Python 3.10 fallback)."""
    return _TOML_FALLBACK_MOD.loads_toml_fallback(text)


def _empty_pyproject_info() -> dict[str, Any]:
    return {
        "parse_error": None,
        "build_backend": None,
        "backend_kind": "setuptools",
        "namespace_ok": False,
        "skills_subpkg_ok": False,
        "namespaces_disabled": False,
        "declares_packages": False,
        "pkg_spec": None,
        "declares_package_dir": False,
        "package_dir": {},
        "has_project_table": False,
        "scripts_dynamic": False,
        "dynamic_scripts_defined": False,
        "dynamic_scripts_error": None,
        "requires_python_dynamic": False,
        "reserved_console_scripts_ep": False,
        "console_scripts": [],
        "declares_package_data": False,
        "package_data": {},
        "declares_exclude_package_data": False,
        "exclude_package_data": {},
        "include_package_data": None,
        "has_python_requires": False,
    }


def _parse_entry_points_ini_groups(text: str) -> dict[str, dict[str, str]]:
    """Mirror setuptools.config.expand.entry_points() INI parsing."""
    parser = configparser.ConfigParser(default_section=None, delimiters=("=",), interpolation=None)  # type: ignore[call-overload]
    parser.optionxform = str  # type: ignore[assignment]
    parser.read_string(text)
    groups = {k: dict(v.items()) for k, v in parser.items()}
    groups.pop(parser.default_section, None)
    return groups


def _read_local_config_files(
    harness: Path | None,
    file_entries: list[str],
    specifier: str,
) -> tuple[str | None, str | None]:
    """Read file(s) constrained inside harness root (mirroring setuptools expand.read_files)."""
    if harness is None:
        return None, f"cannot resolve {specifier} without harness root"
    root_resolved = harness.resolve()
    chunks: list[str] = []
    for raw_rel in file_entries:
        rel = _normalize_platform_seps(raw_rel)
        if not rel or _is_absolute_pattern(rel):
            return None, f"{specifier} path must be relative to harness root: {raw_rel!r}"
        cand = harness / rel
        try:
            cand_resolved = cand.resolve()
            cand_resolved.relative_to(root_resolved)
        except (OSError, ValueError):
            return None, f"{specifier} path escapes harness root: {raw_rel!r}"
        if not cand.is_file():
            return None, f"{specifier} file not found: {raw_rel}"
        chunks.append(_read_text(cand))
    return "\n".join(chunks), None


def _inspect_pyproject_toml_fallback(
    text: str,
    target_pkg: str | None = None,
    harness: Path | None = None,
) -> dict[str, Any]:
    """Python 3.10 stdlib fallback path using the stdlib TOML parser + shared inspection logic."""
    try:
        data = _loads_toml_fallback(text)
    except Exception as exc:
        info = _empty_pyproject_info()
        info["parse_error"] = str(exc) or exc.__class__.__name__
        return info
    return _inspect_pyproject_data(data, target_pkg=target_pkg, harness=harness)


def _inspect_pyproject_toml(
    text: str,
    target_pkg: str | None = None,
    harness: Path | None = None,
) -> dict[str, Any]:
    """Inspect pyproject.toml for PEP 420 namespace packaging and console scripts."""
    try:
        import tomllib  # Python 3.11+

        data = tomllib.loads(text)
    except ImportError:
        return _inspect_pyproject_toml_fallback(text, target_pkg=target_pkg, harness=harness)
    except Exception as exc:
        info = _empty_pyproject_info()
        info["parse_error"] = str(exc) or exc.__class__.__name__
        return info
    return _inspect_pyproject_data(data, target_pkg=target_pkg, harness=harness)


def _inspect_pyproject_data(
    data: Any,
    target_pkg: str | None = None,
    harness: Path | None = None,
) -> dict[str, Any]:
    info = _empty_pyproject_info()
    if not isinstance(data, dict):
        return info

    build_system = data.get("build-system")
    raw_backend = build_system.get("build-backend") if isinstance(build_system, dict) else None
    build_backend = raw_backend.strip() if isinstance(raw_backend, str) and raw_backend.strip() else None
    backend_kind = _classify_build_backend(build_backend)
    info["build_backend"] = build_backend
    info["backend_kind"] = backend_kind

    tool = data.get("tool")
    tool_dict = tool if isinstance(tool, dict) else {}

    if backend_kind == "setuptools":
        setuptools_cfg = tool_dict.get("setuptools")
        if isinstance(setuptools_cfg, dict):
            if isinstance(setuptools_cfg.get("include-package-data"), bool):
                info["include_package_data"] = setuptools_cfg["include-package-data"]
            pkg_dir_cfg = setuptools_cfg.get("package-dir")
            if isinstance(pkg_dir_cfg, dict):
                info["declares_package_dir"] = True
                for pk, pv in pkg_dir_cfg.items():
                    if isinstance(pk, str) and isinstance(pv, str):
                        info["package_dir"][pk] = pv
            pkg_data_cfg = setuptools_cfg.get("package-data")
            if isinstance(pkg_data_cfg, dict):
                info["declares_package_data"] = True
                for pk, pv in pkg_data_cfg.items():
                    if isinstance(pk, str) and isinstance(pv, list):
                        info["package_data"][pk] = [x for x in pv if isinstance(x, str)]
            excl_data_cfg = setuptools_cfg.get("exclude-package-data")
            if isinstance(excl_data_cfg, dict):
                info["declares_exclude_package_data"] = True
                for pk, pv in excl_data_cfg.items():
                    if isinstance(pk, str) and isinstance(pv, list):
                        info["exclude_package_data"][pk] = [x for x in pv if isinstance(x, str)]
            pkgs = setuptools_cfg.get("packages")
            if isinstance(pkgs, dict) and isinstance(pkgs.get("find"), dict):
                info["declares_packages"] = True
                find_cfg = pkgs["find"]
                if find_cfg.get("namespaces") is False:
                    info["namespaces_disabled"] = True
                else:
                    if "where" not in find_cfg:
                        wheres: list[str] | None = None
                    elif isinstance(find_cfg["where"], list):
                        wheres = [v for v in find_cfg["where"] if isinstance(v, str)]
                    elif isinstance(find_cfg["where"], str):
                        wheres = [find_cfg["where"]]
                    else:
                        wheres = []

                    if "include" not in find_cfg:
                        includes: list[str] | None = None
                    elif isinstance(find_cfg["include"], list):
                        includes = [v for v in find_cfg["include"] if isinstance(v, str)]
                    else:
                        includes = []
                    excludes_raw = find_cfg.get("exclude")
                    excludes = (
                        [v for v in excludes_raw if isinstance(v, str)]
                        if isinstance(excludes_raw, list)
                        else None
                    )
                    info["pkg_spec"] = {
                        "kind": "find",
                        "includes": includes,
                        "excludes": excludes,
                        "wheres": wheres,
                        "fills_package_dir": True,
                    }
                    if _find_selects_package(
                        target_pkg,
                        includes,
                        excludes,
                        harness=harness,
                        wheres=wheres,
                    ):
                        info["namespace_ok"] = True
                    if target_pkg and _find_selects_package(
                        f"{target_pkg}.skills",
                        includes,
                        excludes,
                        harness=harness,
                        wheres=wheres,
                        require_init=False,
                    ):
                        info["skills_subpkg_ok"] = True
            elif isinstance(pkgs, list):
                info["declares_packages"] = True
                str_pkgs = [p for p in pkgs if isinstance(p, str)]
                info["pkg_spec"] = {"kind": "explicit", "packages": str_pkgs}
                if _explicit_packages_cover(target_pkg, str_pkgs):
                    info["namespace_ok"] = True
                if target_pkg and f"{target_pkg}.skills" in str_pkgs:
                    info["skills_subpkg_ok"] = True
    elif backend_kind == "hatch":
        hatch_cfg = tool_dict.get("hatch")
        hatch_build = hatch_cfg.get("build") if isinstance(hatch_cfg, dict) else None
        hatch_targets = hatch_build.get("targets") if isinstance(hatch_build, dict) else None
        hatch_wheel = hatch_targets.get("wheel") if isinstance(hatch_targets, dict) else None
        hatch_pkgs = hatch_wheel.get("packages") if isinstance(hatch_wheel, dict) else None
        if isinstance(hatch_pkgs, list):
            info["declares_packages"] = True
            str_pkgs = [p for p in hatch_pkgs if isinstance(p, str)]
            hatch_pkg_dir = _hatch_packages_dir(target_pkg, str_pkgs, harness=harness)
            if hatch_pkg_dir is not None:
                info["namespace_ok"] = True
                info["package_dir"].update(hatch_pkg_dir)
    elif backend_kind == "poetry":
        poetry_cfg = tool_dict.get("poetry")
        poetry_deps = poetry_cfg.get("dependencies") if isinstance(poetry_cfg, dict) else None
        if isinstance(poetry_deps, dict) and "python" in poetry_deps:
            info["has_python_requires"] = True
        poetry_pkgs = poetry_cfg.get("packages") if isinstance(poetry_cfg, dict) else None
        if isinstance(poetry_pkgs, list):
            info["declares_packages"] = True
            pkg_entries = [
                (
                    str(p["include"]),
                    str(p.get("from", ".")) if isinstance(p.get("from", "."), str) else ".",
                )
                for p in poetry_pkgs
                if isinstance(p, dict) and isinstance(p.get("include"), str)
            ]
            poetry_pkg_dir = _poetry_packages_dir(target_pkg, pkg_entries, harness=harness)
            if poetry_pkg_dir is not None:
                info["namespace_ok"] = True
                info["package_dir"].update(poetry_pkg_dir)

    project_cfg = data.get("project")
    dynamic_fields: set[str] = set()
    if isinstance(project_cfg, dict):
        info["has_project_table"] = True
        req_py = project_cfg.get("requires-python")
        if isinstance(req_py, str) and req_py.strip():
            info["has_python_requires"] = True
        dynamic = project_cfg.get("dynamic")
        if isinstance(dynamic, list):
            dynamic_fields = {d for d in dynamic if isinstance(d, str)}
            if "scripts" in dynamic_fields:
                info["scripts_dynamic"] = True
            if "requires-python" in dynamic_fields:
                info["requires_python_dynamic"] = True
        scripts = project_cfg.get("scripts")
        if isinstance(scripts, dict):
            for k, v in scripts.items():
                target_val = v.strip() if isinstance(v, str) else ""
                info["console_scripts"].append((str(k).strip(), target_val))
        ep = project_cfg.get("entry-points")
        if isinstance(ep, dict) and "console_scripts" in ep:
            # PEP 621 reserves console_scripts for [project.scripts]; setuptools drops
            # [project.entry-points.console_scripts] and resets legacy setup.py scripts.
            info["reserved_console_scripts_ep"] = True

    # Mirror setuptools _ConfigExpander._obtain_entry_points() for [tool.setuptools.dynamic].entry-points.
    if backend_kind == "setuptools" and info["has_project_table"]:
        setuptools_cfg = tool_dict.get("setuptools")
        dynamic_cfg = setuptools_cfg.get("dynamic") if isinstance(setuptools_cfg, dict) else None
        if (
            isinstance(dynamic_cfg, dict)
            and "entry-points" in dynamic_cfg
            and any(f in dynamic_fields for f in ("entry-points", "scripts", "gui-scripts"))
        ):
            directive = dynamic_cfg["entry-points"]
            if isinstance(directive, dict) and "file" in directive:
                raw_files = directive["file"]
                if isinstance(raw_files, str):
                    file_list = [raw_files]
                elif isinstance(raw_files, list) and raw_files and all(isinstance(x, str) for x in raw_files):
                    file_list = list(raw_files)
                else:
                    file_list = []
                    info["dynamic_scripts_error"] = (
                        "invalid [tool.setuptools.dynamic].entry-points file directive"
                    )
                if file_list:
                    ep_text, read_err = _read_local_config_files(
                        harness, file_list, "[tool.setuptools.dynamic].entry-points"
                    )
                    if read_err:
                        info["dynamic_scripts_error"] = read_err
                    elif ep_text is not None:
                        try:
                            groups = _parse_entry_points_ini_groups(ep_text)
                        except configparser.Error as exc:
                            info["dynamic_scripts_error"] = (
                                f"invalid [tool.setuptools.dynamic].entry-points INI: {exc}"
                            )
                        else:
                            if "console_scripts" in groups:
                                if "scripts" not in dynamic_fields:
                                    info["dynamic_scripts_error"] = (
                                        "[tool.setuptools.dynamic].entry-points defines [console_scripts], "
                                        "but 'scripts' is not listed in [project].dynamic"
                                    )
                                else:
                                    info["dynamic_scripts_defined"] = True
                                    for k, v in groups["console_scripts"].items():
                                        info["console_scripts"].append((k.strip(), v.strip()))
                            elif groups:
                                # Non-empty entry-points file supersedes legacy setup.py/setup.cfg entry_points.
                                info["dynamic_scripts_defined"] = True
            else:
                info["dynamic_scripts_error"] = (
                    "unsupported [tool.setuptools.dynamic].entry-points directive "
                    "(only file-backed entry-points can be statically verified)"
                )

    if backend_kind == "poetry":
        poetry_cfg = tool_dict.get("poetry")
        poetry_scripts = poetry_cfg.get("scripts") if isinstance(poetry_cfg, dict) else None
        if isinstance(poetry_scripts, dict):
            for k, v in poetry_scripts.items():
                if isinstance(v, str):
                    target_val = v.strip()
                elif isinstance(v, dict):
                    raw_ref = v.get("callable") or v.get("reference")
                    target_val = raw_ref.strip() if isinstance(raw_ref, str) else ""
                else:
                    target_val = ""
                info["console_scripts"].append((str(k).strip(), target_val))

    return info


def _empty_setup_cfg_info() -> dict[str, Any]:
    return {
        "parse_error": None,
        "namespace_ok": False,
        "skills_subpkg_ok": False,
        "uses_regular_find_packages": False,
        "declares_packages": False,
        "pkg_spec": None,
        "package_dir": {},
        "has_entry_points": False,
        "console_scripts": [],
        "package_data": {},
        "exclude_package_data": {},
        "include_package_data": None,
        "has_python_requires": False,
    }


def _parse_setup_cfg_list(raw: str) -> list[str]:
    """Mirror setuptools setup.cfg list parsing (newline- or comma-separated)."""
    if "\n" in raw:
        items = [ln.strip() for ln in raw.splitlines()]
        return [it for it in items if it and not it.startswith(("#", ";"))]
    return [part.strip() for part in raw.split(",") if part.strip()]


def _inspect_setup_cfg(
    text: str,
    target_pkg: str | None = None,
    harness: Path | None = None,
) -> dict[str, Any]:
    """Inspect setuptools setup.cfg for packages, package_dir, package_data, exclusions, and scripts."""
    info = _empty_setup_cfg_info()
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # type: ignore[assignment]
    try:
        cp.read_string(text)
    except configparser.Error as exc:
        info["parse_error"] = str(exc) or exc.__class__.__name__
        return info

    if cp.has_section("options"):
        opts = cp["options"]
        py_req = opts.get("python_requires", "").strip()
        if py_req:
            info["has_python_requires"] = True

        if "include_package_data" in opts:
            raw_inc = opts["include_package_data"].strip().lower()
            if raw_inc in {"true", "1", "yes", "on"}:
                info["include_package_data"] = True
            elif raw_inc in {"false", "0", "no", "off"}:
                info["include_package_data"] = False

        if "package_dir" in opts:
            raw_pd = opts["package_dir"]
            entries = raw_pd.splitlines() if "\n" in raw_pd else raw_pd.split(",")
            for entry in entries:
                s = entry.strip()
                if not s or s.startswith(("#", ";")) or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                info["package_dir"][k.strip()] = v.strip()

        if "packages" in opts:
            raw_pkgs = opts["packages"].strip()
            if raw_pkgs:
                info["declares_packages"] = True
                if raw_pkgs == "find_namespace:":
                    find_sec = cp["options.packages.find"] if cp.has_section("options.packages.find") else {}
                    if "where" in find_sec:
                        w_val = find_sec["where"].strip()
                        wheres: list[str] | None = [w_val] if w_val else ["."]
                    else:
                        wheres = None
                    includes: list[str] | None = (
                        _parse_setup_cfg_list(find_sec["include"]) if "include" in find_sec else None
                    )
                    excludes: list[str] | None = (
                        _parse_setup_cfg_list(find_sec["exclude"]) if "exclude" in find_sec else None
                    )
                    info["pkg_spec"] = {
                        "kind": "find",
                        "includes": includes,
                        "excludes": excludes,
                        "wheres": wheres,
                        "fills_package_dir": True,
                    }
                    if _find_selects_package(
                        target_pkg,
                        includes,
                        excludes,
                        harness=harness,
                        wheres=wheres,
                    ):
                        info["namespace_ok"] = True
                    if target_pkg and _find_selects_package(
                        f"{target_pkg}.skills",
                        includes,
                        excludes,
                        harness=harness,
                        wheres=wheres,
                        require_init=False,
                    ):
                        info["skills_subpkg_ok"] = True
                elif raw_pkgs == "find:":
                    info["uses_regular_find_packages"] = True
                else:
                    explicit = _parse_setup_cfg_list(raw_pkgs)
                    info["pkg_spec"] = {"kind": "explicit", "packages": explicit}
                    if explicit and _explicit_packages_cover(target_pkg, explicit):
                        info["namespace_ok"] = True
                    if explicit and target_pkg and f"{target_pkg}.skills" in explicit:
                        info["skills_subpkg_ok"] = True

    if cp.has_section("options.package_data"):
        for k, v in cp.items("options.package_data"):
            info["package_data"][k.strip()] = _parse_setup_cfg_list(v)

    if cp.has_section("options.exclude_package_data"):
        for k, v in cp.items("options.exclude_package_data"):
            info["exclude_package_data"][k.strip()] = _parse_setup_cfg_list(v)

    if cp.has_section("options.entry_points"):
        raw_cs = cp.get("options.entry_points", "console_scripts", fallback="")
        for ln in raw_cs.splitlines():
            s = ln.strip()
            if not s or s.startswith(("#", ";")) or "=" not in s:
                continue
            name, target = s.split("=", 1)
            info["console_scripts"].append((name.strip(), target.strip()))
    elif cp.has_section("options") and "entry_points" in cp["options"]:
        raw_ep_opt = cp["options"]["entry_points"].strip()
        if raw_ep_opt.startswith("file:"):
            ep_file = raw_ep_opt[len("file:"):].strip()
            ep_text, read_err = _read_local_config_files(harness, [ep_file], "setup.cfg [options] entry_points")
            if not read_err and ep_text is not None:
                try:
                    groups = _parse_entry_points_ini_groups(ep_text)
                except configparser.Error:
                    groups = {}
                for k, v in groups.get("console_scripts", {}).items():
                    info["console_scripts"].append((k.strip(), v.strip()))

    return info


def _check_packaging(
    harness: Path,
    software_slug: str,
    module: Path | None,
) -> tuple[list[CheckResult], Path | None, list[Path], dict[str, Path]]:
    checks: list[CheckResult] = []
    setup_py = harness / "setup.py"
    pyproject = harness / "pyproject.toml"
    setup_cfg = harness / "setup.cfg"
    has_setup = setup_py.is_file()
    has_pyproject = pyproject.is_file()
    has_setup_cfg = setup_cfg.is_file()
    # pip's is_installable_dir() requires setup.py or pyproject.toml; setup.cfg alone is not buildable.
    pkg_file = setup_py if has_setup else (pyproject if has_pyproject else None)
    if pkg_file is None:
        detail = (
            "setup.cfg found without setup.py or pyproject.toml "
            "(pip requires setup.py or pyproject.toml to build/install)"
            if has_setup_cfg
            else "missing setup.py (or pyproject.toml)"
        )
        return [CheckResult("packaging-file", "packaging", FAIL, detail)], module, [], {}

    checks.append(CheckResult("packaging-file", "packaging", PASS, f"{pkg_file.name} present"))
    setup_text = _read_text(setup_py) if has_setup else ""
    pyproject_text = _read_text(pyproject) if has_pyproject else ""
    setup_cfg_text = _read_text(setup_cfg) if has_setup_cfg else ""

    target_pkg = f"cli_anything.{module.name}" if module is not None else None
    target_pkg_label = target_pkg or f"cli_anything.{software_slug.replace('-', '_')}"

    setup_info = _inspect_setup_py(setup_text, target_pkg=target_pkg, harness=harness) if has_setup else {
        "namespace_ok": False,
        "skills_subpkg_ok": False,
        "uses_regular_find_packages": False,
        "declares_packages": False,
        "pkg_spec": None,
        "package_dir": {},
        "has_entry_points": False,
        "console_scripts": [],
        "package_data": {},
        "exclude_package_data": {},
        "include_package_data": None,
        "has_python_requires": False,
    }
    pyproj_info = (
        _inspect_pyproject_toml(pyproject_text, target_pkg=target_pkg, harness=harness)
        if has_pyproject
        else _empty_pyproject_info()
    )

    if has_pyproject and pyproj_info["parse_error"]:
        checks.append(
            CheckResult(
                "pyproject-toml-syntax",
                "packaging",
                FAIL,
                f"invalid pyproject.toml: {pyproj_info['parse_error']}",
            )
        )
        return checks, module, [], {}

    uses_setuptools = not has_pyproject or pyproj_info["backend_kind"] == "setuptools"
    uses_setup_py = has_setup and uses_setuptools
    uses_setup_cfg = has_setup_cfg and uses_setuptools

    setup_cfg_info = (
        _inspect_setup_cfg(setup_cfg_text, target_pkg=target_pkg, harness=harness)
        if uses_setup_cfg
        else _empty_setup_cfg_info()
    )
    if uses_setup_cfg and setup_cfg_info["parse_error"]:
        checks.append(
            CheckResult(
                "setup-cfg-syntax",
                "packaging",
                FAIL,
                f"invalid setup.cfg: {setup_cfg_info['parse_error']}",
            )
        )
        return checks, module, [], {}

    # Determine effective package selection (setuptools precedence: pyproject.toml > setup.py > setup.cfg).
    if pyproj_info["namespaces_disabled"]:
        parent_selected = False
        skills_subpkg_selected = False
        eff_pkg_spec = None
        pkg_source = "pyproject"
    elif pyproj_info["declares_packages"]:
        parent_selected = bool(pyproj_info["namespace_ok"])
        skills_subpkg_selected = bool(pyproj_info["skills_subpkg_ok"])
        eff_pkg_spec = pyproj_info["pkg_spec"]
        pkg_source = "pyproject"
    elif uses_setup_py and setup_info["declares_packages"]:
        parent_selected = bool(setup_info["namespace_ok"])
        skills_subpkg_selected = bool(setup_info["skills_subpkg_ok"])
        eff_pkg_spec = setup_info["pkg_spec"]
        pkg_source = "setup_py"
    elif uses_setup_cfg and setup_cfg_info["declares_packages"]:
        parent_selected = bool(setup_cfg_info["namespace_ok"])
        skills_subpkg_selected = bool(setup_cfg_info["skills_subpkg_ok"])
        eff_pkg_spec = setup_cfg_info["pkg_spec"]
        pkg_source = "setup_cfg"
    else:
        parent_selected = False
        skills_subpkg_selected = False
        eff_pkg_spec = None
        pkg_source = "none"

    if has_pyproject and pyproj_info["backend_kind"] in {"hatch", "poetry"}:
        eff_base_package_dir = dict(pyproj_info["package_dir"])
    elif pyproj_info["declares_package_dir"]:
        eff_base_package_dir = dict(pyproj_info["package_dir"])
    elif uses_setup_py and setup_info["package_dir"]:
        eff_base_package_dir = dict(setup_info["package_dir"])
    elif uses_setup_cfg and setup_cfg_info["package_dir"]:
        eff_base_package_dir = dict(setup_cfg_info["package_dir"])
    else:
        eff_base_package_dir = {}

    eff_package_dir = _apply_find_package_dir(
        harness,
        eff_base_package_dir,
        eff_pkg_spec,
    )

    effective_module = module
    missing_effective_dir: str | None = None
    if target_pkg and parent_selected:
        raw_target_dir = _get_package_dir_rel(target_pkg, eff_package_dir)
        cand_module = (harness / raw_target_dir) if raw_target_dir else module
        if cand_module is not None and cand_module.is_dir():
            effective_module = cand_module
        elif raw_target_dir:
            missing_effective_dir = raw_target_dir

    missing_runtime_subpkgs: list[str] = []
    missing_subpkg_dirs: list[str] = []
    eff_subpkg_dirs: dict[str, Path] = {}

    def _is_subpkg_selected(pkg_name: str) -> bool:
        if eff_pkg_spec is None:
            return True
        if eff_pkg_spec["kind"] == "find":
            return _find_selects_package(
                pkg_name,
                eff_pkg_spec["includes"],
                eff_pkg_spec["excludes"],
                harness=harness,
                wheres=eff_pkg_spec["wheres"],
                require_init=False,
            )
        if eff_pkg_spec["kind"] == "explicit":
            return pkg_name in eff_pkg_spec["packages"]
        return True

    if (
        parent_selected
        and not missing_effective_dir
        and target_pkg
        and effective_module is not None
    ):
        runtime_subpkgs = _collect_runtime_subpackages(effective_module, target_pkg)
        checked_mapped: set[str] = {target_pkg}

        def _check_mapped_pkg_dir(pkg_name: str) -> None:
            if not pkg_name or pkg_name in checked_mapped:
                return
            checked_mapped.add(pkg_name)
            raw_dir = _get_package_dir_rel(pkg_name, eff_package_dir)
            dir_path = (harness / raw_dir) if raw_dir else harness
            if not dir_path.is_dir():
                missing_subpkg_dirs.append(f"{pkg_name} -> '{raw_dir}'")

        for sub_pkg in runtime_subpkgs:
            if eff_pkg_spec is not None and not _is_subpkg_selected(sub_pkg):
                missing_runtime_subpkgs.append(sub_pkg)
                checked_mapped.add(sub_pkg)
                continue
            _check_mapped_pkg_dir(sub_pkg)

        if eff_pkg_spec is not None:
            if eff_pkg_spec["kind"] == "find" and not eff_pkg_spec.get("dynamic_where"):
                scan_wheres = eff_pkg_spec["wheres"] if eff_pkg_spec["wheres"] is not None else ["."]
                for w in scan_wheres:
                    norm_w = _norm_pkg_dir_value(w) or "."
                    for disc_pkg in _find_discovered_packages(
                        harness / norm_w,
                        eff_pkg_spec["includes"],
                        eff_pkg_spec["excludes"],
                    ):
                        if disc_pkg.startswith(f"{target_pkg}."):
                            _check_mapped_pkg_dir(disc_pkg)
            elif eff_pkg_spec["kind"] == "explicit":
                for exp_pkg in eff_pkg_spec["packages"]:
                    if exp_pkg == target_pkg or exp_pkg.startswith(f"{target_pkg}."):
                        _check_mapped_pkg_dir(exp_pkg)

        for mapped_pkg in eff_package_dir:
            if mapped_pkg and mapped_pkg.startswith(f"{target_pkg}.") and _is_subpkg_selected(mapped_pkg):
                _check_mapped_pkg_dir(mapped_pkg)

        if _is_subpkg_selected("cli_anything"):
            _check_mapped_pkg_dir("cli_anything")

        raw_ns = _get_package_dir_rel("cli_anything", eff_package_dir)
        eff_subpkg_dirs["__namespace__"] = (harness / raw_ns) if raw_ns else harness

        for sub_name in ("core", "utils", "tests", "skills"):
            sub_pkg = f"{target_pkg}.{sub_name}"
            if sub_name in ("core", "utils") or _is_subpkg_selected(sub_pkg):
                raw_sub = _get_package_dir_rel(sub_pkg, eff_package_dir)
                eff_subpkg_dirs[sub_name] = (harness / raw_sub) if raw_sub else harness
            else:
                eff_subpkg_dirs[sub_name] = effective_module / sub_name

    # In setuptools >= 61, pyproject.toml [tool.setuptools.packages*] takes precedence over setup.py/setup.cfg.
    # Non-setuptools PEP 517 backends (Hatch, Poetry, etc.) do not execute setup.py or setup.cfg at all.
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
        if pyproj_info["namespace_ok"] and missing_effective_dir:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"effective package directory '{missing_effective_dir}' for {target_pkg_label} does not exist",
                )
            )
        elif pyproj_info["namespace_ok"] and missing_subpkg_dirs:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"mapped source directory missing for selected subpackage(s): {', '.join(missing_subpkg_dirs)}",
                )
            )
        elif pyproj_info["namespace_ok"] and not missing_runtime_subpkgs:
            checks.append(CheckResult("namespace-packages", "packaging", PASS, "namespace package discovery configured in pyproject.toml"))
        elif pyproj_info["namespace_ok"] and missing_runtime_subpkgs:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"pyproject.toml package discovery/packages does not select required runtime subpackage(s): {', '.join(missing_runtime_subpkgs)}",
                )
            )
        else:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"pyproject.toml package discovery/packages does not select {target_pkg_label}",
                )
            )
    elif has_pyproject and pyproj_info["backend_kind"] != "setuptools":
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                f"pyproject.toml uses build-backend '{pyproj_info['build_backend']}' without declaring {target_pkg_label} namespace packages",
            )
        )
    elif pkg_source == "setup_py" and setup_info["uses_regular_find_packages"] and not setup_info["namespace_ok"]:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                "setup.py uses find_packages() instead of find_namespace_packages() (PEP 420 cli_anything/ has no __init__.py)",
            )
        )
    elif pkg_source == "setup_py" and setup_info["namespace_ok"]:
        if missing_effective_dir:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"effective package directory '{missing_effective_dir}' for {target_pkg_label} does not exist",
                )
            )
        elif missing_subpkg_dirs:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"mapped source directory missing for selected subpackage(s): {', '.join(missing_subpkg_dirs)}",
                )
            )
        elif not missing_runtime_subpkgs:
            checks.append(CheckResult("namespace-packages", "packaging", PASS, "namespace package discovery configured"))
        else:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"setup.py package discovery/packages does not select required runtime subpackage(s): {', '.join(missing_runtime_subpkgs)}",
                )
            )
    elif pkg_source == "setup_cfg" and setup_cfg_info["uses_regular_find_packages"] and not setup_cfg_info["namespace_ok"]:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                "setup.cfg uses packages = find: instead of find_namespace: (PEP 420 cli_anything/ has no __init__.py)",
            )
        )
    elif pkg_source == "setup_cfg" and setup_cfg_info["namespace_ok"]:
        if missing_effective_dir:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"effective package directory '{missing_effective_dir}' for {target_pkg_label} does not exist",
                )
            )
        elif missing_subpkg_dirs:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"mapped source directory missing for selected subpackage(s): {', '.join(missing_subpkg_dirs)}",
                )
            )
        elif not missing_runtime_subpkgs:
            checks.append(CheckResult("namespace-packages", "packaging", PASS, "namespace package discovery configured in setup.cfg"))
        else:
            checks.append(
                CheckResult(
                    "namespace-packages",
                    "packaging",
                    FAIL,
                    f"setup.cfg package discovery/packages does not select required runtime subpackage(s): {', '.join(missing_runtime_subpkgs)}",
                )
            )
    else:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                f"{pkg_file.name} does not declare namespace packaging for {target_pkg_label}",
            )
        )

    expected_prefixes = {f"cli-anything-{software_slug}"}
    if module is not None:
        expected_prefixes.add(f"cli-anything-{_slugify(module.name)}")
    # Under PEP 517 / PEP 621: non-setuptools backends ignore setup.py/setup.cfg, setuptools >= 61
    # ignores legacy entry_points whenever [project] omits "scripts" from project.dynamic,
    # [tool.setuptools.dynamic].entry-points supersedes legacy setup.py/setup.cfg scripts, and any
    # truthy setup.py entry_points mapping/string suppresses setup.cfg [options.entry_points].
    legacy_scripts = (
        list(setup_info["console_scripts"])
        if (uses_setup_py and setup_info["has_entry_points"])
        else (list(setup_cfg_info["console_scripts"]) if uses_setup_cfg else [])
    )
    if (
        (not uses_setuptools)
        or pyproj_info["dynamic_scripts_error"]
        or pyproj_info["dynamic_scripts_defined"]
        or (pyproj_info["has_project_table"] and not pyproj_info["scripts_dynamic"])
    ):
        declared_scripts = list(pyproj_info["console_scripts"])
    else:
        declared_scripts = list(pyproj_info["console_scripts"]) + legacy_scripts
    matching_scripts = [
        (name, target)
        for name, target in declared_scripts
        if name in expected_prefixes or re.match(r"^cli-anything-[a-z0-9_-]+$", name)
    ]
    primary_cli_files: list[Path] = []
    all_resolved_cli_files: list[Path] = []
    if pyproj_info["dynamic_scripts_error"]:
        checks.append(
            CheckResult(
                "console-script",
                "packaging",
                FAIL,
                str(pyproj_info["dynamic_scripts_error"]),
            )
        )
    elif matching_scripts:
        invalid_targets: list[str] = []
        for cmd_name, target_spec in matching_scripts:
            ok_target, reason, mod_file = _validate_console_script_target(
                target_spec,
                harness,
                target_pkg,
                parent_selected=parent_selected,
                pkg_spec=eff_pkg_spec,
                base_package_dir=eff_base_package_dir,
            )
            if not ok_target:
                invalid_targets.append(f"{cmd_name}={target_spec} ({reason})")
            elif mod_file is not None:
                if mod_file not in all_resolved_cli_files:
                    all_resolved_cli_files.append(mod_file)
                if cmd_name in expected_prefixes and mod_file not in primary_cli_files:
                    primary_cli_files.append(mod_file)
        if not invalid_targets:
            first_name, first_target = matching_scripts[0]
            checks.append(
                CheckResult(
                    "console-script",
                    "packaging",
                    PASS,
                    f"console_scripts entry point declared: {first_name}={first_target}",
                )
            )
        else:
            checks.append(
                CheckResult(
                    "console-script",
                    "packaging",
                    FAIL,
                    f"console_scripts target invalid: {'; '.join(invalid_targets)}",
                )
            )
    else:
        if pyproj_info["reserved_console_scripts_ep"]:
            detail = (
                "pyproject.toml declares reserved [project.entry-points.console_scripts] instead of [project.scripts] "
                "(rejected/dropped under PEP 621 / setuptools)"
            )
        elif has_pyproject and pyproj_info["backend_kind"] != "setuptools" and (setup_info["console_scripts"] or setup_cfg_info["console_scripts"]):
            detail = (
                f"pyproject.toml uses build-backend '{pyproj_info['build_backend']}' without declaring console scripts "
                "(setup.py/setup.cfg console_scripts are ignored)"
            )
        elif pyproj_info["dynamic_scripts_defined"]:
            detail = (
                "[tool.setuptools.dynamic].entry-points supersedes legacy console_scripts "
                f"without declaring cli-anything-{software_slug}"
            )
        elif pyproj_info["has_project_table"] and not pyproj_info["scripts_dynamic"] and (setup_info["console_scripts"] or setup_cfg_info["console_scripts"]):
            detail = (
                "pyproject.toml defines [project] without scripts (and without 'scripts' in project.dynamic), "
                "so legacy console_scripts are ignored by setuptools"
            )
        elif uses_setup_py and setup_info["has_entry_points"] and not setup_info["console_scripts"] and uses_setup_cfg and setup_cfg_info["console_scripts"]:
            detail = (
                "setup.py passes non-empty entry_points without console_scripts, "
                "so setup.cfg [options.entry_points] is ignored by setuptools"
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
    declared_cli_files = primary_cli_files or all_resolved_cli_files

    skill_data_ok = False
    if has_pyproject and pyproj_info["backend_kind"] in {"hatch", "poetry"}:
        # Hatch and Poetry include non-Python assets inside declared package directories automatically.
        if pyproj_info["namespace_ok"] and target_pkg:
            raw_pkg_dir = _get_package_dir_rel(target_pkg, eff_package_dir)
            skill_path = (
                (harness / raw_pkg_dir / "skills" / "SKILL.md")
                if raw_pkg_dir
                else (harness / "skills" / "SKILL.md")
            )
            skill_data_ok = skill_path.is_file()
        else:
            skill_data_ok = bool(pyproj_info["namespace_ok"])
    else:
        if pyproj_info["declares_package_data"]:
            eff_pkg_data = pyproj_info["package_data"]
            eff_pkg_star = True
        elif uses_setup_py and setup_info["package_data"]:
            eff_pkg_data = setup_info["package_data"]
            eff_pkg_star = False
        elif uses_setup_cfg and setup_cfg_info["package_data"]:
            eff_pkg_data = setup_cfg_info["package_data"]
            eff_pkg_star = True
        else:
            eff_pkg_data = {}
            eff_pkg_star = False

        if pyproj_info["declares_exclude_package_data"]:
            eff_excl_data = pyproj_info["exclude_package_data"]
            eff_excl_star = True
        elif uses_setup_py and setup_info["exclude_package_data"]:
            eff_excl_data = setup_info["exclude_package_data"]
            eff_excl_star = False
        elif uses_setup_cfg and setup_cfg_info["exclude_package_data"]:
            eff_excl_data = setup_cfg_info["exclude_package_data"]
            eff_excl_star = True
        else:
            eff_excl_data = {}
            eff_excl_star = False

        if pyproj_info["include_package_data"] is not None:
            eff_include_pkg_data = bool(pyproj_info["include_package_data"])
        elif uses_setup_py and setup_info["include_package_data"] is True:
            eff_include_pkg_data = True
        elif uses_setup_cfg and setup_cfg_info["include_package_data"] is not None:
            eff_include_pkg_data = bool(setup_cfg_info["include_package_data"])
        elif uses_setup_py and setup_info["include_package_data"] is False:
            eff_include_pkg_data = False
        elif pyproj_info["has_project_table"]:
            # Setuptools >= 61 defaults include-package-data to True for PEP 621 [project] tables.
            eff_include_pkg_data = True
        else:
            eff_include_pkg_data = False

        # Mirror setuptools build_py: analyze_manifest() assigns SKILL.md to the deepest
        # selected package containing it, and exclude_data_files() runs per supplying package.
        suppliers: list[tuple[str, str]] = []
        if target_pkg:
            if parent_selected:
                suppliers.append((target_pkg, "skills/SKILL.md"))
            if skills_subpkg_selected:
                suppliers.append((f"{target_pkg}.skills", "SKILL.md"))

        manifest_owner: str | None = None
        if target_pkg:
            if skills_subpkg_selected:
                skills_dir_rel = _get_package_dir_rel(f"{target_pkg}.skills", eff_package_dir)
                skills_file = (
                    (harness / skills_dir_rel / "SKILL.md")
                    if skills_dir_rel
                    else (harness / "SKILL.md")
                )
                if skills_file.is_file():
                    manifest_owner = f"{target_pkg}.skills"
            if manifest_owner is None and parent_selected:
                manifest_owner = target_pkg

        for pkg_name, rel_path in suppliers:
            raw_pkg_dir = _get_package_dir_rel(pkg_name, eff_package_dir)
            skill_path = (harness / raw_pkg_dir / rel_path) if raw_pkg_dir else (harness / rel_path)
            if not skill_path.is_file():
                continue
            from_pd = _pkg_data_matches_file(
                eff_pkg_data,
                pkg_name,
                rel_path,
                allow_star_wildcard=eff_pkg_star,
                exclusion=False,
            )
            expected_manifest_rel = f"{raw_pkg_dir}/{rel_path}" if raw_pkg_dir else rel_path
            from_manifest = (
                manifest_owner == pkg_name
                and eff_include_pkg_data
                and _manifest_covers_skill(harness, expected_manifest_rel)
            )
            if not (from_pd or from_manifest):
                continue
            excluded = _pkg_data_matches_file(
                eff_excl_data,
                pkg_name,
                rel_path,
                allow_star_wildcard=eff_excl_star,
                exclusion=True,
            )
            if not excluded:
                skill_data_ok = True
                break

    if skill_data_ok:
        checks.append(CheckResult("package-data-skills", "packaging", PASS, f"packaged SKILL.md included in package data for {target_pkg_label}"))
    else:
        checks.append(
            CheckResult(
                "package-data-skills",
                "packaging",
                WARN,
                f"{pkg_file.name} does not declare package_data shipping skills/SKILL.md for {target_pkg_label}",
                severity="warn",
            )
        )

    # Under PEP 621 / setuptools >= 61, [project] ignores legacy setup.py/setup.cfg python_requires
    # unless "requires-python" is explicitly declared in project.dynamic.
    has_legacy_py_req = (uses_setup_py and setup_info["has_python_requires"]) or (
        uses_setup_cfg and setup_cfg_info["has_python_requires"]
    )
    can_use_legacy_py_req = uses_setuptools and (
        not pyproj_info["has_project_table"] or pyproj_info["requires_python_dynamic"]
    )
    if pyproj_info["has_python_requires"] or (can_use_legacy_py_req and has_legacy_py_req):
        checks.append(CheckResult("python-requires", "packaging", PASS, "Python version requirement specified"))
    elif pyproj_info["has_project_table"] and not pyproj_info["requires_python_dynamic"] and has_legacy_py_req:
        checks.append(
            CheckResult(
                "python-requires",
                "packaging",
                WARN,
                "pyproject.toml defines [project] without requires-python (and without 'requires-python' in project.dynamic), so legacy python_requires is ignored by setuptools",
                severity="warn",
            )
        )
    else:
        checks.append(
            CheckResult("python-requires", "packaging", WARN, "python_requires not declared", severity="warn")
        )

    return checks, effective_module, declared_cli_files, eff_subpkg_dirs


def _check_cli_surface(
    module: Path,
    canonical_repl_skin: Path | None,
    *,
    cli_entry_files: list[Path] | None = None,
    subpkg_dirs: dict[str, Path] | None = None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    cli_files = list(cli_entry_files) if cli_entry_files else sorted(module.glob("*_cli.py"))
    core_dir = (subpkg_dirs or {}).get("core") or (module / "core")
    utils_dir = (subpkg_dirs or {}).get("utils") or (module / "utils")

    if cli_files:
        cli_texts = [_read_text(p) for p in cli_files]
        if all("click" in t and ("@click.group" in t or "click.group" in t) for t in cli_texts):
            checks.append(CheckResult("click-groups", "cli", PASS, "uses Click command groups"))
        else:
            checks.append(CheckResult("click-groups", "cli", FAIL, "CLI does not declare a Click command group"))

        if all('"--json"' in t or "'--json'" in t for t in cli_texts):
            checks.append(CheckResult("json-flag", "cli", PASS, "--json output flag declared"))
        else:
            checks.append(CheckResult("json-flag", "cli", FAIL, "missing --json flag in CLI entry point"))

        if all("invoke_without_command=True" in t for t in cli_texts):
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

        has_session = (core_dir / "session.py").is_file()
        session_clis = [t for t in cli_texts if '"--project"' in t or "'--project'" in t]
        if has_session and session_clis:
            if all(
                ('"--dry-run"' in t or "'--dry-run'" in t) and ("result_callback" in t or "call_on_close" in t)
                for t in session_clis
            ):
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

    repl_skin = utils_dir / "repl_skin.py"
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
    *,
    subpkg_dirs: dict[str, Path] | None = None,
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

    tests_dir = (subpkg_dirs or {}).get("tests") or (module / "tests")
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

    skills_dir = (subpkg_dirs or {}).get("skills") or (module / "skills")
    pkg_skill = skills_dir / "SKILL.md"
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
    pkg_checks, effective_module, declared_cli_files, eff_subpkg_dirs = _check_packaging(
        harness, _slugify(software_dir_name), module
    )
    checks.extend(pkg_checks)
    active_module = effective_module or module
    if active_module is not None:
        # Validate PEP 420 namespace purity on the effective mapped `cli_anything` root
        # (never assuming a directly remapped app's physical parent is `cli_anything`).
        mapped_ns_dir = eff_subpkg_dirs.get("__namespace__")
        if mapped_ns_dir is not None:
            flat_ns_resolved = (harness / "cli_anything").resolve()
            try:
                ns_res = mapped_ns_dir.resolve()
            except OSError:
                ns_res = mapped_ns_dir
            if ns_res != flat_ns_resolved and (mapped_ns_dir / "__init__.py").exists():
                try:
                    rel_ns = str(mapped_ns_dir.relative_to(harness)).replace("\\", "/")
                except ValueError:
                    rel_ns = str(mapped_ns_dir)
                init_hint = f"{rel_ns}/__init__.py" if rel_ns not in {"", "."} else "__init__.py"
                checks.append(
                    CheckResult(
                        "effective-namespace-package",
                        "layout",
                        FAIL,
                        f"PEP 420 violation in effective namespace root: {init_hint} must NOT exist",
                    )
                )

        if module is not None and active_module.resolve() != module.resolve():
            # Verify layout invariants on the effective packaged source directory when it differs
            # from the flat cli_anything/ tree (e.g., where = ["src"] or package_dir = {"": "src"}).
            eff_missing_subdirs = [
                sub
                for sub in ("core", "utils", "tests")
                if not (eff_subpkg_dirs.get(sub) or (active_module / sub)).is_dir()
            ]
            if eff_missing_subdirs:
                checks.append(
                    CheckResult(
                        "effective-subdirs",
                        "layout",
                        FAIL,
                        f"effective package source directory missing required subdirectories: {', '.join(eff_missing_subdirs)}",
                    )
                )
            if not list(active_module.glob("*_cli.py")):
                checks.append(
                    CheckResult(
                        "effective-cli-entrypoint-file",
                        "layout",
                        FAIL,
                        "effective package source directory missing <software>_cli.py entry file",
                    )
                )
        checks.extend(
            _check_cli_surface(
                active_module,
                repl_skin_ref,
                cli_entry_files=declared_cli_files,
                subpkg_dirs=eff_subpkg_dirs,
            )
        )
        checks.extend(
            _check_docs_and_tests(
                harness,
                software_dir_name,
                active_module,
                repo_root,
                subpkg_dirs=eff_subpkg_dirs,
            )
        )
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
