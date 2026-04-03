from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable
from urllib import error, request


DEFAULT_BASE_URL = "http://127.0.0.1:8767"
CONTRACT_VERSION = "2026-04-03.v1"


class RuntimeContractError(RuntimeError):
    """Raised when a required runtime-backed contract is unavailable or invalid."""


FetchJson = Callable[[str, int], Any]

_REGISTRY_PATH = Path(__file__).resolve().with_name("intel_tool_registry.json")


def _load_tool_registry_from_disk() -> dict[str, Any]:
    try:
        registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - packaging failure
        raise RuntimeContractError(f"intel tool registry is missing: {_REGISTRY_PATH}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - packaging failure
        raise RuntimeContractError(f"intel tool registry is invalid JSON: {_REGISTRY_PATH}") from exc

    if not isinstance(registry, dict):
        raise RuntimeContractError("intel tool registry must be a JSON object")

    tools = registry.get("tools")
    if not isinstance(tools, list) or not tools:
        raise RuntimeContractError("intel tool registry must include a non-empty tools array")

    for descriptor in tools:
        if not isinstance(descriptor, dict):
            raise RuntimeContractError("intel tool registry contains a non-object tool descriptor")
        name = descriptor.get("name")
        surface = descriptor.get("surface")
        if not isinstance(name, str) or not name.strip():
            raise RuntimeContractError("intel tool registry contains a tool without a valid name")
        if not isinstance(surface, dict) or not isinstance(surface.get("path"), str):
            raise RuntimeContractError(f"intel tool registry tool {name!r} is missing surface.path")

    return registry


_INTEL_TOOL_REGISTRY = _load_tool_registry_from_disk()
_TOOL_DESCRIPTORS = {
    str(descriptor["name"]).strip(): descriptor
    for descriptor in _INTEL_TOOL_REGISTRY["tools"]
}
TOOL_NAMES = {
    tool_name: str(descriptor["surface"]["path"]).strip()
    for tool_name, descriptor in _TOOL_DESCRIPTORS.items()
}


def build_tool_registry(*, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    registry = deepcopy(_INTEL_TOOL_REGISTRY)
    resolved_base_url = base_url.rstrip("/")
    registry["base_url"] = resolved_base_url
    for descriptor in registry["tools"]:
        surface = descriptor.get("surface")
        if isinstance(surface, dict):
            surface["base_url"] = resolved_base_url
    return registry


def _http_fetch_json(url: str, timeout: int = 10) -> Any:
    try:
        with request.urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except error.HTTPError as exc:  # pragma: no cover - network error branch
        raise RuntimeContractError(f"{url} returned HTTP {exc.code}") from exc
    except error.URLError as exc:  # pragma: no cover - network error branch
        raise RuntimeContractError(f"{url} is unreachable: {exc.reason}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - network error branch
        raise RuntimeContractError(f"{url} returned invalid JSON") from exc


def _build_evidence(source: str, detail: str, timestamp: str | None = None, target: str | None = None) -> dict[str, Any]:
    return {
        "source": source,
        "detail": detail,
        "timestamp": timestamp,
        "target": target,
    }


def _coerce_source_issues(source_health: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    findings: list[str] = []
    evidence: list[dict[str, Any]] = []
    for source_key, snapshot in source_health.items():
        state = str(snapshot.get("state") or "unknown").strip()
        healthy = bool(snapshot.get("healthy"))
        if healthy and state == "ok":
            continue
        label = str(snapshot.get("label") or source_key).strip() or source_key
        age_minutes = snapshot.get("age_minutes")
        detail = f"{label} ({state}"
        if age_minutes is not None:
            detail += f", {age_minutes}m"
        detail += ")"
        findings.append(f"Source issue: {detail}")
        evidence.append(_build_evidence(
            "/api/health",
            f"{label} reported state={state}, healthy={healthy}",
            snapshot.get("last_success_at"),
            source_key,
        ))
    return findings, evidence


def _summarize_source_health(source_health: dict[str, Any]) -> str:
    ok_count = 0
    issue_count = 0
    for snapshot in source_health.values():
        if bool(snapshot.get("healthy")) and str(snapshot.get("state") or "unknown") == "ok":
            ok_count += 1
        else:
            issue_count += 1
    return f"{ok_count} healthy, {issue_count} degraded/stale"


def _append_local_ai_findings(local_ai: dict[str, Any] | None, findings: list[str], evidence: list[dict[str, Any]], next_actions: list[str]) -> None:
    if not isinstance(local_ai, dict):
        findings.append("Local AI control plane unavailable.")
        evidence.append(_build_evidence("/api/health", "local_ai_control_plane missing"))
        next_actions.append("Inspect local AI control-plane visibility in /api/health.")
        return

    degraded_parts: list[str] = []
    for key in ("gateway", "ollama", "quick_contract", "watchdog"):
        snapshot = local_ai.get(key)
        if not isinstance(snapshot, dict):
            degraded_parts.append(f"{key}=missing")
            continue
        if snapshot.get("healthy") is False or str(snapshot.get("state") or "unknown") not in {"ok", "healthy", "passed"}:
            degraded_parts.append(f"{key}={snapshot.get('state') or 'unknown'}")
            evidence.append(_build_evidence(
                "/api/health",
                f"local_ai_control_plane.{key} state={snapshot.get('state') or 'unknown'}",
                snapshot.get("checked_at"),
                key,
            ))
    if degraded_parts:
        findings.append(f"Local AI control plane degraded: {', '.join(degraded_parts)}.")
        next_actions.append("Inspect 19000 gateway, 11434 Ollama, and local_ai_control_plane.quick_contract.")


def _append_scoring_findings(scoring: dict[str, Any] | None, findings: list[str], evidence: list[dict[str, Any]], next_actions: list[str]) -> None:
    if not isinstance(scoring, dict):
        findings.append("Scoring pipeline state unavailable.")
        evidence.append(_build_evidence("/api/health", "scoring_pipeline missing"))
        next_actions.append("Inspect scoring pipeline state in /api/health and /api/ops_overview.")
        return

    state = str(scoring.get("state") or "unknown")
    stale_count = scoring.get("stale_count")
    if scoring.get("healthy") is False or state != "healthy":
        findings.append(f"Scoring pipeline degraded: state={state}, stale_count={stale_count}.")
        evidence.append(_build_evidence(
            "/api/ops_overview",
            f"scoring_pipeline state={state}, stale_count={stale_count}",
            scoring.get("checked_at"),
            "scoring_pipeline",
        ))
        next_actions.append("Inspect scoring backlog and stale scoring items before trusting freshness.")


def _append_briefing_findings(briefing: dict[str, Any] | None, findings: list[str], evidence: list[dict[str, Any]], next_actions: list[str]) -> str:
    if not isinstance(briefing, dict) or not briefing.get("content"):
        findings.append("Latest briefing unavailable.")
        next_actions.append("Generate or inspect the latest briefing before acting on briefing-driven judgment.")
        return "unavailable"

    date = briefing.get("date") or "unknown date"
    item_count = briefing.get("item_count")
    findings.append(f"Latest briefing available for {date} ({item_count or 'unknown'} items).")
    evidence.append(_build_evidence(
        "/api/briefing",
        f"latest briefing date={date}, item_count={item_count}",
        briefing.get("created_at") or briefing.get("trace_generated_at"),
        "latest_briefing",
    ))
    return "available"


def _append_control_plane_alert_findings(
    control_plane_alerts: dict[str, Any] | None,
    findings: list[str],
    evidence: list[dict[str, Any]],
    next_actions: list[str],
) -> str:
    if not isinstance(control_plane_alerts, dict):
        findings.append("Control-plane alert fanout unavailable.")
        evidence.append(_build_evidence("/api/health", "control_plane_alerts missing", None, "control_plane_alerts"))
        next_actions.append("Inspect watchdog_status and /api/health.control_plane_alerts before trusting high-level alert delivery.")
        return "missing"

    state = str(control_plane_alerts.get("state") or "missing").strip().lower() or "missing"
    event_count = control_plane_alerts.get("event_count")
    sent = control_plane_alerts.get("sent")
    suppressed = control_plane_alerts.get("suppressed")
    kinds = [str(item).strip() for item in control_plane_alerts.get("kinds", []) if str(item).strip()]
    events = [
        event
        for event in control_plane_alerts.get("events", [])
        if isinstance(event, dict)
    ]
    findings.append(
        f"Control-plane alert fanout state={state}, event_count={event_count if event_count is not None else 'unknown'}, sent={sent if sent is not None else 'unknown'}, suppressed={suppressed if suppressed is not None else 'unknown'}."
    )
    if kinds:
        findings.append(f"Active control-plane alert kinds: {', '.join(kinds)}.")
    if events:
        top_event = events[0]
        top_summary = str(top_event.get("summary") or "").strip().rstrip(".")
        findings.append(
            f"Top control-plane event: {str(top_event.get('kind') or 'unknown')} -> {top_summary or 'no summary'}."
        )
    evidence.append(_build_evidence(
        "/api/health",
        f"control_plane_alerts state={state}, event_count={event_count}, sent={sent}, suppressed={suppressed}, kinds={kinds}",
        control_plane_alerts.get("checked_at"),
        "control_plane_alerts",
    ))

    if state == "dispatch_failed":
        next_actions.append("Inspect watchdog control-plane dispatch path and Discord delivery configuration.")
    elif state in {"dispatched", "suppressed"} and kinds:
        next_actions.append("Review active control-plane alert kinds before treating the operator surface as fully healthy.")
    elif state in {"disabled", "missing"}:
        next_actions.append("Re-enable or restore control-plane fanout visibility in watchdog and /api/health.")
    if events:
        primary_action = str(events[0].get("recommended_action") or "").strip()
        if primary_action:
            next_actions.append(primary_action)

    return state


def _add_unique_actions(actions: list[str]) -> list[str]:
    unique: list[str] = []
    seen = set()
    for action in actions:
        normalized = action.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _fetch_payload(fetch_json: FetchJson, base_url: str, path: str, *, required: bool) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        payload = fetch_json(url, 10)
    except RuntimeContractError:
        if required:
            raise
        return None
    if not isinstance(payload, dict):
        if required:
            raise RuntimeContractError(f"{path} returned a non-object payload")
        return None
    return payload


def _build_failed_envelope(skill_name: str, message: str, *, code: str = "runtime_contract_error") -> dict[str, Any]:
    return {
        "skill_name": skill_name,
        "contract_version": CONTRACT_VERSION,
        "status": "failed",
        "summary": message,
        "findings": [],
        "evidence": [],
        "confidence": "unknown",
        "next_actions": ["Inspect runtime availability and contract shape before retrying."],
        "errors": [{"code": code, "message": message, "recoverable": True}],
    }


def build_tool_response(
    tool_name: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    fetch_json: FetchJson | None = None,
) -> dict[str, Any]:
    descriptor = _TOOL_DESCRIPTORS.get(tool_name)
    if descriptor is None:
        raise RuntimeContractError(f"unsupported tool: {tool_name}")

    fetcher = fetch_json or _http_fetch_json
    surface = descriptor["surface"]

    if tool_name == "intel-briefing":
        latest_path = str(surface["path"]).strip()
        latest_payload = _fetch_payload(fetcher, base_url, latest_path, required=True)
        if latest_payload is None:  # pragma: no cover - guarded by required=True
            raise RuntimeContractError(f"{latest_path} returned no payload")

        selected_payload = latest_payload
        selected_endpoint = f"GET {latest_path}"
        request_payload = {
            "method": str(surface["method"]).strip().upper(),
            "path": latest_path,
            "auxiliary_paths": list(surface.get("auxiliary_paths", [])),
            "base_url": base_url.rstrip("/"),
            "selection_strategy": surface.get("selection_strategy"),
        }

        deep_briefings_path = next(iter(request_payload["auxiliary_paths"]), None)
        try:
            deep_payload = fetcher(f"{base_url.rstrip('/')}{deep_briefings_path}", 10) if deep_briefings_path else None
        except RuntimeContractError:
            deep_payload = None

        if isinstance(deep_payload, list):
            for item in deep_payload:
                if not isinstance(item, dict):
                    continue
                if bool(item.get("protocol_available")) and isinstance(item.get("briefing_protocol"), dict):
                    selected_payload = item
                    selected_endpoint = f"GET {deep_briefings_path}"
                    request_payload["selected_date"] = item.get("date")
                    request_payload["selected_mode"] = "protocol_backed"
                    request_payload["selected_protocol_mode"] = item.get("protocol_mode") or "native"
                    break
            else:
                request_payload["selected_date"] = latest_payload.get("date") if isinstance(latest_payload, dict) else None
                if bool(latest_payload.get("protocol_available")) and isinstance(latest_payload.get("briefing_protocol"), dict):
                    request_payload["selected_mode"] = "protocol_backed"
                    request_payload["selected_protocol_mode"] = latest_payload.get("protocol_mode") or "native"
                else:
                    request_payload["selected_mode"] = "latest_legacy"
        else:
            request_payload["selected_date"] = latest_payload.get("date") if isinstance(latest_payload, dict) else None
            if bool(latest_payload.get("protocol_available")) and isinstance(latest_payload.get("briefing_protocol"), dict):
                request_payload["selected_mode"] = "protocol_backed"
                request_payload["selected_protocol_mode"] = latest_payload.get("protocol_mode") or "native"
            else:
                request_payload["selected_mode"] = "latest_legacy"

        return {
            "tool_name": tool_name,
            "contract_version": CONTRACT_VERSION,
            "endpoint_used": selected_endpoint,
            "request_payload": request_payload,
            "raw_response": selected_payload,
            "error": None,
        }

    path = str(surface["path"]).strip()
    payload = _fetch_payload(fetcher, base_url, path, required=True)
    if payload is None:  # pragma: no cover - guarded by required=True
        raise RuntimeContractError(f"{path} returned no payload")

    return {
        "tool_name": tool_name,
        "contract_version": CONTRACT_VERSION,
        "endpoint_used": f"{str(surface['method']).strip().upper()} {path}",
        "request_payload": {
            "method": str(surface["method"]).strip().upper(),
            "path": path,
            "base_url": base_url.rstrip("/"),
        },
        "raw_response": payload,
        "error": None,
    }


def build_intel_duty_officer_envelope(
    *,
    base_url: str = DEFAULT_BASE_URL,
    fetch_json: FetchJson | None = None,
) -> dict[str, Any]:
    fetcher = fetch_json or _http_fetch_json

    health = _fetch_payload(fetcher, base_url, "/api/health", required=True)
    ops = _fetch_payload(fetcher, base_url, "/api/ops_overview", required=True)
    briefing = _fetch_payload(fetcher, base_url, "/api/briefing", required=False)

    if health is None or ops is None:  # pragma: no cover - guarded by required=True
        raise RuntimeContractError("required runtime payload missing")

    findings: list[str] = []
    evidence: list[dict[str, Any]] = []
    next_actions: list[str] = []
    errors: list[dict[str, Any]] = []
    status = "ok"
    confidence = "high"

    health_status = str(health.get("status") or "unknown").strip()
    findings.append(f"Runtime health status: {health_status}.")
    evidence.append(_build_evidence(
        "/api/health",
        f"status={health_status}",
        health.get("last_fetch"),
        "status",
    ))

    source_health = health.get("source_health") if isinstance(health.get("source_health"), dict) else {}
    findings.append(f"Source health summary: {_summarize_source_health(source_health)}.")
    source_findings, source_evidence = _coerce_source_issues(source_health)
    findings.extend(source_findings)
    evidence.extend(source_evidence)
    if source_findings:
        status = "degraded"
        confidence = "medium"
        for finding in source_findings[:3]:
            label = finding.replace("Source issue: ", "").split(" (", 1)[0]
            next_actions.append(f"Investigate {label} freshness and latest source run details.")

    ops_summary = ops.get("summary") if isinstance(ops.get("summary"), dict) else {}
    scoring_items = ops_summary.get("scoring_items")
    findings.append(f"Ops summary: total_items={ops_summary.get('total_items', 'unknown')}, scoring_items={scoring_items if scoring_items is not None else 'unknown'}.")
    evidence.append(_build_evidence(
        "/api/ops_overview",
        f"summary.total_items={ops_summary.get('total_items', 'unknown')}, summary.scoring_items={scoring_items if scoring_items is not None else 'unknown'}",
        None,
        "summary",
    ))

    _append_scoring_findings(
        ops.get("scoring_pipeline") if isinstance(ops.get("scoring_pipeline"), dict) else health.get("scoring_pipeline"),
        findings,
        evidence,
        next_actions,
    )
    if any("Scoring pipeline degraded" in finding for finding in findings):
        status = "degraded"
        confidence = "medium"

    _append_local_ai_findings(health.get("local_ai_control_plane"), findings, evidence, next_actions)
    if any("Local AI control plane degraded" in finding for finding in findings) or any("Local AI control plane unavailable" in finding for finding in findings):
        status = "degraded"
        confidence = "medium"

    control_plane_alerts = (
        health.get("control_plane_alerts")
        if isinstance(health.get("control_plane_alerts"), dict)
        else ops.get("control_plane_alerts")
    )
    control_plane_state = _append_control_plane_alert_findings(control_plane_alerts, findings, evidence, next_actions)
    if control_plane_state in {"dispatch_failed", "dispatched", "suppressed", "missing"}:
        status = "degraded"
        confidence = "medium"

    briefing_state = _append_briefing_findings(briefing, findings, evidence, next_actions)
    if briefing_state == "unavailable" and confidence == "high":
        confidence = "medium"

    alerts = ops.get("alerts") if isinstance(ops.get("alerts"), dict) else {}
    pipeline_alert = alerts.get("pipeline_stall") if isinstance(alerts.get("pipeline_stall"), dict) else None
    if pipeline_alert:
        findings.append(f"Pipeline alert: {pipeline_alert.get('title') or pipeline_alert.get('kind') or 'unknown'}.")
        evidence.append(_build_evidence(
            "/api/ops_overview",
            pipeline_alert.get("message") or pipeline_alert.get("title") or "pipeline alert present",
            None,
            "alerts.pipeline_stall",
        ))

    if health_status != "OPERATIONAL":
        status = "degraded"
        confidence = "medium"
        next_actions.append("Inspect runtime health before trusting downstream summaries.")

    if briefing is None:
        errors = []

    next_actions = _add_unique_actions(next_actions)
    if not next_actions:
        next_actions = ["Monitor current state. No immediate action required."]

    summary = (
        f"{health_status}; sources {_summarize_source_health(source_health)}; "
        f"scoring {str((ops.get('scoring_pipeline') or {}).get('state') or 'unknown')}; "
        f"control_plane_alerts {control_plane_state}; briefing {briefing_state}."
    )
    return {
        "skill_name": "intel-duty-officer",
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "summary": summary,
        "findings": findings,
        "evidence": evidence,
        "confidence": confidence,
        "next_actions": next_actions,
        "errors": errors,
    }


def build_source_health_triage_envelope(
    target: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    fetch_json: FetchJson | None = None,
) -> dict[str, Any]:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return _build_failed_envelope(
            "source-health-triage",
            "source-health-triage requires a bounded target such as a source key, scoring_pipeline, local_ai_control_plane, or watchdog.",
            code="missing_target",
        )

    fetcher = fetch_json or _http_fetch_json
    health = _fetch_payload(fetcher, base_url, "/api/health", required=True)
    ops = _fetch_payload(fetcher, base_url, "/api/ops_overview", required=True)
    if health is None or ops is None:  # pragma: no cover - guarded by required=True
        raise RuntimeContractError("required runtime payload missing")

    findings: list[str] = []
    evidence: list[dict[str, Any]] = []
    next_actions: list[str] = []
    status = "ok"
    confidence = "high"
    errors: list[dict[str, Any]] = []

    source_health = health.get("source_health") if isinstance(health.get("source_health"), dict) else {}
    scoring = ops.get("scoring_pipeline") if isinstance(ops.get("scoring_pipeline"), dict) else health.get("scoring_pipeline")
    local_ai = health.get("local_ai_control_plane") if isinstance(health.get("local_ai_control_plane"), dict) else {}

    if normalized_target in source_health:
        snapshot = source_health[normalized_target]
        label = str(snapshot.get("label") or normalized_target)
        state = str(snapshot.get("state") or "unknown")
        age_minutes = snapshot.get("age_minutes")
        last_success_at = snapshot.get("last_success_at")
        last_run_status = snapshot.get("last_run_status")

        findings.append(f"{label} state={state}.")
        if age_minutes is not None:
            findings.append(f"{label} age={age_minutes} minutes since last success.")
        if last_run_status:
            findings.append(f"{label} last_run_status={last_run_status}.")
        evidence.append(_build_evidence(
            "/api/health",
            f"{label} reported state={state}, healthy={snapshot.get('healthy')}, age_minutes={age_minutes}",
            last_success_at,
            normalized_target,
        ))

        if not (bool(snapshot.get("healthy")) and state == "ok"):
            status = "degraded"
            confidence = "high"
            next_actions.append(f"Inspect latest {label} run metadata and source-specific capture path.")
        else:
            next_actions.append(f"Monitor {label}; no active source degradation detected.")

        if isinstance(scoring, dict) and scoring.get("healthy") is False:
            by_source = scoring.get("by_source") if isinstance(scoring.get("by_source"), dict) else {}
            source_backlog = by_source.get(normalized_target)
            if source_backlog:
                status = "degraded"
                confidence = "medium"
                findings.append(f"{label} also has scoring backlog pressure.")
                evidence.append(_build_evidence(
                    "/api/ops_overview",
                    f"scoring backlog for {normalized_target}: {source_backlog}",
                    scoring.get("checked_at"),
                    normalized_target,
                ))
                next_actions.append(f"Clear scoring backlog for {label} before trusting freshness.")

        summary = f"{label}: state={state}, age_minutes={age_minutes if age_minutes is not None else 'unknown'}."

    elif normalized_target == "scoring_pipeline":
        if not isinstance(scoring, dict):
            return _build_failed_envelope(
                "source-health-triage",
                "scoring_pipeline is unavailable in runtime health surfaces.",
                code="missing_scoring_pipeline",
            )
        state = str(scoring.get("state") or "unknown")
        stale_count = scoring.get("stale_count")
        oldest_age = scoring.get("oldest_age_minutes")
        findings.append(f"scoring_pipeline state={state}.")
        findings.append(f"stale_count={stale_count}, oldest_age_minutes={oldest_age}.")
        evidence.append(_build_evidence(
            "/api/ops_overview",
            f"scoring_pipeline state={state}, stale_count={stale_count}, oldest_age_minutes={oldest_age}",
            scoring.get("checked_at"),
            "scoring_pipeline",
        ))
        if scoring.get("healthy") is False or state != "healthy":
            status = "degraded"
            confidence = "high"
            next_actions.append("Inspect stale scoring items and scoring locks before treating the feed as current.")
        else:
            next_actions.append("Monitor scoring pipeline; no backlog stall detected.")
        summary = f"scoring_pipeline: state={state}, stale_count={stale_count}."

    elif normalized_target in {"local_ai_control_plane", "watchdog"}:
        if not isinstance(local_ai, dict):
            return _build_failed_envelope(
                "source-health-triage",
                "local_ai_control_plane is unavailable in /api/health.",
                code="missing_local_ai_control_plane",
            )
        relevant_local_ai_keys = ("gateway", "ollama", "quick_contract", "watchdog")
        snapshots = (
            {key: local_ai.get(key) for key in relevant_local_ai_keys}
            if normalized_target == "local_ai_control_plane"
            else {"watchdog": local_ai.get("watchdog")}
        )
        degraded_parts: list[str] = []
        for key, snapshot in snapshots.items():
            if not isinstance(snapshot, dict):
                degraded_parts.append(f"{key}=missing")
                evidence.append(_build_evidence("/api/health", f"{key} missing from local_ai_control_plane", None, key))
                continue
            state = str(snapshot.get("state") or "unknown")
            findings.append(f"{key} state={state}.")
            if snapshot.get("healthy") is False or state not in {"ok", "healthy", "passed"}:
                degraded_parts.append(f"{key}={state}")
            evidence.append(_build_evidence(
                "/api/health",
                f"{key} state={state}, healthy={snapshot.get('healthy')}",
                snapshot.get("checked_at"),
                key,
            ))
        if degraded_parts:
            status = "degraded"
            confidence = "high" if normalized_target == "watchdog" else "medium"
            next_actions.append("Inspect 19000 gateway, 11434 Ollama, quick contract, and watchdog logs.")
        else:
            next_actions.append("Monitor local AI control plane; no active degradation detected.")
        summary = f"{normalized_target}: {', '.join(degraded_parts) if degraded_parts else 'healthy'}."

    elif normalized_target == "control_plane_alerts":
        snapshot = (
            health.get("control_plane_alerts")
            if isinstance(health.get("control_plane_alerts"), dict)
            else ops.get("control_plane_alerts")
        )
        if not isinstance(snapshot, dict):
            return _build_failed_envelope(
                "source-health-triage",
                "control_plane_alerts is unavailable in runtime health surfaces.",
                code="missing_control_plane_alerts",
            )
        state = str(snapshot.get("state") or "missing").strip().lower() or "missing"
        event_count = snapshot.get("event_count")
        sent = snapshot.get("sent")
        suppressed = snapshot.get("suppressed")
        kinds = [str(item).strip() for item in snapshot.get("kinds", []) if str(item).strip()]
        events = [
            event
            for event in snapshot.get("events", [])
            if isinstance(event, dict)
        ]
        findings.append(f"control_plane_alerts state={state}.")
        findings.append(
            f"event_count={event_count if event_count is not None else 'unknown'}, sent={sent if sent is not None else 'unknown'}, suppressed={suppressed if suppressed is not None else 'unknown'}."
        )
        if kinds:
            findings.append(f"active kinds={', '.join(kinds)}.")
        if events:
            top_event = events[0]
            top_summary = str(top_event.get("summary") or "").strip().rstrip(".")
            findings.append(
                f"top event={str(top_event.get('kind') or 'unknown')}: {top_summary or 'no summary'}."
            )
        if snapshot.get("error"):
            findings.append(f"dispatch error={snapshot.get('error')}.")
        evidence.append(_build_evidence(
            "/api/health",
            f"control_plane_alerts state={state}, event_count={event_count}, sent={sent}, suppressed={suppressed}, kinds={kinds}, error={snapshot.get('error')}",
            snapshot.get("checked_at"),
            "control_plane_alerts",
        ))
        if state in {"dispatch_failed", "missing"}:
            status = "degraded"
            confidence = "high"
            next_actions.append("Inspect watchdog fanout state and Discord dispatch wiring before relying on operator alerts.")
        elif state in {"dispatched", "suppressed"} and (event_count or 0):
            status = "degraded"
            confidence = "medium"
            next_actions.append("Review the active control-plane alert kinds and their upstream runtime causes.")
        else:
            next_actions.append("Monitor control-plane alert fanout; no active dispatch issue detected.")
        if events:
            primary_action = str(events[0].get("recommended_action") or "").strip()
            if primary_action:
                next_actions.append(primary_action)
        summary = f"control_plane_alerts: state={state}, event_count={event_count if event_count is not None else 'unknown'}."

    else:
        return _build_failed_envelope(
            "source-health-triage",
            f"Unknown triage target: {normalized_target}",
            code="unknown_target",
        )

    next_actions = _add_unique_actions(next_actions)
    return {
        "skill_name": "source-health-triage",
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "summary": summary,
        "findings": findings,
        "evidence": evidence,
        "confidence": confidence,
        "next_actions": next_actions,
        "errors": errors,
    }


def build_briefing_analyst_envelope(
    *,
    base_url: str = DEFAULT_BASE_URL,
    fetch_json: FetchJson | None = None,
) -> dict[str, Any]:
    briefing_tool = build_tool_response("intel-briefing", base_url=base_url, fetch_json=fetch_json)
    try:
        ops_tool = build_tool_response("intel-ops-overview", base_url=base_url, fetch_json=fetch_json)
    except RuntimeContractError:
        ops_tool = None

    briefing = briefing_tool["raw_response"] if isinstance(briefing_tool.get("raw_response"), dict) else {}
    ops_payload = ops_tool["raw_response"] if isinstance(ops_tool and ops_tool.get("raw_response"), dict) else {}
    ops_latest = ops_payload.get("latest_briefing") if isinstance(ops_payload.get("latest_briefing"), dict) else None

    findings: list[str] = []
    evidence: list[dict[str, Any]] = []
    next_actions: list[str] = []
    errors: list[dict[str, Any]] = []
    status = "ok"
    confidence = "high"

    content = briefing.get("content")
    if not content:
        return {
            "skill_name": "briefing-analyst",
            "contract_version": CONTRACT_VERSION,
            "status": "partial",
            "summary": "No current briefing content is available.",
            "findings": ["Latest briefing is empty or not yet generated."],
            "evidence": [
                _build_evidence(
                    "intel-briefing",
                    "briefing tool returned no content",
                    briefing.get("created_at"),
                    "briefing.content",
                )
            ],
            "confidence": "unknown",
            "next_actions": ["Generate or wait for the next briefing before using briefing-driven judgment."],
            "errors": [],
        }

    briefing_date = briefing.get("date") or "unknown date"
    protocol_available = bool(briefing.get("protocol_available"))
    protocol_mode = str(briefing.get("protocol_mode") or ("native" if protocol_available else "none")).strip() or "none"
    briefing_protocol = briefing.get("briefing_protocol") if isinstance(briefing.get("briefing_protocol"), dict) else None
    verdict = briefing_protocol.get("verdict") if isinstance(briefing_protocol and briefing_protocol.get("verdict"), dict) else None
    evidence_matrix = briefing_protocol.get("evidence_matrix") if isinstance(briefing_protocol and briefing_protocol.get("evidence_matrix"), dict) else None
    final_claims = briefing.get("final_claims") if isinstance(briefing.get("final_claims"), list) else []

    evidence.append(_build_evidence(
        "intel-briefing",
        f"briefing date={briefing_date}, protocol_available={protocol_available}, protocol_mode={protocol_mode}, item_count={briefing.get('item_count')}",
        briefing.get("trace_generated_at") or briefing.get("created_at"),
        "latest_briefing",
    ))
    if ops_latest is not None:
        evidence.append(_build_evidence(
            "intel-ops-overview",
            f"ops latest_briefing date={ops_latest.get('date')}, protocol_available={ops_latest.get('protocol_available')}, protocol_mode={ops_latest.get('protocol_mode') or 'none'}",
            ops_latest.get("trace_generated_at") or ops_latest.get("created_at"),
            "latest_briefing",
        ))

    if protocol_available and verdict:
        headline = str(verdict.get("headline") or "").strip()
        verdict_confidence = str(verdict.get("confidence") or "medium").strip().lower() or "medium"
        action_bias = str(verdict.get("action_bias") or "track").strip().lower() or "track"
        findings.append(f"Verdict: {headline or 'headline unavailable'}.")
        findings.append(f"Confidence={verdict_confidence}, action_bias={action_bias}, protocol_mode={protocol_mode}.")
        if verdict.get("summary"):
            findings.append(f"Summary: {str(verdict.get('summary')).strip()}")

        if evidence_matrix:
            cross_source_count = int(evidence_matrix.get("cross_source_confirmation_count") or 0)
            conflict_signals = [
                str(item or "").strip()
                for item in evidence_matrix.get("conflict_signals", [])
                if str(item or "").strip()
            ]
            supporting_refs = [
                str(item or "").strip()
                for item in evidence_matrix.get("supporting_refs", [])
                if str(item or "").strip()
            ]
            findings.append(
                f"Evidence matrix: cross_source_confirmation_count={cross_source_count}, conflict_signals={len(conflict_signals)}."
            )
            if supporting_refs:
                findings.append(f"Supporting refs: {', '.join(supporting_refs[:3])}.")
            if conflict_signals:
                findings.append(f"Conflict signals: {', '.join(conflict_signals[:3])}.")
            evidence.append(_build_evidence(
                "intel-briefing",
                f"evidence_matrix cross_source_confirmation_count={cross_source_count}, conflict_signals={len(conflict_signals)}",
                briefing.get("trace_generated_at"),
                "briefing_protocol.evidence_matrix",
            ))
            if conflict_signals:
                status = "partial"
                confidence = "medium" if verdict_confidence == "high" else verdict_confidence
                next_actions.append("Review conflict signals before treating the briefing verdict as fully actionable.")
            else:
                confidence = verdict_confidence
        else:
            confidence = verdict_confidence

        if protocol_mode == "legacy_fallback":
            status = "partial"
            if confidence == "high":
                confidence = "medium"
            findings.append("Protocol judgment was synthesized from a legacy trace fallback, not a native analyst protocol sidecar.")
            next_actions.append("Regenerate the latest analyst briefing if native protocol-side judgment is required.")

        if final_claims:
            findings.append(f"Final claims available: {len(final_claims)}.")
            evidence.append(_build_evidence(
                "intel-briefing",
                f"final_claims_count={len(final_claims)}",
                briefing.get("trace_generated_at"),
                "final_claims",
            ))

        if action_bias == "act":
            next_actions.append("Validate the strongest supporting references before executing act-biased follow-up.")
        elif action_bias == "track":
            next_actions.append("Track this briefing and re-check on the next cycle for stronger cross-source confirmation.")
        else:
            next_actions.append("Treat this briefing as watch-only until evidence improves.")

        if protocol_mode == "legacy_fallback":
            summary = f"Legacy-fallback protocol briefing for {briefing_date}: confidence={confidence}, action_bias={action_bias}."
        else:
            summary = f"Protocol briefing for {briefing_date}: confidence={verdict_confidence}, action_bias={action_bias}."
    else:
        status = "partial"
        confidence = "low"
        findings.append(f"Legacy briefing available for {briefing_date}.")
        findings.append("Protocol fields are unavailable; analysis is limited to legacy briefing metadata and content presence.")
        if final_claims:
            findings.append(f"Final claims available without full protocol: {len(final_claims)}.")
            evidence.append(_build_evidence(
                "intel-briefing",
                f"legacy final_claims_count={len(final_claims)}",
                briefing.get("trace_generated_at"),
                "final_claims",
            ))
        next_actions.append("Use this briefing for context only; do not infer protocol-level confidence or action bias.")
        next_actions.append("Regenerate or inspect the latest analyst trace if protocol-backed judgment is required.")
        summary = f"Legacy-only briefing for {briefing_date}; protocol judgment unavailable."

    if ops_tool is None:
        findings.append("Ops overview context unavailable during briefing analysis.")
        errors.append({
            "code": "optional_ops_context_unavailable",
            "message": "intel-ops-overview could not be read; briefing analysis used intel-briefing only.",
            "recoverable": True,
        })

    return {
        "skill_name": "briefing-analyst",
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "summary": summary,
        "findings": findings,
        "evidence": evidence,
        "confidence": confidence,
        "next_actions": _add_unique_actions(next_actions),
        "errors": errors,
    }


def build_skill_envelope(
    skill_name: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    fetch_json: FetchJson | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    if skill_name == "intel-duty-officer":
        return build_intel_duty_officer_envelope(base_url=base_url, fetch_json=fetch_json)
    if skill_name == "source-health-triage":
        return build_source_health_triage_envelope(target or "", base_url=base_url, fetch_json=fetch_json)
    if skill_name == "briefing-analyst":
        return build_briefing_analyst_envelope(base_url=base_url, fetch_json=fetch_json)
    raise RuntimeContractError(f"unsupported skill: {skill_name}")
