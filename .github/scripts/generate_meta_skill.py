#!/usr/bin/env python3
"""Generate cli-hub-skill/SKILL.md from registry.json."""
import json
from pathlib import Path
from collections import defaultdict

def main():
    repo_root = Path(__file__).parent.parent.parent
    registry_path = repo_root / 'registry.json'
    output_path = repo_root / 'cli-hub-skill' / 'SKILL.md'

    with open(registry_path) as f:
        data = json.load(f)

    # Group by category
    by_category = defaultdict(list)
    for cli in data['clis']:
        by_category[cli['category']].append(cli)

    lines = [
        "---",
        "name: cli-anything-hub",
        "description: >-",
        f"  Browse and install {len(data['clis'])}+ agent-native CLI tools for GUI software.",
        "  Covers image editing, 3D, video, audio, office, diagrams, AI, and more.",
        "---",
        "",
        "# CLI-Anything Hub",
        "",
        f"Agent-native stateful CLI interfaces for {len(data['clis'])} applications. All CLIs support `--json` output, REPL mode, and undo/redo.",
        "",
        "## Quick Install",
        "",
        "```bash",
        "# Install any CLI",
        f"pip install git+{data['meta']['repo']}.git#subdirectory=<name>/agent-harness",
        "",
        "# Example: Install GIMP CLI",
        f"pip install git+{data['meta']['repo']}.git#subdirectory=gimp/agent-harness",
        "```",
        "",
        "## Available CLIs",
        ""
    ]

    for category in sorted(by_category.keys()):
        clis = by_category[category]
        lines.append(f"### {category.title()}")
        lines.append("")
        lines.append("| Name | Description | Install |")
        lines.append("|------|-------------|---------|")

        for cli in sorted(clis, key=lambda x: x['name']):
            name = cli['display_name']
            desc = cli['description']
            install = f"`{cli['install_cmd']}`"
            lines.append(f"| **{name}** | {desc} | {install} |")

        lines.append("")

    lines.extend([
        "## Usage Pattern",
        "",
        "All CLIs follow the same pattern:",
        "",
        "```bash",
        "# Interactive REPL",
        "cli-anything-<name>",
        "",
        "# One-shot command",
        "cli-anything-<name> <group> <command> [options]",
        "",
        "# JSON output for agents",
        "cli-anything-<name> --json <group> <command>",
        "```",
        "",
        "## For AI Agents",
        "",
        "1. Install the CLI you need from the table above",
        "2. Read its full SKILL.md at the repo path shown in registry.json",
        "3. Always use `--json` flag for machine-readable output",
        "4. Check exit codes (0=success, non-zero=error)",
        "",
        "## More Info",
        "",
        f"- Repository: {data['meta']['repo']}",
        "- Web Hub: https://hkuds.github.io/CLI-Anything/",
        f"- Last Updated: {data['meta']['updated']}",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines) + '\n')
    print(f"Generated meta-skill with {len(data['clis'])} CLIs at {output_path}")

if __name__ == '__main__':
    main()
