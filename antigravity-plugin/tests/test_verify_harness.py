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


def test_pyproject_py310_fallback_matches_tomllib_semantics() -> None:
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
include = ["cli_anything.*"]
exclude = ["cli_anything.*"]
""",
        """[tool.setuptools.packages.find]
include = ["cli_anything.*"]
exclude = ["cli_anything.*.tests*"]
""",
        """[tool.setuptools.packages]
find = { include = ["cli_anything.*"], exclude = ["cli_anything.*"] }
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
    {include = "cli_anything"},
]

[tool.poetry.scripts]
cli-anything-demoapp = "cli_anything.demoapp.demoapp_cli:main"
""",
    ]
    for sample in samples:
        assert verify_harness._inspect_pyproject_toml_fallback(
            sample, target_pkg=target
        ) == verify_harness._inspect_pyproject_toml(sample, target_pkg=target), sample
