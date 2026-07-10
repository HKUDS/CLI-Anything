# FIX_NOTES.md - PR #223 Calibre Harness Validation

## Blocker Status

- No code blocker was identified in the Calibre harness.
- Remaining validation/documentation blocker addressed by adding no-Calibre subprocess smoke coverage and explicit real-backend validation steps.

## No-Calibre Smoke Validation

These commands validate importability, Click entrypoint behavior, and missing-library
error handling without requiring `calibredb`, `ebook-convert`, or `ebook-meta`.

```bash
cd calibre/agent-harness
python -m py_compile \
  cli_anything/calibre/calibre_cli.py \
  cli_anything/calibre/core/*.py \
  cli_anything/calibre/utils/*.py
python -m pytest cli_anything/calibre/tests/test_core.py -v
```

To require the installed console script for smoke validation:

```bash
cd calibre/agent-harness
pip install -e .
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest \
  cli_anything/calibre/tests/test_core.py::TestCLISubprocessSmoke -v
```

## Real Calibre Backend Validation

Install Calibre first and confirm all wrapped commands resolve:

```bash
which calibredb
which ebook-convert
which ebook-meta
```

Then run the E2E suite:

```bash
cd calibre/agent-harness
pip install -e .
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest \
  cli_anything/calibre/tests/test_full_e2e.py -v -s
```

Expected E2E coverage:

- Temporary Calibre libraries are created for test isolation.
- Generated EPUB fixtures are imported through `calibredb`.
- Metadata changes are round-tripped through the real backend.
- EPUB to TXT/MOBI conversion runs through `ebook-convert`.
- Exported and converted artifacts are checked for existence and nonzero size.

## Remaining Gaps

- Catalog generation, file-level metadata embedding, and real custom-column workflows are documented as E2E gaps in `cli_anything/calibre/tests/TEST.md`.
