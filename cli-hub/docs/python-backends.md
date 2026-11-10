# Python harness backends

CLI-Hub can manage Python harnesses using either pip or uv tools. The registry's
`install_strategy: pip` (also the default for harnesses) describes a Python
package source. `python_backend` in the local installation record identifies
the engine that owns the installed package.

## Selection and ownership

| Operation | `--backend auto` behavior |
| --- | --- |
| New Python harness install | Use uv when available on PATH, otherwise the current Python's pip |
| Install/update/uninstall with a backend record | Keep the recorded backend |
| Existing installation recorded by an older Hub | Keep pip; older records do not identify their original interpreter |
| Update/uninstall without a local record | Keep legacy pip behavior |
| Non-Python strategy | Use the existing npm, command, bundled, or public-uv handler |

Use `--backend pip` or `--backend uv` for an explicit choice. An override cannot
move an already tracked installation into another backend: uninstall it first,
then reinstall with the desired backend. Explicit Python backend overrides on
individual non-Python CLIs return an error. For matrices, `--backend` applies
only to Python members; npm and other members keep their own strategies.
Already installed matrix members are still skipped, with their recorded backend
shown in the plan.
An explicit matrix backend is saved with the attempt and reused by `--resume`
unless another backend is explicitly requested for the failed members.

`--backend uv` can update or remove an untracked uv tool if its console entry
point uniquely identifies an installed distribution. Untracked auto-mode updates
and removals intentionally retain the older pip behavior.

## Package commands

- uv installation: `uv tool install <package-source>`, with supported options
  translated from the registry's pip command. It creates an isolated tool
  environment and exposes its commands in uv's tool binary directory.
- uv update: `uv tool upgrade --reinstall <recorded-distribution>`. This uses the
  requirement in uv's receipt, retaining its original source and version pins.
  A new registry source or a changed pin requires uninstall/reinstall. The Hub
  retains the original recorded install command and records the resolved version
  reported by uv, rather than assuming the registry version was installed.
- uv removal: `uv tool uninstall <recorded-distribution>`.
- pip operations: `<owning-python> -m pip install`, `install --upgrade
  --force-reinstall`, or `uninstall -y`. New pip records save the owning
  interpreter's path. If that interpreter disappears, the operation fails
  instead of targeting another environment.

After a successful uv install/update, the Hub reads `uv tool list --color never`
to resolve the exact distribution owning the registered executable. Registry
slugs, console scripts, and distribution names can differ. Missing or ambiguous
ownership makes the operation report a verification failure; no successful local
record is written. The package-manager operation may already have completed in
that case, so inspect `uv tool list` before retrying or removing the tool.

The tool-list parser uses uv's package-header and executable-line format; uv does
not currently expose JSON for this command. Windows `.exe` executable suffixes
are accepted. Changes to that upstream format fail verification rather than
guessing a distribution to update or remove.

## Registry command support

The Python path accepts `pip install`, `pip3 install`, and `python -m pip install`
spellings, including versioned Python executables. Quoted package sources, VCS
references, and `#subdirectory=` fragments remain single arguments. No shell is
used for these operations.

uv translation accepts one package source and these pip options:

- `-U` / `--upgrade`, `--force-reinstall`, `--no-cache-dir`, `--pre`
- `-e` / `--editable`, `--no-index`, `--no-build-isolation`
- `-i` / `--index-url`, `--extra-index-url`, `-f` / `--find-links`

Multiple sources, requirements files, `--user`, `--target`, and other options that
cannot be translated without changing their meaning return an error suggesting
`--backend pip`. Explicit pip mode retains the original argument list. Existing
pip tracking remains one record per registry CLI; it is not a dependency or
multi-package lockfile.

Public CLIs that already declare an explicit uv strategy continue to use their
registry-defined install/update/uninstall commands. This feature does not change
generic command/script installation policy.

## Reports and failures

`install`, `update`, and `uninstall` accept `--json` and return one object with
`name`, `action`, `success`, `message`, and `installation`. Successful installs
and updates include selected installation metadata (backend, distribution,
version, and entry point); removal and failure reports have a null installation.
Successful operations exit 0, backend/lookup failures exit 1, and invalid CLI
options exit 2. Matrix commands retain their existing JSON/partial-failure
contract.

Installation records change only after a successful backend operation and any
required ownership verification. A failed uv operation never falls back to pip.
Mutating package commands reject malformed installation records before running
a package manager, so an unreadable receipt cannot trigger a backend switch.
If uv is missing for an existing uv installation, restore uv on PATH and retry.
The Hub does not install uv, alter PATH, edit shell startup files, or replace an
existing tool executable using uv's `--force` flag.

## Tests

```bash
PYTHONPATH=cli-hub python -m pytest cli-hub/tests -q
```

`test_python_tools.py` covers backend selection, command translation, state
ownership, CLI JSON/error behavior, and matrix plans. `test_python_tools_e2e.py`
builds a dependency-free wheel locally and runs real install/execute/update/remove
cycles in temporary uv directories and a temporary pip venv. The tests use
offline mode and do not install application harnesses or modify user packages.
The uv test skips only when uv is unavailable; the pip test requires Python's
venv/ensurepip support.
