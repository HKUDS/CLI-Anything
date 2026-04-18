---
name: cli-hub-matrix-image-design
description: >-
  Capability-based multi-tool matrix for image and graphic design: AI generation,
  raster/vector editing, UI mockups, diagrams, upscaling, photo library, and publishing.
---

# Image & Graphic Design Matrix (S5 — v2 capability-based)

Scenario **S5**. Deepest creation coverage after S2 — raster (GIMP + Krita), vector (Inkscape), AI (ComfyUI + Jimeng + 7 APIs), diagram (drawio + mermaid). **Figma** is the headline gap (also affects S7).

Schema: [`docs/cli-matrix/matrix_registry.schema.md`](../../docs/cli-matrix/matrix_registry.schema.md). Matrix plan: [`docs/cli-matrix/cli-matrix-plan.md`](../../docs/cli-matrix/cli-matrix-plan.md).

## Install

```bash
cli-hub matrix install image-design
cli-hub matrix info    image-design
```

---

## Decision rubric

1. **Available & adequate** — ranked by quality then inverse cost.
2. **Free-to-install** — Python libs / native binaries without credentials.
3. **Harness / public CLI install** — when warranted.
4. **Paid API escalation** — only when lower tiers can't meet the bar, env holds the key, or the user consents. AI image is the most paid-API-diverse capability — ask which provider the user prefers.

Offline context? GIMP, Krita, Inkscape, and local `diffusers` cover almost everything offline.

---

## Preflight

```bash
cli-hub list --json
python - <<'PY'
import importlib.util
for m in ("PIL","cv2","skimage","rembg","svgwrite","cairosvg","svgpathtools","vpype",
          "diffusers","replicate","rawpy"):
    print(m, importlib.util.find_spec(m) is not None)
PY
for b in inkscape gimp krita drawio magick convert exiftool upscayl darktable-cli \
         rawtherapee-cli graphviz dot mermaid plantuml hugo mkdocs; do
  command -v "$b" >/dev/null && echo "$b: yes" || echo "$b: no"
done
for e in OPENAI_API_KEY STABILITY_API_KEY IDEOGRAM_API_KEY RECRAFT_API_KEY \
         GOOGLE_API_KEY MIDJOURNEY_TOKEN FIGMA_TOKEN CANVA_API_KEY PENPOT_TOKEN \
         REPLICATE_API_TOKEN TOPAZ_API_KEY REMOVE_BG_API_KEY FIREFLY_TOKEN; do
  [ -n "${!e}" ] && echo "$e: set" || echo "$e: unset"
done
```

---

## Suggest-to-user template

```
To enable <capability> via <provider>, please set <ENV_VAR>.
  Cost: <cost notes>
  Quality: <quality tier>
Reply 'skip' to fall back to <next provider>.
```

Examples:
- *To enable sota AI image generation via OpenAI GPT-Image-1, please set `OPENAI_API_KEY`. Cost: metered per-image. Quality: sota for photoreal + text rendering. Reply 'skip' to fall back to local `comfyui` (FLUX/SDXL).*
- *To round-trip UI mockups with Figma, please set `FIGMA_TOKEN`. Cost: free tier works for most users. Quality: sota (design system aware). Reply 'skip' to fall back to `sketch` or `drawio` wireframes.*

---

## Capabilities

### `visual.generate` — AI image generation

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-comfyui` | harness-cli | ComfyUI + weights | free | high | yes |
| `jimeng` | public-cli | `dreamina` bin | metered | high | no |
| `diffusers` (SD/SDXL/FLUX) | python | pkg + weights + GPU | free | good-high | yes |
| `replicate` | python | `REPLICATE_API_TOKEN` | metered | high | no |
| OpenAI GPT-Image-1 | api | `OPENAI_API_KEY` | metered | sota | no |
| Ideogram | api | `IDEOGRAM_API_KEY` | metered | sota | no |
| Stability AI | api | `STABILITY_API_KEY` | metered | high | no |
| Recraft | api | `RECRAFT_API_KEY` | paid | sota | no |
| Google Imagen / Nano Banana | api | `GOOGLE_API_KEY` | metered | high | no |
| Midjourney (Discord bridge) | api | `MIDJOURNEY_TOKEN` | paid | sota | no |
| Adobe Firefly | api | `FIREFLY_TOKEN` | paid | high | no |

### `visual.edit.raster` — raster editing

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-gimp` | harness-cli | GIMP installed | free | sota | yes |
| `cli-anything-krita` | harness-cli | Krita installed | free | sota | yes |
| `Pillow` | python | pkg | free | good | yes |
| `opencv-python` | python | pkg | free | high | yes |
| `scikit-image` | python | pkg | free | high | yes |
| `rembg` (background removal) | python | pkg | free | high | yes |
| `remove.bg` | api | `REMOVE_BG_API_KEY` | metered | sota | no |
| Adobe Firefly | api | `FIREFLY_TOKEN` | paid | sota | no |
| Cutout.pro | api | token | metered | high | no |

