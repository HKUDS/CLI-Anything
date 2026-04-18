# CLI Matrix — Scenarios × Capabilities

> A living map of the agent tool ecosystem around each workflow: CLI-Anything harnesses, CLI-Hub public CLIs, cloud APIs, and traditional libraries/native tools, organized by **scenarios** (columns) × **capabilities** (rows), with explicit gap analysis to find where closed-loop agent workflows break.

**Last updated:** 2026-04-18

---

## Matrix framing (v2 — capability-based, eco-first)

- **Columns = Scenarios (`S1`…`S16`)** — closed-loop agent workflows (e.g. "video creation", "knowledge work", "game development").
- **Rows = Capabilities** — verbs the agent can compose on demand (`visual.generate`, `model.mesh`, `knowledge.note`, `publish.upload`, …), **not** a fixed pipeline.
- **Cells = providers** for that capability: first-party harness CLIs, public third-party CLIs, Python libs, native binaries, and direct cloud APIs. Each provider declares a `requires` preflight contract (env/binary/package), a `cost_tier`, a `quality_tier`, and whether it works `offline`.

> Stages silently impose a linear order that real workflows don't follow. A screencast tutorial, a generative short, a talking-head explainer, and a podcast-to-video each touch different subsets of the same tools in different orders. **Capabilities compose; stages march.** Workflows become *recipes* over capabilities.

Schema: [`matrix_registry.schema.md`](matrix_registry.schema.md). Reference implementation: [`cli-hub-matrix/video-creation/SKILL.md`](../cli-hub-matrix/video-creation/SKILL.md) and the v2 entry in `matrix_registry.json`.

### Eco-first direction

A matrix is "complete" when every capability has at least one practical agent path — CLI today, direct API tomorrow, Python package or native command as the fallback. Two quality axes:

1. **Coverage + depth** — every capability has multiple providers ranked by cost/quality/offline so the agent can always pick *something* adequate.
2. **Full picture** — when our CLI fails or is inefficient, the matrix explicitly names the external tool/API/library the agent should reach for, including credential requirements. The agent uses a `suggest-to-user` template to escalate transparently rather than silently skipping or silently burning credits.

Provider layers (each capability should have some of each where possible):

- **First-party** — CLI-Anything harnesses; preferred default where available.
- **Public CLI** — `cli-hub` third-party CLIs; broaden coverage fast.
- **Python / native** — free fallbacks an agent can use immediately (`moviepy`, `ffmpeg`, `Pillow`, `whisper`).
- **Cloud API** — when a hosted model is the fastest route to sota quality; escalated with an explicit suggest-to-user prompt.

### Decision rubric (canonical — SKILL.md files reference this)

Per capability, the agent walks this ladder:

1. **Available & adequate** — providers whose `requires` is already satisfied, ranked by quality then inverse cost.
2. **Free-to-install** — Python libs / native binaries installable in seconds without credentials.
3. **Harness / public CLI install** — install a first-party or public CLI when warranted.
4. **Paid API escalation** — only when lower tiers can't meet the bar, the env already holds the key, **or** the user explicitly consents via the suggest-to-user prompt.

Offline context? Filter to `offline: true` providers only.

### Scenario ordering

Scenarios are ordered by **current completeness first** (migrated to v2 capability-form) then by rough strength of coverage, so readers hit the strongest, most-representative scenarios up front. Stage-form scenarios at the tail are still on the v1 framing and will be migrated opportunistically.

| # | Scenario | Form |
|---|---|---|
| S1 | 🎬 Video Creation & Editing | v2 capability (reference) |
| S2 | 📚 Knowledge / Office / Research | v2 capability |
| S3 | 📐 3D & CAD | v2 capability |
| S4 | 🎮 Game Development | v2 capability |
| S5 | 🖼️ Image & Graphic Design | v2 capability |
| S6 | 🎵 Music & Audio Production | v1 stage |
| S7 | 🌐 Web / App Development | v1 stage |
| S8 | 📡 Creator Operations | v1 stage |
| S9 | 🤖 AI/ML & Data Science | v1 stage |
| S10 | 🛠️ DevOps / SRE | v1 stage |
| S11 | 💬 Team Communication | v1 stage |
| S12 | 🛒 E-Commerce | v1 stage |
| S13 | 🔬 Science / Academic | v1 prose |
| S14 | 🎯 Agentic Game Playing | v1 prose |
| S15 | 🛡️ Security / OSINT | v1 prose |
| S16 | 💰 Finance / Trading / Crypto | v1 prose |

