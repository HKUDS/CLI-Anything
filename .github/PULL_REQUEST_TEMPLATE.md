## Description

<!-- Briefly describe the changes in this PR. -->

Fixes #<!-- issue number -->

## Type of Change

<!-- Check the one that applies: -->

- [ ] **New Software CLI (in-repo)** — adds a CLI harness inside this monorepo
- [ ] **New Software CLI (standalone repo)** — registry-only PR pointing to an external repo
- [ ] **New Feature** — adds new functionality to an existing harness or the plugin
- [ ] **Bug Fix** — fixes incorrect behavior
- [ ] **Documentation** — updates docs only
- [ ] **Other** — please describe:

---

### For New Software CLIs (in-repo)

<!-- If this PR adds a new software CLI inside the monorepo, ALL items below must be checked. -->

- [ ] `<SOFTWARE>.md` SOP document exists at `<software>/agent-harness/<SOFTWARE>.md`
- [ ] Canonical `SKILL.md` exists at `skills/cli-anything-<software>/SKILL.md`
- [ ] Packaged compatibility `SKILL.md` exists at `cli_anything/<software>/skills/SKILL.md`
- [ ] Unit tests at `cli_anything/<software>/tests/test_core.py` are present and pass without backend
- [ ] E2E tests at `cli_anything/<software>/tests/test_full_e2e.py` are present
- [ ] `README.md` includes the new software (with link to harness directory)
- [ ] `registry.json` includes an entry with `source_url: null` (see [Contributing guide](CONTRIBUTING.md#registry-fields))
- [ ] `repl_skin.py` in `utils/` is an unmodified copy from the plugin

### For New Software CLIs (standalone repo)

<!-- If this PR only adds a registry.json entry pointing to an external repo, ALL items below must be checked. -->

- [ ] CLI is installable via `pip install <package-name>` or a `pip install git+https://...` URL
- [ ] `SKILL.md` exists in the external repo
- [ ] External repo has its own test suite
- [ ] `registry.json` entry includes `source_url` pointing to the external repo
- [ ] `registry.json` entry includes `skill_md` with full URL to the external SKILL.md
- [ ] `install_cmd` in `registry.json` works (tested locally)

### For Existing CLI Modifications

<!-- If this PR modifies an existing harness, ALL items below must be checked. -->

- [ ] All unit tests pass: `python3 -m pytest cli_anything/<software>/tests/test_core.py -v`
- [ ] All E2E tests pass: `python3 -m pytest cli_anything/<software>/tests/test_full_e2e.py -v`
- [ ] No test regressions — no previously passing tests were removed or weakened
- [ ] `registry.json` entry is updated if version, description, or requirements changed

### General Checklist

- [ ] Code follows existing patterns and conventions
- [ ] `--json` flag is supported on any new commands
- [ ] Commit messages follow the conventional format (`feat:`, `fix:`, `docs:`, `test:`)
- [ ] I have tested my changes locally

## Test Results

<!-- Paste the output of `pytest -v` for the affected harness(es). -->

```
<paste test output here>
```
