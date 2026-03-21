# CMake CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to CMake (cmake).

## Commands
- `configure <src> --build-dir D`
- `build <dir>`
- `install <dir>`
- `clean <dir>`
- `variables <dir>`
- `targets <dir>`

## Usage Pattern
All commands use subprocess to call cmake.
Session provides undo/redo via snapshots.
