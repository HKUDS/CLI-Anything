# Agent Harness

This directory is now the stricter CLI-Anything-style harness root for Mubu.

Recommended install flow:

```bash
cd <repo-root>
python3 -m venv .venv
.venv/bin/python -m pip install -e ./agent-harness
```

Root install now also targets the same canonical source tree:

```bash
cd <repo-root>
.venv/bin/python -m pip install -e .
```

What this gives you:

- `agent-harness/` works as the editable install root
- the canonical implementation now lives inside this directory
- the same `cli-anything-mubu` console script is exposed
- the main CLI is Click-based with grouped command domains
- no-argument daily helpers only work when `MUBU_DAILY_FOLDER` is configured
- `skill_generator.py` can regenerate the packaged `skills/SKILL.md`

Canonical implementation now lives under:

- `agent-harness/mubu_probe.py`
- `agent-harness/cli_anything/mubu`

Compatibility shims remain at the project root for local `python -m ...` and `python3 mubu_probe.py` workflows:

- `mubu_probe.py`
- `cli_anything/mubu`

Current supporting references:

- `agent-harness/MUBU.md`
- `README.md`
- `tests/TEST.md`

Current state:

- packaged and installable from the harness root
- canonical package source is now under `agent-harness/cli_anything/mubu/...`
- root-level wrappers preserve backward compatibility during development
- grouped `discover` / `inspect` / `mutate` / `session` commands now exist
- daily-note helpers require an explicit folder reference unless `MUBU_DAILY_FOLDER` is set
- the packaged `SKILL.md` is now generated from the canonical harness
