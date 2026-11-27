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
import types
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


def _extract_attr_chain(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        prefix = _extract_attr_chain(node.value)
        if prefix is not None:
            return (*prefix, node.attr)
    return None


def _collect_target_attr_chains(node: ast.AST) -> list[tuple[str, ...]]:
    chains: list[tuple[str, ...]] = []
    chain = _extract_attr_chain(node)
    if chain is not None and len(chain) >= 2:
        chains.append(chain)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            chains.extend(_collect_target_attr_chains(elt))
    elif isinstance(node, ast.Starred):
        chains.extend(_collect_target_attr_chains(node.value))
    return chains


def _resolve_local_module_file(
    module_path: str,
    harness: Path,
    eff_pkg_dir: dict[str, str],
) -> tuple[Path | None, bool]:
    """Resolve a dotted module path to a local .py file inside harness via eff_pkg_dir."""
    parts = [p for p in module_path.split(".") if p]
    if not parts or not all(p.isidentifier() and not keyword.iskeyword(p) for p in parts):
        return None, False
    root_resolved = harness.resolve()
    pkg_dir_rel = _get_package_dir_rel(module_path, eff_pkg_dir)
    pkg_init = (harness / pkg_dir_rel / "__init__.py") if pkg_dir_rel else (harness / "__init__.py")
    if pkg_init.is_file():
        try:
            pkg_init.resolve().relative_to(root_resolved)
            return pkg_init, True
        except (OSError, ValueError):
            pass
    parent_pkg = ".".join(parts[:-1])
    parent_dir_rel = _get_package_dir_rel(parent_pkg, eff_pkg_dir) if parent_pkg else ""
    mod_py = (
        (harness / parent_dir_rel / f"{parts[-1]}.py")
        if parent_dir_rel
        else (harness / f"{parts[-1]}.py")
    )
    if mod_py.is_file():
        try:
            mod_py.resolve().relative_to(root_resolved)
            return mod_py, False
        except (OSError, ValueError):
            pass
    return None, False


def _module_defines_symbol(py_file: Path, symbol: str) -> tuple[bool, str | None]:
    """Check statically whether py_file defines or imports `symbol` at module scope."""
    try:
        tree = ast.parse(_read_text(py_file), filename=str(py_file))
    except SyntaxError as exc:
        return False, f"syntax error in {py_file.name}: {exc.msg}"

    try_star = getattr(ast, "TryStar", ())
    match_cls = getattr(ast, "Match", ())

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


def _args_allow_zero_call(
    args: ast.arguments,
    *,
    bound_self: bool = False,
) -> tuple[bool, str | None]:
    """Return (True, None) if a callable with AST `args` can be invoked with zero arguments."""
    pos_params = list(args.posonlyargs) + list(args.args)
    total_pos = len(pos_params)
    required_pos = total_pos - len(args.defaults)
    if bound_self:
        if total_pos == 0 and args.vararg is None:
            return False, "takes 0 positional arguments when bound (missing self/cls)"
        if required_pos > 1:
            return False, f"requires positional argument '{pos_params[1].arg}'"
    else:
        if required_pos > 0:
            return False, f"requires positional argument '{pos_params[0].arg}'"
    for kw_arg, kw_default in zip(args.kwonlyargs, args.kw_defaults):
        if kw_default is None:
            return False, f"requires keyword-only argument '{kw_arg.arg}'"
    return True, None


def _is_provably_non_callable_expr(node: ast.AST) -> bool:
    """Return True if an AST expression provably evaluates to a non-callable value."""
    if isinstance(
        node,
        (
            ast.Constant,
            ast.List,
            ast.Tuple,
            ast.Set,
            ast.Dict,
            ast.JoinedStr,
            ast.FormattedValue,
            ast.ListComp,
            ast.SetComp,
            ast.DictComp,
            ast.GeneratorExp,
            ast.Slice,
        ),
    ):
        return True
    if isinstance(node, ast.UnaryOp):
        return _is_provably_non_callable_expr(node.operand)
    if isinstance(node, ast.BinOp):
        return _is_provably_non_callable_expr(node.left) and _is_provably_non_callable_expr(node.right)
    if isinstance(node, ast.BoolOp):
        return all(_is_provably_non_callable_expr(v) for v in node.values)
    if isinstance(node, ast.Compare):
        return _is_provably_non_callable_expr(node.left) and all(
            _is_provably_non_callable_expr(c) for c in node.comparators
        )
    if isinstance(node, ast.IfExp):
        return _is_provably_non_callable_expr(node.body) and _is_provably_non_callable_expr(node.orelse)
    return False


def _is_known_external_module(base_mod: str, orig_name: str) -> bool:
    """Return True if `from base_mod import orig_name` provably binds a module without executing user code."""
    if not base_mod:
        return False
    full_name = f"{base_mod}.{orig_name}"
    if isinstance(sys.modules.get(full_name), types.ModuleType):
        return True
    parent_mod = sys.modules.get(base_mod)
    if isinstance(parent_mod, types.ModuleType):
        attr_val = getattr(parent_mod, orig_name, None)
        if isinstance(attr_val, types.ModuleType):
            return True
    top_pkg = base_mod.split(".", 1)[0]
    stdlib_names = getattr(sys, "stdlib_module_names", frozenset())
    if top_pkg in stdlib_names:
        try:
            if importlib.util.find_spec(full_name) is not None:
                return True
        except (ImportError, ValueError, AttributeError):
            pass
    return False


def _eval_static_str_seq(node: ast.AST, str_seq_vars: dict[str, list[str]]) -> list[str] | None:
    if isinstance(node, (ast.List, ast.Tuple)):
        out: list[str] = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
            elif (
                isinstance(elt, ast.Starred)
                and isinstance(elt.value, ast.Name)
                and elt.value.id in str_seq_vars
            ):
                out.extend(str_seq_vars[elt.value.id])
            else:
                return None
        return out
    if isinstance(node, ast.Name) and node.id in str_seq_vars:
        return list(str_seq_vars[node.id])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _eval_static_str_seq(node.left, str_seq_vars)
        right = _eval_static_str_seq(node.right, str_seq_vars)
        if left is not None and right is not None:
            return left + right
    return None


def _stmts_mutate_dunder_all(stmts: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
        if isinstance(node, ast.Name) and node.id == "__all__" and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "__all__"
        ):
            return True
    return False


def _extract_module_dunder_all(tree: ast.Module) -> tuple[str, set[str] | None]:
    """Extract effective `__all__` state from a module AST.

    Returns:
      - ("absent", None): module does not define `__all__` (Python wildcard exports non-`_` names)
      - ("static", set[str]): statically resolved `__all__` export names
      - ("dynamic", None): `__all__` is defined or mutated dynamically and cannot be statically verified
    """
    all_state = "absent"
    all_list: list[str] = []
    str_seq_vars: dict[str, list[str]] = {}
    try_star = getattr(ast, "TryStar", ())
    match_cls = getattr(ast, "Match", ())

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            targets_all = any("__all__" in _collect_target_names(t) for t in stmt.targets)
            if targets_all:
                seq = _eval_static_str_seq(stmt.value, str_seq_vars)
                if seq is not None:
                    all_state = "static"
                    all_list = list(seq)
                    str_seq_vars["__all__"] = list(all_list)
                else:
                    all_state = "dynamic"
                    str_seq_vars.pop("__all__", None)
            elif len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                vname = stmt.targets[0].id
                seq = _eval_static_str_seq(stmt.value, str_seq_vars)
                if seq is not None:
                    str_seq_vars[vname] = list(seq)
                else:
                    str_seq_vars.pop(vname, None)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            if "__all__" in _collect_target_names(stmt.target):
                seq = _eval_static_str_seq(stmt.value, str_seq_vars)
                if seq is not None:
                    all_state = "static"
                    all_list = list(seq)
                    str_seq_vars["__all__"] = list(all_list)
                else:
                    all_state = "dynamic"
                    str_seq_vars.pop("__all__", None)
            elif isinstance(stmt.target, ast.Name):
                vname = stmt.target.id
                seq = _eval_static_str_seq(stmt.value, str_seq_vars)
                if seq is not None:
                    str_seq_vars[vname] = list(seq)
                else:
                    str_seq_vars.pop(vname, None)
        elif (
            isinstance(stmt, ast.AugAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "__all__"
        ):
            if isinstance(stmt.op, ast.Add) and all_state == "static":
                rhs = _eval_static_str_seq(stmt.value, str_seq_vars)
                if rhs is not None:
                    all_list.extend(rhs)
                    str_seq_vars["__all__"] = list(all_list)
                else:
                    all_state = "dynamic"
                    str_seq_vars.pop("__all__", None)
            else:
                all_state = "dynamic"
                str_seq_vars.pop("__all__", None)
        elif isinstance(stmt, ast.Delete):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in stmt.targets):
                all_state = "absent"
                all_list = []
                str_seq_vars.pop("__all__", None)
        elif (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Name)
            and stmt.value.func.value.id == "__all__"
        ):
            method = stmt.value.func.attr
            args = stmt.value.args
            if all_state == "static" and not stmt.value.keywords and len(args) == 1:
                if (
                    method == "append"
                    and isinstance(args[0], ast.Constant)
                    and isinstance(args[0].value, str)
                ):
                    all_list.append(args[0].value)
                    str_seq_vars["__all__"] = list(all_list)
                elif method == "extend":
                    ext = _eval_static_str_seq(args[0], str_seq_vars)
                    if ext is not None:
                        all_list.extend(ext)
                        str_seq_vars["__all__"] = list(all_list)
                    else:
                        all_state = "dynamic"
                        str_seq_vars.pop("__all__", None)
                elif (
                    method == "remove"
                    and isinstance(args[0], ast.Constant)
                    and isinstance(args[0].value, str)
                ):
                    if args[0].value in all_list:
                        all_list.remove(args[0].value)
                        str_seq_vars["__all__"] = list(all_list)
                else:
                    all_state = "dynamic"
                    str_seq_vars.pop("__all__", None)
            else:
                all_state = "dynamic"
                str_seq_vars.pop("__all__", None)
        elif isinstance(stmt, ast.If):
            sub_stmts = stmt.orelse if _is_dunder_main_guard(stmt.test) else (stmt.body + stmt.orelse)
            if _stmts_mutate_dunder_all(sub_stmts):
                all_state = "dynamic"
                str_seq_vars.pop("__all__", None)
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            if _stmts_mutate_dunder_all(stmt.body + stmt.orelse):
                all_state = "dynamic"
                str_seq_vars.pop("__all__", None)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            if _stmts_mutate_dunder_all(stmt.body):
                all_state = "dynamic"
                str_seq_vars.pop("__all__", None)
        elif isinstance(stmt, ast.Try) or (try_star and isinstance(stmt, try_star)):
            sub_stmts = list(stmt.body) + list(stmt.orelse) + list(stmt.finalbody)
            for h in stmt.handlers:
                sub_stmts.extend(h.body)
            if _stmts_mutate_dunder_all(sub_stmts):
                all_state = "dynamic"
                str_seq_vars.pop("__all__", None)
        elif match_cls and isinstance(stmt, match_cls):
            sub_stmts = [s for c in stmt.cases for s in c.body]
            if _stmts_mutate_dunder_all(sub_stmts):
                all_state = "dynamic"
                str_seq_vars.pop("__all__", None)

    if all_state == "static":
        return "static", set(all_list)
    return all_state, None


