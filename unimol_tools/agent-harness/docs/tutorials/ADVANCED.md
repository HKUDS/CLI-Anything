# Advanced Usage Tutorial

Advanced techniques and features for Uni-Mol Tools CLI.

---

## Overview

This tutorial covers advanced topics:
1. Multiclass Classification
2. Multilabel Classification
3. Multilabel Regression
4. Batch Processing and Automation
5. Custom Data Loaders
6. Performance Optimization
7. Integration with Python Workflows

---

## 1. Multiclass Classification

### Use Case
Predict molecules into one of multiple exclusive classes (e.g., toxicity levels: low/medium/high).

### Data Format

```csv
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(O)=O,0
CCN(CC)C(=O)Cc1ccccc1,1
CC(C)NCC(COc1ccc(CCOCC(O)=O)cc1)O,2
```

**Labels**: 0, 1, 2, ... (integer class indices)

### Setup

```bash
# Create multiclass project
cli-anything-unimol-tools project new \
  -n toxicity_levels \
  -t multiclass

PROJECT="toxicity_levels.json"

# Set datasets
cli-anything-unimol-tools -p $PROJECT project set-dataset train multiclass_train.csv
cli-anything-unimol-tools -p $PROJECT project set-dataset valid multiclass_valid.csv

# Train
cli-anything-unimol-tools -p $PROJECT train start --epochs 20
```

### Evaluation

```python
from sklearn.metrics import classification_report, confusion_matrix
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Load predictions
test = pd.read_csv('multiclass_test.csv')
pred = pd.read_csv('test_predictions.csv')
merged = test.merge(pred, on='SMILES')

# Classification report
print(classification_report(merged['label'], merged['prediction'],
                           target_names=['Low', 'Medium', 'High']))

# Confusion matrix
cm = confusion_matrix(merged['label'], merged['prediction'])

plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Low', 'Medium', 'High'],
            yticklabels=['Low', 'Medium', 'High'])
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.title('Confusion Matrix')
plt.savefig('confusion_matrix.png', dpi=150, bbox_inches='tight')
```

---

## 2. Multilabel Classification

### Use Case
Predict multiple binary properties simultaneously (e.g., drug has_aromatic_ring=1, has_amine=0, has_alcohol=1).

### Data Format

```csv
SMILES,label1,label2,label3
CC(C)Cc1ccc(cc1)C(C)C(O)=O,1,0,1
CCN(CC)C(=O)Cc1ccccc1,1,1,0
CC(C)NCC(COc1ccc(CCOCC(O)=O)cc1)O,1,1,1
```

**Labels**: Multiple columns with 0/1 values

### Setup

```bash
# Create multilabel classification project
cli-anything-unimol-tools project new \
  -n molecular_properties \
  -t multilabel_cls

PROJECT="molecular_properties.json"

# Set datasets
cli-anything-unimol-tools -p $PROJECT project set-dataset train multilabel_cls_train.csv
cli-anything-unimol-tools -p $PROJECT project set-dataset valid multilabel_cls_valid.csv

# Train
cli-anything-unimol-tools -p $PROJECT train start --epochs 20
```

### Evaluation

```python
from sklearn.metrics import hamming_loss, jaccard_score, accuracy_score
import pandas as pd

# Load predictions
test = pd.read_csv('multilabel_cls_test.csv')
pred = pd.read_csv('test_predictions.csv')

# Extract label columns
label_cols = ['label1', 'label2', 'label3']

# Merge
merged = test.merge(pred, on='SMILES')

# Extract true and predicted labels
y_true = merged[label_cols].values
y_pred = merged[[f'pred_{col}' for col in label_cols]].values

# Metrics
hamming = hamming_loss(y_true, y_pred)
jaccard = jaccard_score(y_true, y_pred, average='samples')
exact_match = accuracy_score(y_true, y_pred)

print("Multilabel Classification Metrics:")
print(f"  Hamming Loss: {hamming:.4f}")  # Lower is better
print(f"  Jaccard Score: {jaccard:.4f}")  # Higher is better
print(f"  Exact Match Ratio: {exact_match:.4f}")  # Higher is better

# Per-label metrics
for i, col in enumerate(label_cols):
    acc = accuracy_score(y_true[:, i], y_pred[:, i])
    print(f"  {col} Accuracy: {acc:.4f}")
```

