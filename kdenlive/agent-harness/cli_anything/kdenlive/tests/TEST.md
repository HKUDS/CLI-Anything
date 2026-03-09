# Kdenlive CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 8 | 118 | Unit tests for project, bin, timeline, filters, transitions, guides, timecode utils, session |
| `test_full_e2e.py` | 3 | 33 | E2E workflows: MLT XML generation, format validation, editing workflows |
| **Total** | **11** | **151** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No Kdenlive installation required.

### TestProject (17 tests)
- Create project with defaults, custom name, named profile (HD 1080p)
- Create with 4K profile and SD PAL profile
- Reject invalid profile, invalid resolution, invalid fps
- Create with custom dimensions
- Default project has empty collections (bin, tracks, guides, transitions)
- Project has metadata with creation timestamp
- Save and open roundtrip
- Open nonexistent file raises error; open invalid file raises error
- Get project info
- List profiles; all profiles have valid settings

### TestBin (12 tests)
- Import clip with name and type; import with auto-generated name
- Import all clip types (video, audio, image)
- Reject invalid clip type; reject negative duration
- Unique clip IDs; unique clip names (auto-dedup)
- Remove clip; reject remove on not-found clip
- List clips; get clip by ID; reject get on not-found ID

### TestTimeline (18 tests)
- Add video track; add audio track; add track with custom name
- Reject invalid track type
- Remove track; reject remove on not-found track
- Add clip to track with in/out points; add clip with auto-calculated out point
- Reject invalid clip ID; reject add to locked track; reject invalid in/out range
- Remove clip from track; reject remove on empty track
- Trim clip boundaries; reject invalid trim
- Split clip at position; reject split at boundary; reject split beyond duration
- Move clip to new position; reject negative position
- List tracks
- Clips sorted by position after multiple insertions

### TestFilters (16 tests)
- Add filter to timeline clip; add filter with default params
- Reject unknown filter; reject invalid param; reject out-of-range param
- Remove filter; reject invalid filter index
- Set filter param; reject invalid param name
- List filters on clip
- List all available filters; list by category
- All filters have MLT service ID
- Chroma key filter; volume filter; speed filter with specific params

### TestTransitions (11 tests)
- Add dissolve transition between tracks
- Reject unknown transition type; reject transition on same track; reject invalid track index
- Remove transition; reject remove on not-found transition
- Set transition param; set transition position; set transition duration
- List transitions
- All transition types have MLT service ID

### TestGuides (8 tests)
- Add guide at position with label
- Add guide with all types (marker, chapter, segment)
- Reject invalid guide type; reject negative position
- Guides sorted by position after multiple additions
- Remove guide; reject remove on not-found guide
- List guides

### TestTimecodeUtils (13 tests)
- Seconds to timecode: zero, simple values, hours
- Reject negative seconds
- Timecode to seconds: simple, hours, plain float string
- Reject invalid timecode format
- Roundtrip timecode conversion
- Seconds to frames and frames to seconds at given fps
- XML escape: ampersand, angle brackets, quotes
- XML escape: apostrophe

### TestSession (12 tests)
- Create session; set/get project; get project when none set raises error
- Undo/redo cycle; undo empty; redo empty
- Snapshot clears redo stack
- Session status reports depth
- Save session to file
- List history; max undo enforced
- Undo reverses clip import

## End-to-End Tests (`test_full_e2e.py`)

E2E tests generate real MLT XML and validate structure, format correctness, and full editing workflows.

### TestXMLGeneration (13 tests)
- Generated XML is a string
- XML has `<mlt>` root element
- XML contains profile element with resolution and fps
- XML has `<producer>` elements for each bin clip
- XML has `<playlist>` elements for each track
- XML has `<tractor>` element for timeline composition
- XML has `<filter>` elements for applied filters
- XML has transition elements
- XML has guide/marker properties
- Empty project produces valid minimal XML
- Special characters in names are XML-escaped
- Clip type numbers mapped correctly in producers
- SD PAL profile produces correct XML profile values

### TestFormatValidation (8 tests)
- JSON save/load roundtrip preserves all data
- JSON has all required top-level keys (name, profile, bin, tracks, etc.)
- Profile object has all required fields (width, height, fps, etc.)
- Clip entries have required fields (id, name, type, path, duration)
- Track entries have required fields (id, name, type, clips, locked)
- Timeline clip entries have required fields (clip_id, position, in, out)
- XML is well-formed (parseable by xml.etree)
- XML producer count matches bin clip count

### TestWorkflowE2E (18 tests)
- Basic edit workflow: import clips, create tracks, place clips on timeline, export XML
- Multicam workflow: multiple video tracks, clips from different cameras
- Audio/video workflow: separate audio and video tracks with clips
- Trim and split workflow: place clip, trim ends, split at midpoint
- Filter chain workflow: add multiple filters to clip, verify in XML
- Transition workflow: add transitions between tracks, verify in XML
- Guide workflow: add markers and chapter points, verify in XML
- Undo/redo workflow: import clips, undo, redo
- Save/load roundtrip: complex project with clips, tracks, filters, transitions, guides
- Render presets available and list correctly
- All profiles produce valid XML
- Complex timeline XML: multiple tracks with multiple clips and filters
- Move clip then export: relocate clip and verify updated XML
- Project info after edits: counts are accurate
- All filter types appear correctly in XML
- XML write to file: save XML string to disk file
- Timecode in workflow: use timecode utilities for positioning
- Split then filter workflow: split clip, add filter to one fragment
- Session with full workflow: undo/redo across complex editing sequence

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.11, pytest-9.0.2, pluggy-1.5.0
rootdir: ~/cli-anything
plugins: langsmith-0.5.1, anyio-4.12.0
collected 151 items

test_core.py   118 passed
test_full_e2e.py   33 passed

============================= 151 passed in 0.18s ==============================
```
