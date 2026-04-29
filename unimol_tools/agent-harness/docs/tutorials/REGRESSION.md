# Regression Tutorial

Complete tutorial for building a regression model to predict molecular properties.

---

## Overview

**Objective**: Build a regression model to predict continuous molecular properties (e.g., solubility, logP, binding affinity).

**What You'll Learn**:
- Prepare regression data
- Train and tune a regressor
- Evaluate model performance
- Handle outliers and errors

**Time Required**: ~30 minutes

**Dataset**: Aqueous solubility prediction (logS values)

---

## Prerequisites

- Uni-Mol Tools CLI installed
- Basic understanding of regression metrics (RMSE, MAE, R²)
- ~100MB disk space

---

## Step 1: Prepare Data

### 1.1 Sample Dataset

Create training data with solubility values (logS):

```bash
cat > solubility_train.csv << 'EOF'
SMILES,target
CC(C)Cc1ccc(cc1)C(C)C(O)=O,-2.45
CCN(CC)C(=O)Cc1ccccc1,-1.83
CC(C)NCC(COc1ccc(CCOCC(O)=O)cc1)O,-3.12
CC(C)(C)NCC(O)COc1ccccc1CC=C,-2.78
CCN(CC)C(=O)c1ccccc1,-1.56
CC(C)Cc1ccc(cc1)C(C)C,-0.89
CCc1ccccc1NC(=O)Cc1ccc(O)cc1,-2.34
CC(C)NCC(O)c1ccc(O)c(CO)c1,-3.45
CCN(CC)CCNC(=O)c1cc(I)c(O)c(I)c1,-4.12
CC(C)NCC(O)COc1cccc2c1cccc2,-2.91
EOF
```

Validation data:

```bash
cat > solubility_valid.csv << 'EOF'
SMILES,target
CC(C)Cc1ccc(cc1)C(C)C(=O)O,-2.67
CCN(CC)C(=O)Cc1ccc(Cl)cc1,-2.01
CC(C)NCC(COc1ccc(CC(C)C)cc1)O,-3.34
CC(C)(C)NCC(O)COc1ccc(Cl)cc1,-2.98
EOF
```

Test data:

```bash
cat > solubility_test.csv << 'EOF'
SMILES,target
CC(C)Cc1ccc(cc1)C(C)C(=O)N,-2.89
CCN(CC)C(=O)Cc1ccc(F)cc1,-1.95
CC(C)NCC(COc1ccc(Br)cc1)O,-3.56
CC(C)(C)NCC(O)COc1ccc(I)cc1,-3.21
EOF
```

### 1.2 Data Statistics

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
train = pd.read_csv('solubility_train.csv')
valid = pd.read_csv('solubility_valid.csv')
test = pd.read_csv('solubility_test.csv')

print("Dataset Statistics:")
print(f"Train: {len(train)} molecules")
print(f"Valid: {len(valid)} molecules")
print(f"Test: {len(test)} molecules")
print()

# Target distribution
print("Solubility (logS) Statistics:")
print(train['target'].describe())
print()

# Plot distribution
plt.figure(figsize=(10, 6))
plt.hist(train['target'], bins=20, alpha=0.7, edgecolor='black')
plt.xlabel('Solubility (logS)')
plt.ylabel('Frequency')
plt.title('Training Data - Solubility Distribution')
plt.axvline(train['target'].mean(), color='red', linestyle='--',
            label=f'Mean: {train["target"].mean():.2f}')
plt.legend()
plt.grid(alpha=0.3)
plt.savefig('target_distribution.png', dpi=150, bbox_inches='tight')
print("Distribution plot saved: target_distribution.png")
```

---

## Step 2: Create Project

```bash
# Create regression project
cli-anything-unimol-tools project new \
  -n solubility \
  -t regression

# Set datasets
PROJECT="solubility.json"

cli-anything-unimol-tools -p $PROJECT \
  project set-dataset train solubility_train.csv

