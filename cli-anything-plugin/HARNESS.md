# Agent Harness: GUI-to-CLI for Open Source Software

## Purpose

This harness provides a standard operating procedure (SOP) and toolkit for coding
agents (Claude Code, Codex, etc.) to build powerful, stateful CLI interfaces for
open-source GUI applications. The goal: let AI agents operate software that was
designed for humans, without needing a display or mouse.

## General SOP: Turning Any GUI App into an Agent-Usable CLI

### Phase 1: Codebase Analysis

**⚠ Binary Application Detection:** Before starting analysis, check if the provided
path is a compiled application bundle (`.app`, `.exe`, `.AppImage`, `.msi`, `.deb`,
`.rpm`, `.flatpak`) rather than source code. If the path contains only compiled
binaries and no source files, **abort immediately** with a clear message:
*"CLI-Anything requires access to the software's source code repository, not a
compiled/installed application. Please provide the source code path or GitHub URL."*

**Scan before reading:** Before opening any files, list the directory tree (file names
and sizes only). Build a prioritized reading plan, starting with high-signal files
(README, CLI entry points, API headers, core modules).

**Always exclude the following from analysis:**
  - Binary files: `.o`, `.so`, `.dylib`, `.a`, `.exe`, `.dll`, `.wasm`, `.pyc`, `.class`, `.jar`
  - Build artifacts: `build/`, `dist/`, `__pycache__/`, `node_modules/`, `.git/`, `target/`, `cmake-build*/`
  - Generated code: `*_generated.*`, `*.pb.go`, `*.pb.cc`
  - Media/assets: images, videos, fonts, archives (`.png`, `.jpg`, `.mp4`, `.zip`, `.tar.*`)
  - Test fixtures and large data files
  - Vendored/third-party code (`vendor/`, `third_party/`)

Perform the analysis:

1. **Identify the backend engine** — Most GUI apps separate presentation from logic.
   Find the core library/framework (e.g., MLT for Shotcut, ImageMagick for GIMP).
2. **Map GUI actions to API calls** — Every button click, drag, and menu item
   corresponds to a function call. Catalog these mappings.
3. **Identify the data model** — What file formats does it use? How is project state
   represented? (XML, JSON, binary, database?)
4. **Find existing CLI tools** — Many backends ship their own CLI (`melt`, `ffmpeg`,
   `convert`). These are building blocks.
5. **Catalog the command/undo system** — If the app has undo/redo, it likely uses a
   command pattern. These commands are your CLI operations.

### Phase 2: CLI Architecture Design

1. **Choose the interaction model**:
   - **Stateful REPL** for interactive sessions (agents that maintain context)
   - **Subcommand CLI** for one-shot operations (scripting, pipelines)
   - **Both** (recommended) — a CLI that works in both modes

