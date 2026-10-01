"""Native uninstall must preserve a pointer to another POSIX directory."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class PointerPathTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX backslash filenames")
    def test_foreign_pointer_with_literal_backslash_survives_uninstall(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / "home"
            plugins = root / "owner" / "plugins"
            installed = plugins / "local" / "cli-anything"
            foreign = root / "owner\\plugins" / "local" / "cli-anything"
            installed.mkdir(parents=True)
            foreign.mkdir(parents=True)
            marker = foreign / "foreign.txt"
            marker.write_text("another installation", encoding="utf-8")
            pointer = home / ".cursor" / "cli-anything-generator.root"
            pointer.parent.mkdir(parents=True)
            pointer.write_text(str(foreign) + "\n", encoding="utf-8")
            result = subprocess.run(
                ["bash", str(SCRIPTS / "uninstall.sh")],
                env=dict(
                    os.environ,
                    HOME=str(home),
                    CURSOR_PLUGINS_HOME=str(plugins),
                ),
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )
            self.assertFalse(installed.exists())
            self.assertEqual(marker.read_text(), "another installation")
            self.assertTrue(pointer.is_file(), result.stdout)
            self.assertEqual(pointer.read_text(), str(foreign) + "\n")

    def test_windows_keys_still_fold_case_and_separators(self):
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; normalize_path_key "$2"',
                "bash",
                str(SCRIPTS / "lib.sh"),
                "C:\\Users\\Rudy\\plugins\\local\\CLI-Anything\\",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout, "c:/users/rudy/plugins/local/cli-anything"
        )


if __name__ == "__main__":
    unittest.main()
