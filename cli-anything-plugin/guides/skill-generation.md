# SKILL.md Generation (Phase 6.5)

Generate a SKILL.md file that makes the CLI discoverable and usable by AI agents
through the skill-creator methodology. This file serves as a self-contained skill
definition that can be loaded by Claude Code or other AI assistants.

## Purpose

SKILL.md files follow a standard format that enables AI agents to:
- Discover the CLI's capabilities
- Understand command structure and usage
- Generate correct command invocations
- Handle output programmatically

## SKILL.md Structure

### 1. YAML Frontmatter — Triggering metadata for skill discovery:

```yaml
---
name: "cli-anything-<software>"
description: "Brief description of what the CLI does"
---
```

### 2. Markdown Body — Usage instructions including:

- Installation prerequisites
- Basic command syntax
- Command groups and their functions
- Usage examples
- Agent-specific guidance (JSON output, error handling)

## Generation Process

### 1. Extract CLI metadata using `skill_generator.py`:

```python
from skill_generator import generate_skill_file

skill_path = generate_skill_file(
    harness_path="/path/to/agent-harness"
)
# Default output: skills/cli-anything-<software>/SKILL.md
```

### 2. The generator automatically extracts:

- Version and literal `console_scripts` entry points from setup.py (without executing it)
- Reachable Click groups, nested command paths, and literal `add_command` registrations,
  including imports/re-exports inside the harness source tree
- Documentation from the package README.md, falling back to the harness README.md
- Backend requirements from optional `harness.json` and known local install instructions
- Help examples for discovered commands, without assuming project, REPL, or undo support

## Backend Metadata

Create `agent-harness/harness.json` alongside `setup.py` when backend requirements
cannot be derived from local installation instructions:

```json
{
  "schema_version": 1,
  "backend": {
    "type": "api",
    "base_url_env": "SERVICE_BASE_URL",
    "auth_env": ["SERVICE_API_TOKEN"],
    "requirements": ["An account with access to the public API"]
  }
}
```

`schema_version` must be integer `1`; `backend.type` is `local`, `api`, or `mcp`.
`base_url_env` is optional, and `auth_env` and `requirements` default to empty
lists. Environment fields accept variable **names**, never URLs or credential
values. `requirements` contains nonempty single-line descriptions. Unknown
fields and malformed metadata fail generation before skill files are written.
Only declare configuration that the backend actually implements.

The API variant documents service access and declared credentials instead of a
local application install. The MCP variant documents a configured reachable
server. The local variant preserves the application/install requirements.
Without metadata, an extracted apt/brew instruction indicates a local backend;
otherwise the generator directs readers to the README without guessing a
dependency. Metadata is build-time input for skill generation, not a runtime
configuration or credential store.

## Command Discovery and Examples

The generator reads the literal `entry_points={"console_scripts": [...]}` mapping
in `setup.py` to select the executable, module, and Click root. Without a usable
literal entry, it falls back to `<software>_cli.py`, then `cli.py`. A wrapper
`main()` can coexist with a decorated `cli()` root. Modules are parsed as Python
syntax; `setup.py`, imports, decorators, and command bodies are never executed.

Supported forms include `@click.group`, `@group.command`, nested decorated
groups, and module-level `group.add_command(command, name="alias")`. Imported
groups can use relative or package-qualified imports and local re-exports.
Registrations retain exact CLI aliases and full command paths. Hidden commands
are omitted, cycles terminate, and unattached groups are not advertised as part
of the root CLI. Multiple packages or ambiguous console scripts are rejected.

Factory-built commands, runtime registration loops, third-party plugins, imported
decorator aliases, and dynamically computed names/entry points require manual
documentation. When no supported commands are found, the output reports the
discovery gap instead of rendering an empty command table. Always review the
generated reference against the installed CLI's `--help`.

Generated examples show `<actual-command-path> --help`. They avoid guessing
required arguments, flags, remote side effects, output paths, or an undo history.
After inspecting help, add verified workflow examples for the particular
harness. Both Jinja2 and the dependency-free renderer use the same backend
prerequisites and command paths. Existing custom templates continue receiving
the original fields, plus `entry_point`, `prerequisites`, and `backend_type`.

### 3. Customize the template (optional):

- Default template: `templates/SKILL.md.template`
- Uses Jinja2 placeholders for dynamic content
- Can be extended for software-specific sections

## Output Location

SKILL.md is generated canonically at the repo root, with a packaged compatibility
copy for installed harnesses:

```
skills/
└── cli-anything-<software>/
    └── SKILL.md

<software>/
└── agent-harness/
    └── cli_anything/
        └── <software>/
            └── skills/
                └── SKILL.md
```

## Manual Generation

```bash
cd cli-anything-plugin
python skill_generator.py /path/to/software/agent-harness
```

## Integration with CLI Build

The SKILL.md generation should be run after Phase 6 (Test Documentation) completes
successfully, ensuring the CLI is fully documented and tested before creating the
skill definition.

## Key Principles

- SKILL.md must be self-contained (no external dependencies for understanding)
- Include agent-specific guidance for programmatic usage
- Document `--json` flag usage for machine-readable output
- List all command groups with brief descriptions
- Provide realistic examples that demonstrate common workflows

## Preview-Capable Harnesses

If the harness supports previews, the generated or edited `SKILL.md` should
include a dedicated preview section that covers:

- the producer command surface: `cli-anything-<software> preview ...`
- the consumer command surface: `cli-hub previews ...`
- whether `preview diff`, `preview live ...`, or poll mode exist
- how agents should use `--json` results and artifact paths
- at least one publish example and one inspect/watch example

For the full preview methodology, see
[`preview-methodology.md`](preview-methodology.md).

## Skill Path in CLI Banner

ReplSkin prefers the repo-root canonical skill file and falls back to the
packaged copy, displaying whichever absolute path is available in the startup
banner. AI agents can read the file at the displayed path:

```python
# In the REPL initialization (e.g., shotcut_cli.py)
from cli_anything.<software>.utils.repl_skin import ReplSkin

skin = ReplSkin("<software>", version="1.0.0")
skin.print_banner()  # Displays repo-root skills/cli-anything-<software>/SKILL.md when available
```

## Package Data

Ensure `setup.py` includes the skill file as package data so it is installed with pip:

```python
package_data={
    "cli_anything.<software>": ["skills/*.md"],
},
```
