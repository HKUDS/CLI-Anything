<h1 align="center"><img src="assets/icon.png" alt="" width="64" style="vertical-align: middle;">&nbsp; CLI-Anything: Making ALL Software Agent-Native</h1>

<div align="center">
<a href="https://trendshift.io/repositories/22991" target="_blank"><img src="https://trendshift.io/api/badge/repositories/22991" alt="HKUDS%2FCLI-Anything | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

<p align="center">
  <strong>Today's Software Serves Humans👨‍💻. Tomorrow's Users will be Agents🤖.<br>
CLI-Anything: Bridging the Gap Between AI Agents and the World's Software</strong><br>
</p>

**🌐 [CLI-Hub](https://hkuds.github.io/CLI-Anything/)**: `pip install cli-anything-hub` then `cli-hub install <name>` — browse, install, and manage all community-built CLIs. Want to add your own? [Open a PR](https://github.com/HKUDS/CLI-Anything/blob/main/CONTRIBUTING.md) — the hub updates instantly.

**🎬 [See Demos](#-real-world-demos)**: Watch AI agents use generated CLIs plus preview, live preview, and trajectory loops to produce real artifacts — CAD builds, 3D scenes, diagrams, gameplay, subtitles, and more.

**🙋 [Become a Contributor, or Request a CLI]**: [Join us](https://github.com/HKUDS/CLI-Anything/issues/new?template=contributor-signup.yml)! Sign up to build a new CLI harness — once reviewed and merged, you'll gain access as one of our community contributors! Wish CLI-Anything supported a specific software or service? Submit a [wishlist request](https://github.com/HKUDS/CLI-Anything/issues/new?template=cli-wishlist.yml)!

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-5_min-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="https://hkuds.github.io/CLI-Anything/"><img src="https://img.shields.io/badge/CLI_Hub-Browse_%26_Install-ff69b4?style=for-the-badge" alt="CLI Hub"></a>
  <a href="#-demonstrations"><img src="https://img.shields.io/badge/Demos-18_Apps-green?style=for-the-badge" alt="Demos"></a>
  <a href="#-test-results"><img src="https://img.shields.io/badge/Tests-2%2C461_Passing-brightgreen?style=for-the-badge" alt="Tests"></a>
  <a href="https://arxiv.org/abs/2606.03854"><img src="https://img.shields.io/badge/Tech_Report-arXiv%3A2606.03854-b31b1b?style=for-the-badge" alt="Tech Report"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-yellow?style=for-the-badge" alt="License"></a>
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

**One Command Line**: Make any software agent-ready for Pi, OpenClaw, nanobot, Cursor, Claude Code, etc.&nbsp;&nbsp;[**中文文档**](README_CN.md) | [**日本語ドキュメント**](README_JA.md) | [**Deutsch**](README_DE.md)

<p align="center">
  <img src="assets/cli-typing.gif" alt="CLI-Anything typing demo" width="800">
</p>

<p align="center">
  <img src="assets/teaser.png" alt="CLI-Anything Teaser" width="800">
</p>

---

## 📰 News

> Thanks to all invaluable efforts from the community! More updates continuously on the way everyday..

- **2026-05-30** 🧭 **Hermes skill** proposed (#320), adding a CLI-Anything orchestration skill with installer scripts and HARNESS fallback guidance. 🗺️ **ArcGIS Pro** was proposed for the public registry (#318) as a Windows/ArcPy CLI for cartography, geoprocessing, feature editing, and live-Pro MCP workflows.

- **2026-05-27** 🔧 **CLI-Hub** registry date updates now handle `python -m pip` install commands (#312), improving package-date detection for registry automation.

- **2026-05-23** 📝 **Obsidian Agent CLI** was proposed for the public registry (#307), bringing a PyPI-installed Obsidian automation CLI with persistent agent memory workflows and a pinned skill link.

- **2026-05-21** 🔒 **Sketch CLI** token-file handling was hardened against path traversal and symlink escapes (#304).

- **2026-05-20** 📓 **Joplin CLI** was proposed (#300) with notebooks, notes, to-dos, tags, attachments, search/sync, import/export, server/E2EE helpers, full docs, packaged skill docs, and a 134-test validation baseline.

- **2026-05-20** 🎛️ **Rekordbox CLI** merged (#252) with guarded SQLCipher write paths, backup-required forced writes, smoke coverage, and root skill sync. 📚 **Calibre CLI** merged (#223) with library/search/metadata/conversion/export workflows, 41 unit tests, real-Calibre E2E evidence, and root skill validation. 🧊 **3MF CLI** merged (#209) with mesh inspection, hole resizing, repair, comparison, and preserved triangle attributes. 🎙️ **MiniMax CLI** merged (#189) with chat/TTS workflows, JSON-safe model/voice listing, REPL quote handling, and smoke/E2E coverage. 🎮 **UEAtelier** joined the registry (#297) as an Unreal Editor MCP self-extension workbench with a Python CLI proxy.

- **2026-05-19** 🛠️ Existing harnesses got a quality/security pass — **Zoom** downloads recordings from direct URLs (#294), **Obsidian** search now uses the Local REST API vendor content types (#289), **LibreOffice** headless conversion is more robust on macOS (#290), and XML/SVG/ODF/MLT/MusicXML/CSL parsing now routes untrusted input through `defusedxml` (#296).

- **2026-05-18** 📈 README presentation refreshed with the Trendshift badge and centered project header polish (#285, #286), keeping the landing section focused on discovery and project momentum.

- **2026-05-17** 🌐 **CLI-Hub** registry handling was hardened (#281) — registry entries are now copied before `_source` tagging, preventing cached or mocked registry data from being mutated in place.

- **2026-05-16** 🔧 **n8n** received the REPL banner crash fix that later merged into main (#280), restoring the no-subcommand interactive startup path with regression coverage.

<details>
<summary>Earlier news (Apr 10–18)</summary>

- **2026-04-18** 🧩 **All SKILL.md files are now being unified under the top-level `skills/` directory** — every CLI skill can be installed from one canonical source with `npx skills add HKUDS/CLI-Anything --skill <skill-name> -g -y`. We also added root-skill validation CI, synced contribution / PR docs and REPL skill-path hints to the new layout, and refreshed the **CLI-Hub** install-first frontend around the new `npx skills` flow.

- **2026-04-17** 🌐 **CLI-Hub** received another install UX pass — public registry metadata and skill coverage were tightened, visit counting was corrected, and the web hub was further refined. 🧪 **Shotcut** render output duration was fixed (#92). 📝 **SKILL** contribution paths were corrected for the new docs flow (#224), and the skill generator now safely handles empty intros (#203).

- **2026-04-16** 🗺️ **QGIS CLI** merged (#207) — a full GIS / map authoring harness landed. 🧬 **UniMol Tools CLI** merged (#219) for molecular modeling workflows. 🌐 **CLI-Hub** also added more public CLIs, including **py4csr**, refreshed its generated meta-skill, corrected SKILL contribution docs, and fixed `apt-get` package extraction in skill generation (#204).

- **2026-04-16** 📈 **Unreal Insights CLI** expanded — added background capture session control (`capture start/status/snapshot/stop`), engine-root-matched `UnrealInsights.exe` resolution/build flows, and refreshed docs/tests for the new orchestration workflow.

- **2026-04-15** 🌐 **CLI-Hub** updated to **v0.2.0** — the PyPI package now supports public CLIs from multiple install sources (`pip`, `npm`, `brew`, bundled/system tools), backed by a new `public_registry.json`. The Hub frontend was redesigned with separate **CLI-Anything CLIs** and **Public CLIs** decks, and live end-to-end checks now cover real install, update, and uninstall flows across both pip and npm packages.

- **2026-04-14** 🧭 **Safari CLI** merged (#212) and added to the Hub registry — browser automation via `safari-mcp`. 🎬 **Kdenlive** also received compatibility fixes for Gen 5 project output and invalid project generation.

- **2026-04-13** 📓 **Obsidian CLI** merged (#211) — knowledge management harness via the Local REST API, with 48 unit tests and 7 E2E tests. ⛓️ **Eth2-Quickstart CLI** merged (#195) — Ethereum staking node management harness. 📚 **Zotero CLI** updated to v0.4.1 (#201) — now shipped from its standalone repo, and CLI-Hub gained support for remote `skill_md` URLs.

- **2026-04-11** 🔗 **n8n CLI** merged (#188) — workflow automation harness for self-hosted automation flows. 🔧 **Exa CLI** fix (#205) added the `x-exa-integration` header for usage tracking. 📦 **CLI-Hub** also gained its PyPI auto-publish workflow and package refresh pipeline.

- **2026-04-10** 📦 **CLI-Hub package manager** launched — `pip install cli-anything-hub` to browse, search, install, update, and uninstall CLI-Anything harnesses from one command. The web Hub also shipped its first install-focused frontend refresh and "Empower yourself" toolkit card.

</details>

<details>
<summary>Earlier news (Apr 1–9)</summary>

- **2026-04-09** 🧹 Cleanup and docs pass (#200) — fixed Openscreen test subtotals, added Openscreen to the Chinese README and project structure, and clarified `/cli-anything` command syntax in the docs.

- **2026-04-08** 🎬 **Openscreen CLI** merged (#183) — screen recording editor harness with 101 tests. ☁️ **CloudAnalyzer CLI** merged (#181) — cloud cost analysis harness with 27 commands. 🌊 **SeaClip / PM2 / ChromaDB** harnesses merged (#129).

- **2026-04-07** 🔄 **Dify Workflow CLI** merged (#191) — workflow automation wrapper. 🔧 **Inkscape** auto-save fix (#193, fixes #182). 🛡️ **DomShell security hardening** (#156) — URL validation and DOM sanitization for the browser CLI. 🥧 **Pi Coding Agent extension** merged (#178).

- **2026-04-06** 🔍 **Exa CLI** merged (#172) — AI-powered web search and answers harness. 🎮 **Godot CLI** merged (#140) — game engine harness with a full demo-game E2E pipeline. ☁️ **CloudAnalyzer** review fixes and frontend improvements also landed.

- **2026-04-03** 🧪 **WireMock CLI** merged (#170) — HTTP mock server harness for API testing. 🥧 **Pi Coding Agent** extension support also landed, and CLI demo recordings were added to the docs.

- **2026-04-01** ⚔️ **Slay the Spire II CLI** merged (#148) — deck-building roguelike harness. 🎥 **VideoCaptioner CLI** merged (#166) — AI-powered video captioning harness. 🛰️ **IntelWatch** was added to the registry for B2B OSINT workflows.

</details>

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

CLI-Anything has two equally useful starting points:

| Goal | Start Here |
|------|------------|
| **Use the existing CLI ecosystem now** | Install `cli-anything-hub`, browse the registry, and install ready-made CLIs. |
| **Build a new agent-native CLI** | Install the CLI-Anything plugin/skill for your agent, then run the 7-phase harness generator. |

<details open>
<summary><strong>Phase 1: Empower yourself — your CLI toolkit</strong></summary>

Install the CLI-Hub package manager first. It lets you browse, search, inspect, install, update, uninstall, and launch CLI-Anything harnesses plus public third-party CLIs from one command.

**PIP**

```bash
pip install cli-anything-hub
```

| Command | What it does |
|---------|--------------|
| `cli-hub list` | Browse the registry |
| `cli-hub search <query>` | Search by keyword |
| `cli-hub info <name>` | Inspect one CLI |
| `cli-hub install <name>` | Install from CLI-Hub |
| `cli-hub update <name>` | Update an install |
| `cli-hub uninstall <name>` | Remove an install |
| `cli-hub launch <name> [args...]` | Run an installed CLI |

```bash
# Browse what is available
cli-hub list
cli-hub search image

# Install and try a CLI immediately
cli-hub install gimp
cli-hub info gimp
cli-hub launch gimp
```

> Some CLIs wrap real desktop or backend software. If a selected CLI needs GIMP, Blender, LibreOffice, or another upstream tool, install that upstream application too.

</details>

<details open>
<summary><strong>Phase 1.5: Empower your agents — install in one command</strong></summary>

Give SKILL-compatible agents the CLI-Hub meta-skill so they can discover and install the right CLI for a task.

**Also available on:** [ClawHub](https://clawhub.ai/yuh-yang/cli-anything-hub), [SkillHub](https://www.skillhub.club/web/skills/itsyuhao-cli-anything-hub), [SkillHub.cn](https://skillhub.cn/skills/cli-hub-meta-skill)

**NPX SKILLS**

```bash
npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y
```

**Works with:** OpenClaw, Nanobot, Claude Code, Codex, Reasonix, Antigravity, and other SKILL-compatible agents.

Then prompt:

```text
Find appropriate CLI software in CLI-Hub and complete the task: ...
```

</details>

<details open>
<summary><strong>Phase 3: Build a new CLI when the registry does not have one yet</strong></summary>

Use the CLI-Anything generator when you need a new harness for software, a codebase, or an internal tool that is not already available through CLI-Hub.

**Prerequisites**

- **Python 3.10+**
- Target software or source repo available locally or online
- A supported AI coding agent: [Claude Code](#-claude-code) | [Pi](#-pi-coding-agent) | [OpenClaw](#-openclaw) | [OpenCode](#-opencode) | [Codex](#-codex) | [Hermes](#-hermes) | [Reasonix](#-reasonix) | [Qodercli](#-qodercli) | [GitHub Copilot CLI](#-github-copilot-cli) | [More Platforms](#-more-platforms-coming-soon)

### Pick Your Agent Platform

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
# /cli-anything <software-path-or-repo>
# Generate a complete CLI for GIMP (all 7 phases)
/cli-anything ./gimp
```

Command compatibility across Claude Code versions:
- Use `/cli-anything` as the primary entrypoint.
- On older builds where `/cli-anything` isn't recognized **after confirming the plugin is installed and loaded**, try the legacy entry form `/cli-anything:cli-anything`.
- Auxiliary commands keep the `:subcommand` form (e.g. `/cli-anything:refine`).

If you see `Unknown skill: cli-anything`, focus on plugin install/load first (both entry forms reference the same skill, so swapping forms won't help):
1. Reload plugin commands: `/reload-plugins`
2. Verify the plugin is loaded: `/help cli-anything` (CLI-Anything help/commands should appear)
3. Reinstall from marketplace if needed:
   - `/plugin marketplace add HKUDS/CLI-Anything`
   - `/plugin install cli-anything`
4. After confirming the plugin is available, retry the entry command:
   - Preferred: `/cli-anything ./gimp`
   - Older builds only: `/cli-anything:cli-anything ./gimp`

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

> **Note:** Please upgrade to the latest OpenCode. Older versions use `command/` (singular) instead of `commands/`. If `commands/` does not exist, use `command/` for both global and project-level installs.

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
/cli-anything ./gimp
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
/cli-anything ./gimp
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
The installer also vendors the canonical `HARNESS.md`, command specifications,
on-demand guides, reusable helper scripts, skill template, and preview protocol
into the installed skill's `references/` and `scripts/` directories.
This keeps the Codex skill self-contained while using `cli-anything-plugin/` as
the source of truth.

Restart Codex after installation so it is discovered.

**Step 2: Use CLI-Anything from Codex**

Describe the task in natural language, for example:

```text
Use CLI-Anything to build a harness for ./gimp
Use CLI-Anything to refine ./shotcut for picture-in-picture workflows
Use CLI-Anything to validate ./libreoffice
Use CLI-Anything to list generated harnesses under the current directory
```

The Codex skill adapts the same methodology used by the Claude Code plugin and
OpenCode commands, while keeping the generated Python harness format unchanged.

To verify the self-contained Codex installation locally:

```bash
bash CLI-Anything/codex-skill/tests/test_install.sh
```
</details>

<details>

<summary><h4 id="-hermes">⚡ Hermes <sup><code>Experimental</code></sup> <sup><code>Community</code></sup></h4></summary>

**Step 1: Install the Skill**

Run the bundled installer:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git

# Install the skill
bash CLI-Anything/hermes-skill/scripts/install.sh
```

On Windows PowerShell, use:

```powershell
.\CLI-Anything\hermes-skill\scripts\install.ps1
```

This installs the skill to `$HERMES_HOME/skills/cli-anything-hermes` (or `~/.hermes/skills/cli-anything-hermes` if `HERMES_HOME` is unset).

Restart [Hermes Agent](https://github.com/NousResearch/hermes-agent) after installation so it is discovered.

**Step 2: Use CLI-Anything from Hermes**

Describe the task in natural language, for example:

```text
Use CLI-Anything to build a harness for ./gimp
Use CLI-Anything to refine ./shotcut for picture-in-picture workflows
Use CLI-Anything to validate ./libreoffice
```

The Hermes skill adapts the same methodology used by the Claude Code plugin and
Codex skill, binding Hermes's `terminal`, `execute_code`, `delegate_task`, and
`read_file` / `write_file` / `patch` tools to the 7-phase harness workflow while
keeping the generated Python harness format unchanged.
</details>

<details>

<summary><h4 id="-reasonix">⚡ Reasonix <sup><code>Experimental</code></sup> <sup><code>Community</code></sup></h4></summary>

**Step 1: Install the Skill**

Run the bundled installer:

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git

# Install the skill
bash CLI-Anything/reasonix-skill/scripts/install.sh
```

On Windows PowerShell, use:

```powershell
.\CLI-Anything\reasonix-skill\scripts\install.ps1
```

This installs the skill to Reasonix's global skill directory at `~/.reasonix/skills/cli-anything`.

Restart Reasonix after installation so it is discovered.

**Step 2: Use CLI-Anything from Reasonix**

Describe the task in natural language, for example:

```text
Use CLI-Anything to build a harness for ./gimp
Use CLI-Anything to refine ./shotcut for picture-in-picture workflows
Use CLI-Anything to validate ./libreoffice
```

The Reasonix skill adapts the same methodology used by the Claude Code plugin and
Codex/Hermes skills, binding Reasonix's `bash`, `write_file`, `edit_file`,
`multi_edit`, `grep`, `glob`, and optional `mcp__codegraph__search` / `mcp__codegraph__context` tools to the
7-phase harness workflow while keeping the generated Python harness format unchanged.
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
/cli-anything ./gimp
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

Each in-repo harness now has a canonical [`SKILL.md`](#-skillmd-generation) at `skills/cli-anything-<software>/SKILL.md`, which makes the monorepo directly discoverable via `npx skills add HKUDS/CLI-Anything --list`. Installed harness packages still ship a compatibility copy at `cli_anything/<software>/skills/SKILL.md`, and the REPL banner prefers the repo-root canonical file when present, falling back to the packaged copy otherwise.

</details>

---

## 🤖 Empower Your Agents with CLI-Hub

CLI-Hub lets agents autonomously discover, install, and use the CLIs they need.

```bash
npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y
```

**Also available on:** [ClawHub](https://clawhub.ai/yuh-yang/cli-anything-hub), [SkillHub](https://www.skillhub.club/web/skills/itsyuhao-cli-anything-hub), [SkillHub.cn](https://skillhub.cn/skills/cli-hub-meta-skill)

Then prompt:

```text
Find appropriate CLI software in CLI-Hub and complete the task: ...
```

The meta-skill points agents to the live CLI-Hub catalog, where they can choose a CLI, install it, and read its own `SKILL.md` for task-specific usage.

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
| **🎨 Creative & Media** | Control content creation, editing, and rendering workflows programmatically | Blender, GIMP, OBS Studio, Audacity, WaveTone, Krita, Kdenlive, Shotcut, Inkscape, Darktable, LMMS, Ardour |
| **🎮 Game Development** | Manage game projects, scenes, exports, and scripting through headless engine interfaces | **[Godot Engine](https://godotengine.org)**, **[s&box](https://sbox.game)** |
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
| ⚡ "Prototype vs Production gap" | 2,280+ tests with real software validation. Battle-tested across 18 major applications |

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

Each generated CLI now has a canonical `SKILL.md` at `skills/cli-anything-<software>/SKILL.md`. This makes the current monorepo directly consumable by `npx skills`, while a packaged compatibility copy at `cli_anything/<software>/skills/SKILL.md` preserves installed-harness behavior.

**What SKILL.md provides:**
- **YAML frontmatter** with name and description for agent skill discovery
- **Command groups** with all available subcommands documented
- **Usage examples** for common workflows
- **Agent-specific guidance** for JSON output, error handling, and programmatic use

SKILL.md files are auto-generated during Phase 6.5 of the pipeline using `skill_generator.py`, which extracts metadata directly from the CLI's Click decorators, setup.py, and README. The generator now writes the canonical repo-root skill file and refreshes the package-local compatibility copy used by installed harnesses. Inside this repo, the REPL banner points agents to the canonical root skill path; after `pip install`, it falls back to the packaged copy.

---

## 🎬 Real-World Demos

AI agents using generated CLIs to produce complete, useful artifacts — no GUI needed.

### FreeCAD &mdash; Curiosity Rover via Preview, Live Preview, and Trajectory

> **Harness:** `cli-anything-freecad` | **Preview Stack:** `preview` + `preview live` + `trajectory.json` | **Artifact:** Agent-built Curiosity-style rover

An agent incrementally assembles a Curiosity-inspired rover while publishing real FreeCAD preview bundles, refreshing a live preview session, and recording command-to-preview history for later replay. The resulting demo shows the artifact evolving step by step before the final showcase.

<p align="center">
  <img src="assets/demos/freecad-curiosity-preview-trajectory.gif" alt="FreeCAD Curiosity rover demo driven by preview, live preview, and trajectory history" width="860" />
</p>

<p align="center">
  <sub>README GIF generated from the full local demo video with a speed-adjusted, high-quality ffmpeg palette workflow.</sub>
</p>

### Blender &mdash; Orbital Relay Drone via Preview, Live Preview, and Trajectory

> **Harness:** `cli-anything-blender` | **Preview Stack:** `preview` + `preview live` + `trajectory.json` | **Artifact:** Agent-built orbital relay drone

An agent uses the Blender harness to grow a hard-surface orbital relay drone under a real preview loop: each stage pushes new render-backed bundles, the live session tracks the current head, and the trajectory ties every command to the matching visual state. The demo finishes with the completed scene ready for a polished turntable.

<p align="center">
  <img src="assets/demos/blender-orbital-relay-drone-preview-trajectory.gif" alt="Blender orbital relay drone demo driven by preview, live preview, and trajectory history" width="860" />
</p>

<p align="center">
  <sub>README GIF generated from the full local demo video with a speed-adjusted, high-quality ffmpeg palette workflow.</sub>
</p>

### Draw.io &mdash; HTTPS Handshake Diagram

> **Harness:** `cli-anything-drawio` | **Time:** ~4 min | **Artifact:** `.drawio` + `.png`

An agent creates a full HTTPS connection lifecycle diagram from scratch — TCP three-way handshake, TLS negotiation, encrypted data exchange, and TCP four-way termination — entirely through CLI commands.

<p align="center">
  <img src="assets/demos/drawio-demo.gif" alt="Draw.io CLI demo: building an HTTPS handshake diagram" width="720" />
</p>

<details>
<summary>Final artifact</summary>
<p align="center">
  <img src="assets/demos/drawio-https-handshake.png" alt="HTTPS handshake sequence diagram" width="600" />
</p>
</details>

*Contributed by [@zhangxilong-43](https://github.com/zhangxilong-43)*

### Slay the Spire II &mdash; Game Automation

> **Harness:** `cli-anything-slay-the-spire-ii` | **Artifact:** Automated gameplay session

An agent plays through a Slay the Spire II run using the CLI harness — reading game state, selecting cards, choosing paths, and making strategic decisions in real-time.

<p align="center">
  <img src="assets/demos/slay-the-spire-ii-gameplay.gif" alt="Slay the Spire II CLI gameplay demo" width="720" />
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
<td><img src="assets/demos/videocaptioner-before.png" alt="Video frame before captioning" width="380" /></td>
<td><img src="assets/demos/videocaptioner-after.png" alt="Video frame after captioning" width="380" /></td>
</tr>
</table>

*Contributed by [@WEIFENG2333](https://github.com/WEIFENG2333)*

### ArcGIS Pro &mdash; Live Agent Cartography via the MCP Bridge

> **Harness:** [`arcgis-pro`](https://github.com/Jasper0122/CLI-Anything-Arcgis-Pro) (registered in [`public_registry.json`](public_registry.json)) | **Mode:** live-Pro MCP bridge | **Artifact:** Agent-driven map navigation in a running ArcGIS Pro session

An agent drives a **live, open ArcGIS Pro session** through an MCP bridge — reading the project, zooming the map to feature layers, running geoprocessing, and exporting layouts — while each step executes inside Pro as you watch. ArcGIS Pro is Esri's commercial GIS desktop (Windows-only, licensed), so this wraps its official **ArcPy / ArcGIS Pro SDK** rather than being generated from source — the ArcGIS Pro counterpart to the QGIS harness.

<p align="center">
  <img src="assets/demos/arcgis-pro-live-bridge-demo.gif" alt="ArcGIS Pro live-bridge demo: an agent driving a running ArcGIS Pro session over MCP" width="860" />
</p>

<p align="center">
  <sub>README GIF generated from the full local demo video with a high-quality ffmpeg palette workflow.</sub>
</p>

*Contributed by [@Jasper0122](https://github.com/Jasper0122)*

*More CLI demos coming soon.*

---

## 🎬 Demonstrations

### 🎯 General-Purpose
CLI-Anything works on any software with a codebase — no domain restrictions or architectural limitations.

### 🏭 Professional-Grade Testing
Tested across 18 diverse, complex applications spanning creative, productivity, communication, diagramming, AI image generation, AI content generation, network ad blocking, local LLM inference, native debugging, and graphics profiling domains previously inaccessible to AI agents.

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
<td align="center"><strong>WaveTone</strong></td>
<td>Audio Transcription</td>
<td><code>cli-anything-wavetone</code></td>
<td>JSON manifest + real WaveTone launch</td>
<td align="center"><a href="wavetone/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center"><strong>🌐 Browser</strong></td>
<td>Browser Automation</td>
<td><code>cli-anything-browser</code></td>
<td>DOMShell MCP + Accessibility Tree</td>
<td align="center">✅ <a href="browser/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center"><strong><a href="web-yu-pri/agent-harness/">Web Yu-pri</a></strong></td>
<td>Japan Post Shipping Labels</td>
<td><code>cli-anything-web-yu-pri</code></td>
<td>Playwright + Web Yu-pri forms</td>
<td align="center">✅ <a href="web-yu-pri/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center"><strong>📄 LibreOffice</strong></td>
<td>Office Suite (Writer, Calc, Impress)</td>
<td><code>cli-anything-libreoffice</code></td>
<td>ODF generation + headless LO</td>
<td align="center">✅ 158</td>
</tr>
<tr>
<td align="center"><strong><a href="openrefine/agent-harness/">OpenRefine</a></strong></td>
<td>Data Cleaning</td>
<td><code>cli-anything-openrefine</code></td>
<td>OpenRefine local HTTP API</td>
<td align="center">✅ 76</td>
</tr>
<tr>
<td align="center"><strong>⚡ <a href="n8n/agent-harness/">n8n</a></strong></td>
<td>Workflow Automation</td>
<td><code>cli-anything-n8n</code></td>
<td>n8n REST API v1.1.1</td>
<td align="center">✅ <a href="n8n/agent-harness/">55+ cmds</a></td>
</tr>
<tr>
<td align="center"><strong>📧 <a href="mailchimp/agent-harness/">Mailchimp</a></strong></td>
<td>Email Marketing &amp; Automation</td>
<td><code>cli-anything-mailchimp</code></td>
<td>Mailchimp Marketing API v3.0</td>
<td align="center">✅ <a href="mailchimp/agent-harness/">303 cmds</a></td>
</tr>
<tr>
<td align="center"><strong>📚 <a href="zotero/agent-harness/">Zotero</a></strong></td>
<td>Reference Management</td>
<td><code>cli-anything-zotero</code></td>
<td>Local SQLite + connector + Local API</td>
<td align="center">✅ <a href="zotero/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center"><strong>📖 <a href="calibre/agent-harness/">Calibre</a></strong></td>
<td>E-book Library Management</td>
<td><code>cli-anything-calibre</code></td>
<td>calibredb + ebook-convert + ebook-meta</td>
<td align="center">✅ <a href="calibre/agent-harness/">58</a></td>
</tr>
<tr>
<td align="center"><strong>📓 <a href="joplin/agent-harness/">Joplin</a></strong></td>
<td>Note-taking &amp; To-dos</td>
<td><code>cli-anything-joplin</code></td>
<td>Joplin terminal CLI subprocess</td>
<td align="center">✅ 134</td>
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
<td align="center"><strong>📱 <a href="nslogger/agent-harness/">NSLogger</a></strong></td>
<td>iOS/macOS Log Capture</td>
<td><code>cli-anything-nslogger</code></td>
<td>NSLogger wire protocol + native macOS Bonjour</td>
<td align="center">✅ 139</td>
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
<td align="center"><strong><a href="eez-studio/agent-harness/">EEZ Studio</a></strong></td>
<td>Embedded UI / Instrument Automation</td>
<td><code>cli-anything-eez-studio</code></td>
<td>.eez-project JSON + EEZ Studio Node backend</td>
<td align="center">✅ <a href="eez-studio/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center"><strong>⛓️ ETH2 QuickStart</strong></td>
<td>DevOps / Ethereum</td>
<td><code>cli-anything-eth2-quickstart</code></td>
<td>eth2-quickstart shell automation + JSON health checks</td>
<td align="center">✅ 18</td>
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
<td align="center"><strong>🧬 <a href="unimol_tools/agent-harness/">Uni-Mol Tools</a></strong></td>
<td>Molecular Property Prediction (AI4S)</td>
<td><code>cli-anything-unimol-tools</code></td>
<td>Uni-Mol molecular ML backend</td>
<td align="center">✅ 67</td>
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
<td align="center"><strong>📦 <a href="sbox/agent-harness/">s&amp;box</a></strong></td>
<td>Game Development</td>
<td><code>cli-anything-sbox</code></td>
<td>Source 2 game engine - direct file I/O on .scene/.prefab/.vmat/.vsnd JSON</td>
<td align="center">✅ 244</td>
</tr>
<tr>
<td align="center"><strong>🐞 <a href="lldb/agent-harness/">LLDB</a></strong></td>
<td>Native Debugging</td>
<td><code>cli-anything-lldb</code></td>
<td>LLDB Python API</td>
<td align="center">✅ 27</td>
</tr>
<tr>
<td align="center"><strong>🟩 <a href="nsight-graphics/agent-harness/">Nsight Graphics CLI</a></strong></td>
<td>GPU Debugging &amp; Profiling</td>
<td><code>cli-anything-nsight-graphics</code></td>
<td>Official ngfx / ngfx-capture orchestration + GPU Trace summary + replay analysis</td>
<td align="center">✅ 51</td>
</tr>
<tr>
<td align="center"><strong>🔍 <a href="exa/agent-harness/">Exa</a></strong></td>
<td>AI-Native Web Search</td>
<td><code>cli-anything-exa</code></td>
<td>exa-py SDK</td>
<td align="center">✅ 40</td>
</tr>
<tr>
<td align="center"><strong>📈 <a href="unrealinsights/agent-harness/">Unreal Insights</a></strong></td>
<td>Performance Profiling</td>
<td><code>cli-anything-unrealinsights</code></td>
<td>Background trace sessions + engine-matched UnrealInsights build + headless export</td>
<td align="center">✅ 50</td>
</tr>
<tr>
<td align="center"><strong>☁️ <a href="cloudanalyzer/agent-harness/">CloudAnalyzer</a></strong></td>
<td>Point cloud / trajectory QA</td>
<td><code>cli-anything-cloudanalyzer</code></td>
<td>CloudAnalyzer (Python API)</td>
<td align="center">✅ 14</td>
</tr>
<tr>
<td align="center"><strong>🗺️ <a href="QGIS/agent-harness/">QGIS</a></strong></td>
<td>Geospatial Analysis &amp; Mapping</td>
<td><code>cli-anything-qgis</code></td>
<td>PyQGIS + qgis_process</td>
<td align="center">✅ 22</td>
</tr>
<tr>
<td align="center"><strong>🔩 <a href="3MF/agent-harness/">3MF</a></strong></td>
<td>Mesh geometry editor for 3D printing</td>
<td><code>cli-anything-3mf</code></td>
<td>numpy, scipy, trimesh</td>
<td align="center">✅ 50</td>
</tr>
<tr>
<td align="center"><strong>🗄️ <a href="tigris/agent-harness/">Tigris</a></strong></td>
<td>Object Storage (S3-compatible, global, no egress) — buckets, objects, snapshots, IAM, access keys</td>
<td><code>cli-anything-tigris</code></td>
<td>subprocess wrapping the official <code>tigris</code> CLI</td>
<td align="center">✅ <a href="tigris/agent-harness/">New</a></td>
</tr>
<tr>
<td align="center" colspan="4"><strong>Total</strong></td>
<td align="center"><strong>✅ 2,461</strong></td>
</tr>
</table>

> **100% pass rate** across all 2,461 tests — 1,732 unit tests + 579 end-to-end tests + 19 Node.js tests.

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
wavetone       30 passed  ✅   (24 unit + 6 default e2e, 2 backend-gated e2e skipped; 32 passed opt-in)
libreoffice   158 passed  ✅   (89 unit + 69 e2e)
mubu           96 passed  ✅   (85 unit + 11 e2e)
obs-studio    153 passed  ✅   (116 unit + 37 e2e)
nslogger      139 passed  ✅   (97 unit + 42 e2e)
kdenlive      155 passed  ✅   (111 unit + 44 e2e)
shotcut       154 passed  ✅   (110 unit + 44 e2e)
zoom           22 passed  ✅   (22 unit + 0 e2e)
drawio        138 passed  ✅   (116 unit + 22 e2e)
eth2-quickstart 18 passed ✅   (18 unit + 3 e2e skipped)
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
lldb           27 passed  ✅   (23 unit + 4 e2e)
nsight-graphics 51 passed ✅   (46 unit/CLI + 5 local e2e)
unrealinsights 50 passed  ✅   (49 unit + 1 e2e, 9 backend-gated e2e skipped)
cloudanalyzer  14 passed  ✅   (7 unit + 7 e2e)
3mf            50 passed  ✅   (50 unit)
joplin        134 passed  ✅   (107 unit + 27 e2e, 1 skipped on Windows)
──────────────────────────────────────────────────────────────────────────────
TOTAL        2,461 passed  ✅   100% pass rate
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
├── 🤖 codex-skill/                      # Self-contained Codex skill installer
│   ├── SKILL.md                         # Codex workflow entry point
│   ├── agents/                          # Codex UI metadata
│   ├── scripts/                         # Bash and PowerShell installers
│   └── tests/                           # Installer resource-sync regression test
├── 🧭 hermes-skill/                     # Hermes Agent skill entry point
├── 🧠 reasonix-skill/                   # Reasonix skill entry point
├── 🎨 gimp/agent-harness/               # GIMP CLI (107 tests)
├── 🧊 blender/agent-harness/            # Blender CLI (208 tests)
├── ✏️ inkscape/agent-harness/            # Inkscape CLI (202 tests)
├── 🎵 audacity/agent-harness/           # Audacity CLI (161 tests)
├── wavetone/agent-harness/              # WaveTone CLI (32 tests: 30 default + 2 backend-gated e2e)
├── 🌐 browser/agent-harness/            # Browser CLI (DOMShell MCP, new)
├── 🌐 web-yu-pri/agent-harness/         # Japan Post Web Yu-pri CLI (new)
├── 📄 libreoffice/agent-harness/        # LibreOffice CLI (158 tests)
├── 🧹 openrefine/agent-harness/         # OpenRefine CLI (76 tests: 64 unit + 12 real backend e2e)
├── 📧 mailchimp/agent-harness/          # Mailchimp Marketing API CLI (303 commands, 36 unit tests)
├── 📚 zotero/agent-harness/             # Zotero CLI (new, write import support)
├── 📖 calibre/agent-harness/            # Calibre CLI (58 tests: 38 unit + 20 E2E)
├── 📓 joplin/agent-harness/             # Joplin CLI (134 tests: 107 unit + 27 e2e)
├── 📝 mubu/agent-harness/               # Mubu CLI (96 tests)
├── 📹 obs-studio/agent-harness/         # OBS Studio CLI (153 tests)
├── 📱 nslogger/agent-harness/           # NSLogger CLI (139 tests)
├── 🎞️ kdenlive/agent-harness/           # Kdenlive CLI (155 tests)
├── 🎬 shotcut/agent-harness/            # Shotcut CLI (154 tests)
├── 📞 zoom/agent-harness/               # Zoom CLI (22 tests)
├── 🎵 musescore/agent-harness/          # MuseScore CLI (56 tests)
├── 📐 drawio/agent-harness/             # Draw.io CLI (138 tests)
├── 🧪 eez-studio/agent-harness/         # EEZ Studio CLI (project, LVGL, SCPI automation)
├── ⛓️ eth2-quickstart/agent-harness/    # ETH2 QuickStart CLI (18 unit, 3 e2e skipped)
├── 🧜 mermaid/agent-harness/            # Mermaid Live Editor CLI (10 tests)
├── ✨ anygen/agent-harness/             # AnyGen CLI (50 tests)
├── 🖼️ comfyui/agent-harness/            # ComfyUI CLI (70 tests)
├── 🧠 notebooklm/agent-harness/         # NotebookLM CLI (experimental, 21 tests)
├── 🧩 dify-workflow/agent-harness/      # Dify Workflow CLI wrapper (11 tests)
├── 🛡️ adguardhome/agent-harness/       # AdGuard Home CLI (36 tests)
├── 🦙 ollama/agent-harness/             # Ollama CLI (98 tests)
├── 🎮 godot/agent-harness/              # Godot Engine CLI (24 tests)
├── 📦 sbox/agent-harness/               # s&box CLI (244 tests: 157 unit + 17 orchestrator + 50 e2e + 20 exit-code)
├── 🎨 sketch/agent-harness/             # Sketch CLI (19 tests, Node.js)
├── 🔬 renderdoc/agent-harness/          # RenderDoc CLI (59 tests)
├── 🟩 nsight-graphics/agent-harness/    # Nsight Graphics CLI (51 tests)
├── 🐞 lldb/agent-harness/               # LLDB CLI (27 tests)
├── 📈 unrealinsights/agent-harness/     # Unreal Insights CLI (50 tests)
├── 🎬 videocaptioner/agent-harness/     # VideoCaptioner CLI (26 tests)
├── 🎬 openscreen/agent-harness/         # Openscreen CLI — screen recording editor (101 tests)
├── ☁️ cloudcompare/agent-harness/       # CloudCompare CLI (88 tests)
├── 🔍 exa/agent-harness/               # Exa CLI (40 tests)
└── ⛅ cloudanalyzer/agent-harness/      # CloudAnalyzer CLI (14 tests)
└── 🔩 3MF/agent-harness/               # 3MF Mesh Editor CLI (50+ tests)
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

The playbook distills key insights from successfully building all 18 diverse, production-ready harnesses.

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

### For CLI-Hub Users

```bash
# Install the package manager
pip install cli-anything-hub

# Browse, search, inspect, and install CLIs
cli-hub list
cli-hub search <query>
cli-hub info <name>
cli-hub install <name>

# Manage installed CLIs
cli-hub update <name>
cli-hub uninstall <name>
cli-hub launch <name> [args...]
```

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

## 📚 Citation

If you find CLI-Anything useful, please cite our technical report:

```bibtex
@misc{yang2026clianythingagentnativecomputeruse,
      title={CLI-Anything: Towards Agent-Native Computer Use}, 
      author={Yuhao Yang and Tianyu Fan and Chao Huang},
      year={2026},
      eprint={2606.03854},
      archivePrefix={arXiv},
      primaryClass={cs.HC},
      url={https://arxiv.org/abs/2606.03854}, 
}
```

---

## 📄 License

Apache License 2.0 — free to use, modify, and distribute.

---

<div align="center">

**CLI-Anything** — *Make any software with a codebase Agent-native.*

<sub>A methodology for the age of AI agents | 18 professional software demos | 2,280 passing tests</sub>

<br>

<img src="assets/icon.png" alt="CLI-Anything Icon" width="80">

</div>

<p align="center">
  <em> Thanks for visiting ✨ CLI-Anything!</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.CLI-Anything&style=for-the-badge&color=00d4ff" alt="Views">
</p>
