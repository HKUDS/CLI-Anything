"""Workflow scaffolds — ready-to-use workflow templates based on proven patterns.

Based on the 5 core patterns from real n8n workflow analysis.
"""

from __future__ import annotations

from typing import Any


PATTERNS: dict[str, dict[str, Any]] = {
    "webhook": {
        "description": "Receive HTTP requests, process, and respond",
        "workflow": {
            "name": "Webhook Processing",
            "nodes": [
                {"parameters": {"path": "my-webhook", "responseMode": "responseNode", "options": {}}, "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0], "name": "Webhook", "webhookId": "scaffold-webhook"},
                {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [], "combinator": "and"}, "options": {}}, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [220, 0], "name": "Validate"},
                {"parameters": {"options": {}}, "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [440, -80], "name": "Transform"},
                {"parameters": {"respondWith": "json", "responseBody": "={{ JSON.stringify({ success: true, data: $json }) }}", "options": {}}, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [660, -80], "name": "Respond OK"},
                {"parameters": {"respondWith": "json", "responseBody": "={{ JSON.stringify({ success: false, error: 'Validation failed' }) }}", "responseCode": 400, "options": {}}, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [440, 120], "name": "Respond Error"},
            ],
            "connections": {
                "Webhook": {"main": [[{"node": "Validate", "type": "main", "index": 0}]]},
                "Validate": {"main": [[{"node": "Transform", "type": "main", "index": 0}], [{"node": "Respond Error", "type": "main", "index": 0}]]},
                "Transform": {"main": [[{"node": "Respond OK", "type": "main", "index": 0}]]},
            },
            "settings": {"executionOrder": "v1"},
        },
    },
    "api": {
        "description": "Fetch from REST API, transform, and store",
        "workflow": {
            "name": "API Integration",
            "nodes": [
                {"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 0], "name": "Manual Trigger"},
                {"parameters": {"url": "https://api.example.com/data", "options": {}}, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [220, 0], "name": "HTTP Request"},
                {"parameters": {"options": {}}, "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [440, 0], "name": "Transform Data"},
                {"parameters": {"options": {}}, "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [660, 0], "name": "Output"},
            ],
            "connections": {
                "Manual Trigger": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]},
                "HTTP Request": {"main": [[{"node": "Transform Data", "type": "main", "index": 0}]]},
                "Transform Data": {"main": [[{"node": "Output", "type": "main", "index": 0}]]},
            },
            "settings": {"executionOrder": "v1"},
        },
    },
    "database": {
        "description": "Read from database, transform, write to destination",
        "workflow": {
            "name": "Database Sync",
            "nodes": [
                {"parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}}, "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [0, 0], "name": "Schedule"},
                {"parameters": {"operation": "executeQuery", "query": "SELECT * FROM source_table LIMIT 100", "options": {}}, "type": "n8n-nodes-base.postgres", "typeVersion": 2.5, "position": [220, 0], "name": "Read Source"},
                {"parameters": {"options": {}}, "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [440, 0], "name": "Transform"},
                {"parameters": {"options": {}}, "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [660, 0], "name": "Write Destination"},
            ],
            "connections": {
                "Schedule": {"main": [[{"node": "Read Source", "type": "main", "index": 0}]]},
                "Read Source": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]},
                "Transform": {"main": [[{"node": "Write Destination", "type": "main", "index": 0}]]},
            },
            "settings": {"executionOrder": "v1"},
        },
    },
    "ai-agent": {
        "description": "AI agent with tools and memory",
        "workflow": {
            "name": "AI Agent",
            "nodes": [
                {"parameters": {"options": {"systemMessage": "You are a helpful assistant."}}, "type": "@n8n/n8n-nodes-langchain.agent", "typeVersion": 1.7, "position": [440, 0], "name": "AI Agent"},
                {"parameters": {}, "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 0], "name": "Manual Trigger"},
                {"parameters": {"options": {"model": "gpt-4o-mini"}}, "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi", "typeVersion": 1.2, "position": [220, 200], "name": "OpenAI Chat Model"},
                {"parameters": {}, "type": "@n8n/n8n-nodes-langchain.memoryBufferWindow", "typeVersion": 1.3, "position": [460, 200], "name": "Window Buffer Memory"},
            ],
            "connections": {
                "Manual Trigger": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
                "OpenAI Chat Model": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
                "Window Buffer Memory": {"ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]},
            },
            "settings": {"executionOrder": "v1"},
        },
    },
    "scheduled": {
        "description": "Recurring task: fetch, process, deliver, log",
        "workflow": {
            "name": "Scheduled Task",
            "nodes": [
                {"parameters": {"rule": {"interval": [{"field": "days", "daysInterval": 1, "triggerAtHour": 8}]}}, "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [0, 0], "name": "Daily 8AM"},
                {"parameters": {"url": "https://api.example.com/report", "options": {}}, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [220, 0], "name": "Fetch Data"},
                {"parameters": {"options": {}}, "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [440, 0], "name": "Process"},
                {"parameters": {"options": {}}, "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [660, 0], "name": "Deliver"},
            ],
            "connections": {
                "Daily 8AM": {"main": [[{"node": "Fetch Data", "type": "main", "index": 0}]]},
                "Fetch Data": {"main": [[{"node": "Process", "type": "main", "index": 0}]]},
                "Process": {"main": [[{"node": "Deliver", "type": "main", "index": 0}]]},
            },
            "settings": {"executionOrder": "v1"},
        },
    },
}


def list_patterns() -> list[dict[str, str]]:
    """List available scaffold patterns."""
    return [{"name": name, "description": p["description"]} for name, p in PATTERNS.items()]


def get_scaffold(pattern: str, *, name: str | None = None) -> dict[str, Any]:
    """Get a scaffold workflow for a pattern. Returns a deep copy."""
    import copy
    if pattern not in PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern}. Available: {', '.join(PATTERNS.keys())}")
    wf = copy.deepcopy(PATTERNS[pattern]["workflow"])
    if name:
        wf["name"] = name
    return wf
