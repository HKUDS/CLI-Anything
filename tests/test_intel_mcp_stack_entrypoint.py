import sys
import unittest
from pathlib import Path


REPO_ROOT = Path("/Users/lixun/Documents/codex ")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class IntelMcpStackEntrypointTests(unittest.TestCase):
    def test_stack_script_runs_core_unittests_and_strict_doctor(self):
        script_path = REPO_ROOT / "scripts" / "test_intel_mcp_stack.sh"
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("test_intel_skill_runtime.py", script)
        self.assertIn("test_intel_mcp_server.py", script)
        self.assertIn("test_intel_mcp_doctor.py", script)
        self.assertIn("test_intel_plugin_manifest.py", script)
        self.assertIn("intel_mcp_doctor.py", script)
        self.assertIn("--strict", script)
