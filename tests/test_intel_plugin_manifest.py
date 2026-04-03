import json
import unittest
from pathlib import Path


REPO_ROOT = Path("/Users/lixun/Documents/codex ")


class IntelPluginManifestTests(unittest.TestCase):
    def test_marketplace_lists_intel_tools_plugin(self):
        marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

        plugins = {entry["name"]: entry for entry in marketplace["plugins"]}
        self.assertIn("deep-scavenger-intel-tools", plugins)
        self.assertEqual(plugins["deep-scavenger-intel-tools"]["source"], "./deep-scavenger-intel-plugin")

    def test_plugin_manifest_exposes_stdio_mcp_entrypoint(self):
        plugin_manifest_path = REPO_ROOT / "deep-scavenger-intel-plugin" / ".claude-plugin" / "plugin.json"
        plugin_manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(plugin_manifest["name"], "deep-scavenger-intel-tools")
        self.assertEqual(plugin_manifest["metadata"]["mcp"]["transport"], "stdio")
        self.assertEqual(plugin_manifest["metadata"]["mcp"]["entrypoint"], "./bin/run-intel-mcp.sh")
        self.assertTrue(plugin_manifest["metadata"]["mcp"]["readOnly"])
        self.assertEqual(
            plugin_manifest["metadata"]["mcp"]["tools"],
            ["intel-health", "intel-ops-overview", "intel-briefing"],
        )
        self.assertEqual(
            plugin_manifest["metadata"]["mcp"]["prompts"],
            ["intel-duty-officer", "source-health-triage", "briefing-analyst"],
        )
        self.assertEqual(
            plugin_manifest["metadata"]["mcp"]["resources"],
            [
                "dsintel://registry/tools",
                "dsintel://contracts/intel-skill-tool-contracts",
                "dsintel://contracts/quickstart",
                "dsintel://docs/plugin-readme",
                "dsintel://skills/intel-duty-officer",
                "dsintel://skills/source-health-triage",
                "dsintel://skills/briefing-analyst",
            ],
        )

    def test_plugin_wrapper_targets_repo_mcp_server(self):
        wrapper_path = REPO_ROOT / "deep-scavenger-intel-plugin" / "bin" / "run-intel-mcp.sh"
        wrapper = wrapper_path.read_text(encoding="utf-8")

        self.assertIn("scripts/intel_mcp_server.py", wrapper)
        self.assertIn("exec python3", wrapper)

    def test_plugin_readme_documents_doctor_and_client_config(self):
        readme_path = REPO_ROOT / "deep-scavenger-intel-plugin" / "README.md"
        readme = readme_path.read_text(encoding="utf-8")

        self.assertIn("scripts/intel_mcp_doctor.py", readme)
        self.assertIn("/Users/lixun/.claude.json", readme)
        self.assertIn("/Users/lixun/.codex/config.toml", readme)
        self.assertIn("intel-duty-officer", readme)
        self.assertIn("source-health-triage", readme)
        self.assertIn("briefing-analyst", readme)
        self.assertIn("dsintel://registry/tools", readme)
        self.assertIn("dsintel://docs/plugin-readme", readme)
        self.assertIn("test_intel_mcp_stack.sh", readme)
        self.assertIn("install_intel_mcp_pre_push_hook.sh", readme)
        self.assertIn("install_intel_mcp_clients.py", readme)
        self.assertIn("bootstrap_intel_mcp_plugin.sh", readme)


if __name__ == "__main__":
    unittest.main()
