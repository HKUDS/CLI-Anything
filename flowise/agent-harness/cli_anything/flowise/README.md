# Flowise CLI

Manage Flowise workflows and run predictions from the terminal. The CLI uses the
Flowise REST API against a local or remote instance.

## Install

```bash
pip install -e .
```

Set `FLOWISE_URL` to the server URL, or pass `--url`. The default is
`http://127.0.0.1:3000`. Set `FLOWISE_API_KEY` to a bearer API key with access to
the workflow management endpoints. For protected prediction endpoints, set the
flow's own `FLOWISE_PREDICTION_KEY`. Credentials are read from the environment.

## Workflow

```bash
cli-anything-flowise --json flow list
cli-anything-flowise --json flow export FLOW_ID > graph.json
cli-anything-flowise --json flow create "Support workflow" graph.json
cli-anything-flowise --json flow update FLOW_ID --name "Support v2" --graph graph.json
cli-anything-flowise --json flow deploy FLOW_ID
cli-anything-flowise --json flow show FLOW_ID
cli-anything-flowise --json predict FLOW_ID --question "How do I reset my password?"
```

An exported graph is a JSON object containing `nodes` and `edges` arrays. Use
`--type AGENTFLOW` when creating an Agentflow V2 graph. The graph references
credentials and integrations configured on the target server.

`flow deploy` sets the deployed flag in Flowise. The server manages execution
and any model or integration configured in the graph. Predictions return the
service's non-streaming JSON response. Run `cli-anything-flowise` without a
subcommand to open the REPL.

## Tests

```bash
python -m pytest cli_anything/flowise/tests/test_core.py
```

Run the installed-command E2E test only against a disposable Flowise instance.
Set `FLOWISE_E2E=1`, `FLOWISE_URL`, and `FLOWISE_API_KEY` and run
`python -m pytest cli_anything/flowise/tests/test_full_e2e.py`. The test creates
and removes its own Agentflow and runs it without model credentials.
