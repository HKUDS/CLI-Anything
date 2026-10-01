"""Exercise two real installer processes sharing an installation destination."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install.sh"


class ConcurrentInstallTests(unittest.TestCase):
    def test_concurrent_install_refuses_second_writer_without_nesting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            wrapper = bin_dir / "mv"
            wrapper.write_text(
                "#!/bin/bash\n"
                'touch "$INSTALL_BARRIER/ready"\n'
                'while [[ ! -f "$INSTALL_BARRIER/release" ]]; do sleep 0.02; done\n'
                'exec "$REAL_MV" "$@"\n',
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            environment = dict(os.environ, CODEX_HOME=str(root / "codex"))
            blocked_environment = dict(
                environment,
                PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                REAL_MV=shutil.which("mv"),
                INSTALL_BARRIER=str(root),
            )
            first = subprocess.Popen(
                ["bash", str(INSTALLER)],
                env=blocked_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 15
                while not (root / "ready").exists():
                    if first.poll() is not None or time.monotonic() > deadline:
                        self.fail("First installer did not reach publication")
                    time.sleep(0.02)
                second = subprocess.run(
                    ["bash", str(INSTALLER)],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            finally:
                (root / "release").touch()
                first_stdout, first_stderr = first.communicate(timeout=15)
            self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
            self.assertNotEqual(second.returncode, 0, second.stdout)
            installed = root / "codex" / "skills" / "cli-anything"
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertEqual(list(installed.glob(".cli-anything.tmp.*")), [])
            self.assertEqual(
                list(installed.parent.glob(".cli-anything.tmp.*")), []
            )
            self.assertFalse(
                (installed.parent / ".cli-anything.install.lock").exists()
            )

    def test_failed_copy_releases_lock_and_keeps_destination_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            wrapper = bin_dir / "cp"
            wrapper.write_text("#!/bin/bash\nexit 17\n", encoding="utf-8")
            wrapper.chmod(0o755)
            environment = dict(os.environ, CODEX_HOME=str(root / "codex"))
            result = subprocess.run(
                ["bash", str(INSTALLER)],
                env=dict(
                    environment,
                    PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                ),
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(result.returncode, 0)
            skills = root / "codex" / "skills"
            self.assertFalse((skills / "cli-anything").exists())
            self.assertFalse((skills / ".cli-anything.install.lock").exists())
            result = subprocess.run(
                ["bash", str(INSTALLER)],
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )


if __name__ == "__main__":
    unittest.main()
