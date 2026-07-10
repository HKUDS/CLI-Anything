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

Start OpenRefine first:

```bash
openrefine -i 127.0.0.1 -p 3333
```
