# GPG CLI-Anything Harness — Architecture SOP

## Overview
GnuPG encryption, signing, and key management via CLI-Anything harness.

## Directory Layout
```
gpg/agent-harness/
├── setup.py                          # Package setup
├── GPG.md                            # This file
└── cli_anything/
    └── gpg/
        ├── __init__.py
        ├── __main__.py               # Entry point
        ├── gpg_cli.py                # Click CLI with REPL
        ├── README.md
        ├── core/
        │   ├── __init__.py
        │   ├── session.py            # Session with undo/redo
        │   ├── keys.py               # Key management functions
        │   └── crypto.py             # Encrypt/decrypt/sign/verify
        ├── utils/
        │   ├── __init__.py
        │   └── repl_skin.py          # Terminal UI styling
        ├── skills/
        │   └── SKILL.md              # Skill documentation
        └── tests/
            ├── __init__.py
            └── test_core.py          # Unit tests
```

## Core Modules

### `keys.py` — Key Management
All functions call `gpg` via `subprocess.run()` with `--batch --yes`.

| Function | gpg args | Returns |
|----------|---------|---------|
| `key_list(secret)` | `--list-keys --with-colons` | List of key dicts |
| `key_generate(name, email, ...)` | `--gen-key` with batch input | Result dict |
| `key_export(key_id)` | `--armor --export` | ASCII armored key string |
| `key_export_secret(key_id)` | `--armor --export-secret-keys` | ASCII armored key string |
| `key_import(file)` | `--import` | Import result dict |
| `key_delete(key_id, secret)` | `--delete-keys` / `--delete-secret-and-public-key` | Result dict |
| `key_trust(key_id, level)` | `--import-ownertrust` | Result dict |
| `key_fingerprint(key_id)` | `--fingerprint --with-colons` | Fingerprint string |

### `crypto.py` — Encryption & Signing

| Function | gpg args | Returns |
|----------|---------|---------|
| `encrypt(file, recipient)` | `--encrypt --recipient` | Result dict |
| `decrypt(file)` | `--decrypt` | Result dict |
| `sign(file, key_id)` | `--detach-sign` | Result dict |
| `verify(file, sig_file)` | `--verify` | Verification result dict |
| `clearsign(file, key_id)` | `--clearsign` | Result dict |
| `detach_sign(file, key_id)` | `--detach-sign --armor` | Result dict |

## Session Model
- `Session` class tracks a JSON project with undo/redo stacks (max 50)
- `snapshot()` before mutations; `undo()`/`redo()` to navigate history
- `save_session()` writes JSON with file locking

## CLI Design
- Click groups: `key`, `encrypt`, `decrypt`, `sign`, `verify`, `clearsign`, `detach-sign`, `status`, `repl`
- `--json` flag for machine-readable output
- REPL with prompt-toolkit, command history, auto-suggest
- `handle_error` decorator catches exceptions consistently

## Testing
```bash
cd /tmp/CLI-Anything/gpg/agent-harness
python3 -m pytest cli_anything/gpg/tests/ -v
```
