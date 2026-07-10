# Render Doctor And Final Promotion

Use this after every render and before presenting a final MP4. Technical validity is not enough, but a binary QC script is also not enough. The render doctor gathers evidence from the exact file being delivered so the agent can investigate issues in context.

## Doctor Principle

`scripts/video_doctor.py` reports facts and investigation signals. It does not decide pass/fail. A nonzero exit means the doctor could not run. A zero exit means the report was produced, not that the video is good.

Agents must read the report, open the referenced frames/logs/audio where relevant, and decide whether the signal is acceptable for the brief.

## Baseline Doctor Commands

```bash
mkdir -p doctor
python cli-hub-matrix/video-creation/scripts/video_doctor.py probe final.mp4 --json > doctor/probe.json
python cli-hub-matrix/video-creation/scripts/video_doctor.py frames final.mp4 doctor/review_frames --json > doctor/frames.json
python cli-hub-matrix/video-creation/scripts/video_doctor.py tail final.mp4 doctor/tail --json > doctor/tail.json
python cli-hub-matrix/video-creation/scripts/video_doctor.py audio final.mp4 doctor/audio --scan-path . --json > doctor/audio.json
```

For captioned narration:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py captions captions.ass \
  --media final.mp4 \
  --narration narration.mp3 \
  --output-language "<brief-or-conversation-language>" \
  --json > doctor/captions.json
```

When the brief expects narration or intertitles to carry the full story, add `--expect-authored-coverage` to surface coverage-gap signals. Omit it for spot captions, music videos, ambient edits, source-audio-led scenes, or videos where captions are intentionally partial.

For source manifests:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py sources sources.json \
  --root . \
  --json > doctor/sources.json
```

For HyperFrames or other linter-backed motion projects:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py lint render_lint.log \
  --disposition lint_disposition.md \
  --json > doctor/lint.json
```

Optional low-level probes are still useful when a signal needs deeper inspection:

```bash
ffmpeg -hide_banner -i final.mp4 -vf blackdetect=d=0.15:pic_th=0.98 -an -f null - 2> doctor/blackdetect.log
ffmpeg -hide_banner -i final.mp4 -af silencedetect=n=-45dB:d=0.5 -vn -f null - 2> doctor/silencedetect.log
ffmpeg -hide_banner -i final.mp4 -vf freezedetect=n=0.003:d=1.0 -an -f null - 2> doctor/freezedetect.log
ffmpeg -v error -i final.mp4 -f null - 2> doctor/decode_errors.log
```

## What To Read

Read doctor reports in this order:

1. `probe`: duration, dimensions, fps, audio/video streams, aspect ratio clues.
2. `frames`: first/middle/last frames, every-2s contact sheet, and a dense final-act sheet. The default final-act sample is the last 20% only as an inspection heuristic.
3. `tail`: black/freeze/static-tail signals and tail contact sheet.
4. `captions`: PlayRes versus final dimensions, effective font size, generic style, caption role, voice-caption span versus narration/media, repeated/debug text signals, and optional authored-coverage checks when the brief needs them.
5. `sources`: provenance fields, source existence, selected ranges, story roles, source-text/watermark risks, quality caveats.
6. `audio`: loudness, high/low-band clues, exported listening snippets, and procedural-audio artifact scan.
7. `lint`: linter warnings/errors and whether the agent fixed, accepted, or blocked on them.

## Investigation Signals

Strong signals deserve manual inspection, not automatic rejection:

- Final duration differs from the requested range or `creative_direction.md`.
- First review frames do not reveal the topic/product/value proposition.
- Tail report points to black/frozen/static frames.
- Captions appear to extend far beyond narration, are authored at a different resolution, or are too small at final size.
- Voice/narration captions end long before the media ends when the brief expects authored narration or intertitles to carry the full story.
- Frame doctor reports very low visual diversity, especially in the final-act sample.
- Source ranges contain hardcoded subtitles, broadcast graphics, watermarks, or platform UI without crop/mask/safe-zone mitigation.
- Linter warnings are present without a written disposition.
- Source manifest lacks selected ranges, story roles, platform evidence, or rights notes.
- Generated or processed audio has harsh high-frequency hiss/sizzle, even if silence/volume scans look normal.
- Audio doctor finds procedural-audio artifacts where a long polished edit should have AI-generated music, downloaded relevant/authorized music, or source-audio-led ambience.
- Low-frequency pulse or repeated impact hits dominate the mix and make the soundtrack feel like test tones instead of music.
- Data/UI/chart/map/caption regions visibly shake or drift without a documented purpose.
- Reports point to a path other than the promoted final.

For each signal, write what you inspected and the decision: accepted with reason, revised, or escalated.

## Promotion Discipline

1. Keep the previous known-good output.
2. Run doctor reports on the candidate.
3. Inspect referenced frames/logs/audio directly.
4. If revising, render a new candidate and rerun the relevant doctor command.
5. After choosing a promoted final, hash it:

```bash
sha256sum final.mp4 > doctor/final_sha256.txt
```

6. Regenerate `probe`, `frames`, and any relevant caption/tail/source reports from the final path.
7. Scan reports for stale source names, old final paths, old hashes, and superseded versions.

## Reporting

A final review note should say:

- Which doctor commands were run.
- Which signals appeared.
- Which frames/logs/audio segments were inspected.
- What was revised or accepted with context.
- For independent reviews, the top visible risks or weaknesses with frame/timestamp evidence; a review that only repeats technical checks is incomplete.

Do not write "doctor passed." Write what the doctor helped you learn.
