from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from agent_skills.intel_mcp import MCP_PROTOCOL_VERSION, PROMPT_CATALOG, RESOURCE_CATALOG


REPO_ROOT = Path("/Users/lixun/Documents/codex ")
DEFAULT_WRAPPER_PATH = REPO_ROOT / "deep-scavenger-intel-plugin/bin/run-intel-mcp.sh"
DEFAULT_CLAUDE_CONFIG_PATH = Path("/Users/lixun/.claude.json")
DEFAULT_CODEX_CONFIG_PATH = Path("/Users/lixun/.codex/config.toml")
DEFAULT_GIT_HOOK_PATH = REPO_ROOT / ".git/hooks/pre-push"
SERVER_NAME = "deep-scavenger-intel-tools"


def inspect_wrapper(wrapper_path: Path = DEFAULT_WRAPPER_PATH) -> dict[str, Any]:
    return {
        "path": str(wrapper_path),
        "exists": wrapper_path.exists(),
        "executable": wrapper_path.exists() and os.access(wrapper_path, os.X_OK),
    }


def inspect_claude_config(
    config_path: Path = DEFAULT_CLAUDE_CONFIG_PATH,
    *,
    expected_command: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(config_path),
        "configured": False,
        "matches_expected_command": False,
        "command": None,
    }
    if not config_path.exists():
        result["error"] = "missing"
        return result

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    server = (payload.get("mcpServers") or {}).get(SERVER_NAME)
    if not isinstance(server, dict):
        result["error"] = "server_not_found"
        return result

    command = server.get("command")
    result["configured"] = True
    result["command"] = command
    result["type"] = server.get("type")
    result["matches_expected_command"] = bool(expected_command and command == expected_command)
    return result


def inspect_codex_config(
    config_path: Path = DEFAULT_CODEX_CONFIG_PATH,
    *,
    expected_command: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(config_path),
        "configured": False,
        "matches_expected_command": False,
        "command": None,
    }
    if not config_path.exists():
        result["error"] = "missing"
        return result

    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    server = (payload.get("mcp_servers") or {}).get(SERVER_NAME)
    if not isinstance(server, dict):
        result["error"] = "server_not_found"
        return result

    command = server.get("command")
    result["configured"] = True
    result["command"] = command
    result["type"] = server.get("type")
    result["matches_expected_command"] = bool(expected_command and command == expected_command)
    return result


def run_handshake(
    wrapper_path: Path = DEFAULT_WRAPPER_PATH,
    *,
    timeout: int = 10,
) -> dict[str, Any]:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "intel-mcp-doctor", "version": "1.0.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "prompts/list", "params": {}},
        {"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}},
    ]
    proc = subprocess.run(
        [str(wrapper_path)],
        input="\n".join(json.dumps(item, ensure_ascii=False) for item in requests) + "\n",
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    result: dict[str, Any] = {
        "ok": False,
        "exit_code": proc.returncode,
        "stderr": proc.stderr.strip() or None,
        "tool_count": 0,
        "prompt_count": 0,
        "resource_count": 0,
        "server_name": None,
        "protocol_version": None,
    }
    if proc.returncode != 0:
        return result

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) < 4:
        result["stderr"] = "incomplete_handshake"
        return result

    responses = [json.loads(line) for line in lines]
    init_response = responses[0].get("result") or {}
    tools_response = responses[1].get("result") or {}
    prompts_response = responses[2].get("result") or {}
    resources_response = responses[3].get("result") or {}

    tool_names = [tool.get("name") for tool in tools_response.get("tools") or []]
    prompt_names = [prompt.get("name") for prompt in prompts_response.get("prompts") or []]
    resource_uris = [resource.get("uri") for resource in resources_response.get("resources") or []]
    expected_resource_uris = set(RESOURCE_CATALOG.keys())
    expected_prompt_names = set(PROMPT_CATALOG.keys())

    result["server_name"] = (init_response.get("serverInfo") or {}).get("name")
    result["protocol_version"] = init_response.get("protocolVersion")
    result["tool_count"] = len(tool_names)
    result["prompt_count"] = len(prompt_names)
    result["resource_count"] = len(resource_uris)
    result["tool_names"] = tool_names
    result["prompt_names"] = prompt_names
    result["resource_uris"] = resource_uris
    result["ok"] = (
        result["server_name"] == SERVER_NAME
        and result["protocol_version"] == MCP_PROTOCOL_VERSION
        and {"intel-health", "intel-ops-overview", "intel-briefing"}.issubset(set(tool_names))
        and expected_prompt_names.issubset(set(prompt_names))
        and expected_resource_uris.issubset(set(resource_uris))
    )
    return result


