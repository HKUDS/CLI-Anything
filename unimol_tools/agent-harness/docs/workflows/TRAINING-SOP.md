# Training Workflow SOP

Standard Operating Procedure for training molecular property prediction models with Uni-Mol Tools CLI.

---

## Overview

This SOP covers the complete workflow from data preparation to model deployment.

**Workflow Stages**:
1. Data Preparation
2. Project Initialization
3. Training
4. Evaluation
5. Model Selection
6. Deployment
7. Cleanup

**Estimated Time**: 30-60 minutes (depending on dataset size)

---

## Prerequisites

- Uni-Mol Tools CLI installed
- Training data in CSV format with SMILES column
- UNIMOL_WEIGHT_DIR configured
- Sufficient disk space (~2GB + dataset size)

---

## Workflow Diagram

```
┌──────────────────┐
│  Data Preparation│
│  - Validate SMILES│
│  - Split datasets │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Create Project   │
│  - Choose type   │
│  - Set datasets  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Train Models   │◄────┐
│  - Baseline      │     │
│  - Tune params   │     │ Iterate
└────────┬─────────┘     │
         │               │
         ▼               │
┌──────────────────┐     │
│   Evaluate       │     │
│  - Check metrics │─────┘
│  - Compare runs  │     Not satisfied
└────────┬─────────┘
         │
         ▼  Satisfied
┌──────────────────┐
│  Select Best     │
│  - Rank models   │
│  - Validate      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│    Deploy        │
│  - Run predictions│
│  - Monitor       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│    Cleanup       │
│  - Archive old   │
│  - Keep best     │
└──────────────────┘
```

---

## Stage 1: Data Preparation

### 1.1 Prepare Training Data

**Input**: Raw molecular data

**Output**: Clean CSV with SMILES and labels

**Steps**:

```python
import pandas as pd
from rdkit import Chem

# Load raw data
data = pd.read_csv('raw_data.csv')

# Validate SMILES
def is_valid_smiles(smiles):
    mol = Chem.MolFromSmiles(smiles)
    return mol is not None

data['valid'] = data['SMILES'].apply(is_valid_smiles)
data_clean = data[data['valid']].drop('valid', axis=1)

print(f"Original: {len(data)} molecules")
print(f"Valid: {len(data_clean)} molecules")
print(f"Removed: {len(data) - len(data_clean)} invalid SMILES")

# Save cleaned data
data_clean.to_csv('data_clean.csv', index=False)
```

**Data format**:

**Classification**:
```csv
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(O)=O,1
CCN(CC)C(=O)Cc1ccccc1,0
```

**Regression**:
```csv
SMILES,target
CC(C)Cc1ccc(cc1)C(C)C(O)=O,-2.45
CCN(CC)C(=O)Cc1ccccc1,-1.83
```

### 1.2 Split Datasets

**80/10/10 split** (recommended):

```python
from sklearn.model_selection import train_test_split

# Read cleaned data
data = pd.read_csv('data_clean.csv')

# First split: 80% train+val, 20% test
train_val, test = train_test_split(data, test_size=0.2, random_state=42)

# Second split: 80% train, 20% val (of the 80%)
train, val = train_test_split(train_val, test_size=0.125, random_state=42)  # 0.125 of 0.8 = 0.1

print(f"Train: {len(train)} ({len(train)/len(data)*100:.1f}%)")
print(f"Val:   {len(val)} ({len(val)/len(data)*100:.1f}%)")
print(f"Test:  {len(test)} ({len(test)/len(data)*100:.1f}%)")

# Save
train.to_csv('train.csv', index=False)
val.to_csv('valid.csv', index=False)
test.to_csv('test.csv', index=False)
```

**Verification**:
```bash
wc -l train.csv valid.csv test.csv
```

---

## Stage 2: Project Initialization

### 2.1 Create Project

```bash
# Choose appropriate task type
cli-anything-unimol-tools project new \
  -n my_drug_discovery \
  -t classification
```

**Task types**:
- `classification`: Binary classification (active/inactive)
- `regression`: Continuous values (solubility, logP, etc.)
- `multiclass`: Multiple exclusive classes (low/medium/high toxicity)
- `multilabel_cls`: Multiple binary labels
- `multilabel_reg`: Multiple continuous values

