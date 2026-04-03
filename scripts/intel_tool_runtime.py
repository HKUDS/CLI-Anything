#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_skills.intel_runtime import (  # noqa: E402
    CONTRACT_VERSION,
    DEFAULT_BASE_URL,
    RuntimeContractError,
    TOOL_NAMES,
    build_tool_registry,
    build_tool_response,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Raw runtime-backed Deep Scavenger tool adapter.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--tool", choices=sorted(TOOL_NAMES))
    mode_group.add_argument("--list-tools", action="store_true")
    mode_group.add_argument("--print-registry", action="store_true")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.list_tools:
        registry = build_tool_registry(base_url=args.base_url)
        payload = {
            "contract_version": CONTRACT_VERSION,
            "base_url": registry["base_url"],
            "tools": [
                {
                    "name": tool["name"],
                    "aliases": tool.get("aliases", []),
                    "method": tool["surface"]["method"],
                    "path": tool["surface"]["path"],
                    "read_only": tool["read_only"],
                }
                for tool in registry["tools"]
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0

    if args.print_registry:
        payload = build_tool_registry(base_url=args.base_url)
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0

    try:
        payload = build_tool_response(args.tool, base_url=args.base_url)
    except RuntimeContractError as exc:
        payload = {
            "tool_name": args.tool,
            "contract_version": CONTRACT_VERSION,
            "endpoint_used": None,
            "request_payload": {
                "method": "GET",
                "path": None,
                "base_url": args.base_url.rstrip("/"),
            },
            "raw_response": None,
            "error": {
                "code": "runtime_contract_error",
                "message": str(exc),
                "recoverable": True,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
