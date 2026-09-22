from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
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
        with tempfile.TemporaryDirectory() as tmp_dir:
            copied_harness = Path(tmp_dir) / "agent-harness"
            shutil.copytree(HARNESS_ROOT, copied_harness)
            output_path = Path(tmp_dir) / "generated-SKILL.md"
            compatibility_path = copied_harness / "cli_anything" / "zotero" / "skills" / "SKILL.md"
            existing_content = "# Existing packaged skill\n"
            compatibility_path.write_text(existing_content, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(copied_harness / "skill_generator.py"), str(copied_harness), "--output", str(output_path)],
                cwd=copied_harness,
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
            self.assertEqual(compatibility_path.read_text(encoding="utf-8"), existing_content)