def run_live_prompt_checks(
    wrapper_path: Path = DEFAULT_WRAPPER_PATH,
    *,
    timeout: int = 10,
) -> dict[str, Any]:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "intel-mcp-doctor", "version": "1.0.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "prompts/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "prompts/get",
            "params": {"name": "source-health-triage", "arguments": {"target": "reddit"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "prompts/get",
            "params": {"name": "briefing-analyst", "arguments": {}},
        },
    ]
    proc = subprocess.run(
        [str(wrapper_path)],
        input="\n".join(json.dumps(item, ensure_ascii=False) for item in requests) + "\n",
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    result: dict[str, Any] = {
        "ok": False,
        "exit_code": proc.returncode,
        "stderr": proc.stderr.strip() or None,
        "prompt_count": 0,
        "prompts": {},
    }
    if proc.returncode != 0:
        return result

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) < 4:
        result["stderr"] = "incomplete_live_prompt_checks"
        return result

    responses = [json.loads(line) for line in lines]
    prompt_list = (responses[1].get("result") or {}).get("prompts") or []
    prompt_names = [prompt.get("name") for prompt in prompt_list]
    result["prompt_count"] = len(prompt_names)
    result["prompt_names"] = prompt_names

    triage_prompt = (responses[2].get("result") or {})
    briefing_prompt = (responses[3].get("result") or {})
    triage_text = (((triage_prompt.get("messages") or [{}])[0].get("content") or {}).get("text")) or ""
    briefing_text = (((briefing_prompt.get("messages") or [{}])[0].get("content") or {}).get("text")) or ""

    result["prompts"] = {
        "source-health-triage": {
            "ok": "reddit" in triage_text and "intel-health" in triage_text and "intel-ops-overview" in triage_text,
            "message_preview": triage_text[:200],
        },
        "briefing-analyst": {
            "ok": "intel-briefing" in briefing_text and "intel-ops-overview" in briefing_text,
            "message_preview": briefing_text[:200],
        },
    }
    result["ok"] = set(PROMPT_CATALOG.keys()).issubset(set(prompt_names)) and all(
        prompt["ok"] for prompt in result["prompts"].values()
    )
    return result


def inspect_pre_push_hook(hook_path: Path = DEFAULT_GIT_HOOK_PATH) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(hook_path),
        "installed": False,
        "matches_release_gate": False,
    }
    if not hook_path.exists():
        result["error"] = "missing"
        return result
    text = hook_path.read_text(encoding="utf-8")
    result["installed"] = True
    result["matches_release_gate"] = "test_intel_mcp_stack.sh" in text
    return result


