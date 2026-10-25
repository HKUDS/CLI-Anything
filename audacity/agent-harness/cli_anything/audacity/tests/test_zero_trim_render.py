"""Check source trim boundaries against the actual exported PCM samples."""

import math

import pytest

from cli_anything.audacity.core.clips import add_clip, trim_clip
from cli_anything.audacity.core.export import _render_clip, render_mix
from cli_anything.audacity.core.project import create_project
from cli_anything.audacity.core.tracks import add_track
from cli_anything.audacity.utils.audio_utils import read_wav, write_wav


@pytest.mark.parametrize("channels", [1, 2])
def test_zero_trim_does_not_leak_into_later_clip(tmp_path, channels):
    source = str(tmp_path / "source.wav")
    output = str(tmp_path / "mix.wav")
    rate = 8000
    write_wav(source, [0.5] * rate * channels, rate, channels, 16)
    project = create_project(sample_rate=rate, channels=channels)
    add_track(project)
    add_clip(project, 0, source)
    trim_clip(project, 0, 0, trim_end=0.0)
    add_clip(project, 0, source, start_time=0.5)

    render_mix(project, output)
    samples, actual_rate, actual_channels, _ = read_wav(output)
    assert (actual_rate, actual_channels) == (rate, channels)
    assert len(samples) == int(1.5 * rate) * channels
    assert samples[:rate // 2 * channels] == [0.0] * (rate // 2 * channels)
    # The surviving clip must still render, without the removed clip mixed in.
    assert samples[rate // 2 * channels:] == pytest.approx(
        [0.5 / math.sqrt(2) if channels == 2 else 0.5] * rate * channels,
        abs=1e-4,
    )


@pytest.mark.parametrize("end, frames", [(None, 8000), (0.0, 0), (0.25, 2000)])
def test_source_trim_distinguishes_zero_from_unspecified(tmp_path, end, frames):
    source = str(tmp_path / "source.wav")
    write_wav(source, [0.5] * 8000, 8000, 1, 16)
    samples = _render_clip({"source": source, "trim_end": end}, 8000, 1)
    assert len(samples) == frames
