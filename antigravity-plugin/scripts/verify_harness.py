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
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
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


def _hatch_packages_cover(
    target_pkg: str | None,
    packages: list[str],
    harness: Path | None = None,
) -> bool:
    mod = target_pkg.split(".", 1)[1] if (target_pkg and "." in target_pkg) else None
    for raw in packages:
        norm = raw.strip().strip("/").replace("\\", "/")
        if not norm:
            continue
        if norm == "cli_anything" or norm.endswith("/cli_anything"):
            if harness is None or not mod:
                return True
            if (harness / norm / mod / "__init__.py").is_file():
                return True
        elif mod and (norm == f"cli_anything/{mod}" or norm.endswith(f"/cli_anything/{mod}")):
            if harness is None or (harness / norm / "__init__.py").is_file():
                return True
        elif not mod and ("cli_anything/" in norm):
            return True
    return False


def _poetry_packages_cover(
    target_pkg: str | None,
    entries: list[tuple[str, str]],
    harness: Path | None = None,
) -> bool:
    mod = target_pkg.split(".", 1)[1] if (target_pkg and "." in target_pkg) else None
    for raw_inc, raw_from in entries:
        norm = raw_inc.strip().strip("/").replace("\\", "/")
        base_root = (harness / raw_from) if (harness is not None and raw_from) else harness
        if norm == "cli_anything":
            if base_root is None or not target_pkg:
                return True
            if _package_exists_under(base_root, target_pkg):
                return True
        elif mod and norm in {f"cli_anything/{mod}", f"cli_anything.{mod}"}:
            if base_root is None or not target_pkg:
                return True
            if _package_exists_under(base_root, target_pkg):
                return True
        elif not mod and (norm.startswith("cli_anything/") or norm.startswith("cli_anything.")):
            return True
    return False


def _is_absolute_pattern(pattern: str) -> bool:
    """Return True if a glob/path pattern is rooted (POSIX `/` or Windows drive / UNC)."""
    s = pattern.strip().replace("\\", "/")
    return s.startswith("/") or bool(re.match(r"^[A-Za-z]:", s))


def _glob_matches_relpath(rel_path: str, pattern: str, *, recursive: bool = True) -> bool:
    """Match a POSIX relative path against a relative glob pattern (`**` matches 0+ dirs when recursive=True)."""
    if _is_absolute_pattern(pattern):
        return False
    rel_norm = rel_path.strip().replace("\\", "/")
    pat_norm = pattern.strip().replace("\\", "/")
    while rel_norm.startswith("./"):
        rel_norm = rel_norm[2:]
    while pat_norm.startswith("./"):
        pat_norm = pat_norm[2:]
    rel_parts = [p for p in rel_norm.split("/") if p]
    pat_parts = [p for p in pat_norm.split("/") if p]
    if not rel_parts or not pat_parts:
        return False

    if not recursive:
        if len(rel_parts) != len(pat_parts):
            return False
        return all(fnmatch.fnmatchcase(rp, pp) for rp, pp in zip(rel_parts, pat_parts))

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
        elif ri < len(rel_parts) and fnmatch.fnmatchcase(rel_parts[ri], pat_parts[pi]):
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
        if _is_absolute_pattern(raw_pat):
            return False
        pat = raw_pat.strip().replace("\\", "/")
        while pat.startswith("./"):
            pat = pat[2:]
        if not pat:
            return False
        if exclusion:
            return fnmatch.fnmatch(rel_path, pat)
        return _glob_matches_relpath(rel_path, pat, recursive=True)

    for pkg_key, patterns in mapping.items():
        if pkg_key in applicable_keys and any(_matches(p) for p in patterns):
            return True
    return False


