# Test Plan - cli-anything-ghidra

## Test Inventory Plan

- `test_core.py`: 104 unit tests (no Ghidra, no Java, `subprocess.Popen` mocked, plus one test with real processes)
- `test_full_e2e.py`: 4 subprocess tests that need no Ghidra, plus 7 live tests against the real Ghidra (5 on six raw bytes, 2 on a real system binary), skipped unless `GHIDRA_INSTALL_DIR` is set

## Unit Test Plan (test_core.py)

- **Locating Ghidra**: `GHIDRA_INSTALL_DIR`, PATH fallback, clear setup error mentioning JDK 25, work folder rejects dot-prefixed path elements (a Ghidra limitation)
- **Allowlists (BatBadBut)**: targets, loader, processor and entry reject `&`, `|`, `%`, `^`, quotes, `<`, `>`, `;`, parentheses, `!`, backtick, space, newline and a leading `-`; symbols, hex addresses, mangled names and language IDs are accepted
- **Staging**: the key is hashed from the private staged copy; a binary named `evil&calc.bin` never appears on the command line; the staging folder is deleted; two staged copies never share a folder; the target is never executed; `shell` is never set; stdin is DEVNULL; the timeout is passed; the launcher gets its own process group
- **Timeouts and failures**: a timeout kills the process tree (a test with real processes proves a grandchild dies); an unreadable result file is a clean error; work, script and scratch folders containing `& | < > ^ % !` or a quote are refused before launch, spaces are accepted, parentheses are refused (the Ghidra launcher script exits 255 on them even in a quoted path; found with the real launcher)
- **Queries**: refuse before analysis, use `-noanalysis -readOnly`, reject bad targets before running, surface the JDK hint / script errors / timeouts, apply `GHIDRA_JAVA_HOME` to the child environment only
- **Core + CLI**: function filter/limit, string min-length/limit, `--json`, `decompile` prints C, option passing, bounds
- **Error contract** (`main()`): a usage error (missing `BINARY`, unknown option) is `{"error": ...}` with exit 2 in `--json` mode and Click text on stderr otherwise; `--help` exits 0; backend errors are JSON with exit 1; an unexpected exception is a message, never a traceback; `--query-timeout` reaches the backend and is bounded
- **REPL line splitting**: a Windows path with backslashes (unquoted or quoted with spaces) reaches the command unchanged; quotes group words and are removed

## E2E Test Plan (test_full_e2e.py)

- Subprocess, no Ghidra: `--help`, missing Ghidra -> JSON error, metacharacters rejected before Ghidra starts
- Live: six raw bytes `b8 2a 00 00 00 c3` (`mov eax, 0x2a; ret`) are written at test time and analyzed with `BinaryLoader` / `x86:LE:64:default` / `--entry 0`. Asserts: format "Raw Binary", one function of 6 bytes, decompile output contains `return 0x2a;`, decompile by address works, an unknown target errors, strings/imports/xrefs are well-formed, and a query before `analyze` fails clearly

- Real file: `find.exe` (Windows) or `true` (elsewhere) is analyzed for real; format is PE or ELF, more than 5 functions, the function list matches `info`, the first function decompiles, imports are returned (non-empty on PE) and `--limit` is honored
- Packaging: a built wheel contains `scripts/CliAnythingQuery.java` and `skills/SKILL.md` (checked by hand with `pip wheel`)

## Realistic workflow verified by hand

A real PE, `C:\Windows\System32\find.exe` (read only, never executed): `analyze` reports format "Portable Executable (PE)" and 44 functions, `imports` returns 25 entries (for example MSVCRT.DLL `_commode`), `strings --min-length 8` returns 107 entries, and `functions` agrees with `info`. After the timeout fix: a query killed after 3 s returns in 3.2 s, leaves no `java` process, lock file or staging folder behind, and the next query works.

## Test Results

With Ghidra 12.2 and JDK 25 (live tests run):

```
........................................................................ [ 62%]
...........................................                              [100%]
115 passed in 313.67s (0:05:13)
```

Without Ghidra (live tests skipped):

```
...................................sssss.ss                              [100%]
108 passed, 7 skipped in 6.33s
```
