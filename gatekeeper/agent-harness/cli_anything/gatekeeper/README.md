# cli-anything-gatekeeper

Agent-native CLI for [Gatekeeper AI](https://www.gatekeeper.blog): evaluate supplier bids
against an RFP — compliance matrix with evidence, pricing arithmetic, risk flags, weighted
ranking and an award recommendation — from the terminal or any AI coding agent.

## Install
```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=gatekeeper/agent-harness
# before it is merged upstream, from a local copy:
pip install ./gatekeeper/agent-harness
```

## Quick start
```bash
cli-anything-gatekeeper health
cli-anything-gatekeeper auth login you@company.com
cli-anything-gatekeeper auth complete --link "<sign-in link copied from the email>"
cli-anything-gatekeeper extract ./tender/                 # free preview
cli-anything-gatekeeper evaluate ./tender/ -o report.json # 1 credit
cli-anything-gatekeeper report compliance report.json --status FAIL --mandatory
cli-anything-gatekeeper report markdown report.json -o report.md
```

Add `--json` before any subcommand for machine-readable output. Run with no arguments for
the interactive REPL.

## Environment
| Variable | Purpose |
|---|---|
| `GATEKEEPER_TOKEN` | Use this access token instead of the stored session |
| `GATEKEEPER_URL` | Service base URL (default `https://www.gatekeeper.blog`) |
| `GATEKEEPER_HOME` | Session directory (default `~/.cli-anything-gatekeeper`) |
| `GATEKEEPER_TIMEOUT` | Evaluate timeout in seconds (default 300) |

## Exit codes
`0` ok · `1` error · `2` sign-in required · `3` plan limit — upgrade at gatekeeper.blog/pricing

## Tests
```bash
pip install -e ".[dev]"
pytest cli_anything/gatekeeper/tests -v
GATEKEEPER_LIVE_TOKEN=<token> pytest -k live_real   # one real, credit-consuming evaluation
```
