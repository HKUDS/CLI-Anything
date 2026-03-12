---
description: Run tests for a CLI harness and update TEST.md with results
---
# cli-anything-test Command

Run tests for a CLI harness and update TEST.md with results.

**Target software**: $1

## CRITICAL: Read HARNESS.md First

**Before running tests, read `./HARNESS.md` (located alongside this command).** It defines the test standards, expected structure, and what constitutes a passing test suite.

## Arguments

- `$1` is the **software path or repo URL** (required). Either:
  - A **local path** to the software source code (e.g., `/home/user/gimp`, `./blender`)
  - A **GitHub repository URL** (e.g., `https://github.com/GNOME/gimp`, `github.com/blender/blender`)

  If a GitHub URL is provided, clone the repo locally first, then work on the local copy.

  The software name is derived from the directory name. The agent locates the CLI harness at `~/CLI-Anything/<software-name>/agent-harness/`.

## What This Command Does

1. **Locates the CLI** - Finds the CLI harness based on the software path
2. **Runs pytest** - Executes tests with `-v -s --tb=short`
3. **Captures output** - Saves full test results
4. **Verifies subprocess backend** - Confirms `[_resolve_cli] Using installed command:` appears in output
5. **Updates TEST.md** - Appends results to the Test Results section
6. **Reports status** - Shows pass/fail summary

## Test Output Format

The command appends to TEST.md:

```markdown
## Test Results

Last run: 2024-03-05 14:30:00

```
[full pytest -v --tb=no output]
```

**Summary**: 103 passed in 3.05s
```

## Success Criteria

- All tests pass (100% pass rate)
- TEST.md is updated with full results
- No test failures or errors
- `[_resolve_cli]` output confirms installed command path

## Failure Handling

If tests fail:
1. Shows which tests failed
2. Does NOT update TEST.md (keeps previous passing results)
3. Suggests fixes based on error messages
4. Offers to re-run after fixes