---

## 3. Multilabel Regression

### Use Case
Predict multiple continuous properties simultaneously (e.g., logP, solubility, binding affinity).

### Data Format

```csv
SMILES,prop1,prop2,prop3
CC(C)Cc1ccc(cc1)C(C)C(O)=O,2.45,1.23,0.87
CCN(CC)C(=O)Cc1ccccc1,1.83,2.11,1.45
CC(C)NCC(COc1ccc(CCOCC(O)=O)cc1)O,3.12,0.98,2.31
```

**Targets**: Multiple columns with continuous values

### Setup

```bash
# Create multilabel regression project
cli-anything-unimol-tools project new \
  -n multi_properties \
  -t multilabel_reg

PROJECT="multi_properties.json"

# Set datasets
cli-anything-unimol-tools -p $PROJECT project set-dataset train multilabel_reg_train.csv
cli-anything-unimol-tools -p $PROJECT project set-dataset valid multilabel_reg_valid.csv

# Train
cli-anything-unimol-tools -p $PROJECT train start --epochs 20
```

### Evaluation

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import pandas as pd
import numpy as np

# Load predictions
test = pd.read_csv('multilabel_reg_test.csv')
pred = pd.read_csv('test_predictions.csv')
merged = test.merge(pred, on='SMILES')

# Property columns
prop_cols = ['prop1', 'prop2', 'prop3']
prop_names = ['logP', 'Solubility', 'Binding Affinity']

# Overall metrics
y_true = merged[prop_cols].values
y_pred = merged[[f'pred_{col}' for col in prop_cols]].values

overall_mae = mean_absolute_error(y_true, y_pred)
overall_rmse = np.sqrt(mean_squared_error(y_true, y_pred))
overall_r2 = r2_score(y_true, y_pred)

print("Overall Metrics:")
print(f"  MAE:  {overall_mae:.4f}")
print(f"  RMSE: {overall_rmse:.4f}")
print(f"  R²:   {overall_r2:.4f}")
print()

# Per-property metrics
print("Per-Property Metrics:")
for col, name in zip(prop_cols, prop_names):
    mae = mean_absolute_error(merged[col], merged[f'pred_{col}'])
    rmse = np.sqrt(mean_squared_error(merged[col], merged[f'pred_{col}']))
    r2 = r2_score(merged[col], merged[f'pred_{col}'])

    print(f"  {name}:")
    print(f"    MAE:  {mae:.4f}")
    print(f"    RMSE: {rmse:.4f}")
    print(f"    R²:   {r2:.4f}")
```

---

## 4. Batch Processing and Automation

### 4.1 Automated Hyperparameter Search

```bash
#!/bin/bash
# hyperparam_search.sh

PROJECT="search.json"

# Grid search parameters
epochs_list=(10 20 30)
lr_list=(1e-4 5e-5 1e-5)
bs_list=(8 16 32)
dropout_list=(0.0 0.1 0.2)

# Initialize tracking file
echo "epochs,lr,bs,dropout,run_id,auc" > search_results.csv

# Grid search
for epochs in "${epochs_list[@]}"; do
  for lr in "${lr_list[@]}"; do
    for bs in "${bs_list[@]}"; do
      for dropout in "${dropout_list[@]}"; do

        echo "Training: epochs=$epochs lr=$lr bs=$bs dropout=$dropout"

        # Train model
        cli-anything-unimol-tools -p $PROJECT train start \
          --epochs $epochs \
          --learning-rate $lr \
          --batch-size $bs \
          --dropout $dropout

        # Get latest run metrics
        RUN=$(cli-anything-unimol-tools --json -p $PROJECT project info | \
              jq -r '.runs[-1].run_id')
        AUC=$(cli-anything-unimol-tools --json -p $PROJECT project info | \
              jq -r '.runs[-1].metrics.auc')

        # Log results
        echo "$epochs,$lr,$bs,$dropout,$RUN,$AUC" >> search_results.csv

      done
    done
  done
