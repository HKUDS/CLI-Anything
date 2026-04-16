from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


HARNESS_ROOT = Path(__file__).resolve().parents[3]


class AgentHarnessPackagingTests(unittest.TestCase):
    def test_required_files_exist(self):
        required = [
            HARNESS_ROOT / "setup.py",
            HARNESS_ROOT / "pyproject.toml",
            HARNESS_ROOT / "ZOTERO.md",
            HARNESS_ROOT / "skill_generator.py",
            HARNESS_ROOT / "templates" / "SKILL.md.template",
            HARNESS_ROOT / "cli_anything" / "zotero" / "README.md",
            HARNESS_ROOT / "cli_anything" / "zotero" / "zotero_cli.py",
            HARNESS_ROOT / "cli_anything" / "zotero" / "utils" / "repl_skin.py",
            HARNESS_ROOT / "cli_anything" / "zotero" / "skills" / "SKILL.md",
            HARNESS_ROOT / "cli_anything" / "zotero" / "tests" / "TEST.md",
        ]
        for path in required:
            self.assertTrue(path.is_file(), msg=f"missing required file: {path}")

    def test_setup_reports_expected_name(self):
        result = subprocess.run([sys.executable, str(HARNESS_ROOT / "setup.py"), "--name"], cwd=HARNESS_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "cli-anything-zotero")

    def test_setup_reports_expected_version(self):
        result = subprocess.run([sys.executable, str(HARNESS_ROOT / "setup.py"), "--version"], cwd=HARNESS_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "0.1.0")

    def test_skill_generator_regenerates_skill(self):
        output_path = HARNESS_ROOT / "tmp-SKILL.md"
        try:
            result = subprocess.run(
                [sys.executable, str(HARNESS_ROOT / "skill_generator.py"), str(HARNESS_ROOT), "--output", str(output_path)],
                cwd=HARNESS_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("cli-anything-zotero", content)
            self.assertIn("## Important Constraints", content)
            self.assertIn("require Zotero's Local API to be enabled", content)
            self.assertIn("## Command Groups", content)
            self.assertIn("### App", content)
            self.assertIn("### Item", content)
            self.assertIn("### Note", content)
            self.assertIn("| `add` |", content)
        finally:
            output_path.unlink(missing_ok=True)
