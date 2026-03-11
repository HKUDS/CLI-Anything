# cli-anything:list Command

> Historical slash-command spec. In skill mode, follow the same workflow without requiring `/cli-anything:list` command support.

List all available CLI-Anything tools (installed and generated).

## Usage

```bash
/cli-anything:list [--path <directory>] [--depth <n>] [--json]
```

## Options

- `--path <directory>` - Directory to search for generated CLIs (default: current directory)
- `--depth <n>` - Maximum recursion depth for scanning (default: unlimited). Use `0` for current directory only, `1` for one level deep, etc.
- `--json` - Output in JSON format for machine parsing

## What This Command Does

Displays all CLI-Anything tools available in the system:

### 1. Installed CLIs

Uses `importlib.metadata` to find installed `cli-anything-*` packages:
- Pattern: package name starts with `cli-anything-`
- Extracts: software name, version, entry point

```python
from importlib.metadata import distributions

installed = {}
for dist in distributions():
    name = dist.metadata.get("Name", "")
    if name.startswith("cli-anything-"):
        software = name.replace("cli-anything-", "")
        version = dist.version
        # Find executable via entry points or shutil.which
        executable = shutil.which(f"cli-anything-{software}")
        installed[software] = {
            "status": "installed",
            "version": version,
            "executable": executable
        }
```

### 2. Generated CLIs

Uses `glob` to find local CLI directories:
- Pattern: `**/agent-harness/cli_anything/*/__init__.py` (or depth-limited variant)
- Extracts: software name, version (from setup.py), source path
- Status: `generated`

```python
from pathlib import Path
import glob
import re

search_path = args.get("path", ".")
max_depth = args.get("depth", None)  # None means unlimited
generated = {}

def extract_version_from_setup(setup_path):
    """Extract version from setup.py using regex."""
    try:
        content = Path(setup_path).read_text()
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        return match.group(1) if match else None
    except:
        return None

def build_glob_patterns(base_path, depth):
    """Build list of glob patterns for depths 0 through max_depth.

    Returns multiple patterns so that --depth 2 finds tools at depth 0, 1, AND 2.
    """
    base = Path(base_path)
    suffix = "agent-harness/cli_anything/*/__init__.py"

    if depth is None:
        # Unlimited depth: use **
        return [str(base / "**" / suffix)]

    # Generate patterns for all depths from 0 to max_depth
    patterns = []
    for d in range(depth + 1):
        if d == 0:
            # depth 0: look in current directory
            patterns.append(str(base / suffix))
        else:
            # depth N: look N levels deep
            prefix = "/".join(["*"] * d)
            patterns.append(str(base / prefix / suffix))
    return patterns

patterns = build_glob_patterns(search_path, max_depth)
for pattern in patterns:
    for init_file in glob.glob(pattern, recursive=True):
    parts = Path(init_file).parts
    # Find cli_anything/<software> pattern
    for i, p in enumerate(parts):
        if p == "cli_anything" and i + 1 < len(parts):
            software = parts[i + 1]
            # Get agent-harness directory as source
            agent_harness_idx = parts.index("agent-harness") if "agent-harness" in parts else i - 1
            source = str(Path(*parts[:agent_harness_idx + 2]))  # up to agent-harness
            # Extract version from setup.py (setup.py is in agent-harness/, not cli_anything/)
            setup_path = Path(*parts[:agent_harness_idx + 1]) / "setup.py"
            version = extract_version_from_setup(setup_path)
            generated[software] = {
                "status": "generated",
                "version": version,
                "executable": None,
                "source": source
            }
            break
```

### 3. Merge Results

- Deduplicate by software name
- If both installed and generated: show `installed` status with both paths
- The `source` field shows where the generated code is (even for installed)

## Output Formats

### Table Format (default)

```
CLI-Anything Tools (found 5)

Name            Status      Version   Source
──────────────────────────────────────────────────────────────
gimp            installed   1.0.0     ./gimp/agent-harness
blender         installed   1.0.0     ./blender/agent-harness
inkscape        generated   1.0.0     ./inkscape/agent-harness
audacity        generated   1.0.0     ./audacity/agent-harness
libreoffice     generated   1.0.0     ./libreoffice/agent-harness
```

### JSON Format (--json)

```json
{
  "tools": [
    {
      "name": "gimp",
      "status": "installed",
      "version": "1.0.0",
      "executable": "/usr/local/bin/cli-anything-gimp",
      "source": "./gimp/agent-harness"
    },
    {
      "name": "inkscape",
      "status": "generated",
      "version": "1.0.0",
      "executable": null,
      "source": "./inkscape/agent-harness"
    }
  ],
  "total": 2,
  "installed": 1,
  "generated_only": 1
}
```

## Error Handling

| Scenario | Action |
|----------|--------|
| No CLIs found | Show "No CLI-Anything tools found" message |
| Invalid --path | Show error: "Path not found: <path>" |
| Permission denied | Skip directory, continue scanning, show warning |

## Implementation Steps

When this command is invoked, the agent should:

1. **Parse arguments**
   - Extract `--path` value (default: `.`)
   - Extract `--depth` value (default: `None` for unlimited recursion)
   - Extract `--json` flag (default: false)

2. **Validate path exists**
   - If `--path` specified and doesn't exist, show error and exit

3. **Scan installed CLIs**
   - Use `importlib.metadata.distributions()` to find all packages
   - Filter for packages starting with `cli-anything-`
   - Extract name, version, find executable path

4. **Scan generated CLIs**
   - Build glob pattern based on depth parameter
   - Use `glob.glob(pattern, recursive=True)`
   - Parse directory structure to extract software name
   - Calculate relative path from current directory

5. **Merge results**
   - Create dict keyed by software name
   - Prefer installed data when both exist
   - Keep source path from generated if available

6. **Format output**
   - If `--json`: output JSON to stdout
   - Otherwise: format as table with proper alignment

7. **Print results**
   - Show summary line with count
   - Show table or JSON

## Examples

```bash
# List all tools in current directory (unlimited depth)
/cli-anything:list

# List tools with depth limit (only scan 2 levels deep)
/cli-anything:list --depth 2

# List tools in current directory only (no recursion)
/cli-anything:list --depth 0

# List tools with JSON output
/cli-anything:list --json

# Search a specific directory with depth limit
/cli-anything:list --path /projects/my-tools --depth 3

# Combined
/cli-anything:list --path ./output --depth 2 --json
```

## Notes

- `--depth` controls how many directory levels to descend from the search path
- Default depth is unlimited (`**` glob pattern)
- CLI-Anything tools typically need at least 3-4 levels to find `agent-harness/cli_anything/software/__init__.py`
- Relative paths are preferred for readability
- The command should work without any external dependencies beyond Python stdlib
