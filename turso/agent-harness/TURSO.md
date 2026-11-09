# Turso harness architecture and SOP

Target the native local Rust Turso engine through its pinned `pyturso==0.8.3`
Python SDK (`turso`), not the Cloud `turso` CLI, libSQL, AgentFS or native MCP.
The standalone `tursodb` shell's list output cannot unambiguously transport
arbitrary text/blobs, so the SDK is the simplest typed binding backend.

`core/values.py` validates JSON types, resolves supported parameter slots and
compiles bound CRUD. `core/session.py` resolves explicit file selection and
optionally saves it with nonblocking Unix flock. `utils/turso_backend.py` lazily
loads the native SDK, verifies FK enforcement, drains bounded results, explicitly
commits/rolls back and releases connection references. No native context manager,
executescript, sqlite3 fallback, resident connection or service is used.
`turso_cli.py` shares one Click command tree between one-shot use and ReplSkin.

Raw SQL is trusted input, with the authority of its native process. The parameter
scanner is not SQL confinement. Structured transaction manifests contain only
compiled table CRUD so the adapter owns the BEGIN IMMEDIATE/COMMIT boundary.
Export is bounded row serialization, not a backup mechanism. Standard schema
inspection uses sqlite_schema and PRAGMA table_info. DDL is explicit SQL.

Qualification requires installed-CLI and REPL tests on new owned synthetic files,
including native-binary readback, bound escaping, deferred commit failure,
rollback, missing dependencies/paths, output caps, and prompt lock failure/release.
Feature availability is bounded by those tests, not copied from current web docs.
See the package README for commands and unsupported interfaces.
