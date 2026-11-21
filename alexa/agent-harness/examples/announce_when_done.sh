#!/usr/bin/env bash
# Run a long command, then have an Echo announce whether it succeeded.
# Usage: examples/announce_when_done.sh "Kitchen" make test
set -u
DEVICE="$1"; shift
"$@"
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
  MSG="Your command finished successfully."
else
  MSG="Your command failed with exit code $STATUS."
fi
cli-anything-alexa --json announce "$MSG" -d "$DEVICE" || true
exit "$STATUS"