cli-anything-unimol-tools -p $PROJECT \
  project set-dataset valid solubility_valid.csv

cli-anything-unimol-tools -p $PROJECT \
  project set-dataset test solubility_test.csv

# Verify
cli-anything-unimol-tools -p $PROJECT project info
```

---

## Step 3: Train Baseline Model

```bash
# Baseline with default parameters
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 10 \
  --batch-size 8
```

**Expected Output**:
```
🚀 Starting training...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run ID: run_001
Save path: models/run_001

[1/3] Processing conformers... ━━━━━━━━━━━━━━━━━━ 100%
[2/3] Training...
  Epoch 1/10: loss=2.345, mae=1.234
  Epoch 2/10: loss=1.678, mae=0.987
  Epoch 3/10: loss=1.234, mae=0.756
  ...
  Epoch 10/10: loss=0.456, mae=0.423

[3/3] Evaluating...

✓ Training complete!

Metrics:
  MAE: 0.4230
  RMSE: 0.5612
  R²: 0.7845

Training time: 19.2s
Model saved: models/run_001/
```

### Key Regression Metrics

**MAE (Mean Absolute Error)**: Average absolute difference
- Lower is better
- Same units as target (logS)
- MAE < 0.5 is good for solubility

**RMSE (Root Mean Square Error)**: Penalizes large errors more
- Lower is better
- RMSE ≥ MAE (always)
- Sensitive to outliers

**R² (Coefficient of Determination)**: Proportion of variance explained
- Range: -∞ to 1
- R² = 1: Perfect predictions
- R² = 0: No better than mean baseline
- R² > 0.7: Good model

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

### 4.3 Larger Batch Size

```bash
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --batch-size 16 \
  --learning-rate 5e-5
```

### 4.4 Compare Models

For regression, ranking is based on lowest MAE (or RMSE):

```bash
cli-anything-unimol-tools -p $PROJECT models rank
cli-anything-unimol-tools -p $PROJECT models history
```

**Note**: The CLI's ranking system currently focuses on AUC (for classification). For regression, manually compare MAE/RMSE values from the output or use JSON mode:

```bash
cli-anything-unimol-tools --json -p $PROJECT models rank | jq
```

---

## Step 5: Model Evaluation

### 5.1 Select Best Model

```bash
# For regression, select based on lowest MAE or RMSE
# Manually check project info
cli-anything-unimol-tools -p $PROJECT project info

# Select the run with best metrics
BEST="run_002"  # Replace with actual best run
```

### 5.2 Test Set Predictions

```bash
cli-anything-unimol-tools -p $PROJECT predict run $BEST \
  solubility_test.csv -o test_predictions.csv

cat test_predictions.csv
```

**Expected Output**:
```csv
SMILES,prediction
CC(C)Cc1ccc(cc1)C(C)C(=O)N,-2.87
CCN(CC)C(=O)Cc1ccc(F)cc1,-1.98
CC(C)NCC(COc1ccc(Br)cc1)O,-3.52
CC(C)(C)NCC(O)COc1ccc(I)cc1,-3.18
```

### 5.3 Calculate Test Metrics

```python
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Load data
test = pd.read_csv('solubility_test.csv')
pred = pd.read_csv('test_predictions.csv')

# Merge
merged = test.merge(pred, on='SMILES')

# Calculate metrics
mae = mean_absolute_error(merged['target'], merged['prediction'])
rmse = np.sqrt(mean_squared_error(merged['target'], merged['prediction']))
r2 = r2_score(merged['target'], merged['prediction'])

print("Test Set Metrics:")
print(f"  MAE:  {mae:.4f}")
print(f"  RMSE: {rmse:.4f}")
print(f"  R²:   {r2:.4f}")
print()

# Error analysis
merged['error'] = merged['prediction'] - merged['target']
merged['abs_error'] = np.abs(merged['error'])

print("Error Analysis:")
print(f"  Max error: {merged['error'].max():.4f}")
print(f"  Min error: {merged['error'].min():.4f}")
print(f"  Mean error: {merged['error'].mean():.4f}")
print()