def _manifest_covers_skill(harness: Path | None, target_pkg: str | None) -> bool:
    """Evaluate MANIFEST.in directives in order (mirroring setuptools egg_info.FileList)."""
    if harness is None or not target_pkg:
        return False
    manifest = harness / "MANIFEST.in"
    if not manifest.is_file():
        return False

    target_rel = f"{target_pkg.replace('.', '/')}/skills/SKILL.md"
    target_dir_parts = target_rel.split("/")[:-1]
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

    def _norm_dir(dir_token: str) -> str | None:
        if _is_absolute_pattern(dir_token):
            return None
        d = dir_token.strip().replace("\\", "/")
        while d.startswith("./"):
            d = d[2:]
        d = d.strip("/")
        return "" if d in {"", "."} else d

    selected = False
    for line in logical_lines:
        tokens = line.split()
        if len(tokens) < 2:
            continue
        action = tokens[0]
        if action == "include":
            if any(_glob_matches_relpath(target_rel, pat, recursive=False) for pat in tokens[1:]):
                selected = True
        elif action == "exclude":
            if any(_glob_matches_relpath(target_rel, pat, recursive=True) for pat in tokens[1:]):
                selected = False
        elif action in {"global-include", "global-exclude"}:
            if any(
                not _is_absolute_pattern(pat) and _glob_matches_relpath(target_rel, f"**/{pat}", recursive=True)
                for pat in tokens[1:]
            ):
                selected = action == "global-include"
        elif action in {"recursive-include", "recursive-exclude"}:
            if len(tokens) < 3:
                continue
            d = _norm_dir(tokens[1])
            if d is None:
                continue
            prefix = f"{d}/**/" if d else "**/"
            if any(
                not _is_absolute_pattern(pat) and _glob_matches_relpath(target_rel, f"{prefix}{pat}", recursive=True)
                for pat in tokens[2:]
            ):
                selected = action == "recursive-include"
        elif action == "graft":
            if len(tokens) != 2:
                continue
            d = _norm_dir(tokens[1])
            if d is None:
                continue
            # setuptools FileList.graft() calls glob(dir) WITHOUT recursive=True, then collects
            # all files recursively beneath each matched directory.
            if not d or any(_glob_matches_relpath(anc, d, recursive=False) for anc in ancestor_dirs):
                selected = True
        elif action == "prune":
            if len(tokens) != 2:
                continue
            d = _norm_dir(tokens[1])
            if d is None:
                continue
            dir_glob = f"{d}/**/*" if d else "**/*"
            if _glob_matches_relpath(target_rel, dir_glob, recursive=True):
                selected = False

    return selected


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
                if where_kw is not None:
                    resolved_where = _resolve(where_kw)
                    if isinstance(resolved_where, ast.Constant) and isinstance(resolved_where.value, str):
                        wheres = [resolved_where.value]
                    else:
                        # Dynamic where expression (e.g., os.path.dirname(__file__)); avoid false failures.
                        wheres = None

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
                info["uses_regular_find_packages"] = True
        else:
            explicit = _const_str_list(node)
            if explicit and _explicit_packages_cover(target_pkg, explicit):
                info["namespace_ok"] = True
            if explicit and target_pkg and f"{target_pkg}.skills" in explicit:
                info["skills_subpkg_ok"] = True

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

    def _extract_pkg_data_mapping(expr: ast.AST, dest: dict[str, list[str]]) -> None:
        node = _resolve(expr)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    vals = _const_str_list(_resolve(v))
                    if vals is not None:
                        dest[k.value] = vals

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node.func) == "setup":
            for kw in node.keywords:
                if kw.arg == "packages":
                    _check_packages_expr(kw.value)
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


