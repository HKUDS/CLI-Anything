# Alexa harness: analysis and SOP

## Target

Amazon Alexa / Echo devices. Unlike desktop apps in this repo there is no
local program or project file: the "software" is the Alexa cloud service that
the Alexa phone app talks to. The real backend is therefore Amazon's Alexa web
API, reached through `alexapy` (Apache-2.0), the maintained library used by
Home Assistant's Alexa Media Player integration.

## Backend choices

| Option | Verdict |
|---|---|
| Alexa Skills Kit / Smart Home Skill API | Official, but only for building skills; cannot make your own Echo speak or run commands. |
| `alexa-remote-control` shell script | Cookie scraping, brittle login, no 2FA support. |
| `alexapy` | Chosen. Async Python, proxy login with captcha/2FA, refresh tokens, TTS, announcements, routines, music, volume, smart-home lights. |

## Authentication

`auth login` runs `alexapy.AlexaProxy` on 127.0.0.1. The user signs in on
Amazon's real page through it; the proxy captures the OAuth result, then
`AlexaLogin.test_loggedin()` registers this CLI as a device (refresh token +
`mac_dms`), exchanges tokens for web cookies and fetches the CSRF token.
`finalize_login()` saves cookies. The CLI stores the OAuth bundle and device
UUID in `account.json` (0600); every later command rebuilds a session from the
refresh token and re-saves rotated tokens.

## Command design

- `auth` login/status/logout/locale
- `device` list/info (speakers only by default; `--all` for everything)
- `speak`, `announce`, `command`, `sequence`
- `routine` list/run
- `music` play/pause/resume/next/previous/stop, `volume`
- `smarthome` list/light
- `repl` (default with no subcommand)

Pure logic lives in `core/` (device resolution, action validation, smart-home
payload flattening). `utils/alexa_backend.py` is the only module that touches
alexapy or the network. Every mutating command builds an action dict in
`core/actions.py`, which makes `--dry-run` exact: it prints the same action the
backend would send.

## State model

There is no undo for actions on physical devices; they are fire-and-forget.
Persistent state is only the account (tokens, locale) and a cached device list
used for dry-run.

## Known risks

- Amazon changes the private API and login flow from time to time; upgrade
  alexapy when commands start failing.
- alexapy swallows some request errors and logs them instead; `"sent": true`
  means the request was issued, not that the Echo spoke.