def _module_wildcard_allows(py_file: Path, symbol: str) -> tuple[bool, str | None]:
    """Check whether `from <py_file> import *` exports `symbol` (honoring `__all__` and `_` rules)."""
    try:
        tree = ast.parse(_read_text(py_file), filename=str(py_file))
    except SyntaxError as exc:
        return False, f"syntax error in {py_file.name}: {exc.msg}"

    state, exports = _extract_module_dunder_all(tree)
    if state == "absent":
        if symbol.startswith("_"):
            return False, f"private symbol '{symbol}' is not exported by wildcard import from {py_file.name}"
        return True, None
    if state == "static" and exports is not None:
        if symbol in exports:
            return True, None
        return False, f"symbol '{symbol}' is not listed in __all__ of {py_file.name}"
    return (
        False,
        f"wildcard import from {py_file.name} uses dynamic __all__ that cannot be statically verified for '{symbol}'",
    )


def _resolve_module_attr_path(
    py_file: Path,
    attr_parts: list[str],
    *,
    module_path: str | None = None,
    harness: Path | None = None,
    target_pkg: str | None = None,
    eff_pkg_dir: dict[str, str] | None = None,
    parent_selected: bool = False,
    pkg_spec: dict[str, Any] | None = None,
    excluded_files: set[str] | None = None,
    hatch_exclude: list[str] | None = None,
    check_manifest: bool = False,
    _visited: frozenset[tuple[Path, tuple[str, ...]]] = frozenset(),
) -> tuple[bool, str | None, Path | None]:
    """Validate a console-script attribute chain and resolve local re-exports to the implementation file.

    For single-component callables (`attr_parts == ["main"]`), verifies the symbol is bound and
    follows local re-export facades (`from .demoapp_cli import main`, `main = demoapp_cli.main`,
    `from .demoapp_cli import *`, etc.) to the defining implementation file while checking that
    any traversed local module is also packaged and not excluded by MANIFEST.in / Poetry rules.
    For multi-component paths (`a.b` / `a.b.c`), verifies the complete attribute chain across
    explicit module-scope attribute assignments, Click command `.main` entrypoints, local class
    definitions/instances/aliases, and local module imports.
    """
    try:
        resolved_self = py_file.resolve()
    except OSError:
        resolved_self = py_file
    visit_key = (resolved_self, tuple(attr_parts))
    if visit_key in _visited:
        return False, f"cyclic dotted callable '{'.'.join(attr_parts)}' in {py_file.name}", None
    next_visited = _visited | {visit_key}

    ok_root, root_err = _module_defines_symbol(py_file, attr_parts[0])
    if not ok_root:
        return False, root_err, None

    try:
        tree = ast.parse(_read_text(py_file), filename=str(py_file))
    except SyntaxError as exc:
        return False, f"syntax error in {py_file.name}: {exc.msg}", None

    try_star = getattr(ast, "TryStar", ())
    match_cls = getattr(ast, "Match", ())

    direct_local_defs: set[str] = set()
    non_callable_local_defs: set[str] = set()
    bad_sig_local_defs: dict[str, str] = {}
    click_modules: set[str] = set()
    click_factories: set[str] = set()
    click_cmds: set[str] = set()
    classes: dict[str, list[ast.ClassDef]] = {}
    attr_assign_values: dict[tuple[str, ...], list[ast.AST | None]] = {}
    aliases: dict[str, list[str]] = {}
    attr_aliases: dict[str, list[tuple[str, ...]]] = {}
    instances: dict[str, list[str]] = {}
    from_imports: dict[str, list[tuple[str, str, bool]]] = {}
    mod_imports: dict[str, list[str]] = {}
    dotted_imports: list[tuple[str, ...]] = []
    star_imports: list[tuple[str, bool]] = []

    is_pkg_init = py_file.name == "__init__.py"
    cur_pkg_parts = (
        module_path.split(".")
        if (module_path and is_pkg_init)
        else (module_path.split(".")[:-1] if module_path else [])
    )

    def _resolve_import_from_module(stmt: ast.ImportFrom) -> str | None:
        if stmt.level == 0:
            return stmt.module or ""
        if not module_path:
            return None
        up = stmt.level - 1
        if up > len(cur_pkg_parts):
            return None
        base_parts = cur_pkg_parts[: len(cur_pkg_parts) - up]
        if stmt.module:
            return ".".join([*base_parts, *stmt.module.split(".")])
        return ".".join(base_parts)

    def _is_click_cmd_expr(expr: ast.AST) -> bool:
        target = expr.func if isinstance(expr, ast.Call) else expr
        if isinstance(target, ast.Name) and target.id in click_factories:
            return True
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id in click_modules and target.attr in {"group", "command", "Group", "Command"}:
                return True
            if target.value.id in click_cmds and target.attr in {"group", "command"}:
                return True
        return False

    def _is_click_cmd_value(val: ast.AST) -> bool:
        if isinstance(val, ast.Call):
            if _is_click_cmd_expr(val):
                return True
            if isinstance(val.func, ast.Call) and _is_click_cmd_expr(val.func):
                return True
        return False

    def _clear_reexports(name: str) -> None:
        from_imports.pop(name, None)
        mod_imports.pop(name, None)
        aliases.pop(name, None)
        attr_aliases.pop(name, None)
        instances.pop(name, None)

    def _record_attr_chains(target: ast.AST, value: ast.AST | None, *, top_level: bool) -> None:
        direct_chain = _extract_attr_chain(target)
        if direct_chain is not None and len(direct_chain) >= 2:
            if top_level:
                attr_assign_values[direct_chain] = [value]
            else:
                attr_assign_values.setdefault(direct_chain, []).append(value)
            return
        if (
            isinstance(target, (ast.Tuple, ast.List))
            and isinstance(value, (ast.Tuple, ast.List))
            and len(target.elts) == len(value.elts)
            and not any(isinstance(e, ast.Starred) for e in target.elts)
            and not any(isinstance(e, ast.Starred) for e in value.elts)
        ):
            for t_elt, v_elt in zip(target.elts, value.elts):
                _record_attr_chains(t_elt, v_elt, top_level=top_level)
            return
        for chain in _collect_target_attr_chains(target):
            if top_level:
                attr_assign_values[chain] = [None]
            else:
                attr_assign_values.setdefault(chain, []).append(None)

    def _record_binding(target: ast.AST, value: ast.AST | None, *, top_level: bool) -> None:
        _record_attr_chains(target, value, top_level=top_level)
        if value is None:
            return
        if isinstance(target, ast.Name):
            name = target.id
            if isinstance(value, ast.Name):
                if top_level:
                    direct_local_defs.discard(name)
                    non_callable_local_defs.discard(name)
                    bad_sig_local_defs.pop(name, None)
                    _clear_reexports(name)
                aliases.setdefault(name, []).append(value.id)
                return
            val_chain = _extract_attr_chain(value)
            if val_chain is not None and len(val_chain) >= 2:
                if top_level:
                    direct_local_defs.discard(name)
                    non_callable_local_defs.discard(name)
                    bad_sig_local_defs.pop(name, None)
                    _clear_reexports(name)
                attr_aliases.setdefault(name, []).append(val_chain)
                return
            if top_level:
                _clear_reexports(name)
            if _is_provably_non_callable_expr(value):
                if top_level:
                    direct_local_defs.discard(name)
                    bad_sig_local_defs.pop(name, None)
                non_callable_local_defs.add(name)
                return
            if isinstance(value, ast.Lambda):
                ok_zero, sig_err = _args_allow_zero_call(value.args, bound_self=False)
                if not ok_zero:
                    if top_level:
                        direct_local_defs.discard(name)
                        non_callable_local_defs.discard(name)
                    bad_sig_local_defs[name] = (
                        f"callable '{name}' in {py_file.name} {sig_err} and cannot be invoked with zero arguments"
                    )
                    return
            if top_level:
                non_callable_local_defs.discard(name)
                bad_sig_local_defs.pop(name, None)
            direct_local_defs.add(name)
            if _is_click_cmd_value(value):
                click_cmds.add(name)
            elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                instances.setdefault(name, []).append(value.func.id)
        else:
            for bound_name in _collect_target_names(target):
                if top_level:
                    _clear_reexports(bound_name)
                    non_callable_local_defs.discard(bound_name)
                    bad_sig_local_defs.pop(bound_name, None)
                direct_local_defs.add(bound_name)

    def _collect_stmts(stmts: list[ast.stmt], *, top_level: bool) -> None:
        for stmt in stmts:
            if isinstance(stmt, ast.ClassDef):
                if top_level:
                    _clear_reexports(stmt.name)
                    non_callable_local_defs.discard(stmt.name)
                    bad_sig_local_defs.pop(stmt.name, None)
                classes.setdefault(stmt.name, []).append(stmt)
                init_err: str | None = None
                if not stmt.decorator_list and not stmt.bases and not stmt.keywords:
                    has_new = False
                    init_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None
                    for cls_stmt in stmt.body:
                        if isinstance(cls_stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if cls_stmt.name == "__new__":
                                has_new = True
                            elif cls_stmt.name == "__init__":
                                init_node = cls_stmt
                    if not has_new and init_node is not None and not init_node.decorator_list:
                        ok_zero, sig_err = _args_allow_zero_call(init_node.args, bound_self=True)
                        if not ok_zero:
                            init_err = (
                                f"class '{stmt.name}.__init__' in {py_file.name} {sig_err} "
                                "and cannot be invoked with zero arguments"
                            )
                if init_err is not None:
                    if top_level:
                        direct_local_defs.discard(stmt.name)
                    bad_sig_local_defs[stmt.name] = init_err
                else:
                    direct_local_defs.add(stmt.name)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if top_level:
                    _clear_reexports(stmt.name)
                    non_callable_local_defs.discard(stmt.name)
                if not stmt.decorator_list:
                    ok_zero, sig_err = _args_allow_zero_call(stmt.args, bound_self=False)
                    if not ok_zero:
                        if top_level:
                            direct_local_defs.discard(stmt.name)
                        bad_sig_local_defs[stmt.name] = (
                            f"function '{stmt.name}' in {py_file.name} {sig_err} and cannot be invoked with zero arguments"
                        )
                        continue
                if top_level:
                    bad_sig_local_defs.pop(stmt.name, None)
                direct_local_defs.add(stmt.name)
                if any(_is_click_cmd_expr(dec) for dec in stmt.decorator_list):
                    click_cmds.add(stmt.name)
            elif isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    _record_binding(tgt, stmt.value, top_level=top_level)
            elif isinstance(stmt, ast.AnnAssign):
                if stmt.value is not None:
                    _record_binding(stmt.target, stmt.value, top_level=top_level)
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    if top_level:
                        direct_local_defs.discard(bound)
                        non_callable_local_defs.discard(bound)
                        bad_sig_local_defs.pop(bound, None)
                        _clear_reexports(bound)
                    if alias.name in {"click", "click.decorators", "click.core"}:
                        click_modules.add(alias.asname or alias.name.split(".", 1)[0])
                    if alias.asname:
                        mod_imports.setdefault(alias.asname, []).append(alias.name)
                    else:
                        top = alias.name.split(".", 1)[0]
                        mod_imports.setdefault(top, []).append(top)
                        if "." in alias.name:
                            dotted_imports.append(tuple(alias.name.split(".")))
            elif isinstance(stmt, ast.ImportFrom):
                resolved_mod = _resolve_import_from_module(stmt)
                is_rel = stmt.level > 0
                for alias in stmt.names:
                    if alias.name == "*":
                        if stmt.level == 0 and stmt.module in {"click", "click.decorators", "click.core"}:
                            click_factories.update({"group", "command", "Group", "Command"})
                        if resolved_mod:
                            star_imports.append((resolved_mod, is_rel))
                        continue
                    bound = alias.asname or alias.name
                    if top_level:
                        direct_local_defs.discard(bound)
                        non_callable_local_defs.discard(bound)
                        bad_sig_local_defs.pop(bound, None)
                        _clear_reexports(bound)
                    if stmt.level == 0 and stmt.module in {"click", "click.decorators", "click.core"} and alias.name in {
                        "group",
                        "command",
                        "Group",
                        "Command",
                    }:
                        click_factories.add(bound)
                    if resolved_mod is not None:
                        from_imports.setdefault(bound, []).append((resolved_mod, alias.name, is_rel))
            elif isinstance(stmt, ast.If):
                if _is_dunder_main_guard(stmt.test):
                    _collect_stmts(stmt.orelse, top_level=False)
                else:
                    _collect_stmts(stmt.body, top_level=False)
                    _collect_stmts(stmt.orelse, top_level=False)
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                for bound_name in _collect_target_names(stmt.target):
                    direct_local_defs.add(bound_name)
                _collect_stmts(stmt.body, top_level=False)
                _collect_stmts(stmt.orelse, top_level=False)
            elif isinstance(stmt, ast.While):
                _collect_stmts(stmt.body, top_level=False)
                _collect_stmts(stmt.orelse, top_level=False)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    if item.optional_vars is not None:
                        for bound_name in _collect_target_names(item.optional_vars):
                            direct_local_defs.add(bound_name)
                _collect_stmts(stmt.body, top_level=False)
            elif isinstance(stmt, ast.Try) or (try_star and isinstance(stmt, try_star)):
                _collect_stmts(stmt.body, top_level=False)
                _collect_stmts(stmt.orelse, top_level=False)
                _collect_stmts(stmt.finalbody, top_level=False)
                for handler in stmt.handlers:
                    if handler.name:
                        direct_local_defs.add(handler.name)
                    _collect_stmts(handler.body, top_level=False)
            elif match_cls and isinstance(stmt, match_cls):
                for case in stmt.cases:
                    _collect_stmts(case.body, top_level=False)

    _collect_stmts(tree.body, top_level=True)

    def _expand_aliases(start_name: str) -> set[str]:
        seen: set[str] = {start_name}
        stack = [start_name]
        while stack:
            cur = stack.pop()
            for nxt in aliases.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def _is_harness_mod_ref(mod_name: str, is_explicit_rel: bool) -> bool:
        if is_explicit_rel:
            return True
        if target_pkg and (mod_name == target_pkg or mod_name.startswith(f"{target_pkg}.")):
            return True
        return False

    def _check_local_module_shipped(
        target_mod: str,
        target_file: Path,
        is_target_pkg_init: bool,
    ) -> str | None:
        if harness is None:
            return None
        try:
            rel_posix = target_file.relative_to(harness).as_posix()
        except ValueError:
            rel_posix = ""
        if excluded_files and rel_posix and _poetry_is_excluded(rel_posix, excluded_files):
            return f"re-exported module '{target_mod}' ({rel_posix}) is excluded from wheel by packaging rules"
        if hatch_exclude and rel_posix and _hatch_is_excluded(rel_posix, hatch_exclude):
            return f"re-exported module '{target_mod}' ({rel_posix}) is excluded from wheel by Hatch exclude rules"
        if check_manifest and rel_posix and not _manifest_covers_skill(
            harness, rel_posix, initially_included=True
        ):
            return f"re-exported module '{target_mod}' ({rel_posix}) is excluded from sdist by MANIFEST.in"
        owner = target_mod if is_target_pkg_init else ".".join(target_mod.split(".")[:-1])
        if (
            target_pkg
            and parent_selected
            and owner
            and owner != target_pkg
            and owner.startswith(f"{target_pkg}.")
            and pkg_spec is not None
        ):
            if pkg_spec["kind"] == "find":
                if not _find_selects_package(
                    owner,
                    pkg_spec["includes"],
                    pkg_spec["excludes"],
                    harness=harness,
                    wheres=pkg_spec["wheres"],
                    require_init=False,
                ):
                    return f"re-exported package '{owner}' is not selected by packaging discovery"
            elif pkg_spec["kind"] == "explicit":
                if owner not in pkg_spec["packages"]:
                    return f"re-exported package '{owner}' is not listed in packaging packages"
        return None

    def _recurse_local(
        target_mod: str,
        target_file: Path,
        is_target_pkg_init: bool,
        sub_attrs: list[str],
    ) -> tuple[bool, str | None, Path | None]:
        ship_err = _check_local_module_shipped(target_mod, target_file, is_target_pkg_init)
        if ship_err is not None:
            return False, ship_err, None
        return _resolve_module_attr_path(
            target_file,
            sub_attrs,
            module_path=target_mod,
            harness=harness,
            target_pkg=target_pkg,
            eff_pkg_dir=eff_pkg_dir,
            parent_selected=parent_selected,
            pkg_spec=pkg_spec,
            excluded_files=excluded_files,
            hatch_exclude=hatch_exclude,
            check_manifest=check_manifest,
            _visited=next_visited,
        )

    root_names = _expand_aliases(attr_parts[0])
    first_local_err: str | None = None

    def _instance_call_sig_error(cand: str) -> str | None:
        cls_refs = instances.get(cand)
        if not cls_refs or cand in classes or cand in click_cmds:
            return None
        errs: list[str] = []
        for cls_ref in cls_refs:
            expanded = [c for c in _expand_aliases(cls_ref) if c in classes]
            if not expanded:
                return None
            for cls_name in expanded:
                for cls_node in classes[cls_name]:
                    if cls_node.decorator_list or cls_node.keywords:
                        return None
                    call_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None
                    for cs in cls_node.body:
                        if (
                            isinstance(cs, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and cs.name == "__call__"
                        ):
                            call_node = cs
                    if call_node is None or call_node.decorator_list:
                        return None
                    ok_zero, sig_err = _args_allow_zero_call(call_node.args, bound_self=True)
                    if ok_zero:
                        return None
                    errs.append(
                        f"callable '{cls_node.name}.__call__' in {py_file.name} {sig_err} "
                        "and cannot be invoked with zero arguments"
                    )
        return errs[0] if errs else None

    # Single-component callable (`module:main`): return directly if defined locally,
    # reject imported module objects and non-callable literals, and follow local re-exports
    # (`from .demoapp_cli import main`, `main = cli_mod.main`, wildcard exports honoring `__all__`, etc.).
    if len(attr_parts) == 1:
        for cand in root_names:
            if cand in direct_local_defs:
                inst_err = _instance_call_sig_error(cand)
                if inst_err is not None:
                    if first_local_err is None:
                        first_local_err = inst_err
                    continue
                return True, None, py_file

        has_external_binding = False
        for cand in root_names:
            # Module objects bound via `import ...` are never callable console-script targets.
            for target_mod in mod_imports.get(cand, ()):
                if first_local_err is None:
                    first_local_err = (
                        f"target '{attr_parts[0]}' resolves to imported module '{target_mod}' which is not callable"
                    )
            if cand in non_callable_local_defs:
                if first_local_err is None:
                    first_local_err = (
                        f"target '{attr_parts[0]}' resolves to a non-callable value in {py_file.name}"
                    )
            if cand in bad_sig_local_defs:
                if first_local_err is None:
                    first_local_err = bad_sig_local_defs[cand]

            for attr_chain in attr_aliases.get(cand, ()):
                ok_sub, sub_err, impl = _resolve_module_attr_path(
                    py_file,
                    list(attr_chain),
                    module_path=module_path,
                    harness=harness,
                    target_pkg=target_pkg,
                    eff_pkg_dir=eff_pkg_dir,
                    parent_selected=parent_selected,
                    pkg_spec=pkg_spec,
                    excluded_files=excluded_files,
                    hatch_exclude=hatch_exclude,
                    check_manifest=check_manifest,
                    _visited=next_visited,
                )
                if ok_sub:
                    return True, None, impl or py_file
                chain_roots = _expand_aliases(attr_chain[0])
                is_local_chain = any(
                    (r in direct_local_defs)
                    or (r in non_callable_local_defs)
                    or (r in bad_sig_local_defs)
                    or (r in classes)
                    or (r in instances)
                    or (r in click_cmds)
                    or (r in from_imports and any(_is_harness_mod_ref(bm, ir) for bm, _, ir in from_imports[r]))
                    or (r in mod_imports and any(_is_harness_mod_ref(tm, False) for tm in mod_imports[r]))
                    for r in chain_roots
                ) or any(
                    attr_chain[0] == di[0] and _is_harness_mod_ref(".".join(di), False)
                    for di in dotted_imports
                )
                if is_local_chain:
                    if first_local_err is None and sub_err:
                        first_local_err = sub_err
                else:
                    has_external_binding = True

            for base_mod, orig_name, is_rel in from_imports.get(cand, ()):
                if harness is not None and eff_pkg_dir is not None:
                    # Check defining package/module symbol first (Python checks package attributes
                    # before falling back to importing a submodule of the same name).
                    if base_mod:
                        base_file, base_is_pkg = _resolve_local_module_file(
                            base_mod, harness, eff_pkg_dir
                        )
                        if base_file is not None:
                            ok_sub, sub_err, impl = _recurse_local(
                                base_mod, base_file, base_is_pkg, [orig_name]
                            )
                            if ok_sub:
                                return True, None, impl or base_file
                            sub_mod = f"{base_mod}.{orig_name}"
                            sub_file, _ = _resolve_local_module_file(sub_mod, harness, eff_pkg_dir)
                            if sub_file is not None:
                                if first_local_err is None:
                                    first_local_err = (
                                        f"target '{attr_parts[0]}' resolves to module '{sub_mod}' which is not callable"
                                    )
                            elif first_local_err is None and sub_err:
                                first_local_err = sub_err
                            continue
                    sub_mod = f"{base_mod}.{orig_name}" if base_mod else orig_name
                    sub_file, _ = _resolve_local_module_file(sub_mod, harness, eff_pkg_dir)
                    if sub_file is not None:
                        if first_local_err is None:
                            first_local_err = (
                                f"target '{attr_parts[0]}' resolves to module '{sub_mod}' which is not callable"
                            )
                        continue
                    if _is_harness_mod_ref(base_mod or orig_name, is_rel):
                        if first_local_err is None:
                            first_local_err = (
                                f"re-exported module '{base_mod or orig_name}' not found in harness"
                            )
                        continue
                if _is_known_external_module(base_mod, orig_name):
                    if first_local_err is None:
                        first_local_err = (
                            f"target '{attr_parts[0]}' resolves to module '{base_mod}.{orig_name}' which is not callable"
                        )
                else:
                    has_external_binding = True

        for star_mod, is_rel in star_imports:
            if harness is not None and eff_pkg_dir is not None:
                star_file, star_is_pkg = _resolve_local_module_file(star_mod, harness, eff_pkg_dir)
                if star_file is not None:
                    allowed, wc_err = _module_wildcard_allows(star_file, attr_parts[0])
                    if not allowed:
                        if first_local_err is None and wc_err:
                            first_local_err = wc_err
                        continue
                    ok_sub, sub_err, impl = _recurse_local(
                        star_mod, star_file, star_is_pkg, [attr_parts[0]]
                    )
                    if ok_sub:
                        return True, None, impl or star_file
                    if first_local_err is None and sub_err:
                        first_local_err = sub_err
                elif _is_harness_mod_ref(star_mod, is_rel):
                    if first_local_err is None:
                        first_local_err = f"re-exported module '{star_mod}' not found in harness"
                else:
                    has_external_binding = True
            else:
                has_external_binding = True

        if has_external_binding or first_local_err is None:
            return True, None, py_file
        return False, first_local_err, None

    def _check_assigned_value_callable(
        val: ast.AST | None,
        target_label: str,
        *,
        bound_self: bool = False,
    ) -> tuple[bool, str | None, Path | None]:
        if val is None:
            return True, None, py_file
        if _is_provably_non_callable_expr(val):
            return (
                False,
                f"target '{target_label}' is assigned a non-callable value in {py_file.name}",
                None,
            )
        if isinstance(val, ast.Lambda):
            ok_zero, sig_err = _args_allow_zero_call(val.args, bound_self=bound_self)
            if not ok_zero:
                return (
                    False,
                    f"target '{target_label}' in {py_file.name} {sig_err} and cannot be invoked with zero arguments",
                    None,
                )
            return True, None, py_file
        if isinstance(val, ast.Name):
            ok_ref, ref_err, ref_impl = _resolve_module_attr_path(
                py_file,
                [val.id],
                module_path=module_path,
                harness=harness,
                target_pkg=target_pkg,
                eff_pkg_dir=eff_pkg_dir,
                parent_selected=parent_selected,
                pkg_spec=pkg_spec,
                excluded_files=excluded_files,
                hatch_exclude=hatch_exclude,
                check_manifest=check_manifest,
                _visited=next_visited,
            )
            if ok_ref:
                return True, None, ref_impl or py_file
            return False, ref_err, None
        rhs_chain = _extract_attr_chain(val)
        if rhs_chain is not None and len(rhs_chain) >= 2:
            ok_ref, ref_err, ref_impl = _resolve_module_attr_path(
                py_file,
                list(rhs_chain),
                module_path=module_path,
                harness=harness,
                target_pkg=target_pkg,
                eff_pkg_dir=eff_pkg_dir,
                parent_selected=parent_selected,
                pkg_spec=pkg_spec,
                excluded_files=excluded_files,
                hatch_exclude=hatch_exclude,
                check_manifest=check_manifest,
                _visited=next_visited,
            )
            if ok_ref:
                return True, None, ref_impl or py_file
            chain_roots = _expand_aliases(rhs_chain[0])
            is_local_ref = any(
                (r in direct_local_defs)
                or (r in non_callable_local_defs)
                or (r in bad_sig_local_defs)
                or (r in classes)
                or (r in instances)
                or (r in click_cmds)
                or (r in from_imports and any(_is_harness_mod_ref(bm, ir) for bm, _, ir in from_imports[r]))
                or (r in mod_imports and any(_is_harness_mod_ref(tm, False) for tm in mod_imports[r]))
                for r in chain_roots
            ) or any(
                rhs_chain[0] == di[0] and _is_harness_mod_ref(".".join(di), False)
                for di in dotted_imports
            )
            if is_local_ref:
                return False, ref_err, None
            return True, None, py_file
        return True, None, py_file

    tail = tuple(attr_parts[1:])

    # 1. Explicit module-scope attribute assignment (e.g. `main.sub = ...` or `A.B.c = ...`).
    matched_attr_vals: list[ast.AST | None] = []
    for cand in root_names:
        chain = (cand, *tail)
        if chain in attr_assign_values:
            matched_attr_vals.extend(attr_assign_values[chain])
    if matched_attr_vals:
        attr_err: str | None = None
        for assigned_val in matched_attr_vals:
            ok_val, val_err, impl = _check_assigned_value_callable(
                assigned_val, ".".join(attr_parts)
            )
            if ok_val:
                return True, None, impl or py_file
            if attr_err is None and val_err:
                attr_err = val_err
        if first_local_err is None and attr_err:
            first_local_err = attr_err

    # 2. Click Command / Group `.main` entrypoint (e.g. `@click.group() def cli(): ...` -> `cli.main`).
    if len(attr_parts) == 2 and attr_parts[1] == "main" and any(c in click_cmds for c in root_names):
        return True, None, py_file

    # 3. Local class (or alias / direct instance of a local class) attribute/method chain.
    def _is_property_decorated(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for dec in fn_node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "property":
                return True
        return False

    def _single_builtin_method_decorator(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        if len(fn_node.decorator_list) == 1 and isinstance(fn_node.decorator_list[0], ast.Name):
            dec_id = fn_node.decorator_list[0].id
            if dec_id in {"staticmethod", "classmethod"}:
                return dec_id
        return None

    def _class_defines_chain(
        cls_node: ast.ClassDef,
        rest: list[str],
        visited_cls: set[str],
        *,
        accessed_on_instance: bool = False,
    ) -> tuple[bool, str | None, Path | None]:
        if not rest:
            return True, None, py_file
        callable_names: set[str] = set()
        non_callable_names: set[str] = set()
        bad_sig_cls_names: dict[str, str] = {}
        cls_attr_vals: dict[str, list[ast.AST | None]] = {}
        nested_classes: dict[str, list[ast.ClassDef]] = {}
        cls_aliases: dict[str, list[str]] = {}
        cls_instances: dict[str, list[str]] = {}

        def _record_cls_assign(t: ast.AST, val: ast.AST | None, *, cls_top: bool) -> None:
            if isinstance(t, ast.Name):
                if val is not None and _is_provably_non_callable_expr(val):
                    if cls_top:
                        callable_names.discard(t.id)
                        bad_sig_cls_names.pop(t.id, None)
                        cls_attr_vals.pop(t.id, None)
                    non_callable_names.add(t.id)
                    return
                if cls_top:
                    non_callable_names.discard(t.id)
                    bad_sig_cls_names.pop(t.id, None)
                    cls_attr_vals[t.id] = [val]
                else:
                    cls_attr_vals.setdefault(t.id, []).append(val)
                if isinstance(val, ast.Name):
                    cls_aliases.setdefault(t.id, []).append(val.id)
                elif isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                    cls_instances.setdefault(t.id, []).append(val.func.id)
                elif isinstance(val, ast.Lambda):
                    pass
                else:
                    callable_names.add(t.id)
            else:
                for bn in _collect_target_names(t):
                    if cls_top:
                        non_callable_names.discard(bn)
                        bad_sig_cls_names.pop(bn, None)
                    callable_names.add(bn)

        def _scan_cls_body(body: list[ast.stmt], *, cls_top: bool) -> None:
            for s in body:
                if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if _is_property_decorated(s):
                        if cls_top:
                            callable_names.discard(s.name)
                            bad_sig_cls_names.pop(s.name, None)
                            cls_attr_vals.pop(s.name, None)
                        non_callable_names.add(s.name)
                    else:
                        builtin_dec = _single_builtin_method_decorator(s)
                        check_sig = (not s.decorator_list) or (builtin_dec is not None)
                        if check_sig:
                            is_bound = (
                                False
                                if builtin_dec == "staticmethod"
                                else (True if builtin_dec == "classmethod" else accessed_on_instance)
                            )
                            ok_zero, sig_err = _args_allow_zero_call(s.args, bound_self=is_bound)
                            if not ok_zero:
                                if cls_top:
                                    callable_names.discard(s.name)
                                    non_callable_names.discard(s.name)
                                    cls_attr_vals.pop(s.name, None)
                                bad_sig_cls_names[s.name] = (
                                    f"method '{cls_node.name}.{s.name}' in {py_file.name} {sig_err} "
                                    "and cannot be invoked with zero arguments"
                                )
                                continue
                        if cls_top:
                            non_callable_names.discard(s.name)
                            bad_sig_cls_names.pop(s.name, None)
                            cls_attr_vals.pop(s.name, None)
                        callable_names.add(s.name)
                elif isinstance(s, ast.ClassDef):
                    if cls_top:
                        non_callable_names.discard(s.name)
                        bad_sig_cls_names.pop(s.name, None)
                        cls_attr_vals.pop(s.name, None)
                    callable_names.add(s.name)
                    nested_classes.setdefault(s.name, []).append(s)
                elif isinstance(s, ast.Assign):
                    for t in s.targets:
                        _record_cls_assign(t, s.value, cls_top=cls_top)
                elif isinstance(s, ast.AnnAssign) and s.value is not None:
                    _record_cls_assign(s.target, s.value, cls_top=cls_top)
                elif isinstance(s, ast.ImportFrom):
                    resolved_mod = _resolve_import_from_module(s) or ""
                    for a in s.names:
                        if a.name == "*":
                            continue
                        bound = a.asname or a.name
                        is_mod = _is_known_external_module(resolved_mod, a.name)
                        if not is_mod and harness is not None and eff_pkg_dir is not None:
                            sub_mod = f"{resolved_mod}.{a.name}" if resolved_mod else a.name
                            sub_file, _ = _resolve_local_module_file(sub_mod, harness, eff_pkg_dir)
                            if sub_file is not None:
                                is_mod = True
                        if is_mod:
                            if cls_top:
                                callable_names.discard(bound)
                                bad_sig_cls_names.pop(bound, None)
                            non_callable_names.add(bound)
                        else:
                            if cls_top:
                                non_callable_names.discard(bound)
                                bad_sig_cls_names.pop(bound, None)
                            callable_names.add(bound)
                elif isinstance(s, ast.If):
                    _scan_cls_body(s.body, cls_top=False)
                    _scan_cls_body(s.orelse, cls_top=False)
                elif isinstance(s, (ast.For, ast.AsyncFor, ast.While)):
                    _scan_cls_body(s.body, cls_top=False)
                    _scan_cls_body(s.orelse, cls_top=False)
                elif isinstance(s, (ast.With, ast.AsyncWith)):
                    _scan_cls_body(s.body, cls_top=False)
                elif isinstance(s, ast.Try) or (try_star and isinstance(s, try_star)):
                    _scan_cls_body(s.body, cls_top=False)
                    _scan_cls_body(s.orelse, cls_top=False)
                    _scan_cls_body(s.finalbody, cls_top=False)
                    for h in s.handlers:
                        _scan_cls_body(h.body, cls_top=False)
                elif match_cls and isinstance(s, match_cls):
                    for c in s.cases:
                        _scan_cls_body(c.body, cls_top=False)

        _scan_cls_body(cls_node.body, cls_top=True)
        head = rest[0]
        cls_err: str | None = None
        if len(rest) == 1:
            if head in callable_names:
                return True, None, py_file
            if head in cls_attr_vals:
                for val in cls_attr_vals[head]:
                    ok_v, v_err, v_impl = _check_assigned_value_callable(
                        val, f"{cls_node.name}.{head}", bound_self=accessed_on_instance
                    )
                    if ok_v:
                        return True, None, v_impl or py_file
                    if cls_err is None and v_err:
                        cls_err = v_err
            if head in bad_sig_cls_names:
                return False, bad_sig_cls_names[head], None
            if head in non_callable_names:
                return (
                    False,
                    cls_err or f"class attribute '{cls_node.name}.{head}' is not callable in {py_file.name}",
                    None,
                )
        else:
            for nested in nested_classes.get(head, ()):
                ok_n, n_err, n_impl = _class_defines_chain(
                    nested, rest[1:], set(), accessed_on_instance=False
                )
                if ok_n:
                    return True, None, n_impl or py_file
                if cls_err is None and n_err:
                    cls_err = n_err
            for ref in cls_aliases.get(head, ()):
                for nested in nested_classes.get(ref, ()):
                    ok_n, n_err, n_impl = _class_defines_chain(
                        nested, rest[1:], set(), accessed_on_instance=False
                    )
                    if ok_n:
                        return True, None, n_impl or py_file
                    if cls_err is None and n_err:
                        cls_err = n_err
                for top_cls in classes.get(ref, ()):
                    if ref not in visited_cls:
                        ok_n, n_err, n_impl = _class_defines_chain(
                            top_cls, rest[1:], visited_cls | {ref}, accessed_on_instance=False
                        )
                        if ok_n:
                            return True, None, n_impl or py_file
                        if cls_err is None and n_err:
                            cls_err = n_err
            for ref in cls_instances.get(head, ()):
                for nested in nested_classes.get(ref, ()):
                    ok_n, n_err, n_impl = _class_defines_chain(
                        nested, rest[1:], set(), accessed_on_instance=True
                    )
                    if ok_n:
                        return True, None, n_impl or py_file
                    if cls_err is None and n_err:
                        cls_err = n_err
                for top_cls in classes.get(ref, ()):
                    if ref not in visited_cls:
                        ok_n, n_err, n_impl = _class_defines_chain(
                            top_cls, rest[1:], visited_cls | {ref}, accessed_on_instance=True
                        )
                        if ok_n:
                            return True, None, n_impl or py_file
                        if cls_err is None and n_err:
                            cls_err = n_err
            if (cls_node.name, *rest) in attr_assign_values:
                for assigned_val in attr_assign_values[(cls_node.name, *rest)]:
                    ok_v, v_err, v_impl = _check_assigned_value_callable(
                        assigned_val, f"{cls_node.name}.{'.'.join(rest)}"
                    )
                    if ok_v:
                        return True, None, v_impl or py_file
                    if cls_err is None and v_err:
                        cls_err = v_err

        for base in cls_node.bases:
            if isinstance(base, ast.Name) and base.id not in visited_cls:
                for base_cls in classes.get(base.id, ()):
                    ok_b, b_err, b_impl = _class_defines_chain(
                        base_cls,
                        rest,
                        visited_cls | {base.id},
                        accessed_on_instance=accessed_on_instance,
                    )
                    if ok_b:
                        return True, None, b_impl or py_file
                    if cls_err is None and b_err:
                        cls_err = b_err
        return False, cls_err, None

    candidate_classes: list[tuple[str, bool]] = []
    seen_cls_candidates: set[tuple[str, bool]] = set()
    for cand in root_names:
        if cand in classes and (cand, False) not in seen_cls_candidates:
            seen_cls_candidates.add((cand, False))
            candidate_classes.append((cand, False))
        for cls_ref in instances.get(cand, ()):
            for expanded_cls in _expand_aliases(cls_ref):
                if expanded_cls in classes and (expanded_cls, True) not in seen_cls_candidates:
                    seen_cls_candidates.add((expanded_cls, True))
                    candidate_classes.append((expanded_cls, True))
    for cls_name, is_inst in candidate_classes:
        for cls_node in classes.get(cls_name, ()):
            ok_cls, cls_err, cls_impl = _class_defines_chain(
                cls_node, attr_parts[1:], {cls_name}, accessed_on_instance=is_inst
            )
            if ok_cls:
                return True, None, cls_impl or py_file
            if first_local_err is None and cls_err:
                first_local_err = cls_err

    # 4. Local attribute aliases (e.g. `sub = demoapp_cli.Runner` -> `sub.run`).
    for cand in root_names:
        for attr_chain in attr_aliases.get(cand, ()):
            ok_sub, sub_err, impl = _resolve_module_attr_path(
                py_file,
                [*attr_chain, *attr_parts[1:]],
                module_path=module_path,
                harness=harness,
                target_pkg=target_pkg,
                eff_pkg_dir=eff_pkg_dir,
                parent_selected=parent_selected,
                pkg_spec=pkg_spec,
                excluded_files=excluded_files,
                hatch_exclude=hatch_exclude,
                check_manifest=check_manifest,
                _visited=next_visited,
            )
            if ok_sub:
                return True, None, impl or py_file
            if first_local_err is None and sub_err:
                first_local_err = sub_err

    # 5. Local imported submodule / symbol chain inside the harness.
    if harness is not None and eff_pkg_dir is not None:
        # 5a. Dotted `import a.b.c` where attr_parts starts with `a.b.c` (or a prefix).
        for imp_parts in dotted_imports:
            max_k = min(len(imp_parts), len(attr_parts) - 1)
            for k in range(max_k, 0, -1):
                if tuple(attr_parts[:k]) == imp_parts[:k]:
                    target_mod = ".".join(attr_parts[:k])
                    target_file, target_is_pkg = _resolve_local_module_file(
                        target_mod, harness, eff_pkg_dir
                    )
                    if target_file is not None:
                        ok_sub, sub_err, impl = _recurse_local(
                            target_mod, target_file, target_is_pkg, attr_parts[k:]
                        )
                        if ok_sub:
                            return True, None, impl or target_file
                        if first_local_err is None and sub_err:
                            first_local_err = sub_err

        for cand in root_names:
            # 5b. `import pkg.sub as alias` -> resolve `attr_parts[1:]` in `pkg.sub`.
            for target_mod in mod_imports.get(cand, ()):
                target_file, target_is_pkg = _resolve_local_module_file(
                    target_mod, harness, eff_pkg_dir
                )
                if target_file is not None:
                    ok_sub, sub_err, impl = _recurse_local(
                        target_mod, target_file, target_is_pkg, attr_parts[1:]
                    )
                    if ok_sub:
                        return True, None, impl or target_file
                    if first_local_err is None and sub_err:
                        first_local_err = sub_err

            # 5c. `from base_mod import orig_name [as cand]` -> submodule or symbol in base_mod.
            for base_mod, orig_name, _is_rel in from_imports.get(cand, ()):
                sub_mod = f"{base_mod}.{orig_name}" if base_mod else orig_name
                sub_file, sub_is_pkg = _resolve_local_module_file(sub_mod, harness, eff_pkg_dir)
                if sub_file is not None:
                    ok_sub, sub_err, impl = _recurse_local(
                        sub_mod, sub_file, sub_is_pkg, attr_parts[1:]
                    )
                    if ok_sub:
                        return True, None, impl or sub_file
                    if first_local_err is None and sub_err:
                        first_local_err = sub_err
                if base_mod:
                    base_file, base_is_pkg = _resolve_local_module_file(base_mod, harness, eff_pkg_dir)
                    if base_file is not None:
                        ok_sub, sub_err, impl = _recurse_local(
                            base_mod, base_file, base_is_pkg, [orig_name, *attr_parts[1:]]
                        )
                        if ok_sub:
                            return True, None, impl or base_file
                        if first_local_err is None and sub_err:
                            first_local_err = sub_err

        # 5d. Local `from .other import *` (must honor `__all__` and `_` visibility for `attr_parts[0]`).
        for star_mod, _is_rel in star_imports:
            star_file, star_is_pkg = _resolve_local_module_file(star_mod, harness, eff_pkg_dir)
            if star_file is not None:
                allowed, wc_err = _module_wildcard_allows(star_file, attr_parts[0])
                if not allowed:
                    if first_local_err is None and wc_err:
                        first_local_err = wc_err
                    continue
                ok_sub, sub_err, impl = _recurse_local(
                    star_mod, star_file, star_is_pkg, attr_parts
                )
                if ok_sub:
                    return True, None, impl or star_file
                if first_local_err is None and sub_err:
                    first_local_err = sub_err

    return (
        False,
        first_local_err
        or f"dotted callable '{'.'.join(attr_parts)}' could not be statically verified in {py_file.name}",
        None,
    )


def _module_defines_attr_path(
    py_file: Path,
    attr_parts: list[str],
    *,
    module_path: str | None = None,
    harness: Path | None = None,
    eff_pkg_dir: dict[str, str] | None = None,
    _visited: frozenset[tuple[Path, tuple[str, ...]]] = frozenset(),
) -> tuple[bool, str | None]:
    """Statically validate the full dotted callable path in py_file."""
    ok, err, _ = _resolve_module_attr_path(
        py_file,
        attr_parts,
        module_path=module_path,
        harness=harness,
        eff_pkg_dir=eff_pkg_dir,
        _visited=_visited,
    )
    return ok, err


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
    excluded_files: set[str] | None = None,
    hatch_exclude: list[str] | None = None,
    check_manifest: bool = False,
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

    try:
        mod_rel = mod_file.relative_to(harness).as_posix()
    except ValueError:
        mod_rel = ""

    if excluded_files and mod_rel and _poetry_is_excluded(mod_rel, excluded_files):
        return False, f"module '{module_path}' is excluded from wheel by packaging rules", None

    if hatch_exclude and mod_rel and _hatch_is_excluded(mod_rel, hatch_exclude):
        return False, f"module '{module_path}' is excluded from wheel by Hatch exclude rules", None

    if check_manifest and mod_rel and not _manifest_covers_skill(
        harness, mod_rel, initially_included=True
    ):
        return False, f"module '{module_path}' ({mod_rel}) is excluded from sdist by MANIFEST.in", None

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

    ok_sym, sym_err, impl_file = _resolve_module_attr_path(
        mod_file,
        attr_parts,
        module_path=module_path,
        harness=harness,
        target_pkg=target_pkg,
        eff_pkg_dir=eff_pkg_dir,
        parent_selected=parent_selected,
        pkg_spec=pkg_spec,
        excluded_files=excluded_files,
        hatch_exclude=hatch_exclude,
        check_manifest=check_manifest,
    )
    if not ok_sym:
        return False, sym_err or f"callable '{attr_path}' not found in '{module_path}'", None
    return True, "", impl_file or mod_file


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


def _hatch_norm_rel_path(raw: str) -> str:
    """Mirror hatchling.builders.utils.normalize_relative_path() using POSIX separators."""
    cleaned = _normalize_platform_seps(raw).strip("/")
    if not cleaned:
        return ""
    norm = PurePosixPath(cleaned).as_posix()
    return "" if norm == "." else norm


def _hatch_norm_rel_dir(raw: str) -> str:
    """Mirror hatchling.builders.utils.normalize_relative_directory() using POSIX separators."""
    norm = _hatch_norm_rel_path(raw)
    return f"{norm}/" if norm else ""


def _hatch_build_sources_map(
    raw_sources: Any,
    norm_packages: list[str],
) -> dict[str, str]:
    """Mirror hatchling.builders.config.BuilderConfig.sources (including package-path collapsing)."""
    sources: dict[str, str] = {}
    if isinstance(raw_sources, list):
        for src in raw_sources:
            if isinstance(src, str) and src and not _is_absolute_pattern(src):
                sources[_hatch_norm_rel_dir(src)] = ""
    elif isinstance(raw_sources, dict):
        for src, repl in raw_sources.items():
            if not isinstance(src, str) or not isinstance(repl, str):
                continue
            if (src and _is_absolute_pattern(src)) or (repl and _is_absolute_pattern(repl)):
                continue
            norm_repl = _hatch_norm_rel_path(repl)
            repl_str = f"{norm_repl}/" if norm_repl else ""
            src_key = _hatch_norm_rel_dir(src) if src else ""
            sources[src_key] = repl_str

    for rel_path in norm_packages:
        if "/" in rel_path:
            parent_dir = rel_path.rsplit("/", 1)[0]
            if parent_dir and _hatch_norm_rel_dir(rel_path) not in sources:
                sources[_hatch_norm_rel_dir(parent_dir)] = ""

    return dict(sorted(sources.items()))


def _hatch_distribution_path(rel_posix: str, sources_map: dict[str, str]) -> str:
    """Mirror hatchling.builders.config.BuilderConfig.get_distribution_path()."""
    for source, replacement in sources_map.items():
        if not source:
            return replacement + rel_posix
        if rel_posix.startswith(source):
            return rel_posix.replace(source, replacement, 1)
    return rel_posix


def _hatch_is_excluded(rel_posix: str, exclude_patterns: list[str]) -> bool:
    """Evaluate Hatch gitignore-style wheel exclude patterns against a project-relative POSIX path."""
    if not exclude_patterns:
        return False
    rel = _hatch_norm_rel_path(rel_posix)
    if not rel:
        return False
    parts = rel.split("/")
    ancestor_dirs = ["/".join(parts[:i]) for i in range(1, len(parts))]

    excluded = False
    for raw in exclude_patterns:
        if not isinstance(raw, str):
            continue
        pat = raw.strip()
        if not pat or pat.startswith("#"):
            continue
        negated = pat.startswith("!")
        if negated:
            pat = pat[1:]
            if not pat:
                continue
        dir_only = pat.endswith("/")
        pat_clean = pat.rstrip("/")
        anchored = pat_clean.startswith("/") or ("/" in pat_clean)
        pat_clean = pat_clean.lstrip("/")
        if not pat_clean:
            continue

        matched = False
        if dir_only:
            if anchored:
                matched = any(
                    _glob_matches_relpath(anc, pat_clean, recursive=True) for anc in ancestor_dirs
                )
            else:
                matched = any(fnmatch.fnmatchcase(p, pat_clean) for p in parts[:-1])
        else:
            if anchored:
                matched = _glob_matches_relpath(rel, pat_clean, recursive=True) or any(
                    _glob_matches_relpath(anc, pat_clean, recursive=True) for anc in ancestor_dirs
                )
            else:
                matched = any(fnmatch.fnmatchcase(p, pat_clean) for p in parts)

        if matched:
            excluded = not negated
    return excluded


def _hatch_packages_dir(
    target_pkg: str | None,
    packages: list[str],
    harness: Path | None = None,
    *,
    only_include: list[str] | None = None,
    raw_sources: Any = None,
) -> dict[str, str] | None:
    """Return effective package_dir mapping if Hatch wheel selection ships target_pkg under cli_anything/.

    Mirrors hatchling's `BuilderConfig.sources` + `get_distribution_path()` rewriting:
    multi-segment `packages` entries (e.g. `packages = ["cli_anything/demoapp"]`) strip their
    parent directory unless explicitly preserved in `sources`, whereas `only-include` preserves
    the path prefix unless rewritten by `sources`.
    """
    mod = target_pkg.split(".", 1)[1] if (target_pkg and "." in target_pkg) else None
    norm_packages = sorted(
        p
        for raw in packages
        if isinstance(raw, str)
        and not _is_absolute_pattern(raw)
        and (p := _hatch_norm_rel_path(raw))
        and not p.startswith("..")
    )
    norm_only_inc = [
        p
        for raw in (only_include or [])
        if isinstance(raw, str)
        and not _is_absolute_pattern(raw)
        and (p := _hatch_norm_rel_path(raw))
        and not p.startswith("..")
    ]
    selected_roots = norm_only_inc or norm_packages
    if not selected_roots:
        return None
    sources_map = _hatch_build_sources_map(raw_sources, norm_packages)

    expected_init = f"cli_anything/{mod}/__init__.py" if mod else None
    for sel_root in selected_roots:
        if mod and expected_init:
            # Case 1: sel_root is the namespace root (`cli_anything` or `src/cli_anything`).
            if _hatch_distribution_path(f"{sel_root}/{mod}/__init__.py", sources_map) == expected_init:
                if harness is None or (harness / sel_root / mod / "__init__.py").is_file():
                    return {} if sel_root == "cli_anything" else {"cli_anything": sel_root}
            # Case 2: sel_root is the app package dir itself (e.g. `only-include = ["cli_anything/demoapp"]`
            # or `packages = ["src/demoapp"]` with `sources = {"src/demoapp" = "cli_anything/demoapp"}`).
            if _hatch_distribution_path(f"{sel_root}/__init__.py", sources_map) == expected_init:
                if harness is None or (harness / sel_root / "__init__.py").is_file():
                    return {} if sel_root == f"cli_anything/{mod}" else {target_pkg: sel_root}  # type: ignore[dict-item]
        else:
            dist_dir = _hatch_distribution_path(f"{sel_root}/", sources_map)
            if dist_dir == "cli_anything/" or dist_dir.startswith("cli_anything/"):
                return {} if sel_root == "cli_anything" else {"cli_anything": sel_root}
    return None


def _poetry_entry_has_wheel_format(
    entry: dict[str, Any],
    *,
    default_formats: tuple[str, ...],
) -> bool:
    """Mirror poetry-core Factory._prepare_formats() + WheelBuilder format filtering."""
    if "format" not in entry:
        return "wheel" in default_formats
    raw_fmt = entry["format"]
    if isinstance(raw_fmt, str):
        return raw_fmt == "wheel"
    if isinstance(raw_fmt, list):
        return any(isinstance(f, str) and f == "wheel" for f in raw_fmt)
    return False


def _poetry_collect_glob_files(harness: Path, patterns: list[str]) -> set[str]:
    """Mirror poetry-core Builder add_all_files() over harness.glob() patterns."""
    files: set[str] = set()
    root_resolved = harness.resolve()
    for pat in patterns:
        if not pat or _is_absolute_pattern(pat):
            continue
        try:
            matches = list(harness.glob(pat))
        except (OSError, ValueError, NotImplementedError):
            continue
        for matched in matches:
            try:
                matched.resolve().relative_to(root_resolved)
            except (OSError, ValueError):
                continue
            if matched.is_dir():
                for child in matched.glob("**/*"):
                    if child.is_file():
                        try:
                            files.add(child.relative_to(harness).as_posix())
                        except ValueError:
                            pass
            elif matched.is_file():
                try:
                    files.add(matched.relative_to(harness).as_posix())
                except ValueError:
                    pass
    return files


def _poetry_wheel_file_sets(
    harness: Path,
    excludes: list[str],
    wheel_includes: list[str],
) -> tuple[set[str], set[str]]:
    """Return (excluded_files, explicitly_included_files) for a Poetry wheel build."""
    explicitly_excluded = _poetry_collect_glob_files(harness, excludes)
    explicitly_included = _poetry_collect_glob_files(harness, wheel_includes)
    return explicitly_excluded - explicitly_included, explicitly_included


def _poetry_is_excluded(rel_posix: str, excluded_files: set[str]) -> bool:
    """Mirror poetry-core Builder.is_excluded() for a project-root-relative POSIX path."""
    p = PurePosixPath(rel_posix)
    if "__pycache__" in p.parts or p.suffix == ".pyc":
        return True
    cur = p
    while True:
        if cur.as_posix() in excluded_files:
            return True
        if len(cur.parts) > 1:
            cur = cur.parent
        else:
            break
    return False


def _poetry_packages_dir(
    target_pkg: str | None,
    entries: list[tuple[str, ...]],
    harness: Path | None = None,
) -> dict[str, str] | None:
    """Return effective package_dir mapping if wheel-eligible Poetry packages cover target_pkg, else None."""
    mod = target_pkg.split(".", 1)[1] if (target_pkg and "." in target_pkg) else None
    for entry in entries:
        raw_inc = entry[0]
        raw_from = entry[1] if len(entry) > 1 else "."
        raw_to = entry[2] if len(entry) > 2 else ""
        if not raw_inc or _is_absolute_pattern(raw_inc):
            continue
        norm = _norm_pkg_dir_value(raw_inc)
        norm_from = _norm_pkg_dir_value(raw_from)
        norm_to = _norm_pkg_dir_value(raw_to)
        if norm_to == ".":
            norm_to = ""
        base_root = (harness / norm_from) if (harness is not None and norm_from not in {"", "."}) else harness
        if not norm_to:
            pkg_dir = {"": norm_from} if norm_from not in {"", "."} else {}
            if norm == "cli_anything":
                if base_root is None or not target_pkg:
                    return pkg_dir
                if _package_exists_under(base_root, target_pkg):
                    return pkg_dir
            elif mod and norm == f"cli_anything/{mod}":
                if base_root is None or not target_pkg:
                    return pkg_dir
                if _package_exists_under(base_root, target_pkg):
                    return pkg_dir
            elif not mod and norm.startswith("cli_anything/"):
                return pkg_dir
        elif norm_to == "cli_anything" and mod and norm == mod:
            src_rel = f"{norm_from}/{mod}" if norm_from not in {"", "."} else mod
            if base_root is None or (base_root / mod / "__init__.py").is_file():
                return {target_pkg: src_rel}  # type: ignore[dict-item]
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
    *,
    initially_included: bool = False,
) -> bool:
    """Evaluate MANIFEST.in directives in order (mirroring setuptools egg_info.FileList + build_py).

    When `initially_included=True` (package_data sdist survival check), starts with `canonical_rel`
    seeded by `add_defaults()` and checks whether any matching path survives MANIFEST.in removals.
    When `initially_included=False` (`include_package_data` check), tracks the exact emitted paths
    (including `./...` from `recursive-include . <pat>`) so `build_py.analyze_manifest()` matches.
    """
    if harness is None or not expected_manifest_rel:
        return False
    manifest = harness / "MANIFEST.in"
    if not manifest.is_file():
        return initially_included

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

    selected_paths: set[str] = {canonical_rel} if initially_included else set()
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

    if initially_included:
        return bool(selected_paths)
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
        "py_modules": [],
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
                elif kw.arg == "py_modules":
                    mods = _const_str_list(_resolve(kw.value))
                    if mods:
                        info["py_modules"] = list(mods)
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
        "declares_py_modules": False,
        "py_modules": [],
        "hatch_packages": [],
        "hatch_only_include": [],
        "hatch_sources": None,
        "hatch_exclude": [],
        "poetry_wheel_packages": [],
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
        "poetry_exclude": [],
        "poetry_wheel_include": [],
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
            py_mods_cfg = setuptools_cfg.get("py-modules")
            if isinstance(py_mods_cfg, list):
                info["declares_py_modules"] = True
                info["py_modules"] = [m for m in py_mods_cfg if isinstance(m, str)]
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
        hatch_wheel_dict = hatch_wheel if isinstance(hatch_wheel, dict) else {}
        hatch_build_dict = hatch_build if isinstance(hatch_build, dict) else {}

        hatch_pkgs = (
            hatch_wheel_dict["packages"]
            if "packages" in hatch_wheel_dict
            else hatch_build_dict.get("packages")
        )
        hatch_only_inc = (
            hatch_wheel_dict["only-include"]
            if "only-include" in hatch_wheel_dict
            else hatch_build_dict.get("only-include")
        )
        hatch_sources = (
            hatch_wheel_dict["sources"]
            if "sources" in hatch_wheel_dict
            else hatch_build_dict.get("sources")
        )
        hatch_excl = (
            hatch_wheel_dict["exclude"]
            if "exclude" in hatch_wheel_dict
            else hatch_build_dict.get("exclude")
        )
        if isinstance(hatch_excl, list):
            info["hatch_exclude"] = [x for x in hatch_excl if isinstance(x, str)]
        info["hatch_sources"] = hatch_sources

        if isinstance(hatch_pkgs, list) or isinstance(hatch_only_inc, list):
            info["declares_packages"] = True
            str_pkgs = [p for p in hatch_pkgs if isinstance(p, str)] if isinstance(hatch_pkgs, list) else []
            str_only_inc = (
                [p for p in hatch_only_inc if isinstance(p, str)]
                if isinstance(hatch_only_inc, list)
                else []
            )
            info["hatch_packages"] = str_pkgs
            info["hatch_only_include"] = str_only_inc
            hatch_pkg_dir = _hatch_packages_dir(
                target_pkg,
                str_pkgs,
                harness=harness,
                only_include=str_only_inc,
                raw_sources=hatch_sources,
            )
            if hatch_pkg_dir is not None:
                info["namespace_ok"] = True
                info["package_dir"].update(hatch_pkg_dir)
    elif backend_kind == "poetry":
        poetry_cfg = tool_dict.get("poetry")
        poetry_deps = poetry_cfg.get("dependencies") if isinstance(poetry_cfg, dict) else None
        if isinstance(poetry_deps, dict) and "python" in poetry_deps:
            info["has_python_requires"] = True
        if isinstance(poetry_cfg, dict):
            poetry_excl = poetry_cfg.get("exclude")
            if isinstance(poetry_excl, list):
                info["poetry_exclude"] = [x for x in poetry_excl if isinstance(x, str)]
            poetry_inc = poetry_cfg.get("include")
            if isinstance(poetry_inc, list):
                wheel_incs: list[str] = []
                for inc_item in poetry_inc:
                    # Bare string entries in [tool.poetry].include default to format=["sdist"] only.
                    if isinstance(inc_item, dict):
                        raw_path = inc_item.get("path")
                        if isinstance(raw_path, str) and _poetry_entry_has_wheel_format(
                            inc_item, default_formats=("sdist",)
                        ):
                            wheel_incs.append(raw_path)
                info["poetry_wheel_include"] = wheel_incs
        package_mode_disabled = isinstance(poetry_cfg, dict) and poetry_cfg.get("package-mode") is False
        poetry_pkgs = poetry_cfg.get("packages") if isinstance(poetry_cfg, dict) else None
        if isinstance(poetry_pkgs, list):
            info["declares_packages"] = True
            if not package_mode_disabled:
                pkg_entries: list[tuple[str, ...]] = [
                    (
                        str(p["include"]),
                        str(p.get("from", ".")) if isinstance(p.get("from", "."), str) else ".",
                        str(p.get("to", "")) if isinstance(p.get("to"), str) else "",
                    )
                    for p in poetry_pkgs
                    if isinstance(p, dict)
                    and isinstance(p.get("include"), str)
                    and _poetry_entry_has_wheel_format(p, default_formats=("sdist", "wheel"))
                ]
                info["poetry_wheel_packages"] = pkg_entries
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
        "py_modules": [],
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

        if "py_modules" in opts:
            info["py_modules"] = _parse_setup_cfg_list(opts["py_modules"])

        if "packages" in opts:
            raw_pkgs = opts["packages"].strip()
            if raw_pkgs:
                info["declares_packages"] = True
                if raw_pkgs == "find_namespace:":
                    find_sec = cp["options.packages.find"] if cp.has_section("options.packages.find") else {}
                    # Mirror setuptools setupcfg.parse_section_packages__find(): empty options are dropped
                    # and revert to their discovery defaults (unlike TOML where `include = []` is empty).
                    raw_wheres = _parse_setup_cfg_list(find_sec["where"]) if "where" in find_sec else []
                    wheres: list[str] | None = [raw_wheres[0]] if raw_wheres else None
                    raw_includes = _parse_setup_cfg_list(find_sec["include"]) if "include" in find_sec else []
                    includes: list[str] | None = raw_includes or None
                    raw_excludes = _parse_setup_cfg_list(find_sec["exclude"]) if "exclude" in find_sec else []
                    excludes: list[str] | None = raw_excludes or None
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
        "py_modules": [],
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

        cli_anything_selected = _is_subpkg_selected("cli_anything")
        if cli_anything_selected:
            _check_mapped_pkg_dir("cli_anything")

        raw_ns = _get_package_dir_rel("cli_anything", eff_package_dir)
        cand_ns_dir = (harness / raw_ns) if raw_ns else harness
        try:
            ns_is_eff_parent = cand_ns_dir.resolve() == effective_module.parent.resolve()
        except OSError:
            ns_is_eff_parent = cand_ns_dir == effective_module.parent
        if cli_anything_selected or ns_is_eff_parent:
            eff_subpkg_dirs["__namespace__"] = cand_ns_dir

        for sub_name in ("core", "utils", "tests", "skills"):
            sub_pkg = f"{target_pkg}.{sub_name}"
            if sub_name in ("core", "utils") or _is_subpkg_selected(sub_pkg):
                raw_sub = _get_package_dir_rel(sub_pkg, eff_package_dir)
                eff_subpkg_dirs[sub_name] = (harness / raw_sub) if raw_sub else harness
            else:
                eff_subpkg_dirs[sub_name] = effective_module / sub_name

    poetry_excluded_files: set[str] = set()
    poetry_wheel_included_files: set[str] = set()
    if has_pyproject and pyproj_info["backend_kind"] == "poetry":
        poetry_excluded_files, poetry_wheel_included_files = _poetry_wheel_file_sets(
            harness,
            pyproj_info["poetry_exclude"],
            pyproj_info["poetry_wheel_include"],
        )

    # Detect packaged top-level `cli_anything.py` modules that shadow the PEP 420 namespace.
    shadowing_ns_module: str | None = None
    if uses_setuptools:
        if pyproj_info["declares_py_modules"]:
            eff_py_modules = list(pyproj_info["py_modules"])
        elif uses_setup_py and setup_info["py_modules"]:
            eff_py_modules = list(setup_info["py_modules"])
        elif uses_setup_cfg and setup_cfg_info["py_modules"]:
            eff_py_modules = list(setup_cfg_info["py_modules"])
        else:
            eff_py_modules = []
        if "cli_anything" in eff_py_modules:
            root_dir_rel = _get_package_dir_rel("", eff_package_dir)
            ns_mod_path = (
                (harness / root_dir_rel / "cli_anything.py")
                if root_dir_rel
                else (harness / "cli_anything.py")
            )
            if ns_mod_path.is_file():
                shadowing_ns_module = (
                    f"{root_dir_rel}/cli_anything.py" if root_dir_rel else "cli_anything.py"
                )
    elif has_pyproject and pyproj_info["backend_kind"] == "poetry":
        if "cli_anything.py" in poetry_wheel_included_files:
            shadowing_ns_module = "cli_anything.py"
        else:
            for entry in pyproj_info["poetry_wheel_packages"]:
                raw_inc = entry[0]
                raw_from = entry[1] if len(entry) > 1 else "."
                raw_to = entry[2] if len(entry) > 2 else ""
                if not raw_inc or _is_absolute_pattern(raw_inc):
                    continue
                norm_inc = _norm_pkg_dir_value(raw_inc)
                norm_from = _norm_pkg_dir_value(raw_from)
                norm_to = _norm_pkg_dir_value(raw_to)
                if norm_to == ".":
                    norm_to = ""
                if not norm_to and norm_inc == "cli_anything.py":
                    cand = (
                        (harness / norm_from / "cli_anything.py")
                        if norm_from not in {"", "."}
                        else (harness / "cli_anything.py")
                    )
                    if cand.is_file():
                        try:
                            rel_cand = cand.relative_to(harness).as_posix()
                        except ValueError:
                            rel_cand = "cli_anything.py"
                        if not _poetry_is_excluded(rel_cand, poetry_excluded_files):
                            shadowing_ns_module = rel_cand
                            break
    elif has_pyproject and pyproj_info["backend_kind"] == "hatch":
        norm_hp_pkgs = sorted(
            p
            for raw in pyproj_info["hatch_packages"]
            if isinstance(raw, str)
            and not _is_absolute_pattern(raw)
            and (p := _hatch_norm_rel_path(raw))
            and not p.startswith("..")
        )
        norm_hp_only = [
            p
            for raw in pyproj_info["hatch_only_include"]
            if isinstance(raw, str)
            and not _is_absolute_pattern(raw)
            and (p := _hatch_norm_rel_path(raw))
            and not p.startswith("..")
        ]
        hp_sources = _hatch_build_sources_map(pyproj_info["hatch_sources"], norm_hp_pkgs)
        for sel_hp in (norm_hp_only or norm_hp_pkgs):
            if (
                _hatch_distribution_path(sel_hp, hp_sources) == "cli_anything.py"
                and (harness / sel_hp).is_file()
                and not _hatch_is_excluded(sel_hp, pyproj_info["hatch_exclude"])
            ):
                shadowing_ns_module = sel_hp
                break

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
    elif shadowing_ns_module:
        checks.append(
            CheckResult(
                "namespace-packages",
                "packaging",
                FAIL,
                f"packaged top-level module '{shadowing_ns_module}' shadows PEP 420 namespace package 'cli_anything'",
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
                excluded_files=poetry_excluded_files if (has_pyproject and pyproj_info["backend_kind"] == "poetry") else None,
                hatch_exclude=pyproj_info["hatch_exclude"] if (has_pyproject and pyproj_info["backend_kind"] == "hatch") else None,
                check_manifest=uses_setuptools,
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
    if has_pyproject and pyproj_info["backend_kind"] == "hatch":
        # Hatch includes non-Python assets inside selected package directories unless excluded.
        if pyproj_info["namespace_ok"] and target_pkg:
            raw_pkg_dir = _get_package_dir_rel(target_pkg, eff_package_dir)
            skill_path = (
                (harness / raw_pkg_dir / "skills" / "SKILL.md")
                if raw_pkg_dir
                else (harness / "skills" / "SKILL.md")
            )
            if skill_path.is_file():
                try:
                    skill_rel = skill_path.relative_to(harness).as_posix()
                except ValueError:
                    skill_rel = f"{raw_pkg_dir}/skills/SKILL.md" if raw_pkg_dir else "skills/SKILL.md"
                skill_data_ok = not _hatch_is_excluded(skill_rel, pyproj_info["hatch_exclude"])
            else:
                skill_data_ok = False
        else:
            skill_data_ok = False
    elif has_pyproject and pyproj_info["backend_kind"] == "poetry":
        # Poetry includes non-Python assets inside wheel-selected packages unless excluded
        # by [tool.poetry].exclude (and not re-included with format="wheel").
        if pyproj_info["namespace_ok"] and target_pkg:
            raw_pkg_dir = _get_package_dir_rel(target_pkg, eff_package_dir)
            skill_path = (
                (harness / raw_pkg_dir / "skills" / "SKILL.md")
                if raw_pkg_dir
                else (harness / "skills" / "SKILL.md")
            )
            expected_wheel_rel = f"{target_pkg.replace('.', '/')}/skills/SKILL.md"
            pkg_skill_included = False
            if skill_path.is_file():
                try:
                    skill_rel = skill_path.relative_to(harness).as_posix()
                except ValueError:
                    skill_rel = (
                        f"{raw_pkg_dir}/skills/SKILL.md" if raw_pkg_dir else "skills/SKILL.md"
                    )
                pkg_skill_included = not _poetry_is_excluded(skill_rel, poetry_excluded_files)
            skill_data_ok = pkg_skill_included or (
                expected_wheel_rel in poetry_wheel_included_files
            )
        else:
            skill_data_ok = False
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
            from_pd_raw = _pkg_data_matches_file(
                eff_pkg_data,
                pkg_name,
                rel_path,
                allow_star_wildcard=eff_pkg_star,
                exclusion=False,
            )
            expected_manifest_rel = f"{raw_pkg_dir}/{rel_path}" if raw_pkg_dir else rel_path
            from_pd = from_pd_raw and _manifest_covers_skill(
                harness, expected_manifest_rel, initially_included=True
            )
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


def _file_declares_click_group(py_file: Path) -> bool:
    """Return True if py_file declares a Click command group (resolving import and local aliases)."""
    text = _read_text(py_file)
    try:
        tree = ast.parse(text, filename=str(py_file))
    except SyntaxError:
        return "click" in text and ("@click.group" in text or "click.group" in text)

    click_mod_aliases: set[str] = set()
    group_factories: set[str] = set()
    command_factories: set[str] = set()
    group_classes: set[str] = set()

    def _expr_is_click_group_factory(expr: ast.AST) -> bool:
        if isinstance(expr, ast.Name) and expr.id in group_factories:
            return True
        chain = _extract_attr_chain(expr)
        if chain is not None:
            if len(chain) == 2 and chain[0] in click_mod_aliases and chain[1] in {"group", "Group", "MultiCommand"}:
                return True
            if chain in {
                ("click", "decorators", "group"),
                ("click", "core", "Group"),
                ("click", "core", "MultiCommand"),
            } and "click" in click_mod_aliases:
                return True
        return False

    def _expr_is_click_group_class(expr: ast.AST) -> bool:
        if isinstance(expr, ast.Name) and expr.id in group_classes:
            return True
        chain = _extract_attr_chain(expr)
        if chain is not None:
            if len(chain) == 2 and chain[0] in click_mod_aliases and chain[1] in {"Group", "MultiCommand"}:
                return True
            if chain in {("click", "core", "Group"), ("click", "core", "MultiCommand")} and "click" in click_mod_aliases:
                return True
        return False

    def _expr_is_click_command_factory(expr: ast.AST) -> bool:
        if isinstance(expr, ast.Name) and expr.id in command_factories:
            return True
        chain = _extract_attr_chain(expr)
        if chain is not None:
            if len(chain) == 2 and chain[0] in click_mod_aliases and chain[1] == "command":
                return True
            if chain == ("click", "decorators", "command") and "click" in click_mod_aliases:
                return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"click", "click.decorators", "click.core"}:
                    click_mod_aliases.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module in {"click", "click.decorators", "click.core"}:
                for alias in node.names:
                    if alias.name == "*":
                        group_factories.update({"group", "Group", "MultiCommand"})
                        group_classes.update({"Group", "MultiCommand"})
                        command_factories.add("command")
                        continue
                    bound = alias.asname or alias.name
                    if alias.name in {"group", "Group", "MultiCommand"}:
                        group_factories.add(bound)
                    if alias.name in {"Group", "MultiCommand"}:
                        group_classes.add(bound)
                    if alias.name == "command":
                        command_factories.add(bound)

    if not click_mod_aliases and not group_factories and not group_classes and not command_factories:
        return False

    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name not in group_classes and any(
                    _expr_is_click_group_class(b) for b in node.bases
                ):
                    group_classes.add(node.name)
                    group_factories.add(node.name)
                    changed = True
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        if tgt.id not in group_factories and _expr_is_click_group_factory(node.value):
                            group_factories.add(tgt.id)
                            changed = True
                        if tgt.id not in group_classes and _expr_is_click_group_class(node.value):
                            group_classes.add(tgt.id)
                            changed = True
                        if tgt.id not in command_factories and _expr_is_click_command_factory(node.value):
                            command_factories.add(tgt.id)
                            changed = True
            elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
                tname = node.target.id
                if tname not in group_factories and _expr_is_click_group_factory(node.value):
                    group_factories.add(tname)
                    changed = True
                if tname not in group_classes and _expr_is_click_group_class(node.value):
                    group_classes.add(tname)
                    changed = True
                if tname not in command_factories and _expr_is_click_command_factory(node.value):
                    command_factories.add(tname)
                    changed = True

    def _is_group_decorator_or_call(expr: ast.AST) -> bool:
        if _expr_is_click_group_factory(expr):
            return True
        if isinstance(expr, ast.Call):
            if _expr_is_click_group_factory(expr.func):
                return True
            if _expr_is_click_command_factory(expr.func):
                for kw in expr.keywords:
                    if kw.arg == "cls" and _expr_is_click_group_class(kw.value):
                        return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(_is_group_decorator_or_call(dec) for dec in node.decorator_list):
                return True
        elif isinstance(node, ast.Call):
            if _is_group_decorator_or_call(node):
                return True

    return False


def _file_has_invoke_without_command(py_file: Path, text: str) -> bool:
    if "invoke_without_command=True" in text:
        return True
    try:
        tree = ast.parse(text, filename=str(py_file))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (
                    kw.arg == "invoke_without_command"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    return True
    return False


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
        if all(_file_declares_click_group(p) for p in cli_files):
            checks.append(CheckResult("click-groups", "cli", PASS, "uses Click command groups"))
        else:
            checks.append(CheckResult("click-groups", "cli", FAIL, "CLI does not declare a Click command group"))

        if all('"--json"' in t or "'--json'" in t for t in cli_texts):
            checks.append(CheckResult("json-flag", "cli", PASS, "--json output flag declared"))
        else:
            checks.append(CheckResult("json-flag", "cli", FAIL, "missing --json flag in CLI entry point"))

        if all(_file_has_invoke_without_command(p, t) for p, t in zip(cli_files, cli_texts)):
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
