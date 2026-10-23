"""Real-WAV regressions for channel conversion followed by resampling."""

import json
import subprocess

import pytest

from cli_anything.audacity.core.clips import add_clip
from cli_anything.audacity.core.export import _render_clip, render_mix
from cli_anything.audacity.core.project import create_project, save_project
from cli_anything.audacity.core.tracks import add_track
from cli_anything.audacity.tests.test_full_e2e import _resolve_cli
from cli_anything.audacity.utils.audio_utils import read_wav, write_wav


def source_wav(tmp_path, channels):
    path = str(tmp_path / "source.wav")
    # Distinct channels make averaging, rather than channel loss, observable.
    frame = [0.25, 0.75] if channels == 2 else [0.5]
    write_wav(path, frame * 4800, 48000, channels, 16)
    return path


@pytest.mark.parametrize("source_channels,target_channels,target_rate", [
    (2, 1, 16000), (2, 1, 96000), (2, 1, 48000),
    (1, 2, 16000), (1, 2, 96000), (2, 2, 16000), (1, 1, 16000),
])
def test_channel_conversion_preserves_resampled_frame_count(
    tmp_path, source_channels, target_channels, target_rate,
):
    source = source_wav(tmp_path, source_channels)
    samples = _render_clip({"source": source}, target_rate, target_channels)
    assert len(samples) == target_rate // 10 * target_channels
    expected = ([0.25, 0.75] if source_channels == target_channels == 2
                else [0.5] * target_channels)
    # Check both halves, avoiding the existing final-frame zero interpolation.
    for fraction in (0, 0.25, 0.5, 0.75, 0.99):
        frame = int(target_rate // 10 * fraction)
        assert samples[frame * target_channels:(frame + 1) * target_channels] == pytest.approx(
            expected, abs=2 / 32767,
        )


def test_render_downmixed_resample_preserves_full_clip_signal(tmp_path):
    source = source_wav(tmp_path, 2)
    project = create_project(sample_rate=16000, channels=1)
    add_track(project, volume=0.5)
    add_clip(project, 0, source)
    output = str(tmp_path / "mix.wav")
    result = render_mix(project, output)
    samples, rate, channels, _ = read_wav(output)
    assert (rate, channels, len(samples), result["duration"]) == (16000, 1, 1600, 0.1)
    assert samples == pytest.approx([0.25] * 1600, abs=2 / 32767)


def test_cli_channel_override_resamples_the_entire_source(tmp_path):
    source = source_wav(tmp_path, 2)
    project = create_project(sample_rate=16000, channels=2)
    add_track(project)
    add_clip(project, 0, source)
    project_path = str(tmp_path / "project.json")
    save_project(project, project_path)
    output = str(tmp_path / "mono.wav")
    process = subprocess.run(
        _resolve_cli("cli-anything-audacity") + [
            "--json", "--project", project_path, "export", "render", output,
            "--channels", "1",
        ], capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["duration"] == 0.1
    assert report["channels"] == 1
    samples, rate, channels, _ = read_wav(output)
    assert (rate, channels, len(samples)) == (16000, 1, 1600)
    assert samples == pytest.approx([0.5] * 1600, abs=2 / 32767)
