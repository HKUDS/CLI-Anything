# Shotcut: Project-Specific Analysis & SOP

## Architecture Summary

Shotcut is a Qt/QML video editor built on the **MLT Multimedia Framework**.

```
┌─────────────────────────────────────────────┐
│                  Shotcut GUI                 │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Timeline │ │ Playlist │ │   Filters   │ │
│  │  (QML)   │ │  (Qt)    │ │   (QML)     │ │
│  └────┬─────┘ └────┬─────┘ └──────┬──────┘ │
│       │             │              │         │
│  ┌────┴─────────────┴──────────────┴──────┐ │
│  │          MainWindow (Singleton)        │ │
│  │     Models: MultitrackModel,           │ │
│  │     PlaylistModel, AttachedFiltersModel│ │
│  └────────────────┬───────────────────────┘ │
│                   │                          │
│  ┌────────────────┴───────────────────────┐ │
│  │       MLT::Controller (Singleton)      │ │
│  │  Mlt::Producer, Mlt::Consumer,         │ │
│  │  Mlt::Profile, Mlt::Tractor            │ │
│  └────────────────┬───────────────────────┘ │
└───────────────────┼─────────────────────────┘
                    │
        ┌───────────┴──────────┐
        │    MLT Framework     │
        │  (libmlt, libmlt++)  │
        │  Producers, Filters, │
        │  Consumers, Tractor  │
        └───────────┬──────────┘
                    │
        ┌───────────┴──────────┐
        │  FFmpeg / LADSPA /   │
        │  frei0r / movit      │
        └──────────────────────┘
```

## The MLT XML Format

Shotcut projects are **MLT XML files** (`.mlt`). This is the key insight: we
manipulate projects entirely by reading and writing this XML format.

### MLT XML Structure

```xml
<?xml version="1.0" encoding="utf-8"?>
<mlt LC_NUMERIC="C" version="7.x" title="Shotcut" producer="main_bin">

  <!-- Video/Audio Profile -->
  <profile description="HD 1080p 30fps"
           width="1920" height="1080"
           frame_rate_num="30000" frame_rate_den="1001"
           sample_aspect_num="1" sample_aspect_den="1"
           display_aspect_num="16" display_aspect_den="9"
           colorspace="709"/>

  <!-- Media Producers (source clips) -->
  <producer id="producer0" in="00:00:00.000" out="00:01:30.000">
    <property name="resource">/path/to/video.mp4</property>
    <property name="mlt_service">avformat</property>
    <property name="shotcut:caption">video.mp4</property>
  </producer>

  <!-- Playlists (tracks) -->
  <playlist id="playlist0">
    <entry producer="producer0" in="00:00:05.000" out="00:00:15.000"/>
    <blank length="00:00:02.000"/>
    <entry producer="producer1" in="00:00:00.000" out="00:00:10.000"/>
  </playlist>

  <!-- Tractor (timeline container) -->
  <tractor id="tractor0" in="00:00:00.000" out="00:01:00.000">
    <multitrack>
      <track producer="background"/>
      <track producer="playlist0"/>   <!-- V1 -->
      <track producer="playlist1"/>   <!-- V2 -->
      <track producer="playlist2"/>   <!-- A1 -->
    </multitrack>
    <transition id="transition0">
      <property name="a_track">0</property>
      <property name="b_track">1</property>
      <property name="mlt_service">mix</property>
    </transition>
  </tractor>
</mlt>
```

### Key MLT Concepts

| Concept | MLT Element | Shotcut Equivalent |
|---------|-------------|-------------------|
| Source clip | `<producer>` | Media file in Source panel |
| Track | `<playlist>` | Timeline track |
| Timeline | `<tractor>` | The full timeline |
| Gap/Space | `<blank>` | Empty space on track |
| Clip on track | `<entry>` | Clip placed on timeline |
| Effect | `<filter>` | Applied filter |
| Transition | `<transition>` | Cross-dissolve, etc. |

### Shotcut-Specific Properties

Shotcut embeds custom properties in MLT XML using the `shotcut:` prefix:

- `shotcut:caption` — Display name for clips
- `shotcut:name` — Track names
- `shotcut:hash` — File content hash for tracking
- `shotcut:uuid` — Unique ID for each clip instance
- `shotcut:projectAudioChannels` — Channel configuration
- `shotcut:projectFolder` — Project folder mode flag

### Where Filters Live in the XML

Filters can be attached to three levels:

1. **Producer-level** (clip filters): `<filter>` as child of `<producer>`.
   Applied to that clip wherever it appears.
2. **Playlist-level** (track filters): `<filter>` as child of `<playlist>`.
   Applied to the whole track.
3. **Tractor-level** (global): `<filter>` as child of `<tractor>`.
   Applied to the final mix.

Our CLI attaches clip-level filters to the `<producer>` and track-level filters
to the `<playlist>`. This matches how Shotcut itself stores them.

## CLI Strategy

