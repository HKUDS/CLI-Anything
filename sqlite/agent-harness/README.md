# cli-anything-sqlite

A structured CLI for the real SQLite engine: inspect schemas, run parameterized
queries, apply atomic SQL batches, import/export CSV, and create online backups.

```bash
python3 -m pip install -e .
cli-anything-sqlite --help
```

Requires Python 3.10+ linked to SQLite 3.35+. No database server is needed.

- [Usage and data contracts](cli_anything/sqlite/README.md)
- [Architecture and operating procedure](SQLITE.md)
- [Agent skill](cli_anything/sqlite/skills/SKILL.md)
- [Test plan and results](cli_anything/sqlite/tests/TEST.md)
