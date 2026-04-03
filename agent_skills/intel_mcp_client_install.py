from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WRAPPER_PATH = REPO_ROOT / "deep-scavenger-intel-plugin/bin/run-intel-mcp.sh"
DEFAULT_CLAUDE_CONFIG_PATH = Path.home() / ".claude.json"
DEFAULT_CODEX_CONFIG_PATH = Path.home() / ".codex/config.toml"
SERVER_NAME = "deep-scavenger-intel-tools"


def _desired_claude_entry(command: str) -> dict[str, Any]:
    return {
        "command": command,
        "type": "stdio",
    }


def _desired_codex_section(command: str) -> str:
    escaped_command = command.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f"[mcp_servers.{SERVER_NAME}]\n"
        'type = "stdio"\n'
        f'command = "{escaped_command}"\n'
    )


def check_claude_config(config_path: Path, *, expected_command: str) -> dict[str, Any]:
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
    result["matches_expected_command"] = command == expected_command and server.get("type") == "stdio"
    return result


def install_claude_config(config_path: Path, *, command: str) -> dict[str, Any]:
    payload: dict[str, Any]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        payload = {}

    mcp_servers = payload.setdefault("mcpServers", {})
    desired = _desired_claude_entry(command)
    changed = mcp_servers.get(SERVER_NAME) != desired
    mcp_servers[SERVER_NAME] = desired
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = check_claude_config(config_path, expected_command=command)
    result["changed"] = changed
    return result


def check_codex_config(config_path: Path, *, expected_command: str) -> dict[str, Any]:
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
    result["matches_expected_command"] = command == expected_command and server.get("type") == "stdio"
    return result


def install_codex_config(config_path: Path, *, command: str) -> dict[str, Any]:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    section_text = _desired_codex_section(command)
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    pattern = re.compile(
        rf"(?ms)^\[mcp_servers\.{re.escape(SERVER_NAME)}\]\n(?:.*\n)*?(?=^\[|\Z)"
    )
    if pattern.search(text):
        new_text = pattern.sub(section_text, text)
    else:
        new_text = text.rstrip()
        if new_text:
            new_text += "\n\n"
        new_text += section_text
    changed = new_text != text
    config_path.write_text(new_text, encoding="utf-8")

    result = check_codex_config(config_path, expected_command=command)
    result["changed"] = changed
    return result


def run_client_install(
    *,
    wrapper_path: Path = DEFAULT_WRAPPER_PATH,
    claude_config_path: Path = DEFAULT_CLAUDE_CONFIG_PATH,
    codex_config_path: Path = DEFAULT_CODEX_CONFIG_PATH,
    install_claude: bool = True,
    install_codex: bool = True,
    check_only: bool = False,
) -> dict[str, Any]:
    command = str(wrapper_path)
    results: dict[str, Any] = {
        "status": "ok",
        "wrapper_path": command,
        "claude": None,
        "codex": None,
    }

    if install_claude:
        results["claude"] = (
            check_claude_config(claude_config_path, expected_command=command)
            if check_only
            else install_claude_config(claude_config_path, command=command)
        )
    if install_codex:
        results["codex"] = (
            check_codex_config(codex_config_path, expected_command=command)
            if check_only
            else install_codex_config(codex_config_path, command=command)
        )

    checks = []
    for key in ("claude", "codex"):
        result = results.get(key)
        if result is not None:
            checks.append(bool(result["matches_expected_command"]))
    results["status"] = "ok" if all(checks) else "degraded"
    return results


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Install or check Deep Scavenger intel MCP client registration.")
    parser.add_argument("--wrapper-path", default=str(DEFAULT_WRAPPER_PATH))
    parser.add_argument("--claude-config", default=str(DEFAULT_CLAUDE_CONFIG_PATH))
    parser.add_argument("--codex-config", default=str(DEFAULT_CODEX_CONFIG_PATH))
    parser.add_argument("--claude-only", action="store_true")
    parser.add_argument("--codex-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    install_claude = not args.codex_only
    install_codex = not args.claude_only
    result = run_client_install(
        wrapper_path=Path(args.wrapper_path),
        claude_config_path=Path(args.claude_config),
        codex_config_path=Path(args.codex_config),
        install_claude=install_claude,
        install_codex=install_codex,
        check_only=args.check,
    )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
