---
name: "cli-anything-intelwatch"
description: >-
  Zero friction. Full context. Competitive intelligence, M&A due diligence, and OSINT directly from your terminal. Uses Node.js/npx.
---

# cli-anything-intelwatch

Intelwatch bridges the gap between hacker OSINT and B2B Sales/M&A data. It executes complex financial data aggregation, technology stack detection, and AI-powered due diligence in seconds.

## Installation

This CLI is installed as part of the cli-anything-intelwatch package:

```bash
pip install cli-anything-intelwatch
```

**Prerequisites:**
- Node.js >=18 must be installed and accessible via `npx`
- Run `node -v` and `npx -v` to ensure your system meets the requirements

## Usage

### Basic Commands

```bash
# Show help
cli-anything-intelwatch --help

# Generate a deep profile for a company
cli-anything-intelwatch profile kpmg.fr

# Generate a profile with AI Due Diligence
cli-anything-intelwatch profile kpmg.fr --ai
```

## For AI Agents

When using this CLI programmatically:

1. Provide the domain name (e.g., `doctolib.fr`)
2. Use the `--ai` flag to let Intelwatch perform due diligence automatically
3. The output is human-readable and provides a deep breakdown of the company
4. Ensure `npx` is available on the machine

## Example Scenarios

- **M&A Due Diligence:** `cli-anything-intelwatch profile company-name.com --ai`
- **Sales Intelligence:** `cli-anything-intelwatch profile target-client.com`
