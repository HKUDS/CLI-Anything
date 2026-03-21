# Git CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to Git (git).

## Commands
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

## Usage Pattern
All commands use subprocess to call git.
Session provides undo/redo via snapshots.
