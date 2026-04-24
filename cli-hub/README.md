# cli-hub

Package manager for [CLI-Anything](https://github.com/HKUDS/CLI-Anything) — a framework that auto-generates stateful CLI interfaces for GUI applications, making them agent-native.

Browse, install, and manage 40+ CLI harnesses for software like GIMP, Blender, Inkscape, LibreOffice, Audacity, OBS Studio, and more — all from your terminal.

**Web Hub**: [clianything.cc](https://clianything.cc)

## Install

```bash
pip install cli-anything-hub
```

## Usage

```bash
# Browse all available CLIs, grouped by category
cli-hub list

# Filter by category (image, 3d, video, audio, office, ai, ...)
cli-hub list -c image

# Search by name, description, or category
cli-hub search "3d modeling"

# Show details for a CLI
cli-hub info gimp

# Install a CLI harness
cli-hub install gimp

# Update a CLI to the latest version
cli-hub update gimp

# Uninstall a CLI
cli-hub uninstall gimp
```

## What gets installed

Each CLI harness is a standalone Python package that wraps a real application (GIMP, Blender, etc.) with a stateful command-line interface. Every harness supports:

- **REPL mode**: `cli-anything-gimp` launches an interactive session
- **One-shot commands**: `cli-anything-gimp project create --name my-project`
- **JSON output**: `cli-anything-gimp --json project list` for machine-readable output
- **Undo/redo**: Stateful project management with full operation history

## For AI agents

cli-hub is designed to be agent-friendly. AI coding agents can:

1. `pip install cli-anything-hub` to get the package manager
2. `cli-hub search <keyword>` or `cli-hub list --json` to discover tools
3. `cli-hub install <name>` to install what they need
4. Use `--json` output for structured data parsing

## Available categories

3D, AI, Audio, Communication, Database, Design, DevOps, Diagrams, Game, GameDev, Generation, Graphics, Image, Music, Network, Office, OSINT, Project Management, Search, Streaming, Testing, Video, Web

## JSON output

All listing commands support `--json` for machine-readable output:

```bash
cli-hub list --json
cli-hub search blender --json
```

## Analytics

cli-hub sends anonymous usage events to help track adoption. The default provider is [PostHog](https://posthog.com), while the legacy Umami path remains available via `CLI_HUB_ANALYTICS_PROVIDER=umami`. No personal data is collected.

Opt out:

```bash
export CLI_HUB_NO_ANALYTICS=1
```

## Links

- **Web Hub**: [clianything.cc](https://clianything.cc)
- **Repository**: [github.com/HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything)
- **Live Catalog**: [SKILL.md](https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md)
