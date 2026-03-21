# Nmap CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to Nmap (nmap).

## Commands
- `scan <target>`
- `scan <target> --ports P`
- `scan <target> --top-ports N`
- `os-detect <target>`
- `service <target>`
- `ping <target>`

## Usage Pattern
All commands use subprocess to call nmap.
Session provides undo/redo via snapshots.
