#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path("/Users/lixun/Documents/codex ")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_skills.intel_mcp import run_stdio_server  # noqa: E402
from agent_skills.intel_runtime import DEFAULT_BASE_URL  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP stdio server for Deep Scavenger intel tools.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    return run_stdio_server(base_url=args.base_url)


if __name__ == "__main__":
    raise SystemExit(main())
