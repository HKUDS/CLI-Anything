# CLI Matrix Registry Schema (v2 — capability-based)

Status: **draft**. Applies to `matrix_registry.json` entries and the companion `cli-hub-matrix/<name>/SKILL.md` files.

The v1 layout organized each matrix by **pipeline stages** (Ideate → Acquire → Edit → ...). This silently imposed a linear ordering that most real workflows do not follow (a screencast tutorial, a generative short, and a podcast-to-video all touch different subsets of the same tools in different orders).

The v2 layout organizes each matrix around **capabilities** — verbs the agent can compose on demand. A workflow becomes a recipe over capabilities, not a march through stages.

---

## Top-level shape

```jsonc
{
  "meta": { "repo": "...", "description": "...", "updated": "YYYY-MM-DD" },
  "matrices": [
    {
      "name": "video-creation",
      "display_name": "Video Creation & Editing",
      "version": "3",
      "schema_version": "2",
      "matrix_id": "V1",
      "category": "video",
      "description": "...",
      "homepage": "...",
      "skill_md": "cli-hub-matrix/video-creation/SKILL.md",

      "capabilities": [ /* see below */ ],
      "recipes":      [ /* see below */ ],
      "known_gaps":   [ /* see below */ ],

      "clis": [ "...flat list preserved for cli-hub install..." ]
    }
  ]
}
```

`clis[]` is kept as a flat install list so `cli-hub matrix install <name>` continues to work unchanged. Everything else is new in v2.

---

## Capability

A capability is a single verb the agent can invoke — not a stage, not a tool. Capabilities are intentionally coarse; a capability has 1..N providers and an agent picks among them using the decision rubric in SKILL.md.

```jsonc
{
  "id": "visual.generate",
  "intent": "Produce a video clip from a text prompt or reference image.",
  "inputs":  ["prompt:text", "ref_image?:path", "duration?:seconds"],
  "outputs": ["video_clip:path"],
  "providers": [ /* see below */ ],
  "skill_search_hints": ["text-to-video", "video generation"]
}
```

Naming: `<domain>.<verb>`. Domains in v2: `visual`, `audio`, `text`, `composite`, `package`, `publish`. Verbs are lowercase, imperative-ish nouns (`generate`, `capture`, `edit`, `synthesize`, `transcribe`, `translate`, `assemble`, `overlay`, `thumbnail`, `encode`, `upload`).

### Cross-matrix capabilities

Capabilities are shared across matrices by ID. `visual.generate` means the same thing in V1 (video) and V2 (image) only if the `outputs` differ — if they would collide, disambiguate (`visual.generate.video` vs `visual.generate.image`). Long-term, common capabilities move to a shared `capabilities.json`; for now each matrix redeclares them.

---

## Provider

A provider is one concrete way to satisfy a capability. Exactly one provider kind per entry.

```jsonc
{
  "kind": "api",                          // harness-cli | public-cli | python | native | api
  "name": "Runway Gen-4",
  "invocation_hint": "POST https://api.runway.ml/v1/...",
  "requires": {
    "env":     ["RUNWAY_API_KEY"],
    "binary":  [],
    "package": []
  },
  "cost_tier":    "paid",     // free | metered | paid | premium
  "quality_tier": "high",     // basic | good | high | sota
  "offline": false,
  "notes": "Best for cinematic motion; ~$0.05/sec as of 2026-04."
}
```

| Kind | Meaning | Typical `requires` |
|---|---|---|
| `harness-cli`  | A CLI-Anything harness (first-party) | `binary: ["cli-anything-<x>"]` |
| `public-cli`   | Third-party CLI from `cli-hub`       | `binary: ["<entry>"]` |
| `python`       | An importable Python package         | `package: ["..."]` |
| `native`       | A system binary / shell pipeline     | `binary: ["ffmpeg", ...]` |
| `api`          | A hosted API the agent calls directly | `env: ["..._API_KEY"]` |

`requires` is a **preflight contract**: the agent can deterministically check it before choosing the provider. If any `env`/`binary`/`package` is missing, that provider is unavailable *unless* the agent explicitly escalates (see below).

---

## Decision rubric (canonical — SKILL.md references this)

When an agent needs to pick a provider for a capability, walk this ladder:

1. **Available & adequate.** Prefer providers whose `requires` is already satisfied in the environment, ranked by `quality_tier` then inverse `cost_tier`.
2. **Free-to-install.** If none available, prefer `python` / `native` providers that can be installed in seconds (`pip install`, `apt`, single binary) without credentials.
3. **Harness install.** If the task warrants it, install a `harness-cli` or `public-cli`.
4. **Paid API escalation.** Only when (a) lower tiers can't meet the quality bar, (b) env already holds the key, or (c) the agent explicitly asks the user and the user consents. Never silently call a paid API without one of these conditions.

Providers marked `offline: true` are preferred when the user indicates an offline context.

---

## Suggest-to-user templates

When escalating to an API whose `requires.env` is missing, the agent uses a canned suggestion so the UX is consistent:

```text
To enable <capability> via <provider.name>, set <env var>.
  Cost: <cost_tier notes>
  Quality: <quality_tier>
Reply 'skip' to fall back to <next provider.name>.
```

SKILL.md files may override the template per matrix but must keep the four slots (capability, provider, env, fallback).

---

## Recipe

A recipe is a named composition of capabilities — not a pipeline. It tells the agent *which capabilities this workflow needs*, not the order.

```jsonc
{
  "id": "screencast-tutorial",
  "description": "Record a screen walkthrough with narration and subtitles.",
  "capabilities_used": [
    "visual.capture", "audio.capture", "text.transcribe",
    "composite.overlay", "package.thumbnail", "package.encode"
  ],
  "notes": "Order is flexible; capture first, transcribe from captured audio, overlay subs last."
}
```

Agents pick a recipe to narrow the capability set, then apply the decision rubric per capability.

---

## Known gaps

```jsonc
"known_gaps": [
  {
    "capability": "publish.upload",
    "reason": "No first-party or public CLI for YouTube/TikTok/Bilibili yet.",
    "workaround": "Instruct user to upload manually, or escalate to a custom API script."
  }
]
```

Surfacing gaps in-schema lets the agent tell the user where the ecosystem genuinely ends instead of flailing.

---

## Preflight block (SKILL.md convention)

Each SKILL.md declares a single preflight block the agent runs once per session:

```bash
# Per-capability detection: CLI installed? package importable? binary on PATH? env var set?
cli-hub list --json
python -c "import importlib, sys; [print(m, importlib.util.find_spec(m) is not None) for m in ('moviepy','whisper','pydub','PIL')]"
for b in ffmpeg sox convert magick; do command -v "$b" >/dev/null && echo "$b: yes" || echo "$b: no"; done
for e in RUNWAY_API_KEY ELEVENLABS_API_KEY MINIMAX_API_KEY OPENAI_API_KEY; do [ -n "${!e}" ] && echo "$e: set" || echo "$e: unset"; done
```

The agent caches the result and consults it when the decision rubric runs.

---

## Migration notes

- v1 `stages[]` → v2 `capabilities[]`. Stage name becomes capability `id`; `goal` becomes `intent`; `clis` + `alternatives` flatten into `providers[]` with an explicit `kind`.
- v1 implied order → v2 `recipes[]`. If a matrix really does have a canonical order, express it as a recipe named `default`.
- `cli-hub` should keep reading v1 entries (by absence of `schema_version`) until all matrices are migrated.
