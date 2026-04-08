# EXA — Architecture & Design

## Overview

`cli-anything-exa` is a CLI harness for the [Exa API](https://exa.ai), an AI-native search
engine built on neural embeddings rather than keyword matching. This harness makes
core Exa capabilities available to any AI coding agent (Claude Code, Codex, OpenCode, etc.)
via a structured command-line interface.

## Backend

Exa exposes a REST API wrapped by the official `exa-py` Python SDK.
Authentication uses `EXA_API_KEY` from the environment — no server process is required.

## Command Hierarchy

```
cli-anything-exa [--json]
├── search   <query>          Neural/keyword/deep web search
├── contents <url> [url …]   Fetch full-text or highlighted page content
└── server   status           Verify API key and connectivity
```

## Output Strategy

All commands emit human-readable output by default and structured JSON when `--json` is
passed at the root level. JSON output is the recommended mode for agent pipelines.

JSON result shape for search/contents:
```json
{
  "results": [
    {
      "title": "...",
      "url": "...",
      "published_date": "...",
      "author": "...",
      "highlights": ["..."],   // when --content highlights
      "text": "...",           // when --content text
      "summary": "..."         // when --content summary
    }
  ],
  "cost_dollars": {"total": 0.005}
}
```

## Design Decisions

**`highlights` as default content mode** — Exa highlights are 10× more token-efficient
than full text and are sufficient for most agent retrieval tasks. Full text is available
via `--content text` when needed.

**Research commands deferred** — Exa's async deep researcher (`/research/v1`) has a
start→poll→get lifecycle that warrants a separate v2 PR with proper state persistence.

**Category slugs use hyphens** — CLI uses `research-paper`, `personal-site`,
`financial-report` (hyphenated) for shell-friendliness; the backend maps these to the
API's space-separated values.

## File Layout

```
exa/agent-harness/
├── setup.py
├── EXA.md                         (this file)
└── cli_anything/exa/
    ├── __init__.py
    ├── __main__.py
    ├── exa_cli.py                 Entry point, Click command tree, REPL
    ├── README.md                  Setup and usage guide
    ├── core/
    │   └── search.py              web_search(), get_contents()
    ├── utils/
    │   ├── exa_backend.py         SDK client init, contents/category helpers
    │   └── repl_skin.py           Shared REPL terminal UI
    ├── skills/
    │   └── SKILL.md               Agent-discoverable skill definition
    └── tests/
        ├── TEST.md
        ├── test_core.py           Unit tests (no API calls)
        └── test_full_e2e.py       E2E tests (real API, requires EXA_API_KEY)
```
