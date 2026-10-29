# GATEKEEPER — Architecture & Design

## Overview
`cli-anything-gatekeeper` makes Gatekeeper AI — a hosted procurement-evaluation engine for the
energy sector — operable by any coding agent (Claude Code, Codex, Cursor, OpenClaw, …) from
the terminal, without the browser.

## Backend (the "real software")
Following HARNESS.md rule #1, the CLI does not reimplement evaluation. It calls the production
service, so results are identical to the web app:

| Endpoint | Used for |
|---|---|
| `GET /api/health` | `health` |
| `GET /api/config` | Supabase URL + anon key (public), billing flag |
| `POST /api/evaluate` `{documents:[{name,content}], weights?}` + `Bearer <token>` | `evaluate` |
| Supabase `POST /auth/v1/otp`, `/auth/v1/verify`, `/auth/v1/token`, `GET /auth/v1/user` | `auth …` |
| Supabase `GET /rest/v1/evaluations` (RLS-scoped) | `reports …` |

HTTP status mapping: `401 → exit 2`, `402 → exit 3`, other failures `→ exit 1`.

## Extraction parity
The web app extracts text in the browser and posts only text. `core/extract.py` ports those
rules (types, 10-file / 10 MB limits, DOCX paragraphs/tabs, XLSX `[Sheet N]` TSV, scanned-PDF
warning), with one fix: XLSX cells are placed by their A1 reference (`r="C2"`), so blank cells —
omitted, or self-closing when formatted — keep their column instead of shifting values left.

## Command hierarchy
```
cli-anything-gatekeeper [--json] [--url URL]
├── health
├── auth      login <email> | complete --link/--code | token <jwt> | status [--verify] | logout
├── extract   <files|dir> [--text]
├── evaluate  <files|dir> [-w weights] [-o out.json] [--dry-run] [--timeout s]
├── reports   list [--limit --offset] | get <id> [-o]
├── report    summary | compliance [--status --mandatory --vendor] | pricing | risks | markdown [-o]
└── repl      (default)
```

## State
`~/.cli-anything-gatekeeper/session.json` (override with `GATEKEEPER_HOME`), mode 0600. Writes go
to a temp file that is `os.replace`d into place, so readers never see a partial file; writers and
token refreshes serialize on `session.lock`, and a refresh re-checks the session under the lock so
Supabase's rotating refresh token is spent once. Access tokens refresh automatically within 120 s
of expiry. Only an auth rejection of the refresh (400/401/403) means "sign in again" (exit 2);
429/5xx keep their status (exit 1, retry). `GATEKEEPER_TOKEN` overrides the file.

## File layout
```
gatekeeper/agent-harness/
├── setup.py
├── GATEKEEPER.md
└── cli_anything/gatekeeper/
    ├── gatekeeper_cli.py      Click tree + REPL
    ├── core/extract.py        document → text (web-app parity)
    ├── core/evaluate.py       weights, payload, run + save
    ├── core/report.py         saved reports + offline views + Markdown
    ├── core/session.py        sign-in state, refresh
    ├── utils/gk_backend.py    HTTP client (stdlib only)
    ├── utils/repl_skin.py     shared CLI-Anything REPL skin
    ├── skills/SKILL.md
    └── tests/                 TEST.md, test_core.py, test_full_e2e.py, fixtures.py
```