### 2.2 Set Datasets

```bash
PROJECT="my_drug_discovery.json"

# Set training data
cli-anything-unimol-tools -p $PROJECT \
  project set-dataset train train.csv

# Set validation data
cli-anything-unimol-tools -p $PROJECT \
  project set-dataset valid valid.csv

# Set test data
cli-anything-unimol-tools -p $PROJECT \
  project set-dataset test test.csv
```

### 2.3 Verify Setup

```bash
# Check project configuration
cli-anything-unimol-tools -p $PROJECT project info
```

**Expected output**:
```
📁 Project: my_drug_discovery
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type: classification
Created: 2024-01-15 10:30:00
Status: initialized

Datasets:
  Train: train.csv (800 samples)
  Valid: valid.csv (100 samples)
  Test: test.csv (100 samples)

Models: 0 runs
Storage: 0B
```

---

## Stage 3: Training

### 3.1 Baseline Model

**Train with default parameters**:

```bash
# Baseline run
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 10 \
  --batch-size 16
```

**Expected duration**: 2-5 minutes (depends on dataset size)

**Monitor progress**:
- Conformer generation progress bar
- Training epoch progress
- Validation metrics

### 3.2 Hyperparameter Tuning

**Recommended tuning strategy**:

```bash
PROJECT="my_drug_discovery.json"

# Run 1: Baseline (done above)
# AUC: ~0.75-0.80

# Run 2: More epochs
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 16

# Run 3: Larger batch size
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 32

# Run 4: Different learning rate
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 16 \
  --learning-rate 5e-5

# Run 5: Add dropout
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 16 \
  --dropout 0.1
```

**Check progress after each run**:
```bash
cli-anything-unimol-tools -p $PROJECT models history
cli-anything-unimol-tools -p $PROJECT models rank
```

### 3.3 Grid Search (Optional)

For systematic exploration:

```bash
#!/bin/bash
# grid_search.sh

PROJECT="my_drug_discovery.json"

for epochs in 10 20 30; do
  for lr in 1e-4 5e-5 1e-5; do
    for bs in 16 32; do
      echo "Training: epochs=$epochs lr=$lr batch_size=$bs"

      cli-anything-unimol-tools -p $PROJECT train start \
        --epochs $epochs \
        --learning-rate $lr \
        --batch-size $bs

      # Check current best
      cli-anything-unimol-tools -p $PROJECT models rank | head -n 5
    done
  done
done

echo "Grid search complete!"
cli-anything-unimol-tools -p $PROJECT models rank
```

---

## Stage 4: Evaluation

### 4.1 Review Model Ranking

```bash
cli-anything-unimol-tools -p $PROJECT models rank
```

**Look for**:
- AUC > 0.85 (Good/Best)
- Consistent metrics across runs
- Reasonable training time

### 4.2 Analyze Performance History

```bash
cli-anything-unimol-tools -p $PROJECT models history
```

**Check**:
- Trend: Should be "improving" or "stable"
- Best model identification
- No recent performance drops

### 4.3 Test Set Evaluation

After selecting candidate model:

```bash
# Use best model
BEST=$(cli-anything-unimol-tools --json -p $PROJECT models rank | \
       jq -r '.models[0].run_id')

echo "Best model: $BEST"

# Run on test set
cli-anything-unimol-tools -p $PROJECT predict run $BEST test.csv -o test_predictions.csv
```

**Analyze predictions**:
```python
import pandas as pd
from sklearn.metrics import roc_auc_score, accuracy_score

# Load test data and predictions
test = pd.read_csv('test.csv')
pred = pd.read_csv('test_predictions.csv')

# Merge on SMILES
merged = test.merge(pred, on='SMILES')

# Calculate metrics
auc = roc_auc_score(merged['label'], merged['probability'])
acc = accuracy_score(merged['label'], merged['prediction'])

print(f"Test Set Metrics:")
print(f"  AUC: {auc:.4f}")
print(f"  Accuracy: {acc:.4f}")
```

---

## Stage 5: Model Selection

### 5.1 Selection Criteria

