---
name: cli-hub-matrix-knowledge-research
description: >-
  Capability-based multi-tool matrix for research, note-taking, document authoring,
  and publishing. Agents compose providers (CLI-Anything harnesses, public CLIs,
  Python libs, native binaries, cloud APIs) per capability.
---

# Knowledge / Office / Research Matrix (S2 — v2 capability-based)

Scenario **S2**. Strongest coverage in the current ecosystem: search, reference management, notes, synthesis, documents, and diagrams all have first-party harnesses; Python/native fallbacks fill the rest.

Schema: [`docs/cli-matrix/matrix_registry.schema.md`](../../docs/cli-matrix/matrix_registry.schema.md). Matrix plan: [`docs/cli-matrix/cli-matrix-plan.md`](../../docs/cli-matrix/cli-matrix-plan.md).

## Install

```bash
cli-hub matrix install knowledge-research
cli-hub matrix info    knowledge-research
```

---

## Decision rubric

1. **Available & adequate** — ranked by quality then inverse cost.
2. **Free-to-install** — Python libs / native binaries without credentials.
3. **Harness / public CLI install** — when warranted.
4. **Paid API escalation** — only when lower tiers can't meet the bar, env holds the key, or the user consents.

Offline context? Filter to `offline: true` providers.

---

## Preflight

```bash
cli-hub list --json
python - <<'PY'
import importlib.util
for m in ("pyzotero","bibtexparser","trafilatura","readability","httpx","playwright",
          "python_docx","openpyxl","pptx","reportlab","pypdf","pdfplumber","weasyprint",
          "langchain","llama_index","haystack","argostranslate"):
    print(m, importlib.util.find_spec(m) is not None)
PY
for b in pandoc qpdf pdftk exiftool latexmk tex dot mermaid plantuml hugo mkdocs jekyll; do
  command -v "$b" >/dev/null && echo "$b: yes" || echo "$b: no"
done
for e in OPENAI_API_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY PERPLEXITY_API_KEY TAVILY_API_KEY \
         SERPAPI_API_KEY BRAVE_API_KEY FIRECRAWL_API_KEY DEEPL_API_KEY \
         NOTION_API_KEY SEMANTIC_SCHOLAR_API_KEY WORDPRESS_TOKEN GHOST_ADMIN_KEY; do
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

Example: *To enable live Notion sync via the Notion API, please set `NOTION_API_KEY`. Cost: free tier suffices for most users. Quality: sota (round-trips block/page IDs). Reply 'skip' to fall back to local Obsidian vault + manual paste.*

---

## Capabilities

### `research.search` — web / literature search

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-exa` | harness-cli | `EXA_API_KEY` | metered | sota | no |
| `cli-anything-browser` / `safari` / `clibrowser` | harness-cli | browser installed | free | high | no |
| `duckduckgo-search` | python | pkg | free | good | no |
| `googlesearch-python` | python | pkg | free | good | no |
| Perplexity API | api | `PERPLEXITY_API_KEY` | paid | sota | no |
| Tavily | api | `TAVILY_API_KEY` | metered | high | no |
| Brave Search | api | `BRAVE_API_KEY` | metered | good | no |
| Google Custom Search | api | `GOOGLE_API_KEY` | metered | high | no |

### `research.retrieve` — fetch article text / scrape pages

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-browser` / `safari` / `clibrowser` | harness-cli | harness installed | free | high | no |
| `trafilatura` | python | pkg | free | high | yes |
| `readability-lxml` | python | pkg | free | good | yes |
| `httpx` + manual parse | python | pkg | free | basic | yes |
| `playwright` | python | pkg + browsers | free | sota | no |
| Firecrawl | api | `FIRECRAWL_API_KEY` | metered | sota | no |
| ScrapingBee | api | `SCRAPINGBEE_API_KEY` | paid | high | no |

### `research.reference` — citations, BibTeX, references

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-zotero` | harness-cli | Zotero installed | free | sota | yes |
| `pyzotero` | python | pkg + Zotero key | free | high | no |
| `habanero` (Crossref) | python | pkg | free | high | no |
| `bibtexparser` | python | pkg | free | good | yes |
| Crossref REST | api | none | free | high | no |
| Semantic Scholar | api | `SEMANTIC_SCHOLAR_API_KEY` (optional) | free | high | no |

### `knowledge.note` — note-taking / PKM

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-obsidian` | harness-cli | Obsidian installed | free | sota | yes |
| `cli-anything-mubu` | harness-cli | Mubu installed | free | high | no |
| `obsidian-cli` | public-cli | bin + vault path | free | high | yes |
| raw markdown + `git` | native | `git` | free | good | yes |
| `mdformat` | python | pkg | free | good | yes |
| Notion API | api | `NOTION_API_KEY` | free | sota | no |
| Roam / Logseq sync | — | — | — | — | — |

### `knowledge.outline` — outlining

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-mubu` | harness-cli | Mubu installed | free | high | no |
| OPML via `lxml` | python | pkg | free | good | yes |
| YAML outlines + `yq` | native | binary | free | good | yes |

