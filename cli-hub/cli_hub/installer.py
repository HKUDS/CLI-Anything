"""Install, uninstall, and manage CLIs and matrices."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cli_hub.registry import get_cli
from cli_hub.matrix import get_matrix, resolve_install_scope, unmanaged_providers
from cli_hub.matrix_skill import render_matrix_skill_file

INSTALLED_FILE = Path.home() / ".cli-hub" / "installed.json"
MATRIX_STATE_FILE = Path.home() / ".cli-hub" / "matrix_state.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load_installed():
    if INSTALLED_FILE.exists():
        try:
            return json.loads(INSTALLED_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_installed(data):
    INSTALLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    INSTALLED_FILE.write_text(json.dumps(data, indent=2))


def _load_matrix_state():
    if MATRIX_STATE_FILE.exists():
        try:
            return json.loads(MATRIX_STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_matrix_state(data):
    MATRIX_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_STATE_FILE.write_text(json.dumps(data, indent=2))


def _find_npm():
    """Find npm executable. Returns path or None."""
    return shutil.which("npm")


def _find_uv():
    """Find uv executable. Returns path or None."""
    return shutil.which("uv")


_UV_INSTALL_HINT = (
    "uv is not installed. Install it first:\n"
    "  macOS / Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
    "  Windows:       powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"\n"
    "  pip:           pip install uv\n"
    "  brew:          brew install uv\n"
    "  See also:      https://docs.astral.sh/uv/getting-started/installation/"
)


_ALLOW_SHELL_ENV = "CLI_HUB_ALLOW_SHELL_COMMANDS"
_POSIX_SHELLS = {"bash", "dash", "ksh", "sh", "zsh"}
_WINDOWS_SHELLS = {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe"}

# Programs that run another program given as their trailing operands. Reaching
# the real executable means walking past the wrapper rather than trusting
# argv[0], and wrappers nest (``sudo env -S ...``), so the walk recurses.
_COMMAND_WRAPPERS = {
    "env",
    "sudo",
    "doas",
    "timeout",
    "nohup",
    "nice",
    "ionice",
    "setsid",
    "stdbuf",
    "chrt",
    "eatmydata",
    "proxychains",
    "proxychains4",
}

# Wrapper parsing is deliberately wrapper-specific. A shared option table
# cannot distinguish flags such as ``env -i`` from value-taking options such as
# ``ionice -c 2`` and can consequently skip the executable that follows. When
# an option shape is not known, the trust gate fails closed instead of guessing
# where the wrapped command starts.
_WRAPPER_FLAG_OPTIONS = {
    "env": {
        "-i", "--ignore-environment", "-0", "--null", "-v", "--debug",
        "--help", "--version",
    },
    "sudo": {
        "-A", "--askpass", "-b", "--background", "-E", "--preserve-env",
        "-e", "--edit", "-H", "--set-home", "-K", "--remove-timestamp",
        "-k", "--reset-timestamp", "-l", "--list", "-n", "--non-interactive",
        "-P", "--preserve-groups", "-S", "--stdin", "-s", "--shell", "-V",
        "--version", "-v", "--validate", "--help",
    },
    "doas": {"-L", "-n", "-s"},
    "timeout": {
        "--foreground", "--preserve-status", "--verbose", "--help", "--version",
    },
    "nohup": {"--help", "--version"},
    "nice": {"--help", "--version"},
    "ionice": {"-t", "--ignore", "-h", "--help", "-V", "--version"},
    "setsid": {
        "-c", "--ctty", "-f", "--fork", "-w", "--wait", "-h", "--help",
        "-V", "--version",
    },
    "stdbuf": {"--help", "--version"},
    "chrt": {
        "-a", "--all-tasks", "-b", "--batch", "-d", "--deadline", "-f",
        "--fifo", "-i", "--idle", "-o", "--other", "-r", "--rr", "-m",
        "--max", "-R", "--reset-on-fork", "-v", "--verbose", "-h", "--help",
        "-V", "--version",
    },
    "eatmydata": {"--help", "--version"},
    "proxychains": {"-q", "--quiet_mode"},
    "proxychains4": {"-q", "--quiet_mode"},
}

_WRAPPER_VALUE_OPTIONS = {
    "env": {
        "-u", "--unset", "-C", "--chdir", "-S", "--split-string",
        "--block-signal", "--default-signal", "--ignore-signal",
    },
    "sudo": {
        "-a", "--auth-type", "-C", "--close-from", "-D", "--chdir", "-g",
        "--group", "-h", "--host", "-p", "--prompt", "-R", "--chroot",
        "-r", "--role", "-t", "--type", "-T", "--command-timeout", "-u",
        "--user", "--other-user",
    },
    "doas": {"-a", "-C", "-u"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "ionice": {
        "-c", "--class", "-n", "--classdata", "-p", "--pid", "-P", "--pgid",
        "-u", "--uid",
    },
    "stdbuf": {"-i", "--input", "-o", "--output", "-e", "--error"},
    "chrt": {
        "-T", "--sched-runtime", "-P", "--sched-period", "-D", "--sched-deadline",
    },
    "proxychains": {"-f"},
    "proxychains4": {"-f"},
}

_WRAPPER_ATTACHED_VALUE_OPTIONS = {
    "env": {"-u", "-C", "-S"},
    "sudo": {"-a", "-C", "-D", "-g", "-h", "-p", "-R", "-r", "-t", "-T", "-u"},
    "doas": {"-a", "-C", "-u"},
    "timeout": {"-s", "-k"},
    "nice": {"-n"},
    "ionice": {"-c", "-n", "-p", "-P", "-u"},
    "stdbuf": {"-i", "-o", "-e"},
    "chrt": {"-T", "-P", "-D"},
    "proxychains": {"-f"},
    "proxychains4": {"-f"},
}

# These wrappers consume positional metadata before the command. timeout takes
# DURATION; chrt takes PRIORITY in its command-execution form.
_WRAPPER_POSITIONAL_OPERANDS = {"timeout": 1, "chrt": 1}

# Programs that hand a string to a shell themselves, via -c/--command, without
# being a shell. su(1) and runuser(1) document "-c, --command <command>" as
# passing that command to the target user's shell.
_SHELL_COMMAND_LAUNCHERS = {"su", "runuser", "doas"}

# PowerShell payload switches. Microsoft documents these as aliases rather than
# prefixes, so "ec" cannot be found by prefix-matching "encodedcommand", and
# about_PowerShell_exe allows either "-" or "/" for parameters under cmd.exe.
_PWSH_PAYLOAD_PARAMETERS = ("command", "commandwithargs", "encodedcommand", "file")
_PWSH_PAYLOAD_ALIASES = {"c", "cwa", "e", "ec", "enc", "f"}

# Depth bound for wrapper unwrapping. Exceeding it means the command nests
# wrappers beyond anything a registry entry legitimately needs, so the gate
# fails closed rather than guessing.
_MAX_WRAPPER_DEPTH = 8


def _contains_shell_operator(cmd):
    """Return True when cmd contains shell syntax outside literal quoting."""
    quote = None
    escaped = False
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if quote == "'":
            # POSIX shells treat backslashes literally inside single quotes.
            # Check the closing quote before applying generic escaping so a
            # trailing backslash cannot hide an operator that follows it.
            if ch == "'":
                quote = None
            i += 1
            continue
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if quote:
            if ch == quote:
                quote = None
            elif quote == '"' and (ch == "`" or (ch == "$" and i + 1 < len(cmd) and cmd[i + 1] == "(")):
                return True
            i += 1
            continue
        if ch in {"'", '"'}:
            quote = ch
        elif ch in {"|", "&", ";", "<", ">"} or ch in {"\n", "\r"}:
            return True
        elif ch == "`" or (ch == "$" and i + 1 < len(cmd) and cmd[i + 1] == "("):
            return True
        i += 1
    return False


def _allows_shell(cli):
    return bool(cli and cli.get("requires_shell") is True)


def _directly_invokes_shell_payload(argv):
    """Return True when argv starts a shell that will interpret a payload."""
    if not argv:
        return False
    executable = Path(argv[0]).name.lower()
    options = {arg.lower() for arg in argv[1:]}
    if executable in _POSIX_SHELLS:
        return any(
            option == "--command"
            or (
                option.startswith("-")
                and not option.startswith("--")
                and "c" in option[1:]
            )
            for option in options
        )
    if executable in {"cmd", "cmd.exe"}:
        return bool(options & {"/c", "/k"})
    if executable in _WINDOWS_SHELLS:
        return any(
            option.startswith(("-", "/"))
            and bool(parameter := option.lstrip("-/"))
            and (
                parameter in _PWSH_PAYLOAD_ALIASES
                or any(name.startswith(parameter) for name in _PWSH_PAYLOAD_PARAMETERS)
            )
            for option in options
        )
    if executable in {"sudo", "doas"}:
        # These wrappers can explicitly request the target user's shell. Once
        # selected, the trailing text is shell input even when no shell binary
        # appears as a separate argv element.
        if any(
            option in {"-s", "--shell", "-i", "--login"}
            or (
                option.startswith("-")
                and not option.startswith("--")
                and any(flag in option[1:] for flag in "si")
            )
            for option in options
        ):
            return True
    if executable in _SHELL_COMMAND_LAUNCHERS:
        # su/runuser do not interpret the string themselves; they hand it to the
        # target user's shell with -c, so the payload is shell-interpreted all
        # the same.
        return any(
            option in {"-c", "--command"}
            or option.startswith("--command=")
            or (
                option.startswith("-")
                and not option.startswith("--")
                and "c" in option[1:]
            )
            for option in options
        )
    return False


def _iter_env_split_strings(argv):
    """Yield GNU env -S/--split-string payloads embedded in argv."""
    if not argv or Path(argv[0]).name.lower() != "env":
        return
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            return
        if arg == "-S":
            if index + 1 < len(argv):
                yield argv[index + 1]
                index += 2
                continue
            return
        if arg.startswith("-S") and len(arg) > 2:
            yield arg[2:]
            index += 1
            continue
        if arg == "--split-string":
            if index + 1 < len(argv):
                yield argv[index + 1]
                index += 2
                continue
            return
        if arg.startswith("--split-string="):
            yield arg.split("=", 1)[1]
        index += 1


def _env_split_invokes_shell_payload(argv, *, _depth=0):
    for split_string in _iter_env_split_strings(argv):
        try:
            split_argv = shlex.split(split_string)
        except ValueError:
            return True
        if _contains_shell_operator(split_string):
            return True
        if _invokes_shell_payload(split_argv, _depth=_depth + 1):
            return True
    return False


def _wrapper_option_arity(wrapper, arg):
    """Return option arity, or None when a wrapper option is not understood."""
    flags = _WRAPPER_FLAG_OPTIONS.get(wrapper, set())
    values = _WRAPPER_VALUE_OPTIONS.get(wrapper, set())
    if arg in flags:
        return 0
    if arg in values:
        return 1
    if arg.startswith("--") and "=" in arg:
        name = arg.split("=", 1)[0]
        if name in values or (wrapper == "sudo" and name == "--preserve-env"):
            return 0
        return None
    if arg.startswith("-") and not arg.startswith("--"):
        for prefix in _WRAPPER_ATTACHED_VALUE_OPTIONS.get(wrapper, set()):
            if arg.startswith(prefix) and len(arg) > len(prefix):
                return 0
        # Known one-letter flags may be bundled (for example sudo -nE).
        if len(arg) > 2 and all(f"-{letter}" in flags for letter in arg[1:]):
            return 0
        # nice accepts the historical ``-N`` adjustment spelling.
        if wrapper == "nice":
            try:
                int(arg)
            except ValueError:
                pass
            else:
                return 0
    return None


def _strip_wrapper_arguments(argv):
    """Return argv positioned at the program a wrapper will actually exec.

    Wrappers take their own options before the command, and some of those
    options take a value (``timeout --signal TERM 5 sh -c ...``, ``env -u VAR``,
    ``sudo -u root``). Scanning the whole argv for a shell name instead of
    walking to the wrapped program is what let ``sudo env -S '...'`` through:
    the shell never appears as a bare token there.
    """
    wrapper = Path(argv[0]).name.lower()
    index = 1
    positional_remaining = _WRAPPER_POSITIONAL_OPERANDS.get(wrapper, 0)
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            index += 1
            break
        if not arg.startswith("-"):
            # env(1) and sudo(1) accept NAME=VALUE assignments before the
            # command, so the first bare token is not necessarily the program.
            if _is_env_assignment(arg):
                index += 1
                continue
            if positional_remaining:
                if wrapper == "timeout" and not _looks_like_duration(arg):
                    return None
                positional_remaining -= 1
                index += 1
                continue
            return argv[index:]
        arity = _wrapper_option_arity(wrapper, arg)
        if arity is None or index + arity >= len(argv):
            return None
        index += arity + 1

    while positional_remaining and index < len(argv):
        if wrapper == "timeout" and not _looks_like_duration(argv[index]):
            return None
        positional_remaining -= 1
        index += 1
    if positional_remaining:
        return []
    return argv[index:]


def _is_env_assignment(token):
    """True for ``NAME=VALUE`` operands that env/sudo consume before the command."""
    name, sep, _ = token.partition("=")
    return bool(sep) and bool(name) and (name[0].isalpha() or name[0] == "_") and all(
        ch.isalnum() or ch == "_" for ch in name
    )


def _looks_like_duration(token):
    """True for timeout(1) durations such as ``5``, ``2.5``, ``10s``, ``1h``."""
    body = token[:-1] if token[-1:] in {"s", "m", "h", "d"} else token
    try:
        float(body)
    except ValueError:
        return False
    return True


def _invokes_shell_payload(argv, _depth=0):
    """Return True for direct, wrapped or nested shell payload invocations.

    Wrappers nest and each layer can hide the next (``sudo env -S 'sh -c ...'``),
    so this walks through them rather than inspecting a single level. The depth
    bound fails closed: a command nesting wrappers deeper than any real registry
    entry needs is treated as requiring shell trust rather than waved through.
    """
    if not argv:
        return False
    if _depth > _MAX_WRAPPER_DEPTH:
        return True
    if _directly_invokes_shell_payload(argv):
        return True
    if _env_split_invokes_shell_payload(argv, _depth=_depth):
        return True
    if Path(argv[0]).name.lower() not in _COMMAND_WRAPPERS:
        return False
    wrapped = _strip_wrapper_arguments(argv)
    if wrapped is None:
        return True
    if not wrapped:
        return False
    return _invokes_shell_payload(wrapped, _depth=_depth + 1)


def _run_command(cmd, *, allow_shell=False, cwd=None):
    """Run a command string.

    Simple commands run without a shell. Commands containing shell operators
    such as pipes, redirections, or command substitutions require a reviewed
    registry entry with ``requires_shell: true``. CLI_HUB_ALLOW_SHELL_COMMANDS=1
    remains a hard override for callers that have reviewed the command locally.
    """
    use_shell = _contains_shell_operator(cmd)
    try:
        argv = None if use_shell else shlex.split(cmd)
    except ValueError as exc:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=2,
            stdout="",
            stderr=f"Invalid command syntax: {exc}",
        )
    requires_shell_trust = use_shell or _invokes_shell_payload(argv)
    if requires_shell_trust and not allow_shell and os.environ.get(_ALLOW_SHELL_ENV) != "1":
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=2,
            stdout="",
            stderr=(
                "Command invokes shell interpretation and was not executed. "
                "Registry entries that intentionally need shell syntax must "
                f"set requires_shell=true. Set {_ALLOW_SHELL_ENV}=1 only after "
                "reviewing the registry entry and install command."
            ),
        )
    try:
        return subprocess.run(
            cmd if use_shell else argv,
            capture_output=True,
            text=True,
            shell=use_shell,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        missing = exc.filename or shlex.split(cmd)[0]
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=127,
            stdout="",
            stderr=f"Command not found: {missing}",
        )


def _command_exists(cmd):
    """Check whether the executable for a command string exists on PATH."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return False
    if not parts:
        return False
    return shutil.which(parts[0]) is not None


