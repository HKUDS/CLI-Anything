# Basic Usage Guide

Comprehensive reference for all Uni-Mol Tools CLI commands.

---

## Command Structure

```bash
cli-anything-unimol-tools [GLOBAL_OPTIONS] COMMAND [ARGS] [OPTIONS]
```

### Global Options

| Option | Description | Example |
|--------|-------------|---------|
| `-p, --project PATH` | Path to project JSON file | `-p myproject.json` |
| `--json` | Output in JSON format (for automation) | `--json` |
| `--version` | Show version and exit | `--version` |
| `--help` | Show help message | `--help` |

---

## Project Management

### `project new` - Create New Project

Create a new project for molecular property prediction.

**Syntax**:
```bash
cli-anything-unimol-tools project new -n NAME -t TYPE
```

**Options**:
| Option | Required | Description | Values |
|--------|----------|-------------|--------|
| `-n, --name` | Yes | Project name | Any string |
| `-t, --task-type` | Yes | Prediction task type | `classification`, `regression`, `multiclass`, `multilabel_cls`, `multilabel_reg` |

**Examples**:
```bash
# Binary classification (e.g., active/inactive)
cli-anything-unimol-tools project new -n drug_activity -t classification

# Regression (e.g., solubility prediction)
cli-anything-unimol-tools project new -n solubility -t regression

# Multiclass (e.g., toxicity levels: low/medium/high)
cli-anything-unimol-tools project new -n toxicity -t multiclass

# Multilabel classification (multiple binary labels)
cli-anything-unimol-tools project new -n properties -t multilabel_cls

# Multilabel regression (multiple continuous values)
cli-anything-unimol-tools project new -n descriptors -t multilabel_reg
```

**Output**:
```
✓ Created project: drug_activity
  Type: classification
  File: drug_activity.json
```

---

### `project info` - Show Project Information

Display project configuration and status.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json project info
```

**Example**:
```bash
cli-anything-unimol-tools -p drug_activity.json project info
```

**Output**:
```
📁 Project: drug_activity
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type: classification
Created: 2024-01-15 10:30:00
Status: trained

Datasets:
  Train: data/train.csv (1000 samples)
  Valid: data/valid.csv (200 samples)
  Test: data/test.csv (200 samples)

Models: 3 runs
  • run_001: AUC 0.8723
  • run_002: AUC 0.8954
  • run_003: AUC 0.9123 ⭐

Storage: 546.8MB
```

---

### `project set-dataset` - Set Dataset Path

Configure train/validation/test dataset paths.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json project set-dataset SPLIT PATH
```

**Arguments**:
| Argument | Description | Values |
|----------|-------------|--------|
| `SPLIT` | Dataset split | `train`, `valid`, `test` |
| `PATH` | Path to CSV file | Any valid file path |

**Examples**:
```bash
# Set training data
cli-anything-unimol-tools -p project.json project set-dataset train data/train.csv

# Set validation data
cli-anything-unimol-tools -p project.json project set-dataset valid data/valid.csv

# Set test data
cli-anything-unimol-tools -p project.json project set-dataset test data/test.csv
```

**Data Format Requirements**:

**Binary Classification**:
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

**Multiclass**:
```csv
SMILES,label
CC(C)Cc1ccc(cc1)C(C)C(O)=O,0
CCN(CC)C(=O)Cc1ccccc1,2
```

**Multilabel Classification**:
```csv
SMILES,label1,label2,label3
CC(C)Cc1ccc(cc1)C(C)C(O)=O,1,1,0
CCN(CC)C(=O)Cc1ccccc1,1,0,1
```

**Multilabel Regression**:
```csv
SMILES,prop1,prop2,prop3
CC(C)Cc1ccc(cc1)C(C)C(O)=O,2.45,1.23,0.87
CCN(CC)C(=O)Cc1ccccc1,1.83,2.11,1.45
```

---

## Training

### `train start` - Train a Model

