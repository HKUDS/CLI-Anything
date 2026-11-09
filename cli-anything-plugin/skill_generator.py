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
import json
import re
import shlex
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


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
) -> Optional[tuple[str, str]]:
    """Return the owner and declared name for a Click decorator."""
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if not (
            isinstance(target, ast.Attribute)
            and target.attr == kind
            and isinstance(target.value, ast.Name)
        ):
            continue

        declared_name = None
        if isinstance(decorator, ast.Call):
            if decorator.args:
                first_arg = decorator.args[0]
                if (
                    isinstance(first_arg, ast.Constant)
                    and isinstance(first_arg.value, str)
                ):
                    declared_name = first_arg.value
                elif not (isinstance(first_arg, ast.Constant) and first_arg.value is None):
                    return None  # Computed command names cannot be inferred safely.
            if declared_name is None:
                for keyword in decorator.keywords:
                    if (
                        keyword.arg == "name"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        declared_name = keyword.value.value
                        break
                    if keyword.arg == "name" and not (
                        isinstance(keyword.value, ast.Constant) and keyword.value.value is None
                    ):
                        return None

        return target.value.id, declared_name or function.name.replace("_", "-")

    return None


def _function_docstring(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return a function docstring without changing its internal formatting."""
    docstring = ast.get_docstring(function, clean=False)
    if docstring:
        return docstring.strip()
    return ""


@dataclass
class CommandInfo:
    """Information about a CLI command."""
    name: str
    description: str
    path: Optional[tuple[str, ...]] = None


@dataclass
class CommandGroup:
    """A group of related CLI commands."""
    name: str
    description: str
    commands: list[CommandInfo] = field(default_factory=list)
    path: tuple[str, ...] = ()


@dataclass
class BackendInfo:
    """Declarative backend requirements; never contains credential values."""
    type: str = "unknown"
    base_url_env: Optional[str] = None
    auth_env: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)


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
    backend: BackendInfo = field(default_factory=BackendInfo)
    entry_point: Optional[str] = None


def extract_backend_metadata(harness_path: Path) -> BackendInfo:
    """Read optional versioned harness.json without consulting the environment."""
    path = harness_path / "harness.json"
    if not path.exists():
        return BackendInfo()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid harness.json: {exc}") from exc
    if not isinstance(data, dict) or set(data) - {"schema_version", "backend"}:
        raise ValueError("harness.json must contain schema_version and backend only")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("harness.json schema_version must be 1")
    backend = data.get("backend")
    fields = {"type", "base_url_env", "auth_env", "requirements"}
    if not isinstance(backend, dict) or set(backend) - fields:
        raise ValueError("Invalid harness.json backend fields")
    if backend.get("type") not in ("local", "api", "mcp"):
        raise ValueError("harness.json backend.type must be local, api, or mcp")
    for key in ("auth_env", "requirements"):
        values = backend.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip()
            or any(ord(char) < 32 for char in value) for value in values
        ):
            raise ValueError(f"harness.json backend.{key} must be a list of nonempty single-line strings")
    base_url_env = backend.get("base_url_env")
    env_names = list(backend.get("auth_env", []))
    if "base_url_env" in backend:
        env_names.append(base_url_env)
    if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in env_names):
        raise ValueError("harness.json environment fields must contain variable names, not values")
    return BackendInfo(**backend)


def _extract_entry_point(setup_path: Path, software_dir: Path):
    """Read literal setuptools console_scripts; never execute setup.py."""
    if not setup_path.exists():
        return None
    try:
        tree = ast.parse(setup_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "entry_points":
            continue
        try:
            entry_points = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        scripts = entry_points.get("console_scripts", []) if isinstance(entry_points, dict) else []
        if not isinstance(scripts, list):
            continue
        for script in scripts:
            if not isinstance(script, str):
                continue
            match = re.fullmatch(r"\s*([\w.-]+)\s*=\s*([\w.]+):([\w]+)\s*", script)
            if not match:
                continue
            name, module, function = match.groups()
            package_name = f"cli_anything.{software_dir.name}"
            if module != package_name and not module.startswith(package_name + "."):
                continue
            relative = module[len(package_name) + 1:].split(".")
            path = (software_dir / "__init__.py" if module == package_name
                    else software_dir.joinpath(*relative).with_suffix(".py"))
            if path.is_file() and path.resolve().is_relative_to(software_dir.resolve()):
                candidates.append((name, path, function))
    expected = f"cli-anything-{software_dir.name.replace('_', '-')}"
    preferred = [item for item in candidates if item[0] == expected]
    candidates = preferred or candidates
    if len(candidates) > 1:
        raise ValueError("Multiple console scripts match the harness; use one canonical cli-anything entry point")
    return candidates[0] if candidates else None


def extract_cli_metadata(harness_path: str) -> SkillMetadata:
    """
    Extract metadata from a CLI-Anything harness directory.

    Args:
        harness_path: Path to the agent-harness directory

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
    software_dirs = sorted(d for d in cli_anything_dir.iterdir()
                           if d.is_dir() and (d / "__init__.py").exists())

    if not software_dirs:
        raise ValueError(f"No CLI package found in {harness_path}")
    if len(software_dirs) > 1:
        raise ValueError(f"Multiple CLI packages found in {harness_path}")

    software_dir = software_dirs[0]
    software_name = software_dir.name

    # Extract metadata from README.md
    readme_path = software_dir / "README.md"
    if not readme_path.exists():
        readme_path = harness_path / "README.md"
    skill_intro = ""
    system_package = None

    if readme_path.exists():
        readme_content = readme_path.read_text(encoding="utf-8")
        skill_intro = extract_intro_from_readme(readme_content)
        system_package = extract_system_package(readme_content)

    # Extract version from setup.py
    setup_path = harness_path / "setup.py"
    version = "1.0.0"

    if setup_path.exists():
        version = extract_version_from_setup(setup_path)

    backend = extract_backend_metadata(harness_path)
    if backend.type == "unknown" and system_package:
        backend.type = "local"

    # Prefer the actual console-script module over filename conventions.
    cli_file = software_dir / f"{software_name}_cli.py"
    if not cli_file.exists():
        cli_file = software_dir / "cli.py"
    entry_point = f"cli-anything-{software_name.replace('_', '-')}"
    root_function = None
    declared_entry = _extract_entry_point(setup_path, software_dir)
    if declared_entry:
        entry_point, cli_file, root_function = declared_entry
    command_groups = []

    if cli_file.exists():
        command_groups = extract_commands_from_cli(cli_file, root_function)

    # Generate help examples from discovered command paths.
    examples = generate_examples(software_name, command_groups, entry_point)

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
        backend=backend,
        entry_point=entry_point,
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


def extract_commands_from_cli(cli_path: Path, root_function: Optional[str] = None) -> list[CommandGroup]:
    """Read reachable Click commands, including local imports and add_command.

    This is static analysis: no target modules, decorators, or setup code run.
    Dynamic registration/factories require manual documentation.
    """
    cli_path = cli_path.resolve()
    namespace = next((p for p in cli_path.parents if p.name == "cli_anything"), None)
    source_root = namespace.parent if namespace else cli_path.parent
    modules = {}

    def module_file(base, parts):
        candidate = base.joinpath(*parts)
        for path in (candidate.with_suffix(".py"), candidate / "__init__.py"):
            if path.is_file() and path.resolve().is_relative_to(source_root):
                return path.resolve()
        return None

    def load(path):
        if path in modules:
            return modules[path]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = {
            node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        imports = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                base = path.parent if node.level else source_root
                for _ in range(max(0, node.level - 1)):
                    base = base.parent
                parts = node.module.split(".") if node.module else []
                imported_module = module_file(base, parts) if parts else None
                for alias in node.names:
                    key = alias.asname or alias.name
                    if imported_module:
                        imports[key] = (imported_module, alias.name)
                    else:
                        imported = module_file(base, [*parts, alias.name])
                        if imported:
                            imports[key] = (imported, None)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported = module_file(source_root, alias.name.split("."))
                    if imported:
                        imports[alias.asname or alias.name] = (imported, None)
        modules[path] = (tree, functions, imports)
        return modules[path]

    def resolve_symbol(path, parts, seen=frozenset()):
        key = (path, tuple(parts))
        if key in seen or not parts:
            return None
        _, functions, imports = load(path)
        if len(parts) == 1 and parts[0] in functions:
            return path, parts[0]
        for length in range(len(parts), 0, -1):
            imported = imports.get(".".join(parts[:length]))
            if imported:
                other, name = imported
                return resolve_symbol(other, ([name] if name else []) + parts[length:], seen | {key})
        if path.name == "__init__.py" and len(parts) > 1:
            submodule = module_file(path.parent, [parts[0]])
            if submodule:
                return resolve_symbol(submodule, parts[1:], seen | {key})
        return None

    def expression_parts(expr):
        if isinstance(expr, ast.Name):
            return [expr.id]
        if isinstance(expr, ast.Attribute):
            return [*expression_parts(expr.value), expr.attr]
        return []

    def definition(key):
        function = load(key[0])[1][key[1]]
        for kind in ("group", "command"):
            info = _click_decorator_info(function, kind)
            if info:
                return function, kind, info[1]
        return None

    def hidden(function):
        return any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in ("command", "group")
            and any(keyword.arg == "hidden" and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True for keyword in decorator.keywords)
            for decorator in function.decorator_list
        )

    def children(key):
        path, name = key
        _, functions, _ = load(path)
        result = []
        # Decorator-attached children live in their owner's module.
        for function in functions.values():
            info = _click_decorator_info(function, "group") or _click_decorator_info(function, "command")
            if info and info[0] == name:
                result.append((0, function.lineno, (path, function.name), info[1]))
        # Explicit registrations can attach standalone groups or commands.
        # Inspect already-reached modules as registrations can live in the entry module.
        for owner_path, (owner_tree, _, _) in list(modules.items()):
            for stmt in owner_tree.body:
                node = stmt.value if isinstance(stmt, ast.Expr) else None
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "add_command" and node.args):
                    continue
                owner = resolve_symbol(owner_path, expression_parts(node.func.value))
                if owner != key:
                    continue
                child = resolve_symbol(owner_path, expression_parts(node.args[0]))
                child_info = definition(child) if child else None
                if not child_info:
                    continue
                alias = node.args[1] if len(node.args) > 1 else next(
                    (kw.value for kw in node.keywords if kw.arg == "name"), None)
                if alias is not None and not (isinstance(alias, ast.Constant) and isinstance(alias.value, str)):
                    continue
                result.append((0 if owner_path == path else 1, node.lineno, child,
                               alias.value if alias is not None else child_info[2]))
        return [(child, name) for _, _, child, name in sorted(result, key=lambda item: item[:2])]

    _, functions, _ = load(cli_path)
    root = resolve_symbol(cli_path, [root_function]) if root_function else None
    if root is None or definition(root) is None:
        root = next(((cli_path, name) for name in ("cli", "main")
                     if name in functions and _click_decorator_info(functions[name], "group")), None)
    if root is None:
        roots = [(cli_path, name) for name, fn in functions.items()
                 if (info := _click_decorator_info(fn, "group")) and info[0] == "click"]
        root = roots[0] if len(roots) == 1 else None
    if root is None:
        # A standalone Click command is the executable, not its own subcommand.
        roots = [(cli_path, name) for name, fn in functions.items()
                 if (info := _click_decorator_info(fn, "command")) and info[0] == "click"]
        root = roots[0] if len(roots) == 1 else None
    if root is None:
        return []

    groups = []

    def visit(key, path, ancestors=frozenset()):
        if key in ancestors:
            return
        info = definition(key)
        if not info:
            return
        function, kind, declared_name = info
        if hidden(function):
            return
        if kind == "command":
            groups.append(CommandGroup("General", "General commands for the CLI.", [
                CommandInfo(declared_name, _function_docstring(function), path)
            ]))
            return
        title = " ".join(_format_display_name(part) for part in path) or _format_display_name(declared_name)
        group = CommandGroup(title, _function_docstring(function) or f"Commands for {title.lower()} operations.", path=path)
        groups.append(group)
        registered = {}
        for child, child_name in children(key):
            registered[child_name] = child  # Match Click's last registration for a name.
        for child_name, child in registered.items():
            child_info = definition(child)
            if not child_info or hidden(child_info[0]):
                continue
            child_path = (*path, child_name)
            if child_info[1] == "group":
                visit(child, child_path, ancestors | {key})
            else:
                group.commands.append(CommandInfo(
                    child_name, _function_docstring(child_info[0]) or f"Execute {child_name} operation.", child_path))

    visit(root, ())
    return groups


def generate_examples(software_name: str, command_groups: list[CommandGroup],
                      entry_point: Optional[str] = None) -> list[Example]:
    """Use discovered command paths without inventing arguments or running writes."""
    entry = entry_point or f"cli-anything-{software_name.replace('_', '-')}"
    examples = [Example("Discover Commands", "Inspect available commands and options.",
                        f"{shlex.quote(entry)} --help")]
    for group in command_groups:
        if not group.commands:
            continue
        commands = [shlex.join([
            entry, *(command.path if command.path is not None else (*group.path, command.name)), "--help"
        ]) for command in group.commands]
        examples.append(Example(
            f"Explore {group.name}",
            "Inspect each command's required arguments, output flags, and side effects before invoking it.",
            "\n".join(commands),
        ))
    return examples


def _prerequisites(metadata: SkillMetadata) -> list[str]:
    backend = metadata.backend
    lines = ["Python 3.10+"]
    if backend.type == "local":
        lines.append(f"{_format_display_name(metadata.software_name)} must be installed on your system")
        if metadata.system_package:
            lines.append(f"Install {metadata.software_name}: `{metadata.system_package}`")
    elif backend.type == "api":
        lines.append("Network access to the vendor's public API; no local application binary is required")
    elif backend.type == "mcp":
        lines.append("A configured, reachable MCP server (see the package README)")
    else:
        lines.append("Configure the backend requirements documented in the package README")
    if backend.base_url_env:
        lines.append(f"Configure the service base URL with `{backend.base_url_env}`")
    for name in backend.auth_env:
        lines.append(f"Provide credentials through `{name}`; never include credential values in this file")
    lines.extend(backend.requirements)
    return lines


def _command_rows(metadata: SkillMetadata):
    """Share table escaping and full invocation paths between both renderers."""
    def cell(text):
        return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    def command_name(command):
        if command.path is None:
            return command.name
        return " ".join(command.path) or metadata.entry_point or f"cli-anything-{metadata.software_name.replace('_', '-')}"
    return [{
        "name": group.name, "description": group.description,
        "commands": [{"name": cell(command_name(command)),
                      "description": cell(command.description)} for command in group.commands],
    } for group in metadata.command_groups if group.commands]


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
        command_groups=_command_rows(metadata),
        entry_point=metadata.entry_point or f"cli-anything-{metadata.software_name.replace('_', '-')}",
        prerequisites=_prerequisites(metadata),
        backend_type=metadata.backend.type,
        examples=[{
            "title": e.title,
            "description": e.description,
            "code": e.code
        } for e in metadata.examples]
    )


