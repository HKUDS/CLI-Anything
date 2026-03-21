# cli-anything · GPG

GnuPG encryption, signing, and key management.

## Install
```bash
cd /tmp/CLI-Anything/gpg/agent-harness
pip install -e .
```

## Quick Start
```bash
# Interactive REPL
python -m cli_anything.gpg

# Key management
python -m cli_anything.gpg key list
python -m cli_anything.gpg key generate "Alice" "alice@example.com" --type ED25519
python -m cli_anything.gpg key export alice@example.com
python -m cli_anything.gpg key import pubkey.asc
python -m cli_anything.gpg key fingerprint alice@example.com

# Encryption
python -m cli_anything.gpg encrypt secret.txt -r alice@example.com
python -m cli_anything.gpg decrypt secret.txt.gpg

# Signing
python -m cli_anything.gpg sign document.pdf -k alice@example.com
python -m cli_anything.gpg verify document.pdf.sig
python -m cli_anything.gpg clearsign message.txt

# JSON output
python -m cli_anything.gpg --json key list
```

## Requirements
- Python >= 3.10
- gpg (`apt install gpg`) — typically pre-installed

## License
MIT
