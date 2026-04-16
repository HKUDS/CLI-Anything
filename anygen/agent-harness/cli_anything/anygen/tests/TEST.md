# AnyGen CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 6 | 45 | Unit tests for config, task creation, polling, session, export verification |
| `test_full_e2e.py` | 3 | 18 | E2E API tests + CLI subprocess tests |
| **Total** | **9** | **63** | |

## Unit Tests (`test_core.py`)

All unit tests use mocked HTTP responses — no real API calls, no API key needed.

### TestConfig (6 tests)
- Load config from file
- Save config creates directory and sets permissions
- API key priority: CLI arg > env var > config file
- Handle missing/corrupt config file
- Make auth token with and without Bearer prefix
- Require API key raises on missing

### TestCreateTask (8 tests)
- Create slide task with all parameters
- Create doc task with minimal parameters
- Reject invalid operation type
- Include file tokens in request body
- Include style in prompt
- Handle HTTP error response
- Handle API error (success=false)
- Create task saves local record

### TestQueryTask (5 tests)
- Query returns full task dict
- Updates local record on query
- Handle HTTP error
- Parse completed task with output
- Parse failed task with error

### TestPollTask (8 tests)
- Poll until completed
- Poll timeout raises TimeoutError
- Poll failed task raises RuntimeError
- Progress callback called on changes
- Multiple poll cycles before completion
- Handle transient query failures
- Respect custom interval and max_time
- Poll updates local record on completion

### TestSession (10 tests)
- Record command to history
- Undo returns last entry
- Redo returns undone entry
- Undo clears redo stack on new record
- Empty undo returns None
- Empty redo returns None
- History limit parameter
- Session status reports counts
- Save and load session file
- Handle corrupt session file

### TestExportVerify (8 tests)
- Verify valid PPTX (ZIP with Content_Types)
- Verify valid DOCX (OOXML)
- Verify valid PDF (magic bytes)
- Verify valid PNG (header)
- Verify valid SVG (xml tag)
- Reject empty file
- Reject missing file
- Reject corrupt ZIP

## E2E Tests (`test_full_e2e.py`)

Require `ANYGEN_API_KEY` environment variable set with a valid key.

### TestSlideWorkflow (6 tests)
- Create slide task returns task_id
- Poll slide task reaches completed
- Download PPTX file exists and is valid OOXML ZIP
- Full run workflow produces local file
- File size is reasonable (> 1KB)
- Task URL is accessible

### TestDocWorkflow (6 tests)
- Create doc task returns task_id
- Poll doc task reaches completed
- Download DOCX file exists and is valid OOXML ZIP
- Full run workflow produces local file
- File size is reasonable (> 1KB)
- Task URL is accessible

### TestCLISubprocess (6 tests)
- `--help` exits 0
- `--json config path` returns valid JSON
- `--json task list` returns JSON array
- `task create --operation slide --prompt "..."` succeeds
- `task status <id>` returns status
- Full workflow via subprocess produces file

## Realistic Workflow Scenarios

### Scenario 1: Quarterly Business Review Deck
- **Simulates**: Executive creating a slide deck from data
- **Operations**: upload file → prepare (multi-turn) → create slide → poll → download
- **Verified**: PPTX file valid, size > 0, is real OOXML ZIP

### Scenario 2: Technical Design Document
- **Simulates**: Engineer generating a design doc
- **Operations**: create doc → poll → download → verify DOCX
- **Verified**: DOCX is valid ZIP/OOXML, has Content_Types.xml

### Scenario 3: Architecture Diagram
- **Simulates**: Drawing a system architecture diagram
- **Operations**: create smart_draw → poll → download drawio/excalidraw
- **Verified**: Output is valid XML (drawio) or JSON (excalidraw)
