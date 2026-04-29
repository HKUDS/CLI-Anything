# Quick Start Guide

Get started with Uni-Mol Tools CLI in 5 minutes.

---

## Prerequisites

Before starting, ensure you have completed the [Installation Guide](01-INSTALLATION.md).

**Quick check**:
```bash
# Verify installation
cli-anything-unimol-tools --version

# Verify weight directory
echo $UNIMOL_WEIGHT_DIR
```

---

## Your First Project

### Step 1: Create a Project

```bash
# Create a binary classification project
cli-anything-unimol-tools project new -n my_first_project -t classification

# This creates: my_first_project.json
```

**Output**:
```
✓ Created project: my_first_project
  Type: classification
  File: my_first_project.json
```

### Step 2: Inspect Project

```bash
cli-anything-unimol-tools -p my_first_project.json project info
```

**Output**:
```
📁 Project: my_first_project
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type: classification
Created: 2024-01-15 10:30:00
Status: initialized

Datasets:
  Train: not set
  Valid: not set
  Test: not set

Models: 0 runs
Storage: 0B
```

---

## Example: Drug Activity Prediction

We'll build a binary classifier to predict drug activity (active/inactive).

### Prepare Sample Data

Create a CSV file with SMILES and labels:

```bash
cat > train_data.csv << 'EOF'
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(O)=O,1
CC(C)NCC(COc1ccc(CCOCC(O)=O)cc1)O,0
CC(C)(C)NCC(O)COc1ccccc1CC=C,1
CCN(CC)C(=O)Cc1ccccc1,0
EOF
```

**Data format**:
- **SMILES**: Molecular structure (required)
- **label**: Target value
  - Classification: 0, 1, 2, ... (integers)
  - Regression: continuous values (floats)

### Step 3: Set Training Data

```bash
cli-anything-unimol-tools -p my_first_project.json \
  project set-dataset train train_data.csv
```

**Output**:
```
✓ Set train dataset: train_data.csv
  Samples: 4
```

### Step 4: Train a Model

```bash
cli-anything-unimol-tools -p my_first_project.json \
  train start --epochs 10 --batch-size 8
```

**What happens**:
1. Generates 3D conformers for each molecule
2. Encodes molecules with Uni-Mol
3. Trains classifier for 10 epochs
4. Saves model to `models/run_001/`

**Expected output**:
```
🚀 Starting training...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run ID: run_001
Save path: models/run_001

[1/10] Processing conformers... ━━━━━━━━━━━━━━━━━━ 100%
[2/10] Training epoch 1/10... loss: 0.523
[3/10] Training epoch 2/10... loss: 0.412
...
[10/10] Training epoch 10/10... loss: 0.089

✓ Training complete!

Metrics:
  AUC: 0.8723
  Accuracy: 0.85
  Training time: 24.3s

Model saved: models/run_001/
```

### Step 5: Run Predictions

Create test data:

```bash
cat > test_data.csv << 'EOF'
SMILES
CC(C)Cc1ccc(cc1)C(C)C
CCN(CC)C(=O)Cc1ccc
EOF
```

Run predictions:

```bash
cli-anything-unimol-tools -p my_first_project.json \
  predict run run_001 test_data.csv -o predictions.csv
```

**Output**:
```
🔮 Running predictions...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Model: run_001
Test data: test_data.csv (2 samples)

Processing... ━━━━━━━━━━━━━━━━━━ 100%

✓ Predictions saved: predictions.csv
```

**Check results**:
```bash
cat predictions.csv
```

```csv
SMILES,prediction
CC(C)Cc1ccc(cc1)C(C)C,0.87
CCN(CC)C(=O)Cc1ccc,0.23
```

---

## Interactive Features

### Check Storage Usage

```bash
cli-anything-unimol-tools -p my_first_project.json storage
```

**Output**:
```
💾 Storage Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Usage: 182.5MB

  Models        180.3MB ( 98.8%)  █████████████████████████████░
  Conformers      2.2MB (  1.2%)  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Models: 1
  • run_001: 180.3MB (AUC: 0.8723)
```

### Rank Models

After training multiple models:

```bash
cli-anything-unimol-tools -p my_first_project.json models rank
```

**Output**:
```
🏆 Model Ranking
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Based on AUC performance

Rank   Run ID       Score    AUC      Status
──────────────────────────────────────────────────────────────────
🥇 1   run_001      8.7/10   0.8723   Good

💡 Recommendation: Use run_001 for production
   - Highest AUC: 0.8723
```

### Performance History

```bash
cli-anything-unimol-tools -p my_first_project.json models history
```

**Output**:
```
📊 Model Performance History
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total runs: 1
Trend: insufficient_data

AUC Progress:
  run_001      │████████████████████████████████████████████ 0.8723

💡 Insights:
   ✓ Best model: run_001 (AUC: 0.8723)
```

---

## Common Workflows

### Workflow 1: Multiple Training Runs

```bash
# Run 1: Default settings
cli-anything-unimol-tools -p my_first_project.json train start --epochs 10

# Run 2: More epochs
cli-anything-unimol-tools -p my_first_project.json train start --epochs 20

# Run 3: Different batch size
cli-anything-unimol-tools -p my_first_project.json train start --epochs 10 --batch-size 16

# Compare all models
cli-anything-unimol-tools -p my_first_project.json models rank
```

### Workflow 2: Clean Up After Experiments

```bash
# Check storage
cli-anything-unimol-tools -p my_first_project.json storage

# Smart cleanup (keep best 2 models)
cli-anything-unimol-tools -p my_first_project.json cleanup --auto --keep-best=2
```

