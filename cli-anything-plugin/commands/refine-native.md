# cli-anything:refine-native Command

Refine a CLI that the software already ships (any language), not a cli-anything harness. This is the same gap analysis as `refine`, but it follows the native CLI's own conventions.

## Usage

```bash
/cli-anything:refine-native <software-path> [focus]
```

- `<software-path>`: **Required.** Local path to the source tree that contains the CLI.
- `[focus]`: Optional. Limits the analysis to one functionality area, as in `refine`.

## When to use

Use it when `refine` has nothing to work on: the path has no `HARNESS.md` and no `agent-harness/`, but the software already has its own command-line tool, such as a Go, Rust, TypeScript or Node CLI, or a Python CLI that cli-anything did not build. Wrapping that tool in a new Python harness would duplicate it, and the two would drift apart.

### Step 0: Route

- If the path has `HARNESS.md` or `agent-harness/`, use `/cli-anything:refine` instead.
- If the software has no CLI at all, use `/cli-anything` to build one.
- Otherwise, continue here. A relative path that doesn't exist (`./myapp` while you are already in `myapp/`) most likely means the current repo; say that you're assuming so.

### Step 1: Inventory the CLI

Read the source, not only `--help`. Find the command table or arg parser (a `switch` on argv, Click/argparse, cobra, clap, commander) and the help text, and list every command, subcommand and flag. Check also:

- **Output modes:** is there `--json`, a `--format`, or quiet output? Which commands support it? Search for the parser's flag declaration (`json:`, `"json"`, `Bool("json"`), not only the literal `--json`, which parsers rarely spell out. Before calling a flag missing, run it once.
- **Exit codes:** do errors exit non-zero, and are usage errors told apart from failures?
- **Non-interactive use:** does any command prompt, open a browser or wait on a TTY without a flag to skip that?
- **Tests:** which test file covers the CLI, and how do the tests isolate state (temp dirs, env vars, fixtures, fake binaries)?

### Step 2: Inventory the capabilities

List what the software can do through its other surfaces, because those are the gaps a CLI user can't reach:

- HTTP or RPC routes (grep the router: `.get(` `.post(` `@app.route` `HandleFunc`);
- dashboard or GUI actions, and the handlers they call;
- public library exports, and config keys that are only settable by editing a file;
- background jobs or watchers with no manual trigger.

For each one, note the **core function** it calls. That function is what the new command will call too.

### Step 3: Gap report, then confirm

Group the gaps:

1. **Agent-native basics:** machine-readable output on read commands, meaningful exit codes, no prompts. These come first, because every agent workflow depends on them.
2. **Write actions:** things users can change in the UI but not from the CLI (comment, approve, accept, assign).
3. **Triggers:** manual runs for background work (rebuild, update, sync).
4. **Read-only views** that the UI has and the CLI lacks.

Present the report with AskUserQuestion (multiSelect, one option per group, your recommendation first) and implement only what is picked. With a `[focus]` argument, cover only that area.

### Step 4: Implement in the CLI's own idiom

- Match the existing command style exactly: the same parser, error type, help-entry format, line width and output tone.
- **Reuse the core function the other surface calls.** If it lives inside the web or server layer, move it to the shared core package rather than copy it. Two copies of the logic is the main way a refine goes wrong.
- `--json` prints one JSON value on stdout and nothing else (logs go to stderr). Build it from the same data the text formatter uses; never re-parse the text.
- Update the help text and any "did you mean" command list.

### Step 5: Test in the project's own framework

- Write a failing test first in the existing CLI test file, then make it pass.
- Use the project's existing fakes for anything costly (model calls, network, cloud). Never make a real paid call in a test.
- Run the CLI test file and the typecheck or lint. Run the whole suite once at the end, not after every command.
- For each new command, break its core call once and confirm a test fails.

### Step 6: Document and report

Update the README or command reference if the project keeps one. Report each new command with a one-line example and the test results, and list any gap you skipped, with the reason.

## Notes

- Like `refine`, this never removes existing commands.
- Present the gap report before implementing, so the user can steer.
