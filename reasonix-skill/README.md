# CLI-Anything for Reasonix

An adapter that brings the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) harness methodology to the [Reasonix](https://github.com/esengine/DeepSeek-Reasonix) coding agent.

CLI-Anything is a methodology for making **any GUI software agent-native** by generating stateful CLI harnesses with REPL mode, JSON output, undo/redo, and comprehensive tests. This adapter lets Reasonix act as the builder agent.

## Installation

**macOS / Linux:**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything/reasonix-skill
./scripts/install.sh
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything\reasonix-skill
.\scripts\install.ps1
```

Both scripts copy the skill to Reasonix's global skill directory at `~/.reasonix/skills/cli-anything`.

## Configuration Note

A full CLI-Anything build (architecture analysis, 10+ file generation, installation, and multiple test runs) typically requires 25–40 tool-call rounds. Reasonix's subagent step budget is derived from the `agent.max_steps` setting in `reasonix.toml`:

- The default `max_steps = 0` means unlimited, which is recommended for this workflow.
- If you have set `max_steps` to a finite value, the subagent receives half that budget (minimum 5), which may cause a build to be truncated before completion.

To ensure builds complete successfully, set `agent.max_steps = 0` in your `reasonix.toml`, or use a sufficiently high value such as 64 or more.

## Usage

After installation, use slash invocation to inline the skill into the parent Reasonix loop:

```
/cli-anything https://github.com/GNOME/gimp
```

Use `run_skill` when you want isolated subagent execution. The same isolation applies when Reasonix invokes the skill through its dedicated subagent path:

```
run_skill({ name: "cli-anything", arguments: "/path/to/software" })
```

### What It Does

The skill follows the CLI-Anything 7-phase methodology:

1. **Codebase Analysis** — Surveys the target software's architecture, data model, and API surface
2. **CLI Architecture Design** — Designs command groups, state model, and output formats
3. **Implementation** — Generates a Click-based Python CLI with REPL, JSON output, and session state
4. **Test Planning** — Creates TEST.md with comprehensive test plan
5. **Test Implementation** — Writes unit tests and E2E tests with real backend invocation
6. **Test Documentation** — Runs all tests and documents results
7. **PyPI Packaging** — Creates setup.py and verifies `pip install -e .`

### Example

```bash
# Build a CLI for GIMP from local source
/cli-anything /home/user/gimp

# Build from a GitHub repo
/cli-anything https://github.com/blender/blender

# Refine an existing harness
/cli-anything /home/user/gimp "Refine the existing harness for batch processing and Script-Fu filters"
```

## Reasonix Tool Mapping

| CLI-Anything Need | Reasonix Tool |
|-------------------|---------------|
| Shell execution | `bash` |
| File generation | `write_file` |
| Code editing | `edit_file` / `multi_edit` |
| Source reading | `read_file` |
| Codebase search | `grep` / `glob` / `ls` |
| Architecture analysis | `mcp__codegraph__search` / `mcp__codegraph__context` when CodeGraph is enabled |
| Documentation fetch | `web_fetch` |

## File Structure

```
reasonix-skill/
├── SKILL.md                      # Main skill document (methodology + tool bindings)
├── README.md                     # This file
├── agents/
│   └── reasonix.yaml             # Agent interface metadata
└── scripts/
    ├── install.sh                # macOS/Linux installer
    └── install.ps1               # Windows installer
```

## How It Compares to Other Agent Adapters

| Feature | Claude Code | Codex | Hermes | **Reasonix** |
|---------|------------|-------|--------|-------------|
| Skill format | `.claude-plugin/` | `SKILL.md` + YAML | `SKILL.md` + YAML | `SKILL.md` + YAML |
| Shell | `bash` | `terminal` | `terminal` | `bash` |
| File ops | native | `execute_code` | `execute_code` / `write_file` | `write_file` / `edit_file` / `multi_edit` |
| Code analysis | file reads | file reads | file reads | Optional `mcp__codegraph__search` / `mcp__codegraph__context` symbol graph |
| Install method | `/plugin install` | `install.sh` → `$CODEX_HOME/skills/` | `install.sh` → `$HERMES_HOME/skills/` | `install.sh` → `~/.reasonix/skills/` |

## Contributing

This adapter follows the same contribution pattern as the Codex and Hermes adapters. See [CONTRIBUTING.md](../CONTRIBUTING.md) in the CLI-Anything repository.

## License

Apache License 2.0 — same as CLI-Anything.