def _install_strategy(cli):
    """Return the install strategy for a CLI entry."""
    strategy = cli.get("install_strategy")
    if strategy:
        return strategy
    if cli.get("_source", "harness") == "harness":
        return "pip"
    if cli.get("npm_package") or cli.get("package_manager") == "npm":
        return "npm"
    if cli.get("package_manager") == "uv":
        return "uv"
    if cli.get("package_manager") == "bundled":
        return "bundled"
    return "command"


def _generic_install(cli):
    install_cmd = cli.get("install_cmd")
    if not install_cmd:
        return False, f"No install command is defined for {cli['display_name']}."
    cwd, cwd_error = _resolve_command_cwd(cli.get("install_cwd"))
    if cwd_error:
        return False, cwd_error
    result = _run_command(install_cmd, allow_shell=_allows_shell(cli), cwd=cwd)
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"Install failed:\n{result.stderr or result.stdout}"


def _resolve_command_cwd(value):
    """Resolve a reviewed registry working-directory marker."""
    if value is None:
        return None, None
    if value != "repository_root":
        return None, f"Unsupported registry command working directory: {value}"
    if not (REPOSITORY_ROOT / "registry.json").is_file():
        return None, (
            "This install requires a CLI-Anything source checkout; "
            "registry.json was not found beside the installed cli-hub package."
        )
    return REPOSITORY_ROOT, None


