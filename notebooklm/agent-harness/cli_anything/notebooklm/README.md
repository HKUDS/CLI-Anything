# CLI-Anything NotebookLM Harness

Experimental NotebookLM harness for CLI-Anything.

This package wraps an installed `notebooklm` CLI and exposes a CLI-Anything-style
interface for authentication checks, notebook selection, source management, chat,
artifact generation, downloads, and sharing.

## Status

- Experimental
- Community-maintained
- Unofficial and not affiliated with Google

## Requirements

- Python 3.10+
- An installed `notebooklm` command
- A valid local NotebookLM login session

## Install

```bash
cd notebooklm/agent-harness
python3 -m pip install -e .
```

If the upstream NotebookLM CLI is not installed yet:

```bash
python3 -m pip install --user 'notebooklm-py[browser]'
python3 -m playwright install chromium
```

## Run

```bash
# Show help
cli-anything-notebooklm --help

# Check auth state (wraps `notebooklm auth check`)
cli-anything-notebooklm auth status

# List notebooks
cli-anything-notebooklm notebook list
```

## Run Tests

```bash
cd notebooklm/agent-harness
python3 -m pytest cli_anything/notebooklm/tests -q
python3 -m cli_anything.notebooklm.notebooklm_cli --help
```

## Command Groups

| Group | Purpose |
| --- | --- |
| `auth` | login helpers and authentication checks |
| `notebook` | list, create, and summarize notebooks |
| `source` | inspect sources and add URL sources |
| `chat` | ask questions and inspect history |
| `artifact` | list artifacts and generate reports |
| `download` | download generated artifacts |
| `share` | inspect sharing status |

## Common Workflows

```bash
cli-anything-notebooklm auth status
cli-anything-notebooklm notebook list
cli-anything-notebooklm source list --notebook nb_123
cli-anything-notebooklm chat ask "Summarize the current notebook"
cli-anything-notebooklm artifact generate-report --notebook nb_123
```

## For AI Agents

- Prefer explicit notebook IDs with `--notebook` instead of relying on ambient state.
- Use `--json` only on commands whose upstream `notebooklm` subcommand supports machine-readable output.
- Treat NotebookLM auth state as sensitive local data and never print cookie or storage files.
- Treat this harness as a thin wrapper around `notebooklm`, not a reimplementation of NotebookLM.

## Acknowledgements

This harness is inspired by the CLI-Anything methodology:
https://github.com/HKUDS/CLI-Anything

It is designed to work with the community-maintained `notebooklm` CLI from `notebooklm-py`:
https://github.com/teng-lin/notebooklm-py

NotebookLM is a Google product:
https://support.google.com/notebooklm/answer/16206563

This project is unofficial and not affiliated with Google.

## Safety Notes

- Do not commit local auth state into the repository.
- Do not upload sensitive content without permission.
- Respect copyright and service terms for imported sources.
- Prefer review-oriented or read-only commands first when working inside a live notebook.
- Treat sharing and artifact generation as user-impacting operations that deserve explicit intent.

## References

- CLI-Anything: https://github.com/HKUDS/CLI-Anything
- CLI-Anything HARNESS.md: https://github.com/HKUDS/CLI-Anything/blob/main/cli-anything-plugin/HARNESS.md
- notebooklm-py: https://github.com/teng-lin/notebooklm-py
- notebooklm-py on PyPI: https://pypi.org/project/notebooklm-py/
- Google NotebookLM help: https://support.google.com/notebooklm/answer/16206563
