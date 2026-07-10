# CLI-Anything OpenRefine

Agent-native CLI for OpenRefine data wrangling through the real local HTTP API.

```bash
cli-anything-openrefine --json project import messy.csv --name cleanup
cli-anything-openrefine --json data rows --limit 5
cli-anything-openrefine ops text-transform trim-name.json --column Name --expression 'value.trim()'
cli-anything-openrefine --json data apply trim-name.json
cli-anything-openrefine --json data export clean.csv
```

Run `cli-anything-openrefine` with no arguments for the REPL.

The REPL also accepts newline-separated commands from stdin, so user journeys
can be replayed in CI without an interactive terminal:

```bash
printf 'help\nexit\n' | cli-anything-openrefine
```

Interactive terminals keep the Unicode banner, prompt history, and styling;
redirected input uses ASCII-only output for cross-platform reliability,
including Windows environments configured with legacy encodings.
Unicode command payloads are preserved as ASCII backslash escapes in this
mode, so values remain identifiable without triggering encoding failures.
If any piped command fails, the REPL continues consuming the script but exits
nonzero at `exit` or EOF so CI can reject the failed user journey.

Start OpenRefine first:

```bash
openrefine -i 127.0.0.1 -p 3333
```
