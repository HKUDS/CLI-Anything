from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from agent_skills.intel_runtime import (
    CONTRACT_VERSION,
    DEFAULT_BASE_URL,
    RuntimeContractError,
    build_tool_registry,
    build_tool_response,
)


MCP_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = (
    MCP_PROTOCOL_VERSION,
    "2025-03-26",
    "2024-11-05",
)
SERVER_INFO = {
    "name": "deep-scavenger-intel-tools",
    "title": "Deep Scavenger Intel Tools",
    "version": CONTRACT_VERSION,
}
SERVER_INSTRUCTIONS = (
    "Read-only Deep Scavenger runtime tools. Do not assume mutation support. "
    "Use intel-health, intel-ops-overview, and intel-briefing as the source of truth."
)
REPO_ROOT = Path(__file__).resolve().parents[1]

RESOURCE_CATALOG = {
    "dsintel://registry/tools": {
        "name": "intel_tool_registry.json",
        "title": "Intel Tool Registry",
        "description": "Machine-readable registry for Deep Scavenger intel MCP tools.",
        "mimeType": "application/json",
        "path": REPO_ROOT / "agent_skills" / "intel_tool_registry.json",
        "audience": ["assistant", "user"],
        "priority": 1.0,
    },
    "dsintel://contracts/intel-skill-tool-contracts": {
        "name": "intel-skill-tool-contracts.md",
        "title": "Intel Skill Tool Contracts",
        "description": "Specification for runtime-backed intel tool surfaces and skill bindings.",
        "mimeType": "text/markdown",
        "path": REPO_ROOT / "specs/002-intel-agent-skills/contracts/intel-skill-tool-contracts.md",
        "audience": ["assistant"],
        "priority": 0.9,
    },
    "dsintel://contracts/quickstart": {
        "name": "quickstart.md",
        "title": "Intel Agent Skills Quickstart",
        "description": "Validation flow for tool contracts, MCP wrapper, and plugin discovery.",
        "mimeType": "text/markdown",
        "path": REPO_ROOT / "specs/002-intel-agent-skills/quickstart.md",
        "audience": ["assistant", "user"],
        "priority": 0.8,
    },
    "dsintel://docs/plugin-readme": {
        "name": "deep-scavenger-intel-plugin",
        "title": "Deep Scavenger Intel Plugin README",
        "description": "Plugin packaging, live client registration, and MCP doctor usage.",
        "mimeType": "text/markdown",
        "path": REPO_ROOT / "deep-scavenger-intel-plugin" / "README.md",
        "audience": ["assistant", "user"],
        "priority": 0.8,
    },
    "dsintel://skills/intel-duty-officer": {
        "name": "intel-duty-officer",
        "title": "Intel Duty Officer Skill",
        "description": "Operator snapshot skill instructions grounded in runtime truth.",
        "mimeType": "text/markdown",
        "path": REPO_ROOT / ".agents/skills/intel-duty-officer/SKILL.md",
        "audience": ["assistant"],
        "priority": 0.8,
    },
    "dsintel://skills/source-health-triage": {
        "name": "source-health-triage",
        "title": "Source Health Triage Skill",
        "description": "Bounded triage skill instructions for stale sources and pipeline targets.",
        "mimeType": "text/markdown",
        "path": REPO_ROOT / ".agents/skills/source-health-triage/SKILL.md",
        "audience": ["assistant"],
        "priority": 0.8,
    },
    "dsintel://skills/briefing-analyst": {
        "name": "briefing-analyst",
        "title": "Briefing Analyst Skill",
        "description": "Skill instructions for protocol-backed briefing analysis and legacy fallback.",
        "mimeType": "text/markdown",
        "path": REPO_ROOT / ".agents/skills/briefing-analyst/SKILL.md",
        "audience": ["assistant"],
        "priority": 0.8,
    },
}

