<h1 align="center"><img src="assets/icon.png" alt="" width="64" style="vertical-align: middle;">&nbsp; CLI-Anything: Making ALL Software Agent-Native</h1>

<p align="center">
  <strong>Today's Software Serves Humans👨‍💻. Tomorrow's Users will be Agents🤖.<br>
CLI-Anything: Bridging the Gap Between AI Agents and the World's Software</strong><br>
</p>

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-5_min-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="#-demonstrations"><img src="https://img.shields.io/badge/Demos-9_Apps-green?style=for-the-badge" alt="Demos"></a>
  <a href="#-test-results"><img src="https://img.shields.io/badge/Tests-1%2C436_Passing-brightgreen?style=for-the-badge" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/click-≥8.0-green" alt="Click">
  <img src="https://img.shields.io/badge/pytest-100%25_pass-brightgreen" alt="Pytest">
  <img src="https://img.shields.io/badge/coverage-unit_%2B_e2e-orange" alt="Coverage">
  <img src="https://img.shields.io/badge/output-JSON_%2B_Human-blueviolet" alt="Output">
  <a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
<a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
</p>

**One Command Line**: Make any software agent-ready for OpenClaw, nanobot, Cursor, Claude Code, etc.  **[中文文档](README_CN.md)**

<p align="center">
  <img src="assets/cli-typing.gif" alt="CLI-Anything typing demo" width="800">
</p>

<p align="center">
  <img src="assets/teaser.png" alt="CLI-Anything Teaser" width="800">
</p>

---

🤔 Why CLI?
CLI is the universal interface for both humans and AI agents:

• **Structured & Composable** - Text commands match LLM format and chain for complex workflows

• **Lightweight & Universal** - Minimal overhead, works across all systems without dependencies

• **Self-Describing** - --help flags provide automatic documentation agents can discover

• **Proven Success** - Claude Code runs thousands of real workflows through CLI daily

• **Agent-First Design** - Structured JSON output eliminates parsing complexity

• **Deterministic & Reliable** - Consistent results enable predictable agent behavior

## 🚀 Quick Start

### Prerequisites

- **Claude Code** (with plugin support)
- **Python 3.10+**
- Target software installed (e.g., GIMP, Blender, LibreOffice, or your own application)

### Step 1: Add the Marketplace

CLI-Anything is distributed as a Claude Code plugin marketplace hosted on GitHub.


```bash
# Add the CLI-Anything marketplace
/plugin marketplace add HKUDS/CLI-Anything
```

### Step 2: Install the Plugin


```bash
# Install the cli-anything plugin from the marketplace
/plugin install cli-anything
```

That's it. The plugin is now available in your Claude Code session.

### Step 3: Build a CLI in One Command


```bash
# /cli-anything <software-path-or-repo>
# Generate a complete CLI for GIMP (all 7 phases)
/cli-anything ./gimp
```

This runs the full pipeline:

1. 🔍 **Analyze** — Scans source code, maps GUI actions to APIs
2. 📐 **Design** — Architects command groups, state model, output formats
3. 🔨 **Implement** — Builds Click CLI with REPL, JSON output, undo/redo
4. 📋 **Plan Tests** — Creates TEST.md with unit + E2E test plans
5. 🧪 **Write Tests** — Implements comprehensive test suite
6. 📝 **Document** — Updates TEST.md with results
7. 📦 **Publish** — Creates `setup.py`, installs to PATH

### Step 4: Use the CLI


```bash
# Install to PATH
cd gimp/agent-harness && pip install -e .

# Use from anywhere
cli-anything-gimp --help
cli-anything-gimp project new --width 1920 --height 1080 -o poster.json
cli-anything-gimp --json layer add -n "Background" --type solid --color "#1a1a2e"

# Enter interactive REPL
cli-anything-gimp
```

<details>
<summary><strong>Alternative: Manual Installation</strong></summary>

If you prefer not to use the marketplace:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git

# Copy plugin to Claude Code plugins directory
cp -r CLI-Anything/cli-anything-plugin ~/.claude/plugins/cli-anything

