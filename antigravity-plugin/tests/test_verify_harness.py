"""Unit and CLI tests for verify_harness.py, list_harnesses.py, and pep420_guard.py."""

from __future__ import annotations

import json
import shutil
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


def test_verify_respects_pep621_precedence_for_console_scripts(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "pep621app")
    # Accompanying [project] omitting scripts without dynamic = ["scripts"] causes setuptools to drop setup.py entry_points.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-pep621app"
version = "1.0.0"
requires-python = ">=3.10"
""",
        encoding="utf-8",
    )
    dropped = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    dropped_checks = {c["id"]: c for c in dropped["checks"]}
    assert dropped["ok"] is False
    assert dropped_checks["console-script"]["status"] == "fail"
    assert "project.dynamic" in dropped_checks["console-script"]["detail"]

    # Marking only entry-points (not scripts) dynamic still drops setup.py console_scripts in setuptools.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-pep621app"
version = "1.0.0"
requires-python = ">=3.10"
dynamic = ["entry-points"]
""",
        encoding="utf-8",
    )
    ep_only = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    ep_checks = {c["id"]: c for c in ep_only["checks"]}
    assert ep_only["ok"] is False
    assert ep_checks["console-script"]["status"] == "fail"

    # Marking scripts dynamic allows setuptools to retain setup.py console_scripts.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-pep621app"
version = "1.0.0"
requires-python = ">=3.10"
dynamic = ["scripts"]
""",
        encoding="utf-8",
    )
    kept = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert kept["ok"] is True, kept["checks"]


def test_verify_rejects_empty_setuptools_find_include_list(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "emptyinc")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[project]
name = "cli-anything-emptyinc"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-emptyinc = "cli_anything.emptyinc.emptyinc_cli:main"

[tool.setuptools.packages.find]
include = []

[tool.setuptools.package-data]
"cli_anything.emptyinc" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks = {c["id"]: c for c in result["checks"]}
    assert result["ok"] is False
    assert checks["namespace-packages"]["status"] == "fail"

    # Omitting include altogether still defaults to full PEP 420 discovery.
    (harness / "pyproject.toml").write_text(
        """[project]
name = "cli-anything-emptyinc"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-emptyinc = "cli_anything.emptyinc.emptyinc_cli:main"

[tool.setuptools.packages.find]
where = ["."]

[tool.setuptools.package-data]
"cli_anything.emptyinc" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    omitted = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert omitted["ok"] is True, omitted["checks"]


def test_verify_accepts_hatch_and_poetry_pyproject_namespace(tmp_path: Path) -> None:
    hatch_harness = _create_valid_harness(tmp_path / "hatch_case", "hatchapp")
    (hatch_harness / "setup.py").unlink()
    (hatch_harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cli-anything-hatchapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-hatchapp = "cli_anything.hatchapp.hatchapp_cli:main"

[tool.hatch.build.targets.wheel]
packages = ["cli_anything"]
package-data = {"cli_anything.hatchapp" = ["skills/*.md"]}
""",
        encoding="utf-8",
    )
    hatch_res = verify_harness.verify_harness(
        hatch_harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert hatch_res["ok"] is True, hatch_res["checks"]

    poetry_harness = _create_valid_harness(tmp_path / "poetry_case", "poetryapp")
    (poetry_harness / "setup.py").unlink()
    (poetry_harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "cli-anything-poetryapp"
version = "1.0.0"
packages = [{include = "cli_anything"}]
include = ["cli_anything/poetryapp/skills/*.md"]

[tool.poetry.dependencies]
python = ">=3.10"

[tool.poetry.scripts]
cli-anything-poetryapp = "cli_anything.poetryapp.poetryapp_cli:main"
""",
        encoding="utf-8",
    )
    poetry_res = verify_harness.verify_harness(
        poetry_harness, strict=False, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    poetry_checks = {c["id"]: c for c in poetry_res["checks"]}
    assert poetry_res["ok"] is True, poetry_res["checks"]
    assert poetry_checks["namespace-packages"]["status"] == "pass"
    assert poetry_checks["console-script"]["status"] == "pass"


def test_verify_applies_setuptools_find_exclusions(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path / "pyproj_exc", "excapp")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-excapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-excapp = "cli_anything.excapp.excapp_cli:main"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]
exclude = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.excapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    excluded = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    exc_checks = {c["id"]: c for c in excluded["checks"]}
    assert excluded["ok"] is False
    assert exc_checks["namespace-packages"]["status"] == "fail"

    # Excluding only tests keeps cli_anything.excapp selected.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-excapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-excapp = "cli_anything.excapp.excapp_cli:main"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]
exclude = ["cli_anything.*.tests*"]

[tool.setuptools.package-data]
"cli_anything.excapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    kept = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert kept["ok"] is True, kept["checks"]

    # setup.py find_namespace_packages(exclude=...) must also reject full exclusion.
    setup_harness = _create_valid_harness(tmp_path / "setup_exc", "setupexc")
    (setup_harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-setupexc",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["cli_anything.*"]),
    package_data={"cli_anything.setupexc": ["skills/*.md"]},
    entry_points={"console_scripts": ["cli-anything-setupexc=cli_anything.setupexc.setupexc_cli:main"]},
)
""",
        encoding="utf-8",
    )
    setup_res = verify_harness.verify_harness(
        setup_harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    setup_checks = {c["id"]: c for c in setup_res["checks"]}
    assert setup_res["ok"] is False
    assert setup_checks["namespace-packages"]["status"] == "fail"


def test_verify_restricts_backend_specific_scripts_and_packages_to_build_backend(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path / "stale_poetry", "staleapp")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-staleapp"
version = "1.0.0"
requires-python = ">=3.10"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.staleapp" = ["skills/*.md"]

[tool.poetry.scripts]
cli-anything-staleapp = "cli_anything.staleapp.staleapp_cli:main"
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

    # A non-setuptools backend (hatchling) must not fall back to setup.py packages or scripts.
    hatch_stale = _create_valid_harness(tmp_path / "hatch_ignores_setup", "hatchign")
    (hatch_stale / "pyproject.toml").write_text(
        """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cli-anything-hatchign"
