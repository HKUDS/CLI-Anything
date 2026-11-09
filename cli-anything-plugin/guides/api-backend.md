# API Backend Pattern

Use this pattern when a target exposes an official public REST API and has no
usable local source or automation binary. Existing API harnesses such as AnyGen
and AdGuardHome demonstrate this backend category. The application can be
closed-source, hosted SaaS, or a self-hosted service.

## Acquire the contract

An explicit `/cli-anything <docs-or-spec> --api` request selects API mode. If the
user only names a closed-source service, offer API mode and ask for its official
documentation. Do not require a Git repository, clone a documentation URL, or
invent undocumented endpoints. Use a local/remote OpenAPI JSON/YAML specification
when available; otherwise use the vendor's public endpoint reference.

Record the service name, documentation URL, API version, and supported operation
scope in `<SOFTWARE>.md`. Create `<software>/agent-harness/` in the working
directory. Specification analysis and offline development do not need live
credentials. Never place credentials in the SOP, fixtures, source, or skill.

## Map API operations to commands

For each operation, document:

| Contract item | Harness behavior |
| --- | --- |
| Method, path, operation ID | Resource-oriented Click command and backend method |
| Parameters and schemas | Typed options/arguments and request validation |
| Authentication and scopes | Named environment variables, least required scopes |
| Read/write effects | Explicit mutation guard, including paid jobs and nonstandard GET writes |
| Pagination | Documented cursor/offset handling, bounded limits, no guessed page fields |
| Rate limits and retries | Bounded retries only where idempotency is established |
| Async jobs | Bounded polling, terminal failure/cancellation handling, timeout errors |
| Downloads | Separate artifact transport and format/content verification |

Use the service's domains (`jobs`, `documents`, `accounts`, etc.). Do not invent
`project new`, local undo/redo, or rendering functionality when the service does
not support it. A CLI session can persist selected resource IDs and configuration
without claiming to roll back remote mutations. Keep one-shot and REPL commands
on the same backend methods; every command supports machine-readable output.

## Backend wrapper

Implement `utils/<service>_backend.py` with these boundaries:

1. **Configuration:** read the token from a documented environment variable,
   such as `SERVICE_API_TOKEN`; read the base URL from `SERVICE_BASE_URL` or an
   explicit CLI option. Keep defaults, supported URL schemes, API version paths,
   and self-hosted HTTP exceptions documented. Never disable TLS verification
   implicitly. Missing configuration produces an actionable error without
   printing secrets. `--help` must work without credentials or network access.
2. **Request construction:** validate relative endpoint paths, resource IDs,
   query parameters, and payload schemas before sending requests. Do not allow
   user-controlled resource IDs to replace the configured origin. Preserve the
   caller's configured API base path.
3. **Write authorization:** reject a mutating command unless it has explicit
   `--allow-write` for that invocation. Enforce this before the network call,
   including inside a REPL; do not persist permission in session state. HTTP
   method alone is insufficient: consult the operation's documented effects.
   A `--dry-run` displays a redacted plan and issues no mutating request.
4. **Transport:** use connect/read timeouts and bounded retries. Do not blindly
   retry a creation request after an ambiguous timeout; use vendor-supported
   idempotency keys when available. Handle 401/403, 404, 409, 429, 5xx, malformed
   JSON, and application-level error responses as nonzero CLI failures.
5. **Output:** return structured results from the backend. Keep diagnostics out
   of JSON stdout and redact authorization headers, tokens, signed download
   query strings, and sensitive payload fields from errors/logs.

For a mutation command, the guard belongs before the backend operation:

```python
@jobs.command("create")
@click.option("--allow-write", is_flag=True, help="Allow this remote mutation.")
@click.option("--prompt", required=True)
@click.pass_context
def create_job(ctx, allow_write, prompt):
    if not allow_write:
        raise click.ClickException("Creating a job requires --allow-write.")
    # Construct the authenticated client lazily, after parsing help/options.
    result = make_client(ctx).create_job(prompt=prompt)
    output(result, as_json=ctx.obj["json"])
```

Adapt this to the harness's shared JSON error handler; the command and backend
must not print or serialize credential values. Test the guard with a spy that
asserts the backend method was never called.

## Remote rendering and downloads

If the service produces artifacts, preserve the real backend workflow:

`submit job → poll terminal status → download artifact → verify file`

- Job submission is a mutation, even if the result is only a preview.
- Poll with a finite deadline and report failed/cancelled jobs as failures.
- Authenticate downloads only as documented. Do not forward the API token to an
  arbitrary object-storage URL or across an untrusted redirect.
- Stream into a temporary file with a size limit; publish the final path only
  after checking response status, file format, and expected content. An HTML
  error page or JSON error body is not a valid PDF/image.
- Verify PDF magic bytes, OOXML archive structure, or media metadata as appropriate.
  Print final artifact paths in human test output, not credential-bearing URLs.
- For APIs without exports, verify response schemas and requested resource
  fields. Do not add fake files merely to satisfy local-render examples.

## Test layers and truthful results

`test_core.py` stays offline. Test request construction, pagination termination,
write guards, redaction, HTTP/application errors, bounded polling, cancellation,
and artifact rejection with fixtures or a local test server. These tests are
not evidence that the real vendor service was exercised.

`test_full_e2e.py` exercises the real configured service and the installed CLI
through `_resolve_cli()`. Missing credentials or an unavailable service must
fail the explicitly selected E2E suite with a setup hint, not silently skip or
substitute mocks. CI can run only the offline suite when credentials are absent;
report real-service E2E as **not run**, never as passed.

Use a dedicated test tenant/account. Read-only E2E commands run first. Tests
that create resources or paid jobs require an explicit environment opt-in such
as `SERVICE_E2E_ALLOW_WRITE=1`, then pass `--allow-write` to each mutation. Fail
clearly if a selected write test lacks that opt-in. Clean up only resources
created by the test and record cleanup failures. Do not automatically issue
mutations to production just to obtain passing test results.

## Skill metadata

Declare the backend in `agent-harness/harness.json`:

```json
{
  "schema_version": 1,
  "backend": {
    "type": "api",
    "base_url_env": "SERVICE_BASE_URL",
    "auth_env": ["SERVICE_API_TOKEN"],
    "requirements": ["Access to the service's public REST API"]
  }
}
```

Only declare variable names the implementation actually consumes. Public APIs
can omit `auth_env`; a fixed official endpoint can omit `base_url_env`. Use the
literal `console_scripts` mapping in `setup.py` so the generator finds the
actual command module and executable. Run `skill_generator.py`, inspect the
generated commands, and add reviewed workflow examples with real supported
arguments as needed. See [skill generation](skill-generation.md) for schema and
static-analysis limits. Both rendering paths use these backend requirements;
neither requires the SaaS application to be installed locally.