def generate_skill_md_simple(metadata: SkillMetadata) -> str:
    """Generate the same backend/command guidance without Jinja2."""
    entry = metadata.entry_point or f"cli-anything-{metadata.software_name.replace('_', '-')}"
    lines = [
        "---",
        f"name: {json.dumps(metadata.skill_name, ensure_ascii=False)}",
        f"description: {json.dumps(metadata.skill_description, ensure_ascii=False)}",
        "---", "", f"# {metadata.skill_name}", "", metadata.skill_intro, "",
        "## Installation", "",
        f"This CLI is installed as part of the cli-anything-{metadata.software_name} package:", "",
        "```bash", f"pip install cli-anything-{metadata.software_name}", "```", "",
        "**Prerequisites:**",
        *[f"- {line}" for line in _prerequisites(metadata)], "",
        "## Usage", "", "Inspect the CLI before choosing an operation:", "",
        "```bash", f"{shlex.quote(entry)} --help", "```", "",
    ]
    groups = _command_rows(metadata)
    if groups:
        lines.extend(["## Command Groups", ""])
        for group in groups:
            lines.extend([f"### {group['name']}", "", group["description"], "",
                          "| Command | Description |", "|---------|-------------|"])
            for command in group["commands"]:
                lines.append(f"| `{command['name']}` | {command['description']} |")
            lines.append("")
    else:
        lines.extend(["No statically discoverable commands. Use `--help` and the package README; "
                      "dynamic registrations require manual documentation.", ""])
    if metadata.examples:
        lines.extend(["## Examples", ""])
        for example in metadata.examples:
            lines.extend([f"### {example.title}", "", example.description, "",
                          "```bash", example.code, "```", ""])
    lines.extend([
        "## For AI Agents", "",
        "1. Use the output flags shown by command help (normally `--json`) for parseable output.",
        "2. Check return codes: 0 for success, non-zero for errors; inspect stderr on failure.",
        "3. Follow command help for required arguments and mutation opt-in; run only requested writes.",
        "4. Use absolute paths for file operations and verify exported files, not just exit status.",
    ])
    if metadata.backend.type == "api":
        lines.append("5. Keep credentials out of logs and artifacts; poll remote jobs to completion before verifying downloads.")
    lines.extend(["", "## Version", "", metadata.version])
    return "\n".join(lines)


def generate_skill_file(harness_path: str, output_path: Optional[str] = None,
                        template_path: Optional[str] = None) -> str:
    """
    Generate a SKILL.md file for a CLI-Anything harness.

    Args:
        harness_path: Path to the agent-harness directory
        output_path: Optional output path for SKILL.md
                     (default: skills/cli-anything-<software>/SKILL.md)
        template_path: Optional path to custom Jinja2 template

    Returns:
        Path to the generated SKILL.md file
    """
    # Extract metadata
    metadata = extract_cli_metadata(harness_path)

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

    args = parser.parse_args()

    output_file = generate_skill_file(
        args.harness_path,
        args.output,
        args.template
    )

    print(f"Generated: {output_file}")