PROMPT_CATALOG = {
    "intel-duty-officer": {
        "title": "Intel Duty Officer",
        "description": "Produce one bounded operator snapshot from live Deep Scavenger runtime truth.",
        "arguments": [],
        "message_builder": lambda arguments: [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "Use the Deep Scavenger intel tools to produce one current operator snapshot. "
                        "Call intel-health and intel-ops-overview. Lead with overall status, top degraded "
                        "signals, and next actions. Stay read-only and cite runtime-backed evidence only."
                    ),
                },
            }
        ],
    },
    "source-health-triage": {
        "title": "Source Health Triage",
        "description": "Diagnose why a specific source or bounded pipeline target is stale, degraded, or blocked.",
        "arguments": [
            {
                "name": "target",
                "description": "Source key or bounded target such as reddit, github, scoring_pipeline, local_ai_control_plane, watchdog, or control_plane_alerts.",
                "required": True,
            }
        ],
        "message_builder": lambda arguments: [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "Use the Deep Scavenger intel tools to triage the bounded runtime concern "
                        f"`{arguments['target']}`. Read from intel-health and intel-ops-overview. Return a "
                        "structured diagnosis grounded in runtime evidence, preserve uncertainty, and lead "
                        "with diagnosis summary, highest-confidence evidence, and next action."
                    ),
                },
            }
        ],
    },
    "briefing-analyst": {
        "title": "Briefing Analyst",
        "description": "Explain the latest briefing verdict, confidence, action bias, evidence matrix, and final claims.",
        "arguments": [],
        "message_builder": lambda arguments: [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "Use the Deep Scavenger intel tools to analyze the latest briefing. "
                        "Call intel-briefing and use intel-ops-overview as optional context. "
                        "Prefer protocol-backed verdict, confidence, action_bias, evidence_matrix, "
                        "and final claims when available. If the briefing is legacy-only, degrade "
                        "explicitly instead of inventing protocol fields."
                    ),
                },
            }
        ],
    },
}


FetchJson = Callable[[str, int], Any]


def _jsonrpc_success(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _jsonrpc_error(message_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": message_id, "error": error}


def _coerce_arguments(schema: dict[str, Any], arguments: Any) -> dict[str, Any]:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object.")

    allowed = set((schema.get("properties") or {}).keys())
    unknown = sorted(set(arguments.keys()) - allowed)
    if unknown:
        raise ValueError(f"Unknown tool arguments: {', '.join(unknown)}")

    if "base_url" in arguments and not isinstance(arguments["base_url"], str):
        raise ValueError("Tool argument 'base_url' must be a string.")

    return arguments


def _build_generic_output_schema(descriptor: dict[str, Any]) -> dict[str, Any]:
    output_contract = descriptor.get("output_contract") or {}
    raw_required = list(output_contract.get("required_raw_fields") or [])
    event_required = list(output_contract.get("required_control_plane_event_fields") or [])
    protocol_backed_fields = list(output_contract.get("protocol_backed_fields") or [])

    raw_response_schema: dict[str, Any] = {
        "type": "object",
        "required": raw_required,
        "additionalProperties": True,
        "properties": {field: {} for field in raw_required},
    }

    if event_required:
        raw_response_schema.setdefault("properties", {})
        raw_response_schema["properties"]["control_plane_alerts"] = {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": event_required,
                        "properties": {field: {} for field in event_required},
                        "additionalProperties": True,
                    },
                }
            },
            "additionalProperties": True,
        }

    for field in protocol_backed_fields:
        raw_response_schema.setdefault("properties", {})
        raw_response_schema["properties"][field] = {}

    return {
        "type": "object",
        "required": [
            "tool_name",
            "contract_version",
            "endpoint_used",
            "request_payload",
            "raw_response",
            "error",
        ],
        "properties": {
            "tool_name": {"type": "string"},
            "contract_version": {"type": "string"},
            "endpoint_used": {"type": ["string", "null"]},
            "request_payload": {"type": "object", "additionalProperties": True},
            "raw_response": raw_response_schema,
            "error": {"type": ["object", "null"], "additionalProperties": True},
        },
        "additionalProperties": True,
    }


def build_mcp_tool_list(*, base_url: str = DEFAULT_BASE_URL) -> list[dict[str, Any]]:
    registry = build_tool_registry(base_url=base_url)
    tools: list[dict[str, Any]] = []
    for descriptor in registry["tools"]:
        tools.append(
            {
                "name": descriptor["name"],
                "title": descriptor.get("title"),
                "description": descriptor.get("description"),
                "inputSchema": descriptor.get("input_schema") or {"type": "object", "properties": {}, "additionalProperties": False},
                "outputSchema": _build_generic_output_schema(descriptor),
                "annotations": {
                    "readOnlyHint": bool(descriptor.get("read_only", False)),
                    "idempotentHint": True,
                    "destructiveHint": False,
                    "openWorldHint": True,
                },
            }
        )
    return tools


