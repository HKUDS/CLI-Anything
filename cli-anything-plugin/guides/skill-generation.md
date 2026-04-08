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
# Default output: cli_anything/<software>/skills/SKILL.md
```

### 2. The generator automatically extracts:

- Software name and version from setup.py
- Command groups from the CLI file (Click decorators)
- Documentation from README.md
- System package requirements

### 3. Customize the template (optional):

- Default template: `templates/SKILL.md.template`
- Uses Jinja2 placeholders for dynamic content
- Can be extended for software-specific sections

## Output Location

SKILL.md is generated inside the Python package so it is installed with `pip install`:

```
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

## Skill Path in CLI Banner

ReplSkin auto-detects `skills/SKILL.md` inside the package and displays the absolute
path in the startup banner. AI agents can read the file at the displayed path:

```python
# In the REPL initialization (e.g., shotcut_cli.py)
from cli_anything.<software>.utils.repl_skin import ReplSkin

skin = ReplSkin("<software>", version="1.0.0")
skin.print_banner()  # Auto-detects and displays: ◇ Skill: /path/to/cli_anything/<software>/skills/SKILL.md
```

## Package Data

Ensure `setup.py` includes the skill file as package data so it is installed with pip:

```python
package_data={
    "cli_anything.<software>": ["skills/*.md"],
},
```