### What We Manipulate Directly (XML)
- Project creation and configuration (profiles)
- Adding/removing tracks (playlists in tractor)
- Placing clips on timeline (entries in playlists, with in/out points)
- Adding/removing filters and setting parameters
- Setting transitions
- Querying project structure and metadata

### What We Delegate to External Tools
- **melt** — Rendering (reads .mlt, applies all effects natively)
- **ffprobe** — Media file analysis (codec, duration, resolution)
- **ffmpeg** — Rendering fallback (requires filter translation), thumbnails

## The Rendering Pipeline

This is the most critical subsystem. Three methods in priority order:

### 1. melt (native, preferred)
Reads the `.mlt` file directly. All filters, transitions, and effects are applied
natively. No translation needed. But `melt` may not be installed everywhere.

### 2. ffmpeg with filter translation (fallback)
When `melt` is unavailable, we render with ffmpeg. This requires translating every
MLT filter into ffmpeg's `-filter_complex` syntax. The process:

1. Parse the MLT XML to extract clips, in/out points, and attached filters
2. For each clip, build an ffmpeg filter chain translating each MLT filter
3. Assemble a `-filter_complex` graph that processes all segments
4. Concat the processed segments into the final output

**Verified filter mappings (MLT → ffmpeg):**

| MLT Service | ffmpeg Filter | Parameter Translation |
|-------------|---------------|----------------------|
| `brightness` | `eq=brightness=X` | `level`: 1.0 = neutral; (level-1)*0.4 for ffmpeg |
| `frei0r.saturat0r` | `eq=saturation=X` | `saturation`: same scale (1.0 = neutral) |
| `frei0r.hueshift0r` | `hue=h=X` | `shift` * 360 for degrees |
| `sepia` | `colorchannelmixer=...` | Fixed matrix: rr=0.393 rg=0.769 rb=0.189 etc. |
| `charcoal` | `edgedetect,negate` | No params |
| `frei0r.IIRblur` | `boxblur=X` | `amount` * 10 for pixel radius |
| `mirror` | `hflip` | No params |
| `crop` | `crop=w:h:x:y` | Direct mapping |
| `dynamictext` | `drawtext=...` | `argument`→text, `size`→fontsize, colors mapped |
| `fadein-video` | `fade=t=in:...` | Parse keyframe string for duration |
| `fadeout-video` | `fade=t=out:...` | Parse keyframe string for duration |
| `volume` | `volume=X` | `level`: same scale (1.0 = neutral) |
| `fadein-audio` | `afade=t=in:...` | Parse keyframe string for duration |
| `fadeout-audio` | `afade=t=out:...` | Parse keyframe string for duration |

**Critical ffmpeg pitfalls:**

- **Multiple `eq=` filters:** ffmpeg rejects two `eq` filters in the same chain.
  If a clip has both brightness and saturation, merge into one:
  `eq=brightness=0.06:saturation=1.3` (not `eq=brightness=0.06,eq=saturation=1.3`).
- **Concat stream ordering:** Must be interleaved `[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1`,
  NOT grouped `[v0][v1][v2][a0][a1][a2]`. Error: "Media type mismatch between
  filter output pad".
- **Track-level vs clip-level filters:** Read filters from both the `<producer>`
  and the `<playlist>`. Missing one level = missing effects.

### 3. Script generation (last resort)
If neither melt nor ffmpeg are available, generate a shell script with the
melt command for the user to run elsewhere.

## Filter Registry

17 registered filters across video and audio:

### Video Filters
| CLI Name | MLT Service | Key Parameters |
|----------|-------------|----------------|
| `brightness` | `brightness` | `level` (1.0 = neutral, >1 = brighter) |
| `saturation` | `frei0r.saturat0r` | `saturation` (1.0 = neutral) |
| `hue` | `frei0r.hueshift0r` | `shift` (0.0–1.0, maps to 0–360°) |
| `blur` | `frei0r.IIRblur` | `amount` (0.0–1.0) |
| `sepia` | `sepia` | `u`, `v` (chrominance values) |
| `charcoal` | `charcoal` | `x_scatter`, `y_scatter`, `scale` |
| `mirror` | `mirror` | `reverse` (0=h, 1=v) |
| `crop` | `crop` | `left`, `right`, `top`, `bottom` |
| `glow` | `frei0r.glow` | `blur` (0.0–1.0) |
| `text` | `dynamictext` | `argument`, `size`, `fgcolour`, `family`, `halign`, `valign` |
| `affine` | `affine` | `transition.rect` (position/size) |
| `fadein-video` | Custom | `level` (keyframe string: "time=val;time=val") |
| `fadeout-video` | Custom | `level` (keyframe string) |
| `speed` | `timewarp` | `speed` (1.0 = normal) |

### Audio Filters
| CLI Name | MLT Service | Key Parameters |
|----------|-------------|----------------|
| `volume` | `volume` | `level` (1.0 = neutral) |
| `fadein-audio` | Custom | `level` (keyframe string) |
| `fadeout-audio` | Custom | `level` (keyframe string) |

## Command Map: GUI Action → CLI Command

