# OBS Studio CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 8 | 117 | Unit tests for project, scenes, sources, filters, audio, transitions, output, session |
| `test_full_e2e.py` | 8 | 36 | E2E workflows: stream setup, source manipulation, scene management, filter chains, output config, save/load, undo/redo, edge cases |
| **Total** | **16** | **153** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No OBS Studio installation required.

### TestProject (16 tests)
- Create project with defaults, custom dimensions, custom encoder, custom name
- Reject invalid resolution, fps, encoder, video bitrate, audio bitrate
- Save and open roundtrip
- Open nonexistent file raises error; open invalid file raises error
- Get project info
- Default project has transitions, streaming config, and recording config

### TestScenes (11 tests)
- Add scene; add scene with unique auto-name; unique IDs
- Remove scene; reject removing last scene; reject invalid index
- Duplicate scene creates independent copy
- Set active scene; reject invalid active scene index
- List scenes
- Removing active scene adjusts active index

### TestSources (19 tests)
- Add video_capture source; add all source types
- Reject invalid source type
- Add source with position, size, and settings
- Reject invalid (negative) size
- Auto-generate unique source names
- Remove source; reject invalid index
- Duplicate source
- Set source properties: visible, opacity; reject invalid property; reject out-of-range opacity
- Transform source: position, size, crop, rotation
- List sources; get source by index
- Source default properties are populated

### TestFilters (14 tests)
- Add filter to source; add filter with params
- Reject invalid filter type; reject invalid param; reject out-of-range param
- Add chroma_key filter; add noise_suppress filter
- Remove filter from source
- Set filter param; reject invalid filter param
- List filters on source
- List all available filters; list by category
- All filter types have param definitions

### TestAudio (13 tests)
- Add audio input source; add audio output source
- Reject invalid audio type
- Set volume; reject out-of-range volume
- Mute and unmute audio source
- Set monitor mode; reject invalid monitor mode
- Set balance; set sync offset
- Remove audio source
- List audio sources; unique audio names

### TestTransitions (11 tests)
- Add transition; add with custom duration
- Reject invalid transition type; reject negative duration
- Remove transition; reject removing last transition
- Set duration; reject negative duration
- Set active transition
- List transitions
- All transition types are valid

### TestOutput (14 tests)
- Set streaming service and config; reject invalid service; set stream key
- Set recording path, format, quality; reject invalid format; reject invalid quality
- Set output settings (resolution, fps, bitrate); set with preset; reject invalid preset
- Reject invalid output width; reject invalid encoder
- Get output info
- List encoding presets
- Valid services list; valid formats list

### TestSession (13 tests)
- Create session; set/get project; get project when none set raises error
- Undo/redo cycle; undo empty; redo empty
- Snapshot clears redo stack
- Session status reports depth
- Save session to file
- List history; max undo enforced
- Undo reverses source addition
- Undo reverses scene addition

## End-to-End Tests (`test_full_e2e.py`)

E2E tests validate complete streaming/recording workflows without OBS Studio installed.

### TestStreamSetupWorkflow (3 tests)
- Full stream setup: create project, add 4 scenes, add sources (webcam, display capture, overlay, BRB image), configure Twitch streaming, set balanced output preset
- Camera with green screen: add video_capture source, attach chroma_key and color_correction filters
- Audio mixer setup: add mic input and desktop audio output, adjust volumes, set monitoring mode

### TestSourceManipulation (4 tests)
- Source layering: create 4-layer scene (game capture, frame overlay, webcam, text) with custom positions
- Source transform workflow: position, resize, crop, and rotate a source
- Duplicate and modify source: duplicate text source, toggle visibility independently
- Source visibility toggle: hide and show source

### TestSceneWorkflow (4 tests)
- Multi-scene setup: 4 scenes with different sources, verify source counts per scene
- Scene switching: change active scene index
- Duplicate scene with sources: verify sources are independent copies
- Remove scene keeps other scenes intact

### TestFilterChains (4 tests)
- Audio filter chain: 5 filters in order (noise_suppress, noise_gate, compressor, gain, limiter)
- Video filter chain: chroma_key, color_correction, sharpen
- Modify filter param in chain
- Remove filter from middle of chain preserves order

### TestTransitionWorkflow (2 tests)
- Add stinger and slide transitions alongside defaults
- Change transition duration

### TestOutputConfiguration (2 tests)
- Full output config: streaming (YouTube), recording (MP4, high quality), encoding settings (1080p60, 8000kbps)
- Apply preset then override single setting (bitrate override keeps encoder from preset)

### TestSaveLoadRoundtrip (2 tests)
- Full roundtrip: project with scenes, sources, filters, audio, transitions, streaming, recording
- Save/load preserves source transforms (position, size, crop)

### TestSessionUndoRedo (5 tests)
- Undo/redo source addition
- Undo scene addition
- Undo filter chain (two filters added, two undos)
- Undo audio volume change
- Multiple undo/redo sequence (3 name changes, 3 undos, 2 redos)

### TestEdgeCases (10 tests)
- Empty project info shows zero sources
- Source on nonexistent scene raises IndexError
- Filter on nonexistent source raises ValueError
- Remove source from empty scene raises ValueError
- Transform nonexistent source raises ValueError
- Negative crop values raise ValueError
- All source types are addable
- All filter types are addable
- Chroma key rejects invalid color type
- Session save with no path raises ValueError
- Large scene collection (20 scenes, 21 sources)

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.11, pytest-9.0.2, pluggy-1.5.0
rootdir: ~/CLI-Anything
plugins: langsmith-0.5.1, anyio-4.12.0
collected 153 items

test_core.py   117 passed
test_full_e2e.py   36 passed

============================= 153 passed in 0.19s ==============================
```
