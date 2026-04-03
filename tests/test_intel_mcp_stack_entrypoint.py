import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class IntelMcpStackEntrypointTests(unittest.TestCase):
    def test_stack_script_runs_core_unittests_and_strict_doctor(self):
        script_path = REPO_ROOT / "scripts" / "test_intel_mcp_stack.sh"
        script = script_path.read_text(encoding="utf-8")

        self.assertIn('SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"', script)
        self.assertIn('cd "$REPO_ROOT"', script)
        self.assertIn("tests.test_intel_skill_runtime", script)
        self.assertIn("tests.test_intel_mcp_server", script)
        self.assertIn("tests.test_intel_mcp_doctor", script)
        self.assertIn("tests.test_intel_plugin_manifest", script)
        self.assertIn("intel_mcp_doctor.py", script)
        self.assertIn("--strict", script)
