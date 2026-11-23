# Test Plan - cli-anything-ghidra

## Test Inventory Plan

- `test_core.py`: 80 unit tests (no Ghidra, no Java, `subprocess.Popen` mocked, plus one test with real processes)
- `test_full_e2e.py`: 3 subprocess tests that need no Ghidra, plus 5 live tests against the real Ghidra (skipped unless `GHIDRA_INSTALL_DIR` is set)

## Unit Test Plan (test_core.py)

- **Locating Ghidra**: `GHIDRA_INSTALL_DIR`, PATH fallback, clear setup error mentioning JDK 25, work folder rejects dot-prefixed path elements (a Ghidra limitation)
- **Allowlists (BatBadBut)**: targets, loader, processor and entry reject `&`, `|`, `%`, `^`, quotes, `<`, `>`, `;`, parentheses, `!`, backtick, space, newline and a leading `-`; symbols, hex addresses, mangled names and language IDs are accepted
- **Staging**: the key is hashed from the private staged copy; a binary named `evil&calc.bin` never appears on the command line; the staging folder is deleted; two staged copies never share a folder; the target is never executed; `shell` is never set; stdin is DEVNULL; the timeout is passed; the launcher gets its own process group
- **Timeouts and failures**: a timeout kills the process tree (a test with real processes proves a grandchild dies); an unreadable result file is a clean error; work, script and scratch folders containing `& | < > ^ % !` or a quote are refused before launch, while spaces and parentheses are accepted
- **Queries**: refuse before analysis, use `-noanalysis -readOnly`, reject bad targets before running, surface the JDK hint / script errors / timeouts, apply `GHIDRA_JAVA_HOME` to the child environment only
- **Core + CLI**: function filter/limit, string min-length/limit, `--json`, `decompile` prints C, option passing, bounds

## E2E Test Plan (test_full_e2e.py)

- Subprocess, no Ghidra: `--help`, missing Ghidra -> JSON error, metacharacters rejected before Ghidra starts
- Live: six raw bytes `b8 2a 00 00 00 c3` (`mov eax, 0x2a; ret`) are written at test time and analyzed with `BinaryLoader` / `x86:LE:64:default` / `--entry 0`. Asserts: format "Raw Binary", one function of 6 bytes, decompile output contains `return 0x2a;`, decompile by address works, an unknown target errors, strings/imports/xrefs are well-formed, and a query before `analyze` fails clearly

## Realistic workflow verified by hand

A real PE, `C:\Windows\System32\find.exe` (read only, never executed): `analyze` reports format "Portable Executable (PE)" and 44 functions, `imports` returns 25 entries (for example MSVCRT.DLL `_commode`), `strings --min-length 8` returns 107 entries, and `functions` agrees with `info`. After the timeout fix: a query killed after 3 s returns in 3.2 s, leaves no `java` process, lock file or staging folder behind, and the next query works.

## Test Results

With Ghidra 12.2 and JDK 25 (live tests run):

```
........................................................................ [ 81%]
................                                                         [100%]
88 passed in 65.22s (0:01:05)
```

Without Ghidra (live tests skipped):

```
...........sssss                                                         [100%]
83 passed, 5 skipped in 1.93s
```
