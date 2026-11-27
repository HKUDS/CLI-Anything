"""Regression tests for compressed audio sources (issue #746).

The Audacity harness reads sources with the stdlib ``wave`` module, so an
MP3 used to become a 10-second silence clip. These tests pin the two fixes:
duration probing and render-time decoding through SoX. The SoX boundary is
stubbed at the module level so the checks are deterministic and need no
external binary.
"""

import math
import os
import struct
import subprocess as real_subprocess
import tempfile
import types
import unittest
import wave
from unittest import mock

from cli_anything.audacity.core.clips import add_clip, import_audio
from cli_anything.audacity.core.export import render_mix
from cli_anything.audacity.core.project import create_project
from cli_anything.audacity.core.tracks import add_track
from cli_anything.audacity.utils import sox_backend
from cli_anything.audacity.utils.audio_utils import generate_sine_wave, write_wav

FAKE_DURATION = 0.5
RECORDED_RUNS = []


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fake_run(cmd, **kwargs):
    """Stand-in for subprocess.run inside sox_backend."""
    RECORDED_RUNS.append(list(cmd))
    executable = os.path.basename(str(cmd[0]))
    if executable == "soxi" and list(cmd[1:2]) == ["-D"]:
        return FakeResult(stdout=f"{FAKE_DURATION}\n")
    if executable == "sox" and len(cmd) >= 2:
        output = str(cmd[-1])
        source = str(cmd[1])
        requested = None
        if "-c" in cmd:
            requested = int(cmd[cmd.index("-c") + 1])
        if requested is None:
            # A surround source keeps its native layout unless SoX is asked
            # to remix it; mono sources stay mono.
            requested = 6 if "surround" in source else 1
        rate = 8000
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / rate)))
            * requested
            for i in range(int(FAKE_DURATION * rate))
        )
        with wave.open(output, "w") as handle:
            handle.setnchannels(requested)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes(frames)
        return FakeResult()
    return FakeResult(returncode=2, stderr="fake sox: unsupported command")


class CompressedInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="audacity-746-")
        self.root = self.tmp_dir.name
        RECORDED_RUNS.clear()
        self.mp3 = os.path.join(self.root, "voice.mp3")
        with open(self.mp3, "wb") as handle:
            handle.write(b"ID3\x04\x00\x00\x00\x00\x00\x00not-a-wav")
        self.old_shutil = sox_backend.shutil
        self.old_subprocess = sox_backend.subprocess
        self._use_fake_sox()

    def tearDown(self):
        sox_backend.shutil = self.old_shutil
        sox_backend.subprocess = self.old_subprocess
        self.tmp_dir.cleanup()

    def _use_fake_sox(self):
        sox_backend.shutil = types.SimpleNamespace(
            which=lambda name: f"/fake/{name}" if name in ("sox", "soxi") else None
        )
        sox_backend.subprocess = types.SimpleNamespace(
            run=fake_run,
            TimeoutExpired=real_subprocess.TimeoutExpired,
        )

    def _without_sox(self):
        sox_backend.shutil = types.SimpleNamespace(which=lambda name: None)

    def _without_soxi(self):
        sox_backend.shutil = types.SimpleNamespace(
            which=lambda name: "/fake/sox" if name == "sox" else None
        )

    def _project(self, source, **kwargs):
        project = create_project()
        add_track(project, name="Track 1")
        clip = add_clip(project, 0, source, **kwargs)
        return project, clip

    def test_import_reports_probed_duration(self):
        info = import_audio(self.mp3)
        self.assertEqual(info["format"], "MP3")
        self.assertAlmostEqual(info["duration"], FAKE_DURATION, places=2)

    def test_clip_add_uses_probed_duration(self):
        _, clip = self._project(self.mp3)
        self.assertAlmostEqual(clip["end_time"], FAKE_DURATION, places=2)
        self.assertAlmostEqual(clip["trim_end"], FAKE_DURATION, places=2)

    def test_render_decodes_compressed_source(self):
        project, _ = self._project(
            self.mp3, end_time=FAKE_DURATION, trim_end=FAKE_DURATION
        )
        output = os.path.join(self.root, "out.wav")
        result = render_mix(project, output, preset="wav")
        self.assertGreater(result["peak_level"], 0.01)
        with wave.open(output, "r") as handle:
            self.assertGreater(handle.getnframes(), 0)

    def test_surround_source_is_decoded_to_project_channels(self):
        """A decoded multichannel source must arrive in the project layout."""
        source = os.path.join(self.root, "surround.flac")
        with open(source, "wb") as handle:
            handle.write(b"fLaC\x00\x00\x00\x22not-really-a-flac")

        project = create_project(sample_rate=8000, channels=1)
        add_track(project, name="Track 1")
        clip = add_clip(project, 0, source)
        self.assertAlmostEqual(clip["end_time"], FAKE_DURATION, places=2)

        output = os.path.join(self.root, "surround-out.wav")
        result = render_mix(project, output, preset="wav")
        self.assertAlmostEqual(result["duration"], FAKE_DURATION, places=2)

        decode_cmds = [
            cmd for cmd in RECORDED_RUNS
            if os.path.basename(str(cmd[0])) == "sox" and str(cmd[-1]).endswith(".wav")
        ]
        self.assertTrue(decode_cmds, "the source was not decoded through SoX")
        self.assertIn("-c", decode_cmds[0], "SoX was not asked for the project layout")
        self.assertEqual(decode_cmds[0][decode_cmds[0].index("-c") + 1], "1")

        with wave.open(output, "r") as handle:
            self.assertEqual(handle.getnchannels(), 1)
            self.assertEqual(handle.getnframes(), int(FAKE_DURATION * 8000))
            raw = handle.readframes(handle.getnframes())
        tail = struct.unpack("<1000h", raw[-2000:])
        self.assertGreater(
            max(abs(sample) for sample in tail),
            3000,
            "the clip was inserted with the source layout and truncated",
        )

    def test_render_fails_loudly_without_sox(self):
        project, _ = self._project(
            self.mp3, end_time=FAKE_DURATION, trim_end=FAKE_DURATION
        )
        output = os.path.join(self.root, "nosox.wav")
        self._without_sox()
        with self.assertRaises(RuntimeError) as raised:
            render_mix(project, output, preset="wav")
        self.assertIn("SoX", str(raised.exception))
        self.assertFalse(os.path.exists(output))

    def test_add_clip_without_duration_fails_clearly(self):
        self._without_sox()
        project = create_project()
        add_track(project, name="Track 1")
        with self.assertRaises(ValueError) as raised:
            add_clip(project, 0, self.mp3)
        self.assertIn("duration", str(raised.exception))

    def test_wav_control_unchanged(self):
        wav_path = os.path.join(self.root, "tone.wav")
        samples = generate_sine_wave(440.0, 0.25, 44100, 0.5, 1)
        write_wav(wav_path, samples, 44100, 1, 16)
        project, clip = self._project(wav_path)
        self.assertAlmostEqual(clip["end_time"], 0.25, places=2)
        output = os.path.join(self.root, "tone-out.wav")
        result = render_mix(project, output, preset="wav")
        self.assertGreater(result["peak_level"], 0.1)

    def test_stereo_to_mono_resampling_keeps_full_duration(self):
        """A converted clip must not be truncated by the resampler."""
        wav_path = os.path.join(self.root, "stereo-8k.wav")
        frames = int(8000 * 0.5)
        payload = b"".join(struct.pack("<hh", 12000, 12000) for _ in range(frames))
        with wave.open(wav_path, "w") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(payload)

        project = create_project(sample_rate=16000, channels=1)
        add_track(project, name="Track 1")
        clip = add_clip(project, 0, wav_path)
        self.assertAlmostEqual(clip["end_time"], 0.5, places=2)

        output = os.path.join(self.root, "resampled.wav")
        result = render_mix(project, output, preset="wav")
        self.assertAlmostEqual(result["duration"], 0.5, places=2)
        with wave.open(output, "r") as handle:
            self.assertEqual(handle.getnframes(), 8000)
            raw = handle.readframes(handle.getnframes())
        tail = struct.unpack("<1000h", raw[-2000:])
        self.assertGreater(
            max(abs(sample) for sample in tail),
            3000,
            "the second half of the clip was left silent",
        )

    def test_probe_fallback_asks_sox_for_plain_mono_pcm(self):
        """The soxi fallback must produce a WAV every Python can read."""
        self._without_soxi()
        duration = sox_backend.probe_duration(self.mp3)
        self.assertAlmostEqual(duration, FAKE_DURATION, places=2)

        decode_cmds = [
            cmd for cmd in RECORDED_RUNS
            if os.path.basename(str(cmd[0])) == "sox"
        ]
        self.assertTrue(decode_cmds, "the fallback did not decode through SoX")
        cmd = decode_cmds[-1]
        self.assertIn("-c", cmd, "the probe kept the source channel layout")
        self.assertEqual(cmd[cmd.index("-c") + 1], "1")
        self.assertIn("-b", cmd, "the probe was not pinned to plain 16-bit PCM")
        self.assertEqual(cmd[cmd.index("-b") + 1], "16")

    def test_add_clip_reports_unreadable_probe(self):
        """An unreadable probe WAV becomes the actionable error, not a crash."""
        project = create_project()
        add_track(project, name="Track 1")
        with mock.patch.object(
            sox_backend,
            "probe_duration",
            side_effect=wave.Error("unknown format: 65534"),
        ):
            with self.assertRaises(ValueError) as raised:
                add_clip(project, 0, self.mp3)
        self.assertIn("duration", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
