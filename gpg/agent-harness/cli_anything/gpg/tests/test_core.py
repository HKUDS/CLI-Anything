"""Tests for gpg core modules."""

import unittest
import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestSession(unittest.TestCase):
    """Test the Session class."""

    def test_init(self):
        from cli_anything.gpg.core.session import Session

        s = Session()
        self.assertFalse(s.has_project())
        self.assertIsNone(s.project)
        self.assertIsNone(s.project_path)

    def test_set_project(self):
        from cli_anything.gpg.core.session import Session

        s = Session()
        proj = {"name": "test", "metadata": {"created": "2024-01-01"}}
        s.set_project(proj, "/tmp/test.json")
        self.assertTrue(s.has_project())
        self.assertEqual(s.get_project()["name"], "test")

    def test_undo_redo(self):
        from cli_anything.gpg.core.session import Session

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
        from cli_anything.gpg.core.session import Session

        s = Session()
        proj = {"name": "test", "metadata": {"created": "2024-01-01"}}
        s.set_project(proj, "/tmp/test.json")
        with self.assertRaises(RuntimeError):
            s.undo()

    def test_status(self):
        from cli_anything.gpg.core.session import Session

        s = Session()
        st = s.status()
        self.assertFalse(st["has_project"])
        self.assertEqual(st["undo_count"], 0)


class TestKeysImports(unittest.TestCase):
    """Test that keys module imports correctly."""

    def test_import(self):
        from cli_anything.gpg.core import keys

        self.assertTrue(callable(keys.key_list))
        self.assertTrue(callable(keys.key_generate))
        self.assertTrue(callable(keys.key_export))
        self.assertTrue(callable(keys.key_export_secret))
        self.assertTrue(callable(keys.key_import))
        self.assertTrue(callable(keys.key_delete))
        self.assertTrue(callable(keys.key_trust))
        self.assertTrue(callable(keys.key_fingerprint))


class TestCryptoImports(unittest.TestCase):
    """Test that crypto module imports correctly."""

    def test_import(self):
        from cli_anything.gpg.core import crypto

        self.assertTrue(callable(crypto.encrypt))
        self.assertTrue(callable(crypto.decrypt))
        self.assertTrue(callable(crypto.sign))
        self.assertTrue(callable(crypto.verify))
        self.assertTrue(callable(crypto.clearsign))
        self.assertTrue(callable(crypto.detach_sign))

    def test_file_not_found(self):
        from cli_anything.gpg.core import crypto

        with self.assertRaises(FileNotFoundError):
            crypto.encrypt("/nonexistent/file.txt", "test@example.com")


if __name__ == "__main__":
    unittest.main()
