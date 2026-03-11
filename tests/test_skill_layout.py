from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "cli-anything"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---\n"):
        return None

    _, rest = text.split("---\n", 1)
    frontmatter, _, _ = rest.partition("\n---\n")
    for line in frontmatter.splitlines():
        prefix = f"{key}:"
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


class SkillLayoutTest(unittest.TestCase):
    def test_cli_anything_skill_layout_exists(self) -> None:
        self.assertTrue(SKILL_DIR.is_dir())
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "HARNESS.md").is_file())

        commands_dir = SKILL_DIR / "references" / "commands"
        self.assertTrue(commands_dir.is_dir())
        for name in ["cli-anything.md", "refine.md", "test.md", "validate.md", "list.md"]:
            self.assertTrue((commands_dir / name).is_file())

    def test_skill_frontmatter_describes_triggering(self) -> None:
        skill_text = _read(SKILL_DIR / "SKILL.md")

        self.assertEqual(_frontmatter_value(skill_text, "name"), "cli-anything")
        description = _frontmatter_value(skill_text, "description")
        self.assertIsNotNone(description)
        assert description is not None
        self.assertTrue("skill" in description.lower() or "skills" in description.lower())
        self.assertIn("cli", description.lower())
        self.assertIn("agent", description.lower())

    def test_readme_documents_plugin_and_skill_installation(self) -> None:
        readme = _read(ROOT / "README.md")
        readme_cn = _read(ROOT / "README_CN.md")

        self.assertIn(".agents/skills/cli-anything", readme)
        self.assertIn(".agents/skills/cli-anything", readme_cn)
        self.assertIn("/plugin install cli-anything", readme)
        self.assertIn("/plugin install cli-anything", readme_cn)
        self.assertNotIn("Legacy Plugin Users", readme)
        self.assertNotIn("Legacy 插件用户", readme_cn)
        self.assertNotIn("preferred generic skill entrypoint", readme)
        self.assertNotIn("首选的通用 skill 入口", readme_cn)


if __name__ == "__main__":
    unittest.main()