version = "1.0.0"
requires-python = ">=3.10"
""",
        encoding="utf-8",
    )
    hatch_res = verify_harness.verify_harness(
        hatch_stale, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    hatch_checks = {c["id"]: c for c in hatch_res["checks"]}
    assert hatch_res["ok"] is False
    assert hatch_checks["namespace-packages"]["status"] == "fail"
    assert hatch_checks["console-script"]["status"] == "fail"


def test_verify_parses_inline_script_tables_on_py310_fallback(tmp_path: Path, monkeypatch) -> None:
    harness = _create_valid_harness(tmp_path, "inlineapp")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-inlineapp"
version = "1.0.0"
requires-python = ">=3.10"
scripts = {cli-anything-inlineapp = 'cli_anything.inlineapp.inlineapp_cli:main'}

[tool.setuptools.packages.find]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.inlineapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )

    # Simulate Python 3.10 where stdlib tomllib is unavailable.
    monkeypatch.setitem(sys.modules, "tomllib", None)
    result = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert result["ok"] is True, result["checks"]


def test_list_harnesses_merges_installed_and_generated_when_module_differs_from_dist_name(
    tmp_path: Path, monkeypatch
) -> None:
    harness = tmp_path / "iterm2" / "agent-harness"
    pkg = harness / "cli_anything" / "iterm2_ctl"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""iTerm2 harness."""\n', encoding="utf-8")
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
PACKAGE_NAME = "cli-anything-iterm2"
PACKAGE_VERSION = "1.4.2"
setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    packages=find_namespace_packages(include=["cli_anything.*"]),
    entry_points={"console_scripts": ["cli-anything-iterm2=cli_anything.iterm2_ctl.iterm2_ctl_cli:main"]},
)
""",
        encoding="utf-8",
    )

    generated = list_harnesses.scan_generated(tmp_path)
    assert list(generated.keys()) == ["iterm2"]
    assert generated["iterm2"]["version"] == "1.4.2"

    monkeypatch.setattr(
        list_harnesses,
        "scan_installed",
        lambda *, include_hub=False: {
            "iterm2": {
                "name": "iterm2",
                "status": "installed",
                "version": "1.4.2",
                "executable": "/usr/local/bin/cli-anything-iterm2",
                "source": None,
            }
        },
    )
    payload = list_harnesses.collect_tools(tmp_path)
    assert payload["total"] == 1
    assert payload["installed"] == 1
    assert payload["generated_only"] == 0
    assert payload["tools"][0]["name"] == "iterm2"
    assert payload["tools"][0]["source"] == "./iterm2/agent-harness"


def test_verify_honors_discovery_search_roots_in_pyproject_and_setup(tmp_path: Path, monkeypatch) -> None:
    # 1. pyproject.toml [tool.setuptools.packages.find] where = ["empty-src"] must fail (Python 3.11+ and 3.10 fallback).
    harness = _create_valid_harness(tmp_path / "pyproj_where", "whereapp")
    (harness / "empty-src").mkdir()
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-whereapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-whereapp = "cli_anything.whereapp.whereapp_cli:main"

[tool.setuptools.packages.find]
where = ["empty-src"]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.whereapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    bad_tomllib = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    bad_checks = {c["id"]: c for c in bad_tomllib["checks"]}
    assert bad_tomllib["ok"] is False
    assert bad_checks["namespace-packages"]["status"] == "fail"

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        bad_py310 = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert bad_py310["ok"] is False
        assert {c["id"]: c for c in bad_py310["checks"]}["namespace-packages"]["status"] == "fail"

    # Including "." alongside "empty-src" discovers the flat-layout package and passes.
    (harness / "pyproject.toml").write_text(
        (harness / "pyproject.toml").read_text(encoding="utf-8").replace(
            'where = ["empty-src"]', 'where = ["empty-src", "."]'
        ),
        encoding="utf-8",
    )
    good_multi = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert good_multi["ok"] is True, good_multi["checks"]

    # Explicitly empty where = [] must also fail.
    (harness / "pyproject.toml").write_text(
        (harness / "pyproject.toml").read_text(encoding="utf-8").replace(
            'where = ["empty-src", "."]', "where = []"
        ),
        encoding="utf-8",
    )
    empty_where = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert empty_where["ok"] is False
    assert {c["id"]: c for c in empty_where["checks"]}["namespace-packages"]["status"] == "fail"

    # 2. setup.py find_namespace_packages(where="empty-src", ...) and positional find_namespace_packages("empty-src", ...)
    for expr in (
        'find_namespace_packages(where="empty-src", include=["cli_anything.*"])',
        'find_namespace_packages("empty-src", include=["cli_anything.*"])',
    ):
        sh = _create_valid_harness(tmp_path / f"setup_{abs(hash(expr))}", "swhere")
        (sh / "empty-src").mkdir()
        (sh / "setup.py").write_text(
            f"""from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-swhere",
    version="1.0.0",
    python_requires=">=3.10",
    packages={expr},
    package_data={{"cli_anything.swhere": ["skills/*.md"]}},
    entry_points={{"console_scripts": ["cli-anything-swhere=cli_anything.swhere.swhere_cli:main"]}},
)
""",
            encoding="utf-8",
        )
        sres = verify_harness.verify_harness(sh, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
        assert sres["ok"] is False
        assert {c["id"]: c for c in sres["checks"]}["namespace-packages"]["status"] == "fail"

    # 3. Poetry packages = [{include = "cli_anything", from = "empty-src"}] must also fail when empty-src lacks the package.
    ph = _create_valid_harness(tmp_path / "poetry_where", "pwhere")
    (ph / "empty-src").mkdir()
    (ph / "setup.py").unlink()
    (ph / "pyproject.toml").write_text(
        """[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "cli-anything-pwhere"
version = "1.0.0"
packages = [{include = "cli_anything", from = "empty-src"}]

[tool.poetry.scripts]
cli-anything-pwhere = "cli_anything.pwhere.pwhere_cli:main"
""",
        encoding="utf-8",
    )
    pres = verify_harness.verify_harness(ph, strict=False, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert {c["id"]: c for c in pres["checks"]}["namespace-packages"]["status"] == "fail"


def test_verify_rejects_reserved_project_entry_points_console_scripts(
    tmp_path: Path, monkeypatch
) -> None:
    harness = _create_valid_harness(tmp_path, "resept")
    # Valid legacy setup.py + [project.entry-points.console_scripts] (reserved under PEP 621):
    # setuptools drops console_scripts and produces no entry_points.txt.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-resept"
version = "1.0.0"
requires-python = ">=3.10"

[project.entry-points.console_scripts]
cli-anything-resept = "cli_anything.resept.resept_cli:main"
""",
        encoding="utf-8",
    )
    res_tomllib = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks_tomllib = {c["id"]: c for c in res_tomllib["checks"]}
    assert res_tomllib["ok"] is False
    assert checks_tomllib["console-script"]["status"] == "fail"
    assert "reserved" in checks_tomllib["console-script"]["detail"]

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        res_py310 = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        checks_py310 = {c["id"]: c for c in res_py310["checks"]}
        assert res_py310["ok"] is False
        assert checks_py310["console-script"]["status"] == "fail"
        assert "reserved" in checks_py310["console-script"]["detail"]


