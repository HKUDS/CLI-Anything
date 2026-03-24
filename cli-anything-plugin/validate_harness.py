#!/usr/bin/env python3
"""
Automated CLI Harness Validator for CLI-Anything.
Validates a harness against the standards defined in HARNESS.md.
"""

import os
import sys
import re
import click
from pathlib import Path
from typing import List, Tuple


class Validator:
    def __init__(self, software_path: str):
        self.software_path = Path(software_path).resolve()
        self.software_name = self.software_path.name
        self.harness_path = self.software_path / "agent-harness"
        self.results = []
        self.errors = 0
        self.warnings = 0

    def log(self, category: str, message: str, status: str = "PASS"):
        if status == "FAIL":
            self.errors += 1
            icon = "❌"
        elif status == "WARN":
            self.warnings += 1
            icon = "⚠️"
        else:
            icon = "✅"
        self.results.append((category, icon, message, status))

    def check_directory_structure(self):
        cat = "Structure"
        if not self.harness_path.exists():
            self.log(cat, f"agent-harness directory not found in {self.software_path}", "FAIL")
            return

        cli_anything_dir = self.harness_path / "cli_anything"
        if not cli_anything_dir.exists():
            self.log(cat, "cli_anything/ directory not found", "FAIL")
        else:
            # PEP 420 Namespace check
            if (cli_anything_dir / "__init__.py").exists():
                self.log(cat, "cli_anything/ should NOT have __init__.py (namespace rule)", "FAIL")
            else:
                self.log(cat, "cli_anything/ has no __init__.py (PEP 420 compliant)")

        software_dir = cli_anything_dir / self.software_name
        if not software_dir.exists():
            # Try underscores instead of hyphens
            software_dir = cli_anything_dir / self.software_name.replace("-", "_")
            
        if not software_dir.exists():
            self.log(cat, f"Sub-package directory '{self.software_name}' not found in cli_anything/", "FAIL")
        else:
            if not (software_dir / "__init__.py").exists():
                self.log(cat, f"{software_dir.name}/ should have __init__.py", "FAIL")
            
            for sub in ["core", "utils", "tests"]:
                if not (software_dir / sub).exists():
                    self.log(cat, f"Missing {sub}/ directory in {software_dir.name}/", "FAIL")
                elif not (software_dir / sub / "__init__.py").exists():
                    self.log(cat, f"Missing __init__.py in {software_dir.name}/{sub}/", "WARN")

    def check_required_files(self):
        cat = "Files"
        base = self.harness_path / "cli_anything" / self.software_name
        if not base.exists():
            base = self.harness_path / "cli_anything" / self.software_name.replace("-", "_")

        required = [
            (self.harness_path / "README.md", "Installation guide"),
            (self.harness_path / "setup.py", "Package config"),
            (base / f"{base.name}_cli.py", "CLI entry point"),
            (base / "core" / "session.py", "Session/Undo logic"),
            (base / "tests" / "TEST.md", "Test plan/results"),
            (base / "tests" / "test_core.py", "Unit tests"),
            (base / "tests" / "test_full_e2e.py", "E2E tests"),
            (self.software_path / f"{self.software_name.upper()}.md", "Software SOP"),
        ]

        for path, desc in required:
            if not path.exists():
                # Some are optional but recommended
                if "SOP" in desc or "Session" in desc:
                    self.log(cat, f"Missing {desc} ({path.name})", "WARN")
                else:
                    self.log(cat, f"Missing {desc} ({path.name})", "FAIL")
            else:
                self.log(cat, f"Found {desc}")

    def check_setup_py(self):
        cat = "Packaging"
        setup_py = self.harness_path / "setup.py"
        if not setup_py.exists():
            return

        content = setup_py.read_text(encoding="utf-8")
        
        if "find_namespace_packages" not in content:
            self.log(cat, "setup.py should use find_namespace_packages", "FAIL")
        
        if f"cli-anything-{self.software_name}" not in content and f"cli-anything-{self.software_name.replace('_', '-')}" not in content:
            self.log(cat, f"Package name should follow cli-anything-{self.software_name} convention", "WARN")

        if "console_scripts" not in content:
            self.log(cat, "setup.py missing entry_points (console_scripts)", "FAIL")

    def check_cli_implementation(self):
        cat = "CLI"
        base = self.harness_path / "cli_anything" / self.software_name
        if not base.exists():
            base = self.harness_path / "cli_anything" / self.software_name.replace("-", "_")
        
        cli_file = base / f"{base.name}_cli.py"
        if not cli_file.exists():
            return

        content = cli_file.read_text(encoding="utf-8")
        
        checks = [
            (r"@click\.group", "Uses Click framework"),
            (r"--json", "Implements --json flag"),
            (r"--project", "Implements --project flag"),
            (r"handle_error", "Uses error handler decorator"),
            (r"invoke_without_command=True", "REPL support (invoke_without_command)"),
        ]

        for pattern, desc in checks:
            if not re.search(pattern, content):
                self.log(cat, f"CLI might be missing: {desc}", "WARN")
            else:
                self.log(cat, f"CLI {desc} verified")

    def run_all(self):
        self.check_directory_structure()
        self.check_required_files()
        self.check_setup_py()
        self.check_cli_implementation()

    def print_report(self):
        click.secho(f"\nValidation Report for {self.software_name}", bold=True, underline=True)
        
        current_cat = ""
        for cat, icon, msg, status in self.results:
            if cat != current_cat:
                click.echo(f"\n[{cat}]")
                current_cat = cat
            
            color = "green" if status == "PASS" else "red" if status == "FAIL" else "yellow"
            click.echo(f"  {icon} ", nl=False)
            click.secho(msg, fg=color)

        click.echo("-" * 40)
        summary = f"Result: {self.errors} Errors, {self.warnings} Warnings"
        if self.errors > 0:
            click.secho(summary, fg="red", bold=True)
        elif self.warnings > 0:
            click.secho(summary, fg="yellow", bold=True)
        else:
            click.secho(summary, fg="green", bold=True)


@click.command()
@click.argument("software_path", type=click.Path(exists=True))
def main(software_path):
    """Validate a CLI harness against CLI-Anything standards."""
    validator = Validator(software_path)
    validator.run_all()
    validator.print_report()
    
    if validator.errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
