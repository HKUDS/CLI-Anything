<h1 align="center"><img src="assets/icon.png" alt="" width="64" style="vertical-align: middle;">&nbsp; CLI-Anything: 让所有软件都能被 Agent 驱动</h1>

<p align="center">
  <strong>今天的软件为人而生👨‍💻，明天的用户是 Agent🤖<br>
CLI-Anything：连接 AI Agent 与全世界软件的桥梁</strong><br>
</p>

**🌐 [CLI-Hub](https://hkuds.github.io/CLI-Anything/)**：在 **[CLI-Hub](https://hkuds.github.io/CLI-Anything/)** 探索社区已构建的所有 CLI，一条命令即可安装。想贡献你的 CLI？[提交 PR](https://github.com/HKUDS/CLI-Anything/blob/main/CONTRIBUTING.md) — Hub 会即时更新。

<p align="center">
  <a href="#-快速上手"><img src="https://img.shields.io/badge/快速上手-5_分钟-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="#-实测展示"><img src="https://img.shields.io/badge/Demo-13_款软件-green?style=for-the-badge" alt="Demos"></a>
  <a href="#-测试结果"><img src="https://img.shields.io/badge/测试-1%2C741_通过-brightgreen?style=for-the-badge" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/click-≥8.0-green" alt="Click">
  <img src="https://img.shields.io/badge/pytest-100%25_pass-brightgreen" alt="Pytest">
  <img src="https://img.shields.io/badge/coverage-unit_%2B_e2e-orange" alt="Coverage">
  <img src="https://img.shields.io/badge/output-JSON_%2B_Human-blueviolet" alt="Output">
  <a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/飞书-交流群-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
<a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/微信-交流群-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
</p>

**一行命令**，让任意软件接入 OpenClaw、nanobot、Cursor、Claude Code 等 Agent 框架。

<p align="center">
  <img src="assets/cli-typing.gif" alt="CLI-Anything typing demo" width="800">
</p>

<p align="center">
  <img src="assets/teaser.png" alt="CLI-Anything Teaser" width="800">
</p>

---

## 🤔 为什么是 CLI？

CLI 是人类和 AI Agent 共通的万能接口：

• **结构化、可组合** - 文本命令天然匹配 LLM 的输入格式，可自由串联成复杂工作流

• **轻量且通用** - 几乎零开销，跨平台运行，不依赖额外环境

• **自描述** - 一个 `--help` 就能让 Agent 自动发现所有功能

• **久经验证** - Claude Code 每天通过 CLI 执行数以千计的真实任务

• **Agent 友好** - 结构化 JSON 输出，Agent 无需任何额外解析

• **确定且可靠** - 输出稳定一致，Agent 行为可预测

## 🚀 快速上手

### 环境要求

- **Python 3.10+**
- 目标软件已安装（如 GIMP、Blender、LibreOffice 或你自己的应用）
- 支持的 AI 编程工具之一：[Claude Code](#-claude-code) | [OpenClaw](#-openclaw) | [OpenCode](#-opencode) | [Codex](#-codex) | [Qodercli](#-qodercli) | [GitHub Copilot CLI](#-github-copilot-cli) | [更多平台](#-更多平台即将支持)

### 选择你的平台

<details open>
<summary><h4 id="-claude-code">⚡ Claude Code</h4></summary>

**第一步：添加插件市场**

CLI-Anything 以 Claude Code 插件市场的形式托管在 GitHub 上。

```bash
# 添加 CLI-Anything 插件市场
/plugin marketplace add HKUDS/CLI-Anything
```

**第二步：安装插件**

```bash
# 从市场安装 cli-anything 插件
/plugin install cli-anything
```

搞定。插件已经在你的 Claude Code 会话中可用了。

**Windows 注意：** Claude Code 通过 `bash` 执行命令。Windows 下请安装 Git for Windows（包含 `bash` 和 `cygpath`）
或使用 WSL，否则可能出现 `cygpath: command not found`。

**第三步：一行命令生成 CLI**

```bash
# /cli-anything <软件路径或仓库地址>
# 为 GIMP 生成完整的 CLI（7 个阶段全自动）
/cli-anything ./gimp

# 兼容写法（旧版本 Claude Code 可重试）
# /cli-anything:cli-anything ./gimp
```

Claude Code 不同版本的命令兼容说明：
- 优先使用 `/cli-anything` 作为主入口。
- 在已**确认插件已安装并加载**的情况下，若旧版本的 Claude Code 不识别 `/cli-anything`，可尝试兼容写法 `/cli-anything:cli-anything`。
- 其他辅助命令保持 `:子命令` 形式（例如 `/cli-anything:refine`）。

如果出现 `Unknown skill: cli-anything`，两种写法都引用同一个 skill 名称，切换写法无法解决，请优先排查插件是否已安装/加载：
1. 重新加载插件命令：`/reload-plugins`
2. 验证插件是否已加载：`/help cli-anything`（能看到 CLI-Anything 帮助即表示已加载）
3. 如仍未识别，重新从市场安装：
   - `/plugin marketplace add HKUDS/CLI-Anything`
   - `/plugin install cli-anything`
4. 确认插件可用后，再重试入口命令：
   - 推荐：`/cli-anything ./gimp`
   - 仅旧版本：`/cli-anything:cli-anything ./gimp`

完整流水线自动执行：
1. 🔍 **分析** — 扫描源码，将 GUI 操作映射到 API
2. 📐 **设计** — 规划命令分组、状态模型、输出格式
3. 🔨 **实现** — 构建 Click CLI，包含 REPL、JSON 输出、撤销/重做
4. 📋 **规划测试** — 生成 TEST.md，涵盖单元测试和端到端测试计划
5. 🧪 **编写测试** — 实现完整测试套件
6. 📝 **文档** — 更新 TEST.md，写入测试结果
7. 📦 **发布** — 生成 `setup.py`，安装到 PATH

**第四步（可选）：优化和扩展 CLI**

初始构建完成后，你可以迭代优化 CLI，扩展覆盖面并补充缺失的功能：

```bash
# 全面优化 — Agent 分析所有功能的覆盖差距
/cli-anything:refine ./gimp

# 定向优化 — 指定特定功能领域
/cli-anything:refine ./gimp "我需要更多图像批处理和滤镜相关的 CLI"
```

优化命令会对软件的完整功能与当前 CLI 覆盖范围进行差距分析，然后为识别到的差距实现新命令、测试和文档。你可以多次运行该命令，逐步扩大功能覆盖范围 — 每次运行都是增量的、非破坏性的。

<details>
<summary><strong>备选方案：手动安装</strong></summary>

如果你不想用插件市场：

```bash
# 克隆仓库
git clone https://github.com/HKUDS/CLI-Anything.git

# 复制插件到 Claude Code 插件目录
cp -r CLI-Anything/cli-anything-plugin ~/.claude/plugins/cli-anything

# 重新加载插件
/reload-plugins
```

</details>

</details>

<details>
<summary><h4 id="-opencode">⚡ OpenCode （实验性支持）</h4></summary>

**第一步：安装命令**

**注意：** 请升级到最新 OpenCode，旧版本可能使用不同的命令目录路径。

将 CLI-Anything 命令**和** `HARNESS.md` 复制到 OpenCode 命令目录：

```bash
# 克隆仓库
git clone https://github.com/HKUDS/CLI-Anything.git

# 全局安装（所有项目可用）
cp CLI-Anything/opencode-commands/*.md ~/.config/opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md ~/.config/opencode/commands/

# 或项目级安装
cp CLI-Anything/opencode-commands/*.md .opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md .opencode/commands/
```

> **注意：** `HARNESS.md` 是所有命令引用的方法论规范，必须和命令文件放在同一目录下。

安装后获得 5 个斜杠命令：`/cli-anything`、`/cli-anything-refine`、`/cli-anything-test`、`/cli-anything-validate` 和 `/cli-anything-list`。

**第二步：一行命令生成 CLI**

```bash
# 为 GIMP 生成完整的 CLI（7 个阶段全自动）
/cli-anything ./gimp

# 从 GitHub 仓库构建
/cli-anything https://github.com/blender/blender
```

命令以子任务方式运行，遵循与 Claude Code 相同的 7 阶段方法论。

**第三步（可选）：优化和扩展 CLI**

```bash
# 全面优化 — Agent 分析所有功能的覆盖差距
/cli-anything-refine ./gimp

# 定向优化 — 指定特定功能领域
/cli-anything-refine ./gimp "批处理和滤镜"
```

</details>

<details>

<summary><h4 id="-qodercli">⚡ Qodercli <sup><code>社区贡献</code></sup></h4></summary>

**第一步：注册插件**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
bash CLI-Anything/qoder-plugin/setup-qodercli.sh
```

脚本会将 cli-anything 插件注册到 `~/.qoder.json`。注册后开启新的 Qodercli 会话即可使用。

**第二步：在 Qodercli 中使用 CLI-Anything**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "批处理和滤镜"
/cli-anything:validate ./gimp
```
</details>

<details>

<summary><h4 id="-openclaw">⚡ OpenClaw</h4></summary>

**第一步：安装 Skill**

CLI-Anything 提供了原生的 OpenClaw `SKILL.md` 文件。请将其复制到你的 OpenClaw 技能目录：

```bash
# Clone the repo
git clone https://github.com/HKUDS/CLI-Anything.git

# Install to the global skills folder
mkdir -p ~/.openclaw/skills/cli-anything
cp CLI-Anything/openclaw-skill/SKILL.md ~/.openclaw/skills/cli-anything/SKILL.md
```

**第二步：构建 CLI**

安装完成后，你就可以在 OpenClaw 中直接调用：

`@cli-anything build a CLI for ./gimp`

该技能采用了与 Claude Code 和 OpenCode 一致的 7 步构建流程。

</details>

<details>

<summary><h4 id="-codex">⚡ Codex <sup><code>实验性</code></sup> <sup><code>社区贡献</code></sup></h4></summary>

**第一步：安装 Skill**

运行仓库内置的安装脚本：

```bash
# 克隆仓库
git clone https://github.com/HKUDS/CLI-Anything.git

# 安装 skill
bash CLI-Anything/codex-skill/scripts/install.sh
```

在 Windows PowerShell 中，可以使用：

```powershell
.\CLI-Anything\codex-skill\scripts\install.ps1
```

脚本会把 skill 安装到 `$CODEX_HOME/skills/cli-anything`；如果没有设置 `CODEX_HOME`，则默认安装到 `~/.codex/skills/cli-anything`。

安装后重启 Codex，让它重新发现这个 skill。

**第二步：在 Codex 里使用 CLI-Anything**

直接用自然语言描述任务，例如：

```text
Use CLI-Anything to build a harness for ./gimp
Use CLI-Anything to refine ./shotcut for picture-in-picture workflows
Use CLI-Anything to validate ./libreoffice
```

这个 Codex skill 复用了 Claude Code 插件和 OpenCode 命令所使用的同一套方法论，
不会改变生成出来的 Python harness 结构。

</details>

<details>

<summary><h4 id="-github-copilot-cli">⚡ GitHub Copilot CLI <sup><code>社区贡献</code></sup></h4></summary>

**第一步：安装插件**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything
copilot plugin install ./cli-anything-plugin
```

这将 CLI-Anything 插件安装到 GitHub Copilot CLI 中。插件应该已经在你的 GitHub Copilot CLI 会话中可用了。

**第二步：在 GitHub Copilot CLI 中使用 CLI-Anything**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "批处理和滤镜"
/cli-anything:validate ./gimp
```

</details>

<details>
<summary><h4 id="-更多平台即将支持">🔮 更多平台（即将支持）</h4></summary>

CLI-Anything 的设计是平台无关的，计划支持更多 AI 编程工具：

- **Codex** — 已通过 `codex-skill/` 提供接入
- **Cursor** — 即将支持
- **Windsurf** — 即将支持
- **你喜欢的工具** — 欢迎贡献！参考 `opencode-commands/` 目录的实现。

</details>

### 开始使用生成的 CLI

无论你用哪个平台构建，生成的 CLI 使用方式完全一样：

```bash
# 安装到 PATH
cd gimp/agent-harness && pip install -e .

# 随处可用
cli-anything-gimp --help
cli-anything-gimp project new --width 1920 --height 1080 -o poster.json
cli-anything-gimp --json layer add -n "Background" --type solid --color "#1a1a2e"

# 进入交互式 REPL
cli-anything-gimp
```

---

## 💡 CLI-Anything 的愿景：构建 Agent 原生的软件生态

• 🌐 **无门槛接入** - 任何软件都能通过结构化 CLI 即刻被 Agent 操控。

• 🔗 **无缝集成** - 不需要专门的 API、不需要操控 GUI、不需要重构代码，也不需要复杂的适配层。

• 🚀 **面向未来** - 一条命令，就能把为人类设计的软件变成 Agent 的原生工具。

---

## 🔧 适用场景

| 类别 | 如何接入 Agent | 典型软件 |
|------|--------------|---------|
| **📂 GitHub 开源项目** | 通过自动生成 CLI，将任意开源项目转化为 Agent 可控工具 | VSCodium、WordPress、Calibre、Zotero、Joplin、Logseq、Penpot、Super Productivity |
| **🤖 AI/ML 平台** | 用结构化命令驱动模型训练、推理流水线和超参搜索 | Stable Diffusion WebUI、ComfyUI、InvokeAI、Text-generation-webui、Open WebUI、Fooocus、Kohya_ss、AnythingLLM、SillyTavern |
| **📊 数据与分析** | 以编程方式完成数据处理、可视化和统计分析工作流 | JupyterLab、Apache Superset、Metabase、Redash、DBeaver、KNIME、Orange、OpenSearch Dashboards、Lightdash |
| **💻 开发工具** | 通过 CLI 串联代码编辑、构建、测试与部署流程 | Jenkins、Gitea、Hoppscotch、Portainer、pgAdmin、SonarQube、ArgoCD、OpenLens、Insomnia、Beekeeper Studio |
| **🎨 创意与媒体** | 以编程方式控制内容创作、编辑和渲染工作流 | Blender、GIMP、OBS Studio、Audacity、Krita、Kdenlive、Shotcut、Inkscape、Darktable、LMMS、Ardour |
| **📐 图表与可视化** | 以编程方式创建和操作流程图、架构图、ER 图等各类图表 | Draw.io (diagrams.net)、Mermaid、PlantUML、Excalidraw、yEd |
| **🔬 科学计算** | 自动化科研工作流、仿真模拟和复杂计算 | ImageJ、FreeCAD、QGIS、ParaView、Gephi、LibreCAD、Stellarium、KiCad、JASP、Jamovi |
| **🏢 企业与办公** | 将商业应用和生产力工具转化为 Agent 可访问的系统 | NextCloud、GitLab、Grafana、Mattermost、LibreOffice、AppFlowy、NocoDB、Odoo (Community)、Plane、ERPNext |
| **📞 通信与协作** | 通过结构化 CLI 自动化会议调度、参会人管理、录制获取和报告生成 | Zoom、Jitsi Meet、BigBlueButton、Mattermost |

---

## CLI-Anything 的核心优势

### Agent 与软件之间的鸿沟

AI Agent 推理能力很强，但操控真实专业软件的能力很弱。现有方案要么是脆弱的 GUI 自动化，要么是覆盖面有限的 API，要么是阉割了 90% 功能的重新实现。

**CLI-Anything 的解法**：把任何专业软件变成 Agent 原生工具，功能一个不少。

| **现有痛点** | **CLI-Anything 怎么解** |
|------------|----------------------|
| 🤖 "AI 用不了真正的专业工具" | 直接对接真实软件后端（Blender、LibreOffice、FFmpeg）—— 完整的专业能力，零妥协 |
| 💸 "GUI 自动化三天两头崩" | 告别截图、点击和 RPA 的脆弱性，纯命令行操控，结构化接口 |
| 📊 "Agent 需要结构化数据" | 内置 JSON 输出供 Agent 直接消费，同时保留可读格式方便调试 |
| 🔧 "定制集成太贵了" | 一个插件就能为任意代码库自动生成 CLI，经过验证的 7 阶段流水线 |
| ⚡ "原型和生产之间差十万八千里" | 1,752+ 测试用例，全部在真实软件上验证通过，覆盖 13 款主流应用 |

---

## 🎯 CLI-Anything 能做什么？

<table>
<tr>
<td width="33%">

### 🛠️ 让 Agent 接管你的工作流

不管是专业场景还是日常事务 —— 把代码库扔给 `/cli-anything` 就行。GIMP、Blender、Shotcut 搞创作，LibreOffice、OBS Studio 干日常。没有源码？找个开源替代品，照样能用。你会立刻得到一套 Agent 可以直接调用的完整 CLI。

</td>
<td width="33%">

### 🔗 把散装 API 统一成一个 CLI

受够了一堆零碎的 Web 服务 API？把文档或 SDK 手册喂给 `/cli-anything`，你的 Agent 就能拿到一个**有状态的、功能完整的 CLI**，把那些零散的接口整合成逻辑清晰的命令组。一个工具可替代几十个裸 API 调用 —— 能力更强，token 更省。

</td>
<td width="33%">

### 🚀 取代 GUI Agent，或让它更强

CLI-Anything 可直接**替代基于 GUI 的 Agent 方案** —— 无需截图，也无需繁琐地点击像素操作。更实用的是：只要你对 GUI 软件执行过 `/cli-anything` 命令，就能**全自动生成 Agent 任务、评测器及 Benchmark** —— 全程采用纯代码与终端操作，支持迭代优化，显著提升效率。

</td>
</tr>
</table>

---

## ✨ ⚙️ CLI-Anything 的工作方式

<table>
<tr>
<td width="50%">

### 🏗️ 全自动 7 阶段流水线

从代码分析到发布上线 —— 插件自动完成架构设计、代码实现、测试规划、测试编写和文档生成，全程无需人工介入。

</td>
<td width="50%">

### 🎯 真实软件集成

直接调用真实应用进行渲染。LibreOffice 生成 PDF，Blender 渲染 3D 场景，Audacity 通过 sox 处理音频。**零妥协**，**零玩具实现**。

</td>
</tr>
<tr>
<td width="50%">

### 🔁 智能会话管理

持久化项目状态，支持撤销/重做，加上统一的 REPL 交互界面（ReplSkin），所有 CLI 的使用体验保持一致。

</td>
<td width="50%">

### 📦 零配置安装

`pip install -e .` 即可将 cli-anything-<软件名> 装到 PATH。Agent 通过标准的 `which` 命令发现工具，不需要额外配置。

</td>
</tr>
<tr>
<td width="50%">

### 🧪 生产级测试

多层验证：使用合成数据的单元测试、使用真实文件和软件的端到端测试，外加已安装命令的 CLI 子进程验证。

</td>
<td width="50%">

### 🐍 干净的包架构

所有 CLI 统一在 cli_anything.* 命名空间下 —— 无冲突、可 pip 安装、命名规范统一：cli-anything-gimp、cli-anything-blender 等。

</td>
</tr>
</table>

---

## 🎬 实测展示

### 🎯 通用性

CLI-Anything 适用于任何有代码库的软件 —— 不限领域，不限架构。

### 🏭 专业级测试

在 13 款复杂应用上进行了实测，涵盖创意、生产力、通信、图表、原生调试、GPU 分析和 AI 内容生成领域 —— 这些软件此前对 AI Agent 来说几乎不可触及。

### 🎨 覆盖多元领域

从创意工作流（图像编辑、3D 建模、矢量图形）到生产工具（音频、办公、直播、视频剪辑）。

### ✅ 完整的 CLI 生成

每款软件都生成了完整的、可投产的 CLI 接口 —— 不是 demo，而是保留全部功能的完整工具接入。

<table>
<tr>
<th align="center">软件</th>
<th align="center">领域</th>
<th align="center">CLI 命令</th>
<th align="center">后端</th>
<th align="center">测试</th>
</tr>
<tr>
<td align="center"><strong>🎨 GIMP</strong></td>
<td>图像编辑</td>
<td><code>cli-anything-gimp</code></td>
<td>Pillow + GEGL/Script-Fu</td>
<td align="center">✅ 107</td>
</tr>
<tr>
<td align="center"><strong>🧊 Blender</strong></td>
<td>3D 建模与渲染</td>
<td><code>cli-anything-blender</code></td>
<td>bpy (Python scripting)</td>
<td align="center">✅ 208</td>
</tr>
<tr>
<td align="center"><strong>✏️ Inkscape</strong></td>
<td>矢量图形</td>
<td><code>cli-anything-inkscape</code></td>
<td>Direct SVG/XML manipulation</td>
<td align="center">✅ 202</td>
</tr>
<tr>
<td align="center"><strong>🎵 Audacity</strong></td>
<td>音频制作</td>
<td><code>cli-anything-audacity</code></td>
<td>Python wave + sox</td>
<td align="center">✅ 161</td>
</tr>
<tr>
<td align="center"><strong>📄 LibreOffice</strong></td>
<td>办公套件（Writer、Calc、Impress）</td>
<td><code>cli-anything-libreoffice</code></td>
<td>ODF generation + headless LO</td>
<td align="center">✅ 158</td>
</tr>
<tr>
<td align="center"><strong>📚 <a href="zotero/agent-harness/">Zotero</a></strong></td>
<td>文献管理与引用</td>
<td><code>cli-anything-zotero</code></td>
<td>Local SQLite + connector + Local API</td>
<td align="center">✅ <a href="zotero/agent-harness/">新增</a></td>
</tr>
<tr>
<td align="center"><strong>📹 OBS Studio</strong></td>
<td>直播与录制</td>
<td><code>cli-anything-obs-studio</code></td>
<td>JSON scene + obs-websocket</td>
<td align="center">✅ 153</td>
</tr>
<tr>
<td align="center"><strong>🎞️ Kdenlive</strong></td>
<td>视频剪辑</td>
<td><code>cli-anything-kdenlive</code></td>
<td>MLT XML + melt renderer</td>
<td align="center">✅ 155</td>
</tr>
<tr>
<td align="center"><strong>🎬 Shotcut</strong></td>
<td>视频剪辑</td>
<td><code>cli-anything-shotcut</code></td>
<td>Direct MLT XML + melt</td>
<td align="center">✅ 154</td>
</tr>
<tr>
<td align="center"><strong>🎬 <a href="openscreen/agent-harness/">Openscreen</a></strong></td>
<td>屏幕录像编辑器</td>
<td><code>cli-anything-openscreen</code></td>
<td>ffmpeg backend</td>
<td align="center">✅ 101</td>
</tr>
<tr>
<td align="center"><strong>📞 Zoom</strong></td>
<td>视频会议</td>
<td><code>cli-anything-zoom</code></td>
<td>Zoom REST API (OAuth2)</td>
<td align="center">✅ 22</td>
</tr>
<tr>
<td align="center"><strong>📐 Draw.io</strong></td>
<td>图表绘制</td>
<td><code>cli-anything-drawio</code></td>
<td>mxGraph XML + draw.io CLI</td>
<td align="center">✅ 138</td>
</tr>
<tr>
<td align="center"><strong>✨ AnyGen</strong></td>
<td>AI 内容生成</td>
<td><code>cli-anything-anygen</code></td>
<td>AnyGen REST API (anygen.io)</td>
<td align="center">✅ 50</td>
</tr>
<tr>
<td align="center"><strong>🐞 <a href="lldb/agent-harness/">LLDB</a></strong></td>
<td>原生调试</td>
<td><code>cli-anything-lldb</code></td>
<td>LLDB Python API</td>
<td align="center">✅ 27</td>
</tr>
<tr>
<td align="center"><strong>🟩 <a href="nsight-graphics/agent-harness/">Nsight Graphics CLI</a></strong></td>
<td>GPU 调试与分析</td>
<td><code>cli-anything-nsight-graphics</code></td>
<td>官方 ngfx / ngfx-capture 编排 + GPU Trace 摘要 + replay 分析</td>
<td align="center">✅ 51</td>
</tr>
<tr>
<td align="center"><strong>📈 <a href="unrealinsights/agent-harness/">Unreal Insights</a></strong></td>
<td>性能分析</td>
<td><code>cli-anything-unrealinsights</code></td>
<td>后台 trace 会话 + 匹配版 UnrealInsights 构建 + 无头导出</td>
<td align="center">✅ 50</td>
</tr>
<tr>
<td align="center"><strong>🎨 Sketch</strong></td>
<td>UI 设计</td>
<td><code>sketch-cli</code></td>
<td>sketch-constructor (Node.js)</td>
<td align="center">✅ 19</td>
</tr>
<tr>
<td align="center" colspan="4"><strong>合计</strong></td>
<td align="center"><strong>✅ 1,752</strong></td>
</tr>
</table>

> 全部 1,752 项测试 **100% 通过** —— 1,266 项单元测试 + 467 项端到端测试 + 19 项 Node.js 测试。

---

## 📊 测试结果

每个 CLI 都经过多层严格测试，确保生产可用：

| 测试层级 | 测什么 | 示例 |
|---------|-------|------|
| **单元测试** | 每个核心函数的隔离验证，使用合成数据 | `test_core.py` — 项目创建、图层操作、滤镜参数 |
| **端到端测试（原生）** | 项目文件的完整生成流程 | ODF ZIP 结构合法性、MLT XML 正确性、SVG 格式完整性 |
| **端到端测试（真实后端）** | 调用真实软件并验证输出 | LibreOffice → 含 `%PDF-` 魔术字节的 PDF，Blender → 渲染后的 PNG |
| **CLI 子进程测试** | 通过 `subprocess.run` 调用已安装命令 | `cli-anything-gimp --json project new` → 合法 JSON 输出 |

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
openscreen    101 passed  ✅   (78 unit + 23 e2e)
zoom           22 passed  ✅   (22 unit + 0 e2e)
drawio        138 passed  ✅   (116 unit + 22 e2e)
anygen         50 passed  ✅   (40 unit + 10 e2e)
lldb           27 passed  ✅   (23 unit + 4 e2e)
nsight-graphics 51 passed ✅   (46 unit/CLI + 5 local e2e)
unrealinsights 50 passed  ✅   (49 unit + 1 e2e, 9 backend-gated e2e skipped)
sketch         19 passed  ✅   (19 jest, Node.js)
──────────────────────────────────────────────────────────────────────────────
TOTAL        1,752 passed  ✅   100% pass rate
```

---

## 🏗️ CLI-Anything 的架构

<p align="center">
  <img src="assets/architecture.png" alt="CLI-Anything Architecture" width="750">
</p>

### 🎯 核心设计原则

1. **真实软件集成** — CLI 生成合法的项目文件（ODF、MLT XML、SVG），然后交给真实应用去渲染。**我们做的是软件的结构化接口，而不是替代品**。
2. **灵活的交互模式** — 每个 CLI 都支持两种模式：有状态的 REPL 用于 Agent 交互会话，子命令模式用于脚本和流水线。**直接运行命令即进入 REPL**。
3. **一致的使用体验** — 所有生成的 CLI 共享统一的 REPL 界面（repl_skin.py），带有品牌横幅、风格化提示符、命令历史、进度指示器和标准化格式。
4. **Agent 原生设计** — 每个命令内置 `--json` 参数，输出结构化数据供 Agent 消费，同时可读的表格格式服务于交互调试。**Agent 通过标准的 `--help` 和 `which` 命令发现能力**。
5. **零妥协的依赖策略** — 真实软件是硬性要求 —— 没有兜底，没有降级。**后端缺失时测试直接失败（而非跳过），确保功能的真实性**。

---

## 📂 项目结构

```
cli-anything/
├── 📄 README.md                          # 英文文档
├── 📄 README_CN.md                       # 中文文档（你在这里）
├── 📁 assets/                            # 图片和媒体文件
│   ├── icon.png                          # 项目图标
│   └── teaser.png                        # 概览图
│
├── 🔌 cli-anything-plugin/               # Claude Code 插件
│   ├── HARNESS.md                        # 方法论 SOP（唯一权威来源）
│   ├── README.md                         # 插件文档
│   ├── QUICKSTART.md                     # 5 分钟快速上手
│   ├── PUBLISHING.md                     # 分发与发布指南
│   ├── repl_skin.py                      # 统一 REPL 界面
│   ├── commands/                         # 插件命令定义
│   │   ├── cli-anything.md               # 主构建命令
│   │   ├── refine.md                     # 扩展已有 harness 覆盖面
│   │   ├── test.md                       # 测试运行器
│   │   ├── validate.md                   # 标准验证
│   │   └── list.md                       # 列出所有 CLI 工具
│   └── scripts/
│       └── setup-cli-anything.sh         # 安装脚本
│
├── 📋 opencode-commands/                # OpenCode 命令
│   ├── cli-anything.md                  # 主构建命令
│   ├── cli-anything-refine.md           # 优化扩展命令
│   ├── cli-anything-test.md             # 测试运行器
│   ├── cli-anything-validate.md         # 标准验证
│   └── cli-anything-list.md             # 列出所有 CLI 工具
│
├── 🤖 codex-skill/                      # Codex skill 接入层
├── 🎨 gimp/agent-harness/               # GIMP CLI（107 项测试）
├── 🧊 blender/agent-harness/            # Blender CLI（208 项测试）
├── ✏️ inkscape/agent-harness/            # Inkscape CLI（202 项测试）
├── 🎵 audacity/agent-harness/           # Audacity CLI（161 项测试）
├── 📄 libreoffice/agent-harness/        # LibreOffice CLI（158 项测试）
├── 📚 zotero/agent-harness/             # Zotero CLI（新增，支持文献导入）
├── 📹 obs-studio/agent-harness/         # OBS Studio CLI（153 项测试）
├── 🎞️ kdenlive/agent-harness/           # Kdenlive CLI（155 项测试）
├── 🎬 shotcut/agent-harness/            # Shotcut CLI（154 项测试）
├── 🎬 openscreen/agent-harness/         # Openscreen CLI — 屏幕录像编辑器（101 项测试）
├── 📞 zoom/agent-harness/               # Zoom CLI（22 项测试）
├── 📐 drawio/agent-harness/             # Draw.io CLI（138 项测试）
├── ✨ anygen/agent-harness/             # AnyGen CLI（50 项测试）
├── 🟩 nsight-graphics/agent-harness/    # Nsight Graphics CLI（51 项测试）
├── 🐞 lldb/agent-harness/               # LLDB CLI（27 项测试）
├── 📈 unrealinsights/agent-harness/     # Unreal Insights CLI（50 项测试）
└── 🎨 sketch/agent-harness/             # Sketch CLI（19 项测试，Node.js）
```

每个 `agent-harness/` 包含一个可安装的 Python 包，位于 `cli_anything.<软件名>/` 下，包含 Click CLI、核心模块、工具类（含 `repl_skin.py` 和后端适配器）以及完整的测试。

---

## 🎯 插件命令

| 命令 | 说明 |
|-----|------|
| `/cli-anything <软件路径或仓库>` | 构建完整的 CLI —— 全部 7 个阶段 |
| `/cli-anything:refine <软件路径> [聚焦方向]` | 优化已有的 CLI —— 通过差距分析扩展覆盖面 |
| `/cli-anything:test <软件路径或仓库>` | 运行测试并更新 TEST.md |
| `/cli-anything:validate <软件路径或仓库>` | 按照 HARNESS.md 标准进行验证 |
| `/cli-anything:list` | 列出所有已安装和已生成的 CLI 工具 |

### 使用示例

```bash
# 从本地源码为 GIMP 构建完整 CLI
/cli-anything /home/user/gimp

# 从 GitHub 仓库构建
/cli-anything https://github.com/blender/blender

# 优化已有的 CLI —— 全面差距分析
/cli-anything:refine /home/user/gimp

# 带聚焦方向的优化
/cli-anything:refine /home/user/shotcut "画中画和视频叠加合成"

# 运行测试并更新 TEST.md
/cli-anything:test /home/user/inkscape

# 按照 HARNESS.md 标准验证
/cli-anything:validate /home/user/audacity
```

---

## 🎮 实际操作演示

以 `cli-anything-libreoffice` 为例，看看 Agent 能做什么：

```bash
# 创建一个 Writer 文档
$ cli-anything-libreoffice document new -o report.json --type writer
✓ Created Writer document: report.json

# 添加内容
$ cli-anything-libreoffice --project report.json writer add-heading -t "Q1 Report" --level 1
✓ Added heading: "Q1 Report"

$ cli-anything-libreoffice --project report.json writer add-table --rows 4 --cols 3
✓ Added 4×3 table

# 通过 LibreOffice headless 导出为真实 PDF
# 需要本机 PATH 中存在 LibreOffice/soffice 可执行文件。
$ cli-anything-libreoffice --project report.json export render output.pdf -p pdf --overwrite
✓ Exported: output.pdf (42,831 bytes) via libreoffice-headless

# JSON 模式供 Agent 消费
$ cli-anything-libreoffice --json document info --project report.json
{
  "name": "Q1 Report",
  "type": "writer",
  "pages": 1,
  "elements": 2,
  "modified": true
}
```

### REPL 模式

```
$ cli-anything-blender
╔══════════════════════════════════════════╗
║       cli-anything-blender v1.0.0       ║
║     Blender CLI for AI Agents           ║
╚══════════════════════════════════════════╝

blender> scene new --name ProductShot
✓ Created scene: ProductShot

blender[ProductShot]> object add cube --location 0,0,1
✓ Added cube: Cube

blender[ProductShot]*> render execute render.png --engine CYCLES --overwrite
✓ Rendered: /absolute/path/render0001.png (84,512 bytes) via blender-headless

blender[ProductShot]> exit
Goodbye! 👋
```

---

## 📖 标准手册：HARNESS.md

HARNESS.md 是我们通过自动化 CLI 生成，使任意软件具备 Agent 可用性的权威标准操作流程（SOP）。

它记录了在自动化生成过程中经验证并沉淀出的模式与方法论。

这本手册提炼了成功构建全部 13 套生产级 CLI 的关键经验。

### 核心经验

| 经验 | 说明 |
|-----|------|
| **必须用真实软件** | CLI 必须调用真实应用进行渲染。不能用 Pillow 替代 GIMP，不能自己写渲染器替代 Blender。正确做法：生成合法的项目文件 → 调用真实后端。 |
| **渲染鸿沟** | GUI 应用在渲染时才应用特效。如果你的 CLI 操作了项目文件但用了简陋的导出工具，特效会被静默丢弃。正确做法：原生渲染器 → 滤镜转译 → 渲染脚本。 |
| **滤镜转译** | 在不同格式间映射特效时（如 MLT → ffmpeg），要注意：重复滤镜合并、交错的流排序、参数空间差异、无法映射的特效。 |
| **时间码精度** | 非整数帧率（如 29.97fps）会导致累积舍入误差。用 `round()` 而非 `int()`，显示时用整数运算，测试中允许 ±1 帧容差。 |
| **输出验证** | 永远不要因为进程退出码为 0 就信任导出成功。要验证：魔术字节、ZIP/OOXML 结构、像素分析、音频 RMS 电平、时长检查。 |

> 完整方法论见：[`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md)

---

## 📦 安装与使用

### Claude Code 用户

```bash
# 添加市场并安装（推荐）
/plugin marketplace add HKUDS/CLI-Anything
/plugin install cli-anything

# 为任何有代码库的软件生成 CLI
/cli-anything:cli-anything <软件路径或仓库>
```

### OpenCode 用户

```bash
# 克隆仓库
git clone https://github.com/HKUDS/CLI-Anything.git

# 请确保使用最新 OpenCode，旧版本可能使用不同的命令目录路径
# 复制命令和 HARNESS.md 到 OpenCode 命令目录
cp CLI-Anything/opencode-commands/*.md ~/.config/opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md ~/.config/opencode/commands/

# 为任何有代码库的软件生成 CLI
/cli-anything <软件路径或仓库>
```

### 使用生成的 CLI

```bash
# 安装任意生成的 CLI
cd <软件名>/agent-harness
pip install -e .

# 验证安装
which cli-anything-<软件名>

# 开始使用
cli-anything-<软件名> --help
cli-anything-<软件名>                    # 进入 REPL
cli-anything-<软件名> --json <命令>      # JSON 输出供 Agent 使用
```

### 运行测试

```bash
# 运行某个 CLI 的测试
cd <软件名>/agent-harness
python3 -m pytest cli_anything/<软件名>/tests/ -v

# 强制安装模式（推荐用于验证）
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<软件名>/tests/ -v -s
```

---

## 🤝 参与贡献

欢迎贡献！CLI-Anything 天然支持扩展：

- **新的目标软件** — 用插件为任意有代码库的软件生成 CLI，然后通过 [`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md) 提交你的成果。
- **方法论改进** — 向 `HARNESS.md` 提 PR，把新的经验教训沉淀下来
- **插件增强** — 新命令、阶段优化、更好的验证逻辑
- **测试覆盖** — 更多端到端场景、边界情况、工作流测试

### 已知局限

- **依赖强大的基础模型** — CLI-Anything 依赖前沿级别的模型（如 Claude Opus 4.6、Claude Sonnet 4.6、GPT-5.4）才能可靠地生成 harness。较弱或较小的模型可能产出不完整或有误的 CLI，需要大量人工修正。
- **依赖可用的源代码** — `/cli-anything` 基于源码进行分析和生成。如果目标软件只提供编译后的二进制文件，需要反编译才能获取代码，harness 的质量和覆盖率会显著下降。
- **可能需要迭代优化** — 单次 `/cli-anything` 运行不一定能完整覆盖所有功能。通常需要执行一次或多次 `/refine` 命令，才能将 CLI 的性能和覆盖率推到生产级水平。

---

## 📖 文档

| 文档 | 说明 |
|-----|------|
| [`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md) | 方法论 SOP — 唯一权威来源 |
| [`cli-anything-plugin/README.md`](cli-anything-plugin/README.md) | 插件文档 — 命令、选项、阶段 |
| [`cli-anything-plugin/QUICKSTART.md`](cli-anything-plugin/QUICKSTART.md) | 5 分钟快速上手 |
| [`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md) | 分发与发布指南 |

每个生成的 CLI 还包含：

- `<软件名>.md` — 该应用的架构 SOP
- `tests/TEST.md` — 测试计划和结果文档

---

## ⭐ Star History

如果 CLI-Anything 帮到了你，给个 Star 吧！⭐

<!-- Uncomment when published:
<div align="center">
  <a href="https://star-history.com/#HKUDS/CLI-Anything&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
    </picture>
  </a>
</div>
-->

---

## 📄 License

MIT License — 可自由使用、修改和分发。

---

<div align="center">

**CLI-Anything** — *一行命令，让任何软件成为 Agent 的原生工具。*

<sub>为 AI Agent 时代而生 | 13 款专业软件实测 | 1,752 项测试全部通过</sub>

<br>

<img src="assets/icon.png" alt="CLI-Anything Icon" width="80">

</div>

<p align="center">
  <em>感谢访问 ✨ CLI-Anything！</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.CLI-Anything&style=for-the-badge&color=00d4ff" alt="Views">
</p>
