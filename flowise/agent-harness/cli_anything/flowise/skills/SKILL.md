---
name: cli-anything-flowise
description: Use the Flowise REST API to list, inspect, export, create, update, deploy, or run workflows through cli-anything-flowise.
---

# Flowise

Configure `FLOWISE_URL` and `FLOWISE_API_KEY` for workflow management.
Use `FLOWISE_PREDICTION_KEY` when the selected flow requires a key for predictions.
Read the harness README for installation, authentication, and graph format.

```bash
cli-anything-flowise --json flow list
cli-anything-flowise --json flow show FLOW_ID
cli-anything-flowise --json flow export FLOW_ID
cli-anything-flowise --json flow create "Name" graph.json
cli-anything-flowise --json flow update FLOW_ID --graph graph.json
cli-anything-flowise --json flow deploy FLOW_ID
cli-anything-flowise --json predict FLOW_ID --question "Test question"
```

Use `flow show` to verify persisted changes. Graphs can reference integrations
and credentials that must be configured on the target Flowise server.
