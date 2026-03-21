# cli-anything · Git

## Overview

This harness wraps **Git** (git) into a REPL-driven
CLI interface following the cli-anything methodology.

## Installation

```bash
# Install the binary
# (refer to your OS package manager)
# e.g. apt install git

# Install the harness
cd /tmp/CLI-Anything/git/agent-harness
pip install -e .
```

## Quick Start

```bash
# Launch the REPL
cli-anything-git

# Or use one-shot commands
cli-anything-git --json <command>
```

## Available Commands

- `status`
- `log --limit N`
- `diff`
- `branches`
- `checkout <branch>`
- `add <files...>`
- `commit --message M`
- `push`
- `pull`
- `stash save`
- `stash list`
- `stash pop`
- `remotes`
- `tags`

## Architecture

The harness uses subprocess to call git, providing
a session layer with undo/redo and structured output.

## License

MIT
