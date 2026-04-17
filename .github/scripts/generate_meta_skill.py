#!/usr/bin/env python3
"""Generate cli-hub-skill/SKILL.md from registry.json, public_registry.json, and matrix_registry.json."""
import json
from pathlib import Path
from collections import defaultdict

def main():
    repo_root = Path(__file__).parent.parent.parent
    registry_path = repo_root / 'registry.json'
    public_registry_path = repo_root / 'public_registry.json'
    matrix_registry_path = repo_root / 'matrix_registry.json'
    output_path = repo_root / 'cli-hub-skill' / 'SKILL.md'

    with open(registry_path) as f:
        data = json.load(f)

    public_clis = []
    if public_registry_path.exists():
        with open(public_registry_path) as f:
            public_data = json.load(f)
        public_clis = public_data.get('clis', [])

    matrices = []
    if matrix_registry_path.exists():
        with open(matrix_registry_path) as f:
            matrix_data = json.load(f)
        matrices = matrix_data.get('matrices', [])

    total_count = len(data['clis']) + len(public_clis)

    # Group harness CLIs by category
    by_category = defaultdict(list)
    for cli in data['clis']:
        by_category[cli['category']].append(cli)

    # Group public CLIs by category
    public_by_category = defaultdict(list)
    for cli in public_clis:
        public_by_category[cli['category']].append(cli)

    lines = [
        "---",
        "name: cli-anything-hub",
        "description: >-",
        f"  Browse and install {total_count}+ CLI tools for GUI software and popular platforms.",
        "  Covers image editing, 3D, video, audio, office, diagrams, AI, communication, devops, and more.",
        "---",
        "",
        "# CLI-Anything Hub",
        "",
        f"Agent-native CLI interfaces for {total_count} applications — {len(data['clis'])} harness CLIs (stateful, `--json`, REPL) plus {len(public_clis)} public/third-party CLIs (npm, uv, brew, and more).",
        "",
        "## Quick Install",
        "",
        "```bash",
        "# First, install the CLI Hub package manager",
        "pip install cli-anything-hub",
        "",
        "# Browse available CLIs",
        "cli-hub list",
        "",
        "# Install any CLI by name",
        "cli-hub install gimp",
        "cli-hub install blender",
        "cli-hub install generate-veo-video",
        "",
        "# Search by category or keyword",
        "cli-hub search image",
        "cli-hub search ai",
        "",
        "# Launch an installed CLI",
        "cli-hub launch <name> [args...]",
        "```",
        "",
        "## CLI Matrices",
        "",
        f"`cli-hub` also ships {len(matrices)} curated cross-tool matrices: install one name to pull in a whole workflow kit and read its dedicated SKILL.md.",
        "",
        "```bash",
        "# Browse curated matrices",
        "cli-hub matrix list",
        "",
        "# Inspect one matrix",
        "cli-hub matrix info video-creation",
        "",
        "# Install the whole matrix",
        "cli-hub matrix install video-creation",
        "```",
        "",
        "## CLI-Anything Harness CLIs",
        "",
        f"Stateful, agent-native wrappers for {len(data['clis'])} GUI applications. All support `--json` output, REPL mode, and undo/redo.",
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
            install = f"`cli-hub install {cli['name']}`"
            lines.append(f"| **{name}** | {desc} | {install} |")

        lines.append("")

    lines.extend([
        "## Public & Third-Party CLIs",
        "",
        f"Official and community CLIs for popular platforms, managed via npm, uv, brew, and other installers. {len(public_clis)} CLIs available.",
        ""
    ])

    for category in sorted(public_by_category.keys()):
        clis = public_by_category[category]
        lines.append(f"### {category.title()}")
        lines.append("")
        lines.append("| Name | Description | Entry Point | Install | Skill |")
        lines.append("|------|-------------|-------------|---------|-------|")

        for cli in sorted(clis, key=lambda x: x['name']):
            name = cli['display_name']
            desc = cli['description']
            entry = f"`{cli['entry_point']}`"
            install = f"`cli-hub install {cli['name']}`"
            skill = cli.get('skill_md') or '—'
            skill_cell = f"`{skill}`" if not str(skill).startswith("http") else skill
            lines.append(f"| **{name}** | {desc} | {entry} | {install} | {skill_cell} |")

        lines.append("")

    if matrices:
        lines.extend([
            "## Curated Matrices",
            "",
            "Each matrix is a curated multi-CLI workflow pulled from the CLI Matrix. Installing a matrix installs all member CLIs and points you at a matrix-specific SKILL.md.",
            "",
            "| Matrix | Description | CLIs | Install | Skill |",
            "|--------|-------------|------|---------|-------|",
        ])

        for matrix in sorted(matrices, key=lambda x: x['name']):
            skill = matrix.get('skill_md') or '—'
            install = f"`cli-hub matrix install {matrix['name']}`"
            lines.append(
                f"| **{matrix['display_name']}** | {matrix['description']} | {len(matrix.get('clis', []))} | {install} | `{skill}` |"
            )

        lines.append("")

    lines.extend([
        "## How It Works",
        "",
        "`cli-hub` is a unified package manager for both harness CLIs and public CLIs:",
        "",
        "- **Harness CLIs**: installed via `pip` as `cli-anything-<name>` packages",
        "- **npm CLIs**: installed via `npm install -g`",
        "- **uv CLIs**: installed via `uv tool install`",
        "- **brew/script CLIs**: installed via the tool's native installer",
        "- **bundled CLIs**: detected from PATH (pre-installed with the host app)",
        "- **Matrices**: install a curated set of harness and public CLIs in one command",
        "",
        "## Harness CLI Usage Pattern",
        "",
        "All harness CLIs follow the same pattern:",
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
        "1. Install the hub: `pip install cli-anything-hub`",
        "2. Install the CLI you need: `cli-hub install <name>`",
        "3. Run the CLI directly via its entry point, or use `cli-hub launch <name> [args...]`",
        "4. For harness CLIs: use `--json` flag for machine-readable output; check exit codes (0=success)",
        "5. Read each harness CLI's full SKILL.md at the repo path shown in registry.json",
        "",
        "## More Info",
        "",
        f"- Repository: {data['meta']['repo']}",
        "- Web Hub: https://clianything.cc",
        f"- Last Updated: {data['meta']['updated']}",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines) + '\n')
    print(
        f"Generated meta-skill with {len(data['clis'])} harness CLIs + "
        f"{len(public_clis)} public CLIs + {len(matrices)} matrices at {output_path}"
    )

if __name__ == '__main__':
    main()
