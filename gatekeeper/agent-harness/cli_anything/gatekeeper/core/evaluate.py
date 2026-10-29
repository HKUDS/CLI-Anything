"""evaluate.py — run a Gatekeeper evaluation and save the report."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from cli_anything.gatekeeper.core import extract, session
from cli_anything.gatekeeper.utils import gk_backend as gk

CRITERIA = ("technical", "pricing", "delivery", "hse", "experience", "commercial")
DEFAULT_WEIGHTS = {"technical": 25, "pricing": 20, "delivery": 15, "hse": 15,
                   "experience": 10, "commercial": 15}

EXIT_AUTH = 2     # 401 — sign in again
EXIT_QUOTA = 3    # 402 — plan limit / Professional feature


def parse_weights(spec: str | None) -> dict[str, int] | None:
    """Parse "technical=30,pricing=15" over the defaults.

    Mirrors the website: returns None when the result equals the defaults
    (so Starter users are never blocked by weights they didn't change), and
    raises if the six criteria don't sum to 100.
    """
    if not spec:
        return None
    w = dict(DEFAULT_WEIGHTS)
    for part in spec.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Bad weight '{part}' — use criterion=percent")
        k, v = (s.strip().lower() for s in part.split("=", 1))
        if k not in CRITERIA:
            raise ValueError(f"Unknown criterion '{k}'. Use: {', '.join(CRITERIA)}")
        try:
            f = float(v)
        except ValueError as exc:
            raise ValueError(f"Weight for {k} must be a number") from exc
        # Whole percentages only ("25" or "25.0"). Truncating 25.9 → 25 would
        # silently change the scoring model, or turn a 100.x% total into 100.
        if not f.is_integer():
            raise ValueError(f"Weight for {k} must be a whole percentage (got {v})")
        n = int(f)
        if n < 0 or n > 100:
            raise ValueError(f"Weight for {k} must be 0-100")
        w[k] = n
    total = sum(w.values())
    if total != 100:
        raise ValueError(f"Scoring weights must add up to 100% (got {total}): "
                         + ", ".join(f"{k}={v}" for k, v in w.items()))
    return None if w == DEFAULT_WEIGHTS else w


def build_payload(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    bad = [e["name"] for e in entries if not e["content"].strip()]
    if bad:
        raise extract.ExtractError(
            "Remove or replace files with no readable text: " + ", ".join(bad))
    return [{"name": e["name"], "content": e["content"]} for e in entries]


def run(paths: list[str], weights_spec: str | None = None,
        output: str | None = None, timeout: float | None = None,
        on_start=None) -> dict[str, Any]:
    entries = extract.extract_many(paths)
    documents = build_payload(entries)
    weights = parse_weights(weights_spec)
    token = session.get_token(required=True)

    if on_start:
        on_start(len(documents))
    t0 = time.time()
    status, data = gk.evaluate(documents, token, weights=weights, timeout=timeout)
    wall_ms = int((time.time() - t0) * 1000)

    if status == 401:
        raise gk.GatekeeperError("Session expired or invalid — run `auth login` again.", 401, data)
    if status == 402:
        msg = (data or {}).get("message") if isinstance(data, dict) else None
        raise gk.GatekeeperError(
            (msg or "Plan limit reached.") + " Upgrade: " + gk.base_url() + "/pricing", 402, data)
    if status >= 400 or not isinstance(data, dict) or not data.get("success"):
        err = data.get("error") if isinstance(data, dict) else str(data)[:300]
        raise gk.GatekeeperError(f"Evaluation failed (HTTP {status}): {err or 'unknown error'}",
                                 status, data)

    data.setdefault("cli", {})
    data["cli"].update({"wall_time_ms": wall_ms, "inputs": extract.summarize(entries)["files"],
                        "weights_sent": weights, "base_url": gk.base_url()})
    if output:
        out = Path(output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        data["cli"]["saved_to"] = str(out.resolve())
    return data
