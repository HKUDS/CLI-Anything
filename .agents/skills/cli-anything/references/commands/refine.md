# cli-anything:refine Command

> Historical slash-command spec. In skill mode, follow the same workflow without requiring `/cli-anything:refine` command support.

Refine an existing CLI harness to improve coverage of the software's functions and usage patterns.

## CRITICAL: Read HARNESS.md First

**Before refining, read `../HARNESS.md`.** All new commands and tests must follow the same standards as the original build. HARNESS.md is the single source of truth for architecture, patterns, and quality requirements.

## Usage

```bash
/cli-anything:refine <software-path> [focus]
```

## Arguments

- `<software-path>` - **Required.** Local path to the software source code (e.g., `/home/user/gimp`, `./blender`). Must be the same source tree used during the original build.

  **Note:** Only local paths are accepted. If you need to work from a GitHub repo, run the build workflow described in `cli-anything.md` first, then refine.

- `[focus]` - **Optional.** A natural-language description of the functionality area to focus on. When provided, the agent skips broad gap analysis and instead targets the specified capability area.

  Examples:
  - `/cli-anything:refine /home/user/shotcut "vid-in-vid and picture-in-picture features"`
  - `/cli-anything:refine /home/user/gimp "all batch processing and scripting filters"`
  - `/cli-anything:refine /home/user/blender "particle systems and physics simulation"`
  - `/cli-anything:refine /home/user/inkscape "path boolean operations and clipping"`

  When `[focus]` is provided:
  - Step 2 (Analyze Software Capabilities) narrows to only the specified area
  - Step 3 (Gap Analysis) compares only the focused capabilities against current coverage
  - The agent should still present findings before implementing, but scoped to the focus area

## What This Command Does

This command is used **after** a CLI harness has already been built with the main CLI-Anything workflow. It analyzes gaps between the software's full capabilities and what the current CLI covers, then iteratively expands coverage. If a `[focus]` is given, the agent narrows its analysis and implementation to that specific functionality area.

### Step 1: Inventory Current Coverage
- Read the existing CLI entry point (`<software>_cli.py`) and all core modules
- List every command, subcommand, and option currently implemented
- Read the existing test suite to understand what's tested
- Build a coverage map: `{ function_name: covered | not_covered }`

### Step 2: Analyze Software Capabilities
- Re-scan the software source at `<software-path>`
- Identify all public APIs, CLI tools, scripting interfaces, and batch-mode operations
- Focus on functions that produce observable output (renders, exports, transforms, conversions)
- Categorize by domain (e.g., for GIMP: filters, color adjustments, layer ops, selection tools)

### Step 3: Gap Analysis
- Compare current CLI coverage against the software's full capability set
- Prioritize gaps by:
  1. **High impact** — commonly used functions missing from the CLI
  2. **Easy wins** — functions with simple APIs that can be wrapped quickly
  3. **Composability** — functions that unlock new workflows when combined with existing commands
- Present the gap report to the user and confirm which gaps to address

### Step 4: Implement New Commands
- Add new commands/subcommands to the CLI for the selected gaps
- Follow the same patterns as existing commands (as defined in HARNESS.md):
  - Click command groups
  - `--json` output support
  - Session state integration
  - Error handling with `handle_error`
- Add corresponding core module functions in `core/` or `utils/`

### Step 5: Expand Tests
- Add unit tests for every new function in `test_core.py`
- Add E2E tests for new commands in `test_full_e2e.py`
- Add workflow tests that combine new commands with existing ones
- Run all tests (old + new) to ensure no regressions

### Step 6: Update Documentation
- Update `README.md` with new commands and usage examples
- Update `TEST.md` with new test results
- Update the SOP document (`<SOFTWARE>.md`) with new coverage notes

## Example

```bash
# Broad refinement — agent finds gaps across all capabilities
/cli-anything:refine /home/user/gimp

# Focused refinement — agent targets a specific functionality area
/cli-anything:refine /home/user/shotcut "vid-in-vid and picture-in-picture compositing"
/cli-anything:refine /home/user/gimp "batch processing and Script-Fu filters"
/cli-anything:refine /home/user/blender "particle systems and physics simulation"
/cli-anything:refine /home/user/inkscape "path boolean operations and clipping masks"
```

## Success Criteria

- All existing tests still pass (no regressions)
- New commands follow the same architectural patterns (per HARNESS.md)
- New tests achieve 100% pass rate
- Coverage meaningfully improved (new functions exposed via CLI)
- Documentation updated to reflect changes

## Notes

- Refine is incremental — run it multiple times to steadily expand coverage
- Each run should focus on a coherent set of related functions rather than trying to cover everything at once
- The agent should present the gap analysis before implementing, so the user can steer priorities
- Refine never removes existing commands — it only adds or enhances