# Reload plugins
/reload-plugins
```

</details>

---

💡 CLI-Anything's Vision: Building Agent-Native Software
• 🌐 **Universal Access** - Every software becomes instantly agent-controllable through structured CLI.

• 🔗 **Seamless Integration** - Agents control any application without APIs, GUI, rebuilding or complex wrappers.

• 🚀 **Future-Ready Ecosystem** - Transform human-designed software into agent-native tools with one command.

---

🔧 When to Use CLI-Anything

| Category                           | How to be Agent-native                                                                                                | Notable Examples                                                                                                          |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **📂 GitHub Repositories**         | Transform any open-source project into agent-controllable tools through automatic CLI generation                      | VSCodium, WordPress, Calibre, Zotero, Joplin, Logseq, Penpot, Super Productivity                                          |
| **🤖 AI/ML Platforms**             | Automate model training, inference pipelines, and hyperparameter tuning through structured commands                   | Stable Diffusion WebUI, ComfyUI, InvokeAI, Text-generation-webui, Open WebUI, Fooocus, Kohya_ss, AnythingLLM, SillyTavern |
| **📊 Data & Analytics**            | Enable programmatic data processing, visualization, and statistical analysis workflows                                | JupyterLab, Apache Superset, Metabase, Redash, DBeaver, KNIME, Orange, OpenSearch Dashboards, Lightdash                   |
| **💻 Development Tools**           | Streamline code editing, building, testing, and deployment processes via command interfaces                           | Jenkins, Gitea, Hoppscotch, Portainer, pgAdmin, SonarQube, ArgoCD, OpenLens, Insomnia, Beekeeper Studio                   |
| **🎨 Creative & Media**            | Control content creation, editing, and rendering workflows programmatically                                           | Blender, GIMP, OBS Studio, Audacity, Krita, Kdenlive, Shotcut, Inkscape, Darktable, LMMS, Ardour                          |
| **🔬 Scientific Computing**        | Automate research workflows, simulations, and complex calculations                                                    | ImageJ, FreeCAD, QGIS, ParaView, Gephi, LibreCAD, Stellarium, KiCad, JASP, Jamovi                                         |
| **🏢 Enterprise & Office**         | Convert business applications and productivity tools into agent-accessible systems                                    | NextCloud, GitLab, Grafana, Mattermost, LibreOffice, AppFlowy, NocoDB, Odoo (Community), Plane, ERPNext                   |
| **📐 Diagramming & Visualization** | Create and manipulate diagrams, flowcharts, architecture diagrams, and visual documentation programmatically          | Draw.io (diagrams.net), Mermaid, PlantUML, Excalidraw, yEd                                                                |
| **✨ AI Content Generation**        | Generate professional deliverables (slides, docs, diagrams, websites, research reports) through AI-powered cloud APIs | [AnyGen](https://www.anygen.io), Gamma, Beautiful.ai, Tome                                                                |

---

CLI-Anything's Key Features
### The Agent-Software Gap

AI agents are great at reasoning but terrible at using real professional software. Current solutions are fragile UI automation, limited APIs, or dumbed-down reimplementations that miss 90% of functionality.

**CLI-Anything's Solution**: Transform any professional software into agent-native tools without losing capabilities.

| **Current Pain Point**                 | **CLI-Anything's Fix**                                                                                                             |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| 🤖 "AI can't use real tools"           | Direct integration with actual software backends (Blender, LibreOffice, FFmpeg) — full professional capabilities, zero compromises |
| 💸 "UI automation breaks constantly"   | No screenshots, no clicking, no RPA fragility. Pure command-line reliability with structured interfaces                            |
| 📊 "Agents need structured data"       | Built-in JSON output for seamless agent consumption + human-readable formats for debugging                                         |
| 🔧 "Custom integrations are expensive" | One Claude plugin auto-generates CLIs for ANY codebase through proven 7-phase pipeline                                             |
| ⚡ "Prototype vs Production gap"        | 1,436+ tests with real software validation. Battle-tested across 9 major applications                                              |

---

🎯 What Can You Do with CLI-Anything?
<table>
<tr>
<td width="33%">

### 🛠️ Let Agents Take Your Workflows

Professional or everyday — just throw the codebase at `/cli-anything`. GIMP, Blender, Shotcut for creative work. LibreOffice, OBS Studio for daily tasks. Don't have the source? Find an open-source alternative and throw *that* in. You'll instantly get a full CLI your agents can use.

</td>
<td width="33%">

### 🔗 Unify Scattered APIs into One CLI

Tired of juggling fragmented web service APIs? Feed the docs or SDK manuscripts to `/cli-anything` and your agents get a **powerful, stateful CLI** that wraps those individual endpoints into coherent command groups. One tool instead of dozens of raw API calls — stronger capabilities while saving tokens.

</td>
<td width="33%">

### 🚀 Replace or Supercharge GUI Agents

CLI-Anything can flat-out **replace GUI-based agent approaches** — no more screenshots, no brittle pixel-clicking. But here's the fun part: once you `/cli-anything` a GUI software, you can **synthesize agent tasks, evaluators, and benchmarks** entirely via code and terminal — fully automated, iteratively refinable, massively more efficient.

</td>
</tr>
</table>

---

✨ ⚙️ How CLI-Anything Works
<table>
<tr>
<td width="50%">

### 🏗️ Fully Automated 7-Phase Pipeline
From codebase analysis to PyPI publishing — the plugin handles architecture design, implementation, test planning, test writing, and documentation completely automatically.

</td>
<td width="50%">

### 🎯 Authentic Software Integration
Direct calls to real applications for actual rendering. LibreOffice generates PDFs, Blender renders 3D scenes, Audacity processes audio via sox. **Zero compromises**, **Zero toy implementations**.

</td>
</tr>
<tr>
<td width="50%">

### 🔁 Smart Session Management
Persistent project state with undo/redo capabilities, plus unified REPL interface (ReplSkin) that delivers consistent interactive experience across all CLIs.

</td>
<td width="50%">

### 📦 Zero-Config Installation
Simple pip install -e . puts cli-anything-<software> directly on PATH. Agents discover tools via standard which commands. No setup, no wrappers.

</td>
</tr>
<tr>
<td width="50%">

### 🧪 Production-Grade Testing
Multi-layered validation: unit tests with synthetic data, end-to-end tests with real files and software, plus CLI subprocess verification of installed commands.

</td>
<td width="50%">

### 🐍 Clean Package Architecture
All CLIs organized under cli_anything.* namespace — conflict-free, pip-installable, with consistent naming: cli-anything-gimp, cli-anything-blender, etc.

</td>
</tr>
</table>

---

🎬 Demonstrations
### 🎯 General-Purpose

CLI-Anything works on any software with a codebase — no domain restrictions or architectural limitations.

### 🏭 Professional-Grade Testing

Tested across 9 diverse, complex open-source applications spanning creative, productivity, and diagramming domains previously inaccessible to AI agents.

### 🎨 Diverse Domain Coverage

From creative workflows (image editing, 3D modeling, vector graphics) to production tools (audio, office, live streaming, video editing).

### ✅ Full CLI Generation

Each application received complete, production-ready CLI interfaces — not demos, but comprehensive tool access preserving full capabilities.

<table>
<tr>
<th align="center">Software</th>
<th align="center">Domain</th>
<th align="center">CLI Command</th>
<th align="center">Backend</th>
<th align="center">Tests</th>
</tr>
<tr>
<td align="center"><strong>🎨 GIMP</strong></td>
<td>Image Editing</td>
<td><code>cli-anything-gimp</code></td>
<td>Pillow + GEGL/Script-Fu</td>
<td align="center">✅ 107</td>
</tr>
<tr>
<td align="center"><strong>🧊 Blender</strong></td>
<td>3D Modeling & Rendering</td>
<td><code>cli-anything-blender</code></td>
<td>bpy (Python scripting)</td>
<td align="center">✅ 208</td>
</tr>
<tr>
<td align="center"><strong>✏️ Inkscape</strong></td>
<td>Vector Graphics</td>
<td><code>cli-anything-inkscape</code></td>
<td>Direct SVG/XML manipulation</td>
<td align="center">✅ 202</td>
</tr>
<tr>
<td align="center"><strong>🎵 Audacity</strong></td>
<td>Audio Production</td>
<td><code>cli-anything-audacity</code></td>
<td>Python wave + sox</td>
<td align="center">✅ 161</td>
</tr>
<tr>
<td align="center"><strong>📄 LibreOffice</strong></td>
<td>Office Suite (Writer, Calc, Impress)</td>
<td><code>cli-anything-libreoffice</code></td>
<td>ODF generation + headless LO</td>
<td align="center">✅ 158</td>
</tr>
<tr>
<td align="center"><strong>📹 OBS Studio</strong></td>
<td>Live Streaming & Recording</td>
<td><code>cli-anything-obs-studio</code></td>
<td>JSON scene + obs-websocket</td>
<td align="center">✅ 153</td>
</tr>
<tr>
<td align="center"><strong>🎞️ Kdenlive</strong></td>
<td>Video Editing</td>
<td><code>cli-anything-kdenlive</code></td>
<td>MLT XML + melt renderer</td>
<td align="center">✅ 155</td>
</tr>
<tr>
<td align="center"><strong>🎬 Shotcut</strong></td>
<td>Video Editing</td>
<td><code>cli-anything-shotcut</code></td>
<td>Direct MLT XML + melt</td>
<td align="center">✅ 154</td>
</tr>
<tr>
<td align="center"><strong>📐 Draw.io</strong></td>
<td>Diagramming</td>
<td><code>cli-anything-drawio</code></td>
<td>mxGraph XML + draw.io CLI</td>
<td align="center">✅ 138</td>
</tr>
<tr>
<td align="center" colspan="4"><strong>Total</strong></td>
<td align="center"><strong>✅ 1,436</strong></td>
</tr>
</table>

> **100% pass rate** across all 1,436 tests — 1,011 unit tests + 425 end-to-end tests.
---

📊 Test Results
Each CLI harness undergoes rigorous multi-layered testing to ensure production reliability:

| Layer                        | What it tests                                        | Example                                                            |
| ---------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| **Unit tests**               | Every core function in isolation with synthetic data | `test_core.py` — project creation, layer ops, filter params        |
| **E2E tests (native)**       | Project file generation pipeline                     | Valid ODF ZIP structure, correct MLT XML, SVG well-formedness      |
| **E2E tests (true backend)** | Real software invocation + output verification       | LibreOffice → PDF with `%PDF-` magic bytes, Blender → rendered PNG |
| **CLI subprocess tests**     | Installed command via `subprocess.run`               | `cli-anything-gimp --json project new` → valid JSON output         |


```
================================ Test Summary ================================
gimp          107 passed  ✅   (64 unit + 43 e2e)
blender       208 passed  ✅   (150 unit + 58 e2e)
inkscape      202 passed  ✅   (148 unit + 54 e2e)
audacity      161 passed  ✅   (107 unit + 54 e2e)
libreoffice   158 passed  ✅   (89 unit + 69 e2e)
obs-studio    153 passed  ✅   (116 unit + 37 e2e)
kdenlive      155 passed  ✅   (111 unit + 44 e2e)
shotcut       154 passed  ✅   (110 unit + 44 e2e)
drawio        138 passed  ✅   (116 unit + 22 e2e)
──────────────────────────────────────────────────────────────────────────────
TOTAL        1,436 passed  ✅   100% pass rate
```

---

🏗️ CLI-Anything's Architecture
<p align="center">
  <img src="assets/architecture.png" alt="CLI-Anything Architecture" width="750">
</p>

### 🎯 Core Design Principles

1. **Authentic Software Integration** — The CLI generates valid project files (ODF, MLT XML, SVG) and delegates to real applications for rendering. **We build structured interfaces TO software, not replacements**.
2. **Flexible Interaction Models** — Every CLI operates in dual modes: stateful REPL for interactive agent sessions + subcommand interface for scripting/pipelines. **Run bare command → enter REPL mode**.
3. **Consistent User Experience** — All generated CLIs share unified REPL interface (repl_skin.py) with branded banners, styled prompts, command history, progress indicators, and standardized formatting.
4. **Agent-Native Design** — Built-in --json flag on every command delivers structured data for machine consumption, while human-readable tables serve interactive use. **Agents discover capabilities via standard --help and which commands**.
5. **Zero Compromise Dependencies** — Real software is a hard requirement — no fallbacks, no graceful degradation. **Tests fail (not skip) when backends are missing, ensuring authentic functionality**.
---

📂 Project Structure

```
cli-anything/
├── 📄 README.md                          # You are here
├── 📁 assets/                            # Images and media
│   ├── icon.png                          # Project icon
│   └── teaser.png                        # Teaser figure
│
├── 🔌 cli-anything-plugin/               # The Claude Code plugin
│   ├── HARNESS.md                        # Methodology SOP (source of truth)
│   ├── README.md                         # Plugin documentation
│   ├── QUICKSTART.md                     # 5-minute getting started
│   ├── PUBLISHING.md                     # Distribution guide
│   ├── repl_skin.py                      # Unified REPL interface
│   ├── commands/                         # Plugin command definitions
│   │   ├── cli-anything.md               # Main build command
│   │   ├── refine.md                     # Expand existing harness coverage
│   │   ├── test.md                       # Test runner
│   │   └── validate.md                   # Standards validation
│   └── scripts/
│       └── setup-cli-anything.sh         # Setup script
│
├── 🎨 gimp/agent-harness/               # GIMP CLI (107 tests)
├── 🧊 blender/agent-harness/            # Blender CLI (208 tests)
├── ✏️ inkscape/agent-harness/            # Inkscape CLI (202 tests)
├── 🎵 audacity/agent-harness/           # Audacity CLI (161 tests)
├── 📄 libreoffice/agent-harness/        # LibreOffice CLI (158 tests)
├── 📹 obs-studio/agent-harness/         # OBS Studio CLI (153 tests)
├── 🎞️ kdenlive/agent-harness/           # Kdenlive CLI (155 tests)
├── 🎬 shotcut/agent-harness/            # Shotcut CLI (154 tests)
└── 📐 drawio/agent-harness/             # Draw.io CLI (138 tests)
```

Each `agent-harness/` contains an installable Python package under `cli_anything.<software>/` with Click CLI, core modules, utils (including `repl_skin.py` and backend wrapper), and comprehensive tests.

---

🎯 Plugin Commands

| Command                                          | Description                                                    |
| ------------------------------------------------ | -------------------------------------------------------------- |
| `/cli-anything <software-path-or-repo>`          | Build complete CLI harness — all 7 phases                      |
| `/cli-anything:refine <software-path> [focus]`   | Refine an existing harness — expand coverage with gap analysis |
| `/cli-anything:test <software-path-or-repo>`     | Run tests and update TEST.md with results                      |
| `/cli-anything:validate <software-path-or-repo>` | Validate against HARNESS.md standards                          |

### Examples


```bash
# Build a complete CLI for GIMP from local source
/cli-anything /home/user/gimp