2. **Define command groups** matching the app's logical domains:
   - Project management (new, open, save, close)
   - Core operations (the app's primary purpose)
   - Import/Export (file I/O, format conversion)
   - Configuration (settings, preferences, profiles)
   - Session/State management (undo, redo, history, status)

3. **Design the state model**:
   - What must persist between commands? (open project, cursor position, selection)
   - Where is state stored? (in-memory for REPL, file-based for CLI)
   - How does state serialize? (JSON session files)

4. **Plan the output format**:
   - Human-readable (tables, colors) for interactive use
   - Machine-readable (JSON) for agent consumption
   - Both, controlled by `--json` flag

### Phase 3: Implementation

1. **Start with the data layer** — XML/JSON manipulation of project files
2. **Add probe/info commands** — Let agents inspect before they modify
3. **Add mutation commands** — One command per logical operation
4. **Add the backend integration** — A `utils/<software>_backend.py` module that
   wraps the real software's CLI. This module handles:
   - Finding the software executable (`shutil.which()`)
   - Invoking it with proper arguments (`subprocess.run()`)
   - Error handling with clear install instructions if not found
   - Example (LibreOffice):
     ```python
     # utils/lo_backend.py
     def convert_odf_to(odf_path, output_format, output_path=None, overwrite=False):
         lo = find_libreoffice()  # raises RuntimeError with install instructions
         subprocess.run([lo, "--headless", "--convert-to", output_format, ...])
         return {"output": final_path, "format": output_format, "method": "libreoffice-headless"}
     ```
5. **Add rendering/export** — The export pipeline calls the backend module.
   Generate valid intermediate files, then invoke the real software for conversion.
6. **Add session management** — State persistence, undo/redo

   **Session file locking** — Use exclusive file locking for session JSON saves
   to prevent concurrent write corruption. See [`guides/session-locking.md`](guides/session-locking.md)
   for the `_locked_save_json` pattern (open `"r+"`, lock, then truncate inside the lock).
7. **Add the REPL with unified skin** — Interactive mode wrapping the subcommands.
   - Copy `repl_skin.py` from the plugin (`cli-anything-plugin/repl_skin.py`) into
     `utils/repl_skin.py` in your CLI package
   - Import and use `ReplSkin` for the REPL interface:
     ```python
     from cli_anything.<software>.utils.repl_skin import ReplSkin

     skin = ReplSkin("<software>", version="1.0.0")
     skin.print_banner()          # Branded startup box (prefers repo-root skills/, falls back to package)
     pt_session = skin.create_prompt_session()  # prompt_toolkit with history + styling
     line = skin.get_input(pt_session, project_name="my_project", modified=True)
     skin.help(commands_dict)     # Formatted help listing
     skin.success("Saved")        # ✓ green message
     skin.error("Not found")      # ✗ red message
     skin.warning("Unsaved")      # ⚠ yellow message
     skin.info("Processing...")   # ● blue message
     skin.status("Key", "value")  # Key-value status line
     skin.table(headers, rows)    # Formatted table
     skin.progress(3, 10, "...")  # Progress bar
     skin.print_goodbye()         # Styled exit message
     ```
   - ReplSkin prefers the repo-root canonical `skills/cli-anything-<software>/SKILL.md`
     when running inside this monorepo, and falls back to the packaged
     `cli_anything/<software>/skills/SKILL.md` copy when installed elsewhere.
     AI agents can read the skill file at the displayed absolute path.
   - Make REPL the default behavior: use `invoke_without_command=True` on the main
     Click group, and invoke the `repl` command when no subcommand is given:
     ```python
     @click.group(invoke_without_command=True)
     @click.pass_context
     def cli(ctx, ...):
         ...
         if ctx.invoked_subcommand is None:
             ctx.invoke(repl, project_path=None)
     ```
   - This ensures `cli-anything-<software>` with no arguments enters the REPL

### Phase 4: Test Planning (TEST.md - Part 1)

**BEFORE writing any test code**, create a `TEST.md` file in the
`agent-harness/cli_anything/<software>/tests/` directory. This file serves as your test plan and
MUST contain:

1. **Test Inventory Plan** — List planned test files and estimated test counts:
   - `test_core.py`: XX unit tests planned
   - `test_full_e2e.py`: XX E2E tests planned

2. **Unit Test Plan** — For each core module, describe what will be tested:
   - Module name (e.g., `project.py`)
   - Functions to test
   - Edge cases to cover (invalid inputs, boundary conditions, error handling)
   - Expected test count

3. **E2E Test Plan** — Describe the real-world scenarios to test:
   - What workflows will be simulated?
   - What real files will be generated/processed?
   - What output properties will be verified?
   - What format validations will be performed?

4. **Realistic Workflow Scenarios** — Detail each multi-step workflow:
   - **Workflow name**: Brief title
   - **Simulates**: What real-world task (e.g., "photo editing pipeline",
     "podcast production", "product render setup")
   - **Operations chained**: Step-by-step operations
   - **Verified**: What output properties will be checked

This planning document ensures comprehensive test coverage before writing code.

### Phase 5: Test Implementation

Now write the actual test code based on the TEST.md plan:

1. **Unit tests** (`test_core.py`) — Every core function tested in isolation with
   synthetic data. No external dependencies.
2. **E2E tests — intermediate files** (`test_full_e2e.py`) — Verify the project files
   your CLI generates are structurally correct (valid XML, correct ZIP structure, etc.)
3. **E2E tests — true backend** (`test_full_e2e.py`) — **MUST invoke the real software.**
   Create a project, export via the actual software backend, and verify the output:
   - File exists and size > 0
   - Correct format (PDF magic bytes `%PDF-`, DOCX/XLSX/PPTX is valid ZIP/OOXML, etc.)
   - Content verification where possible (CSV contains expected data, etc.)
   - **Print artifact paths** so users can manually inspect: `print(f"\n  PDF: {path} ({size:,} bytes)")`
   - **No graceful degradation** — if the software isn't installed, tests fail, not skip
4. **Output verification** — **Don't trust that export works just because it exits
   successfully.** Verify outputs programmatically:
   - Magic bytes / file format validation
   - ZIP structure for OOXML formats (DOCX, XLSX, PPTX)
   - Pixel-level analysis for video/images (probe frames, compare brightness)
   - Audio analysis (RMS levels, spectral comparison)
   - Duration/format checks against expected values
5. **CLI subprocess tests** — Test the installed CLI command as a real user/agent would.
   The subprocess tests MUST also produce real final output (not just ODF intermediate).
   Use the `_resolve_cli` helper to run the installed `cli-anything-<software>` command:
   ```python
   def _resolve_cli(name):
       """Resolve installed CLI command; falls back to python -m for dev.

       Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
       """
       import shutil
       force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
       path = shutil.which(name)
       if path:
           print(f"[_resolve_cli] Using installed command: {path}")
           return [path]
       if force:
           raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
       module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
       print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
       return [sys.executable, "-m", module]


   class TestCLISubprocess:
       CLI_BASE = _resolve_cli("cli-anything-<software>")

       def _run(self, args, check=True):
           return subprocess.run(
               self.CLI_BASE + args,
               capture_output=True, text=True,
               check=check,
           )

       def test_help(self):
           result = self._run(["--help"])
           assert result.returncode == 0

       def test_project_new_json(self, tmp_dir):
           out = os.path.join(tmp_dir, "test.json")
           result = self._run(["--json", "project", "new", "-o", out])
           assert result.returncode == 0
           data = json.loads(result.stdout)
           # ... verify structure
   ```

   **Key rules for subprocess tests:**
   - Always use `_resolve_cli("cli-anything-<software>")` — never hardcode
     `sys.executable` or module paths directly
   - Do NOT set `cwd` — installed commands must work from any directory
   - Use `CLI_ANYTHING_FORCE_INSTALLED=1` in CI/release testing to ensure the
     installed command (not a fallback) is being tested
   - Test `--help`, `--json`, project creation, key commands, and full workflows

6. **Round-trip test** — Create project via CLI, open in GUI, verify correctness
7. **Agent test** — Have an AI agent complete a real task using only the CLI

### Phase 6: Test Documentation (TEST.md - Part 2)

After running all tests successfully, **append** to the existing TEST.md:

1. **Test Results** — Paste the full `pytest -v --tb=no` output showing all tests
   passing with their names and status
2. **Summary Statistics** — Total tests, pass rate, execution time
3. **Coverage Notes** — Any gaps or areas not covered by tests

The TEST.md now serves as both the test plan (written before implementation) and
the test results documentation (appended after execution), providing a complete
record of the testing process.

### Phase 6.5: SKILL.md Generation

Generate a SKILL.md file that makes the CLI discoverable and usable by AI agents
through the skill-creator methodology. This file serves as a self-contained skill
definition that can be loaded by Claude Code or other AI assistants.

**Purpose:** SKILL.md files follow a standard format that enables AI agents to:
- Discover the CLI's capabilities
- Understand command structure and usage
- Generate correct command invocations
- Handle output programmatically

**SKILL.md Structure:**

1. **YAML Frontmatter** — Triggering metadata for skill discovery:
   ```yaml
   ---
   name: "cli-anything-<software>"
   description: "Brief description of what the CLI does"
   ---
   ```

2. **Markdown Body** — Installation prerequisites, command syntax, command groups,
   usage examples, and agent-specific guidance (JSON output, error handling).

**Generation & Customization:** Use `skill_generator.py` to extract CLI metadata
automatically, or customize via the Jinja2 template at `templates/SKILL.md.template`.
See [`guides/skill-generation.md`](guides/skill-generation.md) for the full generation
process, template customization options, and manual generation commands.

**Output Location:** The canonical skill lives at
`skills/cli-anything-<software>/SKILL.md`. A compatibility copy is also written to
`cli_anything/<software>/skills/SKILL.md` so installed harnesses still ship a
local skill file.

**Key Principles:**

- SKILL.md must be self-contained (no external dependencies for understanding)
- Include agent-specific guidance for programmatic usage
- Document `--json` flag usage for machine-readable output
- List all command groups with brief descriptions
- Provide realistic examples that demonstrate common workflows

**Skill Path in CLI Banner:**

ReplSkin prefers the repo-root canonical skill path and falls back to the
packaged `skills/SKILL.md` copy. AI agents can read the displayed path to learn
the CLI's full capabilities.

**Package Data:** Ensure `setup.py` includes the skill file so it ships with pip:

```python
package_data={
    "cli_anything.<software>": ["skills/*.md"],
},
```

### Phase 7: PyPI Publishing and Installation

After building and testing the CLI, make it installable and discoverable using
**PEP 420 namespace packages** under the shared `cli_anything` namespace.

See [`guides/pypi-publishing.md`](guides/pypi-publishing.md) for the full setup.py template,
namespace package structure, import conventions, and verification steps.

**Key rule:** `cli_anything/` has **no** `__init__.py` (namespace package). Each
sub-package (`gimp/`, `blender/`, etc.) **does** have `__init__.py`.

## Architecture Patterns & Pitfalls

### Use the Real Software — Don't Reimplement It

**This is the #1 rule.** The CLI MUST call the actual software for rendering and
export — not reimplement the software's functionality in Python.

**The anti-pattern:** Building a Pillow-based image compositor to replace GIMP,
or generating bpy scripts without ever calling Blender. This produces a toy that
can't handle real workloads and diverges from the actual software's behavior.

**The correct approach:**
1. **Use the software's CLI/scripting interface** as the backend:
   - LibreOffice: `libreoffice --headless --convert-to pdf/docx/xlsx/pptx`
   - Blender: `blender --background --python script.py`
   - GIMP: `gimp -i -b '(script-fu-console-eval ...)'`
   - Inkscape: `inkscape --actions="..." --export-filename=...`
   - Shotcut/Kdenlive: `melt project.mlt -consumer avformat:output.mp4`
   - Audacity: `sox` for effects processing
   - OBS: `obs-websocket` protocol

2. **The software is a required dependency**, not optional. Add it to installation
   instructions. The CLI is useless without the actual software.

3. **Generate valid project/intermediate files** (ODF, MLT XML, .blend, SVG, etc.)
   then hand them to the real software for rendering. Your CLI is a structured
   command-line interface to the software, not a replacement for it.

**Example — LibreOffice CLI export pipeline:**
```python
# 1. Build the document as a valid ODF file (our XML builder)
odf_path = write_odf(tmp_path, doc_type, project)

# 2. Convert via the REAL LibreOffice (not a reimplementation)
subprocess.run([
    "libreoffice", "--headless",
    "--convert-to", "pdf",
    "--outdir", output_dir,
    odf_path,
])
# Result: a real PDF rendered by LibreOffice's full engine
```

### The Rendering Gap

**This is the #2 pitfall.** Most GUI apps apply effects at render time via their
engine. When you build a CLI that manipulates project files directly, you must also
handle rendering — and naive approaches will silently drop effects.

**The problem:** Your CLI adds filters/effects to the project file format. But when
rendering, if you use a simple tool (e.g., ffmpeg concat demuxer), it reads raw
media files and **ignores** all project-level effects. The output looks identical to
the input. Users can't tell anything happened.

**The solution — a filter translation layer:**
1. **Best case:** Use the app's native renderer (`melt` for MLT projects). It reads
   the project file and applies everything.
2. **Fallback:** Build a translation layer that converts project-format effects into
   the rendering tool's native syntax (e.g., MLT filters → ffmpeg `-filter_complex`).
3. **Last resort:** Generate a render script the user can run manually.

**Priority order for rendering:** native engine → translated filtergraph → script.

### MCP Backend Pattern

For software that exposes an MCP (Model Context Protocol) server instead of a traditional
CLI (e.g., DOMShell for browser automation). See [`guides/mcp-backend.md`](guides/mcp-backend.md)
for the full backend wrapper pattern, session management, daemon mode, and example implementations.

**Use when:** no native CLI exists, software has an MCP server, or you need agent-native tool integration.

### Filter Translation Pitfalls

When translating effects between formats (e.g., MLT → ffmpeg), watch for duplicate filter
merging, interleaved stream ordering, parameter scale differences, and unmappable effects.
See [`guides/filter-translation.md`](guides/filter-translation.md) for detailed rules and examples.

### Timecode Precision

Non-integer frame rates (29.97fps) cause cumulative rounding errors. Key rules: use
`round()` not `int()`, use integer arithmetic for display, accept ±1 frame tolerance.
See [`guides/timecode-precision.md`](guides/timecode-precision.md) for the full approach.

### Output Verification Methodology

Never assume an export is correct just because it ran without errors. Verify:

```python
# Video: probe specific frames with ffmpeg
# Frame 0 for fade-in (should be near-black)
# Middle frames for color effects (compare brightness/saturation vs source)
# Last frame for fade-out (should be near-black)

# When comparing pixel values between different resolutions,
# exclude letterboxing/pillarboxing (black padding bars).
# A vertical video in a horizontal frame will have ~40% black pixels.

# Audio: check RMS levels at start/end for fades
# Compare spectral characteristics against source
```

### Testing Strategy

Four test layers with complementary purposes:

1. **Unit tests** (`test_core.py`): Synthetic data, no external dependencies. Tests
   every function in isolation. Fast, deterministic, good for CI.
2. **E2E tests — native** (`test_full_e2e.py`): Tests the project file generation
   pipeline (ODF structure, XML content, format validation). Verifies the
   intermediate files your CLI produces are correct.
3. **E2E tests — true backend** (`test_full_e2e.py`): Invokes the **real software**
   (LibreOffice, Blender, melt, etc.) to produce final output files (PDF, DOCX,
   rendered images, videos). Verifies the output files:
   - Exist and have size > 0
   - Have correct format (magic bytes, ZIP structure, etc.)
   - Contain expected content where verifiable
   - **Print artifact paths** so users can manually inspect results
4. **CLI subprocess tests** (in `test_full_e2e.py`): Invokes the installed
   `cli-anything-<software>` command via `subprocess.run` to run the full workflow
   end-to-end: create project → add content → export via real software → verify output.

**No graceful degradation.** The real software MUST be installed. Tests must NOT
skip or fake results when the software is missing — the CLI is useless without it.
The software is a hard dependency, not optional.

**Example — true E2E test for LibreOffice:**
```python
class TestWriterToPDF:
    def test_rich_writer_to_pdf(self, tmp_dir):
        proj = create_document(doc_type="writer", name="Report")
        add_heading(proj, text="Quarterly Report", level=1)
        add_table(proj, rows=3, cols=3, data=[...])

        pdf_path = os.path.join(tmp_dir, "report.pdf")
        result = export(proj, pdf_path, preset="pdf", overwrite=True)

        # Verify the REAL output file
        assert os.path.exists(result["output"])
        assert result["file_size"] > 1000  # Not suspiciously small
        with open(result["output"], "rb") as f:
            assert f.read(5) == b"%PDF-"  # Validate format magic bytes
        print(f"\n  PDF: {result['output']} ({result['file_size']:,} bytes)")


class TestCLISubprocessE2E:
    CLI_BASE = _resolve_cli("cli-anything-libreoffice")

    def test_full_writer_pdf_workflow(self, tmp_dir):
        proj_path = os.path.join(tmp_dir, "test.json")
        pdf_path = os.path.join(tmp_dir, "output.pdf")
        self._run(["document", "new", "-o", proj_path, "--type", "writer"])
        self._run(["--project", proj_path, "writer", "add-heading", "-t", "Title"])
        self._run(["--project", proj_path, "export", "render", pdf_path, "-p", "pdf", "--overwrite"])
        assert os.path.exists(pdf_path)
        with open(pdf_path, "rb") as f:
            assert f.read(5) == b"%PDF-"
```

   Run tests in force-installed mode to guarantee the real command is used:
   ```bash
   CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s
   ```
   The `-s` flag shows the `[_resolve_cli]` print output confirming which backend
   is being used and **prints artifact paths** for manual inspection.

Real-world workflow test scenarios should include:
- Multi-segment editing (YouTube-style cut/trim)
- Montage assembly (many short clips)
- Picture-in-picture compositing
- Color grading pipelines
- Audio mixing (podcast-style)
- Heavy undo/redo stress testing
- Save/load round-trips of complex projects
- Iterative refinement (add, modify, remove, re-add)

## Principles & Rules

These are non-negotiable. Every harness MUST follow all of them.

**Backend & Rendering:**
- **The real software is a hard dependency.** The CLI MUST invoke the actual application
  (LibreOffice, Blender, GIMP, etc.) for rendering and export. Do NOT reimplement
  rendering in Python. Do NOT gracefully degrade to a fallback library. If the software
  is not installed, error with clear install instructions.
- **Manipulate the native format directly** — Parse and modify the app's native project
  files (MLT XML, ODF, SVG, etc.) as the data layer.
- **Leverage existing CLI tools** — Use `libreoffice --headless`, `blender --background`,
  `melt`, `ffmpeg`, `inkscape --actions`, `sox` as subprocesses for rendering.
- **Verify rendering produces correct output** — See "The Rendering Gap" in
  Architecture Patterns & Pitfalls above.
- **Every filter/effect in the registry MUST have a corresponding render mapping**
  or be explicitly documented as "project-only (not rendered)".

**CLI Design:**
- **Fail loudly and clearly** — Agents need unambiguous error messages to self-correct.
- **Be idempotent where possible** — Running the same command twice should be safe.
- **Provide introspection** — `info`, `list`, `status` commands are critical for agents
  to understand current state before acting.
- **JSON output mode** — Every command MUST support `--json` for machine parsing.
- **Use the unified REPL skin** — Copy `cli-anything-plugin/repl_skin.py` to
  `utils/repl_skin.py` and use `ReplSkin` for banner, prompt, help, and messages.
  REPL MUST be the default behavior (`invoke_without_command=True`).

**Testing:**
- **E2E tests MUST invoke the real software** and produce real output files (PDF, DOCX,
  rendered images, videos). Verify output exists, has correct format (magic bytes, ZIP
  structure), and print artifact paths for manual inspection. Never test only
  intermediate files.
- **Every export/render function MUST be verified** with programmatic output analysis.
  "It ran without errors" is not sufficient.
- **E2E tests MUST include subprocess tests** that invoke the installed
  `cli-anything-<software>` command via `_resolve_cli()`. Tests must work against
  the actual installed package, not just source imports.
- **Test suites MUST include real-file E2E tests**, not just unit tests with synthetic
  data. Format assumptions break constantly with real media.

**Documentation:**
- **Every `cli_anything/<software>/` directory MUST contain a `README.md`** explaining
  how to install the software dependency, install the CLI, run tests, and basic usage.
- **Every `cli_anything/<software>/tests/` directory MUST contain a `TEST.md`**
  documenting test coverage, realistic workflows tested, and full test results output.

## Directory Structure

```
<software>/
└── agent-harness/
    ├── <SOFTWARE>.md          # Project-specific analysis and SOP
    ├── setup.py               # PyPI package configuration (Phase 7)
    ├── cli_anything/          # Namespace package (NO __init__.py here)
    │   └── <software>/        # Sub-package for this CLI
    │       ├── __init__.py
    │       ├── __main__.py    # python3 -m cli_anything.<software>
    │       ├── README.md      # HOW TO RUN — required
    │       ├── <software>_cli.py  # Main CLI entry point (Click + REPL)
    │       ├── core/          # Core modules (one per domain)
    │       │   ├── __init__.py
    │       │   ├── project.py     # Project create/open/save/info
    │       │   ├── ...            # Domain-specific modules
    │       │   ├── export.py      # Render pipeline + filter translation
    │       │   └── session.py     # Stateful session, undo/redo
    │       ├── utils/         # Shared utilities
    │       │   ├── __init__.py
    │       │   ├── <software>_backend.py  # Backend: invokes the real software
    │       │   └── repl_skin.py  # Unified REPL skin (copy from plugin)
    │       └── tests/         # Test suites
    │           ├── TEST.md        # Test documentation and results — required
    │           ├── test_core.py   # Unit tests (synthetic data)
    │           └── test_full_e2e.py # E2E tests (real files)
    └── examples/              # Example scripts and workflows
```

**Critical:** The `cli_anything/` directory must NOT contain an `__init__.py`.
This is what makes it a PEP 420 namespace package — multiple separately-installed
PyPI packages can each contribute a sub-package under `cli_anything/` without
conflicting. For example, `cli-anything-gimp` adds `cli_anything/gimp/` and
`cli-anything-blender` adds `cli_anything/blender/`, and both coexist in the
same Python environment.

Note: This HARNESS.md is part of the cli-anything-plugin. Individual software directories reference this file — do NOT duplicate it.

## Applying This to Other Software

This same SOP applies to any GUI application:

| Software | Backend CLI | Native Format | System Package | How the CLI Uses It |
|----------|-------------|---------------|----------------|-------------------|
| LibreOffice | `libreoffice --headless` | .odt/.ods/.odp (ODF ZIP) | `apt install libreoffice` | Generate ODF → convert to PDF/DOCX/XLSX/PPTX |
| Blender | `blender --background --python` | .blend-cli.json | `apt install blender` | Generate bpy script → Blender renders to PNG/MP4 |
| GIMP | `gimp -i -b '(script-fu ...)'` | .xcf | `apt install gimp` | Script-Fu commands → GIMP processes & exports |
| Inkscape | `inkscape --actions="..."` | .svg (XML) | `apt install inkscape` | Manipulate SVG → Inkscape exports to PNG/PDF |
| Shotcut/Kdenlive | `melt` or `ffmpeg` | .mlt (XML) | `apt install melt ffmpeg` | Build MLT XML → melt/ffmpeg renders video |
| Audacity | `sox` | .aup3 | `apt install sox` | Generate sox commands → sox processes audio |
| OBS Studio | `obs-websocket` | scene.json | `apt install obs-studio` | WebSocket API → OBS captures/records |
| Browser (DOMShell) | `npx @apireno/domshell` (MCP) | Accessibility Tree (virtual FS) | `npm install -g npx` (if needed) + Chrome ext | MCP SDK → DOMShell tools → filesystem navigation |

**The software is a required dependency, not optional.** The CLI generates valid
intermediate files (ODF, MLT XML, bpy scripts, SVG) and hands them to the real
software for rendering. This is what makes the CLI actually useful — it's a
command-line interface TO the software, not a replacement for it.

The pattern is always the same: **build the data → call the real software → verify
the output**.

## Guides Reference

Detailed guides live in `guides/`. Use this table to decide which ones to read
based on the software you're building a harness for.

**Why namespace packages:**
- Multiple CLIs coexist in the same Python environment without conflicts
- Clean, organized imports under a single `cli_anything` namespace
- Each CLI is independently installable/uninstallable via pip
- Agents can discover all installed CLIs via `cli_anything.*`
- Standard Python packaging — no hacks or workarounds

## Optional Modes

### `--economic` Mode

The `--economic` flag activates a token-constrained analysis mode designed for users
working with smaller context windows or who want faster, cheaper runs. When enabled,
it applies stricter budgets and reading strategies on top of the default exclusion rules.

**When to use:** If the target codebase is large and you are running on a model with
a limited context window, or you want to minimize token usage for cost or speed reasons.

**Token budget:** Keep all file content read during Phase 1 under **~50,000 tokens**
(~200KB of text). This leaves room for the prompt, instructions, and completion.

**File size limit:** Skip individual files larger than **100KB**. For important large
files, read only the first 200 lines to understand the interface.

**Priority reading order:**
1. README, CONTRIBUTING, docs/ (architecture overview)
2. CLI entry points and main() functions
3. Public API headers / interface definitions
4. Core module files (< 50KB each)
5. Plugin/extension interfaces
6. Configuration schemas

**Summarize, don't dump:** For large directories with many similar files (e.g., 50
filter implementations), read 2-3 representative examples and note the pattern.
Do not read all 50.

**Incremental deepening:** Start with high-level architecture files. Only drill into
implementation details for areas directly relevant to CLI design.