---

## 🎬 S1 · Video Creation & Editing — **v2 reference**

See [`cli-hub-matrix/video-creation/SKILL.md`](../cli-hub-matrix/video-creation/SKILL.md) and the S1 entry in `matrix_registry.json` for the full shape.

| Capability | Harness CLI | Public CLI | Python / native | Paid API (escalate) |
|---|---|---|---|---|
| `visual.generate` | — | `generate-veo-video`, `jimeng` | `diffusers` (SVD/AnimateDiff), `replicate` | Runway Gen-4, Kling, Pika, **Seedance** |
| `visual.capture` | `openscreen`, `obs-studio` | — | `ffmpeg x11grab`, `screencapture`, `mss+cv2` | — |
| `audio.capture` | `audacity` | — | `ffmpeg`, `sox`, `pydub`, `noisereduce` | — |
| `audio.synthesize` | — | `elevenlabs`, `minimax-cli` | `edge-tts`, `TTS` (coqui), `pyttsx3` | OpenAI TTS, Google TTS, Polly, Azure |
| `audio.music` | — | `suno`, `minimax-cli` | `audiocraft` (MusicGen), `stable-audio-tools` | Udio |
| `text.transcribe` | `videocaptioner` | — | `whisper`, `faster-whisper`, `stable-ts` | AssemblyAI, Deepgram, Google STT |
| `text.translate` | — | — | `argos-translate` | OpenAI/Claude, DeepL |
| `composite.assemble` | `kdenlive`, `shotcut` | — | `moviepy`, `ffmpeg-python`, `ffmpeg` | — |
| `composite.overlay` | (via NLE) | — | `ffmpeg -vf subtitles/overlay`, `moviepy` | — |
| `package.thumbnail` | `gimp`, `krita`, `inkscape` | — | `Pillow`, `cairosvg`, `html2image`, `ffmpeg`, ImageMagick | OpenAI GPT-Image-1, Nano Banana, Ideogram, Stability |
| `package.encode` | (via NLE) | — | `ffmpeg` | — |
| `publish.upload` | ❌ | ❌ | — | YouTube, TikTok, Bilibili, Instagram (**known gap**) |

**Recipes**: `ai-short`, `screencast-tutorial`, `talking-head-explainer`, `podcast-to-video`.
**Known gaps**: `publish.upload` (no CLI anywhere); `visual.generate` sota tier is paid-API-only.
**Verdict**: strong across generation/edit/package; distribution gap persists.

---

## 📚 S2 · Knowledge / Office / Research — **v2**

The strongest scenario in the matrix today. First-party harnesses cover search, notes, references, synthesis, office docs, and diagrams; Python fallbacks fill the rest.

| Capability | Harness CLI | Public CLI | Python / native | Paid API (escalate) |
|---|---|---|---|---|
| `research.search` | `exa`, `browser`, `safari`, `clibrowser` | — | `duckduckgo-search`, `googlesearch-python`, `serpapi` | Google Custom Search, Perplexity, Tavily, Brave Search |
| `research.retrieve` | `browser`, `safari`, `clibrowser` | — | `trafilatura`, `readability-lxml`, `httpx`, `playwright` | Firecrawl, ScrapingBee |
| `research.reference` | `zotero` | — | `pyzotero`, `bibtexparser`, `habanero` (Crossref) | Crossref API, Semantic Scholar API |
| `knowledge.note` | `obsidian`, `mubu` | `obsidian-cli` | raw markdown + `git`, `mdformat` | **Notion API, Roam API, Logseq sync** (known gap) |
| `knowledge.outline` | `mubu` | — | OPML via `lxml`, YAML outlines | — |
| `knowledge.synthesize` | `notebooklm`, `intelwatch` | — | LangChain / LlamaIndex + local LLM, `haystack` | Claude, OpenAI, Gemini (long-context summarization) |
| `document.author` | `libreoffice`, `anygen` | — | `python-docx`, `openpyxl`, `python-pptx`, `reportlab` | Google Docs API, Microsoft Graph |
| `document.format` | `libreoffice` | — | `pandoc` (native), `docx2pdf`, `weasyprint` | CloudConvert |
| `document.pdf` | partial (`libreoffice`) | — | `pypdf`, `pdfplumber`, `pdf2image`, native `qpdf`/`pdftk` | Adobe PDF Services, Smallpdf |
| `diagram.create` | `drawio`, `mermaid` | — | `graphviz`, `mermaid-cli`, `plantuml` | — |
| `text.translate` | — | — | `argos-translate` | DeepL, Google Translate, OpenAI/Claude |
| `publish.web` | — | `contentful`, `sanity` | `hugo` (native), `mkdocs`, `jekyll`, `pelican` | WordPress REST, Ghost Admin API, Medium API |
| `publish.latex` | — | — | `latexmk` + `texlive` (native), `pylatex` | Overleaf API |

