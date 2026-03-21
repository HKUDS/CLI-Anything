# GPG Skill

## Category
crypto

## Description
GnuPG encryption, signing, and key management. Provides a structured CLI interface for all common GPG operations including key generation, import/export, encryption, decryption, and signing.

## Requirements
- `gpg` must be installed (`apt install gpg`) — typically pre-installed

## Commands

### Key Management
- `key list [--secret]` — List keys (public or secret)
- `key generate <name> <email> [--type RSA|ED25519] [--length N]` — Generate new key pair
- `key export <key-id>` — Export public key (ASCII armored)
- `key export-secret <key-id>` — Export secret key (ASCII armored)
- `key import <file>` — Import a key from file
- `key delete <key-id> [--secret]` — Delete a key
- `key trust <key-id> [--level 1-5]` — Set trust level
- `key fingerprint <key-id>` — Show key fingerprint

### Encryption / Decryption
- `encrypt <file> -r <key-id> [-o output]` — Encrypt a file
- `decrypt <file> [-o output]` — Decrypt a file

### Signing / Verification
- `sign <file> [-k key-id] [-o output]` — Create detached signature
- `verify <file> [--sig-file sig]` — Verify a signature
- `clearsign <file> [-k key-id] [-o output]` — Create cleartext signature
- `detach-sign <file> [-k key-id] [-o output]` — Create detached ASCII signature

## Usage
```bash
python -m cli_anything.gpg key list
python -m cli_anything.gpg key generate "Alice" "alice@example.com" --type ED25519
python -m cli_anything.gpg key export alice@example.com
python -m cli_anything.gpg encrypt secret.txt -r alice@example.com
python -m cli_anything.gpg decrypt secret.txt.gpg
python -m cli_anything.gpg sign document.pdf -k alice@example.com
python -m cli_anything.gpg verify document.pdf.sig
```

## Architecture
- Key management functions in `core/keys.py` call gpg via subprocess
- Crypto operations in `core/crypto.py` (encrypt, decrypt, sign, verify)
- Session management with undo/redo in `core/session.py`
- REPL with prompt-toolkit for interactive use
