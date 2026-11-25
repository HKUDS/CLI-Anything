"""
SKILL.md Generator for CLI-Anything

This module extracts metadata from CLI-Anything harnesses and generates
SKILL.md files following the skill-creator methodology.

The generated SKILL.md files contain:
- YAML frontmatter with name and description (triggering metadata)
- Markdown body with usage instructions
- Command documentation
- Examples for AI agents
"""

import ast
import re
import shlex
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


API_REQUIREMENT = "Access to the service's API. See the harness README for the endpoint and any required credentials."


def _format_display_name(name: str) -> str:
    """Format software name for display (replace underscores/hyphens with spaces, then title)."""
    return name.replace("_", " ").replace("-", " ").title()


def _canonical_skill_name(harness_path: Path, software_name: str) -> str:
    """Return the repo-root canonical skill id for a harness."""
    software_dir = software_name
    if harness_path.name == "agent-harness" and harness_path.parent.name:
        software_dir = harness_path.parent.name
    return f"cli-anything-{software_dir.replace('_', '-')}"


def _click_decorator_info(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    kind: str,
    *,
    require_stable_names: bool = False,
) -> Optional[tuple[str, str | None]]:
    """Return the owner and declared name for a Click decorator."""
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if not (
            isinstance(target, ast.Attribute)
            and target.attr == kind
            and isinstance(target.value, ast.Name)
        ):
            continue

        name = None
        if isinstance(decorator, ast.Call):
            name = decorator.args[0] if decorator.args else next(
                (kw.value for kw in decorator.keywords if kw.arg == "name"), None
            )
        if isinstance(name, ast.Constant) and isinstance(name.value, str):
            return target.value.id, name.value

        default_name = function.name.replace("_", "-")
        if require_stable_names:
            if name is not None and not (isinstance(name, ast.Constant) and name.value is None):
                return target.value.id, None
            default_name = default_name.lower()
            # Click 8.2 began removing these suffixes from inferred names.
            if default_name.endswith(("-command", "-cmd", "-group", "-grp")):
                return target.value.id, None
        return target.value.id, default_name

    return None


