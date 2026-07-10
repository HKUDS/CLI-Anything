---
name: cli-hub-meta-skill
description: >-
  Discover agent-native CLIs for professional software. Access the live catalog
  to find tools for creative workflows, productivity, AI, and more.
---

# CLI-Hub Meta-Skill

CLI-Hub is a marketplace of agent-native command-line interfaces that make professional software accessible to AI agents.

## Quick Start

```bash
# Install the CLI Hub package manager
pip install cli-anything-hub

# Browse all available CLIs
cli-hub list

# Search by category or keyword
cli-hub search image
cli-hub search "3d modeling"

# Install a CLI
cli-hub install gimp

# Show details for a CLI
cli-hub info gimp
```

## Workflow Matrices

A single CLI is one tool. A **matrix** is a whole workflow packaged as
capabilities × providers — e.g. `video-creation` maps intents like
`text.transcribe` or `visual.generate` to harness CLIs, public CLIs, Python
libraries, native binaries, and cloud APIs. Reach for a matrix when a task spans
several tools (produce a video, design an image, build a game).

Standard agent sequence — **preflight before you install**:

```bash
cli-hub matrix list                                   # browse all matrices
cli-hub can "transcribe audio"                        # find the capability across matrices
cli-hub matrix search "video subtitle"                # search; shows the matched capability
cli-hub matrix preflight video-creation --json        # what's usable here? (exit 3 = gaps)
cli-hub matrix preflight video-creation -c text.transcribe --fix-hints   # one capability + install hints
cli-hub matrix install video-creation --capability text.transcribe       # install ONLY what the task needs
# After install, the matrix SKILL.md renders locally with provider-selection rules — read it.
```

Scope every install — do not bulk-install a 14-CLI matrix for a one-capability
task. Use `--capability <id>`, `--recipe <id>`, or `--only a,b`, and
`--dry-run` to preview the plan with zero side effects. `--json` is available on
every matrix subcommand; exit codes are `0` ok · `3` partial/gaps · `1` failure ·
`2` usage error. Retry failures with `cli-hub matrix install <name> --resume`,
and audit an install with `cli-hub matrix doctor <name>`.


## Live Catalog

**URL**: [`https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md`](https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md)

The catalog is auto-updated and provides:
- Full list of available CLIs organized by category
- One-line `cli-hub install` commands for each tool
- Complete descriptions and usage patterns


## What Can You Do?

CLI-Hub covers a broad range of software and codebases, empowering agents to conduct complex workflows via CLI:

- **Creative workflows**: Image editing, 3D modeling, video production, audio processing, music notation
- **Productivity tools**: Office suites, knowledge management, live streaming
- **AI platforms**: Local LLMs, image generation, AI APIs, research assistants
- **Communication**: Video conferencing and collaboration
- **Development**: Diagramming, browser automation, network management
- **Content generation**: AI-powered document and media creation

Each CLI provides stateful operations, JSON output for agents, REPL mode, and integrates with real software backends.

## How It Works

`cli-hub` is a lightweight wrapper around `pip`. When you run `cli-hub install gimp`, it installs a separate Python package (`cli-anything-gimp`) with its own CLI entry point (`cli-anything-gimp`). Each CLI is an independent pip package — `cli-hub` simply resolves names from the registry and tracks installs.

## How to Use

1. **Install cli-hub**: `pip install cli-anything-hub`
2. **Find your tool**: `cli-hub search <keyword>` or `cli-hub list -c <category>`
3. **Install**: `cli-hub install <name>` (installs the `cli-anything-<name>` pip package)
4. **Run**: `cli-anything-<name>` for REPL, or `cli-anything-<name> <command>` for one-shot
5. **JSON output**: All CLIs support `--json` flag for machine-readable output

## Example Workflow

```bash
# Install the hub
pip install cli-anything-hub

# Find what you need
cli-hub search video

# Install it
cli-hub install kdenlive

# Use it with JSON output
cli-anything-kdenlive --json project create --name my-project
```

## More Info

- Live Catalog: https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md
- Web Hub: https://clianything.cc
- Repository: https://github.com/HKUDS/CLI-Anything
