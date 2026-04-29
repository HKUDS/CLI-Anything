"""cli-anything REPL Skin — Unified terminal interface for all CLI harnesses.

Copy this file into your CLI package at:
    cli_anything/<software>/utils/repl_skin.py

Usage:
    from cli_anything.<software>.utils.repl_skin import ReplSkin

    skin = ReplSkin("n8n", version="2.4.7")
    skin.print_banner()  # auto-detects repo-root or packaged SKILL.md
    prompt_text = skin.prompt(project_name="my_workflow", modified=True)
    skin.success("Workflow activated")
    skin.error("Connection failed")
    skin.warning("Unsaved changes")
    skin.info("Processing 24 workflows...")
    skin.status("Status", "Connected")
    skin.table(headers, rows)
    skin.print_goodbye()
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import click

# ── ANSI color codes (no external deps for core styling) ──────────────

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_ITALIC = "\033[3m"
_UNDERLINE = "\033[4m"

# Brand colors
_CYAN = "\033[38;5;80m"       # cli-anything brand cyan
_CYAN_BG = "\033[48;5;80m"
_WHITE = "\033[97m"
_GRAY = "\033[38;5;245m"
_DARK_GRAY = "\033[38;5;240m"
_LIGHT_GRAY = "\033[38;5;250m"

# Software accent colors — each software gets a unique accent
_ACCENT_COLORS = {
    "gimp":        "\033[38;5;214m",   # warm orange
    "blender":     "\033[38;5;208m",   # deep orange
    "inkscape":    "\033[38;5;39m",    # bright blue
    "audacity":    "\033[38;5;33m",    # navy blue
    "libreoffice": "\033[38;5;40m",    # green
    "obs_studio":  "\033[38;5;55m",    # purple
    "kdenlive":    "\033[38;5;69m",    # slate blue
    "shotcut":     "\033[38;5;35m",    # teal green
    "n8n":         "\033[38;5;203m",   # n8n coral/red (#EA4B71)
}
_DEFAULT_ACCENT = "\033[38;5;75m"      # default sky blue

# Status colors
_GREEN = "\033[38;5;78m"
_YELLOW = "\033[38;5;220m"
_RED = "\033[38;5;196m"
_BLUE = "\033[38;5;75m"
_MAGENTA = "\033[38;5;176m"

_SKILL_SOURCE_REPO = os.environ.get("CLI_ANYTHING_SKILL_REPO", "HKUDS/CLI-Anything")

# ── Brand icon ────────────────────────────────────────────────────────

# The cli-anything icon: a small colored diamond/chevron mark
_ICON = f"{_CYAN}{_BOLD}◆{_RESET}"
_ICON_SMALL = f"{_CYAN}▸{_RESET}"

# ── Box drawing characters ────────────────────────────────────────────

_H_LINE = "─"
_V_LINE = "│"
_TL = "╭"
_TR = "╮"
_BL = "╰"
_BR = "╯"
_T_DOWN = "┬"
_T_UP = "┴"
_T_RIGHT = "├"
_T_LEFT = "┤"
_CROSS = "┼"


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes for length calculation."""
    import re
    return re.sub(r"\033\[[^m]*m", "", text)


def _visible_len(text: str) -> int:
    """Get visible length of text (excluding ANSI codes)."""
    return len(_strip_ansi(text))


def _display_home_path(path: str) -> str:
    """Display a path relative to the home directory when possible."""
    expanded = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative.as_posix()}"
    except ValueError:
        return str(expanded)