def _function_docstring(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return a function docstring without changing its internal formatting."""
    docstring = ast.get_docstring(function, clean=False)
    if docstring:
        return docstring.strip()
    return ""


def _apply_click_group_registrations(
    tree: ast.Module, group_parents: dict[str, tuple[str, str | None]]
) -> None:
    """Apply direct, module-level add_command registrations of standalone groups."""
    for statement in tree.body:
        if not isinstance(statement, ast.Expr) or not isinstance(
            statement.value, ast.Call
        ):
            continue
        call = statement.value
        target = call.func
        if not (
            isinstance(target, ast.Attribute)
            and target.attr == "add_command"
            and isinstance(target.value, ast.Name)
            and call.args
            and isinstance(call.args[0], ast.Name)
        ):
            continue
        child = call.args[0].id
        if child not in group_parents or group_parents[child][0] != "click":
            continue
        alias = call.args[1] if len(call.args) > 1 else next(
            (kw.value for kw in call.keywords if kw.arg == "name"), None
        )
        if alias is None or (isinstance(alias, ast.Constant) and alias.value is None):
            name = group_parents[child][1]
        elif isinstance(alias, ast.Constant) and isinstance(alias.value, str):
            name = alias.value
        else:
            name = None
        group_parents[child] = (target.value.id, name)


def _requires_click_parameter(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in function.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in {"option", "argument"}
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == "click"
        ):
            continue
        required = next(
            (kw.value for kw in decorator.keywords if kw.arg == "required"), None
        )
        if required is None:
            if decorator.func.attr == "argument":
                return True
        elif not isinstance(required, ast.Constant) or required.value is not False:
            return True
    return False


@dataclass
class CommandInfo:
    """Information about a CLI command."""
    name: str
    description: str


@dataclass
class CommandGroup:
    """A group of related CLI commands."""
    name: str
    description: str
    commands: list[CommandInfo] = field(default_factory=list)
    path: Optional[tuple[str, ...]] = None
    required_ancestor_path: Optional[tuple[str, ...]] = None


@dataclass
class Example:
    """An example of CLI usage."""
    title: str
    description: str
    code: str


@dataclass
class SkillMetadata:
    """Metadata extracted from a CLI-Anything harness."""
    skill_name: str
    skill_description: str
    software_name: str
    skill_intro: str
    version: str
    system_package: Optional[str] = None
    command_groups: list[CommandGroup] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)
    api_backend: bool = False

    @property
    def command_name(self) -> str:
        return _api_command_name(self.software_name) if self.api_backend else f"cli-anything-{self.software_name}"


def extract_cli_metadata(harness_path: str, *, api_backend: bool = False) -> SkillMetadata:
    """
    Extract metadata from a CLI-Anything harness directory.

    Args:
        harness_path: Path to the agent-harness directory
        api_backend: Generate prerequisites and examples for a service API

    Returns:
        SkillMetadata containing extracted information
    """
    harness_path = Path(harness_path)

    # Find the cli_anything/<software> directory
    cli_anything_dir = harness_path / "cli_anything"
    if not cli_anything_dir.exists():
        raise ValueError(
            f"cli_anything directory not found in {harness_path}. "
            "Ensure the harness structure includes cli_anything/<software>/"
        )
    software_dirs = [d for d in cli_anything_dir.iterdir()
                     if d.is_dir() and (d / "__init__.py").exists()]

    if not software_dirs:
        raise ValueError(f"No CLI package found in {harness_path}")

    software_dir = software_dirs[0]
    software_name = software_dir.name

    # Extract metadata from README.md
    readme_path = software_dir / "README.md"
    skill_intro = ""
    system_package = None

    if readme_path.exists():
        readme_content = readme_path.read_text(encoding="utf-8")
        skill_intro = extract_intro_from_readme(readme_content)
        if not api_backend:
            system_package = extract_system_package(readme_content)

    # Extract version from setup.py
    setup_path = harness_path / "setup.py"
    version = "1.0.0"

    if setup_path.exists():
        version = extract_version_from_setup(setup_path)

    # Extract commands from CLI file
    cli_file = software_dir / f"{software_name}_cli.py"
    command_groups = []

    if cli_file.exists():
        command_groups = extract_commands_from_cli(
            cli_file, require_stable_names=api_backend
        )

    # Generate examples based on software type
    if api_backend:
        command_groups = [group for group in command_groups if group.path is not None and group.commands]
        examples = generate_api_examples(software_name, command_groups)
    else:
        examples = generate_examples(software_name, command_groups)

    # Build skill name and description
    skill_name = _canonical_skill_name(harness_path, software_name)
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
        api_backend=api_backend,
    )


def extract_intro_from_readme(content: str) -> str:
    """Extract introduction text from README content."""
    # Find the first paragraph after the title
    lines = content.split("\n")
    intro_lines = []
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

    return " ".join(intro_lines) or f"CLI interface for the software."


def extract_system_package(content: str) -> Optional[str]:
    """Extract system package installation command from README."""
    # Look for apt/brew install patterns
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
    """Extract version from setup.py."""
    content = setup_path.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return "1.0.0"


def extract_commands_from_cli(
    cli_path: Path, *, require_stable_names: bool = False
) -> list[CommandGroup]:
    """Extract command groups and commands from CLI file."""
    content = cli_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(cli_path))
    functions = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    groups = []

    group_lookup = {}
    group_display_paths = {}
    group_functions = [
        (function, decorator_info)
        for function in functions
        if (decorator_info := _click_decorator_info(
            function, "group", require_stable_names=require_stable_names
        ))
    ]
    group_parents = {
        function.name: decorator_info for function, decorator_info in group_functions
    }
    _apply_click_group_registrations(tree, group_parents)
    root_group_funcs = {
        name for name, (parent, _) in group_parents.items() if parent == "click"
    }
    required_groups = {
        function.name
        for function, _ in group_functions
        if _requires_click_parameter(function)
    }

    def resolve_paths(
        group_name: str, seen: frozenset[str] = frozenset()
    ) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
        if group_name in seen or group_name not in group_parents:
            return None, None
        parent, name = group_parents[group_name]
        if parent == "click":
            if len(root_group_funcs) != 1:
                return None, None
            path = ()
            required_path = None
        else:
            parent_path, required_path = resolve_paths(parent, seen | {group_name})
            if parent_path is None or not name:
                return None, None
            path = (*parent_path, name)
        if required_path is None and group_name in required_groups:
            required_path = path
        return path, required_path

    for function, (_, default_name) in group_functions:
        group_func = function.name
        group_doc = _function_docstring(function)
        group_parent, declared_name = group_parents[group_func]
        cli_path, required_path = resolve_paths(group_func)

        local_group_name = _format_display_name(
            declared_name or default_name or function.name
        )
        parent_key = group_parent.lower()
        if cli_path:
            group_path = [_format_display_name(part) for part in cli_path]
        elif parent_key == "click" or group_parent in root_group_funcs:
            group_path = [local_group_name]
        else:
            parent_path = group_display_paths.get(parent_key)
            if parent_path:
                group_path = [*parent_path, local_group_name]
            else:
                group_path = [_format_display_name(group_parent), local_group_name]

        group_name = " ".join(group_path)
        group = CommandGroup(
            name=group_name,
            description=group_doc or f"Commands for {group_name.lower()} operations.",
            commands=[],
            path=cli_path,
            required_ancestor_path=required_path,
        )
        groups.append(group)
        group_lookup[group_func.lower()] = group
        group_display_paths[group_func.lower()] = group_path

    command_functions = [
        (function, decorator_info)
        for function in functions
        if (decorator_info := _click_decorator_info(
            function, "command", require_stable_names=require_stable_names
        ))
    ]

    for function, (group_name, declared_name) in command_functions:
        cmd_func = function.name
        cmd_doc = _function_docstring(function)

        # Find the matching group
        group = group_lookup.get(group_name.lower())
        if group and declared_name:
            group.commands.append(CommandInfo(
                name=declared_name,
                description=cmd_doc or f"Execute {cmd_func} operation."
            ))

    # If no groups found, create a default one with all commands
    if not groups:
        default_group = CommandGroup(
            name="General",
            description="General commands for the CLI.",
            commands=[]
        )

        for function, (_, declared_name) in command_functions:
            cmd_func = function.name
            cmd_doc = _function_docstring(function)
            if declared_name:
                default_group.commands.append(CommandInfo(
                    name=declared_name,
                    description=cmd_doc or f"Execute {cmd_func} operation."
                ))

        if default_group.commands:
            groups.append(default_group)

    return groups


def _api_command_name(software_name: str) -> str:
    return f"cli-anything-{software_name.replace('_', '-')}"


def generate_api_examples(software_name: str, command_groups: list[CommandGroup]) -> list[Example]:
    """Show supported commands without guessing arguments or calling the API."""
    if not command_groups:
        return []
    group = next((item for item in command_groups if item.path), command_groups[0])
    path = group.required_ancestor_path
    if path is None:
        path = (*(group.path or ()), group.commands[0].name)
    command = shlex.join((_api_command_name(software_name), *path, "--help"))
    return [Example(
        title="Inspect Command Options",
        description="Check the accepted arguments before calling the API.",
        code=command,
    )]


def generate_examples(software_name: str, command_groups: list[CommandGroup]) -> list[Example]:
    """Generate usage examples based on software type and available commands."""
    examples = []

    # Basic project creation example
    examples.append(Example(
        title="Create a New Project",
        description=f"Create a new {software_name} project file.",
        code=f"""cli-anything-{software_name} project new -o myproject.json
# Or with JSON output for programmatic use
cli-anything-{software_name} --json project new -o myproject.json"""
    ))

    # REPL usage example
    examples.append(Example(
        title="Interactive REPL Session",
        description="Start an interactive session with undo/redo support.",
        code=f"""cli-anything-{software_name}
# Enter commands interactively
# Use 'help' to see available commands
# Use 'undo' and 'redo' for history navigation"""
    ))

    # Export example if export commands exist
    for group in command_groups:
        if "export" in group.name.lower():
            examples.append(Example(
                title="Export Project",
                description="Export the project to a final output format.",
                code=f"""cli-anything-{software_name} --project myproject.json export render output.pdf --overwrite"""
            ))
            break

    return examples


