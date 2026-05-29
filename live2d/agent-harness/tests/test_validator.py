import json
import tempfile
import unittest
from pathlib import Path

from cli_anything.live2d.core.parser import load_model
from cli_anything.live2d.core.validator import validate_model


class ValidatorStrictModeTest(unittest.TestCase):
    def test_strict_validation_rejects_placeholder_moc3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "textures").mkdir()
            (root / "textures" / "texture_00.png").write_bytes(b"fake-png")
            (root / "yoyo.moc3").write_bytes(b"MOC3\x03\x00\x00\x00")
            (root / "yoyo.model3.json").write_text(
                json.dumps(
                    {
                        "Version": 3,
                        "FileReferences": {
                            "Moc": "yoyo.moc3",
                            "Textures": ["textures/texture_00.png"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            info = load_model(root / "yoyo.model3.json")
            result = validate_model(info, strict=True)

            self.assertFalse(result.ok)
            self.assertTrue(
                any("Moc3 too small" in error for error in result.errors),
                result.errors,
            )


if __name__ == "__main__":
    unittest.main()