### Workflow 3: Production Pipeline

```bash
# 1. Train model
cli-anything-unimol-tools -p production.json train start --epochs 20

# 2. Find best model
BEST=$(cli-anything-unimol-tools --json -p production.json models rank | \
       jq -r '.models[0].run_id')

# 3. Run batch predictions
cli-anything-unimol-tools -p production.json \
  predict run $BEST new_compounds.csv -o results.csv

# 4. Archive old models
cli-anything-unimol-tools -p production.json cleanup --auto
```

---

## Task Types

### Binary Classification

```bash
# Drug activity: active (1) or inactive (0)
cli-anything-unimol-tools project new -n drug_activity -t classification
```

**Data format**:
```csv
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(O)=O,1
CCN(CC)C(=O)Cc1ccccc1,0
```

### Regression

```bash
# Solubility prediction
cli-anything-unimol-tools project new -n solubility -t regression
```

**Data format**:
```csv
SMILES,target
CC(C)Cc1ccc(cc1)C(C)C(O)=O,-2.45
CCN(CC)C(=O)Cc1ccccc1,-1.83
```

### Multiclass Classification

```bash
# Toxicity levels: low (0), medium (1), high (2)
cli-anything-unimol-tools project new -n toxicity -t multiclass
```

**Data format**:
```csv
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(O)=O,0
CCN(CC)C(=O)Cc1ccccc1,2
```

### Multilabel Classification

```bash
# Multiple properties (e.g., has_aromatic, has_ring)
cli-anything-unimol-tools project new -n properties -t multilabel_cls
```

**Data format**:
```csv
SMILES,label1,label2,label3
CC(C)Cc1ccc(cc1)C(C)C(O)=O,1,1,0
CCN(CC)C(=O)Cc1ccccc1,1,0,1
```

### Multilabel Regression

```bash
# Multiple continuous properties
cli-anything-unimol-tools project new -n multi_props -t multilabel_reg
```

**Data format**:
```csv
SMILES,prop1,prop2,prop3
CC(C)Cc1ccc(cc1)C(C)C(O)=O,2.45,1.23,0.87
CCN(CC)C(=O)Cc1ccccc1,1.83,2.11,1.45
```

---

## Getting Help

### Command Help

```bash
# General help
cli-anything-unimol-tools --help

# Command-specific help
cli-anything-unimol-tools project --help
cli-anything-unimol-tools train --help
cli-anything-unimol-tools predict --help
cli-anything-unimol-tools cleanup --help
```

### Common Options

```bash
# JSON output (for automation)
cli-anything-unimol-tools --json -p project.json models rank

# Specify project file
cli-anything-unimol-tools -p /path/to/project.json storage

# Version
cli-anything-unimol-tools --version
```

---

## Next Steps

Now that you've completed the quick start:

1. **Learn More Commands**: See [Basic Usage Guide](03-BASIC-USAGE.md)
2. **Explore Interactive Features**: See [Interactive Features Guide](04-INTERACTIVE-FEATURES.md)
3. **Follow Best Practices**: See [Training SOP](../workflows/TRAINING-SOP.md)
4. **Detailed Tutorials**:
   - [Classification Tutorial](../tutorials/CLASSIFICATION.md)
   - [Regression Tutorial](../tutorials/REGRESSION.md)
   - [Advanced Usage](../tutorials/ADVANCED.md)

---

## Quick Reference

### Essential Commands

```bash
# Create project
cli-anything-unimol-tools project new -n NAME -t TYPE

# Set dataset
cli-anything-unimol-tools -p project.json project set-dataset train data.csv

# Train model
cli-anything-unimol-tools -p project.json train start --epochs 10

# Run predictions
cli-anything-unimol-tools -p project.json predict run RUN_ID test.csv

# Check storage
cli-anything-unimol-tools -p project.json storage

# Rank models
cli-anything-unimol-tools -p project.json models rank

# Clean up
cli-anything-unimol-tools -p project.json cleanup --auto
```

### File Locations

```
my_first_project/
├── my_first_project.json        # Project configuration
├── models/                       # Trained models
│   ├── run_001/                 # First training run
│   │   ├── checkpoint.pth       # Model checkpoint
│   │   └── metric.result        # Training metrics
│   └── run_002/                 # Second training run
├── conformers/                   # Cached 3D structures
│   └── *.sdf                    # SDF files
└── predictions/                  # Prediction results
    └── *.csv                    # Prediction CSVs
```

---

## Troubleshooting

### Issue: Training fails with CUDA error

```bash
# Use CPU instead
export CUDA_VISIBLE_DEVICES=""
cli-anything-unimol-tools -p project.json train start --epochs 10
```

### Issue: Conformer generation is slow

```bash
# Generate conformers once, cache for reuse
# Default behavior - conformers are cached in conformers/ directory
# Subsequent runs will be faster
```

### Issue: Out of memory

```bash
# Reduce batch size
cli-anything-unimol-tools -p project.json train start --epochs 10 --batch-size 4
```

For more troubleshooting, see [Troubleshooting Guide](05-TROUBLESHOOTING.md).

---

## Summary

You've learned:
- ✅ Create projects
- ✅ Prepare data
- ✅ Train models
- ✅ Run predictions
- ✅ Use interactive features (storage, ranking, cleanup)
- ✅ Common workflows

**Continue to**: [Basic Usage Guide](03-BASIC-USAGE.md) for comprehensive command reference.
