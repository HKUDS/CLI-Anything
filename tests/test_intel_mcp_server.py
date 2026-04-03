import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path("/Users/lixun/Documents/codex ")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_skills.intel_mcp import (  # noqa: E402
    MCP_PROTOCOL_VERSION,
    IntelMcpServer,
    build_mcp_prompt_list,
    build_mcp_tool_list,
)


def _make_fetcher(payloads):
    def _fetch(url, timeout=10):
        path = url.split("://", 1)[-1]
        path = "/" + path.split("/", 1)[1] if "/" in path else "/"
        if path not in payloads:
            raise AssertionError(f"missing fixture for {path}")
        return payloads[path]

    return _fetch


class IntelMcpServerUnitTests(unittest.TestCase):
    def test_initialize_negotiates_supported_protocol(self):
        server = IntelMcpServer()
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2099-01-01",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }
        )

        self.assertEqual(response["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)
        self.assertIn("tools", response["result"]["capabilities"])
        self.assertIn("resources", response["result"]["capabilities"])
        self.assertEqual(response["result"]["serverInfo"]["name"], "deep-scavenger-intel-tools")

    def test_tools_list_exposes_read_only_annotations_and_output_schema(self):
        tools = build_mcp_tool_list()
        by_name = {tool["name"]: tool for tool in tools}

        self.assertIn("intel-health", by_name)
        self.assertIn("intel-ops-overview", by_name)
        self.assertIn("intel-briefing", by_name)
        self.assertTrue(by_name["intel-health"]["annotations"]["readOnlyHint"])
        self.assertEqual(
            by_name["intel-health"]["outputSchema"]["properties"]["raw_response"]["required"],
            [
                "status",
                "source_health",
                "local_ai_control_plane",
                "scoring_pipeline",
                "control_plane_alerts",
            ],
        )
        self.assertIn(
            "recommended_action",
            by_name["intel-ops-overview"]["outputSchema"]["properties"]["raw_response"]["properties"]["control_plane_alerts"]["properties"]["events"]["items"]["required"],
        )

    def test_tools_call_returns_structured_content(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {},
                "local_ai_control_plane": {},
                "scoring_pipeline": {},
                "control_plane_alerts": {
                    "state": "idle",
                    "event_count": 0,
                    "sent": 0,
                    "suppressed": 0,
                    "kinds": [],
                    "events": [],
                },
            }
        }
        server = IntelMcpServer(fetch_json=_make_fetcher(payloads))
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "intel-health",
                    "arguments": {},
                },
            }
        )

        self.assertFalse(response["result"]["isError"])
        self.assertEqual(response["result"]["structuredContent"]["tool_name"], "intel-health")
        self.assertEqual(response["result"]["structuredContent"]["raw_response"]["status"], "OPERATIONAL")
        self.assertIn("\"tool_name\": \"intel-health\"", response["result"]["content"][0]["text"])

    def test_tools_call_rejects_unknown_arguments(self):
        server = IntelMcpServer()
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "intel-health",
                    "arguments": {"unexpected": True},
                },
            }
        )

        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("Unknown tool arguments", response["error"]["message"])

    def test_resources_list_and_read_expose_contract_context(self):
        server = IntelMcpServer()
        list_response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/list",
                "params": {},
            }
        )
        resources = {resource["uri"]: resource for resource in list_response["result"]["resources"]}

        self.assertIn("dsintel://registry/tools", resources)
        self.assertIn("dsintel://contracts/intel-skill-tool-contracts", resources)
        self.assertIn("dsintel://docs/plugin-readme", resources)
        self.assertIn("dsintel://skills/briefing-analyst", resources)

        read_response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "resources/read",
                "params": {"uri": "dsintel://registry/tools"},
            }
        )

        self.assertEqual(read_response["result"]["contents"][0]["uri"], "dsintel://registry/tools")
        self.assertEqual(read_response["result"]["contents"][0]["mimeType"], "application/json")
        self.assertIn("\"intel-health\"", read_response["result"]["contents"][0]["text"])

    def test_prompts_list_and_get_expose_operator_workflows(self):
        prompts = {prompt["name"]: prompt for prompt in build_mcp_prompt_list()}
        self.assertIn("intel-duty-officer", prompts)
        self.assertIn("source-health-triage", prompts)
        self.assertIn("briefing-analyst", prompts)
        self.assertEqual(prompts["source-health-triage"]["arguments"][0]["name"], "target")

        server = IntelMcpServer()
        get_response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "prompts/get",
                "params": {
                    "name": "source-health-triage",
                    "arguments": {"target": "reddit"},
                },
            }
        )

        self.assertIn("reddit", get_response["result"]["messages"][0]["content"]["text"])
        self.assertIn("intel-health", get_response["result"]["messages"][0]["content"]["text"])


class IntelMcpServerStdioTests(unittest.TestCase):
    def test_stdio_server_roundtrip(self):
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "stdio-test", "version": "1.0.0"},
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "prompts/list",
                "params": {},
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/list",
                "params": {},
            },
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "intel-briefing",
                    "arguments": {"base_url": "http://127.0.0.1:1"},
                },
            },
        ]

        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/intel_mcp_server.py")],
            input="\n".join(json.dumps(item, ensure_ascii=False) for item in requests) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )

        responses = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(responses), 5)
        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(responses[0]["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)
        self.assertEqual(responses[1]["id"], 2)
        tool_names = [tool["name"] for tool in responses[1]["result"]["tools"]]
        self.assertIn("intel-health", tool_names)
        self.assertEqual(responses[2]["id"], 3)
        prompt_names = [prompt["name"] for prompt in responses[2]["result"]["prompts"]]
        self.assertIn("briefing-analyst", prompt_names)
        self.assertEqual(responses[3]["id"], 4)
        resource_uris = [resource["uri"] for resource in responses[3]["result"]["resources"]]
        self.assertIn("dsintel://registry/tools", resource_uris)
        self.assertEqual(responses[4]["id"], 5)
        self.assertEqual(responses[4]["result"]["structuredContent"]["tool_name"], "intel-briefing")
        self.assertTrue(responses[4]["result"]["isError"])
        self.assertEqual(
            responses[4]["result"]["structuredContent"]["error"]["code"],
            "runtime_contract_error",
        )


if __name__ == "__main__":
    unittest.main()
