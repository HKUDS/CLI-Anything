"""Unit and CLI tests for verify_harness.py, list_harnesses.py, and pep420_guard.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import list_harnesses  # noqa: E402
import pep420_guard  # noqa: E402
import verify_harness  # noqa: E402

CANONICAL_REPL_SKIN = (
    Path(__file__).resolve().parent.parent.parent / "cli-anything-plugin" / "repl_skin.py"
)
if not CANONICAL_REPL_SKIN.is_file():
    CANONICAL_REPL_SKIN = SCRIPTS_DIR / "repl_skin.py"


def _create_valid_harness(root: Path, name: str = "demoapp") -> Path:
    """Create a minimal contract-compliant CLI-Anything harness under root/<name>/agent-harness."""
    harness = root / name / "agent-harness"
    pkg = harness / "cli_anything" / name
    for sub in ("core", "utils", "tests", "skills"):
        (pkg / sub).mkdir(parents=True, exist_ok=True)

    (harness / f"{name.upper()}.md").write_text("# DemoApp SOP\n", encoding="utf-8")
    (harness / "setup.py").write_text(
        f"""from setuptools import setup, find_namespace_packages
setup(
    name="cli-anything-{name}",
    version="1.2.3",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={{"cli_anything.{name}": ["skills/*.md"]}},
    entry_points={{"console_scripts": ["cli-anything-{name}=cli_anything.{name}.{name}_cli:main"]}},
)
""",
        encoding="utf-8",
    )

    (pkg / "__init__.py").write_text('"""DemoApp harness."""\n', encoding="utf-8")
    (pkg / "__main__.py").write_text(
        f"from cli_anything.{name}.{name}_cli import main\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (pkg / "README.md").write_text("# DemoApp CLI\n", encoding="utf-8")
    (pkg / f"{name}_cli.py").write_text(
        """import click

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True)
@click.option("--project", "project_path", default=None)
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_context
def cli(ctx, use_json, project_path, dry_run):
    if ctx.invoked_subcommand is None:
        click.echo("repl")

@cli.result_callback()
def auto_save(result, use_json, project_path, dry_run):
    return result

def main():
    cli()
""",
        encoding="utf-8",
    )
    (pkg / "core" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core" / "session.py").write_text("class Session:\n    pass\n", encoding="utf-8")
    (pkg / "utils" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "utils" / f"{name}_backend.py").write_text("def find_bin():\n    return 'demo'\n", encoding="utf-8")
    (pkg / "utils" / "repl_skin.py").write_text(
        CANONICAL_REPL_SKIN.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (pkg / "tests" / "TEST.md").write_text(
        "# Test Plan\n\n## Test Results\n\n2 passed in 0.10s\n",
        encoding="utf-8",
    )
    (pkg / "tests" / "test_core.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    (pkg / "tests" / "test_full_e2e.py").write_text(
        """import os

def _resolve_cli(name):
    _ = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED")
    return [name]

def test_e2e():
    assert _resolve_cli("cli-anything-demoapp")
""",
        encoding="utf-8",
    )
    (pkg / "skills" / "SKILL.md").write_text(
        f"""---
name: cli-anything-{name}
description: Stateful CLI harness for DemoApp with JSON output and REPL mode.
---

