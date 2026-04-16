#!/bin/bash
# Basic video editing workflow using the Shotcut CLI
# This demonstrates how an AI agent would create a simple video project.

set -e
CLI="python3 -m cli.shotcut_cli"
cd "$(dirname "$0")/.."

echo "=== Shotcut CLI: Basic Workflow Example ==="

# 1. Create a new project
echo ""
echo "--- Creating new HD 1080p30 project ---"
$CLI project new --profile hd1080p30 -o /tmp/demo_project.mlt

# 2. Open the project and add tracks
echo ""
echo "--- Adding tracks ---"
$CLI --project /tmp/demo_project.mlt timeline add-track --type video --name "Main Video"

# 3. Show the timeline
echo ""
echo "--- Timeline overview ---"
$CLI --project /tmp/demo_project.mlt timeline show

# 4. List available filters
echo ""
echo "--- Available video filters ---"
$CLI filter list-available --category video

# 5. List export presets
echo ""
echo "--- Export presets ---"
$CLI export presets

# 6. Get project info in JSON (for agent consumption)
echo ""
echo "--- Project info (JSON) ---"
$CLI --json --project /tmp/demo_project.mlt project info

# 7. View available profiles
echo ""
echo "--- Available profiles ---"
$CLI project profiles

# Cleanup
rm -f /tmp/demo_project.mlt
echo ""
echo "=== Done ==="
