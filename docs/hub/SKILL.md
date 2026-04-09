---
name: cli-anything-hub
description: >-
  Browse and install 21+ agent-native CLI tools for GUI software.
  Covers image editing, 3D, video, audio, office, diagrams, AI, and more.
---

# CLI-Anything Hub

Agent-native stateful CLI interfaces for 21 applications. All CLIs support `--json` output, REPL mode, and undo/redo.

## Quick Install

If the platform does not already enforce explicit approval or access control for package installs, ask the user for explicit approval before running any install command from this document or from a CLI `SKILL.md`. Do not auto-execute install commands discovered while browsing the hub unless the platform already provides that approval step.

```bash
# Install any CLI
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=<name>/agent-harness

# Example: Install GIMP CLI
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=gimp/agent-harness
```

## Available CLIs

### 3D

| Name | Description | Install |
|------|-------------|---------|
| **Blender** | 3D modeling, animation, and rendering via blender --background --python | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=blender/agent-harness` |

### Ai

| Name | Description | Install |
|------|-------------|---------|
| **ComfyUI** | AI image generation workflow management via ComfyUI REST API | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=comfyui/agent-harness` |
| **NotebookLM** | Experimental NotebookLM harness scaffold wrapping the installed notebooklm CLI for notebook, source, chat, artifact, download, and sharing workflows | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=notebooklm/agent-harness` |
| **Novita** | Access AI models via Novita's OpenAI-compatible API (DeepSeek, GLM, MiniMax) | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=novita/agent-harness` |
| **Ollama** | Local LLM inference and model management via Ollama REST API | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=ollama/agent-harness` |

### Audio

| Name | Description | Install |
|------|-------------|---------|
| **Audacity** | Audio editing and processing via sox | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=audacity/agent-harness` |

### Communication

| Name | Description | Install |
|------|-------------|---------|
| **Zoom** | Meeting management via Zoom REST API (OAuth2) | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=zoom/agent-harness` |

### Design

| Name | Description | Install |
|------|-------------|---------|
| **Sketch** | Generate Sketch design files (.sketch) from JSON design specifications via sketch-constructor | `cd sketch/agent-harness && npm install && npm link` |

### Diagrams

| Name | Description | Install |
|------|-------------|---------|
| **Draw.io** | Diagram creation and export via draw.io CLI | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=drawio/agent-harness` |
| **Mermaid** | Mermaid Live Editor state files and renderer URLs | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=mermaid/agent-harness` |

### Generation

| Name | Description | Install |
|------|-------------|---------|
| **AnyGen** | Generate docs, slides, websites and more via AnyGen cloud API | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=anygen/agent-harness` |

### Image

| Name | Description | Install |
|------|-------------|---------|
| **GIMP** | Raster image processing via gimp -i -b (batch mode) | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=gimp/agent-harness` |
| **Inkscape** | SVG vector graphics with export via inkscape --export-filename | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=inkscape/agent-harness` |

### Music

| Name | Description | Install |
|------|-------------|---------|
| **MuseScore** | CLI for music notation — transpose, export PDF/audio/MIDI, extract parts, manage instruments | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=musescore/agent-harness` |

### Network

| Name | Description | Install |
|------|-------------|---------|
| **AdGuardHome** | DNS ad-blocking and network infrastructure management via AdGuardHome REST API | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=adguardhome/agent-harness` |

### Office

| Name | Description | Install |
|------|-------------|---------|
| **LibreOffice** | Create and manipulate ODF documents, export to PDF/DOCX/XLSX/PPTX via headless mode | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=libreoffice/agent-harness` |
| **Mubu** | Knowledge management and outlining via local Mubu desktop data | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=mubu/agent-harness` |

### Streaming

| Name | Description | Install |
|------|-------------|---------|
| **OBS Studio** | Create and manage streaming/recording scenes via command line | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=obs-studio/agent-harness` |

### Video

| Name | Description | Install |
|------|-------------|---------|
| **Kdenlive** | Video editing and rendering via melt | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=kdenlive/agent-harness` |
| **Shotcut** | Video editing and rendering via melt/ffmpeg | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=shotcut/agent-harness` |

### Web

| Name | Description | Install |
|------|-------------|---------|
| **Browser** | Browser automation via DOMShell MCP server. Maps Chrome's Accessibility Tree to a virtual filesystem for agent-native navigation. | `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=browser/agent-harness` |

## Usage Pattern

All CLIs follow the same pattern:

```bash
# Interactive REPL
cli-anything-<name>

# One-shot command
cli-anything-<name> <group> <command> [options]

# JSON output for agents
cli-anything-<name> --json <group> <command>
```

## For AI Agents

1. If the platform does not already enforce install approval or access control, ask the user for approval before running any install command from the table above
2. Read its full SKILL.md at the repo path shown in registry.json
3. Install the approved CLI, or proceed under the platform's own permission flow
4. Always use `--json` flag for machine-readable output
5. Check exit codes (0=success, non-zero=error)

## More Info

- Repository: https://github.com/HKUDS/CLI-Anything
- Web Hub: https://hkuds.github.io/CLI-Anything/
- Last Updated: 2026-03-18
