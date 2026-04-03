import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class IntelMcpHookInstallTests(unittest.TestCase):
    def test_hook_template_runs_stack_script(self):
        hook_path = REPO_ROOT / ".githooks" / "pre-push-intel-mcp"
        hook = hook_path.read_text(encoding="utf-8")

        self.assertIn("test_intel_mcp_stack.sh", hook)
        self.assertIn("exec sh", hook)

    def test_install_script_installs_pre_push_hook_into_target_dir(self):
        script_path = REPO_ROOT / "scripts" / "install_intel_mcp_pre_push_hook.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir) / "hooks"
            proc = subprocess.run(
                ["sh", str(script_path), "--hooks-dir", str(hooks_dir)],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("installed", proc.stdout)
            target = hooks_dir / "pre-push"
            self.assertTrue(target.exists())
            self.assertIn("test_intel_mcp_stack.sh", target.read_text(encoding="utf-8"))

    def test_install_script_refuses_to_replace_unknown_hook_without_force(self):
        script_path = REPO_ROOT / "scripts" / "install_intel_mcp_pre_push_hook.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir) / "hooks"
            hooks_dir.mkdir(parents=True)
            target = hooks_dir / "pre-push"
            target.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")

            proc = subprocess.run(
                ["sh", str(script_path), "--hooks-dir", str(hooks_dir)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("existing pre-push hook differs", proc.stderr)

    def test_install_script_check_mode_reports_install_state(self):
        script_path = REPO_ROOT / "scripts" / "install_intel_mcp_pre_push_hook.sh"
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir) / "hooks"
            hooks_dir.mkdir(parents=True)

            missing = subprocess.run(
                ["sh", str(script_path), "--hooks-dir", str(hooks_dir), "--check"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("not_installed", missing.stdout)

            (hooks_dir / "pre-push").write_text(
                "#!/bin/sh\nexec sh \"$PWD/scripts/test_intel_mcp_stack.sh\"\n",
                encoding="utf-8",
            )
            installed = subprocess.run(
                ["sh", str(script_path), "--hooks-dir", str(hooks_dir), "--check"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(installed.returncode, 0)
            self.assertIn("installed", installed.stdout)
