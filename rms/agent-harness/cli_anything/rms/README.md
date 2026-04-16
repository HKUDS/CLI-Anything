# cli-anything-rms

CLI harness for [Teltonika RMS](https://rms.teltonika-networks.com/) — manage devices, alerts, configurations, and more from the command line.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=rms/agent-harness
```

Or for development:

```bash
cd rms/agent-harness
pip install -e ".[dev]"
```

## Authentication

1. Log in to your Teltonika RMS account
2. Enable 2FA in Security settings (required)
3. Create a Personal Access Token in Applications settings
4. Set the token:

```bash
# Option A: Environment variable
export RMS_API_TOKEN=your_token_here

# Option B: CLI config
cli-anything-rms config set api_token your_token_here
```

## Usage

### One-shot commands

```bash
# List all devices
cli-anything-rms devices list

# Get device details
cli-anything-rms devices get 12345

# List online devices with JSON output
cli-anything-rms --json devices list --status online

# List alerts for a device
cli-anything-rms alerts list --device 12345

# Get device location
cli-anything-rms location get 12345
```

### Interactive REPL

```bash
cli-anything-rms
```

### All command groups

| Group | Description |
|-------|-------------|
| `devices` | List, get, update, delete devices |
| `companies` | Manage companies |
| `users` | Manage users and invitations |
| `tags` | Manage device tags |
| `alerts` | View alerts and manage alert configurations |
| `configs` | View and update device configurations |
| `remote-access` | Manage remote access sessions |
| `logs` | View and manage device logs |
| `location` | Get device location and history |
| `credits` | View credits and transfer codes |
| `files` | Manage files |
| `reports` | Manage reports and templates |
| `hotspots` | Manage device hotspots |
| `passwords` | View and update device passwords |
| `smtp` | Manage SMTP configurations |
| `auth` | Test API connectivity |
| `config` | Manage local CLI configuration |

## Testing

```bash
# Unit tests (no API token needed)
pytest tests/test_core.py -v

# E2E tests (requires RMS_API_TOKEN)
pytest tests/test_full_e2e.py -v
```