# Build from a GitHub repo
/cli-anything https://github.com/blender/blender

# Refine an existing harness — broad gap analysis
/cli-anything:refine /home/user/gimp

# Refine with a specific focus area
/cli-anything:refine /home/user/shotcut "vid-in-vid and picture-in-picture compositing"

# Run tests and update TEST.md
/cli-anything:test /home/user/inkscape

# Validate against HARNESS.md standards
/cli-anything:validate /home/user/audacity
```

---

🎮 Demo: Using a Generated CLI
Here's what an agent can do with `cli-anything-libreoffice`:


```bash
# Create a new Writer document
$ cli-anything-libreoffice document new -o report.json --type writer
✓ Created Writer document: report.json

# Add content
$ cli-anything-libreoffice --project report.json writer add-heading -t "Q1 Report" --level 1
✓ Added heading: "Q1 Report"

$ cli-anything-libreoffice --project report.json writer add-table --rows 4 --cols 3
✓ Added 4×3 table

# Export to real PDF via LibreOffice headless
$ cli-anything-libreoffice --project report.json export render output.pdf -p pdf --overwrite
✓ Exported: output.pdf (42,831 bytes) via libreoffice-headless

# JSON mode for agent consumption
$ cli-anything-libreoffice --json document info --project report.json
{
  "name": "Q1 Report",
  "type": "writer",
  "pages": 1,
  "elements": 2,
  "modified": true
}
```

### REPL Mode


```
$ cli-anything-blender
╔══════════════════════════════════════════╗
║       cli-anything-blender v1.0.0       ║
║     Blender CLI for AI Agents           ║
╚══════════════════════════════════════════╝