def run_live_tool_calls(
    wrapper_path: Path = DEFAULT_WRAPPER_PATH,
    *,
    timeout: int = 10,
    base_url: str | None = None,
) -> dict[str, Any]:
    tool_arguments: dict[str, dict[str, Any]] = {
        "intel-health": {},
        "intel-ops-overview": {},
        "intel-briefing": {},
    }
    if base_url:
        for arguments in tool_arguments.values():
            arguments["base_url"] = base_url

    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "intel-mcp-doctor", "version": "1.0.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    ]
    next_id = 2
    for tool_name, arguments in tool_arguments.items():
        requests.append(
            {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
        )
        next_id += 1

    proc = subprocess.run(
        [str(wrapper_path)],
        input="\n".join(json.dumps(item, ensure_ascii=False) for item in requests) + "\n",
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    result: dict[str, Any] = {
        "ok": False,
        "exit_code": proc.returncode,
        "stderr": proc.stderr.strip() or None,
        "tools": {},
    }
    if proc.returncode != 0:
        return result

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) < 4:
        result["stderr"] = "incomplete_live_tool_calls"
        return result

    responses = [json.loads(line) for line in lines]
    tool_names = ["intel-health", "intel-ops-overview", "intel-briefing"]
    expected_required_fields = {
        "intel-health": [
            "status",
            "source_health",
            "local_ai_control_plane",
            "scoring_pipeline",
            "control_plane_alerts",
        ],
        "intel-ops-overview": [
            "summary",
            "alerts",
            "scoring_pipeline",
            "harness_overview",
            "latest_briefing",
            "control_plane_alerts",
        ],
        "intel-briefing": [
            "date",
            "content",
            "protocol_available",
        ],
    }

    ok = True
    for tool_name, response in zip(tool_names, responses[1:], strict=True):
        tool_result = (response.get("result") or {})
        structured = tool_result.get("structuredContent") or {}
        raw_response = structured.get("raw_response") or {}
        missing_fields = [
            field for field in expected_required_fields[tool_name] if field not in raw_response
        ]
        tool_ok = not tool_result.get("isError") and not missing_fields and structured.get("tool_name") == tool_name
        result["tools"][tool_name] = {
            "ok": tool_ok,
            "is_error": bool(tool_result.get("isError")),
            "missing_fields": missing_fields,
            "endpoint_used": structured.get("endpoint_used"),
            "protocol_available": raw_response.get("protocol_available") if tool_name == "intel-briefing" else None,
        }
        if not tool_ok:
            ok = False

    result["ok"] = ok
    result["tool_count"] = len(result["tools"])
    return result


def run_doctor(
    *,
    wrapper_path: Path = DEFAULT_WRAPPER_PATH,
    claude_config_path: Path = DEFAULT_CLAUDE_CONFIG_PATH,
    codex_config_path: Path = DEFAULT_CODEX_CONFIG_PATH,
    timeout: int = 10,
    base_url: str | None = None,
) -> dict[str, Any]:
    expected_command = str(wrapper_path)
    wrapper = inspect_wrapper(wrapper_path)
    claude = inspect_claude_config(claude_config_path, expected_command=expected_command)
    codex = inspect_codex_config(codex_config_path, expected_command=expected_command)
    pre_push_hook = inspect_pre_push_hook()
    if wrapper["exists"] and wrapper["executable"]:
        handshake = run_handshake(wrapper_path, timeout=timeout)
        live_prompts = run_live_prompt_checks(wrapper_path, timeout=timeout)
        live_tool_calls = run_live_tool_calls(wrapper_path, timeout=timeout, base_url=base_url)
    else:
        handshake = {
            "ok": False,
            "exit_code": None,
            "stderr": "wrapper_not_executable",
            "tool_count": 0,
            "prompt_count": 0,
            "resource_count": 0,
            "server_name": None,
            "protocol_version": None,
        }
        live_prompts = {
            "ok": False,
            "exit_code": None,
            "stderr": "wrapper_not_executable",
            "prompts": {},
            "prompt_count": 0,
        }
        live_tool_calls = {
            "ok": False,
            "exit_code": None,
            "stderr": "wrapper_not_executable",
            "tools": {},
            "tool_count": 0,
        }

    checks = {
        "wrapper": bool(wrapper["exists"] and wrapper["executable"]),
        "claude": bool(claude["configured"] and claude["matches_expected_command"]),
        "codex": bool(codex["configured"] and codex["matches_expected_command"]),
        "handshake": bool(handshake["ok"]),
        "live_prompts": bool(live_prompts["ok"]),
        "live_tools": bool(live_tool_calls["ok"]),
    }
    return {
        "status": "ok" if all(checks.values()) else "degraded",
        "checks": checks,
        "wrapper": wrapper,
        "clients": {"claude": claude, "codex": codex},
        "optional": {"pre_push_hook": pre_push_hook},
        "handshake": handshake,
        "live_prompts": live_prompts,
        "live_tools": live_tool_calls,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Doctor for the Deep Scavenger intel MCP installation.")
    parser.add_argument("--wrapper-path", default=str(DEFAULT_WRAPPER_PATH))
    parser.add_argument("--claude-config", default=str(DEFAULT_CLAUDE_CONFIG_PATH))
    parser.add_argument("--codex-config", default=str(DEFAULT_CODEX_CONFIG_PATH))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    result = run_doctor(
        wrapper_path=Path(args.wrapper_path),
        claude_config_path=Path(args.claude_config),
        codex_config_path=Path(args.codex_config),
        timeout=args.timeout,
        base_url=args.base_url,
    )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    if args.strict and result["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
