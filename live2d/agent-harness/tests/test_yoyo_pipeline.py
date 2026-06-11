import json
import tempfile
import unittest
from pathlib import Path

from cli_anything.live2d.core.yoyo_pipeline import check_yoyo_export


def write_model(root: Path, motions: dict):
    (root / "textures").mkdir()
    (root / "textures" / "texture_00.png").write_bytes(b"fake-png")
    (root / "yoyo.moc3").write_bytes(b"MOC3\x03\x00\x00\x00" + (b"\0" * 2048))
    (root / "yoyo.model3.json").write_text(
        json.dumps(
            {
                "Version": 3,
                "FileReferences": {
                    "Moc": "yoyo.moc3",
                    "Textures": ["textures/texture_00.png"],
                    "Motions": motions,
                },
            }
        ),
        encoding="utf-8",
    )


class YoyoPipelineTest(unittest.TestCase):
    def test_check_requires_idle_motion_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_model(root, motions={"Tap": [{"File": "motions/tap.motion3.json"}]})
            (root / "motions").mkdir()
            (root / "motions" / "tap.motion3.json").write_text(
                json.dumps({"Version": 3, "Meta": {"Duration": 1.0}, "Curves": []}),
                encoding="utf-8",
            )

            report = check_yoyo_export(root / "yoyo.model3.json")

            self.assertFalse(report.ok)
            self.assertTrue(
                any("Missing required motion group: idle" in error for error in report.errors),
                report.errors,
            )

    def test_check_accepts_strict_model_with_idle_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_model(root, motions={"Idle": [{"File": "motions/idle.motion3.json"}]})
            (root / "motions").mkdir()
            (root / "motions" / "idle.motion3.json").write_text(
                json.dumps({"Version": 3, "Meta": {"Duration": 1.0}, "Curves": []}),
                encoding="utf-8",
            )

            report = check_yoyo_export(root / "yoyo.model3.json")

            self.assertTrue(report.ok, report.errors)
            self.assertEqual(report.summary["motion_count"], 1)


if __name__ == "__main__":
    unittest.main()