Train a new model with specified hyperparameters.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json train start [OPTIONS]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--epochs` | 10 | Number of training epochs |
| `--batch-size` | 16 | Batch size for training |
| `--learning-rate` | 1e-4 | Learning rate |
| `--dropout` | 0.0 | Dropout rate |
| `--conf-cache-level` | 1 | Conformer cache level (0=none, 1=cache, 2=reuse) |

**Examples**:
```bash
# Basic training (default settings)
cli-anything-unimol-tools -p project.json train start

# Custom epochs and batch size
cli-anything-unimol-tools -p project.json train start --epochs 20 --batch-size 32

# With learning rate and dropout
cli-anything-unimol-tools -p project.json train start \
  --epochs 30 \
  --learning-rate 5e-5 \
  --dropout 0.1

# Disable conformer caching (slower but uses less disk)
cli-anything-unimol-tools -p project.json train start --conf-cache-level 0
```

**Conformer Cache Levels**:
- `0`: No caching - generate fresh each time (slowest, minimal disk)
- `1`: Cache conformers - generate once, reuse later (default, recommended)
- `2`: Strict reuse - only use existing cache (fastest, requires pre-generated)

**Output**:
```
🚀 Starting training...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run ID: run_001
Save path: models/run_001

[1/3] Processing conformers... ━━━━━━━━━━━━━━━━━━ 100%
[2/3] Training...
  Epoch 1/10: loss=0.523, auc=0.712
  Epoch 2/10: loss=0.412, auc=0.784
  ...
  Epoch 10/10: loss=0.089, auc=0.872

[3/3] Evaluating...

✓ Training complete!

Metrics:
  AUC: 0.8723
  Accuracy: 0.85
  Precision: 0.83
  Recall: 0.87
  F1 Score: 0.85

Training time: 24.3s
Model saved: models/run_001/
```

---

## Prediction

### `predict run` - Run Predictions

Run predictions using a trained model.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json predict run RUN_ID INPUT_CSV [OPTIONS]
```

**Arguments**:
| Argument | Description |
|----------|-------------|
| `RUN_ID` | Model run ID (e.g., `run_001`) |
| `INPUT_CSV` | Path to CSV file with SMILES column |

**Options**:
| Option | Description | Example |
|--------|-------------|---------|
| `-o, --output PATH` | Output CSV path | `-o predictions.csv` |

**Examples**:
```bash
# Basic prediction
cli-anything-unimol-tools -p project.json predict run run_001 test.csv

# Specify output file
cli-anything-unimol-tools -p project.json predict run run_001 test.csv -o results.csv

# Use best model (from ranking)
BEST=$(cli-anything-unimol-tools --json -p project.json models rank | jq -r '.models[0].run_id')
cli-anything-unimol-tools -p project.json predict run $BEST new_data.csv -o output.csv
```

**Input Format**:
```csv
SMILES
CC(C)Cc1ccc(cc1)C(C)C
CCN(CC)C(=O)Cc1ccc
```

**Output Format** (Classification):
```csv
SMILES,prediction,probability
CC(C)Cc1ccc(cc1)C(C)C,1,0.87
CCN(CC)C(=O)Cc1ccc,0,0.23
```

**Output Format** (Regression):
```csv
SMILES,prediction
CC(C)Cc1ccc(cc1)C(C)C,-2.45
CCN(CC)C(=O)Cc1ccc,-1.83
```

---

## Storage Analysis

### `storage` - Analyze Storage Usage

Display detailed storage breakdown and optimization suggestions.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json storage
```

**Example**:
```bash
cli-anything-unimol-tools -p project.json storage
```

**Output**:
```
💾 Storage Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Usage: 549.6MB

Components:
  Models        541.9MB ( 98.6%)  █████████████████████████████░
  Conformers      7.8MB (  1.4%)  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  Predictions     0.0MB (  0.0%)  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Models (3):
  • run_001: 180.6MB (AUC: 0.8723) - 2 days old
  • run_002: 180.6MB (AUC: 0.8954) - 1 day old
  • run_003: 180.7MB (AUC: 0.9123) - 0 days old ⭐

⚠️  Recommendations:
   • 2 models are > 1 day old (save 361MB)
   • 5 SDF files duplicated (save 4MB)

   Potential savings: 365MB (66%)