done

# Find best configuration
echo ""
echo "Best Configuration:"
sort -t',' -k6 -nr search_results.csv | head -n 2
```

### 4.2 Find Best Configuration

```python
import pandas as pd

# Load search results
results = pd.read_csv('search_results.csv')

# Find best
best = results.loc[results['auc'].idxmax()]

print("Best Hyperparameters:")
print(f"  Epochs:  {int(best['epochs'])}")
print(f"  LR:      {best['lr']}")
print(f"  BS:      {int(best['bs'])}")
print(f"  Dropout: {best['dropout']}")
print(f"  AUC:     {best['auc']:.4f}")
print(f"  Run ID:  {best['run_id']}")

# Visualize grid search
import matplotlib.pyplot as plt
import seaborn as sns

# Pivot for heatmap (epochs vs lr, averaged over other params)
pivot = results.groupby(['epochs', 'lr'])['auc'].mean().reset_index()
pivot_table = pivot.pivot(index='epochs', columns='lr', values='auc')

plt.figure(figsize=(10, 6))
sns.heatmap(pivot_table, annot=True, fmt='.3f', cmap='viridis')
plt.title('AUC Heatmap: Epochs vs Learning Rate')
plt.xlabel('Learning Rate')
plt.ylabel('Epochs')
plt.savefig('grid_search_heatmap.png', dpi=150, bbox_inches='tight')
```

### 4.3 Batch Prediction on Multiple Files

```bash
#!/bin/bash
# batch_predict.sh

PROJECT="production.json"
BEST_MODEL="run_005"
INPUT_DIR="compounds_to_predict"
OUTPUT_DIR="predictions"

mkdir -p $OUTPUT_DIR

