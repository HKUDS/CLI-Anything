#!/bin/sh
set -eu

REPO_ROOT="/Users/lixun/Documents/codex "
HOOK_TEMPLATE="$REPO_ROOT/.githooks/pre-push-intel-mcp"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
FORCE=0
CHECK_ONLY=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --hooks-dir)
      HOOKS_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

TARGET="$HOOKS_DIR/pre-push"

if [ ! -f "$HOOK_TEMPLATE" ]; then
  echo "missing hook template: $HOOK_TEMPLATE" >&2
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ -f "$TARGET" ] && grep -q "test_intel_mcp_stack.sh" "$TARGET"; then
    echo "installed"
    exit 0
  fi
  echo "not_installed"
  exit 1
fi

mkdir -p "$HOOKS_DIR"

if [ -f "$TARGET" ] && ! grep -q "test_intel_mcp_stack.sh" "$TARGET"; then
  if [ "$FORCE" -ne 1 ]; then
    echo "existing pre-push hook differs: $TARGET" >&2
    echo "re-run with --force to replace it" >&2
    exit 1
  fi
fi

cp "$HOOK_TEMPLATE" "$TARGET"
chmod +x "$TARGET"
echo "installed $TARGET"