class _TomlFallbackParser:
    """Minimal stdlib-only TOML 1.0 parser for Python 3.10 where tomllib is absent."""

    _ESCAPES = {
        "b": "\b",
        "t": "\t",
        "n": "\n",
        "f": "\f",
        "r": "\r",
        '"': '"',
        "\\": "\\",
    }

    def __init__(self, text: str) -> None:
        cleaned = text[1:] if text.startswith("\ufeff") else text
        self.text = cleaned.replace("\r\n", "\n")
        self.n = len(self.text)
        self.pos = 0

    def parse(self) -> dict[str, Any]:
        root: dict[str, Any] = {}
        current: dict[str, Any] = root
        while True:
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos >= self.n:
                break
            ch = self.text[self.pos]
            if ch == "[":
                if self.pos + 1 < self.n and self.text[self.pos + 1] == "[":
                    self.pos += 2
                    keys = self._parse_key_path()
                    self._skip_ws_inline()
                    if not self.text.startswith("]]", self.pos):
                        raise ValueError("Expected ']]'")
                    self.pos += 2
                    current = self._ensure_array_table(root, keys)
                else:
                    self.pos += 1
                    keys = self._parse_key_path()
                    self._skip_ws_inline()
                    if self.pos >= self.n or self.text[self.pos] != "]":
                        raise ValueError("Expected ']'")
                    self.pos += 1
                    current = self._ensure_table(root, keys)
                self._skip_to_eol()
            else:
                keys = self._parse_key_path()
                self._skip_ws_inline()
                if self.pos >= self.n or self.text[self.pos] != "=":
                    raise ValueError(f"Expected '=' at pos {self.pos}")
                self.pos += 1
                self._skip_ws_inline()
                val = self._parse_value()
                self._assign_path(current, keys, val)
                self._skip_to_eol()
        return root

    def _skip_ws_inline(self) -> None:
        while self.pos < self.n and self.text[self.pos] in {" ", "\t"}:
            self.pos += 1

    def _skip_ws_and_comments(self, *, allow_newlines: bool) -> None:
        ws = {" ", "\t", "\r", "\n"} if allow_newlines else {" ", "\t"}
        while self.pos < self.n:
            ch = self.text[self.pos]
            if ch in ws:
                self.pos += 1
            elif ch == "#":
                while self.pos < self.n and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _skip_to_eol(self) -> None:
        self._skip_ws_inline()
        if self.pos < self.n and self.text[self.pos] == "#":
            while self.pos < self.n and self.text[self.pos] != "\n":
                self.pos += 1
        if self.pos < self.n and self.text[self.pos] == "\r":
            self.pos += 1
        if self.pos < self.n and self.text[self.pos] == "\n":
            self.pos += 1

    def _parse_key_segment(self) -> str:
        self._skip_ws_inline()
        if self.pos >= self.n:
            raise ValueError("Unexpected EOF while parsing TOML key")
        ch = self.text[self.pos]
        if ch == '"':
            return self._parse_basic_string(multiline=False)
        if ch == "'":
            return self._parse_literal_string(multiline=False)
        start = self.pos
        while self.pos < self.n and (self.text[self.pos].isalnum() or self.text[self.pos] in {"_", "-"}):
            self.pos += 1
        if self.pos == start:
            raise ValueError(f"Invalid TOML bare key at pos {self.pos}")
        return self.text[start : self.pos]

    def _parse_key_path(self) -> list[str]:
        parts = [self._parse_key_segment()]
        while True:
            self._skip_ws_inline()
            if self.pos < self.n and self.text[self.pos] == ".":
                self.pos += 1
                parts.append(self._parse_key_segment())
            else:
                break
        return parts

    def _parse_value(self) -> Any:
        self._skip_ws_inline()
        if self.pos >= self.n:
            raise ValueError("Unexpected EOF while parsing TOML value")
        if self.text.startswith('"""', self.pos):
            return self._parse_basic_string(multiline=True)
        if self.text.startswith("'''", self.pos):
            return self._parse_literal_string(multiline=True)
        ch = self.text[self.pos]
        if ch == '"':
            return self._parse_basic_string(multiline=False)
        if ch == "'":
            return self._parse_literal_string(multiline=False)
        if ch == "[":
            return self._parse_array()
        if ch == "{":
            return self._parse_inline_table()
        return self._parse_scalar()

    def _parse_basic_string(self, *, multiline: bool) -> str:
        delim = '"""' if multiline else '"'
        self.pos += len(delim)
        if multiline:
            if self.text.startswith("\r\n", self.pos):
                self.pos += 2
            elif self.text.startswith("\n", self.pos):
                self.pos += 1
        out: list[str] = []
        while self.pos < self.n:
            if multiline and self.text.startswith('"""', self.pos):
                # Allow 1 or 2 trailing quotes immediately before closing delimiter.
                run = 0
                while self.pos + run < self.n and self.text[self.pos + run] == '"':
                    run += 1
                if run > 3:
                    out.append('"' * (run - 3))
                    self.pos += run
                    return "".join(out)
                self.pos += 3
                return "".join(out)
            ch = self.text[self.pos]
            if not multiline and ch == '"':
                self.pos += 1
                return "".join(out)
            if ch == "\\":
                self.pos += 1
                if self.pos >= self.n:
                    raise ValueError("Unterminated escape")
                esc = self.text[self.pos]
                if multiline and esc in {" ", "\t", "\r", "\n"}:
                    while self.pos < self.n and self.text[self.pos] in {" ", "\t", "\r", "\n"}:
                        self.pos += 1
                    continue
                if esc in self._ESCAPES:
                    out.append(self._ESCAPES[esc])
                    self.pos += 1
                elif esc == "u":
                    out.append(chr(int(self.text[self.pos + 1 : self.pos + 5], 16)))
                    self.pos += 5
                elif esc == "U":
                    out.append(chr(int(self.text[self.pos + 1 : self.pos + 9], 16)))
                    self.pos += 9
                else:
                    out.append(esc)
                    self.pos += 1
            else:
                out.append(ch)
                self.pos += 1
        raise ValueError("Unterminated TOML basic string")

    def _parse_literal_string(self, *, multiline: bool) -> str:
        delim = "'''" if multiline else "'"
        self.pos += len(delim)
        if multiline:
            if self.text.startswith("\r\n", self.pos):
                self.pos += 2
            elif self.text.startswith("\n", self.pos):
                self.pos += 1
        start = self.pos
        if multiline:
            end = self.text.find("'''", self.pos)
            if end == -1:
                raise ValueError("Unterminated TOML multiline literal string")
            run = 0
            while end + run < self.n and self.text[end + run] == "'":
                run += 1
            extra = run - 3
            val = self.text[start : end + extra]
            self.pos = end + run
            return val
        end = self.text.find("'", self.pos)
        if end == -1:
            raise ValueError("Unterminated TOML literal string")
        val = self.text[start:end]
        self.pos = end + 1
        return val

    def _parse_array(self) -> list[Any]:
        self.pos += 1  # '['
        items: list[Any] = []
        while True:
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos >= self.n:
                raise ValueError("Unterminated TOML array")
            if self.text[self.pos] == "]":
                self.pos += 1
                return items
            items.append(self._parse_value())
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos < self.n and self.text[self.pos] == ",":
                self.pos += 1
            elif self.pos < self.n and self.text[self.pos] == "]":
                self.pos += 1
                return items
            else:
                raise ValueError(f"Expected ',' or ']' in TOML array at pos {self.pos}")

    def _parse_inline_table(self) -> dict[str, Any]:
        self.pos += 1  # '{'
        table: dict[str, Any] = {}
        while True:
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos >= self.n:
                raise ValueError("Unterminated TOML inline table")
            if self.text[self.pos] == "}":
                self.pos += 1
                return table
            keys = self._parse_key_path()
            self._skip_ws_inline()
            if self.pos >= self.n or self.text[self.pos] != "=":
                raise ValueError(f"Expected '=' in TOML inline table at pos {self.pos}")
            self.pos += 1
            self._skip_ws_inline()
            val = self._parse_value()
            self._assign_path(table, keys, val)
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos < self.n and self.text[self.pos] == ",":
                self.pos += 1
            elif self.pos < self.n and self.text[self.pos] == "}":
                self.pos += 1
                return table
            else:
                raise ValueError(f"Expected ',' or '}}' in TOML inline table at pos {self.pos}")

    def _parse_scalar(self) -> Any:
        start = self.pos
        while self.pos < self.n and self.text[self.pos] not in {",", "]", "}", "#", "\r", "\n"}:
            self.pos += 1
        raw = self.text[start : self.pos].strip()
        if raw == "true":
            return True
        if raw == "false":
            return False
        cleaned = raw.replace("_", "")
        try:
            return int(cleaned, 0)
        except ValueError:
            pass
        try:
            return float(cleaned)
        except ValueError:
            return raw

    @staticmethod
    def _ensure_table(root: dict[str, Any], keys: list[str]) -> dict[str, Any]:
        cur: Any = root
        for k in keys:
            if isinstance(cur, list):
                cur = cur[-1]
            if k not in cur:
                cur[k] = {}
            cur = cur[k]
            if isinstance(cur, list):
                cur = cur[-1]
        if not isinstance(cur, dict):
            raise ValueError(f"Key path {keys!r} does not resolve to a table")
        return cur

    @staticmethod
    def _ensure_array_table(root: dict[str, Any], keys: list[str]) -> dict[str, Any]:
        parent = _TomlFallbackParser._ensure_table(root, keys[:-1]) if len(keys) > 1 else root
        last = keys[-1]
        if last not in parent:
            parent[last] = []
        if not isinstance(parent[last], list):
            raise ValueError(f"Key path {keys!r} is not an array of tables")
        entry: dict[str, Any] = {}
        parent[last].append(entry)
        return entry

    @staticmethod
    def _assign_path(table: dict[str, Any], keys: list[str], value: Any) -> None:
        cur: Any = table
        for k in keys[:-1]:
            if isinstance(cur, list):
                cur = cur[-1]
            if k not in cur:
                cur[k] = {}
            cur = cur[k]
        if isinstance(cur, list):
            cur = cur[-1]
        if not isinstance(cur, dict):
            raise ValueError(f"Cannot assign into non-table at {keys!r}")
        cur[keys[-1]] = value


