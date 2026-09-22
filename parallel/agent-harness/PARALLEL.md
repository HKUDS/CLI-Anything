# Parallel harness architecture

This is a stateless search and extraction harness for the hosted free Search MCP endpoint, following the plugin's MCP backend pattern. It uses the maintained Python MCP SDK with Streamable HTTP; it does not reimplement JSON-RPC or use the paid Search API.

`parallel_cli.py` owns Click options, input validation, JSON rendering, and the REPL's task ID. `utils/parallel_backend.py` owns initialization, discovery pagination, tool calls, HTTP bounds, project attribution, and result validation. Each command opens and closes its transport. Related commands can share a task ID independently of the transport session.

The SDK owns protocol negotiation, correlation, SSE handling, and MCP transport cleanup. The HTTP response hook rejects status errors and redirects, and bounds streaming response bytes. A command deadline includes connection setup, the call, and cleanup. The backend chooses structured content when available, falling back to one JSON text block, and distinguishes malformed/error responses from valid empty results. Fetch warnings and per-URL failures remain in the returned object.

The registry installs this independent package and advertises its root skill. The same skill ships inside the wheel for installed agents. No configuration or credential writes are needed. Tests cover the CLI/backend boundary and actual SDK HTTP traffic; live tests are explicitly enabled because they contact Parallel.