💡 Tip: Run 'cleanup --auto' to free up space
```

---

## Model Management

### `models rank` - Rank All Models

Rank models by performance (AUC-based scoring).

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json models rank
```

**Example**:
```bash
cli-anything-unimol-tools -p project.json models rank
```

**Output**:
```
🏆 Model Ranking
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Based on AUC performance

Rank   Run ID       Score    AUC      Duration   Status
──────────────────────────────────────────────────────────────────
🥇 1   run_003      9.1/10   0.9123   26.8s      Best
🥈 2   run_002      9.0/10   0.8954   19.7s      Good
🥉 3   run_001      8.7/10   0.8723   16.3s      Good

💡 Recommendation: Use run_003 for production
   - Highest AUC: 0.9123
   - Consistent performance
```

**JSON Output** (for automation):
```bash
cli-anything-unimol-tools --json -p project.json models rank | jq
```

```json
{
  "models": [
    {
      "rank": 1,
      "run_id": "run_003",
      "score": 9.1,
      "auc": 0.9123,
      "duration_sec": 26.8,
      "status": "Best"
    }
  ]
}
```

---

### `models history` - Performance History

Show model performance trends over time.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json models history
```

**Example**:
```bash
cli-anything-unimol-tools -p project.json models history
```

**Output**:
```
📊 Model Performance History
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total runs: 3
Trend: improving

AUC Progress:
  run_001      │███████████████████████████████████████ 0.8723
  run_002      │████████████████████████████████████████████ 0.8954
  run_003      │████████████████████████████████████████████████ 0.9123

Training Time:
  run_001      │█████████████████████ 16.3s
  run_002      │████████████████████████████ 19.7s
  run_003      │██████████████████████████████████ 26.8s

💡 Insights:
   ✓ Best model: run_003 (AUC: 0.9123)
   ✓ Improving trend (+0.040 AUC from first to last)
   ⚠ Training time increasing
```

---

## Cleanup and Archival

### `cleanup` - Clean Up Old Models

Interactive or automatic cleanup of old/low-performing models.

**Syntax**:
```bash
# Interactive mode (recommended for first time)
cli-anything-unimol-tools -p PROJECT.json cleanup

# Automatic mode
cli-anything-unimol-tools -p PROJECT.json cleanup --auto [OPTIONS]
```

**Options**:
| Option | Default | Description |
|--------|---------|-------------|
| `--auto` | False | Automatic cleanup without prompts |
| `--keep-best` | 3 | Number of best models to keep |
| `--min-auc` | 0.75 | Minimum AUC to keep (for classification) |
| `--max-age-days` | 7 | Maximum age in days to keep recent models |

**Examples**:
```bash
# Interactive cleanup (asks for confirmation)
cli-anything-unimol-tools -p project.json cleanup

# Automatic: keep best 2, delete rest
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=2

# Automatic: keep models with AUC > 0.80
cli-anything-unimol-tools -p project.json cleanup --auto --min-auc=0.80

# Automatic: custom strategy
cli-anything-unimol-tools -p project.json cleanup --auto \
  --keep-best=3 \
  --min-auc=0.85 \
  --max-age-days=5
```

**Interactive Output**:
```
🧹 Model Cleanup Assistant
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found 6 models

🗑️  Suggested for deletion (2 models):
   • run_001: Low AUC (0.780 < 0.85) - saves 180MB
   • run_004: Low AUC (0.750 < 0.85) - saves 181MB

📦 Suggested for archival (1 model):
   • run_002: Old but decent (AUC: 0.820, 4 days old) - saves 163MB

✅ Will keep (3 models):
   • run_003: Top 3 model (rank 1)
   • run_005: Top 3 model (rank 2)
   • run_006: Recent (0 days old)

Potential savings: 524MB (96%)

Actions:
  1. Auto-clean (delete suggested, archive rest)
  2. Delete all suggested
  3. Archive all suggested
  4. Cancel

Choose action [1-4]:
```

**Automatic Output**:
```
🧹 Automatic Cleanup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Strategy: Keep best 2, delete low performers

