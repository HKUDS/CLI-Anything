"""Unit tests for Audacity CLI core modules.

Tests use synthetic data only — no real audio files or external dependencies
beyond stdlib. 60+ tests covering all core modules.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.audacity.core.project import (
    create_project, open_project, save_project, get_project_info, set_settings,
)
from cli_anything.audacity.core.tracks import (
    add_track, remove_track, get_track, set_track_property, list_tracks,
)
from cli_anything.audacity.core.clips import (
    add_clip, remove_clip, trim_clip, split_clip, move_clip, list_clips,
)
from cli_anything.audacity.core.effects import (
    EFFECT_REGISTRY, list_available, get_effect_info, validate_params,
    add_effect, remove_effect, set_effect_param, list_effects,
)
from cli_anything.audacity.core.labels import add_label, remove_label, list_labels
from cli_anything.audacity.core.selection import set_selection, select_all, select_none, get_selection
from cli_anything.audacity.core.session import Session
from cli_anything.audacity.core.media import probe_audio, check_media, get_duration
from cli_anything.audacity.core.export import list_presets, get_preset_info, EXPORT_PRESETS
from cli_anything.audacity.utils.audio_utils import (
    generate_sine_wave, generate_silence, mix_audio, apply_gain,
    apply_fade_in, apply_fade_out, apply_reverse, apply_echo,
    apply_low_pass, apply_high_pass, apply_normalize, apply_change_speed,
    apply_limit, clamp_samples, write_wav, read_wav, get_rms, get_peak,
    db_from_linear,
)


# -- Project Tests ---------------------------------------------------------

class TestProject:
    def test_create_default(self):
        proj = create_project()
        assert proj["settings"]["sample_rate"] == 44100
        assert proj["settings"]["bit_depth"] == 16
        assert proj["settings"]["channels"] == 2
        assert proj["version"] == "1.0"
        assert proj["name"] == "untitled"

    def test_create_with_name(self):
        proj = create_project(name="My Podcast")
        assert proj["name"] == "My Podcast"

    def test_create_with_custom_settings(self):
        proj = create_project(sample_rate=48000, bit_depth=24, channels=1)
        assert proj["settings"]["sample_rate"] == 48000
        assert proj["settings"]["bit_depth"] == 24
        assert proj["settings"]["channels"] == 1

    def test_create_invalid_sample_rate(self):
        with pytest.raises(ValueError, match="Invalid sample rate"):
            create_project(sample_rate=12345)

    def test_create_invalid_bit_depth(self):
        with pytest.raises(ValueError, match="Invalid bit depth"):
            create_project(bit_depth=20)

    def test_create_invalid_channels(self):
        with pytest.raises(ValueError, match="Invalid channel count"):
            create_project(channels=5)

    def test_save_and_open(self):
        proj = create_project(name="test_project")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)
            assert loaded["name"] == "test_project"
            assert loaded["settings"]["sample_rate"] == 44100
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            open_project("/nonexistent/path.json")

    def test_open_invalid(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"foo": "bar"}, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="Invalid project"):
                open_project(path)
        finally:
            os.unlink(path)

    def test_get_info(self):
        proj = create_project(name="info_test")
        info = get_project_info(proj)
        assert info["name"] == "info_test"
        assert info["track_count"] == 0
        assert info["clip_count"] == 0
        assert "settings" in info

    def test_set_settings(self):
        proj = create_project()
        result = set_settings(proj, sample_rate=48000)
        assert result["sample_rate"] == 48000
        assert proj["settings"]["sample_rate"] == 48000

    def test_set_settings_invalid(self):
        proj = create_project()
        with pytest.raises(ValueError):
            set_settings(proj, sample_rate=99999)


# -- Track Tests -----------------------------------------------------------

class TestTracks:
    def _make_project(self):
        return create_project()

    def test_add_track(self):
        proj = self._make_project()
        track = add_track(proj, name="Voice")
        assert track["name"] == "Voice"
        assert track["type"] == "audio"
        assert len(proj["tracks"]) == 1

    def test_add_track_default_name(self):
        proj = self._make_project()
        track = add_track(proj)
        assert track["name"] == "Track 0"

    def test_add_multiple_tracks(self):
        proj = self._make_project()
        add_track(proj, name="Track A")
        add_track(proj, name="Track B")
        add_track(proj, name="Track C")
        assert len(proj["tracks"]) == 3

    def test_add_track_with_volume_pan(self):
        proj = self._make_project()
        track = add_track(proj, volume=0.8, pan=-0.5)
        assert track["volume"] == 0.8
        assert track["pan"] == -0.5

    def test_add_track_invalid_volume(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Volume"):
            add_track(proj, volume=3.0)

    def test_add_track_invalid_pan(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Pan"):
            add_track(proj, pan=2.0)

    def test_add_track_invalid_type(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid track type"):
            add_track(proj, track_type="video")

    def test_remove_track(self):
        proj = self._make_project()
        add_track(proj, name="To Remove")
        removed = remove_track(proj, 0)
        assert removed["name"] == "To Remove"
        assert len(proj["tracks"]) == 0

    def test_remove_track_out_of_range(self):
        proj = self._make_project()
        with pytest.raises(IndexError):
            remove_track(proj, 0)

    def test_get_track(self):
        proj = self._make_project()
        add_track(proj, name="Test")
        track = get_track(proj, 0)
        assert track["name"] == "Test"

    def test_set_track_name(self):
        proj = self._make_project()
        add_track(proj, name="Old")
        set_track_property(proj, 0, "name", "New")
        assert proj["tracks"][0]["name"] == "New"

    def test_set_track_mute(self):
        proj = self._make_project()
        add_track(proj)
        set_track_property(proj, 0, "mute", "true")
        assert proj["tracks"][0]["mute"] is True

    def test_set_track_solo(self):
        proj = self._make_project()
        add_track(proj)
        set_track_property(proj, 0, "solo", "true")
        assert proj["tracks"][0]["solo"] is True

    def test_set_track_volume(self):
        proj = self._make_project()
        add_track(proj)
        set_track_property(proj, 0, "volume", "0.5")
        assert proj["tracks"][0]["volume"] == 0.5

    def test_set_track_invalid_prop(self):
        proj = self._make_project()
        add_track(proj)
        with pytest.raises(ValueError, match="Unknown track property"):
            set_track_property(proj, 0, "color", "red")

    def test_list_tracks(self):
        proj = self._make_project()
        add_track(proj, name="A")
        add_track(proj, name="B")
        tracks = list_tracks(proj)
        assert len(tracks) == 2
        assert tracks[0]["name"] == "A"
        assert tracks[1]["name"] == "B"


# -- Clip Tests ------------------------------------------------------------

class TestClips:
    def _make_project_with_track(self):
        proj = create_project()
        add_track(proj, name="Track 1")
        return proj

    def test_add_clip(self):
        proj = self._make_project_with_track()
        clip = add_clip(proj, 0, "/fake/audio.wav", name="Test Clip",
                        start_time=0.0, end_time=10.0)
        assert clip["name"] == "Test Clip"
        assert clip["start_time"] == 0.0
        assert clip["end_time"] == 10.0

    def test_add_clip_auto_name(self):
        proj = self._make_project_with_track()
        clip = add_clip(proj, 0, "/fake/recording.wav",
                        start_time=0.0, end_time=5.0)
        assert clip["name"] == "recording"

    def test_add_clip_out_of_range(self):
        proj = self._make_project_with_track()
        with pytest.raises(IndexError):
            add_clip(proj, 5, "/fake/audio.wav", start_time=0.0, end_time=1.0)

    def test_add_clip_invalid_times(self):
        proj = self._make_project_with_track()
        with pytest.raises(ValueError):
            add_clip(proj, 0, "/fake/audio.wav",
                     start_time=10.0, end_time=5.0)

    def test_remove_clip(self):
        proj = self._make_project_with_track()
        add_clip(proj, 0, "/fake/audio.wav", name="Remove Me",
                 start_time=0.0, end_time=5.0)
        removed = remove_clip(proj, 0, 0)
        assert removed["name"] == "Remove Me"
        assert len(proj["tracks"][0]["clips"]) == 0

    def test_remove_clip_out_of_range(self):
        proj = self._make_project_with_track()
        with pytest.raises(IndexError):
            remove_clip(proj, 0, 0)

    def test_split_clip(self):
        proj = self._make_project_with_track()
        add_clip(proj, 0, "/fake/audio.wav", name="Full",
                 start_time=0.0, end_time=10.0, trim_start=0.0, trim_end=10.0)
        parts = split_clip(proj, 0, 0, 5.0)
        assert len(parts) == 2
        assert parts[0]["end_time"] == 5.0
        assert parts[1]["start_time"] == 5.0
        assert len(proj["tracks"][0]["clips"]) == 2

    def test_split_clip_invalid_time(self):
        proj = self._make_project_with_track()
        add_clip(proj, 0, "/fake/audio.wav", start_time=0.0, end_time=10.0)
        with pytest.raises(ValueError, match="Split time"):
            split_clip(proj, 0, 0, 0.0)
        with pytest.raises(ValueError, match="Split time"):
            split_clip(proj, 0, 0, 15.0)

    def test_move_clip(self):
        proj = self._make_project_with_track()
        add_clip(proj, 0, "/fake/audio.wav", start_time=0.0, end_time=5.0)
        result = move_clip(proj, 0, 0, 10.0)
        assert result["start_time"] == 10.0
        assert result["end_time"] == 15.0

    def test_move_clip_negative(self):
        proj = self._make_project_with_track()
        add_clip(proj, 0, "/fake/audio.wav", start_time=5.0, end_time=10.0)
        with pytest.raises(ValueError):
            move_clip(proj, 0, 0, -1.0)

    def test_trim_clip(self):
        proj = self._make_project_with_track()
        add_clip(proj, 0, "/fake/audio.wav", name="Trim",
                 start_time=0.0, end_time=10.0, trim_start=0.0, trim_end=10.0)
        result = trim_clip(proj, 0, 0, trim_end=8.0)
        assert result["trim_end"] == 8.0

    def test_list_clips(self):
        proj = self._make_project_with_track()
        add_clip(proj, 0, "/fake/a.wav", name="A", start_time=0.0, end_time=5.0)
        add_clip(proj, 0, "/fake/b.wav", name="B", start_time=5.0, end_time=10.0)
        clips = list_clips(proj, 0)
        assert len(clips) == 2
        assert clips[0]["name"] == "A"
        assert clips[1]["name"] == "B"


# -- Effect Tests ----------------------------------------------------------

class TestEffects:
    def _make_project_with_track(self):
        proj = create_project()
        add_track(proj, name="FX Track")
        return proj

    def test_list_available(self):
        effects = list_available()
        assert len(effects) > 10
        names = [e["name"] for e in effects]
        assert "amplify" in names
        assert "normalize" in names
        assert "echo" in names

    def test_list_available_by_category(self):
        effects = list_available("volume")
        assert all(e["category"] == "volume" for e in effects)
        assert len(effects) >= 2

    def test_get_effect_info(self):
        info = get_effect_info("amplify")
        assert info["name"] == "amplify"
        assert "gain_db" in info["params"]

    def test_get_effect_info_unknown(self):
        with pytest.raises(ValueError, match="Unknown effect"):
            get_effect_info("nonexistent_effect")

    def test_validate_params_defaults(self):
        result = validate_params("amplify", {})
        assert result["gain_db"] == 0.0

    def test_validate_params_custom(self):
        result = validate_params("amplify", {"gain_db": 6.0})
        assert result["gain_db"] == 6.0

    def test_validate_params_out_of_range(self):
        with pytest.raises(ValueError, match="maximum"):
            validate_params("amplify", {"gain_db": 100.0})

    def test_validate_params_unknown(self):
        with pytest.raises(ValueError, match="Unknown parameters"):
            validate_params("amplify", {"unknown_param": 5})

    def test_add_effect(self):
        proj = self._make_project_with_track()
        result = add_effect(proj, "normalize", 0, {"target_db": -3.0})
        assert result["name"] == "normalize"
        assert result["params"]["target_db"] == -3.0
        assert len(proj["tracks"][0]["effects"]) == 1

    def test_add_effect_unknown(self):
        proj = self._make_project_with_track()
        with pytest.raises(ValueError, match="Unknown effect"):
            add_effect(proj, "nonexistent", 0)

    def test_add_effect_out_of_range(self):
        proj = self._make_project_with_track()
        with pytest.raises(IndexError):
            add_effect(proj, "amplify", 5)

    def test_remove_effect(self):
        proj = self._make_project_with_track()
        add_effect(proj, "amplify", 0, {"gain_db": 3.0})
        removed = remove_effect(proj, 0, 0)
        assert removed["name"] == "amplify"
        assert len(proj["tracks"][0]["effects"]) == 0

    def test_remove_effect_out_of_range(self):
        proj = self._make_project_with_track()
        with pytest.raises(IndexError):
            remove_effect(proj, 0, 0)

    def test_set_effect_param(self):
        proj = self._make_project_with_track()
        add_effect(proj, "echo", 0, {"delay_ms": 300, "decay": 0.4})
        set_effect_param(proj, 0, "delay_ms", 600.0, 0)
        assert proj["tracks"][0]["effects"][0]["params"]["delay_ms"] == 600.0

    def test_set_effect_param_unknown(self):
        proj = self._make_project_with_track()
        add_effect(proj, "amplify", 0)
        with pytest.raises(ValueError, match="Unknown parameter"):
            set_effect_param(proj, 0, "fake_param", 5.0, 0)

    def test_list_effects(self):
        proj = self._make_project_with_track()
        add_effect(proj, "normalize", 0)
        add_effect(proj, "compress", 0)
        effects = list_effects(proj, 0)
        assert len(effects) == 2
        assert effects[0]["name"] == "normalize"
        assert effects[1]["name"] == "compress"

    def test_all_effects_have_valid_params(self):
        """Ensure every effect in the registry has valid param specs."""
        for name, info in EFFECT_REGISTRY.items():
            assert "params" in info, f"Effect {name} missing params"
            assert "category" in info, f"Effect {name} missing category"
            assert "description" in info, f"Effect {name} missing description"
            # Validate defaults pass validation
            result = validate_params(name, {})
            assert isinstance(result, dict)


# -- Label Tests -----------------------------------------------------------

class TestLabels:
    def _make_project(self):
        return create_project()

    def test_add_label_point(self):
        proj = self._make_project()
        label = add_label(proj, 5.0, text="Intro")
        assert label["start"] == 5.0
        assert label["end"] == 5.0
        assert label["text"] == "Intro"

    def test_add_label_range(self):
        proj = self._make_project()
        label = add_label(proj, 5.0, 10.0, "Chorus")
        assert label["start"] == 5.0
        assert label["end"] == 10.0

    def test_add_label_invalid_start(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="start must be >= 0"):
            add_label(proj, -1.0)

    def test_add_label_invalid_range(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="end.*must be >= start"):
            add_label(proj, 10.0, 5.0)

    def test_remove_label(self):
        proj = self._make_project()
        add_label(proj, 1.0, text="Remove")
        removed = remove_label(proj, 0)
        assert removed["text"] == "Remove"
        assert len(proj["labels"]) == 0

    def test_remove_label_out_of_range(self):
        proj = self._make_project()
        with pytest.raises(IndexError):
            remove_label(proj, 0)

    def test_list_labels(self):
        proj = self._make_project()
        add_label(proj, 0.0, text="Start")
        add_label(proj, 5.0, 10.0, "Middle")
        add_label(proj, 15.0, text="End")
        labels = list_labels(proj)
        assert len(labels) == 3
        assert labels[0]["type"] == "point"
        assert labels[1]["type"] == "range"
        assert labels[1]["duration"] == 5.0


# -- Selection Tests -------------------------------------------------------

class TestSelection:
    def _make_project(self):
        return create_project()

    def test_set_selection(self):
        proj = self._make_project()
        result = set_selection(proj, 2.0, 8.0)
        assert result["start"] == 2.0
        assert result["end"] == 8.0

    def test_set_selection_invalid(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="start must be >= 0"):
            set_selection(proj, -1.0, 5.0)
        with pytest.raises(ValueError, match="end.*must be >= start"):
            set_selection(proj, 10.0, 5.0)

    def test_select_all_empty(self):
        proj = self._make_project()
        result = select_all(proj)
        assert result["end"] == 0.0

    def test_select_all_with_clips(self):
        proj = self._make_project()
        add_track(proj, name="T1")
        add_clip(proj, 0, "/fake/a.wav", start_time=0.0, end_time=30.0)
        result = select_all(proj)
        assert result["start"] == 0.0
        assert result["end"] == 30.0

    def test_select_none(self):
        proj = self._make_project()
        set_selection(proj, 1.0, 5.0)
        result = select_none(proj)
        assert result["start"] == 0.0
        assert result["end"] == 0.0

    def test_get_selection(self):
        proj = self._make_project()
        set_selection(proj, 3.0, 7.0)
        result = get_selection(proj)
        assert result["start"] == 3.0
        assert result["end"] == 7.0
        assert result["duration"] == 4.0
        assert result["has_selection"] is True

    def test_get_selection_empty(self):
        proj = self._make_project()
        result = get_selection(proj)
        assert result["has_selection"] is False


# -- Session Tests ---------------------------------------------------------

class TestSession:
    def test_no_project(self):
        sess = Session()
        assert not sess.has_project()
        with pytest.raises(RuntimeError, match="No project loaded"):
            sess.get_project()

    def test_set_project(self):
        sess = Session()
        proj = create_project(name="test")
        sess.set_project(proj)
        assert sess.has_project()
        assert sess.get_project()["name"] == "test"

    def test_undo_empty(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)
        with pytest.raises(RuntimeError, match="Nothing to undo"):
            sess.undo()

    def test_redo_empty(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)
        with pytest.raises(RuntimeError, match="Nothing to redo"):
            sess.redo()

    def test_undo_redo_cycle(self):
        sess = Session()
        proj = create_project(name="original")
        sess.set_project(proj)

        sess.snapshot("Rename")
        proj["name"] = "changed"
        assert sess.get_project()["name"] == "changed"

        sess.undo()
        assert sess.get_project()["name"] == "original"

        sess.redo()
        assert sess.get_project()["name"] == "changed"

    def test_multiple_undos(self):
        sess = Session()
        proj = create_project(name="v0")
        sess.set_project(proj)

        sess.snapshot("v1")
        proj["name"] = "v1"
        sess.snapshot("v2")
        proj["name"] = "v2"
        sess.snapshot("v3")
        proj["name"] = "v3"

        assert sess.get_project()["name"] == "v3"
        sess.undo()
        assert sess.get_project()["name"] == "v2"
        sess.undo()
        assert sess.get_project()["name"] == "v1"
        sess.undo()
        assert sess.get_project()["name"] == "v0"

    def test_status(self):
        sess = Session()
        proj = create_project(name="status_test")
        sess.set_project(proj)
        status = sess.status()
        assert status["has_project"] is True
        assert status["project_name"] == "status_test"
        assert status["undo_count"] == 0

    def test_save_session(self):
        sess = Session()
        proj = create_project(name="save_test")
        sess.set_project(proj)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            saved = sess.save_session(path)
            assert os.path.exists(saved)
            loaded = open_project(saved)
            assert loaded["name"] == "save_test"
        finally:
            os.unlink(path)

    def test_save_session_no_path(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)
        with pytest.raises(ValueError, match="No save path"):
            sess.save_session()

    def test_list_history(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)
        sess.snapshot("Action 1")
        sess.snapshot("Action 2")
        history = sess.list_history()
        assert len(history) == 2
        assert history[0]["description"] == "Action 2"
        assert history[1]["description"] == "Action 1"

    def test_snapshot_clears_redo(self):
        sess = Session()
        proj = create_project(name="v0")
        sess.set_project(proj)
        sess.snapshot("v1")
        proj["name"] = "v1"
        sess.undo()
        # Now redo is available
        assert sess.status()["redo_count"] == 1
        # New snapshot should clear redo
        sess.snapshot("v2")
        assert sess.status()["redo_count"] == 0


# -- Audio Utility Tests ---------------------------------------------------

class TestAudioUtils:
    def test_generate_sine_wave(self):
        samples = generate_sine_wave(440, 0.1, 44100, 0.5, 1)
        assert len(samples) == 4410
        # Peak should be near 0.5
        assert max(abs(s) for s in samples) <= 0.51

    def test_generate_silence(self):
        samples = generate_silence(0.5, 44100, 1)
        assert len(samples) == 22050
        assert all(s == 0.0 for s in samples)

    def test_apply_gain(self):
        samples = [0.5, -0.5, 0.25]
        gained = apply_gain(samples, 6.0)
        # +6dB roughly doubles amplitude
        assert abs(gained[0] - 0.5 * 10 ** (6 / 20)) < 0.01

    def test_apply_fade_in(self):
        samples = [1.0] * 44100  # 1 second at 44100
        faded = apply_fade_in(samples, 0.5, 44100, 1)
        assert faded[0] == 0.0  # Start is silent
        assert abs(faded[-1] - 1.0) < 0.01  # End is unchanged

    def test_apply_fade_out(self):
        samples = [1.0] * 44100
        faded = apply_fade_out(samples, 0.5, 44100, 1)
        assert abs(faded[0] - 1.0) < 0.01  # Start unchanged
        assert abs(faded[-1]) < 0.01  # End is silent

    def test_apply_reverse(self):
        samples = [1.0, 2.0, 3.0, 4.0]
        reversed_s = apply_reverse(samples, 1)
        assert reversed_s == [4.0, 3.0, 2.0, 1.0]

    def test_apply_reverse_stereo(self):
        samples = [1.0, 2.0, 3.0, 4.0]  # 2 frames of stereo
        reversed_s = apply_reverse(samples, 2)
        assert reversed_s == [3.0, 4.0, 1.0, 2.0]

    def test_apply_echo(self):
        samples = [1.0] + [0.0] * 999
        echoed = apply_echo(samples, delay_ms=100, decay=0.5,
                           sample_rate=1000, channels=1)
        # Echo at sample 100
        assert abs(echoed[100] - 0.5) < 0.01

    def test_apply_normalize(self):
        samples = [0.25, -0.25, 0.1]
        normalized = apply_normalize(samples, -1.0)
        peak = max(abs(s) for s in normalized)
        target = 10 ** (-1.0 / 20)
        assert abs(peak - target) < 0.01

    def test_apply_change_speed(self):
        samples = list(range(100))
        sped_up = apply_change_speed([float(s) for s in samples], 2.0, 1)
        assert len(sped_up) == 50

    def test_apply_limit(self):
        samples = [1.0, -1.0, 0.5, -0.5]
        limited = apply_limit(samples, -6.0)
        threshold = 10 ** (-6.0 / 20)
        for s in limited:
            assert abs(s) <= threshold + 0.001

    def test_clamp_samples(self):
        samples = [2.0, -2.0, 0.5]
        clamped = clamp_samples(samples)
        assert clamped == [1.0, -1.0, 0.5]

    def test_mix_audio(self):
        track1 = [0.5] * 10
        track2 = [0.3] * 10
        mixed = mix_audio([track1, track2], channels=1)
        assert abs(mixed[0] - 0.8) < 0.01

    def test_get_rms(self):
        samples = [0.5] * 100
        rms = get_rms(samples)
        assert abs(rms - 0.5) < 0.01

    def test_get_peak(self):
        samples = [0.3, -0.7, 0.5]
        assert get_peak(samples) == 0.7

    def test_db_from_linear(self):
        assert abs(db_from_linear(1.0)) < 0.01
        assert abs(db_from_linear(0.5) - (-6.02)) < 0.1


# -- Export Preset Tests ---------------------------------------------------

class TestExportPresets:
    def test_list_presets(self):
        presets = list_presets()
        assert len(presets) >= 4
        names = [p["name"] for p in presets]
        assert "wav" in names
        assert "mp3" in names

    def test_get_preset_info(self):
        info = get_preset_info("wav")
        assert info["format"] == "WAV"
        assert info["extension"] == ".wav"

    def test_get_preset_info_unknown(self):
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset_info("nonexistent_format")

    def test_all_presets_valid(self):
        for name, preset in EXPORT_PRESETS.items():
            assert "format" in preset
            assert "ext" in preset
            assert "params" in preset


# -- Media Probe Tests (with WAV) -----------------------------------------

class TestMediaProbe:
    def test_probe_wav(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            # Create a real WAV file
            samples = generate_sine_wave(440, 0.5, 44100, 0.5, 1)
            write_wav(path, samples, 44100, 1, 16)
            info = probe_audio(path)
            assert info["format"] == "WAV"
            assert info["sample_rate"] == 44100
            assert info["channels"] == 1
            assert info["bit_depth"] == 16
            assert abs(info["duration"] - 0.5) < 0.01
        finally:
            os.unlink(path)

    def test_probe_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            probe_audio("/nonexistent/audio.wav")

    def test_check_media_all_present(self):
        proj = create_project()
        add_track(proj, name="T")
        # No real files — just testing the check logic
        result = check_media(proj)
        assert result["status"] == "ok"
        assert result["total"] == 0

    def test_check_media_missing(self):
        proj = create_project()
        add_track(proj, name="T")
        add_clip(proj, 0, "/fake/missing.wav", start_time=0, end_time=1)
        result = check_media(proj)
        assert result["status"] == "missing_files"
        assert result["missing"] == 1

    def test_get_duration(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            samples = generate_sine_wave(440, 2.0, 44100, 0.5, 1)
            write_wav(path, samples, 44100, 1, 16)
            dur = get_duration(path)
            assert abs(dur - 2.0) < 0.01
        finally:
            os.unlink(path)