# Process all CSV files
for input_file in $INPUT_DIR/*.csv; do
  filename=$(basename "$input_file" .csv)
  output_file="$OUTPUT_DIR/${filename}_predictions.csv"

  echo "Processing: $input_file"

  cli-anything-unimol-tools -p $PROJECT predict run $BEST_MODEL \
    "$input_file" -o "$output_file"

  echo "  ✓ Saved: $output_file"
done

echo "Batch prediction complete!"
```

---

## 5. Custom Data Preprocessing

### 5.1 SMILES Standardization

```python
from rdkit import Chem
from rdkit.Chem import MolStandardize
import pandas as pd

def standardize_smiles(smiles):
    """Standardize SMILES using RDKit"""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None

        # Remove fragments, take largest
        standardizer = MolStandardize.LargestFragmentChooser()
        mol = standardizer.choose(mol)

        # Normalize
        normalizer = MolStandardize.Normalize()
        mol = normalizer.normalize(mol)

        # Canonical SMILES
        return Chem.MolToSmiles(mol, isomericSmiles=True)

    except:
        return None

# Apply to dataset
data = pd.read_csv('raw_data.csv')
data['SMILES_standardized'] = data['SMILES'].apply(standardize_smiles)

# Remove failed standardizations
data_clean = data[data['SMILES_standardized'].notna()].copy()
data_clean['SMILES'] = data_clean['SMILES_standardized']
data_clean = data_clean.drop('SMILES_standardized', axis=1)

data_clean.to_csv('data_standardized.csv', index=False)
print(f"Standardized: {len(data_clean)}/{len(data)} molecules")
```

### 5.2 Chemical Space Analysis

```python
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

def calculate_descriptors(smiles):
    """Calculate molecular descriptors"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    return {
        'MW': Descriptors.MolWt(mol),
        'LogP': Descriptors.MolLogP(mol),
        'HBA': Descriptors.NumHAcceptors(mol),
        'HBD': Descriptors.NumHDonors(mol),
        'TPSA': Descriptors.TPSA(mol),
        'RotBonds': Descriptors.NumRotatableBonds(mol)
    }

# Calculate for dataset
data = pd.read_csv('train.csv')
descriptors = data['SMILES'].apply(calculate_descriptors)
desc_df = pd.DataFrame(descriptors.tolist())

# Combine
data_with_desc = pd.concat([data, desc_df], axis=1)

# Visualize chemical space
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

axes[0, 0].scatter(desc_df['MW'], desc_df['LogP'], alpha=0.6)
axes[0, 0].set_xlabel('Molecular Weight')
axes[0, 0].set_ylabel('LogP')

axes[0, 1].scatter(desc_df['HBD'], desc_df['HBA'], alpha=0.6)
axes[0, 1].set_xlabel('H-Bond Donors')
axes[0, 1].set_ylabel('H-Bond Acceptors')

axes[1, 0].scatter(desc_df['TPSA'], desc_df['RotBonds'], alpha=0.6)
axes[1, 0].set_xlabel('TPSA')
axes[1, 0].set_ylabel('Rotatable Bonds')

# PCA
pca = PCA(n_components=2)
pca_coords = pca.fit_transform(desc_df)
axes[1, 1].scatter(pca_coords[:, 0], pca_coords[:, 1], alpha=0.6)
axes[1, 1].set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%})')
axes[1, 1].set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%})')

plt.tight_layout()
plt.savefig('chemical_space.png', dpi=150, bbox_inches='tight')
```

---

## 6. Performance Optimization

### 6.1 Conformer Cache Management

```bash
# Check conformer cache size
du -sh conformers/

# If cache is large and you're done training
# Delete cache to save space (will regenerate if needed)
rm -rf conformers/

# Or use CLI cleanup
cli-anything-unimol-tools -p project.json cleanup --auto
```

### 6.2 GPU Memory Optimization

```bash
# Monitor GPU memory
watch -n 1 nvidia-smi

# If running out of memory, reduce batch size
cli-anything-unimol-tools -p project.json train start \
  --batch-size 4  # Smaller batch

# Or use gradient accumulation (train with smaller batches, accumulate gradients)
# Note: Uni-Mol doesn't expose this directly, but batch size reduction helps
```

### 6.3 Parallel Predictions

```python
import subprocess
import multiprocessing as mp
from pathlib import Path

def predict_chunk(args):
    """Predict on a chunk of data"""
    chunk_file, output_file, project, model = args

    cmd = [
        'cli-anything-unimol-tools',
        '-p', project,
        'predict', 'run', model,
        chunk_file,
        '-o', output_file
    ]

    subprocess.run(cmd, check=True)
    return output_file

# Split large file into chunks
import pandas as pd

data = pd.read_csv('large_dataset.csv')
chunk_size = 1000
chunks = []

for i in range(0, len(data), chunk_size):
    chunk = data[i:i+chunk_size]
    chunk_file = f'chunk_{i//chunk_size}.csv'
    chunk.to_csv(chunk_file, index=False)
    chunks.append(chunk_file)

# Parallel prediction
PROJECT = 'project.json'
MODEL = 'run_001'

args_list = [
    (chunk, f'pred_{chunk}', PROJECT, MODEL)
    for chunk in chunks
]

with mp.Pool(processes=4) as pool:
    results = pool.map(predict_chunk, args_list)

# Combine results
all_preds = pd.concat([pd.read_csv(f) for f in results])
all_preds.to_csv('all_predictions.csv', index=False)

# Cleanup chunks
for chunk in chunks + results:
    Path(chunk).unlink()
```

---

## 7. Integration with Python Workflows

### 7.1 Subprocess Integration

```python
import subprocess
import json

class UniMolCLI:
    """Python wrapper for Uni-Mol Tools CLI"""

    def __init__(self, project_path):
        self.project_path = project_path

    def _run_command(self, *args):
        """Run CLI command and return output"""
        cmd = ['cli-anything-unimol-tools', '-p', self.project_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout

    def _run_json_command(self, *args):
        """Run CLI command with JSON output"""
        cmd = ['cli-anything-unimol-tools', '--json', '-p', self.project_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def train(self, epochs=10, batch_size=16, **kwargs):
        """Train a model"""
        args = ['train', 'start', '--epochs', str(epochs), '--batch-size', str(batch_size)]

        if 'learning_rate' in kwargs:
            args.extend(['--learning-rate', str(kwargs['learning_rate'])])
        if 'dropout' in kwargs:
            args.extend(['--dropout', str(kwargs['dropout'])])

        return self._run_command(*args)

    def predict(self, run_id, input_file, output_file):
        """Run predictions"""
        args = ['predict', 'run', run_id, input_file, '-o', output_file]
        return self._run_command(*args)

    def get_best_model(self):
        """Get best model by ranking"""
        data = self._run_json_command('models', 'rank')
        return data['models'][0]['run_id']

    def cleanup(self, keep_best=2):
        """Clean up old models"""
        args = ['cleanup', '--auto', '--keep-best', str(keep_best)]
        return self._run_command(*args)

# Usage
cli = UniMolCLI('myproject.json')

# Train
cli.train(epochs=20, batch_size=16, learning_rate=5e-5)

# Get best model
best = cli.get_best_model()
print(f"Best model: {best}")

# Predict
cli.predict(best, 'test.csv', 'predictions.csv')

# Cleanup
cli.cleanup(keep_best=1)
```

### 7.2 Pipeline Integration

```python
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd
import subprocess

class SMILESValidator(BaseEstimator, TransformerMixin):
    """Validate and standardize SMILES"""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        from rdkit import Chem

        valid_mask = X['SMILES'].apply(lambda s: Chem.MolFromSmiles(s) is not None)
        return X[valid_mask].copy()

class UniMolPredictor(BaseEstimator, TransformerMixin):
    """Uni-Mol prediction step"""

    def __init__(self, project, model):
        self.project = project
        self.model = model

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        # Save to temp file
        temp_input = 'temp_input.csv'
        temp_output = 'temp_output.csv'

        X.to_csv(temp_input, index=False)

        # Run prediction
        cmd = [
            'cli-anything-unimol-tools',
            '-p', self.project,
            'predict', 'run', self.model,
            temp_input, '-o', temp_output
        ]
        subprocess.run(cmd, check=True)

        # Load results
        predictions = pd.read_csv(temp_output)

        # Cleanup
        import os
        os.remove(temp_input)
        os.remove(temp_output)

        return predictions

# Build pipeline
pipeline = Pipeline([
    ('validator', SMILESValidator()),
    ('predictor', UniMolPredictor('project.json', 'run_001'))
])

# Use pipeline
data = pd.read_csv('compounds.csv')
predictions = pipeline.transform(data)
```

---

## 8. Best Practices Summary

### Data Preparation
- ✅ Standardize SMILES before training
- ✅ Remove duplicates
- ✅ Validate chemical structures
- ✅ Analyze chemical space coverage

### Training
- ✅ Start with baseline (default params)
- ✅ Use grid search for hyperparameter tuning
- ✅ Track all experiments
- ✅ Use early stopping (monitor validation)

### Evaluation
- ✅ Use appropriate metrics for task type
- ✅ Visualize results
- ✅ Check for overfitting
- ✅ Validate on held-out test set

### Deployment
- ✅ Document model performance
- ✅ Automate batch predictions
- ✅ Monitor production predictions
- ✅ Version control models and data

### Maintenance
- ✅ Regular cleanup of old models
- ✅ Archive important experiments
- ✅ Update models with new data
- ✅ Track model drift

---

## Next Steps

- **Classification Tutorial**: [CLASSIFICATION.md](CLASSIFICATION.md)
- **Regression Tutorial**: [REGRESSION.md](REGRESSION.md)
- **Architecture Details**: [../architecture/DESIGN.md](../architecture/DESIGN.md)
- **API Reference**: [../architecture/API.md](../architecture/API.md)