**Primary**: Highest AUC on validation set
**Secondary**:
- Test set performance
- Training stability
- Reasonable training time

### 5.2 Select Best Model

```bash
# Rank models
cli-anything-unimol-tools -p $PROJECT models rank

# Extract best
BEST=$(cli-anything-unimol-tools --json -p $PROJECT models rank | \
       jq -r '.models[0].run_id')

echo "Selected model: $BEST"

# Document selection
echo "Model Selection Report" > model_selection.txt
echo "=====================" >> model_selection.txt
echo "" >> model_selection.txt
echo "Selected Model: $BEST" >> model_selection.txt
echo "" >> model_selection.txt
cli-anything-unimol-tools -p $PROJECT models rank >> model_selection.txt
```

---

## Stage 6: Deployment

### 6.1 Validate Model

**Sanity checks**:

```bash
# Check model exists
ls models/$BEST/checkpoint.pth

# Run small prediction test
echo "SMILES" > test_single.csv
echo "CC(C)Cc1ccc(cc1)C(C)C(O)=O" >> test_single.csv

cli-anything-unimol-tools -p $PROJECT predict run $BEST test_single.csv -o test_output.csv

cat test_output.csv
# Should show prediction
```

### 6.2 Production Predictions

```bash
# Run on full production dataset
cli-anything-unimol-tools -p $PROJECT predict run $BEST production_data.csv -o production_predictions.csv

# Verify output
wc -l production_predictions.csv
head production_predictions.csv
```

### 6.3 Monitor Performance

**Create monitoring script**:

```bash
#!/bin/bash
# monitor_predictions.sh

PREDICTIONS="production_predictions.csv"

# Check output file
if [ ! -f "$PREDICTIONS" ]; then
  echo "Error: Predictions file not found"
  exit 1
fi

# Basic statistics
echo "Prediction Statistics"
echo "===================="
echo "Total predictions: $(wc -l < $PREDICTIONS)"

# Distribution (for classification)
python << EOF
import pandas as pd
pred = pd.read_csv('$PREDICTIONS')
print("\nPrediction Distribution:")
print(pred['prediction'].value_counts())
print("\nProbability Statistics:")
print(pred['probability'].describe())
EOF
```

---

## Stage 7: Cleanup

### 7.1 Archive Non-Essential Models

```bash
# Check storage
cli-anything-unimol-tools -p $PROJECT storage

# Keep best 3 models, archive rest
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=3

# Verify
cli-anything-unimol-tools -p $PROJECT storage
```

### 7.2 Backup Important Files

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup project file
cp $PROJECT backups/$(date +%Y%m%d)/

# Backup best model
cp -r models/$BEST backups/$(date +%Y%m%d)/

# Backup predictions
cp production_predictions.csv backups/$(date +%Y%m%d)/
```

### 7.3 Documentation

```bash
# Create project summary
cat > project_summary.md << EOF
# Project: my_drug_discovery

## Summary
- **Task**: Binary classification (drug activity prediction)
- **Dataset**: 1000 molecules (800 train / 100 val / 100 test)
- **Best Model**: $BEST
- **Best AUC**: $(cli-anything-unimol-tools --json -p $PROJECT models rank | jq -r '.models[0].auc')
- **Date**: $(date +%Y-%m-%d)

## Training
- Total runs: $(cli-anything-unimol-tools --json -p $PROJECT project info | jq '.models | length')
- Best hyperparameters: epochs=20, batch_size=16, lr=5e-5

## Deployment
- Production predictions: production_predictions.csv
- Total predictions: $(wc -l < production_predictions.csv)

## Files
- Project: $PROJECT
- Best model: models/$BEST/
- Predictions: production_predictions.csv
- Backup: backups/$(date +%Y%m%d)/
EOF

cat project_summary.md
```

---

## Complete Workflow Script

**Full automated workflow**:

```bash
#!/bin/bash
# complete_workflow.sh

set -e  # Exit on error

PROJECT="drug_discovery.json"
TASK_TYPE="classification"

echo "=== Uni-Mol Tools Training Workflow ==="
echo ""

# Stage 1: Verify data
echo "[1/7] Verifying data..."
if [ ! -f "train.csv" ] || [ ! -f "valid.csv" ] || [ ! -f "test.csv" ]; then
  echo "Error: Missing dataset files"
  exit 1