blender> scene new --name ProductShot
✓ Created scene: ProductShot

blender[ProductShot]> object add-mesh --type cube --location 0 0 1
✓ Added mesh: Cube at (0, 0, 1)

blender[ProductShot]*> render execute --output render.png --engine CYCLES
✓ Rendered: render.png (1920×1080, 2.3 MB) via blender --background

blender[ProductShot]> exit
Goodbye! 👋
```

---

📖 The Standard Playbook: HARNESS.md
HARNESS.md is our definitive SOP for making any software agent-accessible via automated CLI generation.

It encodes proven patterns and methodologies refined through automated generation processes.

The playbook distills key insights from successfully building all 8 diverse, production-ready harnesses.

### Critical Lessons

| Lesson                    | Description                                                                                                                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Use the real software** | The CLI MUST call the actual application for rendering. No Pillow replacements for GIMP, no custom renderers for Blender. Generate valid project files → invoke the real backend.                        |
| **The Rendering Gap**     | GUI apps apply effects at render time. If your CLI manipulates project files but uses a naive export tool, effects get silently dropped. Solution: native renderer → filter translation → render script. |
| **Filter Translation**    | When mapping effects between formats (MLT → ffmpeg), watch for duplicate filter merging, interleaved stream ordering, parameter space differences, and unmappable effects.                               |
| **Timecode Precision**    | Non-integer frame rates (29.97fps) cause cumulative rounding. Use `round()` not `int()`, integer arithmetic for display, and ±1 frame tolerance in tests.                                                |
| **Output Verification**   | Never trust that export worked because it exited 0. Verify: magic bytes, ZIP/OOXML structure, pixel analysis, audio RMS levels, duration checks.                                                         |

> See the full methodology: `cli-anything-plugin/HARNESS.md`
---

📦 Installation & Usage
### For Plugin Users (Claude Code)


```bash
# Add marketplace & install (recommended)
/plugin marketplace add HKUDS/CLI-Anything
/plugin install cli-anything

