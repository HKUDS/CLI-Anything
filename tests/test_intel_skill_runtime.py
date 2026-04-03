import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path("/Users/lixun/Documents/codex ")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_skills.intel_runtime import (  # noqa: E402
    CONTRACT_VERSION,
    RuntimeContractError,
    build_briefing_analyst_envelope,
    build_intel_duty_officer_envelope,
    build_tool_registry,
    build_source_health_triage_envelope,
    build_tool_response,
)


def _make_fetcher(payloads, failures=None):
    failure_map = failures or {}

    def _fetch(url, timeout=10):
        path = url.split("://", 1)[-1]
        path = "/" + path.split("/", 1)[1] if "/" in path else "/"
        if path in failure_map:
            raise RuntimeContractError(failure_map[path])
        if path not in payloads:
            raise RuntimeContractError(f"missing fixture for {path}")
        return payloads[path]

    return _fetch


class IntelDutyOfficerRuntimeTests(unittest.TestCase):
    def test_builds_ok_envelope_from_healthy_runtime(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {
                    "twitter_home_timeline": {
                        "label": "Twitter Home Timeline",
                        "state": "ok",
                        "healthy": True,
                        "age_minutes": 4,
                        "last_success_at": "2026-04-03T07:46:35.554Z",
                    },
                    "github": {
                        "label": "GitHub",
                        "state": "ok",
                        "healthy": True,
                        "age_minutes": 3,
                        "last_success_at": "2026-04-03T07:48:12.190Z",
                    },
                },
                "local_ai_control_plane": {
                    "gateway": {"healthy": True, "state": "ok"},
                    "ollama": {"healthy": True, "state": "ok"},
                    "quick_contract": {"healthy": True, "state": "passed"},
                    "watchdog": {"healthy": True, "state": "ok"},
                },
                "control_plane_alerts": {
                    "healthy": True,
                    "state": "idle",
                    "enabled": True,
                    "event_count": 0,
                    "sent": 0,
                    "suppressed": 0,
                    "kinds": [],
                    "checked_at": "2026-04-03T07:49:00.000Z",
                },
                "scoring_pipeline": {
                    "healthy": True,
                    "state": "healthy",
                    "stale_count": 0,
                },
            },
            "/api/ops_overview": {
                "summary": {
                    "total_items": 12000,
                    "scoring_items": 0,
                },
                "alerts": {
                    "pipeline_stall": {
                        "kind": "healthy",
                        "level": "ok",
                        "title": "抓取与评分基本同步",
                        "message": "最新抓取和最新评分之间没有明显断层。",
                    },
                    "opencli_bridge": {
                        "kind": "healthy",
                        "level": "ok",
                        "title": "OpenCLI bridge 已连接",
                    },
                },
                "scoring_pipeline": {
                    "healthy": True,
                    "state": "healthy",
                    "stale_count": 0,
                },
                "harness_overview": {
                    "state": "healthy",
                    "recent_failures": 0,
                },
                "latest_briefing": None,
            },
            "/api/briefing": {
                "id": 44,
                "date": "2026-04-01",
                "content": "briefing text",
                "item_count": 43,
                "created_at": "2026-04-01 19:55:48",
            },
        }

        envelope = build_intel_duty_officer_envelope(fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["skill_name"], "intel-duty-officer")
        self.assertEqual(envelope["contract_version"], CONTRACT_VERSION)
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["confidence"], "high")
        self.assertIn("OPERATIONAL", envelope["summary"])
        self.assertTrue(any("Latest briefing available" in finding for finding in envelope["findings"]))
        self.assertTrue(any(item["source"] == "/api/health" for item in envelope["evidence"]))
        self.assertTrue(any(item["source"] == "/api/ops_overview" for item in envelope["evidence"]))
        self.assertTrue(any(item["source"] == "/api/briefing" for item in envelope["evidence"]))
        self.assertEqual(envelope["errors"], [])
        self.assertEqual(envelope["next_actions"], ["Monitor current state. No immediate action required."])

    def test_marks_degraded_when_source_and_local_ai_are_unhealthy(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {
                    "reddit": {
                        "label": "Reddit",
                        "state": "stale",
                        "healthy": False,
                        "age_minutes": 67,
                        "last_success_at": "2026-04-03T06:00:00.000Z",
                    },
                    "github": {
                        "label": "GitHub",
                        "state": "ok",
                        "healthy": True,
                        "age_minutes": 5,
                        "last_success_at": "2026-04-03T07:48:12.190Z",
                    },
                },
                "local_ai_control_plane": {
                    "gateway": {"healthy": True, "state": "ok"},
                    "ollama": {"healthy": True, "state": "ok"},
                    "quick_contract": {"healthy": False, "state": "failed", "error": "json parse failed"},
                    "watchdog": {"healthy": False, "state": "failing"},
                },
                "control_plane_alerts": {
                    "healthy": False,
                    "state": "suppressed",
                    "enabled": True,
                    "event_count": 1,
                    "sent": 0,
                    "suppressed": 1,
                    "kinds": ["harness_failed"],
                    "events": [
                        {
                            "kind": "harness_failed",
                            "severity": "critical",
                            "summary": "Harness attention required (failed=1, degraded=0, attention=1).",
                            "dedupe_key": "harness_failed",
                            "recommended_action": "Inspect recent harness attention runs and failing findings before trusting the pipeline.",
                        }
                    ],
                    "checked_at": "2026-04-03T08:02:00.000Z",
                },
                "scoring_pipeline": {
                    "healthy": False,
                    "state": "stale_backlog",
                    "stale_count": 9,
                    "oldest_age_minutes": 42,
                },
            },
            "/api/ops_overview": {
                "summary": {
                    "total_items": 12000,
                    "scoring_items": 9,
                },
                "alerts": {
                    "pipeline_stall": {
                        "kind": "scoring_backlog",
                        "level": "warn",
                        "title": "评分积压",
                        "message": "旧 scoring 队列未消化。",
                    },
                },
                "scoring_pipeline": {
                    "healthy": False,
                    "state": "stale_backlog",
                    "stale_count": 9,
                    "oldest_age_minutes": 42,
                },
                "harness_overview": {
                    "state": "degraded",
                    "recent_failures": 1,
                },
                "latest_briefing": None,
            },
            "/api/briefing": {
                "content": None,
                "message": "尚未生成简报。",
            },
        }

        envelope = build_intel_duty_officer_envelope(fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "degraded")
        self.assertEqual(envelope["confidence"], "medium")
        self.assertTrue(any("Reddit (stale" in finding for finding in envelope["findings"]))
        self.assertTrue(any("Local AI control plane degraded" in finding for finding in envelope["findings"]))
        self.assertTrue(any("Control-plane alert fanout state=suppressed" in finding for finding in envelope["findings"]))
        self.assertTrue(any("Top control-plane event: harness_failed" in finding for finding in envelope["findings"]))
        self.assertTrue(any("scoring backlog" in action.lower() for action in envelope["next_actions"]))
        self.assertTrue(any("Reddit" in action for action in envelope["next_actions"]))
        self.assertTrue(any("Inspect recent harness attention runs" in action for action in envelope["next_actions"]))
        self.assertIn("control_plane_alerts suppressed", envelope["summary"])

    def test_treats_briefing_as_optional(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {},
                "local_ai_control_plane": {
                    "gateway": {"healthy": True, "state": "ok"},
                    "ollama": {"healthy": True, "state": "ok"},
                    "quick_contract": {"healthy": True, "state": "ok"},
                    "watchdog": {"healthy": True, "state": "ok"},
                },
                "control_plane_alerts": {
                    "healthy": True,
                    "state": "idle",
                    "enabled": True,
                    "event_count": 0,
                    "sent": 0,
                    "suppressed": 0,
                    "kinds": [],
                },
                "scoring_pipeline": {
                    "healthy": True,
                    "state": "healthy",
                    "stale_count": 0,
                },
            },
            "/api/ops_overview": {
                "summary": {"total_items": 1, "scoring_items": 0},
                "alerts": {},
                "scoring_pipeline": {"healthy": True, "state": "healthy", "stale_count": 0},
                "harness_overview": None,
                "latest_briefing": None,
            },
        }

        envelope = build_intel_duty_officer_envelope(
            fetch_json=_make_fetcher(payloads, failures={"/api/briefing": "briefing unavailable"})
        )

        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["confidence"], "medium")
        self.assertTrue(any("Latest briefing unavailable" in finding for finding in envelope["findings"]))
        self.assertEqual(envelope["errors"], [])