def test_verify_checks_package_data_skills_against_actual_harness_package(
    tmp_path: Path, monkeypatch
) -> None:
    # 1. Copied package_data key for another package must warn (and fail strict).
    harness = _create_valid_harness(tmp_path / "wrong_key", "pdapp")
    (harness / "setup.py").write_text(
        (harness / "setup.py").read_text(encoding="utf-8").replace(
            '"cli_anything.pdapp"', '"cli_anything.otherapp"'
        ),
        encoding="utf-8",
    )
    wrong = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert wrong["ok"] is False
    assert {c["id"]: c for c in wrong["checks"]}["package-data-skills"]["status"] == "warn"

    # 2. Root-only '*.md' does not include skills/SKILL.md under setuptools.
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-pdapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.pdapp": ["*.md"]},
    entry_points={"console_scripts": ["cli-anything-pdapp=cli_anything.pdapp.pdapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    root_only = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert root_only["ok"] is False
    assert {c["id"]: c for c in root_only["checks"]}["package-data-skills"]["status"] == "warn"

    # 3. Subpackage key cli_anything.pdapp.skills with SKILL.md passes.
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-pdapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.pdapp.skills": ["SKILL.md"]},
    entry_points={"console_scripts": ["cli-anything-pdapp=cli_anything.pdapp.pdapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    subpkg_ok = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert subpkg_ok["ok"] is True, subpkg_ok["checks"]

    # 4. pyproject.toml [tool.setuptools.package-data] targeting another package overrides setup.py.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-pdapp"
version = "1.0.0"
requires-python = ">=3.10"
dynamic = ["scripts"]

[tool.setuptools.package-data]
"cli_anything.otherapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    pyproj_wrong = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert pyproj_wrong["ok"] is False
    assert {c["id"]: c for c in pyproj_wrong["checks"]}["package-data-skills"]["status"] == "warn"

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        pyproj_wrong_310 = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert pyproj_wrong_310["ok"] is False
        assert {c["id"]: c for c in pyproj_wrong_310["checks"]}["package-data-skills"]["status"] == "warn"

    # Fixing the pyproject.toml package-data key passes strict verification.
    (harness / "pyproject.toml").write_text(
        (harness / "pyproject.toml").read_text(encoding="utf-8").replace(
            '"cli_anything.otherapp"', '"cli_anything.pdapp"'
        ),
        encoding="utf-8",
    )
    pyproj_ok = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert pyproj_ok["ok"] is True, pyproj_ok["checks"]


def test_verify_handles_recursive_glob_setup_star_key_exclude_and_manifest_order(
    tmp_path: Path, monkeypatch
) -> None:
    # 1. Recursive glob `skills/**/*.md` matches `skills/SKILL.md` (zero intermediate dirs).
    h_glob = _create_valid_harness(tmp_path / "rec_glob", "globapp")
    (h_glob / "setup.py").write_text(
        (h_glob / "setup.py").read_text(encoding="utf-8").replace("skills/*.md", "skills/**/*.md"),
        encoding="utf-8",
    )
    res_glob = verify_harness.verify_harness(
        h_glob, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert res_glob["ok"] is True, res_glob["checks"]

    # 2. setup.py `package_data={"*": ["skills/*.md"]}` is NOT a wildcard in setuptools -> must warn.
    h_star = _create_valid_harness(tmp_path / "setup_star", "starapp")
    (h_star / "setup.py").write_text(
        (h_star / "setup.py").read_text(encoding="utf-8").replace('"cli_anything.starapp"', '"*"'),
        encoding="utf-8",
    )
    res_star = verify_harness.verify_harness(
        h_star, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert res_star["ok"] is False
    assert {c["id"]: c for c in res_star["checks"]}["package-data-skills"]["status"] == "warn"

    # Empty string `""` IS the setup.py wildcard -> passes.
    (h_star / "setup.py").write_text(
        (h_star / "setup.py").read_text(encoding="utf-8").replace('"*"', '""'),
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(
        h_star, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    # TOML `[tool.setuptools.package-data]` `"*"` IS normalized by setuptools -> passes (tomllib & py310).
    (h_star / "setup.py").unlink()
    (h_star / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-starapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-starapp = "cli_anything.starapp.starapp_cli:main"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"*" = ["skills/**/*.md"]
""",
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(
        h_star, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True
    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        assert verify_harness.verify_harness(
            h_star, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )["ok"] is True

    # Adding `[tool.setuptools.exclude-package-data]` excluding skills/*.md must warn.
    (h_star / "pyproject.toml").write_text(
        (h_star / "pyproject.toml").read_text(encoding="utf-8")
        + '\n[tool.setuptools.exclude-package-data]\n"*" = ["skills/*.md"]\n',
        encoding="utf-8",
    )
    res_excl = verify_harness.verify_harness(
        h_star, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert res_excl["ok"] is False
    assert {c["id"]: c for c in res_excl["checks"]}["package-data-skills"]["status"] == "warn"

    # 3. MANIFEST.in with include_package_data=True evaluates concrete target path and ordered exclusions.
    h_man = _create_valid_harness(tmp_path / "manifest_case", "manapp")
    (h_man / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-manapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    entry_points={"console_scripts": ["cli-anything-manapp=cli_anything.manapp.manapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    # Unrelated include for another app -> warn
    (h_man / "MANIFEST.in").write_text(
        "include cli_anything/otherapp/skills/SKILL.md\n", encoding="utf-8"
    )
    r_other = verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_other["ok"] is False
    assert {c["id"]: c for c in r_other["checks"]}["package-data-skills"]["status"] == "warn"

    # Matching recursive-include followed by prune -> warn
    (h_man / "MANIFEST.in").write_text(
        "recursive-include cli_anything *.md\nprune cli_anything/manapp/skills\n",
        encoding="utf-8",
    )
    r_pruned = verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_pruned["ok"] is False
    assert {c["id"]: c for c in r_pruned["checks"]}["package-data-skills"]["status"] == "warn"

    # Matching recursive-include without exclusion -> pass
    (h_man / "MANIFEST.in").write_text(
        "recursive-include cli_anything *.md\n",
        encoding="utf-8",
    )
    r_man_ok = verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_man_ok["ok"] is True, r_man_ok["checks"]

    # Wildcard directory prune `prune cli_anything/*/skills` excludes the skill.
    (h_man / "MANIFEST.in").write_text(
        "recursive-include cli_anything/manapp/skills *.md\nprune cli_anything/*/skills\n",
        encoding="utf-8",
    )
    r_wild_prune = verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_wild_prune["ok"] is False
    assert {c["id"]: c for c in r_wild_prune["checks"]}["package-data-skills"]["status"] == "warn"

    # Wildcard directory graft / recursive-include selects the skill.
    (h_man / "MANIFEST.in").write_text(
        "graft cli_anything/*/skills\n",
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)["ok"] is True

    (h_man / "MANIFEST.in").write_text(
        "recursive-include cli_anything/*/skills *.md\nrecursive-exclude cli_anything/*/skills *.md\n",
        encoding="utf-8",
    )
    r_wild_rexcl = verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_wild_rexcl["ok"] is False
    assert {c["id"]: c for c in r_wild_rexcl["checks"]}["package-data-skills"]["status"] == "warn"

    # 4. setup.py exclude_package_data uses fnmatch semantics where `*.md` matches `skills/SKILL.md`.
    h_fnm = _create_valid_harness(tmp_path / "excl_fnmatch", "fnmapp")
    (h_fnm / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-fnmapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.fnmapp": ["skills/*.md"]},
    exclude_package_data={"cli_anything.fnmapp": ["*.md"]},
    entry_points={"console_scripts": ["cli-anything-fnmapp=cli_anything.fnmapp.fnmapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    r_fnm = verify_harness.verify_harness(h_fnm, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_fnm["ok"] is False
    assert {c["id"]: c for c in r_fnm["checks"]}["package-data-skills"]["status"] == "warn"

    # 5. graft **/skills must NOT match cli_anything/<pkg>/skills (graft uses non-recursive glob).
    (h_man / "MANIFEST.in").write_text("graft **/skills\n", encoding="utf-8")
    r_graft_rec = verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_graft_rec["ok"] is False
    assert {c["id"]: c for c in r_graft_rec["checks"]}["package-data-skills"]["status"] == "warn"

    # 6. Subpackage package_data is only credited when discovery selects cli_anything.<pkg>.skills,
    #    and manifest ownership + exclude_package_data are evaluated per supplying package.
    h_sub = _create_valid_harness(tmp_path / "subpkg_excl", "subapp")
    (h_sub / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-subapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["cli_anything.*.skills"]),
    package_data={"cli_anything.subapp.skills": ["*.md"]},
    entry_points={"console_scripts": ["cli-anything-subapp=cli_anything.subapp.subapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    r_sub_excl = verify_harness.verify_harness(h_sub, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_sub_excl["ok"] is False
    assert {c["id"]: c for c in r_sub_excl["checks"]}["package-data-skills"]["status"] == "warn"

    # When namespace discovery selects cli_anything.subapp.skills, manifest SKILL.md belongs to that
    # subpackage so a parent-only exclude_package_data does not remove it.
    (h_sub / "MANIFEST.in").write_text("recursive-include cli_anything *.md\n", encoding="utf-8")
    (h_sub / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-subapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    exclude_package_data={"cli_anything.subapp": ["*.md"]},
    entry_points={"console_scripts": ["cli-anything-subapp=cli_anything.subapp.subapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    r_parent_excl_only = verify_harness.verify_harness(h_sub, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_parent_excl_only["ok"] is True, r_parent_excl_only["checks"]

    # Once cli_anything.subapp.skills is excluded from discovery, SKILL.md belongs to the parent
    # package and the same parent exclusion removes it.
    (h_sub / "setup.py").write_text(
        (h_sub / "setup.py").read_text(encoding="utf-8").replace(
            'include=["cli_anything.*"]',
            'include=["cli_anything.*"], exclude=["cli_anything.*.skills"]',
        ),
        encoding="utf-8",
    )
    r_parent_owns_and_excl = verify_harness.verify_harness(h_sub, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_parent_owns_and_excl["ok"] is False
    assert {c["id"]: c for c in r_parent_owns_and_excl["checks"]}["package-data-skills"]["status"] == "warn"

    # 7. Platform-aware fnmatch exclusion (case-insensitive on Windows, case-sensitive on POSIX).
    (h_fnm / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-fnmapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.fnmapp": ["skills/*.md"]},
    exclude_package_data={"cli_anything.fnmapp": ["skills/skill.md"]},
    entry_points={"console_scripts": ["cli-anything-fnmapp=cli_anything.fnmapp.fnmapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    r_case = verify_harness.verify_harness(h_fnm, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    if sys.platform == "win32":
        assert r_case["ok"] is False
        assert {c["id"]: c for c in r_case["checks"]}["package-data-skills"]["status"] == "warn"
    else:
        assert r_case["ok"] is True, r_case["checks"]

    # 7b. Platform-aware package_data inclusion glob (`skills/*.MD` matches `skills/SKILL.md` on Windows, not POSIX).
    (h_fnm / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-fnmapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.fnmapp": ["skills/*.MD"]},
    entry_points={"console_scripts": ["cli-anything-fnmapp=cli_anything.fnmapp.fnmapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    r_inc_case = verify_harness.verify_harness(h_fnm, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    if sys.platform == "win32":
        assert r_inc_case["ok"] is True, r_inc_case["checks"]
    else:
        assert r_inc_case["ok"] is False
        assert {c["id"]: c for c in r_inc_case["checks"]}["package-data-skills"]["status"] == "warn"

    # 8. Absolute globs in package_data or MANIFEST.in must NOT be treated as package-relative.
    h_abs = _create_valid_harness(tmp_path / "abs_glob", "absapp")
    (h_abs / "setup.py").write_text(
        (h_abs / "setup.py").read_text(encoding="utf-8").replace("skills/*.md", "/skills/*.md"),
        encoding="utf-8",
    )
    r_abs = verify_harness.verify_harness(h_abs, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_abs["ok"] is False
    assert {c["id"]: c for c in r_abs["checks"]}["package-data-skills"]["status"] == "warn"

    (h_man / "MANIFEST.in").write_text("graft /cli_anything\n", encoding="utf-8")
    r_abs_man = verify_harness.verify_harness(h_man, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN)
    assert r_abs_man["ok"] is False
    assert {c["id"]: c for c in r_abs_man["checks"]}["package-data-skills"]["status"] == "warn"

    # 9. Inline [tool.setuptools] packages = {find = {...}} works identically on Python 3.10 fallback.
    h_inl = _create_valid_harness(tmp_path / "inline_find", "inlapp")
    (h_inl / "setup.py").unlink()
    (h_inl / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-inlapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-inlapp = "cli_anything.inlapp.inlapp_cli:main"

[tool.setuptools]
packages = {find = {include = ["cli_anything.*"]}}

[tool.setuptools.package-data]
"cli_anything.inlapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        r_inl = verify_harness.verify_harness(
            h_inl, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_inl["ok"] is True, r_inl["checks"]


def test_pyproject_py310_fallback_matches_tomllib_semantics(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "demoapp")
    (harness / "empty-src").mkdir()
    target = "cli_anything.demoapp"
    samples = [
        """[project]
name = "cli-anything-demoapp"
version = "1.0.0"
""",
        """[project]
name = "cli-anything-demoapp"
version = "1.0.0"
dynamic = [
    "scripts",
]
""",
        """[project]
name = "cli-anything-demoapp"
version = "1.0.0"
scripts = {cli-anything-demoapp = 'cli_anything.demoapp.demoapp_cli:main'}
""",
        """[project]
name = "cli-anything-demoapp"
version = "1.0.0"
entry-points = { console_scripts = { "cli-anything-demoapp" = "cli_anything.demoapp.demoapp_cli:main" } }
""",
        """[tool.setuptools.packages.find]
include = []
""",
        """[tool.setuptools.packages.find]
where = ["."]
""",
        """[tool.setuptools.packages.find]
where = ["empty-src"]
include = ["cli_anything.*"]
""",
        """[tool.setuptools.packages.find]
include = ["cli_anything.*"]
exclude = ["cli_anything.*"]
""",
        """[tool.setuptools.packages.find]
include = ["cli_anything.*"]
exclude = ["cli_anything.*.tests*"]
""",
        """[tool.setuptools.packages]
find = { where = ["empty-src"], include = ["cli_anything.*"] }
""",
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-demoapp"
version = "1.0.0"

[tool.poetry.scripts]
cli-anything-demoapp = "cli_anything.demoapp.demoapp_cli:main"
""",
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-demoapp"
version = "1.0.0"

[tool.setuptools]
include-package-data = false

[tool.setuptools.package-data]
"*" = ["skills/**/*.md"]

[tool.setuptools.exclude-package-data]
"cli_anything.demoapp" = ["skills/*.txt"]
""",
        """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["cli_anything"]
""",
        """[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
packages = [
    {include = "cli_anything", from = "empty-src"},
]

[tool.poetry.scripts]
cli-anything-demoapp = "cli_anything.demoapp.demoapp_cli:main"
""",
        """[tool.setuptools]
packages = {find = {include = ["cli_anything.*"]}}
""",
        """[tool.setuptools]
packages.find.include = ["cli_anything.*"]
""",
        """[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[[tool.poetry.packages]]
include = "cli_anything"
from = "."

[tool.poetry.scripts]
cli-anything-demoapp = "cli_anything.demoapp.demoapp_cli:main"
""",
    ]
    try:
        import tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]

    for sample in samples:
        if tomllib is not None:
            assert verify_harness._loads_toml_fallback(sample) == tomllib.loads(sample), sample
        assert verify_harness._inspect_pyproject_toml_fallback(
            sample, target_pkg=target, harness=harness
        ) == verify_harness._inspect_pyproject_toml(sample, target_pkg=target, harness=harness), sample


def test_verify_validates_console_script_targets_in_setup_and_pyproject(
    tmp_path: Path, monkeypatch
) -> None:
    # 1. setup.py pointing to a nonexistent module fails strict verification.
    h_missing_mod = _create_valid_harness(tmp_path / "missing_mod", "tapp")
    (h_missing_mod / "setup.py").write_text(
        (h_missing_mod / "setup.py")
        .read_text(encoding="utf-8")
        .replace("cli_anything.tapp.tapp_cli:main", "cli_anything.tapp.missing_cli:main"),
        encoding="utf-8",
    )
    r_missing_mod = verify_harness.verify_harness(
        h_missing_mod, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_missing_mod["ok"] is False
    assert {c["id"]: c for c in r_missing_mod["checks"]}["console-script"]["status"] == "fail"

    # 2. setup.py pointing to a nonexistent callable in an existing module fails.
    (h_missing_mod / "setup.py").write_text(
        (h_missing_mod / "setup.py")
        .read_text(encoding="utf-8")
        .replace("cli_anything.tapp.missing_cli:main", "cli_anything.tapp.tapp_cli:missing_fn"),
        encoding="utf-8",
    )
    r_missing_fn = verify_harness.verify_harness(
        h_missing_mod, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_missing_fn["ok"] is False
    assert {c["id"]: c for c in r_missing_fn["checks"]}["console-script"]["status"] == "fail"

    # 3. setup.py omitting `:callable` or targeting another harness package fails.
    for bad_target in (
        "cli_anything.tapp.tapp_cli",
        "cli_anything.otherapp.otherapp_cli:main",
    ):
        (h_missing_mod / "setup.py").write_text(
            f"""from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-tapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={{"cli_anything.tapp": ["skills/*.md"]}},
    entry_points={{"console_scripts": ["cli-anything-tapp={bad_target}"]}},
)
""",
            encoding="utf-8",
        )
        r_bad = verify_harness.verify_harness(
            h_missing_mod, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_bad["ok"] is False
        assert {c["id"]: c for c in r_bad["checks"]}["console-script"]["status"] == "fail"

    # 4. pyproject.toml [project.scripts] invalid target fails on both tomllib and Python 3.10 fallback.
    h_pyproj = _create_valid_harness(tmp_path / "pyproj_bad_target", "papp")
    (h_pyproj / "setup.py").unlink()
    (h_pyproj / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-papp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-papp = "cli_anything.papp.missing_cli:main"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.papp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    r_pyproj = verify_harness.verify_harness(
        h_pyproj, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_pyproj["ok"] is False
    assert {c["id"]: c for c in r_pyproj["checks"]}["console-script"]["status"] == "fail"

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        r_pyproj_310 = verify_harness.verify_harness(
            h_pyproj, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_pyproj_310["ok"] is False
        assert {c["id"]: c for c in r_pyproj_310["checks"]}["console-script"]["status"] == "fail"

    # 5. Dotted Click command attribute (`cli.main`) and Poetry inline table callable both pass.
    (h_pyproj / "pyproject.toml").write_text(
        (h_pyproj / "pyproject.toml")
        .read_text(encoding="utf-8")
        .replace("cli_anything.papp.missing_cli:main", "cli_anything.papp.papp_cli:cli.main"),
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(
        h_pyproj, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    # 6. Target in a nested subpackage excluded from packaging discovery fails.
    sub_dir = h_missing_mod / "cli_anything" / "tapp" / "sub"
    sub_dir.mkdir()
    (sub_dir / "__init__.py").write_text("", encoding="utf-8")
    (sub_dir / "entry.py").write_text("def run():\n    pass\n", encoding="utf-8")
    (h_missing_mod / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-tapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["cli_anything.*.sub"]),
    package_data={"cli_anything.tapp": ["skills/*.md"]},
    entry_points={"console_scripts": ["cli-anything-tapp=cli_anything.tapp.sub.entry:run"]},
)
""",
        encoding="utf-8",
    )
    r_sub_excl = verify_harness.verify_harness(
        h_missing_mod, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_sub_excl["ok"] is False
    assert {c["id"]: c for c in r_sub_excl["checks"]}["console-script"]["status"] == "fail"


def test_verify_manifest_preserves_setuptools_character_class_escaping(tmp_path: Path) -> None:
    harness = _create_valid_harness(tmp_path, "charapp")
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-charapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    entry_points={"console_scripts": ["cli-anything-charapp=cli_anything.charapp.charapp_cli:main"]},
)
""",
        encoding="utf-8",
    )

    # Setuptools translate_pattern escapes '-' inside [...], so [A-Z] does NOT match 'S' in SKILL.md.
    (harness / "MANIFEST.in").write_text("global-include [A-Z]*.md\n", encoding="utf-8")
    r_range = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_range["ok"] is False
    assert {c["id"]: c for c in r_range["checks"]}["package-data-skills"]["status"] == "warn"

    # Literal character class `[S]` DOES match `SKILL.md`.
    (harness / "MANIFEST.in").write_text("global-include [S]KILL.md\n", encoding="utf-8")
    r_lit = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_lit["ok"] is True, r_lit["checks"]

    # Regex-backed exclusions (`global-exclude`, `exclude`, `recursive-exclude`, `prune`) also escape '-'.
    for excl_line in (
        "global-exclude [A-Z]*.md",
        "exclude cli_anything/charapp/skills/[A-Z]*.md",
        "recursive-exclude cli_anything [A-Z]*.md",
        "prune cli_anything/[a-z]*/skills",
    ):
        (harness / "MANIFEST.in").write_text(
            f"recursive-include cli_anything *.md\n{excl_line}\n",
            encoding="utf-8",
        )
        r_kept = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_kept["ok"] is True, (excl_line, r_kept["checks"])

    # By contrast, glob-backed `include` / `recursive-include` treat [A-Z] as a range.
    (harness / "MANIFEST.in").write_text(
        "recursive-include cli_anything [A-Z]*.md\n", encoding="utf-8"
    )
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True


def test_verify_resolves_script_targets_and_skills_from_effective_package_dir(
    tmp_path: Path, monkeypatch
) -> None:
    harness = _create_valid_harness(tmp_path / "src_layout", "srcapp")
    shutil.copytree(harness / "cli_anything", harness / "src" / "cli_anything")
    (harness / "empty").mkdir()
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-srcapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-srcapp = "cli_anything.srcapp.srcapp_cli:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.srcapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )

    # Valid when src/ contains the target module and SKILL.md.
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    # Removing src/.../srcapp_cli.py while leaving flat cli_anything/.../srcapp_cli.py MUST fail.
    src_cli = harness / "src" / "cli_anything" / "srcapp" / "srcapp_cli.py"
    saved_cli = src_cli.read_text(encoding="utf-8")
    src_cli.unlink()

    r_missing = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_missing["ok"] is False
    assert {c["id"]: c for c in r_missing["checks"]}["console-script"]["status"] == "fail"

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        r_missing_310 = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_missing_310["ok"] is False
        assert {c["id"]: c for c in r_missing_310["checks"]}["console-script"]["status"] == "fail"

    # Multi-root `where = ["empty", "src"]` also resolves from `src/` (not flat `cli_anything/`).
    (harness / "pyproject.toml").write_text(
        (harness / "pyproject.toml").read_text(encoding="utf-8").replace(
            'where = ["src"]', 'where = ["empty", "src"]'
        ),
        encoding="utf-8",
    )
    r_multi_missing = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_multi_missing["ok"] is False
    assert {c["id"]: c for c in r_multi_missing["checks"]}["console-script"]["status"] == "fail"

    # Restore src CLI; removing src SKILL.md while flat SKILL.md remains must warn on package-data-skills.
    src_cli.write_text(saved_cli, encoding="utf-8")
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    src_skill = harness / "src" / "cli_anything" / "srcapp" / "skills" / "SKILL.md"
    saved_skill = src_skill.read_text(encoding="utf-8")
    src_skill.unlink()
    r_missing_skill = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_missing_skill["ok"] is False
    assert {c["id"]: c for c in r_missing_skill["checks"]}["package-data-skills"]["status"] == "warn"
    src_skill.write_text(saved_skill, encoding="utf-8")

    # Hatch `packages = ["src/cli_anything"]` and Poetry `from = "src"` also resolve from `src/`.
    src_cli.unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cli-anything-srcapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-srcapp = "cli_anything.srcapp.srcapp_cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/cli_anything"]
""",
        encoding="utf-8",
    )
    r_hatch_missing = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_hatch_missing["ok"] is False
    assert {c["id"]: c for c in r_hatch_missing["checks"]}["console-script"]["status"] == "fail"

    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "cli-anything-srcapp"
version = "1.0.0"
packages = [{include = "cli_anything", from = "src"}]

[tool.poetry.dependencies]
python = ">=3.10"

[tool.poetry.scripts]
cli-anything-srcapp = "cli_anything.srcapp.srcapp_cli:main"
""",
        encoding="utf-8",
    )
    r_poetry_missing = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_poetry_missing["ok"] is False
    assert {c["id"]: c for c in r_poetry_missing["checks"]}["console-script"]["status"] == "fail"

    # setup.py with explicit package_dir={"": "src"} resolves from `src/` too.
    (harness / "pyproject.toml").unlink()
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-srcapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(where="src", include=["cli_anything.*"]),
    package_dir={"": "src"},
    package_data={"cli_anything.srcapp": ["skills/*.md"]},
    entry_points={"console_scripts": ["cli-anything-srcapp=cli_anything.srcapp.srcapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    r_setup_missing = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_setup_missing["ok"] is False
    assert {c["id"]: c for c in r_setup_missing["checks"]}["console-script"]["status"] == "fail"
    src_cli.write_text(saved_cli, encoding="utf-8")
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    # Multi-root PEP 420 precedence: where = ["src1", "src2"] with initialized CLI in src1 and
    # namespace-only directory (no __init__.py, only skills/SKILL.md) in src2 -> setuptools gives
    # later root src2 precedence, so the wheel lacks the CLI module and strict verification MUST fail.
    ns_harness = _create_valid_harness(tmp_path / "multi_ns", "nsapp")
    shutil.copytree(ns_harness / "cli_anything", ns_harness / "src1" / "cli_anything")
    src2_skills = ns_harness / "src2" / "cli_anything" / "nsapp" / "skills"
    src2_skills.mkdir(parents=True)
    shutil.copy2(
        ns_harness / "cli_anything" / "nsapp" / "skills" / "SKILL.md",
        src2_skills / "SKILL.md",
    )
    (ns_harness / "setup.py").unlink()
    (ns_harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-nsapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-nsapp = "cli_anything.nsapp.nsapp_cli:main"

[tool.setuptools.packages.find]
where = ["src1", "src2"]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.nsapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    r_ns_override = verify_harness.verify_harness(
        ns_harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_ns_override["ok"] is False
    assert {c["id"]: c for c in r_ns_override["checks"]}["console-script"]["status"] == "fail"

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        r_ns_override_310 = verify_harness.verify_harness(
            ns_harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_ns_override_310["ok"] is False
        assert {c["id"]: c for c in r_ns_override_310["checks"]}["console-script"]["status"] == "fail"

    # Once src2 also provides the full package implementation, strict verification passes.
    shutil.copytree(
        ns_harness / "src1" / "cli_anything" / "nsapp",
        ns_harness / "src2" / "cli_anything" / "nsapp",
        dirs_exist_ok=True,
    )
    assert verify_harness.verify_harness(
        ns_harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True


def test_verify_manifest_preserves_dot_prefix_for_ordered_exclusions_and_build_py(
    tmp_path: Path,
) -> None:
    harness = _create_valid_harness(tmp_path / "dot_manifest", "dotapp")

    # 1. Without package_dir={"": "."}, `recursive-include . *.md` emits `./cli_anything/...` which
    #    setuptools build_py does not match against prefix-free package dirs (and `recursive-exclude . SKILL.md`
    #    removes it as well).
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-dotapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    entry_points={"console_scripts": ["cli-anything-dotapp=cli_anything.dotapp.dotapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    for manifest_text in (
        "recursive-include . *.md\n",
        "recursive-include . *.md\nrecursive-exclude . SKILL.md\n",
    ):
        (harness / "MANIFEST.in").write_text(manifest_text, encoding="utf-8")
        res = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert res["ok"] is False, manifest_text
        assert {c["id"]: c for c in res["checks"]}["package-data-skills"]["status"] == "warn"

    # 2. With package_dir={"": "."}, build_py expects `./cli_anything/...`: `recursive-include . *.md`
    #    succeeds, while `recursive-exclude . SKILL.md` or `prune .` removes the emitted `./` path.
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-dotapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_dir={"": "."},
    include_package_data=True,
    entry_points={"console_scripts": ["cli-anything-dotapp=cli_anything.dotapp.dotapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    (harness / "MANIFEST.in").write_text("recursive-include . *.md\n", encoding="utf-8")
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    for excl_manifest in (
        "recursive-include . *.md\nrecursive-exclude . SKILL.md\n",
        "recursive-include . *.md\nprune .\n",
    ):
        (harness / "MANIFEST.in").write_text(excl_manifest, encoding="utf-8")
        res = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert res["ok"] is False, excl_manifest
        assert {c["id"]: c for c in res["checks"]}["package-data-skills"]["status"] == "warn"

    # 3. `graft .` calls findall(".") which strips `./`, so `prune cli_anything/dotapp/skills`
    #    removes it while `prune .` does not.
    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-dotapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    entry_points={"console_scripts": ["cli-anything-dotapp=cli_anything.dotapp.dotapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    (harness / "MANIFEST.in").write_text("graft .\nprune .\n", encoding="utf-8")
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    (harness / "MANIFEST.in").write_text(
        "graft .\nprune cli_anything/dotapp/skills\n", encoding="utf-8"
    )
    res_graft_pruned = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert res_graft_pruned["ok"] is False
    assert {c["id"]: c for c in res_graft_pruned["checks"]}["package-data-skills"]["status"] == "warn"

    # 4. With `where = ["src"]`, MANIFEST.in must cover `src/cli_anything/...` (not flat `cli_anything/...`).
    shutil.copytree(harness / "cli_anything", harness / "src" / "cli_anything")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-dotapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-dotapp = "cli_anything.dotapp.dotapp_cli:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["cli_anything.*"]
""",
        encoding="utf-8",
    )
    (harness / "MANIFEST.in").write_text("recursive-include cli_anything *.md\n", encoding="utf-8")
    r_wrong_root = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_wrong_root["ok"] is False
    assert {c["id"]: c for c in r_wrong_root["checks"]}["package-data-skills"]["status"] == "warn"

    (harness / "MANIFEST.in").write_text("recursive-include src *.md\n", encoding="utf-8")
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True


def test_verify_checks_cli_surface_docs_and_tests_against_effective_package_dir(
    tmp_path: Path,
) -> None:
    harness = _create_valid_harness(tmp_path / "surface_src", "surfapp")
    shutil.copytree(harness / "cli_anything", harness / "src" / "cli_anything")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-surfapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-surfapp = "cli_anything.surfapp.surfapp_cli:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["cli_anything.*"]

[tool.setuptools.package-data]
"cli_anything.surfapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    # Removing --json ONLY from src/.../surfapp_cli.py (leaving flat cli_anything/... untouched) MUST fail.
    src_cli = harness / "src" / "cli_anything" / "surfapp" / "surfapp_cli.py"
    orig_cli = src_cli.read_text(encoding="utf-8")
    src_cli.write_text(
        orig_cli.replace('@click.option("--json", "use_json", is_flag=True)\n', "").replace(
            "use_json, ", ""
        ),
        encoding="utf-8",
    )
    r_no_json = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_no_json["ok"] is False
    assert {c["id"]: c for c in r_no_json["checks"]}["json-flag"]["status"] == "fail"
    src_cli.write_text(orig_cli, encoding="utf-8")

    # Removing README.md ONLY from src/.../surfapp/ MUST fail readme-md.
    src_readme = harness / "src" / "cli_anything" / "surfapp" / "README.md"
    orig_readme = src_readme.read_text(encoding="utf-8")
    src_readme.unlink()
    r_no_readme = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_no_readme["ok"] is False
    assert {c["id"]: c for c in r_no_readme["checks"]}["readme-md"]["status"] == "fail"
    src_readme.write_text(orig_readme, encoding="utf-8")

    # Adding a forbidden PEP 420 __init__.py inside src/cli_anything/ MUST fail.
    bad_ns_init = harness / "src" / "cli_anything" / "__init__.py"
    bad_ns_init.write_text("# forbidden\n", encoding="utf-8")
    r_bad_ns = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_bad_ns["ok"] is False
    assert {c["id"]: c for c in r_bad_ns["checks"]}["effective-namespace-package"]["status"] == "fail"
    bad_ns_init.unlink()

    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True


def test_verify_applies_pep621_precedence_to_python_requires(
    tmp_path: Path, monkeypatch
) -> None:
    harness = _create_valid_harness(tmp_path / "pep621_pyreq", "pyreqapp")
    # Valid setup.py with python_requires=">=3.10", plus [project] omitting requires-python
    # without listing "requires-python" in project.dynamic -> setuptools ignores setup.py python_requires.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-pyreqapp"
version = "1.0.0"

[project.scripts]
cli-anything-pyreqapp = "cli_anything.pyreqapp.pyreqapp_cli:main"
""",
        encoding="utf-8",
    )
    r_dropped = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    checks_dropped = {c["id"]: c for c in r_dropped["checks"]}
    assert r_dropped["ok"] is False
    assert checks_dropped["python-requires"]["status"] == "warn"
    assert "project.dynamic" in checks_dropped["python-requires"]["detail"]

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        r_dropped_310 = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_dropped_310["ok"] is False
        assert {c["id"]: c for c in r_dropped_310["checks"]}["python-requires"]["status"] == "warn"

    # Declaring "requires-python" in project.dynamic allows setup.py python_requires to apply.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-pyreqapp"
version = "1.0.0"
dynamic = ["requires-python"]

[project.scripts]
cli-anything-pyreqapp = "cli_anything.pyreqapp.pyreqapp_cli:main"
""",
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    # Declaring requires-python directly in [project] also passes.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-pyreqapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-pyreqapp = "cli_anything.pyreqapp.pyreqapp_cli:main"
""",
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True


def test_verify_requires_discovery_to_select_runtime_subpackages(
    tmp_path: Path, monkeypatch
) -> None:
    # 1. Narrowed pyproject.toml include = ["cli_anything.rtapp"] omits core/utils -> must fail.
    harness = _create_valid_harness(tmp_path / "narrow_inc", "rtapp")
    (harness / "setup.py").unlink()
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-rtapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-rtapp = "cli_anything.rtapp.rtapp_cli:main"

[tool.setuptools.packages.find]
include = ["cli_anything.rtapp"]

[tool.setuptools.package-data]
"cli_anything.rtapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    r_narrow = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_narrow["ok"] is False
    ns_check = {c["id"]: c for c in r_narrow["checks"]}["namespace-packages"]
    assert ns_check["status"] == "fail"
    assert "cli_anything.rtapp.core" in ns_check["detail"]
    assert "cli_anything.rtapp.utils" in ns_check["detail"]

    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "tomllib", None)
        r_narrow_310 = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_narrow_310["ok"] is False
        assert {c["id"]: c for c in r_narrow_310["checks"]}["namespace-packages"]["status"] == "fail"

    # 2. Explicit packages = ["cli_anything.rtapp"] without core/utils -> must fail.
    (harness / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cli-anything-rtapp"
version = "1.0.0"
requires-python = ">=3.10"

[project.scripts]
cli-anything-rtapp = "cli_anything.rtapp.rtapp_cli:main"

[tool.setuptools]
packages = ["cli_anything.rtapp"]

[tool.setuptools.package-data]
"cli_anything.rtapp" = ["skills/*.md"]
""",
        encoding="utf-8",
    )
    r_explicit_missing = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_explicit_missing["ok"] is False
    assert {c["id"]: c for c in r_explicit_missing["checks"]}["namespace-packages"]["status"] == "fail"

    # 3. setup.py excluding core or utils -> must fail; excluding only tests -> passes.
    (harness / "pyproject.toml").unlink()
    for excl_pat in ("cli_anything.*.core*", "cli_anything.*.utils*"):
        (harness / "setup.py").write_text(
            f"""from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-rtapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["{excl_pat}"]),
    package_data={{"cli_anything.rtapp": ["skills/*.md"]}},
    entry_points={{"console_scripts": ["cli-anything-rtapp=cli_anything.rtapp.rtapp_cli:main"]}},
)
""",
            encoding="utf-8",
        )
        r_excl = verify_harness.verify_harness(
            harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
        )
        assert r_excl["ok"] is False, excl_pat
        assert {c["id"]: c for c in r_excl["checks"]}["namespace-packages"]["status"] == "fail"

    (harness / "setup.py").write_text(
        """from setuptools import find_namespace_packages, setup
setup(
    name="cli-anything-rtapp",
    version="1.0.0",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"], exclude=["cli_anything.*.tests*"]),
    package_data={"cli_anything.rtapp": ["skills/*.md"]},
    entry_points={"console_scripts": ["cli-anything-rtapp=cli_anything.rtapp.rtapp_cli:main"]},
)
""",
        encoding="utf-8",
    )
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True


def test_verify_inspects_declared_cli_target_instead_of_aggregating_unrelated_cli_files(
    tmp_path: Path,
) -> None:
    harness = _create_valid_harness(tmp_path / "legacy_cli_case", "declapp")
    pkg = harness / "cli_anything" / "declapp"
    active_cli = pkg / "declapp_cli.py"
    orig_cli = active_cli.read_text(encoding="utf-8")

    # Save valid CLI as an unused legacy_cli.py and remove --json ONLY from the declared active CLI.
    (pkg / "legacy_cli.py").write_text(orig_cli, encoding="utf-8")
    active_cli.write_text(
        orig_cli.replace('@click.option("--json", "use_json", is_flag=True)\n', "").replace(
            "use_json, ", ""
        ),
        encoding="utf-8",
    )
    r_masked = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_masked["ok"] is False
    assert {c["id"]: c for c in r_masked["checks"]}["json-flag"]["status"] == "fail"

    # Restoring --json on the declared active CLI passes even if unused legacy_cli.py lacks --json.
    active_cli.write_text(orig_cli, encoding="utf-8")
    (pkg / "legacy_cli.py").write_text("def old_helper():\n    return None\n", encoding="utf-8")
    assert verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )["ok"] is True

    # Pointing console_scripts to a separate module without --json also fails even when declapp_cli.py has it.
    (pkg / "entry_mod.py").write_text(
        "import click\n\n@click.group(invoke_without_command=True)\ndef main():\n    pass\n",
        encoding="utf-8",
    )
    (harness / "setup.py").write_text(
        (harness / "setup.py").read_text(encoding="utf-8").replace(
            "cli_anything.declapp.declapp_cli:main",
            "cli_anything.declapp.entry_mod:main",
        ),
        encoding="utf-8",
    )
    r_custom = verify_harness.verify_harness(
        harness, strict=True, canonical_repl_skin=CANONICAL_REPL_SKIN
    )
    assert r_custom["ok"] is False
    assert {c["id"]: c for c in r_custom["checks"]}["json-flag"]["status"] == "fail"
