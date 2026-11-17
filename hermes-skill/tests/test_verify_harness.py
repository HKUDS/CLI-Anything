"""Tests for hermes-skill/scripts/verify_harness.py.

The fixtures are synthetic: a minimal checkout with one conforming harness, then
one deliberate defect per test. Nothing here needs a real backend, network
access, or a third-party dependency.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_harness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_harness", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_checkout(root: Path) -> Path:
    """Create a checkout with one conforming harness and return the harness dir."""
    write(root / "registry.json", "{}")
    write(root / "cli-anything-plugin" / "repl_skin.py", "CANONICAL = True\n")

    harness = root / "mysw" / "agent-harness"
    write(harness / "MYSW.md", "# MYSW architecture\n")
    write(
        harness / "setup.py",
        "from setuptools import find_namespace_packages, setup\n"
        "setup(name='cli-anything-mysw',\n"
        "      packages=find_namespace_packages(include=['cli_anything.*']),\n"
        "      entry_points={'console_scripts': ['cli-anything-mysw=cli_anything.mysw.mysw_cli:cli']})\n",
    )
    package = harness / "cli_anything" / "mysw"
    write(package / "__main__.py", "from .mysw_cli import cli\n")
    write(
        package / "mysw_cli.py",
        "import click\n"
        "@click.group(invoke_without_command=True)\n"
        "@click.option('--json', 'as_json', is_flag=True)\n"
        "@click.option('--dry-run', is_flag=True)\n"
        "def cli(as_json, dry_run):\n"
        "    pass\n",
    )
    write(package / "utils" / "repl_skin.py", "CANONICAL = True\n")
    write(package / "skills" / "SKILL.md", "---\nname: cli-anything-mysw\ndescription: Do mysw things.\n---\n")
    write(package / "tests" / "test_core.py", "def test_ok():\n    assert True\n")
    write(package / "tests" / "test_full_e2e.py", "def test_e2e():\n    assert True\n")
    write(harness / "TEST.md", "# Test plan\n\n## Results\n\n12 passed\n")

    write(
        root / "skills" / "cli-anything-mysw" / "SKILL.md",
        "---\nname: cli-anything-mysw\ndescription: Do mysw things with a stateful CLI.\n---\n\n# mysw\n",
    )
    return harness


class VerifyHarnessTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.harness = build_checkout(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def result(self):
        return self.module.verify(self.harness)

    def failing(self):
        return {c["id"] for c in self.result()["checks"] if c["status"] == "fail"}

    def test_conforming_harness_passes(self):
        result = self.result()
        self.assertTrue(result["ok"], [c for c in result["checks"] if c["status"] == "fail"])
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertEqual(result["name"], "mysw")

    def test_accepts_software_dir_or_harness_dir(self):
        software = self.harness.parent
        self.assertTrue(self.module.verify(software)["ok"])
        self.assertTrue(self.module.verify(self.harness)["ok"])

    def test_missing_json_flag_is_an_error(self):
        cli = self.harness / "cli_anything" / "mysw" / "mysw_cli.py"
        cli.write_text(cli.read_text().replace("'--json'", "'--as-json'"), encoding="utf-8")
        self.assertIn("json-output", self.failing())

    def test_missing_unit_tests_is_an_error(self):
        (self.harness / "cli_anything" / "mysw" / "tests" / "test_core.py").unlink()
        self.assertIn("tests-core", self.failing())

    def test_missing_root_skill_mirror_is_an_error(self):
        (self.root / "skills" / "cli-anything-mysw" / "SKILL.md").unlink()
        self.assertIn("root-skill", self.failing())

    def test_missing_console_script_is_an_error(self):
        setup_py = self.harness / "setup.py"
        setup_py.write_text(
            setup_py.read_text().replace("cli-anything-mysw=cli_anything.mysw.mysw_cli:cli", "other"),
            encoding="utf-8",
        )
        self.assertIn("console-script", self.failing())

    def test_repl_skin_drift_is_a_warning_not_an_error(self):
        skin = self.harness / "cli_anything" / "mysw" / "utils" / "repl_skin.py"
        skin.write_text("EDITED = True\n", encoding="utf-8")
        result = self.result()
        self.assertTrue(result["ok"])
        self.assertIn("repl-skin", {c["id"] for c in result["checks"] if c["status"] == "warn"})

    def test_strict_escalates_warnings(self):
        skin = self.harness / "cli_anything" / "mysw" / "utils" / "repl_skin.py"
        skin.write_text("EDITED = True\n", encoding="utf-8")
        self.assertFalse(self.module.verify(self.harness, strict=True)["ok"])

    def test_truncated_description_warns(self):
        skill = self.root / "skills" / "cli-anything-mysw" / "SKILL.md"
        skill.write_text(
            "---\nname: cli-anything-mysw\ndescription: >-\n  Command-line interface for My Software - a stateful\n  command-line interface for doing things pow...\n---\n\n# mysw\n",
            encoding="utf-8",
        )
        result = self.result()
        self.assertTrue(result["ok"])
        warnings = {c["id"] for c in result["checks"] if c["status"] == "warn"}
        self.assertIn("skill-frontmatter", warnings)

    def test_directory_without_package_tree_fails(self):
        empty = self.root / "empty"
        empty.mkdir()
        result = self.module.verify(empty)
        self.assertFalse(result["ok"])
        self.assertIn("namespace-package", {c["id"] for c in result["checks"] if c["status"] == "fail"})


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.harness = build_checkout(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + list(args),
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )

    def test_exit_zero_on_conforming_harness(self):
        completed = self.run_cli("mysw")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_exit_one_on_broken_harness(self):
        (self.harness / "cli_anything" / "mysw" / "tests" / "test_full_e2e.py").unlink()
        completed = self.run_cli("mysw")
        self.assertEqual(completed.returncode, 1)

    def test_json_payload_shape(self):
        completed = self.run_cli("mysw", "--json")
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["harnesses"], 1)
        self.assertIn("checks", payload["harnesses"][0])

    def test_all_discovers_harnesses(self):
        completed = self.run_cli("--all", "--json")
        payload = json.loads(completed.stdout)
        self.assertEqual([h["name"] for h in payload["harnesses"]], ["mysw"])


if __name__ == "__main__":
    unittest.main()