# Show predictions vs actual
print("Predictions vs Actual:")
print(merged[['SMILES', 'target', 'prediction', 'error']])
```

---

## Step 6: Visualize Results

### 6.1 Prediction vs Actual Plot

```python
import matplotlib.pyplot as plt
import numpy as np

# Load predictions
merged = test.merge(pred, on='SMILES')

# Create scatter plot
fig, ax = plt.subplots(figsize=(8, 8))

# Plot predictions
ax.scatter(merged['target'], merged['prediction'],
           s=100, alpha=0.6, edgecolors='black', linewidth=1.5)

# Perfect prediction line
min_val = min(merged['target'].min(), merged['prediction'].min())
max_val = max(merged['target'].max(), merged['prediction'].max())
ax.plot([min_val, max_val], [min_val, max_val],
        'k--', linewidth=2, label='Perfect Prediction')

# Labels and title
ax.set_xlabel('Actual Solubility (logS)', fontsize=12)
ax.set_ylabel('Predicted Solubility (logS)', fontsize=12)
ax.set_title(f'Prediction vs Actual (R² = {r2:.3f}, MAE = {mae:.3f})',
             fontsize=14)
ax.legend(fontsize=10)
ax.grid(alpha=0.3)

# Equal aspect ratio
ax.set_aspect('equal')

plt.tight_layout()
plt.savefig('prediction_vs_actual.png', dpi=150, bbox_inches='tight')
print("Saved: prediction_vs_actual.png")
```

### 6.2 Residual Plot

```python
# Residual plot
fig, ax = plt.subplots(figsize=(10, 6))

residuals = merged['prediction'] - merged['target']

ax.scatter(merged['target'], residuals, s=100, alpha=0.6,
           edgecolors='black', linewidth=1.5)
ax.axhline(y=0, color='red', linestyle='--', linewidth=2)
ax.set_xlabel('Actual Solubility (logS)', fontsize=12)
ax.set_ylabel('Residual (Predicted - Actual)', fontsize=12)
ax.set_title('Residual Plot', fontsize=14)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('residuals.png', dpi=150, bbox_inches='tight')
print("Saved: residuals.png")
```

### 6.3 Error Distribution

```python
# Error distribution histogram
fig, ax = plt.subplots(figsize=(10, 6))

ax.hist(residuals, bins=20, alpha=0.7, edgecolor='black')
ax.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Zero Error')
ax.set_xlabel('Prediction Error (logS)', fontsize=12)
ax.set_ylabel('Frequency', fontsize=12)
ax.set_title(f'Error Distribution (Mean: {residuals.mean():.3f}, Std: {residuals.std():.3f})',
             fontsize=14)
ax.legend(fontsize=10)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('error_distribution.png', dpi=150, bbox_inches='tight')
print("Saved: error_distribution.png")
```

---

## Step 7: Handle Outliers

### 7.1 Identify Outliers

```python
# Find predictions with large errors
threshold = 1.0  # logS units

outliers = merged[merged['abs_error'] > threshold]

if len(outliers) > 0:
    print(f"Found {len(outliers)} outliers (|error| > {threshold}):")
    print(outliers[['SMILES', 'target', 'prediction', 'error']])
else:
    print("No outliers found")
```

### 7.2 Analyze Outliers

```python
from rdkit import Chem
from rdkit.Chem import Descriptors

for idx, row in outliers.iterrows():
    mol = Chem.MolFromSmiles(row['SMILES'])

    print(f"\nOutlier: {row['SMILES']}")
    print(f"  Actual:    {row['target']:.2f}")
    print(f"  Predicted: {row['prediction']:.2f}")
    print(f"  Error:     {row['error']:.2f}")

    if mol:
        print(f"  MW:        {Descriptors.MolWt(mol):.2f}")
        print(f"  LogP:      {Descriptors.MolLogP(mol):.2f}")
        print(f"  H-Donors:  {Descriptors.NumHDonors(mol)}")
        print(f"  H-Accept:  {Descriptors.NumHAcceptors(mol)}")
