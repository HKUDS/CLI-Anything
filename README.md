<h1 align="center"><img src="assets/icon.png" alt="" width="64" style="vertical-align: middle;">&nbsp; CLI-Anything: Making ALL Software Agent-Native</h1>

<p align="center">
  <strong>Today's Software Serves Humans👨‍💻. Tomorrow's Users will be Agents🤖.<br>
CLI-Anything: Bridging the Gap Between AI Agents and the World's Software</strong><br>
</p>

**🌐 [CLI-Hub](https://hkuds.github.io/CLI-Anything/)**: `pip install cli-anything-hub` then `cli-hub install <name>` — browse, install, and manage all community-built CLIs. Want to add your own? [Open a PR](https://github.com/HKUDS/CLI-Anything/blob/main/CONTRIBUTING.md) — the hub updates instantly.

**🎬 [See Demos](#-real-world-demos)**: Watch AI agents use generated CLIs to produce real artifacts — diagrams, gameplay, subtitles, and more.

**🙋 [Become a Contributor, or Request a CLI]**: [Join us](https://github.com/HKUDS/CLI-Anything/issues/new?template=contributor-signup.yml)! Sign up to build a new CLI harness — once reviewed and merged, you'll gain access as one of our community contributors! Wish CLI-Anything supported a specific software or service? Submit a [wishlist request](https://github.com/HKUDS/CLI-Anything/issues/new?template=cli-wishlist.yml)!

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-5_min-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="https://hkuds.github.io/CLI-Anything/"><img src="https://img.shields.io/badge/CLI_Hub-Browse_%26_Install-ff69b4?style=for-the-badge" alt="CLI Hub"></a>
  <a href="#-demonstrations"><img src="https://img.shields.io/badge/Demos-16_Apps-green?style=for-the-badge" alt="Demos"></a>
  <a href="#-test-results"><img src="https://img.shields.io/badge/Tests-2%2C130_Passing-brightgreen?style=for-the-badge" alt="Tests"></a>
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

**One Command Line**: Make any software agent-ready for Pi, OpenClaw, nanobot, Cursor, Claude Code, etc.&nbsp;&nbsp;[**中文文档**](README_CN.md) | [**日本語ドキュメント**](README_JA.md)

<p align="center">
  <img src="assets/cli-typing.gif" alt="CLI-Anything typing demo" width="800">
</p>

<p align="center">
  <img src="assets/teaser.png" alt="CLI-Anything Teaser" width="800">
</p>

---

## 📰 News

> Thanks to all invaluable efforts from the community! More updates continuously on the way everyday..

- **2026-04-10** 📦 **CLI-Hub package manager** launched — `pip install cli-anything-hub` to browse, install, and manage all CLIs. Download tracking via Umami analytics. Hub frontend updated with new install flow and "Empower yourself" toolkit card.

- **2026-04-09** 🧹 Cleanup and docs pass (#200) — fixed Openscreen test subtotals, added Openscreen to Chinese README and project structure.

- **2026-04-08** 🎬 **Openscreen CLI** merged (#183) — screen recording editor harness with 101 tests. ☁️ **CloudAnalyzer CLI** merged (#181) — cloud cost analysis harness with 27 commands. 🌊 **SeaClip / PM2 / ChromaDB** harnesses merged (#129).

- **2026-04-07** 🔄 **Dify Workflow CLI** merged (#191) — workflow automation wrapper. 🔧 **Inkscape** auto-save fix (#193, fixes #182). 🛡️ **DomShell security hardening** (#156) — URL validation and DOM sanitization for browser CLI. 🥧 **Pi Coding Agent extension** merged (#178).

- **2026-04-06** 🔍 **Exa CLI** merged (#172) — AI-powered web search and answers harness. 🎮 **Godot CLI** merged (#140) — game engine harness with full demo-game E2E pipeline. CLI-Hub frontend improvements.

- **2026-04-03** 🧪 **WireMock CLI** merged (#170) — HTTP mock server harness for API testing. Added CLI demo recordings to documentation.

- **2026-04-01** ⚔️ **Slay the Spire II CLI** merged (#148) — game harness for deck-building roguelike. 🎥 **VideoCaptioner CLI** merged (#166) — AI-powered video captioning harness. **IntelWatch** added to registry for B2B OSINT.

<details>
<summary>Earlier news (Mar 23–30)</summary>

- **2026-03-30** 🏗️ **CLI-Anything v0.2.0** — HARNESS.md progressive disclosure redesign. Detailed guides extracted into `guides/` for on-demand loading. Phases 1–7 now contiguous. Key Principles and Rules merged into a single authoritative section.

- **2026-03-29** 📐 Blender skill docs updated — enforce absolute render paths and correct prerequisites.

- **2026-03-28** 🌐 **CLIBrowser** added to CLI-Hub registry for agent-accessible browser automation.

- **2026-03-27** 📚 Zotero SKILL.md enhanced with agent-facing constraints; REPL config and executable resolution fixes.

- **2026-03-26** 📖 **Zotero CLI** harness landed for Zotero desktop (library management, collections, citations). Draw.io custom ID bugfix (#132) and registry.json syntax fix.

- **2026-03-25** 🎮 **RenderDoc CLI** merged for GPU frame capture analysis. FreeCAD updated for v1.1. Blender EEVEE engine name corrected. Zoom token permissions hardened.

- **2026-03-24** 🏭 **FreeCAD CLI** added with 258 commands across 17 groups. **iTerm2** and **Teltonika RMS** harnesses added to registry.

- **2026-03-23** 🤖 Launched **CLI-Hub meta-skill** — agents can now discover and install CLIs autonomously. **Krita CLI** harness merged for digital painting.

</details>

<details>
<summary>Earlier news (Mar 11–22)</summary>

- **2026-03-22** 🎵 **MuseScore CLI** merged with transpose, export, and instrument management.

- **2026-03-21** 🔧 Infrastructure improvements — refined test harnesses and documentation across multiple CLIs. Enhanced Windows compatibility for several backends.

- **2026-03-20** 🌐 **Novita AI** CLI added for OpenAI-compatible API access. Registry metadata improvements for better hub discovery.

- **2026-03-19** 📦 Package structure refinements across harnesses. Improved SKILL.md generation with better command documentation.

- **2026-03-18** 🧪 Test coverage expansion — additional E2E scenarios and edge case validation across multiple CLIs.

- **2026-03-17** 🌐 Launched the **[CLI-Hub](https://hkuds.github.io/CLI-Anything/)** — a central registry where you can browse, search, and install any CLI with a single `pip` command.

- **2026-03-16** 🤖 Added **SKILL.md generation** (Phase 6.5) — every generated CLI now ships with an AI-discoverable skill definition.

- **2026-03-15** 🐾 Support for **OpenClaw** from the community! Merged Windows `cygpath` guard for cross-platform support.

- **2026-03-14** 🔒 Fixed a GIMP Script-Fu path injection vulnerability and added **Japanese README** translation.

- **2026-03-13** 🔌 **Qodercli** plugin officially merged as a community contribution with dedicated setup scripts.

- **2026-03-12** 📦 **Codex skill** integration landed, bringing CLI-Anything to yet another AI coding platform.

- **2026-03-11** 📞 **Zoom** video conferencing harness added as the 11th supported application.

</details>

---

## 🤔 Why CLI?

CLI is the universal interface for both humans and AI agents:

• **Structured & Composable** - Text commands match LLM format and chain for complex workflows

• **Lightweight & Universal** - Minimal overhead, works across all systems without dependencies

• **Self-Describing** - --help flags provide automatic documentation agents can discover

• **Proven Success** - Claude Code runs thousands of real workflows through CLI daily

• **Agent-First Design** - Structured JSON output eliminates parsing complexity

• **Deterministic & Reliable** - Consistent results enable predictable agent behavior

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- Target software installed (e.g., GIMP, Blender, LibreOffice, or your own application)
- A supported AI coding agent: [Claude Code](#-claude-code) | [Pi](#-pi-coding-agent) | [OpenClaw](#-openclaw) | [OpenCode](#-opencode) | [Codex](#-codex) | [Qodercli](#-qodercli) | [GitHub Copilot CLI](#-github-copilot-cli) | [More Platforms](#-more-platforms-coming-soon)

### Pick Your Platform

<details open>
<summary><h4 id="-claude-code">⚡ Claude Code</h4></summary>

**Step 1: Add the Marketplace**

CLI-Anything is distributed as a Claude Code plugin marketplace hosted on GitHub.

```bash
# Add the CLI-Anything marketplace
/plugin marketplace add HKUDS/CLI-Anything
```

**Step 2: Install the Plugin**

```bash
# Install the cli-anything plugin from the marketplace
/plugin install cli-anything
```

That's it. The plugin is now available in your Claude Code session.

> **Note for Win Users:** Claude Code runs shell commands via `bash`. On Windows, install Git for Windows (includes `bash` and
`cygpath`) or use WSL; otherwise commands may fail with `cygpath: command not found`.

**Step 3: Build a CLI in One Command**

```bash
# /cli-anything:cli-anything <software-path-or-repo>
# Generate a complete CLI for GIMP (all 7 phases)
/cli-anything:cli-anything ./gimp

# Note: If your Claude Code is under 2.x, use "/cli-anything" instead.
```

This runs the full pipeline:
1. 🔍 **Analyze** — Scans source code, maps GUI actions to APIs
2. 📐 **Design** — Architects command groups, state model, output formats
3. 🔨 **Implement** — Builds Click CLI with REPL, JSON output, undo/redo
4. 📋 **Plan Tests** — Creates TEST.md with unit + E2E test plans
5. 🧪 **Write Tests** — Implements comprehensive test suite
6. 📝 **Document** — Updates TEST.md with results
7. 📦 **Publish** — Creates `setup.py`, installs to PATH

**Step 4 (Optional): Refine and Improve the CLI**

After the initial build, you can iteratively refine the CLI to expand coverage and add missing capabilities:

```bash
# Broad refinement — agent analyzes gaps across all capabilities
/cli-anything:refine ./gimp

# Focused refinement — target a specific functionality area
/cli-anything:refine ./gimp "I want more CLIs on image batch processing and filters"
```

The refine command performs gap analysis between the software's full capabilities and current CLI coverage, then implements new commands, tests, and documentation for the identified gaps. You can run it multiple times to steadily expand coverage — each run is incremental and non-destructive.

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

</details>

<details>
<summary><h4 id="-pi-coding-agent">⚡ Pi Coding Agent</h4></summary>

**Step 1: Install the Extension**

The extension lives at `.pi-extension/cli-anything/` in this repository. Install it globally so `/cli-anything` commands are available in **all** Pi projects:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything

# Install globally into Pi's extensions directory
bash .pi-extension/cli-anything/install.sh
```

To uninstall:

```bash
bash .pi-extension/cli-anything/install.sh --uninstall
```

> **How it works:** `install.sh` copies the extension files (including HARNESS.md, commands, guides, scripts, and templates from `cli-anything-plugin/`) into `~/.pi/agent/extensions/cli-anything/`, which Pi auto-discovers on startup. Run `/reload` in Pi or restart Pi to activate.

**Step 2: Build a CLI in One Command**

Once the extension is loaded, the following commands are available:

```bash
# Generate a complete CLI for GIMP (all 7 phases)
/cli-anything ./gimp

# Build from a GitHub repo
/cli-anything https://github.com/blender/blender
```

**Step 3 (Optional): Refine and Improve the CLI**

```bash
# Broad refinement — agent analyzes gaps across all capabilities
/cli-anything:refine ./gimp

# Focused refinement — target a specific functionality area
/cli-anything:refine ./gimp "batch processing and filters"
```

**Available Commands**

| Command | Description |
|---------|-------------|
| `/cli-anything <path-or-repo>` | Build a complete CLI harness |
| `/cli-anything:refine <path> [focus]` | Refine an existing CLI harness |
| `/cli-anything:test <path-or-repo>` | Run tests for a CLI harness |
| `/cli-anything:validate <path-or-repo>` | Validate a CLI harness |
| `/cli-anything:list [options]` | List all CLI-Anything tools |

</details>

<details>
<summary><h4 id="-opencode">⚡ OpenCode (Experimental)</h4></summary>

**Step 1: Install the Commands**

> **Note:** Please upgrade to the latest OpenCode. Older versions may use a different commands path.

Copy the CLI-Anything commands **and** `HARNESS.md` to your OpenCode commands directory:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git

# Global install (available in all projects)
cp CLI-Anything/opencode-commands/*.md ~/.config/opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md ~/.config/opencode/commands/

# Or project-level install
cp CLI-Anything/opencode-commands/*.md .opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md .opencode/commands/
```

> **Note:** `HARNESS.md` is the methodology spec that all commands reference. It must be in the same directory as the commands.

This adds 5 slash commands: `/cli-anything`, `/cli-anything-refine`, `/cli-anything-test`, `/cli-anything-validate`, and `/cli-anything-list`.

**Step 2: Build a CLI in One Command**

```bash
# Generate a complete CLI for GIMP (all 7 phases)
/cli-anything ./gimp

# Build from a GitHub repo
/cli-anything https://github.com/blender/blender
```

The command runs as a subtask and follows the same 7-phase methodology as Claude Code.

**Step 3 (Optional): Refine and Improve the CLI**

```bash
# Broad refinement — agent analyzes gaps across all capabilities
/cli-anything-refine ./gimp

# Focused refinement — target a specific functionality area
/cli-anything-refine ./gimp "batch processing and filters"
```

</details>

<details>
<summary><h4 id="-goose">⚡ Goose (Desktop / CLI) <sup><code>Experimental</code></sup> <sup><code>Community</code></sup></h4></summary>

**Step 1: Install Goose**

Install Goose (Desktop or CLI) using the official Goose instructions for your OS.

**Step 2: Configure a CLI Provider**

Configure Goose to use a CLI provider such as Claude Code, and make sure that CLI is installed and authenticated.

**Step 3: Use CLI-Anything in a Goose Session**

Once Goose is configured, start a session and use the same CLI-Anything commands described above for Claude Code, for example:

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "batch processing and filters"
```

> Note: When Goose runs through a CLI provider, it uses that provider's capabilities and command format.
</details>

<details>

<summary><h4 id="-qodercli">⚡ Qodercli <sup><code>Community</code></sup></h4></summary>

**Step 1: Register the Plugin**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
bash CLI-Anything/qoder-plugin/setup-qodercli.sh
```

This registers the cli-anything plugin in `~/.qoder.json`. Start a new Qodercli session after registration.

**Step 2: Use CLI-Anything from Qodercli**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "batch processing and filters"
/cli-anything:validate ./gimp
```
</details>

<details>

<summary><h4 id="-openclaw">⚡ OpenClaw <sup><code>Community</code></sup></h4></summary>

**Step 1: Install the Skill**

CLI-Anything provides a native OpenClaw `SKILL.md` file. Copy it to your OpenClaw skills directory:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git

# Install to the global skills folder
mkdir -p ~/.openclaw/skills/cli-anything
cp CLI-Anything/openclaw-skill/SKILL.md ~/.openclaw/skills/cli-anything/SKILL.md
```

**Step 2: Build a CLI**

Now you can invoke the skill inside OpenClaw:

`@cli-anything build a CLI for ./gimp`

The skill follows the same 7-phase methodology as Claude Code and OpenCode.

</details>

<details>

<summary><h4 id="-codex">⚡ Codex <sup><code>Experimental</code></sup> <sup><code>Community</code></sup></h4></summary>

**Step 1: Install the Skill**

Run the bundled installer:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git

# Install the skill
bash CLI-Anything/codex-skill/scripts/install.sh
```

On Windows PowerShell, use:

```powershell
.\CLI-Anything\codex-skill\scripts\install.ps1
```

This installs the skill to `$CODEX_HOME/skills/cli-anything` (or `~/.codex/skills/cli-anything` if `CODEX_HOME` is unset).

Restart Codex after installation so it is discovered.

**Step 2: Use CLI-Anything from Codex**

Describe the task in natural language, for example:

```text
Use CLI-Anything to build a harness for ./gimp
Use CLI-Anything to refine ./shotcut for picture-in-picture workflows
Use CLI-Anything to validate ./libreoffice
```

The Codex skill adapts the same methodology used by the Claude Code plugin and
OpenCode commands, while keeping the generated Python harness format unchanged.
</details>

<details>

<summary><h4 id="-github-copilot-cli">⚡ GitHub Copilot CLI <sup><code>Community</code></sup></h4></summary>

**Step 1: Install the Plugin**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything
copilot plugin install ./cli-anything-plugin
```

This installs the CLI-Anything plugin to GitHub Copilot CLI. The plugin should now be available in your GitHub Copilot CLI session.

**Step 2: Use CLI-Anything from GitHub Copilot CLI**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "batch processing and filters"
/cli-anything:validate ./gimp
```

</details>

<details>
<summary><h4 id="-more-platforms-coming-soon">🔮 More Platforms (Coming Soon)</h4></summary>

CLI-Anything is designed to be platform-agnostic. Support for more AI coding agents is planned:

- **Codex** — available via the bundled skill in `codex-skill/`
- **Cursor** — coming soon
- **Windsurf** — coming soon
- **Your favorite tool** — contributions welcome! See the `opencode-commands/` directory for a reference implementation.

</details>

### Use the Generated CLI

Regardless of which platform you used to build it, the generated CLI works the same way:

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

Each installed CLI ships with a [`SKILL.md`](#-skillmd-generation) inside the Python package (`cli_anything/<software>/skills/SKILL.md`). The REPL banner automatically displays the absolute path to this file so AI agents know exactly where to read the skill definition. No extra configuration needed — `pip install` makes the skill discoverable.

---

## 🤖 Empower Your Agents with CLI-Hub

CLI-Hub lets agents autonomously discover and install the CLIs they need — zero human intervention required.

We published a **meta-skill** that lets any AI agent freely explore the full catalog of community CLIs and pick the right one for the task.

**Install in one command:**

```bash
# OpenClaw
openclaw skills install cli-anything-hub

# nanobot
nanobot skills install cli-anything-hub
```

**Then just prompt your agent:**

```
Find appropriate CLI software in CLI-Hub and complete the task: <your task here>
```

The agent will browse the catalog, install whichever CLI fits the task, and use it — all autonomously.

**How it works under the hood:**

1. The meta-skill points to the live catalog at [`https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md`](https://reeceyang.sgp1.cdn.digitaloceanspaces.com/SKILL.md)
2. The agent reads 20+ CLIs organized by category with one-line `pip install` commands
3. The agent installs whichever CLI fits the task, then reads that CLI's own SKILL.md for detailed usage

The catalog auto-updates whenever `registry.json` changes — new community CLIs show up automatically.

> **For Claude Code users:** Copy [`cli-hub-meta-skill/SKILL.md`](cli-hub-meta-skill/SKILL.md) into your project or skills directory for the same automatic CLI discovery.

---

## 💡 CLI-Anything's Vision: Building Agent-Native Software

• 🌐 **Universal Access** - Every software becomes instantly agent-controllable through structured CLI.

• 🔗 **Seamless Integration** - Agents control any application without APIs, GUI, rebuilding or complex wrappers.

• 🚀 **Future-Ready Ecosystem** - Transform human-designed software into agent-native tools with one command.

---

## 🔧 When to Use CLI-Anything

| Category | How to be Agent-native | Notable Examples |
|----------|----------------------|----------|
| **📂 GitHub Repositories** | Transform any open-source project into agent-controllable tools through automatic CLI generation | VSCodium, WordPress, Calibre, Zotero, Joplin, Logseq, Penpot, Super Productivity |
| **🤖 AI/ML Platforms** | Automate model training, inference pipelines, and hyperparameter tuning through structured commands | Stable Diffusion WebUI, ComfyUI, Ollama, InvokeAI, Text-generation-webui, Open WebUI, Fooocus, Kohya_ss, AnythingLLM, SillyTavern |
| **📊 Data & Analytics** | Enable programmatic data processing, visualization, and statistical analysis workflows | JupyterLab, Apache Superset, Metabase, Redash, DBeaver, KNIME, Orange, OpenSearch Dashboards, Lightdash |
| **💻 Development Tools** | Streamline code editing, building, testing, and deployment processes via command interfaces | Jenkins, Gitea, Hoppscotch, Portainer, pgAdmin, SonarQube, ArgoCD, OpenLens, Insomnia, Beekeeper Studio, **[iTerm2](https://iterm2.com)** |
| **🎨 Creative & Media** | Control content creation, editing, and rendering workflows programmatically | Blender, GIMP, OBS Studio, Audacity, Krita, Kdenlive, Shotcut, Inkscape, Darktable, LMMS, Ardour |
| **🎮 Game Development** | Manage game projects, scenes, exports, and scripting through headless engine interfaces | **[Godot Engine](https://godotengine.org)** |
| **🔬 Scientific Computing** | Automate research workflows, simulations, and complex calculations | ImageJ, FreeCAD, QGIS, ParaView, Gephi, LibreCAD, Stellarium, KiCad, JASP, Jamovi |
| **🏢 Enterprise & Office** | Convert business applications and productivity tools into agent-accessible systems | NextCloud, GitLab, Grafana, Mattermost, LibreOffice, AppFlowy, NocoDB, Odoo (Community), Plane, ERPNext |
| **📞 Communication & Collaboration** | Automate meeting scheduling, participant management, recording retrieval, and reporting through structured CLI | Zoom, Jitsi Meet, BigBlueButton, Mattermost |
| **📐 Diagramming & Visualization** | Create and manipulate diagrams, flowcharts, architecture diagrams, and visual documentation programmatically | Draw.io (diagrams.net), Mermaid, PlantUML, Excalidraw, yEd |
| **🌐 Network & Infrastructure** | Manage network services, DNS, ad-blocking, and infrastructure through structured CLI commands | AdGuardHome |
| **🧪 Testing & Mocking** | Control HTTP mock servers, manage test stubs, record and replay API traffic for integration testing | **[WireMock](https://wiremock.org)** |
| **🔬 Graphics & GPU Debugging** | Analyze GPU frame captures, inspect pipeline state, export shaders, and diff rendering state | RenderDoc |
| **🎬 Video & Subtitles** | Transcribe speech, translate subtitles, burn styled captions into video — full captioning pipeline | VideoCaptioner |
| **🔍 AI-Native Search** | Neural and deep web search with structured content retrieval through embedding-based APIs | [Exa](https://exa.ai) |
| **✨ AI Content Generation** | Generate professional deliverables (slides, docs, diagrams, websites, research reports) through AI-powered cloud APIs | [AnyGen](https://www.anygen.io), Gamma, Beautiful.ai, Tome |

---

## CLI-Anything's Key Features

### The Agent-Software Gap
AI agents are great at reasoning but terrible at using real professional software. Current solutions are fragile UI automation, limited APIs, or dumbed-down reimplementations that miss 90% of functionality.

**CLI-Anything's Solution**: Transform any professional software into agent-native tools without losing capabilities.

| **Current Pain Point** | **CLI-Anything's Fix** |
|----------|----------------------|
| 🤖 "AI can't use real tools" | Direct integration with actual software backends (Blender, LibreOffice, FFmpeg) — full professional capabilities, zero compromises |
| 💸 "UI automation breaks constantly" | No screenshots, no clicking, no RPA fragility. Pure command-line reliability with structured interfaces |
| 📊 "Agents need structured data" | Built-in JSON output for seamless agent consumption + human-readable formats for debugging |
| 🔧 "Custom integrations are expensive" | One Claude plugin auto-generates CLIs for ANY codebase through proven 7-phase pipeline |
| ⚡ "Prototype vs Production gap" | 1,839+ tests with real software validation. Battle-tested across 16 major applications |

---

## 🎯 What Can You Do with CLI-Anything?

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

## ✨ ⚙️ How CLI-Anything Works

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

### 🤖 SKILL.md Generation

Each generated CLI includes a `SKILL.md` file inside the Python package at `cli_anything/<software>/skills/SKILL.md`. This self-contained skill definition enables AI agents to discover and use the CLI through Claude Code's skill system or other agent frameworks.

**What SKILL.md provides:**
- **YAML frontmatter** with name and description for agent skill discovery
- **Command groups** with all available subcommands documented
- **Usage examples** for common workflows
- **Agent-specific guidance** for JSON output, error handling, and programmatic use

SKILL.md files are auto-generated during Phase 6.5 of the pipeline using `skill_generator.py`, which extracts metadata directly from the CLI's Click decorators, setup.py, and README. Because the file lives inside the package, it is installed alongside the CLI via `pip install` and auto-detected by the REPL banner — agents can read the absolute path displayed at startup.

---

## 🎬 Real-World Demos

AI agents using generated CLIs to produce complete, useful artifacts — no GUI needed.

### Draw.io &mdash; HTTPS Handshake Diagram

> **Harness:** `cli-anything-drawio` | **Time:** ~4 min | **Artifact:** `.drawio` + `.png`

An agent creates a full HTTPS connection lifecycle diagram from scratch — TCP three-way handshake, TLS negotiation, encrypted data exchange, and TCP four-way termination — entirely through CLI commands.

<p align="center">
  <img src="examples/drawio/drawio_demo.gif" alt="Draw.io CLI demo: building an HTTPS handshake diagram" width="720" />
</p>

<details>
<summary>Final artifact</summary>
<p align="center">
  <img src="examples/drawio/https_handshake.png" alt="HTTPS handshake sequence diagram" width="600" />
</p>
</details>

*Contributed by [@zhangxilong-43](https://github.com/zhangxilong-43)*

### Slay the Spire II &mdash; Game Automation

> **Harness:** `cli-anything-slay-the-spire-ii` | **Artifact:** Automated gameplay session

An agent plays through a Slay the Spire II run using the CLI harness — reading game state, selecting cards, choosing paths, and making strategic decisions in real-time.

<p align="center">
  <img src="examples/slay_the_spire_ii/example_preview.gif" alt="Slay the Spire II CLI gameplay demo" width="720" />
</p>

*Contributed by [@TianyuFan0504](https://github.com/TianyuFan0504)*

### VideoCaptioner &mdash; Auto-Generated Subtitles

> **Harness:** `cli-anything-videocaptioner` | **Artifact:** Captioned video frames

An agent uses the VideoCaptioner CLI to automatically generate and overlay styled subtitles onto video content, with bilingual text rendering and customizable formatting.

<table align="center">
<tr>
<td align="center"><strong>Sub A</strong></td>
<td align="center"><strong>Sub B</strong></td>
</tr>
<tr>
<td><img src="examples/videocaptioner/videocaptioner_before.png" alt="Video frame before captioning" width="380" /></td>
<td><img src="examples/videocaptioner/videocaptioner_after.png" alt="Video frame after captioning" width="380" /></td>
</tr>
</table>

*Contributed by [@WEIFENG2333](https://github.com/WEIFENG2333)*

*More CLI demos coming soon.*

---

## 🎬 Demonstrations

### 🎯 General-Purpose
CLI-Anything works on any software with a codebase — no domain restrictions or architectural limitations.

### 🏭 Professional-Grade Testing
Tested across 16 diverse, complex applications spanning creative, productivity, communication, diagramming, AI image generation, AI content generation, network ad blocking, and local LLM inference domains previously inaccessible to AI agents.

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
<td align="center"><strong>🌐 Browser</strong></td>
<td>Browser Automation</td>
<td><code>cli-anything-browser</code></td>
<td>DOMShell MCP + Accessibility Tree</td>
<td align="center">✅ <a href="browser/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center"><strong>📄 LibreOffice</strong></td>
<td>Office Suite (Writer, Calc, Impress)</td>
<td><code>cli-anything-libreoffice</code></td>
<td>ODF generation + headless LO</td>
<td align="center">✅ 158</td>
</tr>
<tr>
<td align="center"><strong>⚡ <a href="n8n/agent-harness/">n8n</a></strong></td>
<td>Workflow Automation</td>
<td><code>cli-anything-n8n</code></td>
<td>n8n REST API v1.1.1</td>
<td align="center">✅ <a href="n8n/agent-harness/">55+ cmds</a></td>
</tr>
<tr>
<td align="center"><strong>📚 <a href="zotero/agent-harness/">Zotero</a></strong></td>
<td>Reference Management</td>
<td><code>cli-anything-zotero</code></td>
<td>Local SQLite + connector + Local API</td>
<td align="center">✅ <a href="zotero/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center"><strong>📝 <a href="mubu/agent-harness/">Mubu</a></strong></td>
<td>Knowledge Management &amp; Outlining</td>
<td><code>cli-anything-mubu</code></td>
<td>Local Mubu data + sync logs</td>
<td align="center">✅ 96</td>
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
<td align="center"><strong>🎬 <a href="openscreen/agent-harness/">Openscreen</a></strong></td>
<td>Screen Recording Editor</td>
<td><code>cli-anything-openscreen</code></td>
<td>ffmpeg backend</td>
<td align="center">✅ 101</td>
</tr>
<tr>
<td align="center"><strong>📞 Zoom</strong></td>
<td>Video Conferencing</td>
<td><code>cli-anything-zoom</code></td>
<td>Zoom REST API (OAuth2)</td>
<td align="center">✅ 22</td>
</tr>
<tr>
<td align="center"><strong>🎵 MuseScore</strong></td>
<td>Music Notation</td>
<td><code>cli-anything-musescore</code></td>
<td>mscore CLI (MSCX/MusicXML)</td>
<td align="center">✅ 56</td>
</tr>
<tr>
<td align="center"><strong>📐 Draw.io</strong></td>
<td>Diagramming</td>
<td><code>cli-anything-drawio</code></td>
<td>mxGraph XML + draw.io CLI</td>
<td align="center">✅ 138</td>
</tr>
<tr>
<td align="center"><strong>🧜 Mermaid Live Editor</strong></td>
<td>Diagramming</td>
<td><code>cli-anything-mermaid</code></td>
<td>Mermaid state + mermaid.ink renderer</td>
<td align="center">✅ 10</td>
</tr>
<tr>
<td align="center"><strong>✨ AnyGen</strong></td>
<td>AI Content Generation</td>
<td><code>cli-anything-anygen</code></td>
<td>AnyGen REST API (anygen.io)</td>
<td align="center">✅ 50</td>
</tr>
<tr>
<td align="center"><strong>🧠 NotebookLM</strong></td>
<td>AI Research Assistant</td>
<td><code>cli-anything-notebooklm</code></td>
<td>NotebookLM CLI wrapper (experimental)</td>
<td align="center">✅ 21</td>
</tr>
<tr>
<td align="center"><strong>🧩 <a href="dify-workflow/agent-harness/">Dify Workflow</a></strong></td>
<td>Dify DSL Editing</td>
<td><code>cli-anything-dify-workflow</code></td>
<td>Wrapper around the open-source dify-workflow CLI</td>
<td align="center">✅ 11</td>
</tr>
<tr>
<td align="center"><strong>🖼️ ComfyUI</strong></td>
<td>AI Image Generation</td>
<td><code>cli-anything-comfyui</code></td>
<td>ComfyUI REST API</td>
<td align="center">✅ 70</td>
</tr>
<tr>
<td align="center"><strong>🛡️ AdGuard Home</strong></td>
<td>Network-wide Ad Blocking</td>
<td><code>cli-anything-adguardhome</code></td>
<td>AdGuard Home REST API</td>
<td align="center">✅ 36</td>
</tr>
<tr>
<td align="center"><strong>🦙 Ollama</strong></td>
<td>Local LLM Inference</td>
<td><code>cli-anything-ollama</code></td>
<td>Ollama REST API</td>
<td align="center">✅ 98</td>
</tr>
<tr>
<td align="center"><strong>🎬 <a href="videocaptioner/agent-harness/">VideoCaptioner</a></strong></td>
<td>AI Video Captioning</td>
<td><code>cli-anything-videocaptioner</code></td>
<td>videocaptioner CLI (PyPI)</td>
<td align="center">✅ 26</td>
</tr>
<tr>
<td align="center"><strong>🎨 Sketch</strong></td>
<td>UI Design</td>
<td><code>sketch-cli</code></td>
<td>sketch-constructor (Node.js)</td>
<td align="center">✅ 19</td>
</tr>
<tr>
<td align="center"><strong>🎮 Godot Engine</strong></td>
<td>Game Development</td>
<td><code>cli-anything-godot</code></td>
<td>Godot 4.x headless subprocess</td>
<td align="center">✅ 24</td>
</tr>
<tr>
<td align="center"><strong>🔍 <a href="exa/agent-harness/">Exa</a></strong></td>
<td>AI-Native Web Search</td>
<td><code>cli-anything-exa</code></td>
<td>exa-py SDK</td>
<td align="center">✅ 40</td>
</tr>
<tr>
<td align="center"><strong>☁️ <a href="cloudanalyzer/agent-harness/">CloudAnalyzer</a></strong></td>
<td>Point cloud / trajectory QA</td>
<td><code>cli-anything-cloudanalyzer</code></td>
<td>CloudAnalyzer (Python API)</td>
<td align="center">✅ 14</td>
</tr>
<tr>
<td align="center" colspan="4"><strong>Total</strong></td>
<td align="center"><strong>✅ 2,130</strong></td>
</tr>
</table>

> **100% pass rate** across all 2,130 tests — 1,551 unit tests + 560 end-to-end tests + 19 Node.js tests.

---

## 📊 Test Results

Each CLI harness undergoes rigorous multi-layered testing to ensure production reliability:

| Layer | What it tests | Example |
|-------|---------------|---------|
| **Unit tests** | Every core function in isolation with synthetic data | `test_core.py` — project creation, layer ops, filter params |
| **E2E tests (native)** | Project file generation pipeline | Valid ODF ZIP structure, correct MLT XML, SVG well-formedness |
| **E2E tests (true backend)** | Real software invocation + output verification | LibreOffice → PDF with `%PDF-` magic bytes, Blender → rendered PNG |
| **CLI subprocess tests** | Installed command via `subprocess.run` | `cli-anything-gimp --json project new` → valid JSON output |

```
================================ Test Summary ================================
gimp          107 passed  ✅   (64 unit + 43 e2e)
blender       208 passed  ✅   (150 unit + 58 e2e)
inkscape      202 passed  ✅   (148 unit + 54 e2e)
audacity      161 passed  ✅   (107 unit + 54 e2e)
libreoffice   158 passed  ✅   (89 unit + 69 e2e)
mubu           96 passed  ✅   (85 unit + 11 e2e)
obs-studio    153 passed  ✅   (116 unit + 37 e2e)
kdenlive      155 passed  ✅   (111 unit + 44 e2e)
shotcut       154 passed  ✅   (110 unit + 44 e2e)
zoom           22 passed  ✅   (22 unit + 0 e2e)
drawio        138 passed  ✅   (116 unit + 22 e2e)
mermaid        10 passed  ✅   (5 unit + 5 e2e)
anygen         50 passed  ✅   (40 unit + 10 e2e)
notebooklm     21 passed  ✅   (21 unit + 0 e2e)
comfyui        70 passed  ✅   (60 unit + 10 e2e)
adguardhome    36 passed  ✅   (24 unit + 12 e2e)
ollama         98 passed  ✅   (87 unit + 11 e2e)
sketch         19 passed  ✅   (19 jest, Node.js)
renderdoc      59 passed  ✅   (45 unit + 14 e2e)
cloudcompare   88 passed  ✅   (49 unit + 39 e2e)
openscreen    101 passed  ✅   (78 unit + 23 e2e)
cloudanalyzer  14 passed  ✅   (7 unit + 7 e2e)
──────────────────────────────────────────────────────────────────────────────
TOTAL        2,120 passed  ✅   100% pass rate
```

---

## 🏗️ CLI-Anything's Architecture

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

## 📂 Project Structure

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
├── 🤖 codex-skill/                      # Codex skill entry point
├── 🎨 gimp/agent-harness/               # GIMP CLI (107 tests)
├── 🧊 blender/agent-harness/            # Blender CLI (208 tests)
├── ✏️ inkscape/agent-harness/            # Inkscape CLI (202 tests)
├── 🎵 audacity/agent-harness/           # Audacity CLI (161 tests)
├── 🌐 browser/agent-harness/            # Browser CLI (DOMShell MCP, new)
├── 📄 libreoffice/agent-harness/        # LibreOffice CLI (158 tests)
├── 📚 zotero/agent-harness/             # Zotero CLI (new, write import support)
├── 📝 mubu/agent-harness/               # Mubu CLI (96 tests)
├── 📹 obs-studio/agent-harness/         # OBS Studio CLI (153 tests)
├── 🎞️ kdenlive/agent-harness/           # Kdenlive CLI (155 tests)
├── 🎬 shotcut/agent-harness/            # Shotcut CLI (154 tests)
├── 📞 zoom/agent-harness/               # Zoom CLI (22 tests)
├── 🎵 musescore/agent-harness/          # MuseScore CLI (56 tests)
├── 📐 drawio/agent-harness/             # Draw.io CLI (138 tests)
├── 🧜 mermaid/agent-harness/            # Mermaid Live Editor CLI (10 tests)
├── ✨ anygen/agent-harness/             # AnyGen CLI (50 tests)
├── 🖼️ comfyui/agent-harness/            # ComfyUI CLI (70 tests)
├── 🧠 notebooklm/agent-harness/         # NotebookLM CLI (experimental, 21 tests)
├── 🧩 dify-workflow/agent-harness/      # Dify Workflow CLI wrapper (11 tests)
├── 🛡️ adguardhome/agent-harness/       # AdGuard Home CLI (36 tests)
├── 🦙 ollama/agent-harness/             # Ollama CLI (98 tests)
├── 🎮 godot/agent-harness/              # Godot Engine CLI (24 tests)
├── 🎨 sketch/agent-harness/             # Sketch CLI (19 tests, Node.js)
├── 🔬 renderdoc/agent-harness/          # RenderDoc CLI (59 tests)
├── 🎬 videocaptioner/agent-harness/     # VideoCaptioner CLI (26 tests)
├── 🎬 openscreen/agent-harness/         # Openscreen CLI — screen recording editor (101 tests)
├── ☁️ cloudcompare/agent-harness/       # CloudCompare CLI (88 tests)
├── 🔍 exa/agent-harness/               # Exa CLI (40 tests)
└── ⛅ cloudanalyzer/agent-harness/      # CloudAnalyzer CLI (14 tests)
```

Each `agent-harness/` contains an installable Python package under `cli_anything.<software>/` with Click CLI, core modules, utils (including `repl_skin.py` and backend wrapper), and comprehensive tests.

---

## 🎯 Plugin Commands

| Command | Description |
|---------|-------------|
| `/cli-anything <software-path-or-repo>` | Build complete CLI harness — all 7 phases |
| `/cli-anything:refine <software-path> [focus]` | Refine an existing harness — expand coverage with gap analysis |
| `/cli-anything:test <software-path-or-repo>` | Run tests and update TEST.md with results |
| `/cli-anything:validate <software-path-or-repo>` | Validate against HARNESS.md standards |

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

## 🎮 Demo: Using a Generated CLI

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

## 📖 The Standard Playbook: HARNESS.md

HARNESS.md is our definitive SOP for making any software agent-accessible via automated CLI generation.

It encodes proven patterns and methodologies refined through automated generation processes.

The playbook distills key insights from successfully building all 16 diverse, production-ready harnesses.

### Critical Lessons

| Lesson | Description |
|--------|-------------|
| **Use the real software** | The CLI MUST call the actual application for rendering. No Pillow replacements for GIMP, no custom renderers for Blender. Generate valid project files → invoke the real backend. |
| **The Rendering Gap** | GUI apps apply effects at render time. If your CLI manipulates project files but uses a naive export tool, effects get silently dropped. Solution: native renderer → filter translation → render script. |
| **Filter Translation** | When mapping effects between formats (MLT → ffmpeg), watch for duplicate filter merging, interleaved stream ordering, parameter space differences, and unmappable effects. |
| **Timecode Precision** | Non-integer frame rates (29.97fps) cause cumulative rounding. Use `round()` not `int()`, integer arithmetic for display, and ±1 frame tolerance in tests. |
| **Output Verification** | Never trust that export worked because it exited 0. Verify: magic bytes, ZIP/OOXML structure, pixel analysis, audio RMS levels, duration checks. |

> See the full methodology: [`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md)

---

## 📦 Installation & Usage

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

## 🤝 Contributing

We welcome contributions! CLI-Anything is designed to be extensible:

- **New software targets** — Use the plugin to generate a CLI for any software with a codebase, then submit your harness via [`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md).
- **Methodology improvements** — PRs to `HARNESS.md` that encode new lessons learned
- **Plugin enhancements** — New commands, phase improvements, better validation
- **Test coverage** — More E2E scenarios, edge cases, workflow tests

### Limitations

- **Requires strong foundation models** — CLI-Anything relies on frontier-class models (e.g., Claude Opus 4.6, Claude Sonnet 4.6, GPT-5.4) for reliable harness generation. Weaker or smaller models may produce incomplete or incorrect CLIs that require significant manual correction.
- **Relies on available source code** — The 7-phase pipeline analyzes and generates from source code. When the target software only provides compiled binaries that require decompilation, harness quality and coverage will degrade substantially.
- **May require iterative refinement** — A single `/cli-anything` run may not fully cover all capabilities. Running `/refine` one or more times is often needed to push the CLI's performance and coverage to production quality.

### Roadmap

- [ ] Support for more application categories (CAD, DAW, IDE, EDA, scientific tools)
- [ ] Benchmark suite for agent task completion rates
- [ ] Community-contributed CLI harnesses for internal/custom software
- [ ] Integration with additional agent frameworks beyond Claude Code
- [ ] Support packaging APIs for closed-source software and web services into CLIs
- [x] Produce SKILL.md alongside the CLI for agent skill discovery and orchestration

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md) | The methodology SOP — single source of truth |
| [`cli-anything-plugin/README.md`](cli-anything-plugin/README.md) | Plugin documentation — commands, options, phases |
| [`cli-anything-plugin/QUICKSTART.md`](cli-anything-plugin/QUICKSTART.md) | 5-minute getting started guide |
| [`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md) | Distribution and publishing guide |

Each generated harness also includes:
- `<SOFTWARE>.md` — Architecture SOP specific to that application
- `tests/TEST.md` — Test plan and results documentation

---

## ⭐ Star History

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

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">

**CLI-Anything** — *Make any software with a codebase Agent-native.*

<sub>A methodology for the age of AI agents | 16 professional software demos | 1,839 passing tests</sub>

<br>

<img src="assets/icon.png" alt="CLI-Anything Icon" width="80">

</div>

<p align="center">
  <em> Thanks for visiting ✨ CLI-Anything!</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.CLI-Anything&style=for-the-badge&color=00d4ff" alt="Views">
</p>
