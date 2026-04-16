# NotebookLM: Project-Specific Analysis & SOP

## Architecture Summary

NotebookLM is a hosted Google research and content-generation product. Unlike the
local GUI applications that CLI-Anything usually targets, this harness wraps an
installed `notebooklm` command-line client that already manages authentication,
source ingestion, chat, artifact generation, and downloads.

This harness therefore behaves as a **service-style CLI wrapper**:

1. Resolve the local `notebooklm` executable.
2. Build explicit commands with notebook context where needed.
3. Sanitize sensitive auth-related error output.
4. Persist lightweight local session state for REPL convenience.

## Backend Strategy

- Prefer the installed `notebooklm` CLI over reimplementing NotebookLM internals.
- Keep credentials outside the repository and outside test fixtures.
- Treat this integration as experimental and unofficial.
- Require explicit confirmation for destructive or high-impact operations.
- Preserve clear attribution to CLI-Anything, notebooklm-py, and Google NotebookLM documentation.

## Contribution Boundary

This harness is designed to be safe for an upstream contribution review:

- it wraps an installed community CLI instead of vendoring third-party NotebookLM code
- it documents copyright and service-boundary concerns instead of implying official support
- it limits automated verification to non-destructive smoke coverage unless a local authenticated session is intentionally used
- it keeps end-to-end authenticated testing manual so secrets and account state stay out of CI and fixtures

## Constraints

- Depends on a valid local Google-authenticated NotebookLM session.
- Depends on behavior provided by the installed `notebooklm` CLI.
- Full authenticated end-to-end tests are manual by design.

## References

- CLI-Anything methodology: https://github.com/HKUDS/CLI-Anything
- notebooklm-py project: https://github.com/teng-lin/notebooklm-py
- Google NotebookLM help: https://support.google.com/notebooklm/answer/16206563
