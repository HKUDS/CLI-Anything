# Audacity CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 10 | 109 | Unit tests for project, tracks, clips, effects, labels, selection, session, audio utils, export presets, media probe |
| `test_full_e2e.py` | 7 | 45 | E2E workflows: real WAV I/O, audio processing, render pipeline, project lifecycle, CLI subprocess |
| **Total** | **17** | **154** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No Audacity installation required.

### TestProject (12 tests)
- Create project with defaults, custom name, custom settings (sample rate, bit depth, channels)
- Reject invalid sample rate, bit depth, and channel count
- Save and open roundtrip
- Open nonexistent file raises error; open invalid file raises error
- Get project info
- Set project settings; reject invalid settings

### TestTracks (16 tests)
- Add track with name; add track with auto-generated default name
- Add multiple tracks
- Add track with custom volume and pan
- Reject invalid volume, invalid pan, invalid track type
- Remove track; reject out-of-range index
- Get track by index
- Set track properties: name, mute, solo, volume; reject invalid property
- List all tracks

### TestClips (11 tests)
- Add clip to track with name and time range; add clip with auto-name
- Reject clip on out-of-range track; reject invalid time values (negative, end before start)
- Remove clip; reject out-of-range clip index
- Split clip at time point; reject split at invalid time
- Move clip to new position; reject negative position
- Trim clip boundaries
- List clips on a track

### TestEffects (17 tests)
- List all available effects; list by category
- Get effect info; reject unknown effect
- Validate params with defaults; validate custom params
- Reject out-of-range params; reject unknown effect params
- Add effect to track; reject unknown effect; reject out-of-range track
- Remove effect; reject out-of-range effect index
- Set effect param after creation; reject unknown param
- List effects on a track
- All registered effects have valid param definitions

### TestLabels (7 tests)
- Add point label; add range label
- Reject invalid start time (negative); reject invalid range (end before start)
- Remove label; reject out-of-range label index
- List labels

### TestSelection (7 tests)
- Set selection range; reject invalid selection (end before start)
- Select all with no clips returns zero range; select all with clips spans full range
- Select none clears selection
- Get current selection; get selection when empty

### TestSession (12 tests)
- Get project when none set raises error
- Set and get project
- Undo empty stack is no-op; redo empty stack is no-op
- Undo/redo cycle preserves state; multiple undos in sequence
- Session status reports depth
- Save session to file; save session with no path raises error
- List history entries
- Snapshot clears redo stack

### TestAudioUtils (16 tests)
- Generate sine wave (verified non-zero samples)
- Generate silence (verified all-zero samples)
- Apply gain (positive amplification)
- Apply fade in (first samples near zero, last samples at full)
- Apply fade out (first samples at full, last samples near zero)
- Apply reverse (mono and stereo)
- Apply echo (output longer than input)
- Apply normalize to target level
- Apply change speed (doubles rate, halves length)
- Apply limiter (clamps peak)
- Clamp samples to [-1, 1] range
- Mix two audio arrays
- Get RMS level; get peak level
- Convert linear amplitude to dB

### TestExportPresets (4 tests)
- List all export presets
- Get preset info for known preset
- Reject unknown preset name
- All presets have valid format and settings

### TestMediaProbe (5 tests)
- Probe real WAV file returns sample rate, channels, duration
- Probe nonexistent file raises error
- Check media reports all files present
- Check media reports missing files
- Get duration from WAV file

## End-to-End Tests (`test_full_e2e.py`)

E2E tests use real WAV file I/O with numpy arrays for audio sample verification.

### TestWavIO (5 tests)
- Write and read 16-bit WAV roundtrip preserves sample data
- Write and read stereo WAV roundtrip
- Write and read 24-bit WAV roundtrip
- WAV file properties (sample rate, channels, bit depth) are correct
- Stereo WAV file properties are correct

### TestAudioProcessing (12 tests)
- Positive gain increases RMS level
- Negative gain decreases RMS level
- Normalize reaches target RMS
- Fade in starts silent and ends at full volume
- Fade out starts at full volume and ends silent
- Reverse correctness (reversed array matches numpy flip)
- Echo adds delayed copy (output longer, contains original)
- Low-pass filter attenuates high frequencies (FFT verification)
- High-pass filter attenuates low frequencies (FFT verification)
- Change speed doubles playback rate (halves duration)
- Limiter clamps peak below threshold
- Mix two tracks sums samples correctly

### TestRenderPipeline (14 tests)
- Render empty project produces silent output
- Render single track to WAV
- Render stereo output
- Render mono output
- Render with gain effect applied
- Render with fade-in effect
- Render with reverse effect
- Render multiple tracks (mixed down)
- Muted track excluded from render
- Solo track isolates single track in render
- Overwrite protection on render output
- Render with echo effect
- Render with compression effect
- Render 24-bit output; render with channel count override

### TestProjectLifecycle (4 tests)
- Full workflow: create project, add tracks, add clips, add effects, render
- Save/open roundtrip preserves effects on tracks
- Multiple clips on timeline maintain positions
- Clip split and move operations

### TestSessionE2E (3 tests)
- Undo reverses track addition
- Undo reverses effect addition
- Heavy undo/redo stress test (many operations)

### TestMediaProbeE2E (4 tests)
- Probe real WAV file on disk
- Probe stereo WAV file
- Get duration from real file
- Check media with real files on disk

### TestCLISubprocess (4 tests)
- `project new` via CLI
- `project new --json` outputs valid JSON
- `effect list-available` lists effects
- `export presets` lists presets

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.11, pytest-9.0.2, pluggy-1.5.0
rootdir: /root/cli-anything
plugins: langsmith-0.5.1, anyio-4.12.0
collected 154 items

test_core.py   109 passed
test_full_e2e.py   45 passed

============================= 154 passed in 4.89s ==============================
```