**Recipes**: `literature-review` (search → retrieve → reference → synthesize → author), `meeting-to-doc` (transcribe via S1 `text.transcribe` → synthesize → author → format), `blog-post` (synthesize → author → publish.web), `paper-draft` (reference → author → publish.latex).

**Known gaps**: **Notion** (highest-leverage missing CLI — recurs in S11); **Google Docs live editing**; a maintained LaTeX harness. Translation has no first-party CLI yet.

**Verdict**: deepest coverage of any scenario. Closing Notion would also close S11's note-taking gap — highest cross-scenario ROI in this group.

---

## 📐 S3 · 3D & CAD — **v2**

Mid-pipe (modeling, point cloud, GPU debug, engine export) is strong. Texturing and fabrication are the two structural gaps — an agent can model but can't realistically texture or 3D-print.

| Capability | Harness CLI | Public CLI | Python / native | Paid API (escalate) |
|---|---|---|---|---|
| `model.mesh` | `blender` | — | `trimesh`, `pymeshlab`, `open3d`, `pygalmesh` | — |
| `model.parametric` | `freecad` | — | `cadquery`, `build123d`, `OpenSCAD` (native), `SolidPython` | Fusion 360 API, Onshape API |
| `model.sculpt` | partial (`blender` sculpt mode) | — | — | **ZBrush, Nomad Sculpt** (known gap) |
| `pointcloud.process` | `cloudcompare`, `cloudanalyzer` | — | `open3d`, `laspy`, `pdal` (native), `pyvista` | — |
| `photogrammetry.reconstruct` | ❌ | — | `Meshroom` (native), `OpenMVG`+`OpenMVS`, `colmap` (native) | RealityCapture, Polycam API, Luma AI |
| `material.texture` | partial (`blender` shader nodes) | — | `Pillow`, `numpy`-based PBR synthesis, `bpy` (scripted) | **Substance 3D, Polycam Materials, Adobe Sampler** (known gap) |
| `render.preview` | `blender` (eevee), `godot` | — | `bpy` background renders | — |
| `render.offline` | `blender` (cycles) | — | `bpy` + `cycles` (native) | Octane Cloud, RenderMan (offline farms) |
| `gpu.debug` | `renderdoc` | — | `apitrace` (native), `vulkan-tools` | — |
| `fabricate.slice` | ❌ | — | `PrusaSlicer` (native CLI), `CuraEngine` (native), `slic3r` | **Bambu Studio, OrcaSlicer** (known gap for API-driven) |
| `fabricate.cam` | partial (`freecad` Path workbench) | — | `pycam`, `kiri:moto` (native) | Fusion 360 CAM, OnShape CAM |
| `export.engine` | `godot`, `blender` (glTF/FBX export) | — | `pygltflib`, `trimesh` glTF writer | Unity Asset Pipeline, Unreal Datasmith |

**Recipes**: `printable-part` (parametric → slice → fabricate), `game-asset` (mesh → texture → export.engine), `reality-scan` (photogrammetry.reconstruct → mesh clean → export), `cnc-part` (parametric → cam → gcode).

**Known gaps**: `material.texture` (no good CLI or open alternative approaches Substance quality); `fabricate.slice` (native slicers exist but need an agent-native wrapper); `model.sculpt`.

