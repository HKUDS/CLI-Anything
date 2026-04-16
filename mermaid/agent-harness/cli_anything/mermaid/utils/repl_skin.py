"""Minimal REPL skin compatible with CLI-Anything REPL usage."""

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory


class ReplSkin:
    def __init__(self, software: str, version: str = "1.0.0"):
        self.software = software
        self.version = version

    def print_banner(self) -> None:
        print(f"cli-anything-{self.software} v{self.version}")
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
