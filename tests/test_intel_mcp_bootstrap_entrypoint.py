import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class IntelMcpBootstrapEntrypointTests(unittest.TestCase):
    def test_bootstrap_script_runs_install_hook_and_stack_gate(self):
        script_path = REPO_ROOT / "scripts" / "bootstrap_intel_mcp_plugin.sh"
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("install_intel_mcp_clients.py", script)
        self.assertIn("install_intel_mcp_pre_push_hook.sh", script)
        self.assertIn("test_intel_mcp_stack.sh", script)
