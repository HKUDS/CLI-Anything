#!/bin/bash

# Demo Script: Train 5 Tasks Using Real Examples + Test All Features
# Uses real example data from examples/ directory
# Usage: bash demo_real_examples.sh [path_to_examples_dir] [path_to_weights_dir]

set -e

echo "🚀 Uni-Mol Tools - 5 Real Examples + Feature Testing Demo"
echo "=========================================================="
echo ""

# Configuration
PROJECT_DIR="demo_projects"

# Get examples directory from argument or ask user
if [ -n "$1" ]; then
    EXAMPLES_DIR="$1"
else
    # Try relative path first
    if [ -d "../examples" ]; then
        EXAMPLES_DIR="../examples"
    else
        echo "Please provide the path to examples directory:"
        echo "Usage: bash demo_real_examples.sh <path_to_examples> [path_to_weights]"
        echo ""
        echo "Example:"
        echo "  bash demo_real_examples.sh /path/to/examples /path/to/weights"
        echo ""
        exit 1
    fi
fi

# Set weights directory
if [ -n "$2" ]; then
    # Use provided weights path
    export UNIMOL_WEIGHT_DIR="$2"
    echo "Using weights directory: $UNIMOL_WEIGHT_DIR"
elif [ -n "$UNIMOL_WEIGHT_DIR" ]; then
    # Use existing environment variable
    echo "Using weights directory from env: $UNIMOL_WEIGHT_DIR"
else
    # Try to find weights in common locations
    POSSIBLE_WEIGHTS=(
        "../Uni-Mol/unimol_tools/unimol_tools/weights"
        "../../Uni-Mol/unimol_tools/unimol_tools/weights"
        "../../../Uni-Mol/unimol_tools/unimol_tools/weights"
    )

    for WEIGHTS_PATH in "${POSSIBLE_WEIGHTS[@]}"; do
        if [ -d "$WEIGHTS_PATH" ]; then
            export UNIMOL_WEIGHT_DIR="$(cd "$WEIGHTS_PATH" && pwd)"
            echo "Found weights directory: $UNIMOL_WEIGHT_DIR"
            break
        fi
    done

    if [ -z "$UNIMOL_WEIGHT_DIR" ]; then
        echo "⚠️  Warning: Weights directory not found. Weights will be downloaded."
        echo "   To avoid downloading, set UNIMOL_WEIGHT_DIR or provide path as 2nd argument:"
        echo "   bash demo_real_examples.sh <examples_path> <weights_path>"
        echo ""
    fi
fi

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

error() {
    echo -e "${RED}✗ $1${NC}"
}