### `visual.edit.vector` — vector editing

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-inkscape` | harness-cli | Inkscape installed | free | sota | yes |
| `svgwrite` | python | pkg | free | good | yes |
| `cairosvg` | python | pkg | free | good | yes |
| `svgpathtools` | python | pkg | free | high | yes |
| `vpype` (vector post-processing) | python | pkg | free | high | yes |

### `visual.mockup` — UI / mockup / wireframe

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-sketch` | harness-cli | Sketch installed (macOS) | paid app | sota | yes |
| `cli-anything-drawio` | harness-cli | drawio installed | free | high | yes |
| `drawio-desktop` | native | binary | free | high | yes |
| `penpot` | native | binary / self-host | free | high | yes |
| Figma API | api | `FIGMA_TOKEN` | free tier | sota | no |
| Canva API | api | `CANVA_API_KEY` | paid | high | no |
| Penpot API | api | `PENPOT_TOKEN` | free | high | no |

**Known gap** — Figma is the cross-scenario gap (S5 and S7).

### `visual.diagram` — diagrams / flowcharts

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-drawio` | harness-cli | drawio | free | sota | yes |
| `cli-anything-mermaid` | harness-cli | mermaid-cli | free | high | yes |
| `graphviz` (`dot`) | native | binary | free | high | yes |
| `plantuml` | native | binary + java | free | high | yes |

### `visual.upscale` — super-resolution

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `Real-ESRGAN` | python | pkg + weights | free | high | yes |
| `GFPGAN` (faces) | python | pkg + weights | free | high | yes |
| `upscayl` | native | binary | free | high | yes |
| Topaz | api | `TOPAZ_API_KEY` | paid | sota | no |
| Replicate upscalers | python | `REPLICATE_API_TOKEN` | metered | high | no |

### `photo.library` — DAM / photo organization

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `exiftool` + `Pillow` | native+python | binary+pkg | free | high | yes |
| `digikam` | native | binary | free | high | yes |
| `photoprism` | native | binary / self-host | free | high | yes |
| Google Photos API | api | OAuth | free tier | high | no |

### `photo.develop` — RAW processing

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `rawpy` | python | pkg | free | high | yes |
| `darktable-cli` | native | binary | free | sota | yes |
| `rawtherapee-cli` | native | binary | free | sota | yes |
| Adobe Lightroom API | api | Adobe creds | paid | sota | no |

### `publish.cms` — publish images / articles to a CMS

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `contentful` | public-cli | bin + token | metered | high | no |
| `sanity` | public-cli | bin + token | metered | high | no |
| `hugo` / `mkdocs` | native/python | binary/pkg | free | high | yes |
| WordPress REST | api | app password | free | high | no |

---

## Recipes

- **`social-card`** — generate + compose a social sharing image.
  Uses: `visual.generate`, `visual.edit.raster`, `publish.cms`.

- **`logo-set`** — design a logo + size variants.
  Uses: `visual.edit.vector`, `visual.edit.raster` (rasterize), batch export.

- **`ui-wireframe`** — mockup a UI flow.
  Uses: `visual.mockup`, optional `visual.edit.vector` polish.

- **`photo-batch`** — RAW ingest → develop → edit → library → publish.
  Uses: `photo.develop`, `visual.edit.raster`, `photo.library`, `publish.cms`.

- **`icon-pack`** — systematic icon production.
  Uses: `visual.edit.vector`, batch rasterize via `cairosvg`.

- **`thumbnail-set`** — thumbnails for a video/article series.
  Uses: `visual.generate` (hero imagery), `visual.edit.raster` (layout, type), batch variant export.

- **`ai-concept-art`** — generate → upscale → touch up.
  Uses: `visual.generate`, `visual.upscale`, `visual.edit.raster`.

---

## Known gaps

- **Figma** — cross-scenario gap (UI/UX loop for S5 and S7). API escalation works but we lack a native harness.
- **`photo.library` / `photo.develop`** — strong native CLIs, no harness.
- **Midjourney** — Discord bridge only; no clean API.

---

## Agent guidance

- **Match generation provider to intent.** GPT-Image-1 for text-in-image and photoreal; Ideogram for poster/typography; FLUX for artistic; Midjourney for stylized beauty shots; Stability for control+speed.
- **Vector-first for design systems** — logos, icons, illustrations start in `visual.edit.vector`, rasterize last.
- **Preserve color profiles.** `exiftool` + `Pillow` handles ICC; when moving between `rawpy` and `Pillow`, convert to sRGB at the boundary.
- **AI + edit chain.** Agents should plan: generate → background removal (`rembg`) → composite (`visual.edit.raster`) → export. Skipping cleanup is the most common visible defect.
- **Workspace discipline.** Keep generation seeds + prompts in a manifest alongside output PNGs so variations are reproducible.
