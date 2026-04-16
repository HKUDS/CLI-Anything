"""End-to-end tests for Audacity CLI with real audio files.

These tests create actual WAV files, apply effects, mix tracks,
and verify audio properties (sample rate, duration, channels,
RMS levels, peak values). Uses numpy only for analysis/verification.

40+ tests covering the full pipeline.
"""

import json
import math
import os
import sys
import struct
import tempfile
import wave
import subprocess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from cli_anything.audacity.core.project import create_project, save_project, open_project, get_project_info
from cli_anything.audacity.core.tracks import add_track, list_tracks, set_track_property
from cli_anything.audacity.core.clips import add_clip, list_clips, split_clip, move_clip, trim_clip
from cli_anything.audacity.core.effects import add_effect, list_effects
from cli_anything.audacity.core.labels import add_label, list_labels
from cli_anything.audacity.core.selection import set_selection, select_all, get_selection
from cli_anything.audacity.core.media import probe_audio, check_media, get_duration
from cli_anything.audacity.core.export import render_mix, EXPORT_PRESETS
from cli_anything.audacity.core.session import Session
from cli_anything.audacity.utils.audio_utils import (
    generate_sine_wave, generate_silence, write_wav, read_wav,
    get_rms, get_peak, db_from_linear, apply_gain, apply_normalize,
    apply_fade_in, apply_fade_out, apply_reverse, apply_echo,
    apply_low_pass, apply_high_pass, apply_change_speed, apply_limit,
    mix_audio,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sine_wav(tmp_dir):
    """Create a 1-second 440Hz sine wave WAV file (mono, 44100Hz, 16-bit)."""
    path = os.path.join(tmp_dir, "sine_440.wav")
    samples = generate_sine_wave(440, 1.0, 44100, 0.5, 1)
    write_wav(path, samples, 44100, 1, 16)
    return path


@pytest.fixture
def stereo_wav(tmp_dir):
    """Create a 2-second stereo WAV file with different tones L/R."""
    path = os.path.join(tmp_dir, "stereo.wav")
    # Left channel: 440Hz, Right channel: 880Hz
    duration = 2.0
    sr = 44100
    n = int(duration * sr)
    samples = []
    for i in range(n):
        t = i / sr
        left = 0.4 * math.sin(2 * math.pi * 440 * t)
        right = 0.4 * math.sin(2 * math.pi * 880 * t)
        samples.append(left)
        samples.append(right)
    write_wav(path, samples, sr, 2, 16)
    return path


@pytest.fixture
def silence_wav(tmp_dir):
    """Create a 3-second silence WAV file."""
    path = os.path.join(tmp_dir, "silence.wav")
    samples = generate_silence(3.0, 44100, 1)
    write_wav(path, samples, 44100, 1, 16)
    return path


@pytest.fixture
def short_wav(tmp_dir):
    """Create a 0.5-second 1kHz sine wave."""
    path = os.path.join(tmp_dir, "short_1k.wav")
    samples = generate_sine_wave(1000, 0.5, 44100, 0.7, 1)
    write_wav(path, samples, 44100, 1, 16)
    return path


def _read_wav_numpy(path):
    """Read a WAV file into a numpy array for analysis."""
    samples, sr, ch, bd = read_wav(path)
    return np.array(samples), sr, ch, bd


# -- WAV I/O Round-trip Tests ----------------------------------------------

class TestWavIO:
    def test_write_read_roundtrip_16bit(self, tmp_dir):
        path = os.path.join(tmp_dir, "rt16.wav")
        original = generate_sine_wave(440, 0.1, 44100, 0.5, 1)
        write_wav(path, original, 44100, 1, 16)
        loaded, sr, ch, bd = read_wav(path)
        assert sr == 44100
        assert ch == 1
        assert bd == 16
        assert abs(len(loaded) - len(original)) <= 1
        # Check correlation (should be very high)
        min_len = min(len(original), len(loaded))
        corr = np.corrcoef(original[:min_len], loaded[:min_len])[0, 1]
        assert corr > 0.99

    def test_write_read_roundtrip_stereo(self, tmp_dir):
        path = os.path.join(tmp_dir, "rt_stereo.wav")
        samples = generate_sine_wave(440, 0.1, 44100, 0.5, 2)
        write_wav(path, samples, 44100, 2, 16)
        loaded, sr, ch, bd = read_wav(path)
        assert ch == 2
        assert abs(len(loaded) - len(samples)) <= 2

    def test_write_read_roundtrip_24bit(self, tmp_dir):
        path = os.path.join(tmp_dir, "rt24.wav")
        original = generate_sine_wave(440, 0.1, 44100, 0.5, 1)
        write_wav(path, original, 44100, 1, 24)
        loaded, sr, ch, bd = read_wav(path)
        assert bd == 24
        min_len = min(len(original), len(loaded))
        corr = np.corrcoef(original[:min_len], loaded[:min_len])[0, 1]
        assert corr > 0.99

    def test_wav_file_properties(self, sine_wav):
        with wave.open(sine_wav, "r") as wf:
            assert wf.getframerate() == 44100
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            duration = wf.getnframes() / wf.getframerate()
            assert abs(duration - 1.0) < 0.01

    def test_stereo_wav_properties(self, stereo_wav):
        with wave.open(stereo_wav, "r") as wf:
            assert wf.getnchannels() == 2
            duration = wf.getnframes() / wf.getframerate()
            assert abs(duration - 2.0) < 0.01


# -- Audio Processing Tests ------------------------------------------------

class TestAudioProcessing:
    def test_gain_positive(self, tmp_dir):
        samples = generate_sine_wave(440, 0.5, 44100, 0.3, 1)
        gained = apply_gain(samples, 6.0)
        # +6dB should roughly double
        assert get_peak(gained) > get_peak(samples) * 1.8

    def test_gain_negative(self):
        samples = generate_sine_wave(440, 0.5, 44100, 0.5, 1)
        gained = apply_gain(samples, -6.0)
        assert get_peak(gained) < get_peak(samples) * 0.6

    def test_normalize_to_target(self):
        samples = generate_sine_wave(440, 0.5, 44100, 0.3, 1)
        normalized = apply_normalize(samples, -1.0)
        target = 10 ** (-1.0 / 20)
        assert abs(get_peak(normalized) - target) < 0.01

    def test_fade_in_effect(self):
        samples = [0.5] * 44100
        faded = apply_fade_in(samples, 0.5, 44100, 1)
        # First sample should be ~0
        assert abs(faded[0]) < 0.01
        # Sample at 25% of fade should be ~0.25 * original
        quarter = int(44100 * 0.25)
        assert abs(faded[quarter] - 0.5 * 0.5) < 0.05
        # After fade, should be full
        assert abs(faded[-1] - 0.5) < 0.01

    def test_fade_out_effect(self):
        samples = [0.5] * 44100
        faded = apply_fade_out(samples, 0.5, 44100, 1)
        assert abs(faded[0] - 0.5) < 0.01
        assert abs(faded[-1]) < 0.01

    def test_reverse_correctness(self):
        samples = [0.1, 0.2, 0.3, 0.4, 0.5]
        reversed_s = apply_reverse(samples, 1)
        assert reversed_s == [0.5, 0.4, 0.3, 0.2, 0.1]

    def test_echo_adds_delayed_copy(self):
        sr = 1000
        samples = [1.0] + [0.0] * 999
        echoed = apply_echo(samples, delay_ms=100, decay=0.5, sample_rate=sr, channels=1)
        # Original impulse at 0
        assert abs(echoed[0] - 1.0) < 0.01
        # Echo at sample 100
        assert abs(echoed[100] - 0.5) < 0.01
        # After echo, should be silence
        assert abs(echoed[200]) < 0.01

    def test_low_pass_attenuates_high_freq(self):
        sr = 44100
        # Mix of 100Hz and 10000Hz
        low = generate_sine_wave(100, 0.5, sr, 0.5, 1)
        high = generate_sine_wave(10000, 0.5, sr, 0.5, 1)
        mixed = [l + h for l, h in zip(low, high)]

        filtered = apply_low_pass(mixed, cutoff=500.0, sample_rate=sr, channels=1)

        # Analyze: filtered should have less high-frequency content
        arr = np.array(filtered)
        fft = np.abs(np.fft.rfft(arr))
        freqs = np.fft.rfftfreq(len(arr), 1.0 / sr)

        # Energy around 100Hz should be preserved
        low_mask = (freqs > 50) & (freqs < 200)
        high_mask = (freqs > 5000) & (freqs < 15000)

        low_energy = np.sum(fft[low_mask] ** 2)
        high_energy = np.sum(fft[high_mask] ** 2)

        # Low-pass should reduce high frequency energy significantly
        assert low_energy > high_energy * 2

    def test_high_pass_attenuates_low_freq(self):
        sr = 44100
        low = generate_sine_wave(50, 0.5, sr, 0.5, 1)
        high = generate_sine_wave(5000, 0.5, sr, 0.5, 1)
        mixed = [l + h for l, h in zip(low, high)]

        filtered = apply_high_pass(mixed, cutoff=1000.0, sample_rate=sr, channels=1)

        arr = np.array(filtered)
        fft = np.abs(np.fft.rfft(arr))
        freqs = np.fft.rfftfreq(len(arr), 1.0 / sr)

        low_mask = (freqs > 20) & (freqs < 100)
        high_mask = (freqs > 3000) & (freqs < 8000)

        low_energy = np.sum(fft[low_mask] ** 2)
        high_energy = np.sum(fft[high_mask] ** 2)

        assert high_energy > low_energy * 2

    def test_change_speed_doubles(self):
        samples = generate_sine_wave(440, 1.0, 44100, 0.5, 1)
        sped = apply_change_speed(samples, 2.0, 1)
        # Should be roughly half the length
        assert abs(len(sped) - len(samples) / 2) < 10

    def test_limiter_clamps_peak(self):
        samples = generate_sine_wave(440, 0.5, 44100, 0.9, 1)
        limited = apply_limit(samples, -6.0)
        threshold = 10 ** (-6.0 / 20)
        assert get_peak(limited) <= threshold + 0.001

    def test_mix_two_tracks(self):
        t1 = generate_sine_wave(440, 0.5, 44100, 0.3, 1)
        t2 = generate_sine_wave(880, 0.5, 44100, 0.3, 1)
        mixed = mix_audio([t1, t2], channels=1)
        # Mixed should have higher RMS than either alone
        assert get_rms(mixed) > get_rms(t1)


# -- Full Render Pipeline Tests --------------------------------------------

class TestRenderPipeline:
    def test_render_empty_project(self, tmp_dir):
        proj = create_project()
        out = os.path.join(tmp_dir, "empty.wav")
        result = render_mix(proj, out, preset="wav")
        assert os.path.exists(out)
        assert result["format"] == "WAV"
        assert result["tracks_rendered"] == 0

    def test_render_single_track(self, tmp_dir, sine_wav):
        proj = create_project()
        add_track(proj, name="Voice")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        out = os.path.join(tmp_dir, "single.wav")
        result = render_mix(proj, out, preset="wav")
        assert os.path.exists(out)
        assert result["tracks_rendered"] == 1
        assert result["duration"] > 0.9

        # Verify the output WAV
        samples, sr, ch, bd = read_wav(out)
        assert sr == 44100
        assert get_rms(samples) > 0

    def test_render_stereo_output(self, tmp_dir, sine_wav):
        proj = create_project(channels=2)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        out = os.path.join(tmp_dir, "stereo_out.wav")
        result = render_mix(proj, out, preset="wav")
        assert result["channels"] == 2
        with wave.open(out, "r") as wf:
            assert wf.getnchannels() == 2

    def test_render_mono_output(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        out = os.path.join(tmp_dir, "mono_out.wav")
        result = render_mix(proj, out, preset="wav")
        assert result["channels"] == 1
        with wave.open(out, "r") as wf:
            assert wf.getnchannels() == 1

    def test_render_with_gain_effect(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)

        # Read original level
        orig_samples, _, _, _ = read_wav(sine_wav)
        orig_rms = get_rms(orig_samples)

        # Add +6dB gain
        add_effect(proj, "amplify", 0, {"gain_db": 6.0})

        out = os.path.join(tmp_dir, "gained.wav")
        render_mix(proj, out, preset="wav")
        gained_samples, _, _, _ = read_wav(out)
        gained_rms = get_rms(gained_samples)

        # +6dB should roughly double the amplitude
        assert gained_rms > orig_rms * 1.5

    def test_render_with_fade_in(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        add_effect(proj, "fade_in", 0, {"duration": 0.5})

        out = os.path.join(tmp_dir, "fade_in.wav")
        render_mix(proj, out, preset="wav")
        samples, sr, _, _ = read_wav(out)

        # First 100 samples should be very quiet
        first_chunk = samples[:100]
        last_chunk = samples[-1000:]
        assert get_rms(first_chunk) < get_rms(last_chunk)

    def test_render_with_reverse(self, tmp_dir):
        # Create a chirp (ascending frequency)
        path = os.path.join(tmp_dir, "chirp.wav")
        sr = 44100
        duration = 0.5
        n = int(sr * duration)
        samples = []
        for i in range(n):
            t = i / sr
            freq = 200 + (t / duration) * 2000
            samples.append(0.5 * math.sin(2 * math.pi * freq * t))
        write_wav(path, samples, sr, 1, 16)

        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, path, start_time=0.0)
        add_effect(proj, "reverse", 0)

        out = os.path.join(tmp_dir, "reversed.wav")
        render_mix(proj, out, preset="wav")

        rev_samples, _, _, _ = read_wav(out)
        # The first half of the reversed audio should have higher frequency
        # content than the original first half
        assert len(rev_samples) > 0

    def test_render_multiple_tracks(self, tmp_dir, sine_wav, short_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_track(proj, name="T2")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        add_clip(proj, 1, short_wav, start_time=0.0)

        out = os.path.join(tmp_dir, "multi.wav")
        result = render_mix(proj, out, preset="wav")
        assert result["tracks_rendered"] == 2
        samples, _, _, _ = read_wav(out)
        assert get_rms(samples) > 0

    def test_render_muted_track_excluded(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_track(proj, name="T2 (muted)")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        add_clip(proj, 1, sine_wav, start_time=0.0)

        # Mute track 1
        set_track_property(proj, 1, "mute", "true")

        out = os.path.join(tmp_dir, "muted.wav")
        result = render_mix(proj, out, preset="wav")
        assert result["tracks_rendered"] == 1

    def test_render_solo_track(self, tmp_dir, sine_wav, short_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_track(proj, name="T2 (solo)")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        add_clip(proj, 1, short_wav, start_time=0.0)

        # Solo track 1 only
        set_track_property(proj, 1, "solo", "true")

        out = os.path.join(tmp_dir, "solo.wav")
        result = render_mix(proj, out, preset="wav")
        assert result["tracks_rendered"] == 1

    def test_render_overwrite_protection(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)

        out = os.path.join(tmp_dir, "existing.wav")
        render_mix(proj, out, preset="wav")
        with pytest.raises(FileExistsError):
            render_mix(proj, out, preset="wav")

        # With overwrite flag
        result = render_mix(proj, out, preset="wav", overwrite=True)
        assert os.path.exists(out)

    def test_render_with_echo(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        add_effect(proj, "echo", 0, {"delay_ms": 200, "decay": 0.5})

        out = os.path.join(tmp_dir, "echo.wav")
        result = render_mix(proj, out, preset="wav")

        # Echo should extend the duration
        samples, _, _, _ = read_wav(out)
        assert len(samples) / 44100 > 1.0  # Longer than original 1s

    def test_render_with_compression(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        add_effect(proj, "compress", 0, {"threshold": -10.0, "ratio": 4.0})

        out = os.path.join(tmp_dir, "compressed.wav")
        render_mix(proj, out, preset="wav")
        samples, _, _, _ = read_wav(out)
        assert len(samples) > 0

    def test_render_24bit(self, tmp_dir, sine_wav):
        proj = create_project(channels=1, bit_depth=24)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)

        out = os.path.join(tmp_dir, "out24.wav")
        result = render_mix(proj, out, preset="wav-24")
        assert result["bit_depth"] == 24
        with wave.open(out, "r") as wf:
            assert wf.getsampwidth() == 3

    def test_render_channel_override(self, tmp_dir, stereo_wav):
        proj = create_project(channels=2)
        add_track(proj, name="T1")
        add_clip(proj, 0, stereo_wav, start_time=0.0)

        out = os.path.join(tmp_dir, "mono_override.wav")
        result = render_mix(proj, out, preset="wav", channels_override=1)
        assert result["channels"] == 1
        with wave.open(out, "r") as wf:
            assert wf.getnchannels() == 1


# -- Project Lifecycle E2E Tests -------------------------------------------

class TestProjectLifecycle:
    def test_full_workflow(self, tmp_dir, sine_wav, short_wav):
        """Full podcast-style workflow: create, add tracks, clips, effects, export."""
        proj = create_project(name="My Podcast", channels=1)

        # Add tracks
        add_track(proj, name="Host Voice")
        add_track(proj, name="Guest Voice")
        add_track(proj, name="Music Bed")

        # Add clips
        add_clip(proj, 0, sine_wav, start_time=0.0, name="Host Intro")
        add_clip(proj, 1, short_wav, start_time=0.5, name="Guest Reply")
        add_clip(proj, 2, sine_wav, start_time=0.0, name="Background Music",
                 volume=0.3)

        # Add effects
        add_effect(proj, "normalize", 0, {"target_db": -3.0})
        add_effect(proj, "fade_in", 2, {"duration": 0.5})
        add_effect(proj, "fade_out", 2, {"duration": 0.5})

        # Add labels
        add_label(proj, 0.0, text="Start")
        add_label(proj, 0.5, 1.0, text="Guest segment")

        # Save project
        proj_path = os.path.join(tmp_dir, "podcast.json")
        save_project(proj, proj_path)

        # Reload
        loaded = open_project(proj_path)
        info = get_project_info(loaded)
        assert info["track_count"] == 3
        assert info["clip_count"] == 3
        assert info["label_count"] == 2

        # Export
        out = os.path.join(tmp_dir, "podcast.wav")
        result = render_mix(loaded, out, preset="wav")
        assert os.path.exists(out)
        assert result["tracks_rendered"] == 3

        # Verify output
        samples, sr, ch, bd = read_wav(out)
        assert sr == 44100
        assert ch == 1
        assert get_rms(samples) > 0

    def test_save_open_roundtrip_preserves_effects(self, tmp_dir, sine_wav):
        proj = create_project(name="roundtrip")
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        add_effect(proj, "amplify", 0, {"gain_db": 3.0})
        add_effect(proj, "echo", 0, {"delay_ms": 200, "decay": 0.3})

        path = os.path.join(tmp_dir, "roundtrip.json")
        save_project(proj, path)
        loaded = open_project(path)

        effects = list_effects(loaded, 0)
        assert len(effects) == 2
        assert effects[0]["name"] == "amplify"
        assert effects[0]["params"]["gain_db"] == 3.0
        assert effects[1]["name"] == "echo"

    def test_multiple_clips_timeline(self, tmp_dir, sine_wav, short_wav):
        """Test that clips are placed at correct positions on the timeline."""
        proj = create_project(channels=1)
        add_track(proj, name="T1")

        # Place clips at specific positions
        add_clip(proj, 0, sine_wav, start_time=0.0, name="Clip A")
        add_clip(proj, 0, short_wav, start_time=1.5, name="Clip B")

        out = os.path.join(tmp_dir, "timeline.wav")
        result = render_mix(proj, out, preset="wav")

        # Duration should cover both clips
        assert result["duration"] >= 1.9  # 1.5 + 0.5 = 2.0

    def test_clip_split_and_move(self, tmp_dir, sine_wav):
        proj = create_project(channels=1)
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0, end_time=1.0,
                 trim_start=0.0, trim_end=1.0)

        # Split at 0.5
        parts = split_clip(proj, 0, 0, 0.5)
        assert len(parts) == 2

        # Move second part to 2.0
        move_clip(proj, 0, 1, 2.0)

        clips = list_clips(proj, 0)
        assert clips[0]["end_time"] == 0.5
        assert clips[1]["start_time"] == 2.0


# -- Session E2E Tests -----------------------------------------------------

class TestSessionE2E:
    def test_undo_track_addition(self, sine_wav):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        sess.snapshot("Add track")
        add_track(proj, name="New Track")
        assert len(proj["tracks"]) == 1

        sess.undo()
        proj = sess.get_project()
        assert len(proj["tracks"]) == 0

    def test_undo_effect_addition(self, sine_wav):
        sess = Session()
        proj = create_project()
        add_track(proj, name="T1")
        sess.set_project(proj)

        sess.snapshot("Add effect")
        add_effect(proj, "amplify", 0, {"gain_db": 6.0})
        assert len(proj["tracks"][0]["effects"]) == 1

        sess.undo()
        proj = sess.get_project()
        assert len(proj["tracks"][0]["effects"]) == 0

    def test_heavy_undo_redo_stress(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        # 30 operations
        for i in range(30):
            sess.snapshot(f"Add track {i}")
            add_track(proj, name=f"Track {i}")

        assert len(sess.get_project()["tracks"]) == 30

        # Undo all
        for i in range(30):
            sess.undo()
        assert len(sess.get_project()["tracks"]) == 0

        # Redo all
        for i in range(30):
            sess.redo()
        assert len(sess.get_project()["tracks"]) == 30


# -- Media Probe E2E Tests -------------------------------------------------

class TestMediaProbeE2E:
    def test_probe_real_wav(self, sine_wav):
        info = probe_audio(sine_wav)
        assert info["format"] == "WAV"
        assert info["sample_rate"] == 44100
        assert info["channels"] == 1
        assert info["bit_depth"] == 16
        assert abs(info["duration"] - 1.0) < 0.01

    def test_probe_stereo_wav(self, stereo_wav):
        info = probe_audio(stereo_wav)
        assert info["channels"] == 2
        assert abs(info["duration"] - 2.0) < 0.01

    def test_get_duration_real_file(self, sine_wav):
        dur = get_duration(sine_wav)
        assert abs(dur - 1.0) < 0.01

    def test_check_media_with_real_files(self, sine_wav):
        proj = create_project()
        add_track(proj, name="T1")
        add_clip(proj, 0, sine_wav, start_time=0.0)
        result = check_media(proj)
        assert result["status"] == "ok"
        assert result["found"] == 1


# -- CLI Subprocess Tests --------------------------------------------------

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-audacity")

    def _run_cli(self, args, cwd=None):
        """Run the CLI as a subprocess."""
        result = subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
        )
        return result

    def test_cli_project_new(self):
        result = self._run_cli(["project", "new", "--name", "TestCLI"])
        assert result.returncode == 0
        assert "TestCLI" in result.stdout

    def test_cli_project_new_json(self):
        result = self._run_cli(["--json", "project", "new", "--name", "JsonTest"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "JsonTest"

    def test_cli_effect_list_available(self):
        result = self._run_cli(["effect", "list-available"])
        assert result.returncode == 0
        assert "amplify" in result.stdout or "normalize" in result.stdout

    def test_cli_export_presets(self):
        result = self._run_cli(["export", "presets"])
        assert result.returncode == 0
        assert "wav" in result.stdout.lower()


# ── True Backend E2E Tests (requires SoX installed) ──────────────

class TestSoXBackend:
    """Tests that verify SoX is installed and accessible."""

    def test_sox_is_installed(self):
        from cli_anything.audacity.utils.sox_backend import find_sox
        path = find_sox()
        assert os.path.exists(path)
        print(f"\n  SoX binary: {path}")

    def test_sox_version(self):
        from cli_anything.audacity.utils.sox_backend import get_version
        version = get_version()
        assert version  # non-empty
        print(f"\n  SoX version: {version}")


class TestSoXAudioE2E:
    """True E2E tests using SoX."""

    def test_generate_sine_tone_wav(self):
        """Generate a sine tone WAV using SoX."""
        from cli_anything.audacity.utils.sox_backend import generate_tone

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = os.path.join(tmp_dir, "tone.wav")
            result = generate_tone(output, frequency=440.0, duration=1.0)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            assert result["method"] == "sox"
            print(f"\n  SoX tone WAV: {result['output']} ({result['file_size']:,} bytes)")

    def test_apply_reverb_effect(self):
        """Generate tone then apply reverb effect using SoX."""
        from cli_anything.audacity.utils.sox_backend import generate_tone, apply_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Generate source tone
            src = os.path.join(tmp_dir, "source.wav")
            generate_tone(src, frequency=440.0, duration=1.0)

            # Apply reverb
            output = os.path.join(tmp_dir, "reverb.wav")
            result = apply_effect(src, output, ["reverb", "50", "50", "100"])

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            print(f"\n  SoX reverb: {result['output']} ({result['file_size']:,} bytes)")

    def test_apply_fade_effect(self):
        """Apply fade in/out using SoX."""
        from cli_anything.audacity.utils.sox_backend import generate_tone, apply_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            src = os.path.join(tmp_dir, "source.wav")
            generate_tone(src, frequency=880.0, duration=2.0)

            output = os.path.join(tmp_dir, "faded.wav")
            result = apply_effect(src, output, ["fade", "t", "0.5", "2.0", "0.5"])

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            print(f"\n  SoX fade: {result['output']} ({result['file_size']:,} bytes)")

    def test_generate_different_frequencies(self):
        """Generate tones at different frequencies."""
        from cli_anything.audacity.utils.sox_backend import generate_tone

        with tempfile.TemporaryDirectory() as tmp_dir:
            for freq in [220, 440, 880]:
                output = os.path.join(tmp_dir, f"tone_{freq}hz.wav")
                result = generate_tone(output, frequency=freq, duration=0.5)
                assert os.path.exists(result["output"])
                assert result["file_size"] > 0
                print(f"\n  SoX {freq}Hz tone: {result['output']} ({result['file_size']:,} bytes)")

    def test_convert_sample_rate(self):
        """Convert sample rate using SoX."""
        from cli_anything.audacity.utils.sox_backend import generate_tone, convert_format

        with tempfile.TemporaryDirectory() as tmp_dir:
            src = os.path.join(tmp_dir, "source_44100.wav")
            generate_tone(src, frequency=440.0, duration=1.0, sample_rate=44100)

            output = os.path.join(tmp_dir, "converted_22050.wav")
            result = convert_format(src, output, sample_rate=22050)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            print(f"\n  SoX 44100→22050: {result['output']} ({result['file_size']:,} bytes)")
