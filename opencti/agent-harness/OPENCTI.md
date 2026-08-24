# OpenCTI: Project-Specific Analysis & SOP

## Architecture Summary

OpenCTI is an open-source threat intelligence platform built on a GraphQL API
(Node.js) over Elasticsearch, with a React frontend. Intelligence objects
(indicators, observables, reports, cases, threat actors, malware) follow the
STIX 2.1 standard and are stored as entities connected by STIX relationships.

```
+----------------------------------------------------------+
|                    OpenCTI Platform                       |
|  +--------------------+   +---------------------------+  |
|  |   GraphQL API      |   |      React Frontend       |  |
|  |   (single /graphql |   +---------------------------+  |
|  |    endpoint)       |                                  |
|  +---------+----------+                                  |
|            |                                             |
|  +---------v-------------------------------------+       |
|  | Elasticsearch (objects) | RabbitMQ (queueing)  |      |
|  | MinIO (files)           | Redis (pubsub/cache) |      |
|  +-----------------------------------------------+       |
+----------------------------------------------------------+
              |
     Connectors ingest from MISP, CVE feeds, etc.
```

## CLI Strategy: GraphQL over HTTP

Unlike file-format tools, OpenCTI is network-native. The harness is a thin
client over one endpoint:

1. **Single POST** to `{base_url}/graphql` per operation; auth via
   `Authorization: Bearer <token>`.
2. **Relay pagination** (`edges` / `pageInfo {endCursor hasNextPage}`) is
   normalized by a shared `paginated()` helper so every list command returns a
   flat list of nodes.
3. **Retry policy**: 429/5xx/connection errors retried up to 4 times with
   exponential backoff + jitter; server `Retry-After` honored.
4. **Writes with guardrails**: create mutations for observables, indicators,
   reports, cases, entities, and relationships; deletion requires an explicit
   `--force` flag (without it, `delete` is a dry-run). Status messages go to
   stderr so stdout stays machine-parseable.

### GraphQL Conventions Discovered on v7 (7.260824.0)

- Fields are snake_case at the API surface: `created_at`, `updated_at`,
  `observable_value`, `x_opencti_score`, `valid_from`, `valid_until`,
  `pattern_type`.
- Observable queries are named `stixCyberObservables` / `stixCyberObservable`
  (NOT `stixObservables` — that name does not exist on v7 Query).
- Connections must select through edges:
  `externalReferences { edges { node { source_name url } } }`; selecting
  `source_name` directly fails validation.
- Filters use the structured form
  `{"mode":"and","filters":[{"key","values","operator"}],"filterGroups":[]}`;
  pattern prefix search uses `operator: "starts_with"` on key `"pattern"`.
- Case types have dedicated top-level queries: `caseIncidents`, `caseRfis`,
  `caseRfts` (+ singular `caseIncident(id)` etc.) — there is no generic
  `cases` query.
- STIX export is a field selection: `{ toStix }` returns a JSON-encoded STIX
  2.1 bundle for any STIX object or relationship.
- Observable creation uses per-type input objects (`IPv4Addr: {value: ...}`,
  `StixFile: {hashes: {"SHA-256": ...}}`) plus common args
  (`x_opencti_score`, `objectLabel`, `createIndicator`).
- Entity adds: v7 splits threat actors into Group/Individual; this harness
  creates groups via `threatActorGroupAdd`.
- Relationship types are validated server-side against STIX rules (e.g.
  `uses` is rejected between Threat-Actor-Group and Domain-Name; `related-to`
  is broadly allowed).
- Deletion: `stixCoreObjectEdit(id) { delete }` for any object,
  `stixCoreRelationshipEdit(id) { delete }` for relationships;
  `stixDomainObjectsDelete(idList)` exists for bulk domain-object deletion.

## Module Map

```
cli_anything/opencti/
├── opencti_cli.py        # Click groups; --json at group level; REPL
├── core/
│   ├── system.py         # about / me / status (version + identity + liveness)
│   ├── observables.py    # stixCyberObservables list/get/export-stix
│   ├── indicators.py     # indicators list/get/search-pattern
│   ├── reports.py        # reports list/get (+ contained objects)
│   ├── cases.py          # caseIncidents/caseRfis/caseRfts dispatch
│   ├── entities.py       # threat-actor/intrusion-set/malware/campaign/tool
│   └── relationships.py  # stixCoreRelationships
├── utils/
│   ├── opencti_backend.py# transport: retry/backoff/pagination/config resolution
│   └── repl_skin.py      # unmodified plugin copy + output helpers
└── tests/
    ├── test_core.py      # mocked unit tests (23)
    └── test_full_e2e.py  # live tests gated by OPENCTI_E2E=1 (9)
```

## Configuration Resolution

Precedence: CLI args > environment > `~/.cli-anything/opencti/config.json`.

- `OPENCTI_BASE_URL` (alias `OPENCTI_URL`) — e.g. `http://localhost:8090`
- `OPENCTI_API_KEY` (alias `OPENCTI_TOKEN`) — bearer token
- `OPENCTI_TIMEOUT` — seconds (default 30)

## Verification Performed

- Unit suite: 34 tests, all HTTP mocked (transport, retries, pagination guard,
  filter payloads, type dispatch, write mutation payloads).
- E2E suite: 10 tests against OpenCTI 7.260824.0 in OrbStack Docker
  (`http://localhost:8090`), including a full write lifecycle
  (create observable + auto-indicator + entity -> relate -> export STIX ->
  delete everything, asserting no residue).
- Manual smoke: every CLI write command exercised against the live instance
  (observable/entity/report/case add, relationship add, delete guard,
  --force deletes); instance verified clean afterwards.

## Known Limitations

- No update/patch commands yet (`*Edit` field patches are unexposed).
- Relationship listing is unfiltered (no `--from/--to/--type` yet).
- File-hash observables supported via `hashes`; binary upload not exposed.
- No connector management (that lives in separate worker containers).