**Verdict**: strongest technical scenario by depth — Blender + FreeCAD + CloudCompare + RenderDoc is rare coverage. Closing **texture + slicer** makes the full "idea → CAD → printed part" loop agentic.

---

## 🎮 S4 · Game Development — **v2**

All asset-creation capabilities are covered via the S3 stack; the gap is publishing and alternative engines.

| Capability | Harness CLI | Public CLI | Python / native | Paid API (escalate) |
|---|---|---|---|---|
| `game.engine` | `godot` | — | `pygame`, `arcade`, `panda3d`, `ursina` | **Unity, Unreal** (known gap) |
| `asset.3d` | `blender`, `freecad` | — | `trimesh`, `pygltflib` | — |
| `asset.2d` | `krita`, `inkscape` | — | `Pillow`, `aseprite` (native CLI), `pyxel` | OpenAI GPT-Image-1, Scenario GG, Leonardo AI |
| `asset.audio` | `audacity` | — | `pydub`, `librosa`, `sfxr`/`jsfxr` | ElevenLabs SFX, Mubert |
| `asset.notation` | `musescore` | — | `music21`, `mido`, `abjad` | — |
| `ai.gen-asset` | — | `comfyui`, `jimeng` | `diffusers`, `replicate` | Scenario GG, Leonardo, OpenAI Image, Stability |
| `playtest.agent` | `slay_the_spire_ii` | — | `gym`/`gymnasium` wrappers for headless games | — |
| `build.package` | partial (`godot` export) | — | `pyinstaller` (for pygame), `butler` (itch CLI, native) | — |
| `publish.store` | ❌ | — | `steamcmd` (native), `butler` (itch, native) | **Steamworks Web API, Epic Games Services, Google Play, App Store Connect** (known gap) |
| `telemetry.ingest` | ❌ | `sentry` | `posthog` SDK, raw HTTP analytics | **GameAnalytics, Unity Analytics, PlayFab** (known gap) |

**Recipes**: `godot-jam-game` (engine + asset.2d + asset.audio + build.package), `agent-bot` (playtest.agent on an existing game), `ai-indie-short` (ai.gen-asset → asset.2d → engine → build), `steam-release` (build.package → publish.store → telemetry.ingest).

**Known gaps**: `publish.store` (Steam/itch wrappers exist natively but need agent-native harnesses); `telemetry.ingest`; `game.engine` for Unity/Unreal. `asset.notation` via MuseScore is a surprisingly strong differentiator — very few agent stacks can write sheet music.

**Verdict**: all creation covered, same agent-can-ship gap as S1 and S8 — the missing piece is *distribution*. `playtest.agent` (S14 overlap) is unique among frameworks.

---

## 🖼️ S5 · Image & Graphic Design — **v2**

All creation capabilities are strongly covered; Figma remains the single highest-leverage missing CLI (also affects S7 web/app).

| Capability | Harness CLI | Public CLI | Python / native | Paid API (escalate) |
|---|---|---|---|---|
| `visual.generate` | — | `comfyui`, `jimeng` | `diffusers` (SD/SDXL/FLUX), `replicate` | Midjourney (via Discord bridge), OpenAI GPT-Image-1, Ideogram, Stability, Recraft, Google Imagen, Nano Banana |
| `visual.edit.raster` | `gimp`, `krita` | — | `Pillow`, `opencv-python`, `scikit-image`, `rembg` (bg removal) | Adobe Firefly, Cutout.pro, remove.bg |
| `visual.edit.vector` | `inkscape` | — | `svgwrite`, `cairosvg`, `svgpathtools`, `vpype` | — |
| `visual.mockup` | `sketch`, `drawio` | — | `drawio-desktop` (native), `penpot` (native), `figma-plugin-sdk` (partial) | **Figma API, Canva API, Penpot API** (known gap — Figma is the big one) |
| `visual.diagram` | `drawio`, `mermaid` | — | `graphviz`, `plantuml`, `mermaid-cli` | — |
| `visual.upscale` | — | — | `Real-ESRGAN`, `GFPGAN`, `upscayl` (native) | Topaz, Replicate upscalers |
| `photo.library` | ❌ | — | `Pillow` + `exiftool` (native), `digikam` (native), `photoprism` (native/self-host) | Google Photos API, Apple Photos (limited) |
| `photo.develop` | ❌ | — | `rawpy`, `darktable-cli` (native), `rawtherapee-cli` (native) | Adobe Lightroom API |
| `publish.cms` | — | `contentful`, `sanity` | `hugo`, `mkdocs` | WordPress, Ghost |

