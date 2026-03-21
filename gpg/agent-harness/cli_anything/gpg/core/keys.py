"""GPG key management core."""

import subprocess
import json
import os
from typing import Any, Dict, List, Optional


def _run_gpg(
    args: List[str], stdin_data: Optional[str] = None, timeout: int = 60
) -> Dict[str, Any]:
    """Run gpg with given args and return stdout/stderr."""
    cmd = ["gpg", "--batch", "--yes"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_data if stdin_data else None,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except FileNotFoundError:
        raise RuntimeError("gpg not found. Install gpg: apt install gpg")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"gpg timed out after {timeout}s")


def key_list(secret: bool = False) -> List[Dict[str, Any]]:
    """List keys (--secret for secret keys)."""
    args = ["--list-keys"]
    if secret:
        args = ["--list-secret-keys"]
    args.extend(["--with-colons", "--fixed-list-mode"])
    res = _run_gpg(args)
    if not res["ok"] and "No secret keys" in res["stderr"] and secret:
        return []
    if not res["ok"] and "No public keys" in res["stderr"]:
        return []
    keys = []
    current = None
    for line in res["stdout"].splitlines():
        parts = line.split(":")
        record_type = parts[0] if parts else ""
        if record_type in ("pub", "sec"):
            if current:
                keys.append(current)
            current = {
                "validity": parts[1] if len(parts) > 1 else "",
                "key_length": parts[2] if len(parts) > 2 else "",
                "algorithm": parts[3] if len(parts) > 3 else "",
                "key_id": parts[4] if len(parts) > 4 else "",
                "creation_date": parts[5] if len(parts) > 5 else "",
                "expiration_date": parts[6] if len(parts) > 6 else "",
                "uid": "",
                "fingerprint": "",
                "type": "secret" if secret else "public",
            }
        elif record_type == "uid" and current and not current["uid"]:
            current["uid"] = parts[9] if len(parts) > 9 else ""
        elif record_type == "fpr" and current and not current["fingerprint"]:
            current["fingerprint"] = parts[9] if len(parts) > 9 else ""
    if current:
        keys.append(current)
    return keys


def key_generate(
    name: str,
    email: str,
    key_type: str = "RSA",
    key_length: int = 2048,
    passphrase: str = "",
) -> Dict[str, Any]:
    """Generate new key pair."""
    algo_map = {"RSA": "rsa", "ED25519": "ed25519"}
    algo = algo_map.get(key_type.upper(), "rsa")
    if algo == "ed25519":
        key_params = "Key-Type: EDDSA\nKey-Curve: Ed25519"
    else:
        key_params = f"Key-Type: RSA\nKey-Length: {key_length}"
    batch_input = f"""{key_params}
Subkey-Type: {"EDDSA" if algo == "ed25519" else "RSA"}
Subkey-Length: {key_length}
Name-Real: {name}
Name-Email: {email}
Expire-Date: 0
%no-protection
%commit
"""
    res = _run_gpg(["--gen-key"], stdin_data=batch_input, timeout=120)
    if not res["ok"]:
        raise RuntimeError(f"Key generation failed: {res['stderr'].strip()}")
    return {
        "ok": True,
        "name": name,
        "email": email,
        "type": key_type,
        "length": key_length,
        "message": res["stderr"].strip(),
    }


def key_export(key_id: str) -> str:
    """Export public key."""
    res = _run_gpg(["--armor", "--export", key_id])
    if not res["ok"]:
        raise RuntimeError(f"Export failed: {res['stderr'].strip()}")
    if not res["stdout"].strip():
        raise RuntimeError(f"No public key found for: {key_id}")
    return res["stdout"]


def key_export_secret(key_id: str) -> str:
    """Export secret key."""
    res = _run_gpg(["--armor", "--export-secret-keys", key_id])
    if not res["ok"]:
        raise RuntimeError(f"Export failed: {res['stderr'].strip()}")
    if not res["stdout"].strip():
        raise RuntimeError(f"No secret key found for: {key_id}")
    return res["stdout"]


def key_import(file: str) -> Dict[str, Any]:
    """Import a key from file."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    res = _run_gpg(["--import", file])
    imported = 0
    for line in res["stderr"].splitlines():
        if "imported:" in line.lower() or "imported" in line.lower():
            imported += 1
    return {"ok": res["ok"], "imported": imported, "details": res["stderr"].strip()}


def key_delete(key_id: str, secret: bool = False) -> Dict[str, Any]:
    """Delete a key."""
    if secret:
        res = _run_gpg(["--delete-secret-and-public-key", key_id])
    else:
        res = _run_gpg(["--delete-keys", key_id])
    if not res["ok"]:
        raise RuntimeError(f"Delete failed: {res['stderr'].strip()}")
    return {
        "ok": True,
        "deleted": key_id,
        "type": "secret+public" if secret else "public",
    }


def key_trust(key_id: str, level: int = 5) -> Dict[str, Any]:
    """Set trust level for a key (1=unknown, 2=never, 3=marginal, 4=full, 5=ultimate)."""
    trust_input = f"{key_id}:{level}:\n"
    res = _run_gpg(["--import-ownertrust"], stdin_data=trust_input)
    if not res["ok"]:
        raise RuntimeError(f"Trust setting failed: {res['stderr'].strip()}")
    return {"ok": True, "key_id": key_id, "trust_level": level}


def key_fingerprint(key_id: str) -> str:
    """Show key fingerprint."""
    res = _run_gpg(["--fingerprint", "--with-colons", key_id])
    if not res["ok"]:
        raise RuntimeError(f"Fingerprint failed: {res['stderr'].strip()}")
    for line in res["stdout"].splitlines():
        if line.startswith("fpr:"):
            parts = line.split(":")
            if len(parts) > 9:
                return parts[9]
    raise RuntimeError(f"No fingerprint found for: {key_id}")