def generate_skill_md(metadata: SkillMetadata, template_path: Optional[str] = None) -> str:
    """
    Generate SKILL.md content from metadata using Jinja2 template.

    Args:
        metadata: SkillMetadata containing CLI information
        template_path: Optional path to custom template file

    Returns:
        Generated SKILL.md content as string
    """
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        # Fallback to simple string formatting if Jinja2 not available
        return generate_skill_md_simple(metadata)

    # Load template
    if template_path is None:
        template_path = Path(__file__).parent / "templates" / "SKILL.md.template"
    else:
        template_path = Path(template_path)

    if not template_path.exists():
        return generate_skill_md_simple(metadata)

    env = Environment(loader=FileSystemLoader(template_path.parent))
    template = env.get_template(template_path.name)

    # Render template
    return template.render(
        skill_name=metadata.skill_name,
        skill_description=metadata.skill_description,
        software_name=metadata.software_name,
        skill_intro=metadata.skill_intro,
        version=metadata.version,
        system_package=metadata.system_package,
        command_name=metadata.command_name,
        api_backend=metadata.api_backend,
        api_requirement=API_REQUIREMENT,
        command_groups=[{
            "name": g.name,
            "description": g.description,
            "commands": [{"name": c.name, "description": c.description} for c in g.commands]
        } for g in metadata.command_groups],
        examples=[{
            "title": e.title,
            "description": e.description,
            "code": e.code
        } for e in metadata.examples]
    )