def _loads_toml_fallback(text: str) -> dict[str, Any]:
    """Parse TOML text into Python dicts/lists without tomllib (Python 3.10 fallback)."""
    return _TomlFallbackParser(text).parse()


def _empty_pyproject_info() -> dict[str, Any]:
    return {
        "build_backend": None,
        "backend_kind": "setuptools",
        "namespace_ok": False,
        "skills_subpkg_ok": False,
        "namespaces_disabled": False,
        "declares_packages": False,
        "has_project_table": False,
        "scripts_dynamic": False,
        "reserved_console_scripts_ep": False,
        "console_scripts": [],
        "declares_package_data": False,
        "package_data": {},
        "declares_exclude_package_data": False,
        "exclude_package_data": {},
        "include_package_data": None,
        "has_python_requires": False,
    }


def _inspect_pyproject_toml_fallback(
    text: str,
    target_pkg: str | None = None,
    harness: Path | None = None,
) -> dict[str, Any]:
    """Python 3.10 stdlib fallback path using the stdlib TOML parser + shared inspection logic."""
    try:
        data = _loads_toml_fallback(text)
    except Exception:
        return _empty_pyproject_info()
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
    except Exception:
        return _empty_pyproject_info()
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
            if _hatch_packages_cover(target_pkg, str_pkgs, harness=harness):
                info["namespace_ok"] = True
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
            if _poetry_packages_cover(target_pkg, pkg_entries, harness=harness):
                info["namespace_ok"] = True

    project_cfg = data.get("project")
    if isinstance(project_cfg, dict):
        info["has_project_table"] = True
        req_py = project_cfg.get("requires-python")
        if isinstance(req_py, str) and req_py.strip():
            info["has_python_requires"] = True
        dynamic = project_cfg.get("dynamic")
        if isinstance(dynamic, list) and "scripts" in dynamic:
            info["scripts_dynamic"] = True
        scripts = project_cfg.get("scripts")
        if isinstance(scripts, dict):
            info["console_scripts"].extend(str(k) for k in scripts.keys())
        ep = project_cfg.get("entry-points")
        if isinstance(ep, dict) and "console_scripts" in ep:
            # PEP 621 reserves console_scripts for [project.scripts]; setuptools drops
            # [project.entry-points.console_scripts] and resets legacy setup.py scripts.
            info["reserved_console_scripts_ep"] = True

    if backend_kind == "poetry":
        poetry_cfg = tool_dict.get("poetry")
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

    target_pkg = f"cli_anything.{module.name}" if module is not None else None
    target_pkg_label = target_pkg or f"cli_anything.{software_slug.replace('-', '_')}"

    setup_info = _inspect_setup_py(setup_text, target_pkg=target_pkg, harness=harness) if has_setup else {
        "namespace_ok": False,
        "skills_subpkg_ok": False,
        "uses_regular_find_packages": False,
        "console_scripts": [],
        "package_data": {},
        "exclude_package_data": {},
        "include_package_data": None,
        "has_python_requires": False,
    }
    pyproj_info = _inspect_pyproject_toml(pyproject_text, target_pkg=target_pkg, harness=harness) if has_pyproject else {
        "build_backend": None,
        "backend_kind": "setuptools",
        "namespace_ok": False,
        "skills_subpkg_ok": False,
        "namespaces_disabled": False,
        "declares_packages": False,
        "has_project_table": False,
        "scripts_dynamic": False,
        "reserved_console_scripts_ep": False,
        "console_scripts": [],
        "declares_package_data": False,
        "package_data": {},
        "declares_exclude_package_data": False,
        "exclude_package_data": {},
        "include_package_data": None,
        "has_python_requires": False,
    }

    uses_setup_py = has_setup and (not has_pyproject or pyproj_info["backend_kind"] == "setuptools")

    # In setuptools >= 61, pyproject.toml [tool.setuptools.packages*] takes precedence over setup.py.
    # Non-setuptools PEP 517 backends (Hatch, Poetry, etc.) do not execute setup.py at all.
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
    elif uses_setup_py and setup_info["uses_regular_find_packages"] and not setup_info["namespace_ok"]:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                "setup.py uses find_packages() instead of find_namespace_packages() (PEP 420 cli_anything/ has no __init__.py)",
            )
        )
    elif uses_setup_py and setup_info["namespace_ok"]:
        checks.append(CheckResult("namespace-packages", "packaging", PASS, "namespace package discovery configured"))
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
    # Under PEP 517 / PEP 621: non-setuptools backends ignore setup.py, and setuptools >= 61
    # ignores setup.py entry_points whenever [project] omits "scripts" from project.dynamic.
    if (not uses_setup_py) or (pyproj_info["has_project_table"] and not pyproj_info["scripts_dynamic"]):
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
        if pyproj_info["reserved_console_scripts_ep"]:
            detail = (
                "pyproject.toml declares reserved [project.entry-points.console_scripts] instead of [project.scripts] "
                "(rejected/dropped under PEP 621 / setuptools)"
            )
        elif has_pyproject and pyproj_info["backend_kind"] != "setuptools" and setup_info["console_scripts"]:
            detail = (
                f"pyproject.toml uses build-backend '{pyproj_info['build_backend']}' without declaring console scripts "
                "(setup.py console_scripts are ignored)"
            )
        elif pyproj_info["has_project_table"] and not pyproj_info["scripts_dynamic"] and setup_info["console_scripts"]:
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

    skill_data_ok = False
    if has_pyproject and pyproj_info["backend_kind"] in {"hatch", "poetry"}:
        # Hatch and Poetry include non-Python assets inside declared package directories automatically.
        skill_data_ok = bool(pyproj_info["namespace_ok"])
    else:
        if pyproj_info["declares_package_data"]:
            eff_pkg_data = pyproj_info["package_data"]
            eff_pkg_star = True
        elif uses_setup_py:
            eff_pkg_data = setup_info["package_data"]
            eff_pkg_star = False
        else:
            eff_pkg_data = {}
            eff_pkg_star = False

        if pyproj_info["declares_exclude_package_data"]:
            eff_excl_data = pyproj_info["exclude_package_data"]
            eff_excl_star = True
        elif uses_setup_py:
            eff_excl_data = setup_info["exclude_package_data"]
            eff_excl_star = False
        else:
            eff_excl_data = {}
            eff_excl_star = False

        if pyproj_info["include_package_data"] is not None:
            eff_include_pkg_data = bool(pyproj_info["include_package_data"])
        elif uses_setup_py and setup_info["include_package_data"] is not None:
            eff_include_pkg_data = bool(setup_info["include_package_data"])
        elif pyproj_info["has_project_table"]:
            # Setuptools >= 61 defaults include-package-data to True for PEP 621 [project] tables.
            eff_include_pkg_data = True
        else:
            eff_include_pkg_data = False

        # Determine which setuptools packages are actually selected by discovery.
        if pyproj_info["namespaces_disabled"]:
            parent_selected = False
            skills_subpkg_selected = False
        elif pyproj_info["declares_packages"]:
            parent_selected = bool(pyproj_info["namespace_ok"])
            skills_subpkg_selected = bool(pyproj_info["skills_subpkg_ok"])
        elif uses_setup_py:
            parent_selected = bool(setup_info["namespace_ok"])
            skills_subpkg_selected = bool(setup_info["skills_subpkg_ok"])
        else:
            parent_selected = False
            skills_subpkg_selected = False

        # Mirror setuptools build_py: analyze_manifest() assigns SKILL.md to the deepest
        # selected package containing it, and exclude_data_files() runs per supplying package.
        manifest_has_skill = eff_include_pkg_data and _manifest_covers_skill(harness, target_pkg)
        manifest_owner: str | None = None
        if manifest_has_skill and target_pkg:
            if skills_subpkg_selected:
                manifest_owner = f"{target_pkg}.skills"
            elif parent_selected:
                manifest_owner = target_pkg

        suppliers: list[tuple[str, str]] = []
        if target_pkg:
            if parent_selected:
                suppliers.append((target_pkg, "skills/SKILL.md"))
            if skills_subpkg_selected:
                suppliers.append((f"{target_pkg}.skills", "SKILL.md"))

        for pkg_name, rel_path in suppliers:
            from_pd = _pkg_data_matches_file(
                eff_pkg_data,
                pkg_name,
                rel_path,
                allow_star_wildcard=eff_pkg_star,
                exclusion=False,
            )
            from_manifest = manifest_owner == pkg_name
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

    if pyproj_info["has_python_requires"] or (uses_setup_py and setup_info["has_python_requires"]):
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