Deleting:
  ✓ run_001 (180MB freed)
  ✓ run_004 (181MB freed)

Archiving:
  ✓ run_002 → ~/.unimol-archive/ (163MB saved)

Keeping:
  • run_003 (rank 1)
  • run_005 (rank 2)

Total freed: 524MB
```

---

### `archive list` - List Archived Models

Show all archived models.

**Syntax**:
```bash
cli-anything-unimol-tools archive list
```

**Output**:
```
📦 Archived Models
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total: 3 archives

Archives in: ~/.unimol-archive/

  • drug_activity_run_002.tar.gz (18.2MB) - 2024-01-15
  • solubility_run_001.tar.gz (18.1MB) - 2024-01-14
  • toxicity_run_003.tar.gz (18.3MB) - 2024-01-13

💡 Use 'archive restore RUN_ID' to restore an archive
```

---

### `archive restore` - Restore Archived Model

Restore a previously archived model.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json archive restore RUN_ID
```

**Arguments**:
| Argument | Description |
|----------|-------------|
| `RUN_ID` | Run ID to restore (e.g., `run_002`) |

**Example**:
```bash
cli-anything-unimol-tools -p project.json archive restore run_002
```

**Output**:
```
📦 Restoring Archive
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Archive: drug_activity_run_002.tar.gz
Size: 18.2MB → 180.6MB

Extracting... ━━━━━━━━━━━━━━━━━━ 100%

✓ Restored: models/run_002/
✓ Model ready for use

You can now use this model:
  cli-anything-unimol-tools -p project.json predict run run_002 data.csv
```

---

## Automation with JSON Output

All commands support `--json` flag for machine-readable output.

### Examples

**Get best model programmatically**:
```bash
BEST=$(cli-anything-unimol-tools --json -p project.json models rank | \
       jq -r '.models[0].run_id')

echo "Best model: $BEST"
# Best model: run_003
```

**Check storage programmatically**:
```bash
USAGE=$(cli-anything-unimol-tools --json -p project.json storage | \
        jq -r '.total_mb')

if [ $USAGE -gt 500 ]; then
  echo "Storage over 500MB, cleaning up..."
  cli-anything-unimol-tools -p project.json cleanup --auto
fi
```

**Batch processing**:
```bash
# Train multiple configurations
for epochs in 10 20 30; do
  cli-anything-unimol-tools -p project.json train start --epochs $epochs
done

# Find best model
BEST=$(cli-anything-unimol-tools --json -p project.json models rank | \
       jq -r '.models[0].run_id')

# Run predictions
cli-anything-unimol-tools -p project.json predict run $BEST test.csv
```

---

## Tips and Best Practices

### Tip 1: Conformer Caching

```bash
# First run: generates and caches conformers (slower)
cli-anything-unimol-tools -p project.json train start --epochs 10

# Subsequent runs: reuses cached conformers (faster)
cli-anything-unimol-tools -p project.json train start --epochs 20
```

### Tip 2: Regular Cleanup

```bash
# After experiments, clean up automatically
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=2
```

### Tip 3: Monitor Storage

```bash
# Check storage before and after cleanup
cli-anything-unimol-tools -p project.json storage
cli-anything-unimol-tools -p project.json cleanup --auto
cli-anything-unimol-tools -p project.json storage
```

### Tip 4: Use Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias umol='cli-anything-unimol-tools'
alias umol-train='cli-anything-unimol-tools -p project.json train start'
alias umol-rank='cli-anything-unimol-tools -p project.json models rank'

# Usage
umol-train --epochs 20
umol-rank
```

---

## Next Steps

- **Interactive Features**: See [Interactive Features Guide](04-INTERACTIVE-FEATURES.md)
- **Troubleshooting**: See [Troubleshooting Guide](05-TROUBLESHOOTING.md)
- **Workflows**: See [Training SOP](../workflows/TRAINING-SOP.md)
- **Tutorials**:
  - [Classification Tutorial](../tutorials/CLASSIFICATION.md)
  - [Regression Tutorial](../tutorials/REGRESSION.md)
  - [Advanced Usage](../tutorials/ADVANCED.md)
