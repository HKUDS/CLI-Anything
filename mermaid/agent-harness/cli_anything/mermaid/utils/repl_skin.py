"""Minimal REPL skin compatible with CLI-Anything REPL usage."""

from __future__ import annotations

import os
from pathlib import Path
import textwrap

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory

_SKILL_SOURCE_REPO = os.environ.get("CLI_ANYTHING_SKILL_REPO", "HKUDS/CLI-Anything")


def _display_home_path(path: str) -> str:
    expanded = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative.as_posix()}"
    except ValueError:
        return str(expanded)


class ReplSkin:
    def __init__(self, software: str, version: str = "1.0.0", skill_path: str | None = None):
        self.software = software
        self.version = version
        self.skill_slug = self.software.replace("_", "-")
        self.skill_id = f"cli-anything-{self.skill_slug}"
        self.skill_install_cmd = (
            f"npx skills add {_SKILL_SOURCE_REPO} --skill {self.skill_id} -g -y"
        )
        global_skill_root = Path(
            os.environ.get("CLI_ANYTHING_GLOBAL_SKILLS_DIR", str(Path.home() / ".agents" / "skills"))
        ).expanduser()
        self.global_skill_path = str(global_skill_root / self.skill_id / "SKILL.md")
        self.skill_path = skill_path or self._detect_skill_path()

    def _detect_skill_path(self) -> str | None:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "skills" / self.skill_id / "SKILL.md"
            if candidate.is_file():
                return str(candidate)
        package_skill = Path(__file__).resolve().parent.parent / "skills" / "SKILL.md"
        if package_skill.is_file():
            return str(package_skill)
        return None

    def print_banner(self) -> None:
        print(f"cli-anything-{self.software} v{self.version}")
        install_lines = textwrap.wrap(
            self.skill_install_cmd, width=88, break_long_words=True, break_on_hyphens=False
        ) or [self.skill_install_cmd]
        for index, line in enumerate(install_lines):
            prefix = "Install: " if index == 0 else "         "
            print(f"{prefix}{line}")
        print(f"Global skill: {_display_home_path(self.global_skill_path)}")
        print("Type help for commands, quit to exit")

    def create_prompt_session(self) -> PromptSession:
        return PromptSession(history=InMemoryHistory(), auto_suggest=AutoSuggestFromHistory())

    def get_input(self, session: PromptSession, project_name: str = "", modified: bool = False) -> str:
        suffix = "*" if modified else ""
        ctx = f"[{project_name}{suffix}]" if project_name else ""
        return session.prompt(f"{self.software}{ctx}> ")

    def help(self, commands: dict[str, str]) -> None:
        for command, desc in commands.items():
            print(f"{command}: {desc}")

    def success(self, message: str) -> None:
        print(f"OK {message}")

    def error(self, message: str) -> None:
        print(f"ERROR {message}")

    def warning(self, message: str) -> None:
        print(f"WARN {message}")

    def info(self, message: str) -> None:
        print(f"INFO {message}")

    def print_goodbye(self) -> None:
        print("Goodbye!")
