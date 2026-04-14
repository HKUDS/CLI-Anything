# Binary Classification Tutorial

Complete tutorial for building a binary classification model to predict drug activity.

---

## Overview

**Objective**: Build a classifier to predict if a molecule is active (1) or inactive (0) against a biological target.

**What You'll Learn**:
- Prepare classification data
- Train and tune a classifier
- Evaluate model performance
- Deploy for predictions

**Time Required**: ~30 minutes

**Dataset**: Drug activity prediction (active/inactive compounds)

---

## Prerequisites

- Uni-Mol Tools CLI installed
- Basic understanding of molecular SMILES notation
- ~100MB disk space

---

## Step 1: Prepare Data

### 1.1 Sample Dataset

Create sample training data:

```bash
cat > drug_activity_train.csv << 'EOF'
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(O)=O,1
CCN(CC)C(=O)Cc1ccccc1,0
CC(C)NCC(COc1ccc(CCOCC(O)=O)cc1)O,1
CC(C)(C)NCC(O)COc1ccccc1CC=C,0
CCN(CC)C(=O)c1ccccc1,1
CC(C)Cc1ccc(cc1)C(C)C,0
CCc1ccccc1NC(=O)Cc1ccc(O)cc1,1
CC(C)NCC(O)c1ccc(O)c(CO)c1,0
CCN(CC)CCNC(=O)c1cc(I)c(O)c(I)c1,1
CC(C)NCC(O)COc1cccc2c1cccc2,0
EOF
```

Validation data:

```bash
cat > drug_activity_valid.csv << 'EOF'
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(=O)O,1
CCN(CC)C(=O)Cc1ccc(Cl)cc1,0
CC(C)NCC(COc1ccc(CC(C)C)cc1)O,1
CC(C)(C)NCC(O)COc1ccc(Cl)cc1,0
EOF
```

Test data:

```bash
cat > drug_activity_test.csv << 'EOF'
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(=O)N,1
CCN(CC)C(=O)Cc1ccc(F)cc1,0
CC(C)NCC(COc1ccc(Br)cc1)O,1
CC(C)(C)NCC(O)COc1ccc(I)cc1,0
EOF
```

### 1.2 Data Statistics

```bash
echo "Dataset Statistics:"
echo "Train: $(tail -n +2 drug_activity_train.csv | wc -l) molecules"
echo "Valid: $(tail -n +2 drug_activity_valid.csv | wc -l) molecules"
echo "Test: $(tail -n +2 drug_activity_test.csv | wc -l) molecules"

# Class distribution
echo ""
echo "Train Class Distribution:"
tail -n +2 drug_activity_train.csv | cut -d',' -f2 | sort | uniq -c
```

---

## Step 2: Create Project

```bash
# Create classification project
cli-anything-unimol-tools project new \
  -n drug_activity \
  -t classification

# Set datasets
PROJECT="drug_activity.json"

cli-anything-unimol-tools -p $PROJECT \
  project set-dataset train drug_activity_train.csv

cli-anything-unimol-tools -p $PROJECT \
  project set-dataset valid drug_activity_valid.csv

cli-anything-unimol-tools -p $PROJECT \
  project set-dataset test drug_activity_test.csv

# Verify setup
cli-anything-unimol-tools -p $PROJECT project info
```

**Expected Output**:
```
📁 Project: drug_activity
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type: classification
Created: 2024-01-15 10:30:00
Status: initialized

Datasets:
  Train: drug_activity_train.csv (10 samples)
  Valid: drug_activity_valid.csv (4 samples)
  Test: drug_activity_test.csv (4 samples)

Models: 0 runs
Storage: 0B
```

---

## Step 3: Train Baseline Model

### 3.1 Initial Training

```bash
# Train with default parameters
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 10 \
  --batch-size 8
```

**What Happens**:
1. Generates 3D conformers for each SMILES
2. Encodes molecules with Uni-Mol
3. Trains binary classifier
4. Evaluates on validation set

**Expected Output**:
```
🚀 Starting training...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run ID: run_001
Save path: models/run_001

[1/3] Processing conformers... ━━━━━━━━━━━━━━━━━━ 100%
[2/3] Training...
  Epoch 1/10: loss=0.693, auc=0.550
  Epoch 2/10: loss=0.612, auc=0.650
  Epoch 3/10: loss=0.523, auc=0.750
  ...
  Epoch 10/10: loss=0.234, auc=0.875

[3/3] Evaluating...

✓ Training complete!

Metrics:
  AUC: 0.8750
  Accuracy: 0.80
  Precision: 0.83
  Recall: 0.75
  F1 Score: 0.79

Training time: 18.3s
Model saved: models/run_001/
```

### 3.2 Check Results

```bash
cli-anything-unimol-tools -p $PROJECT models rank
```

---

## Step 4: Hyperparameter Tuning

### 4.1 Try More Epochs

```bash
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 8
```

### 4.2 Adjust Learning Rate

```bash
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 8 \
  --learning-rate 5e-5
```

