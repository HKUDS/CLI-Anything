"""Unit tests for the shared REPL skin helper.

Regression for issue #748: `_display_home_path` resolved symlinks, so a
global skill installed as a symlink into synced storage was displayed as its
long physical target and the banner truncated it.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import repl_skin


class DisplayHomePathTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"
        (self.home / ".agents" / "skills").mkdir(parents=True)
        self._old_home = os.environ.get("HOME")

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        self._tmp.cleanup()

    def _symlink_skill(self, target: Path) -> Path:
        link = self.home / ".agents" / "skills" / "cli-anything-demo"
        link.symlink_to(target)
        os.environ["HOME"] = str(self.home)
        return link

    def test_symlink_to_synced_storage_keeps_the_short_home_path(self):
        target = (
            self.root / "CloudStorage" / "GoogleDrive-account" / "skills" /
            "cli-anything-demo"
        )
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("x", encoding="utf-8")
        link = self._symlink_skill(target)

        displayed = repl_skin._display_home_path(str(link / "SKILL.md"))

        self.assertEqual(displayed, "~/.agents/skills/cli-anything-demo/SKILL.md")

    def test_symlink_inside_home_keeps_the_link_path(self):
        target = self.root / "home" / "dotfiles" / "skills" / "cli-anything-demo"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("x", encoding="utf-8")
        link = self._symlink_skill(target)

        displayed = repl_skin._display_home_path(str(link / "SKILL.md"))

        self.assertEqual(displayed, "~/.agents/skills/cli-anything-demo/SKILL.md")

    def test_path_outside_home_stays_absolute(self):
        outside = self.root / "elsewhere" / "SKILL.md"
        outside.parent.mkdir(parents=True)
        outside.write_text("x", encoding="utf-8")
        os.environ["HOME"] = str(self.home)

        displayed = repl_skin._display_home_path(str(outside))

        self.assertEqual(displayed, str(outside))

    def test_relative_skill_dir_is_made_absolute_against_the_cwd(self):
        """A relative global skills dir must not leak into the banner."""
        target = self.home / ".agents" / "skills" / "cli-anything-demo"
        target.mkdir(parents=True)
        os.environ["HOME"] = str(self.home)
        old_cwd = os.getcwd()
        os.chdir(str(self.home / ".agents"))
        try:
            displayed = repl_skin._display_home_path("skills/cli-anything-demo")
        finally:
            os.chdir(old_cwd)

        self.assertEqual(displayed, "~/.agents/skills/cli-anything-demo")

    def test_relative_path_outside_home_is_absolute(self):
        """A relative path outside home is displayed as an absolute path."""
        outside = self.root / "work"
        outside.mkdir()
        os.environ["HOME"] = str(self.home)
        old_cwd = os.getcwd()
        os.chdir(str(self.root))
        try:
            displayed = repl_skin._display_home_path("work")
        finally:
            os.chdir(old_cwd)

        self.assertEqual(displayed, str(outside))


if __name__ == "__main__":
    unittest.main()