class IntelRuntimeToolTests(unittest.TestCase):
    def test_tool_response_preserves_raw_health_payload(self):
        payloads = {
            "/api/health": {"status": "OPERATIONAL", "source_health": {}, "local_ai_control_plane": {}, "scoring_pipeline": {}},
        }

        response = build_tool_response("intel-health", fetch_json=_make_fetcher(payloads))

        self.assertEqual(response["tool_name"], "intel-health")
        self.assertEqual(response["endpoint_used"], "GET /api/health")
        self.assertEqual(response["request_payload"]["path"], "/api/health")
        self.assertEqual(response["raw_response"]["status"], "OPERATIONAL")
        self.assertIsNone(response["error"])

    def test_health_tool_preserves_control_plane_alert_event_details(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {},
                "local_ai_control_plane": {},
                "scoring_pipeline": {},
                "control_plane_alerts": {
                    "state": "suppressed",
                    "event_count": 1,
                    "sent": 0,
                    "suppressed": 1,
                    "kinds": ["harness_failed"],
                    "events": [
                        {
                            "kind": "harness_failed",
                            "severity": "warning",
                            "summary": "Harness attention required (failed=0, degraded=2, attention=3).",
                            "dedupe_key": "harness_failed",
                            "recommended_action": "Inspect recent harness attention runs and failing findings before trusting the pipeline.",
                        }
                    ],
                },
            },
        }

        response = build_tool_response("intel-health", fetch_json=_make_fetcher(payloads))

        self.assertEqual(response["raw_response"]["control_plane_alerts"]["state"], "suppressed")
        self.assertEqual(response["raw_response"]["control_plane_alerts"]["events"][0]["kind"], "harness_failed")
        self.assertIn(
            "Inspect recent harness attention runs",
            response["raw_response"]["control_plane_alerts"]["events"][0]["recommended_action"],
        )

    def test_ops_overview_tool_preserves_control_plane_alert_event_details(self):
        payloads = {
            "/api/ops_overview": {
                "summary": {"total_items": 1, "scoring_items": 0},
                "alerts": {},
                "latest_briefing": None,
                "control_plane_alerts": {
                    "state": "dispatched",
                    "event_count": 1,
                    "sent": 1,
                    "suppressed": 0,
                    "kinds": ["briefing_degraded"],
                    "events": [
                        {
                            "kind": "briefing_degraded",
                            "severity": "warning",
                            "summary": "Latest briefing is degraded (protocol_mode=legacy_fallback, protocol_available=true).",
                            "dedupe_key": "briefing_degraded:legacy_fallback",
                            "recommended_action": "Regenerate the latest analyst briefing or inspect the research trace protocol snapshot.",
                        }
                    ],
                },
            },
        }

        response = build_tool_response("intel-ops-overview", fetch_json=_make_fetcher(payloads))

        self.assertEqual(response["endpoint_used"], "GET /api/ops_overview")
        self.assertEqual(response["raw_response"]["control_plane_alerts"]["sent"], 1)
        self.assertEqual(response["raw_response"]["control_plane_alerts"]["events"][0]["dedupe_key"], "briefing_degraded:legacy_fallback")

    def test_briefing_tool_prefers_protocol_backed_candidate(self):
        payloads = {
            "/api/briefing": {
                "date": "2026-04-03",
                "content": "latest legacy",
                "protocol_available": False,
            },
            "/api/deep_briefings": [
                {
                    "date": "2026-04-03",
                    "content": "legacy",
                    "protocol_available": False,
                },
                {
                    "date": "2026-04-02",
                    "content": "protocol",
                    "protocol_available": True,
                    "briefing_protocol": {"verdict": {"headline": "Protocol briefing"}},
                },
            ],
        }

        response = build_tool_response("intel-briefing", fetch_json=_make_fetcher(payloads))

        self.assertEqual(response["endpoint_used"], "GET /api/deep_briefings")
        self.assertEqual(response["request_payload"]["selected_mode"], "protocol_backed")
        self.assertEqual(response["raw_response"]["date"], "2026-04-02")

    def test_briefing_tool_falls_back_to_latest_legacy(self):
        payloads = {
            "/api/briefing": {
                "date": "2026-04-03",
                "content": "latest legacy",
                "protocol_available": False,
            },
            "/api/deep_briefings": [
                {
                    "date": "2026-04-03",
                    "content": "legacy",
                    "protocol_available": False,
                }
            ],
        }

        response = build_tool_response("intel-briefing", fetch_json=_make_fetcher(payloads))

        self.assertEqual(response["endpoint_used"], "GET /api/briefing")
        self.assertEqual(response["request_payload"]["selected_mode"], "latest_legacy")
        self.assertEqual(response["raw_response"]["date"], "2026-04-03")

    def test_briefing_tool_preserves_fallback_protocol_metadata_from_latest_payload(self):
        payloads = {
            "/api/briefing": {
                "date": "2026-04-03",
                "content": "fallback protocol",
                "protocol_available": True,
                "protocol_mode": "legacy_fallback",
                "briefing_protocol": {"verdict": {"headline": "Fallback protocol"}},
            },
        }

        response = build_tool_response("intel-briefing", fetch_json=_make_fetcher(payloads))

        self.assertEqual(response["endpoint_used"], "GET /api/briefing")
        self.assertEqual(response["request_payload"]["selected_mode"], "protocol_backed")
        self.assertEqual(response["request_payload"]["selected_protocol_mode"], "legacy_fallback")
        self.assertEqual(response["raw_response"]["protocol_mode"], "legacy_fallback")