def _generic_uninstall(cli):
    uninstall_cmd = cli.get("uninstall_cmd")
    if not uninstall_cmd:
        note = cli.get("uninstall_notes") or f"No uninstall command is defined for {cli['display_name']}."
        return False, note
    result = _run_command(uninstall_cmd, allow_shell=_allows_shell(cli))
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"Uninstall failed:\n{result.stderr or result.stdout}"


def _generic_update(cli):
    update_cmd = cli.get("update_cmd")
    if not update_cmd:
        note = cli.get("update_notes") or f"No update command is defined for {cli['display_name']}."
        return False, note
    result = _run_command(update_cmd, allow_shell=_allows_shell(cli))
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']}"
    return False, f"Update failed:\n{result.stderr or result.stdout}"


def _bundled_install(cli):
    detect_cmd = cli.get("detect_cmd") or cli.get("entry_point")
    if detect_cmd and _command_exists(detect_cmd):
        return True, f"{cli['display_name']} is already available ({cli['entry_point']})"
    note = cli.get("install_notes") or (
        f"{cli['display_name']} is bundled with its parent app. "
        "Install or enable it in the upstream app first, then run this command again."
    )
    return False, note


def _bundled_uninstall(cli):
    note = cli.get("uninstall_notes") or (
        f"{cli['display_name']} is bundled with its parent app. "
        "Disable it in the upstream app or uninstall the parent app manually."
    )
    return False, note