### 4.3 Add Regularization

```bash
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 8 \
  --learning-rate 5e-5 \
  --dropout 0.1
```

### 4.4 Compare Models

```bash
# View performance history
cli-anything-unimol-tools -p $PROJECT models history

# Rank all models
cli-anything-unimol-tools -p $PROJECT models rank
```

---

## Step 5: Model Evaluation

### 5.1 Select Best Model

```bash
# Get best model
BEST=$(cli-anything-unimol-tools --json -p $PROJECT models rank | \
       jq -r '.models[0].run_id')

echo "Best model: $BEST"
```

### 5.2 Test Set Evaluation

```bash
# Run predictions on test set
cli-anything-unimol-tools -p $PROJECT predict run $BEST \
  drug_activity_test.csv -o test_predictions.csv

# View predictions
cat test_predictions.csv
```

**Expected Output**:
```csv
SMILES,prediction,probability
CC(C)Cc1ccc(cc1)C(C)C(=O)N,1,0.87
CCN(CC)C(=O)Cc1ccc(F)cc1,0,0.23
CC(C)NCC(COc1ccc(Br)cc1)O,1,0.91
CC(C)(C)NCC(O)COc1ccc(I)cc1,0,0.15
```

### 5.3 Calculate Test Metrics

```python
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

# Load test data and predictions
test = pd.read_csv('drug_activity_test.csv')
pred = pd.read_csv('test_predictions.csv')

# Merge
merged = test.merge(pred, on='SMILES')

# Calculate metrics
auc = roc_auc_score(merged['label'], merged['probability'])
acc = accuracy_score(merged['label'], merged['prediction'])
prec = precision_score(merged['label'], merged['prediction'])
rec = recall_score(merged['label'], merged['prediction'])
f1 = f1_score(merged['label'], merged['prediction'])

print("Test Set Metrics:")
print(f"  AUC: {auc:.4f}")
print(f"  Accuracy: {acc:.4f}")
print(f"  Precision: {prec:.4f}")
print(f"  Recall: {rec:.4f}")
print(f"  F1 Score: {f1:.4f}")
print()

# Confusion matrix
cm = confusion_matrix(merged['label'], merged['prediction'])
print("Confusion Matrix:")
print(cm)
print()

# Detailed report
print("Classification Report:")
print(classification_report(merged['label'], merged['prediction'],
                           target_names=['Inactive', 'Active']))
```

**Expected Output**:
```
Test Set Metrics:
  AUC: 0.9375
  Accuracy: 1.0000
  Precision: 1.0000
  Recall: 1.0000
  F1 Score: 1.0000

Confusion Matrix:
[[2 0]
 [0 2]]

Classification Report:
              precision    recall  f1-score   support

    Inactive       1.00      1.00      1.00         2
      Active       1.00      1.00      1.00         2

    accuracy                           1.00         4
   macro avg       1.00      1.00      1.00         4
weighted avg       1.00      1.00      1.00         4
```

---

## Step 6: Visualize Results

### 6.1 ROC Curve

```python
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve

# Calculate ROC curve
fpr, tpr, thresholds = roc_curve(merged['label'], merged['probability'])

# Plot
plt.figure(figsize=(8, 6))
plt.plot(fpr, tpr, linewidth=2, label=f'ROC (AUC = {auc:.3f})')
plt.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('ROC Curve - Drug Activity Classifier')
plt.legend()
plt.grid(alpha=0.3)
plt.savefig('roc_curve.png', dpi=150, bbox_inches='tight')
print("ROC curve saved: roc_curve.png")
```

### 6.2 Probability Distribution

```python
# Separate by class
inactive = merged[merged['label'] == 0]['probability']
active = merged[merged['label'] == 1]['probability']

# Plot
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(inactive, bins=20, alpha=0.5, label='Inactive (0)', color='red')
ax.hist(active, bins=20, alpha=0.5, label='Active (1)', color='green')
ax.axvline(0.5, color='black', linestyle='--', linewidth=2, label='Threshold')
ax.xlabel('Predicted Probability')
ax.ylabel('Count')
ax.title('Prediction Probability Distribution')
ax.legend()
plt.savefig('probability_distribution.png', dpi=150, bbox_inches='tight')
print("Distribution saved: probability_distribution.png")
```

---

## Step 7: Deploy for Production

### 7.1 Production Predictions

Create new compounds to predict:

```bash
cat > new_compounds.csv << 'EOF'
SMILES
CC(C)Cc1ccc(cc1)C(C)C(=O)Cl
CCN(CC)C(=O)Cc1ccc(NO2)cc1
CC(C)NCC(COc1ccc(CN)cc1)O
CC(C)(C)NCC(O)COc1ccc(OH)cc1
EOF
```

Run predictions:

```bash
cli-anything-unimol-tools -p $PROJECT predict run $BEST \
  new_compounds.csv -o production_predictions.csv

cat production_predictions.csv
```

### 7.2 Interpret Results

