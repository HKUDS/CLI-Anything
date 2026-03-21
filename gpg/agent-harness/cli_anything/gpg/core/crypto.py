"""GPG encryption, signing, and verification core."""

import subprocess
import os
from typing import Any, Dict, Optional


def _run_gpg(
    args: list, stdin_data: Optional[str] = None, timeout: int = 60
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


def encrypt(file: str, recipient: str, output: Optional[str] = None) -> Dict[str, Any]:
    """Encrypt a file for a recipient."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    if not output:
        output = file + ".gpg"
    args = ["--encrypt", "--recipient", recipient, "--output", output, file]
    res = _run_gpg(args)
    if not res["ok"]:
        raise RuntimeError(f"Encryption failed: {res['stderr'].strip()}")
    return {"ok": True, "input": file, "output": output, "recipient": recipient}


def decrypt(file: str, output: Optional[str] = None) -> Dict[str, Any]:
    """Decrypt a file."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    if not output:
        if file.endswith(".gpg"):
            output = file[:-4]
        else:
            output = file + ".dec"
    args = ["--decrypt", "--output", output, file]
    res = _run_gpg(args)
    if not res["ok"]:
        raise RuntimeError(f"Decryption failed: {res['stderr'].strip()}")
    return {"ok": True, "input": file, "output": output}


def sign(
    file: str, key_id: Optional[str] = None, output: Optional[str] = None
) -> Dict[str, Any]:
    """Sign a file (creates .sig detached by default, or clearsign)."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    if not output:
        output = file + ".sig"
    args = ["--detach-sign"]
    if key_id:
        args.extend(["--local-user", key_id])
    args.extend(["--output", output, file])
    res = _run_gpg(args)
    if not res["ok"]:
        raise RuntimeError(f"Signing failed: {res['stderr'].strip()}")
    return {"ok": True, "input": file, "output": output, "key": key_id}


def verify(file: str, sig_file: Optional[str] = None) -> Dict[str, Any]:
    """Verify a signature."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    args = ["--verify"]
    if sig_file:
        if not os.path.isfile(sig_file):
            raise FileNotFoundError(f"Signature file not found: {sig_file}")
        args.extend([sig_file, file])
    else:
        args.append(file)
    res = _run_gpg(args)
    verified = res["ok"]
    signer = ""
    for line in res["stderr"].splitlines():
        if "Good signature from" in line:
            verified = True
            signer = line.strip()
        elif "BAD signature" in line:
            verified = False
    return {
        "ok": verified,
        "input": file,
        "signature_file": sig_file,
        "signer": signer,
        "details": res["stderr"].strip(),
    }


def clearsign(
    file: str, key_id: Optional[str] = None, output: Optional[str] = None
) -> Dict[str, Any]:
    """Create cleartext signature."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    if not output:
        output = file + ".asc"
    args = ["--clearsign"]
    if key_id:
        args.extend(["--local-user", key_id])
    args.extend(["--output", output, file])
    res = _run_gpg(args)
    if not res["ok"]:
        raise RuntimeError(f"Clearsign failed: {res['stderr'].strip()}")
    return {"ok": True, "input": file, "output": output, "key": key_id}


def detach_sign(
    file: str, key_id: Optional[str] = None, output: Optional[str] = None
) -> Dict[str, Any]:
    """Create detached signature."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    if not output:
        output = file + ".sig"
    args = ["--detach-sign", "--armor"]
    if key_id:
        args.extend(["--local-user", key_id])
    args.extend(["--output", output, file])
    res = _run_gpg(args)
    if not res["ok"]:
        raise RuntimeError(f"Detached sign failed: {res['stderr'].strip()}")
    return {"ok": True, "input": file, "output": output, "key": key_id}
