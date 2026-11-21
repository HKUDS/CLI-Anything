# cli-anything-alexa

Control your Amazon Echo devices from the command line or from an AI agent:
make an Echo speak or announce, run any voice command as text, trigger
routines, play music, set volume and switch smart-home lights.

It drives Amazon's Alexa web API through
[alexapy](https://gitlab.com/keatontaylor/alexapy), the library behind Home
Assistant's Alexa Media Player. Amazon offers no official API for this, so it
is unofficial and may break when Amazon changes things.

## Requirements

- Python 3.10+
- An Amazon account with at least one Echo device
- A computer with a web browser for the one-time sign-in (run it on your own
  machine, not on a shared server)

## Install

From CLI-Hub:

```bash
cli-hub install alexa
```

Or straight from GitHub:

```bash
pip install "git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=alexa/agent-harness"
```

Or from a checkout of this repository:

```bash
cd alexa/agent-harness
pip install -e .
```

## Sign in (once)

```bash
cli-anything-alexa auth login --email you@example.com
```

This starts a small proxy on a free local port (e.g. `http://127.0.0.1:53712`;
the exact address is printed) and opens it in your browser. Sign in on Amazon's real page (captcha and two-step verification
work). When the page says you are logged in, the CLI saves a refresh token and
registers itself as a device on your Amazon account. Your password is never
stored.

Outside the US, pass your Amazon domain, e.g. `--domain amazon.co.uk`,
`amazon.de`, `amazon.in`, `amazon.ca`, `amazon.com.au`; the speech language is
set to match (en-GB for amazon.co.uk, de-DE for amazon.de, ...). Change it
with `cli-anything-alexa auth locale <locale>`.

Tokens and cookies live in `~/.cli-anything-alexa/` (owner-only permissions;
override with `ALEXA_CLI_HOME`). `auth logout` deletes them. To revoke access
fully, remove the registered device in the Alexa app or at Amazon's
"Manage Your Content and Devices".

## Use

```bash
cli-anything-alexa device list
cli-anything-alexa speak "Kitchen" "Dinner is ready"
cli-anything-alexa announce "Leaving in five minutes"            # all online Echos
cli-anything-alexa announce "Bedtime" -d "Kids Room" -d "Bedroom"
cli-anything-alexa command "Kitchen" "turn off the living room lights"
cli-anything-alexa command "Kitchen" "set a timer for 10 minutes"
cli-anything-alexa sequence "Kitchen" weather
cli-anything-alexa routine list
cli-anything-alexa routine run "Kitchen" "good night"
cli-anything-alexa music play "Kitchen" "lofi beats" --provider spotify
cli-anything-alexa music pause "Kitchen"
cli-anything-alexa volume "Kitchen" 30
cli-anything-alexa smarthome list
cli-anything-alexa smarthome light <entity_id> --on --brightness 40
```

Device names match case-insensitively by full name, unique part of a name, or
serial number.

- `--json` on any command gives machine-readable output; errors come back as
  `{"ok": false, "error": "<code>", "message": "..."}` with exit code 1.
- `--dry-run` validates the command and prints the action without contacting
  Amazon (uses the device list cached by the last `device list`).
- Running `cli-anything-alexa` with no arguments starts an interactive REPL.

## Tests

```bash
pip install -e '.[dev]'
pytest cli_anything/alexa/tests -v
```

Tests against your real account are opt-in:

```bash
ALEXA_E2E=1 pytest cli_anything/alexa/tests/test_full_e2e.py -v -s
ALEXA_E2E=1 ALEXA_E2E_SPEAK=1 ALEXA_E2E_DEVICE="Kitchen" pytest cli_anything/alexa/tests/test_full_e2e.py -v -s
```

## Troubleshooting

- **The browser shows another app instead of Amazon:** another program uses that
  port. Run `auth login` without `--port` so a free port is picked, and open the
  exact address printed in the terminal.
- **`CERTIFICATE_VERIFY_FAILED`:** the CLI already trusts the certifi bundle that
  ships with alexapy. If you still see it (or you set `SSL_CERT_FILE` yourself), run
  `/Applications/Python 3.x/Install Certificates.command` on macOS.
- **"Your Amazon account is on amazon.co.uk, but you signed in with amazon.com":**
  run the `auth logout` and `auth login --domain ...` command the warning prints.
- **Terminal keeps waiting after you signed in:** you finished on amazon.com
  instead of the local page. Use a private window and stay on the `127.0.0.1` page.

## Limits

- Unofficial API: Amazon can change or block it without notice.
- Amazon does not report whether an Echo actually spoke; `"sent": true` means
  Amazon accepted the request.
- `command` behaves like speaking to the Echo, so the Echo answers out loud.
- Smart-home control beyond lights works through `command`, e.g.
  `command "Kitchen" "turn on the fan"`.