```

---

## Step 8: Production Deployment

### 8.1 Predict New Molecules

```bash
cat > new_molecules.csv << 'EOF'
SMILES
CC(C)Cc1ccc(cc1)C(C)C(=O)Cl
CCN(CC)C(=O)Cc1ccc(NO2)cc1
CC(C)NCC(COc1ccc(CN)cc1)O
CC(C)(C)NCC(O)COc1ccc(OH)cc1
EOF
```

```bash
cli-anything-unimol-tools -p $PROJECT predict run $BEST \
  new_molecules.csv -o production_predictions.csv

cat production_predictions.csv
```

### 8.2 Interpret Predictions

```python
import pandas as pd

pred = pd.read_csv('production_predictions.csv')

# Add interpretation
def interpret_solubility(logs):
    if logs > -1:
        return "Highly soluble"
    elif logs > -2:
        return "Moderately soluble"
    elif logs > -3:
        return "Poorly soluble"
    else:
        return "Insoluble"

pred['interpretation'] = pred['prediction'].apply(interpret_solubility)

print("Production Predictions:")
print(pred[['SMILES', 'prediction', 'interpretation']])

# Export with units
pred['solubility_logS'] = pred['prediction'].round(2)
pred[['SMILES', 'solubility_logS', 'interpretation']].to_csv(
    'production_predictions_formatted.csv', index=False)
```

---

## Step 9: Model Validation

### 9.1 Cross-Validation (Optional)

For more robust evaluation, use k-fold cross-validation:

```python
import pandas as pd
from sklearn.model_selection import KFold
import numpy as np

# Load all data
data = pd.read_csv('solubility_train.csv')

# 5-fold CV
kf = KFold(n_splits=5, shuffle=True, random_state=42)

fold_results = []

for fold, (train_idx, val_idx) in enumerate(kf.split(data), 1):
    print(f"Fold {fold}/5")

    # Split data
    train_fold = data.iloc[train_idx]
    val_fold = data.iloc[val_idx]

    # Save to CSV
    train_fold.to_csv(f'train_fold{fold}.csv', index=False)
    val_fold.to_csv(f'val_fold{fold}.csv', index=False)

    # Note: You would train a model here using CLI
    # For demonstration, this is the workflow:
    # 1. cli-anything-unimol-tools -p project.json project set-dataset train train_fold{fold}.csv
    # 2. cli-anything-unimol-tools -p project.json project set-dataset valid val_fold{fold}.csv
    # 3. cli-anything-unimol-tools -p project.json train start --epochs 20
    # 4. Collect metrics from each fold

# After all folds, calculate average metrics
print("\nCross-Validation Results:")
print(f"Average MAE: {np.mean([r['mae'] for r in fold_results]):.4f}")
print(f"Std MAE: {np.std([r['mae'] for r in fold_results]):.4f}")
```

---

## Step 10: Clean Up

```bash
# Check storage
cli-anything-unimol-tools -p $PROJECT storage

# Keep best model only
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=1

# Verify
cli-anything-unimol-tools -p $PROJECT project info
```

---

## Common Issues

### Issue: High MAE (>1.0)

**Possible causes**:
- Insufficient training data
- Outliers in data
- Need more epochs
- Complex property to predict

**Solutions**:
```bash
# More epochs
cli-anything-unimol-tools -p $PROJECT train start --epochs 30

# Check for outliers
python << EOF
import pandas as pd
data = pd.read_csv('solubility_train.csv')
print(data['target'].describe())
print("\nPotential outliers:")
print(data[data['target'] < data['target'].quantile(0.05)])
print(data[data['target'] > data['target'].quantile(0.95)])
EOF
```

### Issue: Large difference between train and validation error

**Cause**: Overfitting

**Solution**: Add regularization
```bash
cli-anything-unimol-tools -p $PROJECT train start \
  --epochs 20 \
  --dropout 0.2
