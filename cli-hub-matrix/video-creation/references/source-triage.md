# Source Triage For Found-Footage Video

Use this when a video depends on internet footage, public-domain clips, platform-origin media, or named scenes. The goal is to avoid cutting with weak sources just because they downloaded.

## Evidence Levels

Classify every source before editing:

| Level | Meaning | Use |
|---|---|---|
| Direct platform source | Downloaded from the original or intended platform URL. | Preferred when user supplied the URL or the platform source is authorized and reachable. |
| Verified platform-origin transport | Downloaded through another host that preserves credible source metadata, such as a Wikimedia transcode with source information or a `ytarchive:` capture. | Accept when direct platform access fails but the transport proves origin well enough for the brief. |
| Weak mirror | Reupload, compilation, fan edit, generic mirror, or unverifiable clip. | Use only when the user accepts the caveat and the final deliverable is appropriate for that risk. |

Downloadability is not permission. Do not bypass DRM, paywalls, login restrictions, or access controls. Use cookies only when the user has authorized access to the content.

## Required Manifest Fields

For `sources.json`, include one object per source:

```json
{
  "id": "source_short_name",
  "platform_url": "https://...",
  "transport_url": "https://...",
  "evidence_level": "direct-platform|verified-transport|weak-mirror",
  "download_command": "yt-dlp ...",
  "cookie_file": "path or null",
  "local_file": "sources/source_short_name.mp4",
  "probe": {
    "duration": 123.45,
    "width": 1920,
    "height": 1080,
    "fps": "30000/1001",
    "video_bitrate": 8000000,
    "audio_bitrate": 160000
  },
  "selected_ranges": [
    {
      "start": 12.3,
      "end": 18.8,
      "role": "setup|reveal|impact|contrast|proof|payoff",
      "audio_role": "silent_or_mute|ambience_keep|dialogue_keep|music_only|mixed_music_speech|needs_separation",
      "source_music_present": "none|light|dominant|unknown",
      "speech_needed": false,
      "overlap_policy": "mute_source|keep_ambience_low|source_dialogue_foreground|source_music_only|duck_new_music|separate_vocals|reject_range",
      "separation_tool": "none|demucs|spleeter|uvr|api",
      "quality_notes": "why this range survives triage",
      "risk": "watermark/source subtitle/soft crop/etc."
    }
  ],
  "creator": "name if known",
  "license": "license or unknown",
  "rights_notes": "authorization/attribution/caveat",
  "quality_caveat": "none or specific caveat"
}
```

For music, keep equivalent details in `music_sources.json`.

Audio fields are required when a selected range has an audio stream and the final uses any source sound. Classify source audio before editing:

- `silent_or_mute`: irrelevant audio, platform intro, pure source BGM that would fight added music, or source commentary that would fight new narration.
- `ambience_keep`: natural ambience with no dominant music or speech.
- `dialogue_keep`: source speech is needed; it must become foreground with subtitles/translation, not background under new narration.
- `music_only`: source music is the intentional bed for that window; do not add another full music bed there.
- `mixed_music_speech` / `needs_separation`: use Demucs, Spleeter, UVR, an approved API, or reject the range before adding new music or narration.

If the source audio is only used for authenticity, prove it is ambience. Do not label speech/music bleed as "texture."

## Triage Workflow

1. Probe every source before watching it in detail:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py probe sources/source.mp4
```

2. Make a source overview contact sheet:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py frames sources/source.mp4 review/source_name
```

3. After drafting `sources.json`, run the source doctor:

```bash
python cli-hub-matrix/video-creation/scripts/video_doctor.py sources sources.json --root .
```

4. Read the doctor signals for missing provenance, stale files, weak ranges, low-quality sources, missing audio roles, and risky source-audio overlap policies. The doctor is not a rights verifier; it is a prompt for investigation.
5. Mark likely usable ranges with a story role. A range without a role is not selected footage.
6. Make contact sheets for selected ranges or dense action sections.
7. Reject bad ranges before timeline work; do not push the problem into color, crop, captions, or NLE effects.

When source footage has hardcoded subtitles, broadcast graphics, watermarks, or platform UI, record the risk and mitigation in the selected range: safe-zone placement, crop, mask/blur, replacement, or a written reason it is acceptable. The source doctor will flag text-heavy risks that lack mitigation notes.

## Rejection Checklist

Reject or crop/mask ranges that have:

- Too-low resolution for the final format, unless the low-fi look is intentional.
- Static shots that do not support the beat.
- Countdown cards, ranking cards, source title cards, end credits, sponsor cards, or large hardcoded numbers.
- Hardcoded captions/subtitles that fight the final captions.
- Watermarks or platform UI that cannot be justified or safely cropped.
- Repeated content from another selected range unless it is a deliberate callback.
- Off-theme action, wrong character/team/object, or generic stock feel.
- Weak platform evidence when the brief requires real YouTube/Bilibili/source provenance.
- Audio with dialogue/SFX bleed when the source is supposed to be clean music.
- Source music stacked under a new music bed without a source-only, ducking, mute, or separation decision.
- Source commentary stacked under new narration; choose one foreground voice or separate/replace the source audio.

## Contact Sheets To Keep

For found-footage edits, keep these under `review/` or equivalent:

- One overview sheet per raw source.
- One sheet of all selected ranges.
- One final used-ranges sheet after assembly.
- One dense final-act sheet for trailer/sports/music edits, using the final section size that fits the genre.

Reports must name the exact final source files and ranges used. If a source is replaced after review, regenerate the sheets and update the manifest.
