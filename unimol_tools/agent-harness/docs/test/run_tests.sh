#!/bin/bash

# Run all tests for Uni-Mol Tools CLI
# Usage: bash run_tests.sh [options]

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Uni-Mol Tools CLI - Test Suite${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Check if pytest is installed
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${RED}Error: pytest not installed${NC}"
    echo "Install with: pip install pytest pytest-cov pytest-xdist"
    exit 1
fi

# Navigate to project root (from docs/test/ to project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Parse arguments
RUN_UNIT=true
RUN_INTEGRATION=false
RUN_COVERAGE=false
VERBOSE=false
PARALLEL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            RUN_UNIT=true
            RUN_INTEGRATION=false
            shift
            ;;
        --integration)
            RUN_INTEGRATION=true
            RUN_UNIT=false
            shift
            ;;
        --all)
            RUN_UNIT=true
            RUN_INTEGRATION=true
            shift
            ;;
        --coverage)
            RUN_COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--unit|--integration|--all] [--coverage] [-v|--verbose] [--parallel]"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest"
PYTEST_ARGS=""

if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -v"
fi

if [ "$PARALLEL" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -n auto"
fi

if [ "$RUN_COVERAGE" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS --cov=cli_anything.unimol_tools.core --cov-report=html --cov-report=term"
fi

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
echo ""

if [ "$RUN_UNIT" = true ]; then
    echo -e "${YELLOW}=== Unit Tests ===${NC}"
    $PYTEST_CMD $PYTEST_ARGS \
        cli_anything/unimol_tools/tests/test_storage.py \
        cli_anything/unimol_tools/tests/test_models_manager.py \
        cli_anything/unimol_tools/tests/test_cleanup.py \
        cli_anything/unimol_tools/tests/test_core.py \
        -m "not integration" || {
        echo -e "${RED}Unit tests failed!${NC}"
        exit 1
    }
    echo ""
fi

if [ "$RUN_INTEGRATION" = true ]; then
    echo -e "${YELLOW}=== Integration Tests ===${NC}"
    $PYTEST_CMD $PYTEST_ARGS \
        cli_anything/unimol_tools/tests/test_all_tasks.py \
        -m "integration" || {
        echo -e "${RED}Integration tests failed!${NC}"
        exit 1
    }
    echo ""
fi

# Summary
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}All tests passed! ✓${NC}"
echo -e "${GREEN}================================${NC}"

if [ "$RUN_COVERAGE" = true ]; then
    echo ""
    echo -e "${YELLOW}Coverage report generated: htmlcov/index.html${NC}"
fi
