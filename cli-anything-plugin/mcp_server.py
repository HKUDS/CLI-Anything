#!/usr/bin/env python3
"""
CLI-Anything MCP Server for Trae IDE
Using FastMCP framework for simpler setup
"""

from mcp.server.fastmcp import FastMCP
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent
COMMANDS_DIR = PLUGIN_DIR / "commands"
HARNESS_PATH = PLUGIN_DIR / "HARNESS.md"

mcp = FastMCP("CLI-Anything")


def load_command_md(command_name: str) -> str:
    """Load command definition from markdown file"""
    cmd_file = COMMANDS_DIR / f"{command_name}.md"
    if cmd_file.exists():
        return cmd_file.read_text(encoding="utf-8")
    return ""


@mcp.tool()
def cli_anything(software_path: str) -> str:
    """Build a complete, stateful CLI harness for any GUI application"""
    cmd_doc = load_command_md("cli-anything")
    return f"""# CLI-Anything Build Command

## Instructions
{cmd_doc}

## Usage
To build a CLI harness, provide the software path or GitHub URL:

- Local path: `{software_path}`
- GitHub URL: `https://github.com/user/repo`

The agent will follow the HARNESS.md methodology to:
1. Analyze the codebase
2. Design CLI architecture
3. Implement the CLI
4. Create tests
5. Document everything
"""


@mcp.tool()
def cli_anything_refine(software_path: str, focus: str = "All capabilities") -> str:
    """Refine an existing CLI harness to improve coverage"""
    cmd_doc = load_command_md("refine")
    return f"""# CLI-Anything Refine Command

## Instructions
{cmd_doc}

## Usage
To refine an existing CLI harness:

- Base path: `{software_path}`
- Focus area: {focus}

The agent will analyze gaps and expand coverage.
"""


@mcp.tool()
def cli_anything_test(software_path: str) -> str:
    """Run tests for a CLI harness"""
    cmd_doc = load_command_md("test")
    return f"""# CLI-Anything Test Command

## Instructions
{cmd_doc}

## Usage
Software path: {software_path}
"""


@mcp.tool()
def cli_anything_validate(software_path: str) -> str:
    """Validate a CLI harness against HARNESS.md standards"""
    cmd_doc = load_command_md("validate")
    return f"""# CLI-Anything Validate Command

## Instructions
{cmd_doc}

## Usage
Software path: {software_path}
"""


@mcp.tool()
def cli_anything_list(path: str = ".", depth: int = 0, json_output: bool = False) -> str:
    """List all available CLI-Anything tools"""
    import os
    import json
    
    tools = []
    search_dir = Path(path)
    
    def scan_dir(p, current_depth):
        if depth > 0 and current_depth > depth:
            return
        if not p.exists():
            return
        for item in p.iterdir():
            if item.is_dir():
                cli_file = item / "agent-harness" / "cli_anything"
                if cli_file.exists():
                    tools.append({
                        "name": item.name,
                        "path": str(item),
                        "status": "generated"
                    })
                scan_dir(item, current_depth + 1)
    
    scan_dir(search_dir, 0)
    
    if json_output:
        return json.dumps(tools, indent=2)
    
    return f"Found {len(tools)} CLI tools:\n\n" + "\n".join(f"- {t['name']}: {t['path']} ({t['status']})" for t in tools)


@mcp.tool()
def get_harness_doc() -> str:
    """Get the HARNESS.md documentation for cli-anything methodology"""
    if HARNESS_PATH.exists():
        return HARNESS_PATH.read_text(encoding="utf-8")
    return "HARNESS.md not found"


@mcp.tool()
def get_command_doc(command_name: str) -> str:
    """Get documentation for a specific cli-anything command"""
    content = load_command_md(command_name)
    if not content:
        content = load_command_md(f"cli-anything-{command_name}")
    return content or f"Command {command_name} not found"


if __name__ == "__main__":
    mcp.run()
