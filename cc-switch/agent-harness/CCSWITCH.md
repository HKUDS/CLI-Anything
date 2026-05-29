# CC Switch SOP: CLI Harness Design

## Software Identity
- **Name**: CC Switch v3.15.0
- **Type**: Cross-platform desktop GUI (Tauri 2: Rust + React)
- **Purpose**: All-in-One configuration manager for AI-powered coding CLI tools (Claude Code, Codex, Gemini CLI, OpenCode, OpenClaw, Hermes Agent)
- **Core operations**: Provider switching management, local HTTP proxy, MCP server management, skills management, prompt management, session browsing, usage tracking, cloud sync

## Architecture Analysis

### Backend Engine
- **Rust/Tauri 2** (`src-tauri/src/`) — native system integration, SQLite database, embedded HTTP proxy (axum), config file I/O
- **React/TypeScript** (`src/`) — UI components, forms, charts

### Data Model
- **Primary Store**: SQLite database at `~/.cc-switch/cc-switch.db` (12+ tables)
- **Config Files**: `~/.cc-switch/config.json` (MultiAppConfig), `~/.cc-switch/settings.json`
- **Managed Files**: `~/.claude/settings.json`, `~/.codex/*`, `~/.gemini/*`, `~/.opencode/*`, `~/.openclaw/*`, Hermes config dirs

### Key Database Tables
| Table | Purpose |
|-------|---------|
| providers | AI provider configurations (API keys, endpoints, models) |
| mcp_servers | MCP server definitions with per-app enable flags |
| skills | Installed skills with per-app enable flags |
| skill_repos | Registered skill GitHub repos |
| prompts | Prompt presets with per-app association |
| proxy_config | Per-app proxy settings (claude/codex/gemini) |
| proxy_request_logs | API request logs for usage tracking |
| usage_daily_rollups | Daily aggregated usage stats |
| model_pricing | Model pricing data |
| provider_health | Provider health monitoring |
| session_log_sync | Session log file sync state |
| settings | Key-value settings store |

### Existing CLI/Scripting Capabilities
- **None**. All operations are Tauri IPC commands invoked from React frontend via `invoke()`.
- **Deep Link Protocol** (`ccswitch://`) provides URL-based import for providers/MCP/prompts/skills.

## Command Map

| GUI Feature | CLI Command Group | Data Source |
|-------------|------------------|-------------|
| Provider Management | `providers` | SQLite providers table |
| Proxy Server | `proxy` | SQLite proxy_config, proxy_request_logs tables |
| MCP Management | `mcp` | SQLite mcp_servers table + app config files |
| Skills Management | `skills` | SQLite skills + skill_repos tables + filesystem |
| Prompt Management | `prompts` | SQLite prompts table + prompt files |
| Session Browser | `sessions` | Filesystem (JSON log files) + SQLite session_log_sync |
| Usage Dashboard | `usage` | SQLite proxy_request_logs + usage_daily_rollups |
| Settings | `settings` | SQLite settings table + settings.json |
| Cloud Sync | `sync` | WebDAV config + filesystem |

## Rendering Gap Assessment
- **No rendering gap** — CC Switch manages text-based AI CLI configuration files. There is no visual/graphical rendering. The CLI directly reads/writes SQLite and JSON, which is functionally identical to what the GUI does.

The current harness focuses on status, provider switching, proxy, MCP, skills, usage, settings, and sessions. Preview-style summaries can be added later on top of the existing `usage stats` data.
