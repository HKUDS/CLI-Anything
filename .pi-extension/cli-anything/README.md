# CLI-Anything Extension for Pi Coding Agent

This directory contains the Pi Coding Agent extension for CLI-Anything, enabling AI agents to build powerful, stateful CLI interfaces for any GUI application.

## Overview

The CLI-Anything Pi extension provides 5 slash commands that inject the HARNESS.md methodology and command specifications into the agent session. This enables the agent to build CLI harnesses for any software with a codebase.

## Installation

### Option 1: Global Install (Recommended)

Install the extension globally so `/cli-anything` commands are available in **all** Pi projects:

```bash
cd CLI-Anything
bash .pi-extension/cli-anything/install.sh
```

To uninstall:

```bash
bash .pi-extension/cli-anything/install.sh --uninstall
```

### Verify

After installing, run `/reload` in Pi or restart Pi. Then type `/cli-anything` to verify the command is available.

## Commands

| Command | Description |
|---------|-------------|
| `/cli-anything <path-or-repo>` | Build a complete CLI harness for any GUI application |
| `/cli-anything:refine <path> [focus]` | Refine an existing CLI harness to improve coverage |
| `/cli-anything:test <path-or-repo>` | Run tests for a CLI harness and update TEST.md |
| `/cli-anything:validate <path-or-repo>` | Validate a CLI harness against HARNESS.md standards |
| `/cli-anything:list [options]` | List all CLI-Anything tools (installed and generated) |

## Usage Examples

### Build a CLI for GIMP

```
/cli-anything ./gimp
```

### Build from a GitHub repository

```
/cli-anything https://github.com/blender/blender
```

### Refine an existing harness

```
/cli-anything:refine ./gimp "batch processing and filters"
```

### List all installed CLIs

```
/cli-anything:list
```

## Extension Structure

```
.pi-extension/cli-anything/
├── index.ts                    # Main extension entry point
├── install.sh                  # Global installation script
├── README.md                   # This file
└── tests/
    └── test_extension.test.ts  # Command registration tests
```

Tests for `skill_generator.py` live in `cli-anything-plugin/tests/` (next to the source).

> **Note:** Command specs, guides, scripts (skill_generator.py, repl_skin.py),
> templates, and HARNESS.md live in `cli-anything-plugin/` (canonical source).
> `install.sh` copies them into `~/.pi/agent/extensions/cli-anything/` alongside
> `index.ts` at install time. The extension reads them from its own directory
> via `__dirname`.

## How It Works

1. **Command Registration**: The extension registers 5 slash commands with Pi's Extension API
2. **Context Injection**: When a command is invoked, it reads HARNESS.md and the relevant command spec
3. **Message Construction**: Builds a comprehensive message with methodology, specs, and user arguments
4. **Agent Execution**: Injects the message into the agent session via `pi.sendUserMessage()`
5. **Path Remapping**: Automatically remaps container paths to local system paths

## Path Remapping

The extension handles path remapping between the containerized environment (referenced in HARNESS.md) and the local system:

| Container Path | Local Path |
|----------------|------------|
| `/root/cli-anything/<software>/` | Current working directory |
| `cli-anything-plugin/repl_skin.py` | Resolved from `cli-anything-plugin/` (single source of truth) |
| `~/.claude/plugins/cli-anything/` | `<extension>/` |

## Development

To modify or extend this extension:

1. Edit `index.ts` for command behavior changes
2. Edit files in `commands/` for command specification changes
3. Edit `cli-anything-plugin/HARNESS.md` for methodology changes (the canonical source)
4. Edit `guides/` for implementation guide changes

## Dependencies

- `@mariozechner/pi-coding-agent` - Pi Extension API
- Node.js built-in modules: `fs`, `path`, `url`

## License

MIT License - See the main CLI-Anything repository for full license details.

## See Also

- [CLI-Anything Main Repository](https://github.com/HKUDS/CLI-Anything)
- [CLI-Hub](https://hkuds.github.io/CLI-Anything/) - Browse all community CLIs
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guidelines
