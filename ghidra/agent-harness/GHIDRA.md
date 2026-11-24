# Ghidra - CLI Harness SOP

## Overview

Ghidra is the NSA's open-source reverse-engineering suite (disassembler, decompiler, analyzers). It ships a headless launcher, `support/analyzeHeadless`, that imports binaries into a project, runs analysis and executes scripts.

**Real software:** Ghidra 12.x `analyzeHeadless` (Java, needs a JDK 25+).
**CLI role:** stage the binary - import/analyze once - answer read-only queries via a Java post-script - return JSON.

## Architecture

- **Launcher:** `$GHIDRA_INSTALL_DIR/support/analyzeHeadless[.bat]`, or `analyzeHeadless` on PATH.
- **Java:** Ghidra 12 needs JDK 25+. If your default `JAVA_HOME` is older, set `GHIDRA_JAVA_HOME`; it is applied to the child process only.
- **Work folder:** `~/cli-anything-ghidra/` (override with `CLI_ANYTHING_GHIDRA_HOME`; a profile path Ghidra cannot take falls back to an ASCII-safe per-user folder, see "Work folder and user names"). Ghidra rejects any path element starting with `.`, so a dot folder is not used. `projects/` holds the analyzed programs, `inputs/` holds the temporary staged copy (deleted after analysis).
- **Identity:** a program is identified by the first 16 hex chars of its SHA-256. The same bytes reuse the same analysis, whatever the file is called or where it lives.
- **Queries:** `-process <key>.bin -noanalysis -readOnly`, so a query never re-analyzes (analysis can take minutes) and never modifies the project. Each query still pays ~10 s of JVM and Ghidra start-up.
- **Output channel:** the post-script `scripts/CliAnythingQuery.java` writes JSON to a temp file. Ghidra's stdout is log noise and is never parsed. A Java script is used because it runs in every headless setup without extra pip packages.

## Command groups

| Command | Post-script command |
|---------|---------------------|
| `analyze BINARY [--loader --processor --entry --timeout]` | import + analysis + `info` |
| `info BINARY` | `info` |
| `functions BINARY [--filter --limit]` | `functions` |
| `decompile BINARY TARGET` | `decompile` (name or address) |
| `strings BINARY [--min-length --limit]` | `strings` |
| `imports BINARY` | `imports` |
| `xrefs BINARY TARGET` | `xrefs` (symbol or address) |

Every command supports `--json`. Running with no subcommand starts the REPL. Root options: `--json` and `--query-timeout SEC` (default 300; the decompiler gets that minus 30 s as its own budget).

`analyze` reuses an earlier complete analysis of the same bytes with the same options (loader, processor, entry) and answers from a stored result in well under a second (`"cached": true`); `--force` re-imports and re-analyzes. A timed-out analysis is never reused. `analyze` also returns `analysis_timed_out`. Ghidra ends a timed-out analysis with exit 0 and a partial result, so the harness reads its log and flags it; the partial result stays queryable. A binary counts as analyzed only after a successful `analyze` (a marker file), never just because a project exists, because a failed import also leaves one.

Raw firmware has no header, so tell Ghidra how to read it: `--loader BinaryLoader --processor x86:LE:64:default`, and `--entry <addr>` to create a function where execution starts.

## Safety rules (enforced in code, covered by tests)

- **The target binary is never executed.** It is read, hashed and copied.
- **Windows `.bat` injection (BatBadBut):** `analyzeHeadless.bat` runs through `cmd.exe` even for list-form `subprocess`. Every user string that reaches the command line (function/symbol target, loader, processor, entry address) is checked against a strict allowlist, so `&`, `|`, `%`, `^`, quotes, spaces and a leading `-` are rejected. The input binary is staged as `<hash>.bin`, so its own (possibly attacker-chosen) filename never appears on the command line.
- Paths that reach the command line (work folder, script folder, scratch folder, launcher) are refused on Windows if they contain `& | < > ^ % !` or a quote (on POSIX only newline and NUL are refused), so a folder such as `R&D` cannot split the command line either. Spaces are fine. Parentheses are refused too: the Ghidra launcher script exits with code 255 on them, even in a quoted path.
- No shell is used, stdin is `DEVNULL` (Ghidra's launcher can prompt for a JDK and would hang), and every run has a timeout. On timeout the whole process tree is killed, because killing only the `.bat` would leave `java.exe` running and holding the project lock.
- Each analysis stages its input in a private folder and hashes the staged copy, so parallel runs on the same binary cannot delete each other's input.

## Work folder and user names

The default work folder is `~/cli-anything-ghidra`, so it contains the user name. Ghidra validates every element of its project path, and what it accepts is narrower than what Windows allows in a user name. Probed with Ghidra 12.2 by running the real launcher:

| Accepted | Refused |
|----------|---------|
| letters and digits that the Windows code page can represent (`Jürgen Müller`, `José García`, `Žofia`, `ß`), space, `_ - . ~ @ + [ ]` | `' # $ { } , ; = `` ` ``, symbols such as the euro sign, letters outside the code page (CJK names), and any element starting with `.` |

When the profile path contains a refused character (a user called `O'Neil`, for example), the harness does not fail: it uses `%ProgramData%\cli-anything-ghidra\<8 hex of the profile path>` on Windows or `/var/tmp/cli-anything-ghidra-<8 hex>` elsewhere, one folder per user. A `CLI_ANYTHING_GHIDRA_HOME` that you set yourself is never replaced silently: a refused character there is an error that names the character. Nothing in the harness refers to a particular user, drive or home folder; a test scans the package for that.

## Exit codes and what they mean (observed with Ghidra 12.2)

| Exit | Meaning | What the harness reports |
|------|---------|--------------------------|
| 0 | Ghidra ran. It also exits 0 when an import failed (`No load spec found`, `Import failed`) or an analysis timed out (`Analysis timed out`), so the harness reads the log. | the loader hint, or `analysis_timed_out: true` |
| 1 | Ghidra aborted with an `ERROR` line: bad option, missing folder, project not found, a path element starting with `.`, `LockException: Unable to lock project!`; or a Java parse error when a path argument ends in a parenthesis. | the first `ERROR` or `Exception` lines; the lock gets a "busy" message |
| 255 (Windows) | `cmd.exe` could not parse the `.bat` command line: a parenthesis in the middle of a path argument. One localized line, no `ERROR`. Java never starts. | "cmd.exe could not parse the launcher command line ... a parenthesis" plus the line |

The harness itself exits 0 on success, 1 on any error (`{"error": ...}` with `--json`) and 2 on a usage error. Two runs on the same binary are queued by a lock file in `~/cli-anything-ghidra/locks/`, because Ghidra locks the project even for read-only queries (three parallel queries made two of them fail with exit 1 before the queue existed).

## State

There is no session file and no undo: the Ghidra project under `~/cli-anything-ghidra/projects` is the persisted state (one analyzed program per binary content), and every query is read-only.

## Known limits

- A run waits up to its own timeout for another run on the same binary; after that it answers "stayed busy". A second tool that opens the same project (the Ghidra GUI, for example) is not covered by the queue.

- Analysis is only as good as Ghidra's analyzers; decompiler output is not guaranteed to compile.
- Queries are read-only: no renaming, retyping or patching.
- `strings` and `imports` depend on the loader; raw binaries have none.
- The copy of the binary doubles the disk use of large inputs while analysis runs.
- `functions`, `strings` and `imports` return at most 100,000 entries each. `strings --min-length` counts characters, not bytes.