**Recipes**: `social-card` (visual.generate → edit.raster → publish), `logo-set` (visual.edit.vector → export variants), `ui-wireframe` (visual.mockup → export), `photo-batch` (photo.develop → edit.raster → photo.library → publish), `icon-pack` (visual.edit.vector → batch export).

**Known gaps**: **Figma** (also blocks S7 UI/UX); `photo.library` and `photo.develop` have strong native CLIs but no harness. AI image escalation is the most paid-API-diverse capability in the matrix — the agent should consult the user's preferred provider.

**Verdict**: creation side is the deepest in the matrix after S2 — raster (GIMP + Krita), vector (Inkscape), AI (ComfyUI + Jimeng + 7 APIs), diagram (drawio + mermaid). Figma is the headline gap.

---

## 🎵 S6 · Music & Audio Production

| Stage | CLI | Gap |
|---|---|---|
| Compose/notation | `musescore` | — |
| Audio edit | `audacity` | |
| Record | `obs-studio` | |
| **DAW** | ❌ | **Reaper, Ableton, Logic, FL** |
| **AI music** | `suno`, `minimax-cli` | Udio, MusicGen |
| **Voice/TTS** | `elevenlabs`, `minimax-cli` | OpenAI TTS |
| Distribution | ❌ | Spotify (track mgmt), SoundCloud, DistroKid |

**Verdict**: still one of the weakest full scenarios, but no longer empty on the AI side. The biggest remaining gaps are a DAW and distribution.

---

## 🌐 S7 · Web / App Development

| Stage | CLI | Gap |
|---|---|---|
| Code LLM | `ollama`, `novita`, `minimax-cli` | — |
| CMS/content | `contentful`, `sanity` | WordPress, Strapi |
| E-commerce | `shopify` | Stripe, WooCommerce |
| Test mocks | `wiremock` | Postman/Insomnia, Playwright |
| Browser automation | `browser`, `safari`, `clibrowser` | — |
| Vector DB | `chromadb` | Pinecone, Weaviate, Qdrant |
| Process mgmt | `pm2` | — |
| Error tracking | `sentry` | — |
| Secrets | `1password-cli` | Doppler, Vault |
| Terminal | `iterm2` | — |
| **Hosting/deploy** | ❌ | **Vercel, Netlify, Cloudflare, Fly.io** |
| **Cloud provider** | ❌ | **AWS (aws-cli exists), GCP, Azure** |
| **Database** | ❌ | **Postgres, MySQL, Redis, MongoDB** |
| **CI/CD** | ❌ | GitHub Actions (gh), CircleCI |
| **Feature flags** | ❌ | LaunchDarkly, Unleash |
| Logging/APM | ❌ | Datadog, New Relic, Grafana |
| Analytics | ❌ | PostHog, Amplitude, GA |

**Verdict**: building blocks there, **but the deploy→observe loop is broken**. Closing `hosting + DB + analytics` would make web-dev fully agentic end-to-end.

---

## 📡 S8 · Creator Operations (stream-to-audience)

| Stage | CLI | Gap |
|---|---|---|
| Plan | LLM stack | — |
| Stream | `obs-studio`, `zoom` | Twitch/YouTube Live |
| Record | `openscreen` | — |
| Edit | `kdenlive`, `shotcut` | — |
| Caption | `videocaptioner` | — |
| Thumbnail | `gimp`, `krita` | — |
| **Upload** | ❌ | **YouTube, TikTok, Bilibili, Instagram** |
| **Social promo** | ❌ | **Twitter/X, LinkedIn, Threads** |
| Livestream chat | ❌ | Twitch API, StreamElements |

**Verdict**: same gap as S1 — **no social/platform distribution**. Highest-impact gap across the whole matrix because it breaks 3+ scenarios.

---

## 🤖 S9 · AI/ML & Data Science