```

### Issue: Predictions outside reasonable range

**Cause**: Model extrapolating beyond training data

**Solution**: Check if test molecules are similar to training set
```python
from rdkit import Chem
from rdkit.Chem import AllChem
import numpy as np

def get_fingerprint(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        return AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048)
    return None

# Calculate Tanimoto similarity
train = pd.read_csv('solubility_train.csv')
test = pd.read_csv('solubility_test.csv')

for test_smi in test['SMILES']:
    test_fp = get_fingerprint(test_smi)
    similarities = []

    for train_smi in train['SMILES']:
        train_fp = get_fingerprint(train_smi)
        if test_fp and train_fp:
            sim = DataStructs.TanimotoSimilarity(test_fp, train_fp)
            similarities.append(sim)

    max_sim = max(similarities) if similarities else 0
    print(f"{test_smi}: Max similarity = {max_sim:.3f}")

    if max_sim < 0.3:
        print("  ⚠️  Warning: Low similarity to training data")
```

---

## Best Practices

### 1. Data Quality

- Remove or investigate outliers
- Ensure target values are in reasonable range
- Check for data errors (e.g., wrong units)
- Use sufficient data (>100 molecules recommended)

### 2. Feature Scaling

Uni-Mol handles feature scaling internally, but be aware of target value ranges:

```python
# Check target distribution
import pandas as pd
data = pd.read_csv('solubility_train.csv')
print(f"Mean: {data['target'].mean():.2f}")
print(f"Std:  {data['target'].std():.2f}")
print(f"Min:  {data['target'].min():.2f}")
print(f"Max:  {data['target'].max():.2f}")

# Very wide ranges (>5 orders of magnitude) may need log transformation
```

### 3. Evaluation

- Use multiple metrics (MAE, RMSE, R²)
- Visualize predictions vs actual
- Check residual plots for patterns
- Validate on held-out test set

### 4. Error Interpretation

For solubility (logS):
- MAE < 0.5: Excellent
- MAE < 0.7: Good
- MAE < 1.0: Acceptable
- MAE > 1.0: Poor

For other properties, define acceptable error based on domain knowledge.

---

## Summary Checklist

- [x] Prepared regression data with continuous targets
- [x] Created and configured project
- [x] Trained baseline model
- [x] Tuned hyperparameters
- [x] Evaluated using MAE, RMSE, R²
- [x] Visualized predictions vs actual
- [x] Analyzed residuals and outliers
- [x] Deployed for production predictions
- [x] Cleaned up old models

---

## Next Steps

- **Classification Tutorial**: [CLASSIFICATION.md](CLASSIFICATION.md)
- **Advanced Usage**: [ADVANCED.md](ADVANCED.md)
- **Multioutput Regression**: See Advanced tutorial for multilabel regression
- **Training SOP**: [../workflows/TRAINING-SOP.md](../workflows/TRAINING-SOP.md)

---

## Additional Resources

### Public Regression Datasets

- **ESOL**: Aqueous solubility (1128 molecules)
- **FreeSolv**: Solvation free energy (642 molecules)
- **Lipophilicity**: logD at pH 7.4 (4200 molecules)

Download from MoleculeNet: http://moleculenet.ai/

### Solubility Interpretation

**logS Scale** (mol/L in logarithmic units):
- `> -1`: Highly soluble (>100 mg/mL)
- `-1 to -2`: Soluble (10-100 mg/mL)
- `-2 to -3`: Moderately soluble (1-10 mg/mL)
- `-3 to -4`: Poorly soluble (0.1-1 mg/mL)
- `< -4`: Insoluble (<0.1 mg/mL)

### Regression Metrics Guide

**When to use each**:
- **MAE**: When all errors are equally important
- **RMSE**: When large errors are particularly bad
- **R²**: To understand explained variance (always report with MAE/RMSE)
