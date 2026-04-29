"""
SKILL.md Generator for CLI-Anything harnesses.
"""

from __future__ import annotations

import argparse
import ast
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
    important_constraints: list[str] = field(default_factory=list)
    command_groups: list[CommandGroup] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)


def extract_intro_from_readme(content: str) -> str:
    lines = content.splitlines()
    intro: list[str] = []
    seen_title = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if seen_title and intro:
                break
            continue
        if stripped.startswith("# "):
            seen_title = True
            continue
        if stripped.startswith("##"):
            break
        if seen_title:
            intro.append(stripped)
    return " ".join(intro) or "Agent-native CLI interface."


def extract_version_from_setup(setup_path: Path) -> str:
    content = setup_path.read_text(encoding="utf-8")
    match = re.search(r'PACKAGE_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    return match.group(1) if match else "1.0.0"


def _string_literal(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _click_decorator_info(decorator: ast.AST) -> tuple[str | None, str | None, str | None]:
    target: ast.AST
    explicit_name: str | None = None
    if isinstance(decorator, ast.Call):
        target = decorator.func
        if decorator.args:
            explicit_name = _string_literal(decorator.args[0])
        if explicit_name is None:
            for keyword in decorator.keywords:
                if keyword.arg == "name":
                    explicit_name = _string_literal(keyword.value)
                    break
    else:
        target = decorator
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        return target.value.id, target.attr, explicit_name
    return None, None, explicit_name


def _default_group_name(function_name: str) -> str:
    return re.sub(r"_group$", "", function_name).replace("_", " ")


def _default_command_name(function_name: str) -> str:
    return re.sub(r"_command$", "", function_name).replace("_", "-")


def extract_commands_from_cli(cli_path: Path) -> list[CommandGroup]:
    module = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
    groups: list[CommandGroup] = []
    group_name_by_function: dict[str, str] = {}
    group_by_display_name: dict[str, CommandGroup] = {}
    functions = [node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

    for node in functions:
        for decorator in node.decorator_list:
            owner_name, decorator_name, explicit_name = _click_decorator_info(decorator)
            if owner_name != "cli" or decorator_name != "group":
                continue
            raw_name = explicit_name or _default_group_name(node.name)
            display_name = raw_name.replace("-", " ").title()
            group = CommandGroup(
                name=display_name,
                description=ast.get_docstring(node) or f"Commands for {raw_name}.",
            )
            group_name_by_function[node.name] = display_name
            group_by_display_name[display_name] = group
            groups.append(group)
            break

    for node in functions:
        for decorator in node.decorator_list:
            owner_name, decorator_name, explicit_name = _click_decorator_info(decorator)
            if decorator_name != "command" or owner_name not in group_name_by_function:
                continue
            display_name = group_name_by_function[owner_name]
            cmd_name = explicit_name or _default_command_name(node.name)
            group_by_display_name[display_name].commands.append(
                CommandInfo(cmd_name, ast.get_docstring(node) or f"Execute `{cmd_name}`.")
            )
            break
    return groups


def generate_examples(software_name: str) -> list[Example]:
    return [
        Example("Runtime Status", "Inspect Zotero paths and backend availability.", f"cli-anything-{software_name} app status --json"),
        Example("Read Selected Collection", "Persist the collection selected in the Zotero GUI.", f"cli-anything-{software_name} collection use-selected --json"),
        Example("Render Citation", "Render a citation using Zotero's Local API.", f"cli-anything-{software_name} item citation <item-key> --style apa --locale en-US --json"),
        Example("Add Child Note", "Create a child note under an existing Zotero item.", f"cli-anything-{software_name} note add <item-key> --text \"Key takeaway\" --json"),
        Example("Build LLM Context", "Assemble structured context for downstream model analysis.", f"cli-anything-{software_name} item context <item-key> --include-notes --include-links --json"),
    ]


def generate_important_constraints(software_name: str) -> list[str]:
    if software_name != "zotero":
        return []
    return [
        "`search items`, `item export`, `item citation`, and `item bibliography` require Zotero's Local API to be enabled.",
        "`note add` depends on the live Zotero GUI context and expects the same library to be selected in the app.",
        "Import-time PDF attachment support is limited to items created in the same connector session; arbitrary existing-item attachment upload is still out of scope.",
        "Experimental SQLite write commands are local-only, user-library-only, and should be treated as non-stable power-user operations.",
        "If a bare key is duplicated across libraries, set `session use-library <id>` before follow-up commands.",
    ]


def extract_cli_metadata(harness_path: str) -> SkillMetadata:
    harness_root = Path(harness_path)
    cli_root = harness_root / "cli_anything"
    software_dir = next(path for path in cli_root.iterdir() if path.is_dir() and (path / "__init__.py").exists())
    software_name = software_dir.name
    intro = extract_intro_from_readme((software_dir / "README.md").read_text(encoding="utf-8"))
    version = extract_version_from_setup(harness_root / "setup.py")
    groups = extract_commands_from_cli(software_dir / f"{software_name}_cli.py")
    return SkillMetadata(
        skill_name=f"cli-anything-{software_name}",
        skill_description=f"CLI harness for {_format_display_name(software_name)}.",
        software_name=software_name,
        skill_intro=intro,
        version=version,
        important_constraints=generate_important_constraints(software_name),
        command_groups=groups,
        examples=generate_examples(software_name),
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
        "```bash",
        "pip install -e .",
        "```",
        "",
        "## Entry Points",
        "",
        "```bash",
        f"cli-anything-{metadata.software_name}",
        f"python -m cli_anything.{metadata.software_name}",
        "```",
        "",
    ]
    if metadata.important_constraints:
        lines.extend(["## Important Constraints", ""])
        for constraint in metadata.important_constraints:
            lines.append(f"- {constraint}")
        lines.append("")
    lines.extend(["## Command Groups", ""])
    for group in metadata.command_groups:
        lines.extend([f"### {group.name}", "", group.description, "", "| Command | Description |", "|---------|-------------|"])
        for cmd in group.commands:
            lines.append(f"| `{cmd.name}` | {cmd.description} |")
        lines.append("")
    lines.extend(["## Examples", ""])
    for example in metadata.examples:
        lines.extend([f"### {example.title}", "", example.description, "", "```bash", example.code, "```", ""])
    lines.extend(["## Version", "", metadata.version, ""])
    return _normalize_generated_markdown("\n".join(lines))


def _normalize_generated_markdown(content: str) -> str:
    content = re.sub(r"(\|\s*\n)(#{2,3}\s)", r"\1\n\2", content)
    content = re.sub(r"(```\n)(#{2,3}\s)", r"\1\n\2", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip() + "\n"


def generate_skill_md(metadata: SkillMetadata, template_path: Optional[str] = None) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        return generate_skill_md_simple(metadata)

    template = Path(template_path) if template_path else Path(__file__).parent / "templates" / "SKILL.md.template"
    if not template.exists():
        return generate_skill_md_simple(metadata)
    env = Environment(loader=FileSystemLoader(template.parent), trim_blocks=True, lstrip_blocks=True)
    tpl = env.get_template(template.name)
    rendered = tpl.render(
        skill_name=metadata.skill_name,
        skill_description=metadata.skill_description,
        software_name=metadata.software_name,
        skill_intro=metadata.skill_intro,
        version=metadata.version,
        important_constraints=metadata.important_constraints,
        command_groups=[
            {"name": group.name, "description": group.description, "commands": [{"name": c.name, "description": c.description} for c in group.commands]}
            for group in metadata.command_groups
        ],
        examples=[{"title": ex.title, "description": ex.description, "code": ex.code} for ex in metadata.examples],
    )
    return _normalize_generated_markdown(rendered)


def generate_skill_file(harness_path: str, output_path: Optional[str] = None, template_path: Optional[str] = None) -> str:
    metadata = extract_cli_metadata(harness_path)
    content = generate_skill_md(metadata, template_path=template_path)
    harness_root = Path(harness_path)
    skill_id = f"cli-anything-{harness_root.parent.name.replace('_', '-')}"
    output = Path(output_path) if output_path else harness_root.parent.parent / "skills" / skill_id / "SKILL.md"
    mirror = harness_root / "cli_anything" / metadata.software_name / "skills" / "SKILL.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    if mirror != output:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(content, encoding="utf-8")
    return str(output)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate SKILL.md for a CLI-Anything harness")
    parser.add_argument("harness_path")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-t", "--template", default=None)
    args = parser.parse_args(argv)
    print(generate_skill_file(args.harness_path, output_path=args.output, template_path=args.template))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