class IntelToolRegistryTests(unittest.TestCase):
    def test_build_tool_registry_exposes_mcp_style_descriptors(self):
        registry = build_tool_registry()

        self.assertEqual(registry["kind"], "deep-scavenger-tool-registry")
        self.assertEqual(registry["contract_version"], CONTRACT_VERSION)
        self.assertTrue(registry["$schema"].endswith("intel-tool-registry.schema.json"))

        descriptors = {tool["name"]: tool for tool in registry["tools"]}

        self.assertIn("intel-health", descriptors)
        self.assertIn("intel-ops-overview", descriptors)
        self.assertIn("intel-briefing", descriptors)

        self.assertIn("get_health_snapshot", descriptors["intel-health"]["aliases"])
        self.assertIn("get_ops_overview", descriptors["intel-ops-overview"]["aliases"])
        self.assertIn("get_latest_briefing", descriptors["intel-briefing"]["aliases"])
        self.assertIn("get_briefing_snapshot", descriptors["intel-briefing"]["aliases"])

        self.assertEqual(descriptors["intel-health"]["surface"]["path"], "/api/health")
        self.assertEqual(descriptors["intel-ops-overview"]["surface"]["path"], "/api/ops_overview")
        self.assertEqual(descriptors["intel-briefing"]["surface"]["path"], "/api/briefing")
        self.assertEqual(
            descriptors["intel-briefing"]["surface"]["selection_strategy"],
            "prefer_latest_protocol_backed_briefing_else_latest_briefing",
        )
        self.assertIn(
            "recommended_action",
            descriptors["intel-health"]["output_contract"]["required_control_plane_event_fields"],
        )
        self.assertIn(
            "recommended_action",
            descriptors["intel-ops-overview"]["output_contract"]["required_control_plane_event_fields"],
        )

    def test_registry_schema_and_registry_json_are_present_and_consistent(self):
        registry_path = REPO_ROOT / "agent_skills" / "intel_tool_registry.json"
        schema_path = REPO_ROOT / "specs/002-intel-agent-skills/contracts/intel-tool-registry.schema.json"

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertEqual(registry["$schema"], str(schema_path))
        self.assertEqual(schema["title"], "Deep Scavenger Intel Tool Registry")
        self.assertEqual(schema["properties"]["kind"]["const"], registry["kind"])

    def test_cli_print_registry_emits_machine_readable_registry(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/intel_tool_runtime.py"),
                "--print-registry",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(completed.stdout)
        descriptors = {tool["name"]: tool for tool in payload["tools"]}

        self.assertEqual(payload["contract_version"], CONTRACT_VERSION)
        self.assertEqual(descriptors["intel-health"]["surface"]["base_url"], "http://127.0.0.1:8767")
        self.assertEqual(descriptors["intel-ops-overview"]["surface"]["path"], "/api/ops_overview")
        self.assertIn("/api/deep_briefings", descriptors["intel-briefing"]["surface"]["auxiliary_paths"])


class SourceHealthTriageRuntimeTests(unittest.TestCase):
    def test_triages_stale_source_with_high_confidence(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {
                    "reddit": {
                        "label": "Reddit",
                        "state": "stale",
                        "healthy": False,
                        "age_minutes": 67,
                        "last_success_at": "2026-04-03T06:00:00.000Z",
                        "last_run_status": "success",
                    },
                },
                "local_ai_control_plane": {"gateway": {"healthy": True, "state": "ok"}},
                "control_plane_alerts": {"healthy": True, "state": "idle", "event_count": 0, "sent": 0, "suppressed": 0, "kinds": []},
                "scoring_pipeline": {"healthy": True, "state": "healthy", "stale_count": 0},
            },
            "/api/ops_overview": {
                "scoring_pipeline": {"healthy": True, "state": "healthy", "stale_count": 0},
            },
        }

        envelope = build_source_health_triage_envelope("reddit", fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["skill_name"], "source-health-triage")
        self.assertEqual(envelope["status"], "degraded")
        self.assertEqual(envelope["confidence"], "high")
        self.assertIn("Reddit: state=stale", envelope["summary"])
        self.assertTrue(any("age=67 minutes" in finding for finding in envelope["findings"]))
        self.assertTrue(any("Reddit" in action for action in envelope["next_actions"]))

    def test_triages_scoring_pipeline_backlog(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {},
                "local_ai_control_plane": {"gateway": {"healthy": True, "state": "ok"}},
                "control_plane_alerts": {"healthy": True, "state": "idle", "event_count": 0, "sent": 0, "suppressed": 0, "kinds": []},
                "scoring_pipeline": {"healthy": False, "state": "stale_backlog", "stale_count": 9, "oldest_age_minutes": 42},
            },
            "/api/ops_overview": {
                "scoring_pipeline": {"healthy": False, "state": "stale_backlog", "stale_count": 9, "oldest_age_minutes": 42},
            },
        }

        envelope = build_source_health_triage_envelope("scoring_pipeline", fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "degraded")
        self.assertEqual(envelope["confidence"], "high")
        self.assertIn("scoring_pipeline: state=stale_backlog", envelope["summary"])
        self.assertTrue(any("stale_count=9" in finding for finding in envelope["findings"]))

    def test_triages_local_ai_control_plane(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {},
                "local_ai_control_plane": {
                    "gateway": {"healthy": True, "state": "ok"},
                    "ollama": {"healthy": True, "state": "ok"},
                    "quick_contract": {"healthy": False, "state": "failed"},
                    "watchdog": {"healthy": False, "state": "failing"},
                },
                "control_plane_alerts": {"healthy": True, "state": "idle", "event_count": 0, "sent": 0, "suppressed": 0, "kinds": []},
                "scoring_pipeline": {"healthy": True, "state": "healthy", "stale_count": 0},
            },
            "/api/ops_overview": {
                "scoring_pipeline": {"healthy": True, "state": "healthy", "stale_count": 0},
            },
        }

        envelope = build_source_health_triage_envelope("local_ai_control_plane", fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "degraded")
        self.assertEqual(envelope["confidence"], "medium")
        self.assertTrue(any("quick_contract state=failed" in finding for finding in envelope["findings"]))
        self.assertTrue(any("watchdog state=failing" in finding for finding in envelope["findings"]))

    def test_triages_control_plane_alerts(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {},
                "local_ai_control_plane": {
                    "gateway": {"healthy": True, "state": "ok"},
                    "ollama": {"healthy": True, "state": "ok"},
                    "quick_contract": {"healthy": True, "state": "passed"},
                    "watchdog": {"healthy": True, "state": "ok"},
                },
                "control_plane_alerts": {
                    "healthy": False,
                    "state": "suppressed",
                    "enabled": True,
                    "event_count": 1,
                    "sent": 0,
                    "suppressed": 1,
                    "kinds": ["harness_failed"],
                    "events": [
                        {
                            "kind": "harness_failed",
                            "severity": "critical",
                            "summary": "Harness attention required (failed=1, degraded=0, attention=1).",
                            "dedupe_key": "harness_failed",
                            "recommended_action": "Inspect recent harness attention runs and failing findings before trusting the pipeline.",
                        }
                    ],
                    "checked_at": "2026-04-03T08:12:00.000Z",
                },
                "scoring_pipeline": {"healthy": True, "state": "healthy", "stale_count": 0},
            },
            "/api/ops_overview": {
                "control_plane_alerts": {
                    "healthy": False,
                    "state": "suppressed",
                    "enabled": True,
                    "event_count": 1,
                    "sent": 0,
                    "suppressed": 1,
                    "kinds": ["harness_failed"],
                },
                "scoring_pipeline": {"healthy": True, "state": "healthy", "stale_count": 0},
            },
        }

        envelope = build_source_health_triage_envelope("control_plane_alerts", fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "degraded")
        self.assertEqual(envelope["confidence"], "medium")
        self.assertIn("control_plane_alerts: state=suppressed", envelope["summary"])
        self.assertTrue(any("active kinds=harness_failed" in finding for finding in envelope["findings"]))
        self.assertTrue(any("top event=harness_failed" in finding for finding in envelope["findings"]))
        self.assertTrue(any("control-plane alert kinds" in action.lower() for action in envelope["next_actions"]))
        self.assertTrue(any("Inspect recent harness attention runs" in action for action in envelope["next_actions"]))

    def test_rejects_unknown_target(self):
        payloads = {
            "/api/health": {
                "status": "OPERATIONAL",
                "source_health": {},
                "local_ai_control_plane": {},
                "control_plane_alerts": {},
                "scoring_pipeline": {},
            },
            "/api/ops_overview": {
                "scoring_pipeline": {},
            },
        }

        envelope = build_source_health_triage_envelope("does-not-exist", fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "failed")
        self.assertEqual(envelope["errors"][0]["code"], "unknown_target")


