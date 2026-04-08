# Godot CLI Harness — Architecture

## Strategy

Godot Engine is a feature-rich open-source game engine with strong CLI support via `--headless`, `--script`, and `--export-*` flags. This harness wraps those capabilities into an agent-friendly interface with structured JSON output.

## Backend

- **Binary**: Godot 4.x executable, discovered via PATH or `GODOT_BIN` env var
- **Interaction**: `subprocess.run()` — no REST API, no socket; pure CLI subprocess
- **Headless**: All operations use `--headless` flag (no GPU/display required)

## Command Map

| CLI Command | Godot Mechanism |
|-------------|-----------------|
| `project create` | Write `project.godot` INI file directly |
| `project info` | Parse `project.godot` |
| `project scenes/scripts/resources` | Filesystem glob (`*.tscn`, `*.gd`, `*.tres`) |
| `project reimport` | `godot --headless --import --quit` |
| `scene create` | Write `.tscn` file (Godot scene format) |
| `scene read` | Parse `.tscn` text format |
| `scene add-node` | Append `[node]` section to `.tscn` |
| `export build` | `godot --headless --export-release <preset>` |
| `export presets` | Parse `export_presets.cfg` |
| `script run` | `godot --headless --script res://path.gd --quit` |
| `script inline` | Write temp `.gd`, run with `--script`, delete |
| `script validate` | `godot --headless --check-only --script` |
| `engine version` | `godot --version --quit` |

## Key Design Decisions

1. **No Godot REST API** — unlike OBS or Ollama, Godot has no built-in HTTP server. All interaction is via subprocess + file I/O.
2. **Scene file I/O** — `.tscn` is a human-readable text format. We parse and generate it directly for scene operations instead of requiring Godot to be running.
3. **Project file parsing** — `project.godot` is INI-like. We read it with string parsing rather than requiring the engine.
4. **Temp scripts** — `script inline` writes a temporary `.gd` file inside the project (required for `res://` resolution), runs it, then cleans up.

## Security

- **`script inline`**: The provided GDScript code is written to a temporary file inside the project directory and executed via `godot --headless --script`. The temp file is deleted after execution. This command executes arbitrary code on the host machine — only use with trusted input. In an agent context, the agent is responsible for ensuring the code it generates is safe.

## Version Compatibility

- **`--export-all`** is available in Godot **4.3+**. Earlier 4.x versions require exporting each preset individually with `--export-release <preset>`.
- **`--check-only`** for script validation may not be available in all Godot 4.x versions.
- Binary discovery searches for `godot`, `godot4`, and common versioned binary names. Set `GODOT_BIN` for non-standard installations.
