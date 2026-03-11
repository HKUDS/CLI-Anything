# Quick Start Guide

Get started with the cli-anything plugin in 5 minutes.

## Installation

```bash
# Copy plugin to Claude Code plugins directory
REPO_ROOT=/path/to/CLI-Anything
cp -r "$REPO_ROOT/cli-anything-plugin" ~/.claude/plugins/cli-anything

# Reload plugins in Claude Code
/reload-plugins

# Verify installation
/help cli-anything
```

## Your First CLI Harness

Let's build a CLI for a simple GUI application:

```bash
# Build complete CLI harness for GIMP
/cli-anything /path/to/gimp-source
```

This will:
1. ✅ Analyze GIMP's architecture
2. ✅ Design the CLI structure
3. ✅ Implement all core modules
4. ✅ Create test plan
5. ✅ Write and run tests
6. ✅ Document results
7. ✅ Create setup.py and install to PATH

**Time:** ~10-15 minutes (depending on complexity)

**Output:** `/path/to/gimp-source/agent-harness/`

## Install the CLI

```bash
# Install to system PATH
cd /path/to/gimp-source/agent-harness
pip install -e .

# Verify it's in PATH
which cli-anything-gimp

# Use it from anywhere
cli-anything-gimp --help
```

## Test the CLI

```bash
# Navigate to the CLI directory
cd /path/to/gimp-source/agent-harness

# Run the CLI directly (if installed)
cli-anything-gimp --help

# Or run as module
python3 -m cli_anything.gimp.gimp_cli --help

# Try creating a project
cli-anything-gimp project new --width 800 --height 600 -o test.json

# Enter REPL mode
cli-anything-gimp repl
```

## Run Tests

```bash
# Run all tests
/cli-anything:test /path/to/gimp-source

# Or manually
cd /path/to/gimp-source/agent-harness
python3 -m pytest cli_anything/gimp/tests/ -v

# Force tests to use the installed command (recommended for validation)
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/gimp/tests/ -v -s
# Output should show: [_resolve_cli] Using installed command: /path/to/cli-anything-gimp
```

## Validate Quality

```bash
# Check if CLI meets all standards
/cli-anything:validate /path/to/gimp-source
```

## Build Another CLI

```bash
# Build CLI for Blender (3D software)
/cli-anything /path/to/blender-source

# Build CLI for Inkscape (vector graphics)
/cli-anything /path/to/inkscape-source

# Build CLI for Audacity (audio editor)
/cli-anything /path/to/audacity-source
```

## Refining an Existing CLI

After the initial build, use the refine command to expand coverage:

```bash
# Broad refinement — agent finds gaps across all capabilities
/cli-anything:refine /home/user/obs-studio

# Focused refinement — target a specific functionality area
/cli-anything:refine /home/user/obs-studio "scene transitions and streaming profiles"
```

## Common Workflows

### Build and Test
```bash
/cli-anything /home/user/gimp
/cli-anything:test /home/user/gimp
```

### Build, Validate, Test, Install
```bash
/cli-anything /home/user/blender
/cli-anything:validate /home/user/blender
/cli-anything:test /home/user/blender
cd /home/user/blender/agent-harness
pip install -e .
which cli-anything-blender
```

### Refine After Initial Build
```bash
# Expand coverage with gap analysis
/cli-anything:refine /home/user/inkscape

# Focus on a specific area
/cli-anything:refine /home/user/inkscape "path boolean operations and clipping masks"
```

## Troubleshooting

### Plugin not found
```bash
# Check if plugin is in the right location
ls ~/.claude/plugins/cli-anything

# Reload plugins
/reload-plugins
```

### Tests fail
```bash
# Check Python version (need 3.10+)
python3 --version

# Install dependencies
pip install click pytest pillow numpy

# Run validation
/cli-anything:validate <software>
```

### CLI doesn't work
```bash
# Check if all files were created
ls <software-path>/agent-harness/cli_anything/<software>/

# Verify Python can import
cd <software-path>/agent-harness
python3 -c "import cli_anything.<software>"

# Check if installed to PATH
which cli-anything-<software>

# Reinstall if needed
pip install -e .
```

## Publishing to PyPI

Once your CLI is ready:

```bash
cd <software-path>/agent-harness

# Install build tools
pip install build twine

# Build distribution packages
python -m build

# Upload to PyPI (requires account)
twine upload dist/*
```

Users can then install (multiple CLIs coexist without conflicts):
```bash
pip install cli-anything-gimp cli-anything-blender
cli-anything-gimp --help
cli-anything-blender --help
```

## Next Steps

1. **Read the full README:** `cat README.md`
2. **Study an example:** Explore `<software-path>/agent-harness/cli_anything/<software>/`
3. **Read HARNESS.md:** Understand the methodology at `<plugin-dir>/HARNESS.md` (commonly `~/.claude/plugins/cli-anything/HARNESS.md`)
4. **Build your own:** Choose a GUI app and run `/cli-anything <software-path-or-repo>`

## Tips

- Start with simpler applications (GIMP, Inkscape) before complex ones (Blender, LibreOffice)
- Always run validation before considering a CLI complete
- Read the generated TEST.md to understand what's tested
- Use `--json` flag for machine-readable output
- REPL mode is great for interactive exploration
- Install CLIs to PATH for agent discoverability
- Publish to PyPI to share with the community

## Help

```bash
# Get help on any command
/help cli-anything
/help cli-anything:refine
/help cli-anything:test
/help cli-anything:validate

# Or read the command docs
cat commands/cli-anything.md
```

## Success!

You now have a powerful tool for building CLI harnesses for any GUI application. Happy building!