class BriefingAnalystRuntimeTests(unittest.TestCase):
    def test_analyzes_protocol_backed_briefing(self):
        payloads = {
            "/api/briefing": {
                "date": "2026-04-03",
                "content": "briefing body",
                "item_count": 8,
                "protocol_available": True,
                "trace_generated_at": "2026-04-03T08:00:00Z",
                "briefing_protocol": {
                    "verdict": {
                        "headline": "Structure-layer shift is actionable.",
                        "confidence": "high",
                        "summary": "Cross-source support is present.",
                        "action_bias": "act",
                    },
                    "evidence_matrix": {
                        "cross_source_confirmation_count": 3,
                        "supporting_refs": ["[1]", "[36]", "[42]"],
                        "conflict_signals": [],
                    },
                },
                "final_claims": ["Claim 1", "Claim 2"],
            },
            "/api/ops_overview": {
                "latest_briefing": {
                    "date": "2026-04-03",
                    "protocol_available": True,
                    "trace_generated_at": "2026-04-03T08:00:00Z",
                }
            },
        }

        envelope = build_briefing_analyst_envelope(fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["confidence"], "high")
        self.assertIn("Protocol briefing", envelope["summary"])
        self.assertTrue(any("action_bias=act" in finding for finding in envelope["findings"]))
        self.assertTrue(any(item["source"] == "intel-briefing" for item in envelope["evidence"]))
        self.assertTrue(any("act-biased" in action for action in envelope["next_actions"]))

    def test_marks_partial_when_protocol_is_missing(self):
        payloads = {
            "/api/briefing": {
                "date": "2026-04-01",
                "content": "legacy briefing",
                "item_count": 43,
                "protocol_available": False,
                "briefing_protocol": None,
                "final_claims": [],
            },
            "/api/ops_overview": {
                "latest_briefing": None,
            },
        }

        envelope = build_briefing_analyst_envelope(fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "partial")
        self.assertEqual(envelope["confidence"], "low")
        self.assertIn("Legacy-only briefing", envelope["summary"])
        self.assertTrue(any("Protocol fields are unavailable" in finding for finding in envelope["findings"]))

    def test_marks_partial_when_conflict_signals_exist(self):
        payloads = {
            "/api/briefing": {
                "date": "2026-04-03",
                "content": "briefing body",
                "item_count": 8,
                "protocol_available": True,
                "trace_generated_at": "2026-04-03T08:00:00Z",
                "briefing_protocol": {
                    "verdict": {
                        "headline": "Action is tempting.",
                        "confidence": "high",
                        "summary": "But there is conflict.",
                        "action_bias": "act",
                    },
                    "evidence_matrix": {
                        "cross_source_confirmation_count": 1,
                        "supporting_refs": ["[1]"],
                        "conflict_signals": ["Source conflict"],
                    },
                },
                "final_claims": [],
            },
            "/api/ops_overview": {
                "latest_briefing": {
                    "date": "2026-04-03",
                    "protocol_available": True,
                }
            },
        }

        envelope = build_briefing_analyst_envelope(fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "partial")
        self.assertEqual(envelope["confidence"], "medium")
        self.assertTrue(any("Conflict signals" in finding for finding in envelope["findings"]))
        self.assertTrue(any("Review conflict signals" in action for action in envelope["next_actions"]))

    def test_marks_legacy_fallback_protocol_as_partial(self):
        payloads = {
            "/api/briefing": {
                "date": "2026-04-01",
                "content": "legacy fallback briefing",
                "item_count": 43,
                "protocol_available": True,
                "protocol_mode": "legacy_fallback",
                "trace_generated_at": "2026-04-01T19:52:26Z",
                "briefing_protocol": {
                    "verdict": {
                        "headline": "Legacy snapshot still points to a structure-layer shift.",
                        "confidence": "medium",
                        "summary": "This verdict was synthesized from legacy trace evidence.",
                        "action_bias": "track",
                    },
                    "evidence_matrix": {
                        "cross_source_confirmation_count": 2,
                        "supporting_refs": ["[1]", "[2]"],
                        "conflict_signals": [],
                    },
                },
                "final_claims": ["Claim 1", "Claim 2"],
            },
            "/api/ops_overview": {
                "latest_briefing": {
                    "date": "2026-04-01",
                    "protocol_available": True,
                    "protocol_mode": "legacy_fallback",
                }
            },
        }

        envelope = build_briefing_analyst_envelope(fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "partial")
        self.assertEqual(envelope["confidence"], "medium")
        self.assertIn("Legacy-fallback protocol briefing", envelope["summary"])
        self.assertTrue(any("protocol_mode=legacy_fallback" in finding for finding in envelope["findings"]))
        self.assertTrue(any("synthesized from a legacy trace fallback" in finding for finding in envelope["findings"]))
        self.assertTrue(any("native protocol-side judgment" in action for action in envelope["next_actions"]))

    def test_handles_empty_briefing(self):
        payloads = {
            "/api/briefing": {
                "content": None,
                "message": "尚未生成简报。",
            },
            "/api/ops_overview": {
                "latest_briefing": None,
            },
        }

        envelope = build_briefing_analyst_envelope(fetch_json=_make_fetcher(payloads))

        self.assertEqual(envelope["status"], "partial")
        self.assertEqual(envelope["confidence"], "unknown")
        self.assertIn("No current briefing content", envelope["summary"])


if __name__ == "__main__":
    unittest.main()