# DemoApp CLI Skill
""",
        encoding="utf-8",
    )
    return harness


def test_verify_valid_harness_strict(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path)
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert result["ok"] is True, result["checks"]
    assert result["errors"] == 0
    assert result["warnings"] == 0


def test_verify_catches_pep420_init_violation(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path)
    (harness / "cli_anything" / "__init__.py").write_text("# forbidden\n", encoding="utf-8")
    result = verify_harness.verify_harness(harness, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert result["ok"] is False
    ns_check = next(c for c in result["checks"] if c["id"] == "namespace-package")
    assert ns_check["status"] == "fail"


def test_verify_catches_missing_json_and_syntax_error(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path)
    cli_py = harness / "cli_anything" / "demoapp" / "demoapp_cli.py"
    cli_py.write_text("import click\n@click.group()\ndef cli():\n    pass\n", encoding="utf-8")
    (harness / "cli_anything" / "demoapp" / "core" / "broken.py").write_text(
        "def bad(:\n", encoding="utf-8"
    )
    result = verify_harness.verify_harness(harness, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert result["ok"] is False
    failed_ids = {c["id"] for c in result["checks"] if c["status"] == "fail"}
    assert "json-flag" in failed_ids
    assert "python-syntax" in failed_ids


def test_verify_warns_on_repl_skin_drift_bare_except_and_ellipsis(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path)
    (harness / "cli_anything" / "demoapp" / "utils" / "repl_skin.py").write_text(
        "# modified copy\n", encoding="utf-8"
    )
    (harness / "cli_anything" / "demoapp" / "core" / "session.py").write_text(
        "def load():\n    try:\n        return '/root/cli-anything/demo'\n    except:\n        return None\n",
        encoding="utf-8",
    )
    (harness / "cli_anything" / "demoapp" / "skills" / "SKILL.md").write_text(
        "---\nname: cli-anything-demoapp\ndescription: Truncated summary...\n---\n",
        encoding="utf-8",
    )
    normal = verify_harness.verify_harness(harness, strict=False, canonical_repl_skin=CANONICAL_REPL_SKIN)
    strict = verify_harness.verify_harness(harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert normal["ok"] is True
    assert strict["ok"] is False
    warn_ids = {c["id"] for c in normal["checks"] if c["status"] == "warn"}
    assert {"repl-skin", "no-bare-except", "no-hardcoded-root", "skill-frontmatter"} <= warn_ids


def test_verify_cli_json_and_all_mode(tmp_path: Path) -> None:
    _create_valid_harness(tmp_path, "alpha")
    _create_valid_harness(tmp_path, "beta")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "verify_harness.py"),
            str(tmp_path),
            "--all",
            "--json",
            "--strict",
            "--canonical-repl-skin",
            str(CANONICAL_REPL_SKIN),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["count"] == 2
    assert {h["software"] for h in data["harnesses"]} == {"alpha", "beta"}


def test_list_harnesses_discovers_generated_and_respects_depth(tmp_path: Path) -> None:
    _create_valid_harness(tmp_path, "alpha")
    nested = tmp_path / "group" / "sub"
    nested.mkdir(parents=True)
    _create_valid_harness(nested, "beta")

    all_gen = list_harnesses.scan_generated(tmp_path)
    assert set(all_gen.keys()) == {"alpha", "beta"}
    assert all_gen["alpha"]["version"] == "1.2.3"

    shallow = list_harnesses.scan_generated(tmp_path, max_depth=1)
    assert set(shallow.keys()) == {"alpha"}

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "list_harnesses.py"), "--path", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    names = {t["name"] for t in payload["tools"]}
    assert {"alpha", "beta"} <= names


def test_pep420_guard_blocks_namespace_init_and_allows_others() -> None:
    blocked_unix = pep420_guard.evaluate(
        {"toolCall": {"name": "write_file", "args": {"Path": "/repo/gimp/agent-harness/cli_anything/__init__.py"}}}
    )
    assert blocked_unix["decision"] == "deny"

    blocked_win = pep420_guard.evaluate(
        {"toolCall": {"name": "write_file", "args": {"Path": r"D:\src\gimp\agent-harness\cli_anything\__init__.py"}}}
    )
    assert blocked_win["decision"] == "deny"

    allowed_subpkg = pep420_guard.evaluate(
        {"toolCall": {"name": "write_file", "args": {"Path": r"D:\src\gimp\agent-harness\cli_anything\gimp\__init__.py"}}}
    )
    assert allowed_subpkg["decision"] == "allow"

    allowed_other = pep420_guard.evaluate(
        {"toolCall": {"name": "write_file", "args": {"Path": r"D:\src\app\__init__.py"}}}
    )
    assert allowed_other["decision"] == "allow"


def test_pep420_guard_subprocess_and_malformed_stdin_fail_open() -> None:
    proc = subprocess.run(
        [sys.executable, "-S", str(SCRIPTS_DIR / "pep420_guard.py")],
        input="not valid json{{{",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["decision"] == "allow"


def test_verify_handles_utf8_bom_and_pyproject_explicit_namespace(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "bomapp")
    # Add UTF-8 BOM to a Python source file (valid for Python's parser)
    helper = harness / "cli_anything" / "bomapp" / "utils" / "bom_helper.py"
    helper.write_bytes(b"\xef\xbb\xbfdef ok():\n    return True\n")
    # Replace setup.py with pyproject.toml declaring explicit cli_anything sub-package
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[project]
name = "cli-anything-bomapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-bomapp = "cli_anything.bomapp.bomapp_cli:main"

[tool.setuptools]
packages = ["cli_anything.bomapp", "cli_anything.bomapp.core", "cli_anything.bomapp.utils"]

[tool.setuptools.package-data]
"cli_anything.bomapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert result["ok"] is True, result["checks"]


def test_verify_detects_standalone_canonical_skill_drift(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "syncapp")
    pkg_skill = harness / "cli_anything" / "syncapp" / "skills" / "SKILL.md"
    canon_skill = tmp_path / "skills" / "cli-anything-syncapp" / "SKILL.md"
    canon_skill.parent.mkdir(parents=True, exist_ok=True)
    canon_skill.write_text(pkg_skill.read_text(encoding="utf-8"), encoding="utf-8")

    ok_res = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks_ok = {c["id"]: c for c in ok_res["checks"]}
    assert ok_res["ok"] is True
    assert checks_ok["root-skill-mirror"]["status"] == "pass"

    # Mutate canonical skill without updating packaged copy
    canon_skill.write_text(pkg_skill.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
    drift_res = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks_drift = {c["id"]: c for c in drift_res["checks"]}
    assert drift_res["ok"] is False
    assert checks_drift["root-skill-mirror"]["status"] == "warn"


def test_verify_rejects_regular_find_packages_with_namespace_glob(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "regpkg")
    setup_py = harness / "setup.py"
    setup_py.write_text(
        setup_py.read_text(encoding="utf-8").replace("find_namespace_packages", "find_packages"),
        encoding="utf-8",
    )
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks = {c["id"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert checks["namespace-packages"]["status"] == "fail"
    assert "find_packages()" in checks["namespace-packages"]["detail"]


def test_verify_rejects_missing_console_scripts_even_when_distribution_name_matches(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "nocmd")
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-nocmd",
    version="1.0.0",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.nocmd": ["skills/*.md"]},
    python_requires=">=3.10",
)
""",
        encoding="utf-8",
    )
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks = {c["id"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert checks["namespace-packages"]["status"] == "pass"
    assert checks["console-script"]["status"] == "fail"


def test_verify_rejects_pyproject_namespaces_false_and_missing_scripts(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "badtoml")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[project]
name = "cli-anything-badtoml"
version = "1.0.0"
requires-python = ">=3.10"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]
namespaces = false
""",
        encoding="utf-8",
    )
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks = {c["id"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert checks["namespace-packages"]["status"] == "fail"
    assert checks["console-script"]["status"] == "fail"


def test_verify_honors_pyproject_namespaces_false_even_with_valid_setup_py(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "bothcfg")
    # Add pyproject.toml overriding setup.py with namespaces = false (mirrors setuptools precedence)
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]
namespaces = false
""",
        encoding="utf-8",
    )
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks = {c["id"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert checks["namespace-packages"]["status"] == "fail"


def test_verify_scans_python_files_under_ancestor_named_build(tmp_path: Path) -> None:
    build_parent = tmp_path / "build"
    build_parent.mkdir()
    harness = _create_valid_harness(build_parent, "underbuild")
    cli_file = harness / "cli_anything" / "underbuild" / "underbuild_cli.py"
    cli_file.write_text("def broken(:\n", encoding="utf-8")

    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks = {c["id"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert checks["python-syntax"]["status"] == "fail"


def test_list_harnesses_skips_unreadable_namespace_dir(tmp_path: Path, monkeypatch) -> None:
    _create_valid_harness(tmp_path, "goodapp")
    bad_harness = _create_valid_harness(tmp_path, "lockedapp")
    locked_ns = (bad_harness / "cli_anything").resolve()

    orig_iterdir = Path.iterdir

    def _guarded_iterdir(self: Path):
        if self.resolve() == locked_ns:
            raise PermissionError(13, "Permission denied", str(self))
        return orig_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _guarded_iterdir)
    found = list_harnesses.scan_generated(tmp_path)
    assert "goodapp" in found
    assert "lockedapp" not in found
