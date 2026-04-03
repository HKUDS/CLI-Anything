#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_skills.intel_runtime import CONTRACT_VERSION, DEFAULT_BASE_URL, RuntimeContractError, build_skill_envelope  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime-backed Deep Scavenger skill adapter.")
    parser.add_argument("--skill", required=True, choices=["intel-duty-officer", "source-health-triage", "briefing-analyst"])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--target", help="Bounded target for triage skills, such as a source key, scoring_pipeline, local_ai_control_plane, watchdog, or control_plane_alerts.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        payload = build_skill_envelope(args.skill, base_url=args.base_url, target=args.target)
    except RuntimeContractError as exc:
        payload = {
            "skill_name": args.skill,
            "contract_version": CONTRACT_VERSION,
            "status": "failed",
            "summary": f"{args.skill} failed to read required runtime contracts.",
            "findings": [],
            "evidence": [],
            "confidence": "unknown",
            "next_actions": ["Inspect runtime availability and contract shape before retrying."],
            "errors": [{"code": "runtime_contract_error", "message": str(exc), "recoverable": True}],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