```python
import pandas as pd

pred = pd.read_csv('production_predictions.csv')

# Classify confidence
def classify_confidence(prob):
    if prob < 0.3 or prob > 0.7:
        return "High"
    elif prob < 0.4 or prob > 0.6:
        return "Medium"
    else:
        return "Low"

pred['confidence'] = pred['probability'].apply(classify_confidence)

# Add interpretation
def interpret(row):
    if row['prediction'] == 1:
        return f"Active ({row['probability']:.2%} confidence)"
    else:
        return f"Inactive ({1-row['probability']:.2%} confidence)"

pred['interpretation'] = pred.apply(interpret, axis=1)

print(pred[['SMILES', 'prediction', 'probability', 'confidence', 'interpretation']])
```

---

## Step 8: Clean Up

### 8.1 Review Storage

```bash
cli-anything-unimol-tools -p $PROJECT storage
```

### 8.2 Keep Best Model Only

```bash
# Automatic cleanup - keep best 1 model
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=1
```

### 8.3 Verify

```bash
cli-anything-unimol-tools -p $PROJECT project info
cli-anything-unimol-tools -p $PROJECT storage
```

---

## Common Issues

### Issue: Poor AUC (<0.70)

**Possible causes**:
- Insufficient training data
- Class imbalance
- Poor quality SMILES
- Need more epochs

**Solutions**:
```bash
# Try more epochs
cli-anything-unimol-tools -p $PROJECT train start --epochs 30

# Check data quality
python << EOF
import pandas as pd
from rdkit import Chem

data = pd.read_csv('drug_activity_train.csv')
print(f"Total: {len(data)}")
print(f"Class 0: {(data['label']==0).sum()}")
print(f"Class 1: {(data['label']==1).sum()}")

# Validate SMILES
invalid = []
for smi in data['SMILES']:
    if Chem.MolFromSmiles(smi) is None:
        invalid.append(smi)
print(f"Invalid SMILES: {len(invalid)}")
EOF
```

### Issue: Overfitting (high train AUC, low val AUC)

**Solution**: Add regularization
```bash
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --dropout 0.2
```

### Issue: Model predicts all one class

**Cause**: Severe class imbalance

**Solution**: Balance dataset
```python
import pandas as pd

data = pd.read_csv('drug_activity_train.csv')

# Separate classes
class_0 = data[data['label'] == 0]
class_1 = data[data['label'] == 1]

# Undersample majority class
min_size = min(len(class_0), len(class_1))
class_0_balanced = class_0.sample(min_size, random_state=42)
class_1_balanced = class_1.sample(min_size, random_state=42)

# Combine and shuffle
balanced = pd.concat([class_0_balanced, class_1_balanced])
balanced = balanced.sample(frac=1, random_state=42).reset_index(drop=True)

balanced.to_csv('drug_activity_train_balanced.csv', index=False)
```

---

## Best Practices

### 1. Data Quality

- Validate all SMILES before training
- Remove duplicates
- Balance classes if possible
- Use sufficient data (>100 molecules per class)

### 2. Training

- Start with baseline (10 epochs)
- Increase epochs if underfitting
- Add dropout if overfitting
- Use validation set for model selection

### 3. Evaluation

- Always evaluate on held-out test set
- Check confusion matrix for errors
- Visualize ROC curve
- Consider probability calibration

### 4. Deployment

- Document model performance
- Set probability threshold based on use case
- Monitor predictions in production
- Retrain periodically with new data

---

## Summary Checklist

- [x] Prepared balanced classification data
- [x] Created and configured project
- [x] Trained baseline model
- [x] Tuned hyperparameters
- [x] Selected best model based on validation AUC
- [x] Evaluated on test set
- [x] Visualized results (ROC, distributions)
- [x] Deployed for production predictions
- [x] Cleaned up old models

---

## Next Steps

- **Regression Tutorial**: [REGRESSION.md](REGRESSION.md)
- **Advanced Usage**: [ADVANCED.md](ADVANCED.md)
- **Training SOP**: [../workflows/TRAINING-SOP.md](../workflows/TRAINING-SOP.md)
- **Troubleshooting**: [../guides/05-TROUBLESHOOTING.md](../guides/05-TROUBLESHOOTING.md)

---

## Additional Resources

### Sample Datasets

Larger public datasets for practice:
- **BACE**: Blood-brain barrier penetration (1522 molecules)
- **BBBP**: Beta-secretase inhibitors (1513 molecules)
- **Tox21**: Toxicity prediction (7831 molecules)

Download from MoleculeNet: http://moleculenet.ai/

### Metrics Reference

**AUC (Area Under ROC Curve)**:
- 0.9-1.0: Excellent
- 0.8-0.9: Good
- 0.7-0.8: Fair
- 0.6-0.7: Poor
- 0.5-0.6: Fail

**Accuracy**: Overall correctness (use with balanced datasets)

**Precision**: Of predicted actives, how many are truly active

**Recall**: Of true actives, how many were predicted

**F1 Score**: Harmonic mean of precision and recall