section() {
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Clean up old demo projects
if [ -d "$PROJECT_DIR" ]; then
    info "Cleaning up old demo projects..."
    rm -rf "$PROJECT_DIR"
fi
mkdir -p "$PROJECT_DIR"

# Check if examples directory exists
if [ ! -d "$EXAMPLES_DIR" ]; then
    error "Examples directory not found at: $EXAMPLES_DIR"
    exit 1
fi

# ============================================
# Part 1: Train 5 Example Tasks
# ============================================

section "🎯 Step 1: Train 5 Real Example Tasks"

# Task 1: Binary Classification
info "Task 1: Binary Classification..."
python -m cli_anything.unimol_tools \
    project new \
    --name "task1_binary" \
    --task classification \
    --output-dir "$PROJECT_DIR"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task1_binary/project.json" \
    project set-dataset train "$EXAMPLES_DIR/binary_classification/mol_train.csv"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task1_binary/project.json" \
    train start \
    --epochs 10 \
    --batch-size 16

success "Task 1 completed - Binary Classification"

# Task 2: Regression
info "Task 2: Regression..."
python -m cli_anything.unimol_tools \
    project new \
    --name "task2_regression" \
    --task regression \
    --output-dir "$PROJECT_DIR"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task2_regression/project.json" \
    project set-dataset train "$EXAMPLES_DIR/regression/train.csv"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task2_regression/project.json" \
    train start \
    --epochs 10 \
    --batch-size 16

success "Task 2 completed - Regression"

# Task 3: Multiclass Classification
info "Task 3: Multiclass Classification..."
python -m cli_anything.unimol_tools \
    project new \
    --name "task3_multiclass" \
    --task multiclass \
    --output-dir "$PROJECT_DIR"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task3_multiclass/project.json" \
    project set-dataset train "$EXAMPLES_DIR/multiclass/train.csv"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task3_multiclass/project.json" \
    train start \
    --epochs 10 \
    --batch-size 16

success "Task 3 completed - Multiclass Classification"

# Task 4: Multilabel Classification
info "Task 4: Multilabel Classification..."
python -m cli_anything.unimol_tools \
    project new \
    --name "task4_multilabel_cls" \
    --task multilabel_classification \
    --output-dir "$PROJECT_DIR"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task4_multilabel_cls/project.json" \
    project set-dataset train "$EXAMPLES_DIR/multilabel_classification/train.csv"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task4_multilabel_cls/project.json" \
    train start \
    --epochs 10 \
    --batch-size 16

success "Task 4 completed - Multilabel Classification"

# Task 5: Multilabel Regression
info "Task 5: Multilabel Regression..."
python -m cli_anything.unimol_tools \
    project new \
    --name "task5_multilabel_reg" \
    --task multilabel_regression \
    --output-dir "$PROJECT_DIR"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task5_multilabel_reg/project.json" \
    project set-dataset train "$EXAMPLES_DIR/multilabel_regression/train.csv"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_DIR/task5_multilabel_reg/project.json" \
    train start \
    --epochs 10 \
    --batch-size 16

success "Task 5 completed - Multilabel Regression"

section "✅ All 5 Tasks Training Completed"

echo "Trained Tasks:"
echo "  ✓ Task 1: Binary Classification"
echo "  ✓ Task 2: Regression"
echo "  ✓ Task 3: Multiclass Classification (3 classes)"
echo "  ✓ Task 4: Multilabel Classification (3 labels)"
echo "  ✓ Task 5: Multilabel Regression (3 targets)"

# ============================================
# Part 2: Choose Task 1 for Feature Testing
# ============================================

section "🔬 Step 2: Feature Testing (Using Task 1 - Binary Classification)"

PROJECT_JSON="$PROJECT_DIR/task1_binary/project.json"

info "Selected project: Binary Classification Example"
info "Training 4 more models to demonstrate model management features..."
echo ""

# Train 4 more models for testing model management
for i in {2..5}; do
    info "Training additional model $(($i-1))/4..."
    python -m cli_anything.unimol_tools \
        -p "$PROJECT_JSON" \
        train start \
        --epochs 8 \
        --batch-size 16 \
        > /dev/null 2>&1
    success "Model $i trained"
done

echo ""
success "Total: 5 models trained for Task 1"
info "Now testing all 6 management features..."

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
# Bonus: Test Prediction with Best Model
# ============================================

section "🔮 Bonus: Prediction with Best Model"

info "Making predictions on test set using best model..."
# Get best model run_id using Python to properly parse JSON
BEST_RUN=$(python3 -c "
import json
import sys
try:
    import subprocess
    result = subprocess.run(
        ['python', '-m', 'cli_anything.unimol_tools', '-p', '$PROJECT_JSON', 'models', 'best', '--json'],
        capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout)
    print(data.get('run_id', 'run_001'))
except Exception as e:
    print('run_001', file=sys.stderr)
    print('run_001')
" 2>/dev/null || echo "run_001")

echo "Using model: $BEST_RUN"

python -m cli_anything.unimol_tools \
    -p "$PROJECT_JSON" \
    predict run "$BEST_RUN" "$EXAMPLES_DIR/binary_classification/mol_test.csv" \
    --output "$PROJECT_DIR/predictions.csv"

success "Predictions saved to $PROJECT_DIR/predictions.csv"

# ============================================
# Summary
# ============================================

section "📊 Demo Summary"

echo "✅ TRAINING COMPLETED:"
echo ""
echo "  Task 1: Binary Classification"
echo "    Data: $EXAMPLES_DIR/binary_classification/"
echo "    Models trained: 5"
echo "    Project: $PROJECT_DIR/task1_binary/project.json"
echo ""
echo "  Task 2: Regression"
echo "    Data: $EXAMPLES_DIR/regression/"
echo "    Models trained: 1"
echo "    Project: $PROJECT_DIR/task2_regression/project.json"
echo ""
echo "  Task 3: Multiclass Classification (3 classes)"
echo "    Data: $EXAMPLES_DIR/multiclass/"
echo "    Models trained: 1"
echo "    Project: $PROJECT_DIR/task3_multiclass/project.json"
echo ""
echo "  Task 4: Multilabel Classification (3 labels)"
echo "    Data: $EXAMPLES_DIR/multilabel_classification/"
echo "    Models trained: 1"
echo "    Project: $PROJECT_DIR/task4_multilabel_cls/project.json"
echo ""
echo "  Task 5: Multilabel Regression (3 targets)"
echo "    Data: $EXAMPLES_DIR/multilabel_regression/"
echo "    Models trained: 1"
echo "    Project: $PROJECT_DIR/task5_multilabel_reg/project.json"
echo ""
echo "✅ FEATURE TESTING (on Task 1):"
echo ""
echo "  ✓ Storage Analysis - Disk usage by component"
echo "  ✓ Models Ranking - 5 models ranked by AUC"
echo "  ✓ Best Model - Best performer identified"
echo "  ✓ Model History - Performance trends analyzed"
echo "  ✓ Cleanup Suggestions - Intelligent cleanup suggestions"
echo "  ✓ Model Comparison - Metrics compared between models"
echo "  ✓ Prediction - Test set predictions generated"
echo ""
echo "📁 Output Files:"
find "$PROJECT_DIR" -maxdepth 2 -name "project.json" | sort | awk -v pd="$PROJECT_DIR" '{gsub(pd"/", ""); print "  - " $0}'
echo "  - $PROJECT_DIR/predictions.csv"
echo ""

success "Demo completed successfully!"

echo ""
echo "💡 Next Steps - Test features on other tasks:"
echo ""
echo "  # Storage analysis on regression task"
echo "  python -m cli_anything.unimol_tools -p $PROJECT_DIR/task2_regression/project.json storage"
echo ""
echo "  # Model ranking on multiclass task"
echo "  python -m cli_anything.unimol_tools -p $PROJECT_DIR/task3_multiclass/project.json models rank"
echo ""
echo "  # View storage in JSON format (note: --json must be before subcommand)"
echo "  python -m cli_anything.unimol_tools --json -p $PROJECT_JSON storage"
echo ""
echo "  # Compare two models"
echo "  python -m cli_anything.unimol_tools -p $PROJECT_JSON models compare run_001 run_002"
echo ""
