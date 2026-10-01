"""Check the real global installation with isolated home and source trees."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "checkout"
        for directory in [".pi-extension", "cli-anything-plugin", "docs"]:
            shutil.copytree(
                REPOSITORY / directory,
                self.source / directory,
                ignore=shutil.ignore_patterns("node_modules", "__pycache__"),
            )
        shutil.copy2(REPOSITORY / "CONTRIBUTING.md", self.source)
        self.installer = self.source / ".pi-extension/cli-anything/install.sh"
        self.home = self.root / "home"
        self.target = self.home / ".pi/agent/extensions/cli-anything"
        self.environment = dict(os.environ, HOME=str(self.home))

    def install(self, environment=None):
        return subprocess.run(
            ["bash", str(self.installer)],
            env=environment or self.environment,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_install_includes_executable_preview_helper_and_protocol(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        protocol = self.target / "docs/PREVIEW_PROTOCOL.md"
        self.assertTrue(
            protocol.is_file(),
            "Installed methodology references missing protocol",
        )
        helper = self.target / "scripts/preview_bundle.py"
        self.assertTrue(
            helper.is_file(), "Installed preview workflow has no helper"
        )
        spec = importlib.util.spec_from_file_location(
            "installed_preview", helper
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.PROTOCOL_VERSION, "preview-bundle/v1")
        self.assertEqual(len(module.hash_data({"installed": True})), 64)

    def test_all_five_installed_commands_resolve_preview_resources(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(
            [
                os.environ.get("NODE", "node"),
                str(Path(__file__).with_name("test_installed_extension.mjs")),
                str(self.target),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_required_assets_does_not_publish_broken_extension(self):
        for resource in [
            "cli-anything-plugin/HARNESS.md",
            "docs/PREVIEW_PROTOCOL.md",
            "cli-anything-plugin/commands/refine.md",
        ]:
            with self.subTest(resource=resource):
                path = self.source / resource
                content = path.read_bytes()
                path.unlink()
                try:
                    result = self.install()
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertFalse(self.target.exists())
                finally:
                    path.write_bytes(content)

    def test_copy_failure_keeps_previous_extension_unchanged(self):
        self.target.mkdir(parents=True)
        previous = self.target / "index.ts"
        previous.write_text("previous working extension", encoding="utf-8")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "cp"
        wrapper.write_text(
            "#!/bin/bash\n"
            'if [[ "$1" == */HARNESS.md ]]; then exit 17; fi\n'
            'exec "$REAL_CP" "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        environment = dict(
            self.environment,
            PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
            REAL_CP=shutil.which("cp"),
        )
        result = self.install(environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(previous.read_text(), "previous working extension")
        self.assertEqual(
            list(self.target.parent.glob(".cli-anything.tmp.*")), []
        )

    def test_publication_failure_restores_previous_extension(self):
        self.target.mkdir(parents=True)
        previous = self.target / "index.ts"
        previous.write_text("previous working extension", encoding="utf-8")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "mv"
        wrapper.write_text(
            "#!/bin/bash\n"
            'if [[ "$1" == */.cli-anything.tmp.* ]]; then exit 17; fi\n'
            'exec "$REAL_MV" "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        result = self.install(
            dict(
                self.environment,
                PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                REAL_MV=shutil.which("mv"),
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(previous.read_text(), "previous working extension")
        self.assertEqual(
            list(self.target.parent.glob(".cli-anything.tmp.*")), []
        )
        self.assertEqual(
            list(self.target.parent.glob(".cli-anything.backup.*")), []
        )

    def test_upgrade_and_uninstall_complete(self):
        self.target.mkdir(parents=True)
        (self.target / "old-version.txt").write_text("old", encoding="utf-8")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.target / "old-version.txt").exists())
        result = subprocess.run(
            ["bash", str(self.installer), "--uninstall"],
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