| Stage | CLI | Gap |
|---|---|---|
| LLM inference | `ollama`, `novita`, `minimax-cli`, `notebooklm` | — |
| Image gen | `comfyui`, `jimeng` | — |
| Video gen | `jimeng`, `generate-veo-video` | — |
| Workflow | `dify-workflow`, `n8n` | LangGraph, Flowise |
| Vector DB | `chromadb` | — |
| Domain ML (chem) | `unimol_tools` | — |
| **Dataset mgmt** | ❌ | **HuggingFace CLI, kaggle** |
| **Experiment tracking** | ❌ | **W&B, MLflow** |
| **Training** | ❌ | Axolotl, Unsloth, trl |
| **Eval** | ❌ | lm-eval-harness, promptfoo |
| **Serving** | ❌ | Modal, Replicate, BentoML |

**Verdict**: inference side rich; **training/eval/serving totally absent** — no way for an agent to fine-tune and ship a model today.

---

## 🛠️ S10 · DevOps / SRE

| Stage | CLI | Gap |
|---|---|---|
| Terminal | `iterm2` | |
| Process | `pm2` | |
| Error/APM | `sentry` | Datadog, New Relic |
| Secrets | `1password-cli` | Vault, Doppler |
| Network/DNS | `adguardhome` | Cloudflare DNS |
| IoT fleet | `rms` | |
| Blockchain node | `eth2-quickstart` | |
| **K8s/Docker** | ❌ | kubectl/helm (standard) |
| **Cloud** | ❌ | **AWS, GCP, Azure** |
| **IaC** | ❌ | **Terraform, Pulumi** |
| **Incident** | ❌ | PagerDuty, Opsgenie |
| **Uptime** | ❌ | Statuspage, Uptime Kuma |

---

## 💬 S11 · Team Communication & Productivity

| Stage | CLI | Gap |
|---|---|---|
| IM (APAC) | `feishu`, `wecom` | |
| IM (global) | ❌ | **Slack, Teams, Discord** |
| Meetings | `zoom` | Google Meet, Webex |
| Kanban | `seaclip` | **Linear, Jira, Asana, Trello** |
| Notes | `obsidian`, `mubu` | Notion |
| Email | ❌ | **Gmail, Outlook** |
| Calendar | partial | **Google Calendar, Cal.com** |
| Automation | `n8n` | Zapier, Make |

**Verdict**: China/APAC side strong (feishu + wecom), **Western SaaS totally absent**. Slack + Linear + Gmail would unblock most Western-team workflows.

---

## 🛒 S12 · E-Commerce

| Stage | CLI | Gap |
|---|---|---|
| Storefront | `shopify` | WooCommerce |
| Catalog/CMS | `contentful`, `sanity` | — |
| Asset gen | `jimeng`, `comfyui`, `krita`, `inkscape` | — |
| Video ads | `jimeng`, `generate-veo-video`, `kdenlive` | — |
| **Payments** | ❌ | **Stripe, PayPal, Square** |
| **Email marketing** | ❌ | **Resend, Mailchimp, Klaviyo** |
| **Shipping** | ❌ | ShipStation, EasyPost |
| **Analytics** | ❌ | GA, Shopify Analytics deep |

---

## 🔬 S13 · Science / Academic

Strong (`zotero` + `notebooklm` + `exa` + `unimol_tools` + `mubu` + `obsidian` + `mermaid`) — mostly **missing LaTeX, arXiv, Jupyter-as-CLI, R/stats, domain-specific (PyMol/Chimera/QGIS)**.

---

## 🎯 S14 · Agentic Game Playing

Single CLI: `slay_the_spire_ii` — niche but demonstrates the pattern (agent drives a real GUI game through a local bridge API). Future expansion: other single-player games with mod APIs.

---

## 🛡️ S15 · Security / OSINT / Competitive Intel

Current: `intelwatch` (OSINT), `1password-cli` (secrets), `exa`/`safari` (search).
**Gaps**: Shodan, Censys, VirusTotal, pentesting frameworks, secrets-scanning, CVE feeds.

---

## 💰 S16 · Finance / Trading / Crypto