| GUI Action | CLI Command |
|-----------|-------------|
| File → New | `project new --profile hd1080p30` |
| File → Open | `project open <path>` |
| File → Save | `project save [path]` |
| File → Export | `export render <output> [--preset name]` |
| Add video track | `timeline add-track --type video --name "V1"` |
| Add audio track | `timeline add-track --type audio --name "A1"` |
| Drag clip to timeline | `timeline add-clip <file> --track <n> --in <tc> --out <tc>` |
| Trim clip | `timeline trim <track> <clip> --in/--out <tc>` |
| Split clip | `timeline split <track> <clip> --at <tc>` |
| Remove clip | `timeline remove-clip <track> <clip>` |
| Move clip | `timeline move-clip <track> <clip> --to-track <n>` |
| Apply filter | `filter add <name> --track <n> --clip <n> --param k=v` |
| Set filter param | `filter set <index> <param> <value> --track <n> --clip <n>` |
| Remove filter | `filter remove <index> --track <n> --clip <n>` |
| View timeline | `timeline show` |
| Probe media | `media probe <file>` |

## Timecode Handling

### Accepted Formats

| Format | Example | Use Case |
|--------|---------|----------|
| `HH:MM:SS.mmm` | `00:01:30.500` | Standard timecode |
| `HH:MM:SS:FF` | `00:01:30:15` | Frame-precise editing |
| `HH:MM:SS` | `00:01:30` | Quick entry |
| `SS.mmm` | `90.5` | Short durations |
| Frame number | `2715` | Programmatic use |

### Precision at 29.97fps (30000/1001)

This is the standard NTSC rate and the default profile. Key issues:

- One frame = 33.3667ms (not exactly representable in decimal)
- `round()` must be used for float→frame conversion (not `int()` which truncates)
- `frames_to_timecode` uses integer millisecond arithmetic to avoid drift:
  ```
  total_ms = round(frames * fps_den * 1000 / fps_num)
  ```
- Timecode→frames→timecode roundtrips may differ by ±1 frame. This is inherent
  to non-integer FPS; tests should use `abs(a - b) <= 1` assertions.

## Export Presets

| Preset | Codec | Container | Use Case |
|--------|-------|-----------|----------|
| `default` | H.264 CRF 21 | MP4 | General purpose |
| `h264-high` | H.264 CRF 18 | MP4 | High quality |
| `h264-fast` | H.264 CRF 23, ultrafast | MP4 | Quick preview |
| `h265` | H.265 CRF 22 | MP4 | Smaller files |
| `webm-vp9` | VP9 CRF 30 | WebM | Web delivery |
| `prores` | ProRes 422 | MOV | Professional editing |
| `gif` | GIF palette | GIF | Animations |
| `audio-mp3` | MP3 192k | MP3 | Audio only |
| `audio-wav` | PCM s16le | WAV | Lossless audio |
| `png-sequence` | PNG | PNG files | Frame extraction |

## Verified Workflow: Social Media Highlight Reel

This end-to-end workflow was implemented and verified with pixel-level analysis:

1. **Probe** source video (1.mp4: 7s vertical 834x1112)
2. **Create** project (hd1080p30 profile)
3. **Add** 3 tracks (Main video, Titles, Music audio)
4. **Add** 3 clips cut from source (0.5–2.5s, 2.5–5.0s, 5.0–6.8s)
5. **Apply** filters:
   - Segment 1: brightness +15%, fade-in 0.5s, title text overlay
   - Segment 2: brightness +5%, saturation +30%, warm hue shift
   - Segment 3: sepia tone, brightness -10%, fade-out 1.5s
   - Audio track: fade-in 0.8s, fade-out 1.0s
6. **Export** to MP4 via ffmpeg-filtergraph method

**Verification results** (pixel analysis of output):
- Brightness +15%: content pixel mean 85.5 vs source 70.8 (+14.7 confirmed)
- Saturation +30%: color channel spread 71.8 vs source 58.3 (+13.5 confirmed)
- Fade-in: first frame mean brightness 3.3 (near black, confirmed)
- Fade-out: last frame mean brightness 0.0 (pure black, confirmed)
- Sepia: R > G > B channel ordering confirmed (24 > 22 > 17)

**Note on letterboxing:** The vertical source (834x1112) is scaled into 1920x1080
with black pillarbox bars. When comparing pixel values, exclude padding columns
(only analyze center ~810px) to avoid black bars skewing the averages.

## Test Coverage

**144 total tests** across two suites:

- `test_core.py` (65 tests): Unit tests with synthetic data. No ffmpeg/media needed.
- `test_full_e2e.py` (79 tests): E2E with real video file. Includes:
  - Project lifecycle (5)
  - Timeline tracks (7)
  - Timeline clips (16)
  - Filters (10)
  - Media probing (5)
  - Export/render (5)
  - Session undo/redo (6)
  - Timecode edge cases (5)
  - Real-world workflows (10): YouTube edit, montage, multicam, podcast,
    picture-in-picture, color grading, undo-heavy, save/load complex,
    iterative refinement, timeline visualization
  - CLI subprocess invocation (10)
