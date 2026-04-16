import subprocess
import sys
import unittest
from pathlib import Path


SOFTWARE_ROOT = Path(__file__).resolve().parents[4]
HARNESS_ROOT = SOFTWARE_ROOT / "agent-harness"
STANDALONE_ROOT = SOFTWARE_ROOT if (SOFTWARE_ROOT / "setup.py").is_file() else None


def _find_contribution_root() -> Path:
    candidates = [SOFTWARE_ROOT, *SOFTWARE_ROOT.parents]
    for candidate in candidates:
        if (candidate / "CONTRIBUTING.md").is_file() and (candidate / "registry.json").is_file():
            return candidate
    raise AssertionError("unable to locate contribution root containing CONTRIBUTING.md and registry.json")


CONTRIBUTION_ROOT = _find_contribution_root()


class AgentHarnessPackagingTests(unittest.TestCase):
    def test_agent_harness_packaging_files_exist(self):
        self.assertTrue((HARNESS_ROOT / "setup.py").is_file())
        self.assertTrue((HARNESS_ROOT / "pyproject.toml").is_file())

    def test_agent_harness_contains_canonical_package_tree(self):
        expected_paths = [
            HARNESS_ROOT / "cli_anything" / "mubu" / "__init__.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "__main__.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "mubu_cli.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "utils" / "__init__.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "utils" / "repl_skin.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "skills" / "SKILL.md",
            HARNESS_ROOT / "cli_anything" / "mubu" / "tests" / "TEST.md",
        ]
        for path in expected_paths:
            self.assertTrue(path.is_file(), msg=f"missing canonical harness file: {path}")

    def test_agent_harness_contains_canonical_test_modules(self):
        expected_paths = [
            HARNESS_ROOT / "cli_anything" / "mubu" / "tests" / "test_mubu_probe.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "tests" / "test_cli_entrypoint.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "tests" / "test_agent_harness.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "tests" / "test_core.py",
            HARNESS_ROOT / "cli_anything" / "mubu" / "tests" / "test_full_e2e.py",
        ]
        for path in expected_paths:
            self.assertTrue(path.is_file(), msg=f"missing canonical harness test: {path}")

    def test_contribution_files_exist(self):
        self.assertTrue((CONTRIBUTION_ROOT / "CONTRIBUTING.md").is_file())
        self.assertTrue((CONTRIBUTION_ROOT / "registry.json").is_file())

    def test_agent_harness_setup_reports_expected_name(self):
        result = subprocess.run(
            [sys.executable, str(HARNESS_ROOT / "setup.py"), "--name"],
            cwd=HARNESS_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "cli-anything-mubu")

    def test_agent_harness_setup_reports_expected_version(self):
        result = subprocess.run(
            [sys.executable, str(HARNESS_ROOT / "setup.py"), "--version"],
            cwd=HARNESS_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "0.1.1")

    def test_root_setup_targets_canonical_harness_source(self):
        if STANDALONE_ROOT is None:
            self.assertFalse((SOFTWARE_ROOT / "setup.py").exists())
            self.assertTrue((SOFTWARE_ROOT / "agent-harness" / "setup.py").is_file())
            return
        setup_text = (STANDALONE_ROOT / "setup.py").read_text()
        self.assertIn('find_namespace_packages(where="agent-harness"', setup_text)
        self.assertIn('package_dir={"": "agent-harness"}', setup_text)

    def test_setup_files_declare_click_runtime_dependency(self):
        harness_setup = (HARNESS_ROOT / "setup.py").read_text()
        if STANDALONE_ROOT is not None:
            root_setup = (STANDALONE_ROOT / "setup.py").read_text()
            self.assertIn('"click>=8.0"', root_setup)
        self.assertIn('"click>=8.0"', harness_setup)

    def test_skill_generator_assets_exist(self):
        self.assertTrue((HARNESS_ROOT / "skill_generator.py").is_file())
        self.assertTrue((HARNESS_ROOT / "templates" / "SKILL.md.template").is_file())

    def test_repl_skin_matches_cli_anything_copy_shape(self):
        repl_skin = (HARNESS_ROOT / "cli_anything" / "mubu" / "utils" / "repl_skin.py").read_text()
        self.assertIn('"""cli-anything REPL Skin — Unified terminal interface for all CLI harnesses.', repl_skin)
        self.assertIn("Copy this file into your CLI package at:", repl_skin)
        self.assertIn("skin.print_goodbye()", repl_skin)

    def test_skill_generator_can_regenerate_skill_from_canonical_harness(self):
        output_path = HARNESS_ROOT / "tmp-generated-SKILL.md"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(HARNESS_ROOT / "skill_generator.py"),
                    str(HARNESS_ROOT),
                    "--output",
                    str(output_path),
                ],
                cwd=HARNESS_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = output_path.read_text()
            self.assertIn('name: >-\n  cli-anything-mubu', content)
            self.assertIn("## Command Groups", content)
            self.assertIn("### Discover", content)
            self.assertNotIn("### Cli", content)
            self.assertIn("| `docs` |", content)
            self.assertIn("`daily-current`", content)
            self.assertIn("`update-text`", content)
            self.assertIn("### Session", content)
            self.assertIn("| `status` |", content)
            self.assertIn("| `state-path` |", content)
            self.assertIn("MUBU_DAILY_FOLDER", content)
            self.assertNotIn("Workspace/Daily tasks", content)
            self.assertNotIn("Daily tasks resolution", content)
            self.assertIn("## Version\n\n0.1.1", content)
        finally:
            output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