Current: `eth2-quickstart` (Ethereum staking).
**Gaps**: exchange CLIs (Coinbase, Binance), DeFi protocols, wallets, accounting (QuickBooks), invoicing (Stripe Billing).

---

## Closed-loop gap heatmap (where to invest)

Ranked by **how many scenarios unblock**:

| Gap | Impact (# scenarios) | Examples |
|---|---|---|
| 🔥 **Social/video upload CLIs** | 3 (S1, S8, S12) | YouTube, TikTok, Bilibili, Twitter/X |
| 🔥 **Cloud/hosting CLI harnesses** | 2 (S7, S10) | Vercel, Cloudflare, Fly.io |
| 🔥 **Slack / Linear / Gmail** | 2 (S7, S11) | completes Western team-comms |
| ⭐ **Notion** | 2 (S2, S11) | closes knowledge stack and team notes |
| ⭐ **Figma** | 2 (S5, S7) | UI/UX agent loop |
| ⭐ **Udio / MusicGen** | 2 (S1, S6) | deeper AI music coverage beyond Suno |
| ⭐ **MiniMax Voice / OpenAI TTS** | 3 (S1, S6, S8) | broader TTS coverage beyond ElevenLabs |
| ⭐ **HF + W&B + training harness** | 1 (S9) | full ML loop |
| ⭐ **3D texturing (Substance) + slicer (Cura/Bambu)** | 1 (S3) | 3D-to-physical loop |
| ⭐ **Unity / Steam / itch** | 1 (S4) | full gamedev ship loop |
| ⭐ **Stripe + Resend** | 1 (S12) | full e-com loop |

---

## Recommendations — making the matrix a first-class concept

1. **Add a `scenarios` field** to each registry entry (one CLI can belong to several). Then `cli-hub` can offer `cli-hub scenarios list` and `cli-hub scenarios <name> --missing` to directly surface gaps to an agent.
2. **Flip the category system** from taxonomy (`image`, `video`, `ai`) to **capability domain** (`visual`, `audio`, `text`, `composite`, `package`, `publish`). Capability reveals closed-loop gaps; category doesn't.
3. **Define each matrix as an ecosystem bundle, not just an install bundle**: every capability should document the best available first-party CLI, adjacent public CLIs, relevant APIs, and traditional package/native fallbacks.
4. **Seed matrix installs** in cli-hub for the installable portion only: `cli-hub matrix install <name>` grabs the CLIs, while the paired matrix docs also name non-installable APIs and library-level options.
5. **Publish this matrix as a living doc** — gaps in the matrix *are* the contributor roadmap. Missing CLIs are one category of gap; sometimes the immediate improvement is documenting the right API or fallback package before we build a harness.

---

## Appendix — full CLI inventory (by current registry category)

| Category | Harness CLIs | Public CLIs |
|---|---|---|
| ai | `comfyui`, `notebooklm`, `ollama`, `novita`, `dify-workflow` | `minimax-cli`, `generate-veo-video`, `jimeng` |
| audio | `audacity` | `elevenlabs` |
| 3d | `blender`, `freecad` | — |
| automation | `n8n` | — |
| communication | `zoom` | `feishu`, `wecom` |
| database | `chromadb` | — |
| design | `sketch` | — |
| devops | `eth2-quickstart`, `pm2`, `iterm2` | `sentry`, `1password-cli` |
| diagrams | `drawio`, `mermaid` | — |
| game / gamedev | `slay_the_spire_ii`, `godot` | — |
| generation | `anygen` | — |
| graphics | `renderdoc`, `cloudcompare`, `cloudanalyzer` | — |
| image | `gimp`, `inkscape`, `krita` | — |
| knowledge | `obsidian` | `obsidian-cli` |
| music | `musescore` | `suno` |
| network | `adguardhome`, `rms` | — |
| office | `libreoffice`, `mubu`, `zotero` | — |
| osint | `intelwatch` | — |
| project-management | `seaclip` | — |
| science | `unimol_tools` | — |
| search | `exa` | — |
| streaming | `obs-studio` | — |
| testing | `wiremock` | — |
| video | `kdenlive`, `shotcut`, `openscreen`, `videocaptioner` | — |
| web | `browser`, `safari`, `clibrowser` | `contentful`, `sanity`, `shopify` |
