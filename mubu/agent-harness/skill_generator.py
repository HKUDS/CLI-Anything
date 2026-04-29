"""
SKILL.md Generator for CLI-Anything

This module extracts metadata from CLI-Anything harnesses and generates
SKILL.md files following the skill-creator methodology.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _format_display_name(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


@dataclass
class CommandInfo:
    name: str
    description: str


@dataclass
class CommandGroup:
    name: str
    description: str
    commands: list[CommandInfo] = field(default_factory=list)


@dataclass
class Example:
    title: str
    description: str
    code: str


@dataclass
class SkillMetadata:
    skill_name: str
    skill_description: str
    software_name: str
    skill_intro: str
    version: str
    system_package: Optional[str] = None
    command_groups: list[CommandGroup] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)


def extract_intro_from_readme(content: str) -> str:
    lines = content.split("\n")
    intro_lines: list[str] = []
    in_intro = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_intro and intro_lines:
                break
            continue
        if line.startswith("# "):
            in_intro = True
            continue
        if line.startswith("##"):
            break
        if in_intro:
            intro_lines.append(line)

    return " ".join(intro_lines) or "CLI interface for the software."


def extract_system_package(content: str) -> Optional[str]:
    patterns = [
        r"`apt install ([\w\-]+)`",
        r"`brew install ([\w\-]+)`",
        r"`apt-get install ([\w\-]+)`",
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            package = match.group(1)
            if "apt-get" in pattern:
                return f"apt-get install {package}"
            elif "apt" in pattern:
                return f"apt install {package}"
            elif "brew" in pattern:
                return f"brew install {package}"
    return None


def extract_version_from_setup(setup_path: Path) -> str:
    content = setup_path.read_text(encoding="utf-8")
    direct_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    if direct_match:
        return direct_match.group(1)

    constant_match = re.search(r'PACKAGE_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if constant_match:
        return constant_match.group(1)

    return "1.0.0"


def extract_commands_from_cli(cli_path: Path) -> list[CommandGroup]:
    content = cli_path.read_text(encoding="utf-8")
    groups: list[CommandGroup] = []

    group_pattern = (
        r'@(\w+)\.group\(([^)]*)\)'
        r'(?:\s*@[\w.]+(?:\([^)]*\))?)*'
        r'\s*def\s+(\w+)\([^)]*\)'
        r'(?:\s*->\s*[^:]+)?'
        r':\s*'
        r'(?:"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'\'\')?'
    )
    for match in re.finditer(group_pattern, content):
        decorator_owner = match.group(1)
        group_func = match.group(3)
        group_doc = (match.group(4) or match.group(5) or "").strip()
        if decorator_owner == "click" or group_func == "cli":
            continue
        groups.append(
            CommandGroup(
                name=group_func.replace("_", " ").title() or group_func.title(),
                description=group_doc or f"Commands for {group_func.replace('_', ' ')} operations.",
            )
        )

    command_pattern = (
        r'@(\w+)\.command\(([^)]*)\)'
        r'(?:\s*@[\w.]+(?:\([^)]*\))?)*'
        r'\s*def\s+(\w+)\([^)]*\)'
        r'(?:\s*->\s*[^:]+)?'
        r':\s*'
        r'(?:"""([\s\S]*?)"""|\'\'\'([\s\S]*?)\'\'\')?'
    )
    for match in re.finditer(command_pattern, content):
        group_name = match.group(1)
        decorator_args = match.group(2)
        cmd_name = match.group(3)
        cmd_doc = (match.group(4) or match.group(5) or "").strip()
        if group_name == "cli":
            continue
        explicit_name = re.search(r'["\']([^"\']+)["\']', decorator_args)
        command_display_name = explicit_name.group(1) if explicit_name else cmd_name.replace("_", "-")
        for group in groups:
            if group.name.lower().replace(" ", "_") == group_name.lower():
                group.commands.append(
                    CommandInfo(
                        name=command_display_name,
                        description=cmd_doc or f"Execute {cmd_name.replace('_', '-')} operation.",
                    )
                )

    if not groups:
        default_group = CommandGroup(name="General", description="General commands for the CLI.")
        for match in re.finditer(command_pattern, content):
            decorator_args = match.group(2)
            cmd_name = match.group(3)
            cmd_doc = (match.group(4) or match.group(5) or "").strip()
            explicit_name = re.search(r'["\']([^"\']+)["\']', decorator_args)
            default_group.commands.append(
                CommandInfo(
                    name=explicit_name.group(1) if explicit_name else cmd_name.replace("_", "-"),
                    description=cmd_doc or f"Execute {cmd_name.replace('_', '-')} operation.",
                )
            )
        if default_group.commands:
            groups.append(default_group)

    return groups


def generate_examples(software_name: str, command_groups: list[CommandGroup]) -> list[Example]:
    examples = [
        Example(
            title="Interactive REPL Session",
            description="Start an interactive session with persistent document and node context.",
            code=f"""cli-anything-{software_name}
