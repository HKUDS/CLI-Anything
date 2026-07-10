# Shotcut And Kdenlive NLE Workflow

Use this when an edit benefits from a real timeline: multiple tracks, transitions, reusable project files, source crops, long audio beds, or harness-controlled NLE rendering.

## When To Choose An NLE

Prefer Shotcut or Kdenlive when:

- The timeline has many clips, transitions, or layered tracks.
- The user may want a project file they can reopen.
- Manual review or future editability matters.
- MoviePy/ffmpeg filtergraphs are becoming brittle.

Prefer MoviePy or raw `ffmpeg` when:

- The edit is deterministic and simple.
- The task is mostly concat, burn-in, resize, trim, mux, or thumbnail extraction.
- The environment cannot run long NLE jobs reliably.

## Provider Boundary Pattern

Use a clear boundary between tools:

1. `ffmpeg`: create stable mezzanine clips, source crops, speed-ramp snippets, and title-card video segments when NLE text filters are risky.
2. NLE harness: create the project, import media, arrange tracks, add transitions/filters, and render a master.
3. `ffmpeg`: burn ASS captions if the caption pass is post-NLE, normalize fps/SAR/DAR/profile/color tags, mux final audio, and run doctor investigation.

Do not assume a clean mezzanine segment contains later captions, chapter cards, watermarks, or overlays. Choose one caption stage and document it before rendering.

## Mezzanine Conventions

Use boring, stable clip properties:

- Constant frame rate matching the final project, usually 24, 25, 30, or 60 fps.
- `yuv420p`, square pixels, known dimensions, and normalized rotation.
- Clean crop/scale decisions made before NLE import.
- Audio-less video snippets unless audio from that source is intentionally used.
- Short filenames with no spaces when harnesses or MLT paths are fragile.

Example:

```bash
ffmpeg -y -i source.mp4 \
  -ss 12.3 -t 5.7 \
  -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,setsar=1" \
  -an -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p mezz/shot_001.mp4
```

## Render Resilience

For long renders:

- Write progress logs from the harness or render command.
- Keep the previous good output until the new candidate has been investigated and accepted.
- Probe the rendered file before promotion.
- Full-decode the candidate to catch missing `moov`, corrupt packets, and partial MP4s.
- If the environment kills long renders, render shorter chunks and assemble with `ffmpeg`.
- Never update reports before the exact promoted final file exists.

Checks after every NLE render:

- Actual duration versus intended timeline duration.
- Video stream fps versus project fps.
- SAR/DAR and final dimensions.
- Video track coverage through the audio tail.
- Whether content speed visually matches audio after any normalization.
- Whether captions/chapter cards survived the selected caption stage.

## Known Failure Modes

| Symptom | Likely cause | Response |
|---|---|---|
| Black or frozen tail | Video track shorter than audio or render ended on empty track. | Extend/fill video track, trim audio, rerender, run `video_doctor.py tail` and inspect the tail contact sheet. |
| Valid MP4 with bad playback | Partial render, missing `moov`, bad timestamps. | Full-decode, rerender or remux from a healthy master. |
| Wrong speed after normalization | FPS/timebase changed after NLE render. | Compare duration/fps before and after normalization; avoid filters that rewrite timing unintentionally. |
| Captions disappeared | Clean mezzanine was rendered before caption overlay stage. | Burn captions after NLE master or include captions inside NLE by design. |
| Source cards or hardcoded subs dominate | Source triage skipped or ranges were selected from overview cards. | Rebuild scene library and reject/crop those ranges. |
| PNG overlays render with black backing | Alpha/format handling issue in MLT path. | Pre-render cards as video with alpha-safe settings or use ffmpeg overlay. |

## Promotion

Promote only after `video_doctor.py probe`, `video_doctor.py frames`, and relevant tail/caption/source doctor reports have been read and accepted in context. Hash the candidate and final path, regenerate review assets from the final path, and update reports last. Do not write "doctor passed"; record which signals were investigated and why the final is acceptable.