fi
echo "✓ Data files found"
echo ""

# Stage 2: Create project
echo "[2/7] Creating project..."
if [ -f "$PROJECT" ]; then
  echo "Project already exists, using existing"
else
  cli-anything-unimol-tools project new -n ${PROJECT%.json} -t $TASK_TYPE
fi

cli-anything-unimol-tools -p $PROJECT project set-dataset train train.csv
cli-anything-unimol-tools -p $PROJECT project set-dataset valid valid.csv
cli-anything-unimol-tools -p $PROJECT project set-dataset test test.csv

cli-anything-unimol-tools -p $PROJECT project info
echo ""

# Stage 3: Training
echo "[3/7] Training models..."

# Baseline
echo "Training baseline..."
cli-anything-unimol-tools -p $PROJECT train start --epochs 10 --batch-size 16

# Tuned
echo "Training with more epochs..."
cli-anything-unimol-tools -p $PROJECT train start --epochs 20 --batch-size 16

echo ""

# Stage 4: Evaluation
echo "[4/7] Evaluating models..."
cli-anything-unimol-tools -p $PROJECT models rank
cli-anything-unimol-tools -p $PROJECT models history
echo ""

# Stage 5: Selection
echo "[5/7] Selecting best model..."
BEST=$(cli-anything-unimol-tools --json -p $PROJECT models rank | jq -r '.models[0].run_id')
echo "Selected: $BEST"
echo ""

# Stage 6: Deployment
echo "[6/7] Running predictions..."
cli-anything-unimol-tools -p $PROJECT predict run $BEST test.csv -o test_predictions.csv
echo "✓ Predictions saved: test_predictions.csv"
echo ""

# Stage 7: Cleanup
echo "[7/7] Cleaning up..."
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=2
cli-anything-unimol-tools -p $PROJECT storage
echo ""

echo "=== Workflow Complete ==="
echo "Best model: $BEST"
echo "Project file: $PROJECT"
echo "Predictions: test_predictions.csv"
```

Run with:
```bash
bash complete_workflow.sh
```

---

## Best Practices

### 1. Always Split Data Properly

- **80/10/10** train/val/test split
- Use `random_state` for reproducibility
- Stratify by label if imbalanced

### 2. Start with Baseline

- Train simple model first (10 epochs, default params)
- Establishes performance floor
- Validates data and setup

### 3. Iterate Systematically

- Change one parameter at a time
- Document what you try
- Use `models history` to track progress

### 4. Validate on Test Set

- Only evaluate best model on test set
- Test set should remain "untouched" until final validation
- Use validation set for model selection

### 5. Clean Up Regularly

- Archive old models after experiments
- Keep only top 2-3 models
- Saves disk space and keeps project organized

---

## Quality Checklist

Before considering model ready for production:

- [ ] Data validated (no invalid SMILES)
- [ ] Proper train/val/test split
- [ ] Multiple training runs completed
- [ ] Best model selected based on validation AUC
- [ ] Test set performance verified
- [ ] Model checkpoint exists and loads
- [ ] Sample predictions successful
- [ ] Storage cleaned up
- [ ] Files backed up
- [ ] Documentation complete

---

## Troubleshooting

**Training fails**:
- Check [Troubleshooting Guide](../guides/05-TROUBLESHOOTING.md)
- Verify datasets are set correctly
- Check CUDA/GPU availability

**Poor performance (AUC < 0.70)**:
- Check data quality (valid SMILES, correct labels)
- Try more epochs (20-30)
- Try different learning rates
- Consider data augmentation

**Storage issues**:
- Run `cleanup --auto` regularly
- Archive old models
- Delete conformer cache if not needed

---

## Next Steps

- **Classification Tutorial**: [CLASSIFICATION.md](../tutorials/CLASSIFICATION.md)
- **Regression Tutorial**: [REGRESSION.md](../tutorials/REGRESSION.md)
- **Cleanup SOP**: [CLEANUP-SOP.md](CLEANUP-SOP.md)
- **Workflow Diagrams**: [DIAGRAMS.md](DIAGRAMS.md)