def _bundled_update(cli):
    note = cli.get("update_notes") or (
        f"{cli['display_name']} is bundled with its parent app. "
        "Update the parent app to update this CLI."
    )
    return False, note


# ── pip operations (harness CLIs) ──


def _pip_install(cli):
    install_cmd = cli["install_cmd"]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install"] + install_cmd.replace("pip install ", "").split(),
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"pip install failed:\n{result.stderr}"


def _pip_uninstall(cli):
    pkg_name = f"cli-anything-{cli['name']}"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", pkg_name],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"pip uninstall failed:\n{result.stderr}"


def _pip_update(cli):
    install_cmd = cli["install_cmd"]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall"]
        + install_cmd.replace("pip install ", "").split(),
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']} to {cli['version']}"
    return False, f"Update failed:\n{result.stderr}"


# ── uv operations (public CLIs) ──


def _uv_install(cli):
    if _find_uv() is None:
        return False, _UV_INSTALL_HINT
    result = _run_command(cli["install_cmd"], allow_shell=_allows_shell(cli))
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"uv install failed:\n{result.stderr or result.stdout}"


def _uv_uninstall(cli):
    if _find_uv() is None:
        return False, _UV_INSTALL_HINT
    uninstall_cmd = cli.get("uninstall_cmd")
    if not uninstall_cmd:
        return False, f"No uninstall command is defined for {cli['display_name']}."
    result = _run_command(uninstall_cmd, allow_shell=_allows_shell(cli))
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"uv uninstall failed:\n{result.stderr or result.stdout}"