def generate_skill_md_simple(metadata: SkillMetadata) -> str:
    """Generate SKILL.md without Jinja2 dependency."""
    lines = [
        "---",
        f'name: "{metadata.skill_name}"',
        f'description: "{metadata.skill_description}"',
        "---",
        "",
        f"# {metadata.skill_name}",
        "",
        metadata.skill_intro,
        "",
        "## Installation",
        "",
        f"This CLI is installed as part of the {metadata.command_name} package:",
        "",
        f"```bash",
        f"pip install {metadata.command_name}",
        f"```",
        "",
        "**Prerequisites:**",
        "- Python 3.10+",
    ]

    if metadata.api_backend:
        lines.append(f"- {API_REQUIREMENT}")
    else:
        lines.append(f"- {_format_display_name(metadata.software_name)} must be installed on your system")
        if metadata.system_package:
            lines.append(f"- Install {metadata.software_name}: `{metadata.system_package}`")

    lines.extend([
        "",
        "## Usage",
        "",
        "### Basic Commands",
        "",
        "```bash",
        "# Show help",
        f"{metadata.command_name} --help",
    ])
    if not metadata.api_backend:
        lines.extend([
            "",
            "# Start interactive REPL mode",
            f"cli-anything-{metadata.software_name}",
            "",
            "# Create a new project",
            f"cli-anything-{metadata.software_name} project new -o project.json",
            "",
            "# Run with JSON output (for agent consumption)",
            f"cli-anything-{metadata.software_name} --json project info -p project.json",
        ])
    lines.extend(["```", ""])

    # Add command groups
    if metadata.command_groups:
        lines.append("## Command Groups")
        lines.append("")

        for group in metadata.command_groups:
            lines.append(f"### {group.name}")
            lines.append("")
            lines.append(group.description)
            lines.append("")

            if group.commands:
                lines.append("| Command | Description |")
                lines.append("|---------|-------------|")
                for cmd in group.commands:
                    lines.append(f"| `{cmd.name}` | {cmd.description} |")
                lines.append("")

    # Add examples
    if metadata.examples:
        lines.append("## Examples")
        lines.append("")

        for example in metadata.examples:
            lines.append(f"### {example.title}")
            lines.append("")
            lines.append(example.description)
            lines.append("")
            lines.append("```bash")
            lines.append(example.code)
            lines.append("```")
            lines.append("")

    # Add AI agent guidance
    lines.extend([
        "## For AI Agents",
        "",
        "When using this CLI programmatically:",
        "",
        "1. **Always use `--json` flag** for parseable output",
        "2. **Check return codes** - 0 for success, non-zero for errors",
        "3. **Parse stderr** for error messages on failure",
        "4. **Use absolute paths** for all file operations",
        "5. **Verify outputs exist** after export operations",
        "",
        "## Version",
        "",
        metadata.version,
    ])

    return "\n".join(lines)


def generate_skill_file(harness_path: str, output_path: Optional[str] = None,
                        template_path: Optional[str] = None, *,
                        api_backend: bool = False) -> str:
    """
    Generate a SKILL.md file for a CLI-Anything harness.

    Args:
        harness_path: Path to the agent-harness directory
        output_path: Optional output path for SKILL.md
                     (default: skills/cli-anything-<software>/SKILL.md)
        template_path: Optional path to custom Jinja2 template
        api_backend: Generate prerequisites and examples for a service API

    Returns:
        Path to the generated SKILL.md file
    """
    # Extract metadata
    metadata = extract_cli_metadata(harness_path, api_backend=api_backend)

    # Generate content
    content = generate_skill_md(metadata, template_path)

    # Determine output path
    harness_path_obj = Path(harness_path)
    compatibility_path = harness_path_obj / "cli_anything" / metadata.software_name / "skills" / "SKILL.md"
    if output_path is None:
        repo_root = harness_path_obj.parent.parent
        output_path = repo_root / "skills" / metadata.skill_name / "SKILL.md"
    else:
        output_path = Path(output_path)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    output_path.write_text(content, encoding="utf-8")
    if compatibility_path != output_path:
        compatibility_path.parent.mkdir(parents=True, exist_ok=True)
        compatibility_path.write_text(content, encoding="utf-8")

    return str(output_path)


# CLI interface for standalone usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate SKILL.md for CLI-Anything harnesses"
    )
    parser.add_argument(
        "harness_path",
        help="Path to the agent-harness directory"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output path for SKILL.md (default: skills/cli-anything-<software>/SKILL.md)",
        default=None
    )
    parser.add_argument(
        "-t", "--template",
        help="Path to custom Jinja2 template",
        default=None
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Generate usage and prerequisites for an API-backed harness.",
    )

    args = parser.parse_args()

    output_file = generate_skill_file(
        args.harness_path,
        args.output,
        args.template,
        api_backend=args.api,
    )

    print(f"Generated: {output_file}")
