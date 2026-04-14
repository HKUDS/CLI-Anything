#!/bin/bash

# Test Features Only - Skip Training
# Usage: bash test_features.sh [project_json_path]

set -e

# Configuration
if [ -n "$1" ]; then
    PROJECT_JSON="$1"
else
    PROJECT_JSON="demo_projects/task1_binary/project.json"
fi

# Check if project exists
if [ ! -f "$PROJECT_JSON" ]; then
    echo "Error: Project file not found at: $PROJECT_JSON"
    echo ""
    echo "Usage: bash test_features.sh [project_json_path]"
    echo ""
    echo "Example:"
    echo "  bash test_features.sh demo_projects/task1_binary/project.json"
    exit 1
fi

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

section() {
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

echo "🧪 Testing Features on: $PROJECT_JSON"
echo ""

# ============================================
# Feature Test 1: Storage Analysis
# ============================================

section "💾 Feature Test 1: Storage Analysis"

info "Analyzing disk usage by component (models, conformers, predictions)..."
python -m cli_anything.unimol_tools \
    -p "$PROJECT_JSON" \
    storage

success "Storage analysis completed"

# ============================================
# Feature Test 2: Models Ranking
# ============================================

section "🏆 Feature Test 2: Models Ranking"

info "Ranking all models by performance (AUC-based scoring)..."
python -m cli_anything.unimol_tools \
    -p "$PROJECT_JSON" \
    models rank

success "Model ranking completed"

# ============================================
# Feature Test 3: Best Model
# ============================================

section "⭐ Feature Test 3: Best Model"

info "Finding the best performing model..."
python -m cli_anything.unimol_tools \
    -p "$PROJECT_JSON" \
    models best

success "Best model identified"

# ============================================
# Feature Test 4: Model History
# ============================================

section "📈 Feature Test 4: Model History"

info "Viewing performance trends over time..."
python -m cli_anything.unimol_tools \
    -p "$PROJECT_JSON" \
    models history

success "Model history analysis completed"

# ============================================
# Feature Test 5: Cleanup Suggestions
# ============================================

section "🧹 Feature Test 5: Cleanup Suggestions"

info "Getting intelligent suggestions for model cleanup..."
python -m cli_anything.unimol_tools \
    -p "$PROJECT_JSON" \
    cleanup

success "Cleanup suggestions generated"

# ============================================
# Feature Test 6: Model Comparison
# ============================================

section "⚖️  Feature Test 6: Model Comparison"

info "Comparing metrics between first two models..."
python -m cli_anything.unimol_tools \
    -p "$PROJECT_JSON" \
    models compare run_001 run_002

success "Model comparison completed"

# ============================================
# Summary
# ============================================

section "✅ All Feature Tests Completed"

echo "Tested features on: $PROJECT_JSON"
echo ""
echo "💡 Next steps:"
echo "  # Test JSON output"
echo "  python -m cli_anything.unimol_tools -p $PROJECT_JSON storage --json"
echo ""
echo "  # Compare different models"
echo "  python -m cli_anything.unimol_tools -p $PROJECT_JSON models compare run_002 run_003"
echo ""
