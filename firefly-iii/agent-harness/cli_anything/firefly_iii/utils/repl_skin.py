r"""
Unified REPL Skin

Provides consistent REPL interface experience for all CLI-Anything tools.
"""

import sys
from typing import Dict, Optional

# Try importing prompt_toolkit, fallback if unavailable
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


class ReplSkin:
    """Unified REPL skin"""

    # ANSI color codes
    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
    }

    def __init__(self, software: str, version: str = "1.0.0"):
        """
        Initialize REPL skin

        Args:
            software: Software name
            version: Version number
        """
        self.software = software
        self.version = version
        self.session = None

        if HAS_PROMPT_TOOLKIT:
            try:
                style = Style.from_dict({
                    'prompt': '#00aa00 bold',
                    'software': '#0088ff bold',
                })
                self.session = PromptSession(style=style)
            except Exception:
                # In non-interactive environments (e.g., some IDEs), prompt_toolkit may fail to initialize
                self.session = None

    def _color(self, text: str, color: str) -> str:
        """Add color to text"""
        if sys.platform == 'win32':
            # Windows may need ANSI support enabled
            import os
            os.system('')
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def print_banner(self):
        """Print branded startup banner"""
        banner = f"""
╔══════════════════════════════════════════════════════════════╗
║  {self._color(f'Firefly III CLI', 'cyan')} {self._color(f'v{self.version}', 'yellow')}                              ║
║  {self._color('Personal Finance Management', 'white')}                       ║
║  {self._color('Based on CLI-Anything Spec', 'white')}                              ║
╚══════════════════════════════════════════════════════════════╝
        """
        print(banner)

    def prompt(self, software_name: str) -> str:
        """Display styled prompt and get input"""
        prompt_text = f"{self._color(software_name, 'green')} > "

        if self.session:
            try:
                return self.session.prompt(prompt_text)
            except KeyboardInterrupt:
                return "exit"
        else:
            # Fallback to standard input
            try:
                return input(prompt_text)
            except KeyboardInterrupt:
                return "exit"

    def success(self, msg: str):
        """Display success message"""
        print(f"{self._color('✓', 'green')} {msg}")

    def error(self, msg: str):
        """Display error message"""
        print(f"{self._color('✗', 'red')} {msg}", file=sys.stderr)

    def warning(self, msg: str):
        """Display warning message"""
        print(f"{self._color('⚠', 'yellow')} {msg}")

    def info(self, msg: str):
        """Display info message"""
        print(f"{self._color('●', 'blue')} {msg}")

    def table(self, headers: list, rows: list):
        """Format table output"""
        if not rows:
            self.info("No data")
            return

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Print header
        header_line = " | ".join(
            self._color(h.ljust(col_widths[i]), 'bold')
            for i, h in enumerate(headers)
        )
        print(header_line)
        print("-" * len(header_line))

        # Print data rows
        for row in rows:
            print(" | ".join(
                str(cell).ljust(col_widths[i])
                for i, cell in enumerate(row)
            ))

    def progress(self, current: int, total: int, msg: str = ""):
        """Display progress bar"""
        percent = (current / total) * 100 if total > 0 else 0
        bar_length = 30
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r{self._color('⏳', 'yellow')} [{bar}] {percent:.1f}% {msg}", end="", flush=True)
        if current >= total:
            print()  # New line

    def help(self, commands: Dict):
        """Display help information"""
        print(f"\n{self._color('Available Commands:', 'bold')}")
        print("-" * 40)

        for name, command in commands.items():
            if name == 'repl':
                continue
            desc = command.help or command.callback.__doc__ or "No description"
            print(f"  {self._color(name, 'cyan'):20} {desc}")

        print(f"\n{self._color('REPL Commands:', 'bold')}")
        print("-" * 40)
        print(f"  {self._color('help', 'cyan'):20} Show this help")
        print(f"  {self._color('exit/quit/q', 'cyan'):20} Exit REPL")
        print()

    def print_goodbye(self):
        """Display goodbye message"""
        print(f"\n{self._color('Thank you for using Firefly III CLI, goodbye!', 'green')}")