def _uv_update(cli):
    if _find_uv() is None:
        return False, _UV_INSTALL_HINT
    update_cmd = cli.get("update_cmd")
    if not update_cmd:
        return False, f"No update command is defined for {cli['display_name']}."
    result = _run_command(update_cmd, allow_shell=_allows_shell(cli))
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']}"
    return False, f"uv update failed:\n{result.stderr or result.stdout}"


# ── npm operations (public CLIs) ──


def _npm_install(cli):
    npm = _find_npm()
    if npm is None:
        return False, (
            "npm is not installed. Install Node.js first:\n"
            "  macOS: brew install node\n"
            "  Linux: curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs\n"
            "  Windows: Download from https://nodejs.org"
        )
    result = subprocess.run(
        [npm, "install", "-g", cli["npm_package"]],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Installed {cli['display_name']} ({cli['entry_point']})"
    return False, f"npm install failed:\n{result.stderr}"


def _npm_uninstall(cli):
    npm = _find_npm()
    if npm is None:
        return False, "npm is not installed."
    result = subprocess.run(
        [npm, "uninstall", "-g", cli["npm_package"]],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Uninstalled {cli['display_name']}"
    return False, f"npm uninstall failed:\n{result.stderr}"


def _npm_update(cli):
    npm = _find_npm()
    if npm is None:
        return False, "npm is not installed."
    result = subprocess.run(
        [npm, "install", "-g", cli["npm_package"] + "@latest"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, f"Updated {cli['display_name']} to latest"
    return False, f"Update failed:\n{result.stderr}"


def _perform_action(cli, action):
    """Dispatch install/uninstall/update based on CLI strategy."""
    strategy = _install_strategy(cli)
    actions = {
        "pip": {"install": _pip_install, "uninstall": _pip_uninstall, "update": _pip_update},
        "npm": {"install": _npm_install, "uninstall": _npm_uninstall, "update": _npm_update},
        "uv": {"install": _uv_install, "uninstall": _uv_uninstall, "update": _uv_update},
        "command": {"install": _generic_install, "uninstall": _generic_uninstall, "update": _generic_update},
        "bundled": {"install": _bundled_install, "uninstall": _bundled_uninstall, "update": _bundled_update},
    }
    handler = actions.get(strategy, actions["command"]).get(action)
    return strategy, handler(cli)


def _installed_entry(cli, source, strategy):
    """Return the installed.json payload for a CLI."""
    entry = {
        "version": cli["version"],
        "entry_point": cli["entry_point"],
        "source": source,
        "strategy": strategy,
    }
    if cli.get("package_manager"):
        entry["package_manager"] = cli["package_manager"]
    if cli.get("npm_package"):
        entry["npm_package"] = cli["npm_package"]
    if cli.get("install_cmd"):
        entry["install_cmd"] = cli["install_cmd"]
    if cli.get("uninstall_cmd"):
        entry["uninstall_cmd"] = cli["uninstall_cmd"]
    if cli.get("update_cmd"):
        entry["update_cmd"] = cli["update_cmd"]
    if cli.get("requires_shell") is True:
        entry["requires_shell"] = True
    return entry


# ── Unified interface ──


def install_cli(name):
    """Install a CLI by name. Dispatches to pip or npm based on source. Returns (success, message)."""
    cli = get_cli(name)
    if cli is None:
        return False, f"CLI '{name}' not found in registry. Use 'cli-hub list' to see available CLIs."

    source = cli.get("_source", "harness")
    strategy, (success, msg) = _perform_action(cli, "install")

    if success:
        installed = _load_installed()
        installed[cli["name"]] = _installed_entry(cli, source, strategy)
        _save_installed(installed)

    return success, msg


def uninstall_cli(name):
    """Uninstall a CLI by name. Returns (success, message)."""
    cli = get_cli(name)
    if cli is None:
        return False, f"CLI '{name}' not found in registry."

    _, (success, msg) = _perform_action(cli, "uninstall")

    if success:
        installed = _load_installed()
        installed.pop(cli["name"], None)
        _save_installed(installed)

    return success, msg


def update_cli(name):
    """Update a CLI by reinstalling. Returns (success, message)."""
    cli = get_cli(name, force_refresh=True)
    if cli is None:
        return False, f"CLI '{name}' not found in registry."

    source = cli.get("_source", "harness")
    strategy, (success, msg) = _perform_action(cli, "update")

    if success:
        installed = _load_installed()
        installed[cli["name"]] = _installed_entry(cli, source, strategy)
        _save_installed(installed)

    return success, msg


def get_installed():
    """Return dict of installed CLIs."""
    return _load_installed()


def _scope_label(scope, capabilities=None):
    """Human-readable label for an install scope (used in state + output)."""
    scope_type = scope.get("type")
    if scope_type == "capability":
        return f"capability {scope.get('value')}"
    if scope_type == "recipe":
        return f"recipe {scope.get('value')}"
    if scope_type == "only":
        return f"only {', '.join(scope.get('value', []))}"
    return "full matrix"


def plan_matrix_install(name, capability=None, recipe=None, only=None):
    """Compute what ``matrix install`` would do — no side effects (F2.1).

    Returns ``(ok, payload)``. ``ok`` is false only on lookup/usage errors;
    ``payload['arg_error']`` distinguishes usage errors (exit 2) from not-found.
    """
    matrix_item = get_matrix(name)
    if matrix_item is None:
        return False, {"error": f"Matrix '{name}' not found. Use 'cli-hub matrix list' to see available matrices."}

    scope = resolve_install_scope(matrix_item, capability=capability, recipe=recipe, only=only)
    if scope.get("error"):
        return False, {"error": scope["error"], "arg_error": True, "matrix": matrix_item}

    installed = set(get_installed())
    plan = []
    for cli_name in scope["cli_names"]:
        cli = get_cli(cli_name)
        if cli_name in installed:
            action, via = "skip", (_install_strategy(cli) if cli else None)
        elif cli is None:
            action, via = "error", None
        else:
            action, via = "install", _install_strategy(cli)
        plan.append({
            "name": cli_name,
            "display_name": cli["display_name"] if cli else cli_name,
            "action": action,
            "via": via,
            "already_installed": cli_name in installed,
            "found": cli is not None,
        })

    scope_caps = scope.get("capabilities")
    cap_objs = None
    if scope_caps is not None and scope["scope"].get("type") in {"capability", "recipe"}:
        cap_set = set(scope_caps)
        cap_objs = [c for c in matrix_item.get("capabilities", []) if c.get("id") in cap_set]
    not_managed = unmanaged_providers(matrix_item, cap_objs)

    summary = {
        "total": len(plan),
        "to_install": sum(1 for p in plan if p["action"] == "install"),
        "to_skip": sum(1 for p in plan if p["action"] == "skip"),
        "unresolved": sum(1 for p in plan if p["action"] == "error"),
    }
    payload = {
        "matrix": matrix_item,
        "scope": scope["scope"],
        "scope_label": _scope_label(scope["scope"]),
        "plan": plan,
        "not_managed": not_managed,
        "summary": summary,
    }
    return True, payload


def install_matrix(name, capability=None, recipe=None, only=None, resume=False):
    """Install the CLIs in a named matrix, optionally scoped (F2.2) or resumed (F2.3).

    Returns ``(success, payload)``. ``payload['arg_error']`` marks usage errors.
    Records per-CLI outcomes to ``matrix_state.json`` so ``--resume`` and
    ``matrix doctor`` can act on them.
    """
    matrix_item = get_matrix(name)
    if matrix_item is None:
        return False, {"error": f"Matrix '{name}' not found. Use 'cli-hub matrix list' to see available matrices."}

    state = _load_matrix_state()

    if resume:
        if capability or recipe or only:
            return False, {"error": "Cannot combine --resume with --capability/--recipe/--only.",
                           "arg_error": True, "matrix": matrix_item}
        prior = state.get(name)
        if not prior:
            return False, {"error": f"No previous install of '{name}' to resume. "
                                    f"Run 'cli-hub matrix install {name}' first.",
                           "arg_error": True, "matrix": matrix_item}
        target_names = [r["name"] for r in prior.get("results", []) if r.get("status") == "failed"]
        scope = prior.get("scope", {"type": "all"})
        if not target_names:
            return True, {"matrix": matrix_item, "results": [], "scope": scope,
                          "scope_label": _scope_label(scope),
                          "summary": {"total": 0, "installed": 0, "skipped": 0, "failed": 0},
                          "resumed": True, "nothing_to_resume": True}
    else:
        scope_info = resolve_install_scope(matrix_item, capability=capability, recipe=recipe, only=only)
        if scope_info.get("error"):
            return False, {"error": scope_info["error"], "arg_error": True, "matrix": matrix_item}
        target_names = scope_info["cli_names"]
        scope = scope_info["scope"]

    installed = set(get_installed())
    results = []

    for cli_name in target_names:
        cli = get_cli(cli_name)
        display_name = cli["display_name"] if cli else cli_name
        via = _install_strategy(cli) if cli else None

        if cli_name in installed:
            results.append({"name": cli_name, "display_name": display_name,
                            "status": "skipped", "via": via, "message": "Already installed"})
            continue

        if cli is None:
            results.append({"name": cli_name, "display_name": display_name,
                            "status": "failed", "via": via, "message": "CLI not found in registry"})
            continue

        success, msg = install_cli(cli_name)
        results.append({"name": cli_name, "display_name": display_name,
                        "status": "installed" if success else "failed", "via": via, "message": msg})
        if success:
            installed.add(cli_name)

    summary = {
        "total": len(results),
        "installed": sum(1 for result in results if result["status"] == "installed"),
        "skipped": sum(1 for result in results if result["status"] == "skipped"),
        "failed": sum(1 for result in results if result["status"] == "failed"),
    }

    state[name] = {
        "last_run": datetime.now().isoformat(timespec="seconds"),
        "scope": scope,
        "results": results,
    }
    _save_matrix_state(state)

    installed_state = get_installed()
    rendered_skill_path = render_matrix_skill_file(matrix_item, installed=installed_state)
    payload = {
        "matrix": matrix_item,
        "results": results,
        "scope": scope,
        "scope_label": _scope_label(scope),
        "summary": summary,
        "resumed": resume,
        "rendered_skill_path": str(rendered_skill_path),
    }
    return summary["failed"] == 0, payload


def doctor_matrix(name):
    """Audit install completeness for a matrix's CLIs against the environment (F2.3).

    Unlike preflight (which reports provider availability for selection), doctor
    checks whether the matrix's own ``clis[]`` are installed and on PATH, and
    emits a fix command per broken/missing member.
    """
    matrix_item = get_matrix(name)
    if matrix_item is None:
        return False, {"error": f"Matrix '{name}' not found. Use 'cli-hub matrix list' to see available matrices."}

    installed = get_installed()
    state = _load_matrix_state().get(name)
    checks = []
    for cli_name in matrix_item.get("clis", []):
        cli = get_cli(cli_name)
        entry_point = cli.get("entry_point") if cli else None
        record = installed.get(cli_name)

        if record is None:
            status = "not_installed"
            detail = "Not installed"
            fix = f"cli-hub install {cli_name}"
        elif entry_point and not _command_exists(entry_point):
            status = "broken"
            detail = f"Recorded as installed but '{entry_point}' is not on PATH"
            fix = f"cli-hub install {cli_name}"
        else:
            status = "ok"
            detail = "Installed"
            fix = None

        checks.append({
            "name": cli_name,
            "entry_point": entry_point,
            "status": status,
            "detail": detail,
            "fix": fix,
        })

    summary = {
        "total": len(checks),
        "ok": sum(1 for check in checks if check["status"] == "ok"),
        "broken": sum(1 for check in checks if check["status"] == "broken"),
        "not_installed": sum(1 for check in checks if check["status"] == "not_installed"),
    }
    payload = {
        "matrix": matrix_item,
        "last_run": state.get("last_run") if state else None,
        "checks": checks,
        "summary": summary,
    }
    healthy = summary["broken"] == 0 and summary["not_installed"] == 0
    return healthy, payload
