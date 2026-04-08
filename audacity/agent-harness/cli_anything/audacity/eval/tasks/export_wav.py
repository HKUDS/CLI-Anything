"""Eval task: WAV export."""

import os

from cli_anything.audacity.core.project import create_project
from cli_anything.audacity.core.tracks import add_track
from cli_anything.audacity.core.clips import add_clip
from cli_anything.audacity.core.export import render_mix
from cli_anything.audacity.utils.audio_utils import generate_sine_wave, write_wav


TASK = {
    "id": "export_wav",
    "name": "WAV export",
    "description": "Render a simple project to WAV",
}


def run(ctx):
    work_dir = ctx.task_work_dir()
    artifacts_dir = ctx.task_artifacts_dir()

    source_wav = work_dir / "source.wav"
    samples = generate_sine_wave(
        frequency=440.0,
        duration=0.5,
        sample_rate=8000,
        amplitude=0.5,
        channels=1,
    )
    write_wav(str(source_wav), samples, sample_rate=8000, channels=1, bit_depth=16)

    project = create_project(
        name="Eval Export",
        sample_rate=8000,
        bit_depth=16,
        channels=1,
    )
    add_track(project, name="Track 1")
    add_clip(project, track_index=0, source=str(source_wav))

    output_path = artifacts_dir / "mix.wav"
    result = render_mix(project, str(output_path), preset="wav", overwrite=True)

    ok = os.path.exists(output_path) and result.get("file_size", 0) > 0
    metrics = {
        "file_size": result.get("file_size"),
        "duration": result.get("duration"),
        "tracks_rendered": result.get("tracks_rendered"),
    }

    return {
        "ok": ok,
        "metrics": metrics,
        "artifacts": [str(output_path)],
    }
