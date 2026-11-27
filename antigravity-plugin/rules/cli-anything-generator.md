---
trigger: glob
globs: "**/agent-harness/**, **/.cli-anything-progress.json, **/cli_anything/**"
description: CLI-Anything generator invariants, PEP 420 namespace rule, and phase gates when editing harness directories.
---

# CLI-Anything Harness Guardrails

These rules activate automatically only when working inside `agent-harness/`,
`cli_anything/`, or `.cli-anything-progress.json`:

1. **PEP 420 namespace rule (hard requirement):** `cli_anything/` MUST NEVER
   contain an `__init__.py` file. Only sub-packages (`cli_anything/<software>/`)
   have `__init__.py`.
2. **Real software backend:** Never reimplement rendering/export in Python or
   silently degrade when the target software is missing.
3. **Absolute methodology resolution:** Read `HARNESS.md`, commands, and guides
   from the installed `cli-anything` plugin's `references/` directory (never
   assume `./HARNESS.md` exists in the user's workspace).
4. **Phase gates:** When `agent-harness/.cli-anything-progress.json` is present
   and `"terminal": false`, complete and record the active phase before
   advancing to the next phase.
5. **CLI contract:** Preserve Click command groups, `--json` output, default
   REPL (`invoke_without_command=True`) with unmodified canonical `ReplSkin`,
   locked UTF-8 session JSON writes, and auto-save + `--dry-run` on session
   mutations.
6. **Verify mechanically before reporting done:** Run the plugin's
   `scripts/verify_harness.py` and `pytest` with `CLI_ANYTHING_FORCE_INSTALLED=1`.
