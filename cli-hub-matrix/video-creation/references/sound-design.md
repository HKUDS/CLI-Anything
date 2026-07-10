# Sound Design For Video Edits

Use this when a video needs more than a single music bed: trailer hits, risers, whooshes, drones, heartbeats, crowd/source accents, silence gaps, or narration-aware ducking.

## Required Deliverable

For polished edits, create `sound_design.md` with:

- Section map: time ranges, emotion, music role, and loudness target.
- Main music strategy: AI-generated music, downloaded relevant/authorized music, source ambience-led, or user-supplied music.
- Cue list: exact time, stem/file, story function, and visual sync point.
- Source Audio Policy when any downloaded/captured clip audio is used: time range, source file, `audio_role`, keep reason, overlap policy, processing, and review snippet.
- Ducking notes for narration, dialogue, source audio, or captions that need clarity.
- Generated-stem notes, including tools and parameters.
- Review notes for section loudness, true peak, final-act shape, and a listening pass that explicitly checks hiss, sizzle, clipping, and narration intelligibility.

Generated procedural stems should be separate WAV files named by role, for example `pulse.wav`, `riser_01.wav`, `impact_03.wav`, `drone_low.wav`, `heartbeat.wav`, or `whoosh_fast.wav`. Mark them as generated in `music_sources.json` or `sound_design.md`.

## Procedural Audio Guardrails

Procedural audio is useful for short UI hits, pulses, and risers, but raw noise is easy to make unlistenable.

- For polished videos around 60 seconds or longer, do not make a NumPy/ffmpeg/sox procedural bed the default main soundtrack. Use AI-generated music or downloaded relevant/authorized music as the main bed unless the brief explicitly asks for procedural/generative sound or the piece is intentionally source-ambience-led.
- Treat procedural audio as SFX/accent stems first: UI ticks, soft impacts, short risers, transition whooshes, drones, pulses, or a brief final hit.
- Do not use unfiltered Gaussian/full-band noise as a music bed, riser, or repeated whoosh.
- Shape noise with a short envelope, band-limit it, keep it low in the mix, and reserve it for transitional moments.
- Prefer tonal UI clicks, soft impacts, filtered sweeps, and real ambience over constant hiss.
- Export stems separately before mixing so a noisy stem can be muted or replaced without rebuilding the edit.
- If the user reports sizzling/noise, treat it as a critical issue even when `silencedetect`, `volumedetect`, or decode checks look normal.

Bad smell examples:

- `np.sin` low drones plus `rng.normal` risers as the entire music bed.
- Repeating sub hits every few seconds to fake pacing.
- "Procedural score" in `music_sources.json` with no real music, AI-generated music, or source-audio-led rationale.
- Source ambience mixed so low that it is only texture while synthetic pulses dominate the edit.

## Audio Roles

| Role | Purpose |
|---|---|
| Music bed | Continuity, tone, pacing. |
| Pulse | Gives cuts a motor without overwhelming narration. |
| Riser | Builds into a reveal, chapter change, or final hit. |
| Impact/sub drop | Marks a beat, dunk, reveal, title, or scene turn. |
| Whoosh | Motivates motion graphics, fast pans, or chapter transitions. |
| Drone | Adds dread, scale, or unresolved tension. |
| Heartbeat/silence | Creates a hold before a payoff. |
| Source audio | Proves authenticity or gives a scene a human edge. |
| Narration | Leads story logic; music should move around it. |

## Source Audio Overlap Rules

Classify every source-audio range before mixing it. Do not use vague labels such as "source texture" unless the range has been checked and is truly ambience.

| Audio role | Use |
|---|---|
| `silent_or_mute` | Source audio is unused, irrelevant, noisy, copyrighted music, platform intro, or would conflict with the designed mix. |
| `ambience_keep` | Natural room/machine/crowd/market sound with no dominant music or speech; may sit quietly under narration/music. |
| `dialogue_keep` | Source speech is story-critical; make it foreground and subtitle/translate it instead of talking over it. |
| `music_only` | Source music is the intended bed for that window, or mute it when adding a separate music bed. |
| `mixed_music_speech` | Speech and music are tangled; do not stack new narration/music without separation, replacement, or a source-only decision. |
| `needs_separation` | Use a separation step such as Demucs/Spleeter/UVR or choose a cleaner range before final mix. |

Keep one foreground voice at a time: agent narration or source dialogue, not both. Keep one intentional music bed at a time: source music or added music, not both. If a source clip has music and you add a new bed, mute the source audio by default unless the written policy says source-only, ducked, or separated. If a source clip has commentary and you add narration, mute/replace the source voice or let the source voice lead with subtitles.

Suggested `sound_design.md` table:

| Time | Source audio | Audio role | Keep reason | Overlap policy | Processing | Review snippet |
|---|---|---|---|---|---|---|
| 12-18s | `sources/clip.mp4` | `ambience_keep` | real machine room tone | low under music, no speech/music detected | high-pass, low-pass, duck under narration | `qc/audio/source_overlap_01.wav` |

## Patterns

Trailer final act:

- Quiet hold or drop-out.
- Riser into denser cuts.
- Several synchronized hits.
- One impact or silence gap.
- Unresolved sting, final image, or hard resolve.

Sports hype:

- Cut on downbeats and visible impacts.
- Use crowd/source accents sparingly to increase authenticity.
- Include one energy dip before the signature final hit.
- Avoid score loops that ignore athletic motion.

Film commentary:

- Narration leads the mix.
- Chapter score changes signal argument turns.
- Source audio reveals should be short and meaningful.
- Do not let effects fight dialogue or subtitles.

Digital/product launch:

- Small UI whooshes and tactile hits work better than oversized trailer booms.
- Sync audio changes to product state changes, not decorative text.

## Mix Review

Run whole-file and section-level loudness checks:

```bash
ffmpeg -hide_banner -i final.mp4 -af ebur128 -f null -
ffmpeg -hide_banner -i final.mp4 -af volumedetect -f null -
```

Review the opening, a dense middle section, and the ending/final act. Revise or justify the mix if the ending has no intentional shape for the genre, if narration is buried, if hits are visually unsynchronized, or if the same loop runs unchanged from start to finish without a deliberate calm/ambient reason.

For hiss/sizzle checks, also isolate the high band and listen or measure:

```bash
ffmpeg -hide_banner -i final.mp4 -af highpass=f=6000,volumedetect -f null -
```

A high-band measurement is only a clue; the final decision is the listening pass.

Use the bundled audio doctor to collect these clues and export listening snippets:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py audio final.mp4 qc/audio --scan-path .
```

When source audio is used, pass the manifests and sound design file so the doctor can export overlap snippets:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py audio final.mp4 qc/audio \
  --scan-path . \
  --sources-manifest sources.json \
  --music-manifest music_sources.json \
  --sound-design sound_design.md
```

Read the signals in context. Revise or justify the mix if the doctor finds procedural-audio artifacts, dominant low-frequency pulse, strong high-frequency hiss/sizzle, clipped peaks, flat loudness range, missing source-audio roles, or source audio layered under music/narration without a clear mute/duck/source-only/separation policy. For polished long edits, the normal fix is to replace the main bed with AI-generated music or downloaded relevant/authorized music, keep procedural stems only as low-volume accents, and keep source audio only where its role is explicit.
