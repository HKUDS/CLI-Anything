"""Tests for ffprobe core modules."""

import unittest
import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestSession(unittest.TestCase):
    """Test the Session class."""

    def test_init(self):
        from cli_anything.ffprobe.core.session import Session

        s = Session()
        self.assertFalse(s.has_project())
        self.assertIsNone(s.project)
        self.assertIsNone(s.project_path)

    def test_set_project(self):
        from cli_anything.ffprobe.core.session import Session

        s = Session()
        proj = {"name": "test", "metadata": {"created": "2024-01-01"}}
        s.set_project(proj, "/tmp/test.json")
        self.assertTrue(s.has_project())
        self.assertEqual(s.get_project()["name"], "test")

    def test_undo_redo(self):
        from cli_anything.ffprobe.core.session import Session

        s = Session()
        proj = {"name": "v1", "metadata": {"created": "2024-01-01"}}
        s.set_project(proj, "/tmp/test.json")
        s.snapshot("change 1")
        s.project["name"] = "v2"
        self.assertEqual(s.get_project()["name"], "v2")
        desc = s.undo()
        self.assertEqual(s.get_project()["name"], "v1")
        desc = s.redo()
        self.assertEqual(s.get_project()["name"], "v2")

    def test_undo_empty(self):
        from cli_anything.ffprobe.core.session import Session

        s = Session()
        proj = {"name": "test", "metadata": {"created": "2024-01-01"}}
        s.set_project(proj, "/tmp/test.json")
        with self.assertRaises(RuntimeError):
            s.undo()

    def test_status(self):
        from cli_anything.ffprobe.core.session import Session

        s = Session()
        st = s.status()
        self.assertFalse(st["has_project"])
        self.assertEqual(st["undo_count"], 0)


class TestAnalyzeImports(unittest.TestCase):
    """Test that analyze module imports correctly."""

    def test_import(self):
        from cli_anything.ffprobe.core import analyze

        self.assertTrue(callable(analyze.analyze_info))
        self.assertTrue(callable(analyze.analyze_streams))
        self.assertTrue(callable(analyze.analyze_format))
        self.assertTrue(callable(analyze.analyze_codec))
        self.assertTrue(callable(analyze.analyze_chapters))
        self.assertTrue(callable(analyze.analyze_packets))
        self.assertTrue(callable(analyze.analyze_frames))
        self.assertTrue(callable(analyze.analyze_thumbnails))
        self.assertTrue(callable(analyze.batch_analyze))
        self.assertTrue(callable(analyze.compare))

    def test_file_not_found(self):
        from cli_anything.ffprobe.core import analyze

        with self.assertRaises(FileNotFoundError):
            analyze.analyze_info("/nonexistent/file.mp4")


if __name__ == "__main__":
    unittest.main()
