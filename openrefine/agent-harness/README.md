# OpenRefine Agent Harness

This is the standalone CLI-Anything harness package for OpenRefine.

Install:

```bash
python -m pip install -e .
```

Run:

```bash
cli-anything-openrefine --help
cli-anything-openrefine
```

Replay a scripted REPL user journey in CI or a shell pipeline:

```bash
printf 'help\nexit\n' | cli-anything-openrefine
```

Start OpenRefine first for backend commands:

```bash
openrefine -i 127.0.0.1 -p 3333
```