def build_mcp_resource_list() -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for uri, descriptor in RESOURCE_CATALOG.items():
        path = Path(descriptor["path"])
        stat = path.stat()
        resources.append(
            {
                "uri": uri,
                "name": descriptor["name"],
                "title": descriptor.get("title"),
                "description": descriptor.get("description"),
                "mimeType": descriptor.get("mimeType"),
                "size": stat.st_size,
                "annotations": {
                    "audience": descriptor.get("audience", ["assistant"]),
                    "priority": descriptor.get("priority", 0.5),
                    "lastModified": descriptor.get("last_modified")
                    or datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                },
            }
        )
    return resources


def read_mcp_resource(uri: str) -> dict[str, Any]:
    descriptor = RESOURCE_CATALOG.get(uri)
    if descriptor is None:
        raise KeyError(uri)
    path = Path(descriptor["path"])
    text = path.read_text(encoding="utf-8")
    return {
        "uri": uri,
        "mimeType": descriptor.get("mimeType", "text/plain"),
        "text": text,
    }


def build_mcp_prompt_list() -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    for name, descriptor in PROMPT_CATALOG.items():
        prompts.append(
            {
                "name": name,
                "title": descriptor.get("title"),
                "description": descriptor.get("description"),
                "arguments": descriptor.get("arguments", []),
            }
        )
    return prompts


