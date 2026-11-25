# MCP Backend Pattern

For services that expose an MCP (Model Context Protocol) server instead of a traditional CLI.

## When to Use

- The software has an official or community MCP server
- No native CLI exists, or MCP provides better functionality
- You want to integrate AI/agent tools that speak MCP protocol

**Use case:** When the software provides an MCP server instead of a traditional CLI.
Example: DOMShell provides browser automation via MCP tools.

## Backend Wrapper (`utils/<service>_backend.py`)

```python
import asyncio
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def _call_tool(tool_name: str, arguments: dict) -> Any:
    """Call an MCP tool."""
    server_params = StdioServerParameters(
        command="npx",
        args=["@apireno/domshell"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result

def is_available() -> bool:
    """Check if MCP server is available."""
    # Try to spawn and verify
    ...

# Sync wrappers for each tool
def ls(path: str = "/") -> dict:
    """List directory contents."""
    return asyncio.run(_call_tool("domshell_ls", {"path": path}))
```

## Session Management

- MCP server spawns per command (stateless from server perspective)
- CLI maintains state (URL, working directory, navigation history)
- Each command re-spawns the MCP server process

## Daemon Mode (Optional)

- Spawn MCP server once, reuse connection for multiple commands
- Reduces latency for interactive use
- Requires explicit start/stop or `--daemon` flag

## Dependencies

Add `mcp>=0.1.0` to `install_requires`.

## Example Implementations

- `browser/agent-harness` — DOMShell MCP server for browser automation
- See: https://github.com/HKUDS/CLI-Anything/tree/main/browser/agent-harness
