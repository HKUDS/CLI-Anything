"""Eval task: track + clip flow."""

from cli_anything.audacity.core.project import create_project
from cli_anything.audacity.core.tracks import add_track
from cli_anything.audacity.core.clips import add_clip, list_clips, split_clip
from cli_anything.audacity.utils.audio_utils import generate_sine_wave, write_wav


TASK = {
    "id": "track_clip_flow",
    "name": "Track and clip flow",
    "description": "Add track, add clip, split clip",
}


def run(ctx):
    work_dir = ctx.task_work_dir()
    wav_path = work_dir / "tone.wav"

    samples = generate_sine_wave(
        frequency=440.0,
        duration=0.5,
        sample_rate=8000,
        amplitude=0.5,
        channels=1,
    )
    write_wav(str(wav_path), samples, sample_rate=8000, channels=1, bit_depth=16)

    project = create_project(
        name="Eval Track Clip",
        sample_rate=8000,
        bit_depth=16,
        channels=1,
    )
    add_track(project, name="Track 1")
    clip = add_clip(project, track_index=0, source=str(wav_path))

    before = list_clips(project, 0)
    split_time = clip["start_time"] + (clip["end_time"] - clip["start_time"]) / 2.0
    split_clip(project, track_index=0, clip_index=0, split_time=split_time)
    after = list_clips(project, 0)

    ok = len(before) == 1 and len(after) == 2
    metrics = {
        "clips_before": len(before),
        "clips_after": len(after),
        "duration": after[0].get("duration", 0.0) if after else 0.0,
    }

    return {
        "ok": ok,
        "metrics": metrics,
        "artifacts": [],
    }
