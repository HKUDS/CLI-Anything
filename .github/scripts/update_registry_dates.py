#!/usr/bin/env python3
"""Update registry-dates.json with last modified dates from harness directories."""
import json
import subprocess
from pathlib import Path
from datetime import datetime

def get_last_modified(harness_path):
    """Get the most recent git commit date for files in a harness directory."""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ct', '--', str(harness_path)],
            capture_output=True,
            text=True,
            check=True
        )
        timestamp = int(result.stdout.strip())
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    except (subprocess.CalledProcessError, ValueError):
        return None

def main():
    repo_root = Path(__file__).parent.parent.parent
    registry_path = repo_root / 'registry.json'
    dates_path = repo_root / 'docs' / 'hub' / 'registry-dates.json'

    with open(registry_path) as f:
        data = json.load(f)

    dates = {}
    for cli in data['clis']:
        harness_path = repo_root / cli['name'] / 'agent-harness'
        if harness_path.exists():
            dates[cli['name']] = get_last_modified(harness_path)

    with open(dates_path, 'w') as f:
        json.dump(dates, f, indent=2)

    print(f"Updated dates for {len(dates)} CLI entries")

if __name__ == '__main__':
    main()