# Enter commands interactively
# Use 'help' to see builtins
# Use session commands to persist current-doc/current-node""",
        )
    ]

    group_names = {group.name.lower() for group in command_groups}
    if "discover" in group_names:
        examples.append(
            Example(
                title="Discover Current Daily Note",
                description="Resolve the current daily note from an explicit folder reference.",
                code=f"""cli-anything-{software_name} --json discover daily-current '<daily-folder-ref>'""",
            )
        )
    if "mutate" in group_names:
        examples.append(
            Example(
                title="Dry-Run Atomic Update",
                description="Inspect the exact outgoing payload before a live mutation.",
                code=(
                    f"cli-anything-{software_name} mutate update-text "
                    "'<doc-ref>' --node-id <node-id> --text 'new text' --json"
                ),
            )
        )
    return examples


def extract_cli_metadata(harness_path: str) -> SkillMetadata:
    harness_root = Path(harness_path)
    cli_anything_dir = harness_root / "cli_anything"
    if not cli_anything_dir.exists():
        raise ValueError(f"cli_anything directory not found in {harness_root}")

    software_dirs = [path for path in cli_anything_dir.iterdir() if path.is_dir() and (path / "__init__.py").exists()]
    if not software_dirs:
        raise ValueError(f"No CLI package found in {harness_root}")

    software_dir = software_dirs[0]
    software_name = software_dir.name
    readme_path = software_dir / "README.md"
    skill_intro = ""
    system_package = None
    if readme_path.exists():
        readme_content = readme_path.read_text(encoding="utf-8")
        skill_intro = extract_intro_from_readme(readme_content)
        system_package = extract_system_package(readme_content)

    setup_path = harness_root / "setup.py"
    version = extract_version_from_setup(setup_path) if setup_path.exists() else "1.0.0"

    cli_file = software_dir / f"{software_name}_cli.py"
    command_groups = extract_commands_from_cli(cli_file) if cli_file.exists() else []
    examples = generate_examples(software_name, command_groups)
    skill_name = f"cli-anything-{software_name}"
    if skill_intro:
        intro_snippet = skill_intro[:100]
        suffix = "..." if len(skill_intro) > 100 else ""
        skill_description = f"Command-line interface for {_format_display_name(software_name)} - {intro_snippet}{suffix}"
    else:
        skill_description = f"Command-line interface for {_format_display_name(software_name)}"

    return SkillMetadata(
        skill_name=skill_name,
        skill_description=skill_description,
        software_name=software_name,
        skill_intro=skill_intro,
        version=version,
        system_package=system_package,
        command_groups=command_groups,
        examples=examples,
    )