### `knowledge.synthesize` — multi-doc synthesis / summarization

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-notebooklm` | harness-cli | harness installed | metered | sota | no |
| `cli-anything-intelwatch` | harness-cli | harness installed | free-metered | high | partial |
| `langchain` / `llama_index` + local LLM | python | pkg + ollama | free | high | yes |
| `haystack` | python | pkg | free | good | partial |
| Claude / OpenAI / Gemini (long context) | api | model key | metered | sota | no |

### `document.author` — write docs (DOCX, XLSX, PPTX, PDF)

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-libreoffice` | harness-cli | LibreOffice installed | free | high | yes |
| `cli-anything-anygen` | harness-cli | harness installed | free | high | yes |
| `python-docx` / `openpyxl` / `python-pptx` / `reportlab` | python | pkg | free | good | yes |
| Google Docs API | api | OAuth token | metered | sota | no |
| Microsoft Graph | api | Azure app + token | metered | sota | no |

### `document.format` — convert / reformat

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `pandoc` | native | binary | free | sota | yes |
| `cli-anything-libreoffice` (headless convert) | harness-cli | LibreOffice | free | high | yes |
| `docx2pdf` | python | pkg + Word/LO | free | good | yes |
| `weasyprint` | python | pkg | free | high | yes |
| CloudConvert | api | `CLOUDCONVERT_API_KEY` | metered | sota | no |

### `document.pdf` — manipulate PDFs (split, merge, OCR, extract)

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `qpdf` / `pdftk` | native | binary | free | sota | yes |
| `pypdf` | python | pkg | free | high | yes |
| `pdfplumber` | python | pkg | free | high | yes |
| `pdf2image` | python | pkg + poppler | free | good | yes |
| `ocrmypdf` | native | binary + tesseract | free | high | yes |
| Adobe PDF Services | api | Adobe creds | paid | sota | no |

### `diagram.create` — diagrams, flowcharts, architecture

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-drawio` | harness-cli | drawio installed | free | sota | yes |
| `cli-anything-mermaid` | harness-cli | mermaid-cli | free | high | yes |
| `graphviz` (`dot`) | native | binary | free | high | yes |
| `plantuml` | native | binary | free | high | yes |

### `text.translate` — translation

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `argos-translate` | python | pkg + lang packs | free | good | yes |
| DeepL | api | `DEEPL_API_KEY` | metered | sota | no |
| Google Translate | api | `GOOGLE_API_KEY` | metered | high | no |
| OpenAI / Claude | api | model key | metered | sota | no |

### `publish.web` — publish articles / blog posts

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `contentful` | public-cli | bin + space token | metered | high | no |
| `sanity` | public-cli | bin + project token | metered | high | no |
| `hugo` / `mkdocs` / `jekyll` / `pelican` | native/python | binary/pkg | free | high | yes |
| WordPress REST | api | app password | free | high | no |
| Ghost Admin | api | `GHOST_ADMIN_KEY` | free | high | no |
| Medium (legacy) | api | token | free | good | no |

### `publish.latex` — build PDFs from LaTeX

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `latexmk` + `texlive` | native | binaries | free | sota | yes |
| `pylatex` | python | pkg + texlive | free | high | yes |
| Overleaf API | api | `OVERLEAF_API_KEY` | paid | sota | no |
| Tectonic | native | binary | free | high | yes |

---

## Recipes

- **`literature-review`** — survey a topic, extract key papers, synthesize.
  Uses: `research.search`, `research.retrieve`, `research.reference`, `knowledge.synthesize`, `document.author`.

- **`meeting-to-doc`** — turn a recorded meeting into a structured document.
  Uses: `text.transcribe` (via S1 matrix), `knowledge.synthesize`, `document.author`, `document.format`.

- **`blog-post`** — research → write → publish.
  Uses: `research.search`, `research.retrieve`, `knowledge.synthesize`, `document.author`, `publish.web`.

- **`paper-draft`** — research + citations + LaTeX.
  Uses: `research.reference`, `knowledge.synthesize`, `document.author`, `publish.latex`.

- **`competitive-brief`** — fetch competitor pages, extract positioning, produce a briefing deck.
  Uses: `research.retrieve`, `knowledge.synthesize`, `document.author` (PPTX).

- **`pdf-book-digest`** — ingest a PDF book, OCR if needed, produce chapter summaries + quote file.
  Uses: `document.pdf`, `knowledge.synthesize`, `knowledge.note`.

---

## Known gaps

- **Notion** — Notion API exists as an escalation, but there is no harness for local-first Notion workflows. Recurs in S11 (team comms).
- **Google Docs / Microsoft 365 live editing** — API path only.
- **LaTeX harness** — `latexmk` + Tectonic cover the native path, but no agent-native wrapper yet.
- **Translation** — no first-party CLI; Python fallback and APIs only.

---

## Agent guidance

- **Run preflight once per session.** Many capabilities have strong Python or native paths that bypass the need to install anything.
- **Prefer local** for sensitive docs (legal, health, internal): use Obsidian + local LLM + `whisper` rather than cloud APIs.
- **Citations are load-bearing** — for academic work always route through `research.reference` so bibliographies stay consistent.
- **Chain `document.format` at the end**, not the middle: author in the richest source format (markdown or LaTeX) and convert last.
- **Workspace discipline** — one directory per project; keep `refs.bib`, source markdown, figures, and output PDFs colocated.
