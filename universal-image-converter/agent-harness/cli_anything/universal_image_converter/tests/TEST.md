# Universal Image Converter CLI Harness — Test Documentation

## Test Inventory

| File | Test Classes | Focus |
|------|-------------|-------|
| `test_core.py` | 5 | Unit tests for formats, converter, and CLI commands |
| `test_full_e2e.py` | 5 | E2E workflows with real image I/O |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No external files or disk I/O required.

### TestFormats (8 tests)
- List input and output formats
- Get output format info for valid and invalid formats
- List quality presets
- Get quality preset for valid and invalid names
- Format info returns correct keys

### TestConverter (8 tests)
- Probe image returns correct dimensions and format
- Probe nonexistent file raises error
- Convert PNG to JPEG
- Convert with resize
- Convert with quality preset
- Convert rejects overwrite without flag
- Convert nonexistent file raises error

### TestCLI (8 tests)
- --help prints usage info
- formats command lists output formats
- format-info command shows format details
- quality-presets command lists presets
- info command on nonexistent file returns error
- convert --help shows options
- convert with --json returns valid JSON
- resize --help shows options

## End-to-End Tests (`test_full_e2e.py`)

### TestFormatConversion (5 tests)
- PNG to JPEG conversion
- PNG to WebP conversion
- PNG to BMP conversion
- PNG to TIFF conversion
- Conversion preserves image dimensions

### TestResizeConversion (3 tests)
- Resize with width only
- Resize with height only
- Resize with exact dimensions (no aspect)

### TestProbeImage (2 tests)
- Probe PNG file
- Probe JPEG file

### TestBatchConversion (2 tests)
- Batch convert multiple files
- Batch convert with prefix/suffix

### TestCLISubprocess (4 tests)
- Full workflow via CLI
- JSON output via CLI
- Convert with resize via CLI
- Error handling for missing files