def get_mcp_prompt(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    descriptor = PROMPT_CATALOG.get(name)
    if descriptor is None:
        raise KeyError(name)
    arguments = arguments or {}
    for argument in descriptor.get("arguments", []):
        arg_name = argument["name"]
        if argument.get("required") and not isinstance(arguments.get(arg_name), str):
            raise ValueError(f"Missing required prompt argument: {arg_name}")
    return {
        "description": descriptor.get("description"),
        "messages": descriptor["message_builder"](arguments),
    }


@dataclass
class IntelMcpServer:
    base_url: str = DEFAULT_BASE_URL
    fetch_json: FetchJson | None = None

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        message_id = message.get("id")
        method = message.get("method")
        params = message.get("params")

        if not isinstance(method, str) or not method:
            if message_id is None:
                return None
            return _jsonrpc_error(message_id, -32600, "Invalid Request")

        if method == "initialize":
            return self._handle_initialize(message_id, params)
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return _jsonrpc_success(message_id, {})
        if method == "resources/list":
            return self._handle_resources_list(message_id, params)
        if method == "resources/read":
            return self._handle_resources_read(message_id, params)
        if method == "prompts/list":
            return self._handle_prompts_list(message_id, params)
        if method == "prompts/get":
            return self._handle_prompts_get(message_id, params)
        if method == "tools/list":
            return self._handle_tools_list(message_id, params)
        if method == "tools/call":
            return self._handle_tools_call(message_id, params)

        if message_id is None:
            return None
        return _jsonrpc_error(message_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, message_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return _jsonrpc_error(message_id, -32602, "initialize params must be an object")
        requested_version = params.get("protocolVersion")
        negotiated_version = (
            requested_version
            if isinstance(requested_version, str) and requested_version in SUPPORTED_PROTOCOL_VERSIONS
            else MCP_PROTOCOL_VERSION
        )
        result = {
            "protocolVersion": negotiated_version,
            "capabilities": {
                "prompts": {
                    "listChanged": False,
                },
                "resources": {
                    "subscribe": False,
                    "listChanged": False,
                },
                "tools": {
                    "listChanged": False,
                }
            },
            "serverInfo": SERVER_INFO,
            "instructions": SERVER_INSTRUCTIONS,
        }
        return _jsonrpc_success(message_id, result)

    def _handle_prompts_list(self, message_id: Any, params: Any) -> dict[str, Any]:
        cursor = None
        if params is not None:
            if not isinstance(params, dict):
                return _jsonrpc_error(message_id, -32602, "prompts/list params must be an object")
            cursor = params.get("cursor")
        if cursor not in (None, ""):
            return _jsonrpc_success(message_id, {"prompts": [], "nextCursor": None})
        return _jsonrpc_success(message_id, {"prompts": build_mcp_prompt_list()})

    def _handle_prompts_get(self, message_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return _jsonrpc_error(message_id, -32602, "prompts/get params must be an object")
        name = params.get("name")
        arguments = params.get("arguments")
        if not isinstance(name, str) or not name.strip():
            return _jsonrpc_error(message_id, -32602, "prompts/get requires a non-empty name")
        if arguments is not None and not isinstance(arguments, dict):
            return _jsonrpc_error(message_id, -32602, "prompts/get arguments must be an object")
        try:
            prompt = get_mcp_prompt(name, arguments)
        except KeyError:
            return _jsonrpc_error(message_id, -32602, f"Unknown prompt: {name}")
        except ValueError as exc:
            return _jsonrpc_error(message_id, -32602, str(exc))
        return _jsonrpc_success(message_id, prompt)

    def _handle_resources_list(self, message_id: Any, params: Any) -> dict[str, Any]:
        cursor = None
        if params is not None:
            if not isinstance(params, dict):
                return _jsonrpc_error(message_id, -32602, "resources/list params must be an object")
            cursor = params.get("cursor")
        if cursor not in (None, ""):
            return _jsonrpc_success(message_id, {"resources": [], "nextCursor": None})
        return _jsonrpc_success(message_id, {"resources": build_mcp_resource_list()})

    def _handle_resources_read(self, message_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return _jsonrpc_error(message_id, -32602, "resources/read params must be an object")
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            return _jsonrpc_error(message_id, -32602, "resources/read requires a non-empty uri")
        try:
            content = read_mcp_resource(uri)
        except KeyError:
            return _jsonrpc_error(message_id, -32602, f"Unknown resource: {uri}")
        return _jsonrpc_success(message_id, {"contents": [content]})

    def _handle_tools_list(self, message_id: Any, params: Any) -> dict[str, Any]:
        cursor = None
        if params is not None:
            if not isinstance(params, dict):
                return _jsonrpc_error(message_id, -32602, "tools/list params must be an object")
            cursor = params.get("cursor")
        if cursor not in (None, ""):
            return _jsonrpc_success(message_id, {"tools": [], "nextCursor": None})
        return _jsonrpc_success(message_id, {"tools": build_mcp_tool_list(base_url=self.base_url)})

    def _handle_tools_call(self, message_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return _jsonrpc_error(message_id, -32602, "tools/call params must be an object")

        tool_name = params.get("name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            return _jsonrpc_error(message_id, -32602, "tools/call requires a non-empty tool name")

        registry = build_tool_registry(base_url=self.base_url)
        descriptor = next((tool for tool in registry["tools"] if tool["name"] == tool_name), None)
        if descriptor is None:
            return _jsonrpc_error(message_id, -32602, f"Unknown tool: {tool_name}")

        try:
            arguments = _coerce_arguments(descriptor.get("input_schema") or {}, params.get("arguments"))
        except ValueError as exc:
            return _jsonrpc_error(message_id, -32602, str(exc))

        try:
            payload = build_tool_response(
                tool_name,
                base_url=str(arguments.get("base_url") or self.base_url),
                fetch_json=self.fetch_json,
            )
            is_error = bool(payload.get("error"))
        except RuntimeContractError as exc:
            payload = {
                "tool_name": tool_name,
                "contract_version": CONTRACT_VERSION,
                "endpoint_used": None,
                "request_payload": {
                    "method": descriptor["surface"]["method"],
                    "path": descriptor["surface"]["path"],
                    "base_url": str(arguments.get("base_url") or self.base_url).rstrip("/"),
                },
                "raw_response": None,
                "error": {
                    "code": "runtime_contract_error",
                    "message": str(exc),
                    "recoverable": True,
                },
            }
            is_error = True

        result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, ensure_ascii=False),
                }
            ],
            "structuredContent": payload,
            "isError": is_error,
        }
        return _jsonrpc_success(message_id, result)


def _iter_stdio_messages(stdin: Any) -> Any:
    for line in stdin:
        stripped = line.strip()
        if not stripped:
            continue
        yield stripped


def run_stdio_server(*, base_url: str = DEFAULT_BASE_URL, fetch_json: FetchJson | None = None) -> int:
    server = IntelMcpServer(base_url=base_url, fetch_json=fetch_json)
    for raw_message in _iter_stdio_messages(sys.stdin):
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            response = _jsonrpc_error(None, -32700, "Parse error")
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        if isinstance(message, list):
            responses = []
            for item in message:
                if not isinstance(item, dict):
                    responses.append(_jsonrpc_error(None, -32600, "Invalid Request"))
                    continue
                response = server.handle_message(item)
                if response is not None:
                    responses.append(response)
            if responses:
                sys.stdout.write(json.dumps(responses, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            continue

        if not isinstance(message, dict):
            response = _jsonrpc_error(None, -32600, "Invalid Request")
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        response = server.handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    return 0