def generate_skill_md_simple(metadata: SkillMetadata) -> str:
    lines = [
        "---",
        "name: >-",
        f"  {metadata.skill_name}",
        "description: >-",
        f"  {metadata.skill_description}",
        "---",
        "",
        f"# {metadata.skill_name}",
        "",
        metadata.skill_intro,
        "",
        "## Installation",
        "",
        "This CLI is packaged from the canonical `agent-harness` source tree:",
        "",
        "```bash",
        "pip install -e .",
        "```",
        "",
        "**Prerequisites:**",
        "- Python 3.10+",
        "- An active Mubu desktop session on this machine",
        "- Local Mubu profile data available to the CLI",
        "- Set `MUBU_DAILY_FOLDER` if you want no-argument daily helpers",
        "",
        "## Entry Points",
        "",
        "```bash",
        f"cli-anything-{metadata.software_name}",
        f"python -m cli_anything.{metadata.software_name}",
        "```",
        "",
        "When invoked without a subcommand, the CLI enters an interactive REPL session.",
        "",
        "## Command Groups",
        "",
    ]

    for group in metadata.command_groups:
        lines.extend([f"### {group.name}", "", group.description, ""])
        if group.commands:
            lines.extend(["| Command | Description |", "|---------|-------------|"])
            for command in group.commands:
                lines.append(f"| `{command.name}` | {command.description} |")
            lines.append("")

    lines.extend(
        [
            "## Recommended Agent Workflow",
            "",
            "```text",
            "discover daily-current '<daily-folder-ref>' --json",
            "        ->",
            "inspect daily-nodes '<daily-folder-ref>' --query '<anchor>' --json",
            "        ->",
            "session use-doc '<doc_path>'",
            "        ->",
            "mutate update-text / create-child / delete-node --json",
            "        ->",
            "--execute only after payload inspection",
            "```",
            "",
            "## Safety Rules",
            "",
            "1. Prefer grouped commands for agent use; flat legacy commands remain for compatibility.",
            "2. Use `--json` whenever an agent will parse the output.",
            "3. Prefer `discover` or `inspect` commands before any `mutate` command.",
            "4. Live mutations are dry-run by default and only execute with `--execute`.",
            "5. Prefer `--node-id` and `--parent-node-id` over text matching.",
            "6. `delete-node` removes the full targeted subtree.",
            "7. Even same-text updates can still advance document version history.",
            "8. Pass a daily-folder reference explicitly or set `MUBU_DAILY_FOLDER` before using no-arg daily helpers.",
            "",
            "## Examples",
            "",
        ]
    )
    for example in metadata.examples:
        lines.extend([f"### {example.title}", "", example.description, "", "```bash", example.code, "```", ""])
    lines.extend(
        [
            "## Session State",
            "",
            "The CLI maintains lightweight session state in JSON:",
            "",
            "- `current_doc`",
            "- `current_node`",
            "- local command history",
            "",
            "Use the `session` command group to inspect or update this state.",
            "",
            "## For AI Agents",
            "",
            "1. Start with `discover` or `inspect`, not `mutate`.",
            "2. Use `session status --json` to recover persisted context.",
            "3. Use grouped commands in generated prompts and automation.",
            "4. Verify postconditions after any live mutation.",
            "5. Read the package `TEST.md` and `README.md` when stricter operational detail is needed.",
            "",
            "## Version",
            "",
            metadata.version,
            "",
        ]
    )
    return "\n".join(lines)


def generate_skill_md(metadata: SkillMetadata, template_path: Optional[str] = None) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        return generate_skill_md_simple(metadata)

    if template_path is None:
        template_path = Path(__file__).parent / "templates" / "SKILL.md.template"
    else:
        template_path = Path(template_path)

    if not template_path.exists():
        return generate_skill_md_simple(metadata)

    env = Environment(loader=FileSystemLoader(template_path.parent))
    template = env.get_template(template_path.name)
    return template.render(
        skill_name=metadata.skill_name,
        skill_description=metadata.skill_description,
        software_name=metadata.software_name,
        skill_intro=metadata.skill_intro,
        version=metadata.version,
        system_package=metadata.system_package,
        command_groups=[
            {
                "name": group.name,
                "description": group.description,
                "commands": [{"name": command.name, "description": command.description} for command in group.commands],
            }
            for group in metadata.command_groups
        ],
        examples=[{"title": example.title, "description": example.description, "code": example.code} for example in metadata.examples],
    )


def generate_skill_file(harness_path: str, output_path: Optional[str] = None, template_path: Optional[str] = None) -> str:
    metadata = extract_cli_metadata(harness_path)
    content = generate_skill_md(metadata, template_path)
    harness_root = Path(harness_path)
    skill_id = f"cli-anything-{harness_root.parent.name.replace('_', '-')}"
    if output_path is None:
        output = harness_root.parent.parent / "skills" / skill_id / "SKILL.md"
    else:
        output = Path(output_path)
    mirror = harness_root / "cli_anything" / metadata.software_name / "skills" / "SKILL.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    if mirror != output:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(content, encoding="utf-8")
    return str(output)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate SKILL.md for CLI-Anything harnesses")
    parser.add_argument("harness_path", help="Path to the agent-harness directory")
    parser.add_argument("-o", "--output", help="Output path for SKILL.md", default=None)
    parser.add_argument("-t", "--template", help="Path to a custom Jinja2 template", default=None)
    args = parser.parse_args(argv)
    output_path = generate_skill_file(args.harness_path, output_path=args.output, template_path=args.template)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
