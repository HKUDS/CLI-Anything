# CLI-Anything Trae Integration Guide

This guide explains how to integrate CLI-Anything plugin with Trae IDE and use it to build CLI tools for applications like Shotcut.

## Table of Contents

1. [Background](#background)
2. [Prerequisites](#prerequisites)
3. [Configure MCP Server](#configure-mcp-server)
4. [Use MCP Server](#use-mcp-server)
5. [Install and Use Shotcut CLI](#install-and-use-shotcut-cli)
6. [FAQ](#faq)

---

## Background

### What is CLI-Anything?

CLI-Anything is a framework for building CLI interfaces for GUI applications. It converts any GUI application into a CLI tool that AI Agents can use.

### What is Trae?

Trae is an AI-native IDE developed by ByteDance, supporting AI capability extension through MCP (Model Context Protocol).

### Why MCP Server?

Trae and Claude Code use different plugin systems. Claude Code uses `.claude-plugin` directory, while Trae uses MCP Server mechanism. Therefore, CLI-Anything needs to be wrapped as an MCP Server to work with Trae.

---

## Prerequisites

### 1. Install Python Dependencies

```bash
pip install mcp click prompt-toolkit lxml pytest
```

### 2. Ensure CLI-Anything Plugin Exists

CLI-Anything plugin should be located at:
```
D:\AwesomeGithub\CLI-Anything\cli-anything-plugin\
```

This directory should contain:
- `commands/` - Command definition files
- `HARNESS.md` - Methodology documentation
- `mcp_server.py` - MCP Server implementation
- `.trae-plugin/` - Trae IDE configuration

---

## Configure MCP Server

### Step 1: Create .trae-plugin Directory

Create `.trae-plugin` directory under `cli-anything-plugin`:

```bash
mkdir cli-anything-plugin\.trae-plugin
```

### Step 2: Create mcp-config.json

Create `mcp-config.json` in `.trae-plugin` directory:

```json
{
  "mcpServers": {
    "cli-anything": {
      "command": "python",
      "args": [
        "D:\\AwesomeGithub\\CLI-Anything\\cli-anything-plugin\\mcp_server.py"
      ]
    }
  }
}
```

### Step 3: Create plugin.json

Create `plugin.json` in `.trae-plugin` directory:

```json
{
  "name": "cli-anything",
  "version": "1.0.0",
  "description": "Build CLI harnesses for any GUI application",
  "entry": "mcp_server.py"
}
```

---

## Use MCP Server

### In Trae IDE:

1. Open Settings → Plugins
2. Find "MCP Servers" or "Custom Servers"
3. Click "Add Server"
4. Select the `mcp-config.json` file from `cli-anything-plugin\.trae-plugin\`
5. Restart Trae IDE

After configuration, you can use the `cli_anything` tool in Trae's AI chat to build CLI tools for any application.

---

## Install and Use Shotcut CLI

### Build CLI for Shotcut

In Trae IDE, use the following command:

```
Use cli_anything to build a CLI tool for Shotcut, path is D:\AwesomeGithub\shotcut
```

### Install the Built CLI

```bash
cd D:\AwesomeGithub\shotcut\agent-harness
pip install -e .
```

### Run Tests

```bash
cd D:\AwesomeGithub\shotcut\agent-harness
python -m pytest cli_anything/shotcut/tests/ -v
```

### Use Shotcut CLI

```bash
shotcut-cli --help
```

---

## FAQ

### Q: MCP Server fails to start?

A: Check Python path in `mcp-config.json` is correct. Ensure all dependencies are installed.

### Q: Tool not available in Trae?

A: Restart Trae IDE after configuring MCP Server. Check plugin settings.

### Q: How to update CLI-Anything?

A: Pull latest changes from repository and restart Trae IDE.

---

For more information, visit: https://github.com/HKUDS/CLI-Anything