# Build a CLI for any software with a codebase
/cli-anything <software-name>
```

### For Generated CLIs


```bash
# Install any generated CLI
cd <software>/agent-harness
pip install -e .

# Verify
which cli-anything-<software>

# Use
cli-anything-<software> --help
cli-anything-<software>                    # enters REPL
cli-anything-<software> --json <command>   # JSON output for agents
```

### Running Tests


```bash
# Run tests for a specific CLI
cd <software>/agent-harness
python3 -m pytest cli_anything/<software>/tests/ -v

# Force-installed mode (recommended for validation)
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s
```

---

🤝 Contributing
We welcome contributions! CLI-Anything is designed to be extensible:

- **New software targets** — Use the plugin to generate a CLI for any software with a codebase, then submit your harness via `cli-anything-plugin/PUBLISHING.md`.
- **Methodology improvements** — PRs to `HARNESS.md` that encode new lessons learned
- **Plugin enhancements** — New commands, phase improvements, better validation
- **Test coverage** — More E2E scenarios, edge cases, workflow tests

### Roadmap

- [ ] Support for more application categories (CAD, DAW, IDE, EDA, scientific tools)
- [ ] Benchmark suite for agent task completion rates
- [ ] Community-contributed CLI harnesses for internal/custom software
- [ ] Integration with additional agent frameworks beyond Claude Code
- [ ] Support packaging APIs for closed-source software and web services into CLIs
- [ ] Produce SKILL.md alongside the CLI for agent skill discovery and orchestration
---

📖 Documentation

| Document                            | Description                                      |
| ----------------------------------- | ------------------------------------------------ |
| `cli-anything-plugin/HARNESS.md`    | The methodology SOP — single source of truth     |
| `cli-anything-plugin/README.md`     | Plugin documentation — commands, options, phases |
| `cli-anything-plugin/QUICKSTART.md` | 5-minute getting started guide                   |
| `cli-anything-plugin/PUBLISHING.md` | Distribution and publishing guide                |

Each generated harness also includes:

- `<SOFTWARE>.md` — Architecture SOP specific to that application
- `tests/TEST.md` — Test plan and results documentation
---

⭐ Star History
If CLI-Anything helps make your software Agent-native, give us a star! ⭐

<div align="center">
  <a href="https://star-history.com/#HKUDS/CLI-Anything&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
    </picture>
  </a>
</div>

---

📄 License
MIT License — free to use, modify, and distribute.

<div align="center">

**CLI-Anything** — *Make any software with a codebase Agent-native.*

<sub>A methodology for the age of AI agents | 9 professional software demos | 1,436 passing tests</sub>

<br>&#8203;

<img src="assets/icon.png" alt="CLI-Anything Icon" width="80">

</div>

<p align="center">
  <em> Thanks for visiting ✨ CLI-Anything!</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.CLI-Anything&style=for-the-badge&color=00d4ff" alt="Views">
</p>

---
