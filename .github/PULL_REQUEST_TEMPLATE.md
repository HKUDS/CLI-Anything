## Description

<!-- Briefly describe the changes in this PR. -->

Fixes #<!-- issue number -->

## Type of Change

<!-- Check the one that applies: -->

- [ ] **New Software CLI** — adds a CLI harness for a new application
- [ ] **New Feature** — adds new functionality to an existing harness or the plugin
- [ ] **Bug Fix** — fixes incorrect behavior
- [ ] **Documentation** — updates docs only
- [ ] **Other** — please describe:

---

### For New Software CLIs

<!-- If this PR adds a new software CLI, ALL items below must be checked. -->

- [ ] `<SOFTWARE>.md` SOP document exists at `<software>/agent-harness/<SOFTWARE>.md`
- [ ] `SKILL.md` exists inside the Python package (`cli_anything/<software>/SKILL.md`)
- [ ] Unit tests at `cli_anything/<software>/tests/test_core.py` are present and pass without backend
- [ ] E2E tests at `cli_anything/<software>/tests/test_full_e2e.py` are present
- [ ] `README.md` includes the new software (with link to harness directory)
- [ ] `registry.json` includes an entry for the new software (for the [CLI-Hub](https://hkuds.github.io/CLI-Anything/hub/))
- [ ] `repl_skin.py` in `utils/` is an unmodified copy from the plugin

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