class ReplSkin:
    """Unified REPL skin for cli-anything CLIs.

    Provides consistent branding, prompts, and message formatting
    across all CLI harnesses built with the cli-anything methodology.
    """

    def __init__(self, software: str, version: str = "1.0.0",
                 history_file: str | None = None, skill_path: str | None = None):
        """Initialize the REPL skin.

        Args:
            software: Software name (e.g., "gimp", "shotcut", "blender").
            version: CLI version string.
            history_file: Path for persistent command history.
                         Defaults to ~/.cli-anything-<software>/history
            skill_path: Path to the SKILL.md file for agent discovery.
                        Auto-detected from the repo-root skills/ tree when present,
                        otherwise from the package's skills/ directory.
                        Displayed in banner for AI agents to know where to read skill info.
        """
        self.software = software.lower().replace("-", "_")
        self.display_name = software.replace("_", " ").title()
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

        # Prefer repo-root canonical skills/<skill-id>/SKILL.md when running
        # inside the CLI-Anything monorepo. Fall back to the packaged
        # cli_anything/<software>/skills/SKILL.md for installed harnesses.
        if skill_path is None:
            package_skill = Path(__file__).resolve().parent.parent / "skills" / "SKILL.md"
            repo_skill = None
            for parent in Path(__file__).resolve().parents:
                candidate = parent / "skills" / self.skill_id / "SKILL.md"
                if candidate.is_file():
                    repo_skill = candidate
                    break
            if repo_skill and repo_skill.is_file():
                skill_path = str(repo_skill)
            elif package_skill.is_file():
                skill_path = str(package_skill)
        self.skill_path = skill_path
        self.accent = _ACCENT_COLORS.get(self.software, _DEFAULT_ACCENT)

        # History file
        if history_file is None:
            hist_dir = Path.home() / f".cli-anything-{self.software}"
            hist_dir.mkdir(parents=True, exist_ok=True)
            self.history_file = str(hist_dir / "history")
        else:
            self.history_file = history_file

        # Detect terminal capabilities
        self._color = self._detect_color_support()

    def _detect_color_support(self) -> bool:
        """Check if terminal supports color."""
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("CLI_ANYTHING_NO_COLOR"):
            return False
        if not hasattr(sys.stdout, "isatty"):
            return False
        return sys.stdout.isatty()

    def _c(self, code: str, text: str) -> str:
        """Apply color code if colors are supported."""
        if not self._color:
            return text
        return f"{code}{text}{_RESET}"

    # ── Banner ────────────────────────────────────────────────────────

    def print_banner(self):
        """Print the startup banner with branding."""
        import textwrap

        inner = 72

        def _box_line(content: str) -> str:
            """Wrap content in box drawing, padding to inner width."""
            pad = inner - _visible_len(content)
            vl = self._c(_DARK_GRAY, _V_LINE)
            return f"{vl}{content}{' ' * max(0, pad)}{vl}"

        def _meta_lines(label: str, value: str) -> list[str]:
            """Wrap a metadata line for the banner box."""
            icon = self._c(_MAGENTA, "◇")
            label_text = self._c(_DARK_GRAY, label)
            prefix = f" {icon} {label_text} "
            available = max(12, inner - _visible_len(prefix))
            wrapped = textwrap.wrap(
                value,
                width=available,
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]
            lines = [f"{prefix}{self._c(_LIGHT_GRAY, wrapped[0])}"]
            continuation_prefix = " " * _visible_len(prefix)
            for chunk in wrapped[1:]:
                lines.append(f"{continuation_prefix}{self._c(_LIGHT_GRAY, chunk)}")
            return lines

        top = self._c(_DARK_GRAY, f"{_TL}{_H_LINE * inner}{_TR}")
        bot = self._c(_DARK_GRAY, f"{_BL}{_H_LINE * inner}{_BR}")

        # Title:  ◆  cli-anything · N8N
        icon = self._c(_CYAN + _BOLD, "◆")
        brand = self._c(_CYAN + _BOLD, "cli-anything")
        dot = self._c(_DARK_GRAY, "·")
        name = self._c(self.accent + _BOLD, self.display_name)
        title = f" {icon}  {brand} {dot} {name}"

        ver = f" {self._c(_DARK_GRAY, f'   v{self.version}')}"
        tip = f" {self._c(_DARK_GRAY, '   Type help for commands, quit to exit')}"
        empty = ""

        meta_lines: list[str] = []
        meta_lines.extend(_meta_lines("Install:", self.skill_install_cmd))
        meta_lines.extend(_meta_lines("Global skill:", _display_home_path(self.global_skill_path)))
        print(top)
        print(_box_line(title))
        print(_box_line(ver))
        for line in meta_lines:
            print(_box_line(line))
        print(_box_line(empty))
        print(_box_line(tip))
        print(bot)
        print()

    # ── Prompt ────────────────────────────────────────────────────────

    def prompt(self, project_name: str = "", modified: bool = False,
               context: str = "") -> str:
        """Build a styled prompt string for prompt_toolkit or input().

        Args:
            project_name: Current project name (empty if none open).
            modified: Whether the project has unsaved changes.
            context: Optional extra context to show in prompt.

        Returns:
            Formatted prompt string.
        """
        parts = []

        # Icon
        if self._color:
            parts.append(f"{_CYAN}◆{_RESET} ")
        else:
            parts.append("> ")

        # Software name
        parts.append(self._c(self.accent + _BOLD, self.software))

        # Project context
        if project_name or context:
            ctx = context or project_name
            mod = "*" if modified else ""
            parts.append(f" {self._c(_DARK_GRAY, '[')}")
            parts.append(self._c(_LIGHT_GRAY, f"{ctx}{mod}"))
            parts.append(self._c(_DARK_GRAY, ']'))

        parts.append(self._c(_GRAY, " ❯ "))

        return "".join(parts)

    def prompt_tokens(self, project_name: str = "", modified: bool = False,
                      context: str = ""):
        """Build prompt_toolkit formatted text tokens for the prompt.

        Use with prompt_toolkit's FormattedText for proper ANSI handling.

        Returns:
            list of (style, text) tuples for prompt_toolkit.
        """
        tokens = []

        tokens.append(("class:icon", "◆ "))
        tokens.append(("class:software", self.software))

        if project_name or context:
            ctx = context or project_name
            mod = "*" if modified else ""
            tokens.append(("class:bracket", " ["))
            tokens.append(("class:context", f"{ctx}{mod}"))
            tokens.append(("class:bracket", "]"))

        tokens.append(("class:arrow", " ❯ "))

        return tokens

    def get_prompt_style(self):
        """Get a prompt_toolkit Style object matching the skin.

        Returns:
            prompt_toolkit.styles.Style
        """
        try:
            from prompt_toolkit.styles import Style
        except ImportError:
            return None

        accent_hex = _ANSI_256_TO_HEX.get(self.accent, "#5fafff")

        return Style.from_dict({
            "icon": "#5fdfdf bold",     # cyan brand color
            "software": f"{accent_hex} bold",
            "bracket": "#585858",
            "context": "#bcbcbc",
            "arrow": "#808080",
            # Completion menu
            "completion-menu.completion": "bg:#303030 #bcbcbc",
            "completion-menu.completion.current": f"bg:{accent_hex} #000000",
            "completion-menu.meta.completion": "bg:#303030 #808080",
            "completion-menu.meta.completion.current": f"bg:{accent_hex} #000000",
            # Auto-suggest
            "auto-suggest": "#585858",
            # Bottom toolbar
            "bottom-toolbar": "bg:#1c1c1c #808080",
            "bottom-toolbar.text": "#808080",
        })

    # ── Messages ──────────────────────────────────────────────────────

    def success(self, message: str):
        """Print a success message with green checkmark."""
        icon = self._c(_GREEN + _BOLD, "✓")
        print(f"  {icon} {self._c(_GREEN, message)}")

    def error(self, message: str):
        """Print an error message with red cross."""
        icon = self._c(_RED + _BOLD, "✗")
        print(f"  {icon} {self._c(_RED, message)}", file=sys.stderr)

    def warning(self, message: str):
        """Print a warning message with yellow triangle."""
        icon = self._c(_YELLOW + _BOLD, "⚠")
        print(f"  {icon} {self._c(_YELLOW, message)}")

    def info(self, message: str):
        """Print an info message with blue dot."""
        icon = self._c(_BLUE, "●")
        print(f"  {icon} {self._c(_LIGHT_GRAY, message)}")

    def hint(self, message: str):
        """Print a subtle hint message."""
        print(f"  {self._c(_DARK_GRAY, message)}")

    def section(self, title: str):
        """Print a section header."""
        print()
        print(f"  {self._c(self.accent + _BOLD, title)}")
        print(f"  {self._c(_DARK_GRAY, _H_LINE * len(title))}")

    # ── Status display ────────────────────────────────────────────────

    def status(self, label: str, value: str):
        """Print a key-value status line."""
        lbl = self._c(_GRAY, f"  {label}:")
        val = self._c(_WHITE, f" {value}")
        print(f"{lbl}{val}")

    def status_block(self, items: dict[str, str], title: str = ""):
        """Print a block of status key-value pairs.

        Args:
            items: Dict of label -> value pairs.
            title: Optional title for the block.
        """
        if title:
            self.section(title)

        max_key = max(len(k) for k in items) if items else 0
        for label, value in items.items():
            lbl = self._c(_GRAY, f"  {label:<{max_key}}")
            val = self._c(_WHITE, f"  {value}")
            print(f"{lbl}{val}")

    def progress(self, current: int, total: int, label: str = ""):
        """Print a simple progress indicator.

        Args:
            current: Current step number.
            total: Total number of steps.
            label: Optional label for the progress.
        """
        pct = int(current / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        text = f"  {self._c(_CYAN, bar)} {self._c(_GRAY, f'{pct:3d}%')}"
        if label:
            text += f" {self._c(_LIGHT_GRAY, label)}"
        print(text)

    # ── Table display ─────────────────────────────────────────────────

    def table(self, headers: list[str], rows: list[list[str]],
              max_col_width: int = 40):
        """Print a formatted table with box-drawing characters.

        Args:
            headers: Column header strings.
            rows: List of rows, each a list of cell strings.
            max_col_width: Maximum column width before truncation.
        """
        if not headers:
            return

        # Calculate column widths
        col_widths = [min(len(h), max_col_width) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = min(
                        max(col_widths[i], len(str(cell))), max_col_width
                    )

        def pad(text: str, width: int) -> str:
            t = str(text)[:width]
            return t + " " * (width - len(t))

        # Header
        header_cells = [
            self._c(_CYAN + _BOLD, pad(h, col_widths[i]))
            for i, h in enumerate(headers)
        ]
        sep = self._c(_DARK_GRAY, f" {_V_LINE} ")
        header_line = f"  {sep.join(header_cells)}"
        print(header_line)

        # Separator
        print(self._c(_DARK_GRAY, f"  {'───'.join([_H_LINE * w for w in col_widths])}"))

        # Rows
        for row in rows:
            cells = []
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    cells.append(self._c(_LIGHT_GRAY, pad(str(cell), col_widths[i])))
            row_sep = self._c(_DARK_GRAY, f" {_V_LINE} ")
            print(f"  {row_sep.join(cells)}")

    # ── Help display ──────────────────────────────────────────────────

    def help(self, commands: dict[str, str]):
        """Print a formatted help listing.

        Args:
            commands: Dict of command -> description pairs.
        """
        self.section("Commands")
        max_cmd = max(len(c) for c in commands) if commands else 0
        for cmd, desc in commands.items():
            cmd_styled = self._c(self.accent, f"  {cmd:<{max_cmd}}")
            desc_styled = self._c(_GRAY, f"  {desc}")
            print(f"{cmd_styled}{desc_styled}")
        print()

    # ── Goodbye ───────────────────────────────────────────────────────

    def print_goodbye(self):
        """Print a styled goodbye message."""
        print(f"\n  {_ICON_SMALL} {self._c(_GRAY, 'Goodbye!')}\n")

    # ── Prompt toolkit session factory ────────────────────────────────

    def create_prompt_session(self):
        """Create a prompt_toolkit PromptSession with skin styling.

        Returns:
            A configured PromptSession, or None if prompt_toolkit unavailable.
        """
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import FileHistory
            from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

            style = self.get_prompt_style()

            session = PromptSession(
                history=FileHistory(self.history_file),
                auto_suggest=AutoSuggestFromHistory(),
                style=style,
                enable_history_search=True,
            )
            return session
        except ImportError:
            return None

    def get_input(self, pt_session, project_name: str = "",
                  modified: bool = False, context: str = "") -> str:
        """Get input from user using prompt_toolkit or fallback.

        Args:
            pt_session: A prompt_toolkit PromptSession (or None).
            project_name: Current project name.
            modified: Whether project has unsaved changes.
            context: Optional context string.

        Returns:
            User input string (stripped).
        """
        if pt_session is not None:
            from prompt_toolkit.formatted_text import FormattedText
            tokens = self.prompt_tokens(project_name, modified, context)
            return pt_session.prompt(FormattedText(tokens)).strip()
        else:
            raw_prompt = self.prompt(project_name, modified, context)
            return input(raw_prompt).strip()

    # ── Toolbar builder ───────────────────────────────────────────────

    def bottom_toolbar(self, items: dict[str, str]):
        """Create a bottom toolbar callback for prompt_toolkit.

        Args:
            items: Dict of label -> value pairs to show in toolbar.

        Returns:
            A callable that returns FormattedText for the toolbar.
        """
        def toolbar():
            from prompt_toolkit.formatted_text import FormattedText
            parts = []
            for i, (k, v) in enumerate(items.items()):
                if i > 0:
                    parts.append(("class:bottom-toolbar.text", "  │  "))
                parts.append(("class:bottom-toolbar.text", f" {k}: "))
                parts.append(("class:bottom-toolbar", v))
            return FormattedText(parts)
        return toolbar


# ── ANSI 256-color to hex mapping (for prompt_toolkit styles) ─────────

_ANSI_256_TO_HEX = {
    "\033[38;5;33m":  "#0087ff",  # audacity navy blue
    "\033[38;5;35m":  "#00af5f",  # shotcut teal
    "\033[38;5;39m":  "#00afff",  # inkscape bright blue
    "\033[38;5;40m":  "#00d700",  # libreoffice green
    "\033[38;5;55m":  "#5f00af",  # obs purple
    "\033[38;5;69m":  "#5f87ff",  # kdenlive slate blue
    "\033[38;5;75m":  "#5fafff",  # default sky blue
    "\033[38;5;80m":  "#5fd7d7",  # brand cyan
    "\033[38;5;203m": "#ff5f5f",  # n8n coral
    "\033[38;5;208m": "#ff8700",  # blender deep orange
    "\033[38;5;214m": "#ffaf00",  # gimp warm orange
}


# ── Module-level convenience wrappers ─────────────────────────────────
# These delegate to a lazily-initialized ReplSkin singleton so that
# n8n_cli.py can do `from ...repl_skin import success, error, warn`
# while still routing through the standard ReplSkin class.

_skin: ReplSkin | None = None


def _get_skin() -> ReplSkin:
    global _skin
    if _skin is None:
        # Import VERSION lazily to avoid circular imports
        try:
            from cli_anything.n8n.n8n_cli import VERSION
        except ImportError:
            VERSION = "0.0.0"
        _skin = ReplSkin("n8n", version=VERSION)
    return _skin


def print_banner() -> None:
    """Print the cli-anything branded banner."""
    _get_skin().print_banner()


def success(msg: str) -> None:
    """Print a success message."""
    _get_skin().success(msg)


def error(msg: str) -> None:
    """Print an error message."""
    _get_skin().error(msg)


def warn(msg: str) -> None:
    """Print a warning message."""
    _get_skin().warning(msg)


# ── n8n-specific output helpers ───────────────────────────────────────
# These handle --json flag and n8n API response formatting.
# Not part of the standard ReplSkin because they depend on click and
# n8n API response structure (data/nextCursor pagination).

def output(data: Any, as_json: bool) -> None:
    """Print data as JSON or human-readable."""
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            _print_table(data["data"])
            if "nextCursor" in data:
                click.secho(f"\n  Next cursor: {data['nextCursor']}", fg="bright_black")
        else:
            _print_dict(data)
    elif isinstance(data, list):
        if data and isinstance(data[0], dict):
            _print_table(data)
        else:
            click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(str(data))


def _print_dict(d: dict[str, Any], indent: int = 0) -> None:
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.secho(f"{prefix}{k}:", fg="cyan")
            _print_dict(v, indent + 1)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            click.secho(f"{prefix}{k}:", fg="cyan")
            _print_table(v)
        else:
            click.echo(f"{prefix}{click.style(str(k), fg='cyan')}: {v}")


def _print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        click.secho("  (empty)", fg="bright_black")
        return

    term_width = shutil.get_terminal_size().columns
    keys = list(rows[0].keys())

    # Filter out overly complex nested fields for table view
    simple_keys = [k for k in keys if not isinstance(rows[0].get(k), (dict, list))]
    if not simple_keys:
        simple_keys = keys[:5]

    col_widths = {k: len(str(k)) for k in simple_keys}
    for row in rows:
        for k in simple_keys:
            val = str(row.get(k, ""))
            col_widths[k] = min(max(col_widths[k], len(val)), 40)

    # Truncate columns if they exceed terminal width
    total = sum(col_widths.values()) + (len(simple_keys) - 1) * 3
    if total > term_width:
        max_col = max(10, term_width // len(simple_keys) - 3)
        col_widths = {k: min(v, max_col) for k, v in col_widths.items()}

    header = " | ".join(
        click.style(k.ljust(col_widths[k])[:col_widths[k]], fg="cyan")
        for k in simple_keys
    )
    click.echo(header)
    click.echo("-+-".join("-" * col_widths[k] for k in simple_keys))

    # Color rules for specific columns
    color_rules = {
        "status": {"success": "green", "error": "red", "running": "bright_yellow", "waiting": "cyan"},
        "active": {"True": "green", "False": "bright_black"},
    }

    for row in rows:
        vals = []
        for k in simple_keys:
            v = str(row.get(k, ""))
            w = col_widths[k]
            if len(v) > w and w > 3:
                cell = v[: w - 1] + "\u2026"
            else:
                cell = v.ljust(w)[:w]
            # Apply color if column has a rule
            if k in color_rules and v in color_rules[k]:
                cell = click.style(cell, fg=color_rules[k][v])
            vals.append(cell)
        click.echo(" | ".join(vals))
