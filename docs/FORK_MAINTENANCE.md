# Downstream Fork Maintenance

This repository is maintained as a close mirror of `HKUDS/CLI-Anything`.
Downstream-only changes should stay small, temporary, and upstreamable.

## Policy

- Treat `upstream/main` as the source of truth.
- Use local branches only for focused fixes or validation work.
- Do not accumulate long-lived downstream feature patches.
- Prefer upstream pull requests for bug fixes, compatibility fixes, tests, and documentation.
- Keep local-only operational notes outside the upstreamable patch when they are not generally useful.

## Sync Routine

```bash
git fetch upstream --prune
git switch main
git merge --ff-only upstream/main
git switch -c fix/<short-topic>
```

If local work already exists, rebase it onto the fetched upstream head:

```bash
git fetch upstream --prune
git rebase upstream/main
```

When rebase conflicts are broad or unclear, stop and re-check whether the local patch is still needed before resolving by hand.

## Patch Workflow

1. Reproduce the issue on the current upstream baseline.
2. Make the smallest patch that fixes the upstream-visible behavior.
3. Add or update tests when the repository has a nearby test surface.
4. Run the narrowest relevant checks first.
5. Run the broader checks that protect the touched surface.
6. Open an upstream pull request against `HKUDS/CLI-Anything:main`.
7. Keep the downstream branch only until upstream accepts the fix or makes it obsolete.

## Validation Checklist

For Python compatibility fixes:

```bash
python3 -m py_compile <changed-python-files>
python3.10 -m py_compile <changed-python-files>  # when available
python3.11 -m py_compile <changed-python-files>  # when available
```

For command-doc or plugin-command fixes:

```bash
rg '^\s*except\s*:' opencode-commands cli-anything-plugin cli-hub
```

For harness changes:

```bash
python3 -m pytest <software>/agent-harness/cli_anything/<software>/tests/test_core.py -q
```

Run `git diff --check` before publishing a branch.

## Upstream PR Notes

The pull request should state:

- the upstream-visible bug or compatibility issue,
- the Python versions or harnesses tested,
- the exact validation commands used,
- whether the change affects only docs, generated command files, a harness, or shared runtime code.

Avoid mixing unrelated harness changes in the same pull request.
