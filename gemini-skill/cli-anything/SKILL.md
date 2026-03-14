---
name: cli-anything
description: Automatically generate, test, and maintain Agent-Native CLIs for existing software. Designed for integrating complex GUI software (e.g., Blender, GIMP, LibreOffice) into AI agent workflows with structured control capabilities.
---

# CLI-Anything: Empowering Software with Agent-Native Capabilities

## Core Vision
CLI-Anything aims to bridge the gap between AI agents and complex software. By generating structured CLIs, AI agents can control software with the same precision and reliability as a human interacting with a GUI.

## The 7-Stage Automation Pipeline

Follow this Standard Operating Procedure (SOP) when tasked with "Creating a CLI for [Software Name]":

### 1. Analyze
- Scan the source code to identify core APIs, underlying libraries (e.g., Blender's `bpy`), or headless modes.
- Map GUI operations (e.g., File -> New) to internal function calls (e.g., `bpy.ops.wm.read_homefile()`).
- Define the software's state model (e.g., active objects, open documents, current selection).

### 2. Design
- **Command Architecture**: Use hierarchical command groups (e.g., `project new`, `image resize`).
- **JSON Schema**: All commands MUST support the `--json` flag. Define input parameters and expected output structures for every command.
- **State Management**: Design how to persist software sessions or handle Undo/Redo operations within the CLI.

### 3. Implement
- Build the CLI framework using the **Python Click** library.
- Encapsulate backend logic to ensure atomic command execution.
- Implement a `repl_skin.py` style interactive shell for persistent sessions.

### 4. Plan Tests
- Identify critical functional paths (Happy Paths).
- Design edge-case test scenarios (e.g., invalid parameters, missing dependencies).

### 5. Write Tests
- Generate **pytest** unit tests for individual commands.
- Develop End-to-End (E2E) tests to verify that the CLI correctly drives the authentic software backend.

### 6. Document
- Provide comprehensive `--help` information for every command.
- Ensure documentation includes usage examples and sample JSON outputs optimized for LLM learning.

### 7. Publish
- Create standard distribution files such as `setup.py` or `pyproject.toml`.
- Package the tool using the naming convention: `agent-harness-[software-name]`.

## Technical Standards

### Agent-First JSON Output
- Successful responses MUST include `status: "success"`.
- Error responses MUST include `status: "error"` and a detailed `message`.
- Outputs should prioritize machine-readable data fields over plain text descriptions.

### REPL and Stateful Interaction
- Default to an interactive REPL mode.
- MUST support `undo` and `redo` commands where applicable.
- Provide a `history` command to track execution trajectories.

## Usage Examples
- "Analyze the source code of [Software Path] and list core functionalities for CLI conversion."
- "Design a Click-based command hierarchy for [Software]."
- "Write a test script to verify if `cli-anything-xxx image grayscale` executes correctly."

---
*Note: This skill is strictly aligned with the HKUDS/CLI-Anything project specifications.*
