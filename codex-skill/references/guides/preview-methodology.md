# Preview Methodology for Harnesses

Use this guide when a harness can expose meaningful intermediate state through
images, video snippets, inspection bundles, or other honest artifacts derived
from the real software.

This guide complements `docs/PREVIEW_PROTOCOL.md`. The protocol defines the
bundle/session/trajectory format. This document defines the harness-side
methodology and the agent-facing command contract.

## Producer vs consumer

Keep preview production and preview consumption as separate roles:

- **Producer:** `cli-anything-<software> preview ...`
  - talks to the real backend
  - computes source fingerprints
  - chooses recipes
  - publishes bundles, sessions, and trajectories
- **Consumer:** `cli-hub previews ...`
  - reads existing preview state
  - provides `inspect`, `html`, `watch`, and `open`
  - never renders or synthesizes preview artifacts

This distinction should be visible in:

- command help
- README examples
- `SKILL.md`
- live-session viewer hints

The short rule is:

- publish with `cli-anything-<software>`
- inspect with `cli-hub`

## Three-layer model: bundle, session, trajectory

Preview-capable harnesses should model history explicitly instead of treating
the latest bundle directory as the permanent object.

### `bundle_dir`: immutable snapshot

A bundle directory is one concrete preview result:

- one static capture
- one diff capture
- one live-session publish step

It should implement `preview-bundle/v1` and contain:

- `manifest.json`
- `summary.json`
- `artifacts/`

Treat bundle directories as immutable once published.

### `session.json`: mutable live head

`session.json` represents the current live view for a project and recipe. It is
the stable entry point for “what is current right now”.

Typical fields include:

- current bundle id and paths
- session root and recipe
- viewer commands
- current step id
- trajectory location

### `trajectory.json`: append-only permanent history

`trajectory.json` is the durable replay object. It should survive beyond the
current head and allow later tooling to reconstruct how the artifact evolved.

At minimum, each trajectory step should capture:

- `step_id`
- `step_index`
- `command`
- `command_started_at`
- `command_finished_at`
- `publish_reason`
- `source_fingerprint`
- `bundle_id`
- `bundle_dir`
- `manifest_path`
- `summary_path`
- optional `stage_label`
- optional `note`

This is the right place to bind agent actions to preview state. Do not expect
`_bundle_dir` alone to serve that role.

## Recommended CLI surface

### Baseline surface

If the software has meaningful previewable state, expose:

- `preview recipes`
- `preview capture`
- `preview latest`

Recommended behavior:

- `preview recipes`
  - list the supported preview recipes and what they produce
- `preview capture`
  - produce a fresh or cache-reused bundle from the current source state
- `preview latest`
  - return the newest existing bundle for the project and recipe without re-rendering

### Optional diff surface

Expose `preview diff` when the software benefits from direct A/B comparison.

Good fits:

- GPU capture tools
- tools with before/after inspection states
- workflows where the delta is more important than the current hero frame

### Optional live surface

Expose these when iterative live inspection is useful:

- `preview live start`
- `preview live push`
- `preview live status`
- `preview live stop`

Recommended semantics:

- `start`
  - initialize the session root and publish the first bundle
- `push`
  - append a new bundle into the existing live session
- `status`
  - report current state only; do not render
- `stop`
  - mark the session inactive but preserve all published history

### Optional poll-first refresh

Use poll-first refresh when the source of truth is file-backed and agents may
save through separate commands between preview calls.

Good fits:

- JSON project files
- XML timelines
- capture files or scene files whose fingerprints are cheap to recompute

Poll support usually looks like:

- `preview live start --mode poll`
- an internal background monitor loop
- source fingerprint checks before rendering

Only add poll mode when it reduces agent friction. Do not add background loops
that publish meaningless duplicate bundles.

## Agent-facing design for `preview live status --json`

This command exists to make the live loop cheap for agents.

It should answer:

- does a live session exist?
- is it active?
- what is the current bundle?
- what was the latest publish reason?
- what is the latest command-to-preview mapping?

Recommended fields:

- `status`
- `active`
- `_session_dir`
- `_session_path`
- `current_bundle_id`
- `current_bundle_dir`
- `current_manifest_path`
- `current_summary_path`
- `_trajectory_path`
- `current_step_id`
- `latest_command`
- `latest_publish_reason`
- `trajectory_summary`

`trajectory_summary` should be compact and cheap to parse. Include:

- `step_count`
- `current_step_id`
- `latest_command`
- `latest_publish_reason`
- `latest_bundle_id`
- `recent_steps`

This lets an agent decide whether the session is progressing without opening the
full trajectory file on every loop.

## README and SKILL guidance

Preview-capable harnesses should explain preview in both `README.md` and
`SKILL.md`.

### README.md should cover

- what preview modes exist
- what each recipe emits
- how to publish a bundle
- how to inspect/watch/open it with `cli-hub previews ...`
- how live sessions behave
- any truthfulness caveats, such as injected cameras or helper rigs

### SKILL.md should cover

- the producer command surface under `preview`
- whether `diff`, `live`, and poll mode are available
- the fact that `cli-hub previews ...` is the read-only consumer
- agent guidance for `--json`
- what artifact roles to expect, such as `hero`, `gallery`, `clip`, or diff outputs

Every preview example should show both sides:

```bash
cli-anything-<software> --project demo.ext preview capture --recipe quick --json
cli-hub previews inspect /path/to/bundle
```

## When to add diff, live, or poll

Use this decision table:

| Capability | Add it when... | Avoid it when... |
|------------|----------------|------------------|
| `preview diff` | the comparison itself is the product | the current-state bundle already answers the question |
| `preview live` | iterative agent work benefits from a stable current head | the tool only produces occasional one-shot exports |
| poll-first refresh | project fingerprints change outside preview commands | the source is expensive to fingerprint or updates are rare |

Do not add complexity just to match another harness. Add the capability only
when it matches the software’s actual iteration loop.

## Truthfulness rules

Previews must be honest enough for agent decisions.

Preferred sources, in order:

1. native render/export from the real backend
2. native inspection or replay outputs from the real tool
3. real-project offscreen capture helpers

Avoid:

- fake renders synthesized outside the tool
- screen recordings of the GUI as the primary preview artifact
- approximations that silently diverge from what the software would really produce

If the harness needs temporary helper state, surface that honestly:

- mark the bundle `partial` or equivalent
- note injected preview cameras, lights, or helpers in summary/context output
- keep the project fingerprint separate from the injected preview rig when possible

## Implementation checklist

- Decide whether preview is meaningful for this software.
- Define one or more recipes with clear outputs.
- Publish `preview-bundle/v1` bundles.
- Keep bundle, session, and trajectory distinct.
- Ensure all preview commands support `--json`.
- Make `preview latest` read-only.
- Make `preview live status --json` cheap for agents.
- Document producer vs consumer commands in README and SKILL.
- Verify outputs come from the real backend.

## Related references

- [`../HARNESS.md`](../HARNESS.md)
- [`skill-generation.md`](skill-generation.md)
- [`../../docs/PREVIEW_PROTOCOL.md`](../../docs/PREVIEW_PROTOCOL.md)
