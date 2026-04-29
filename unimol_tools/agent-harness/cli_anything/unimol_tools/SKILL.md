---
name: "cli-anything-unimol-tools"
description: >-
  Interactive CLI for Uni-Mol molecular property prediction training and inference workflows.
---

# Uni-Mol Tools - Molecular Property Prediction CLI

**Package**: `cli-anything-unimol-tools`
**Command**: `python3 -m cli_anything.unimol_tools`

## Description

Interactive CLI for training and inference of molecular property prediction models using Uni-Mol Tools. Supports 5 task types: binary classification, regression, multiclass, multilabel classification, and multilabel regression.

## Key Features

- **Project Management**: Organize experiments with named projects
- **5 Task Types**: Classification, regression, multiclass, multilabel variants
- **Model Tracking**: Automatic performance history and rankings
- **Smart Storage**: Analyze usage and clean up underperformers
- **JSON API**: Full automation support with `--json` flag

## Common Commands

### Project Management
```bash
# Create a new project
project create --name drug_discovery

# List all projects
project list

# Switch to a project
project switch --name drug_discovery
```

### Training
```bash
# Train a classification model
train --data-path train.csv --target-col active --task-type classification --epochs 10

# Train a regression model
train --data-path train.csv --target-col affinity --task-type regression --epochs 10
```

### Model Management
```bash
# List all trained models
models list

# Show model details and performance
models show --model-id <id>

# Rank models by performance
models rank
```

### Storage & Cleanup
```bash
# Analyze storage usage
storage analyze

# Automatic cleanup of poor performers
cleanup auto

# Manual cleanup with criteria
cleanup manual --max-models 10 --min-score 0.7
```

### Prediction
```bash
# Make predictions with a trained model
predict --model-id <id> --data-path test.csv
```

## Data Format

CSV files must contain:
- `SMILES` column: Molecular structures in SMILES format
- Target column(s): Values to predict (name specified via `--target-col`)

Example:
```csv
SMILES,target
CCO,1
CCCO,0
CC(C)O,1
```

## Task Types

1. **classification**: Binary classification (0/1)
2. **regression**: Continuous value prediction
3. **multiclass**: Multiple class classification
4. **multilabel_classification**: Multiple binary labels
5. **multilabel_regression**: Multiple continuous values

## JSON Mode

Add `--json` flag to any command for machine-readable output:
```bash
python3 -m cli_anything.unimol_tools --json models list
```

Output format:
```json
{
  "status": "success",
  "data": [...],
  "message": "..."
}
```

## Interactive Mode

Launch without commands for interactive REPL:
```bash
python3 -m cli_anything.unimol_tools
```

Features:
- Tab completion
- Command history
- Contextual help
- Project state persistence

## Test Data

Example datasets available at:
https://github.com/545487677/CLI-Anything-unimol-tools/tree/main/unimol_tools/examples

Includes data for all 5 task types.

## Requirements

- Python 3.8+
- PyTorch 1.12+
- Uni-Mol Tools backend
- 4GB+ RAM (8GB+ recommended for training)

## Installation

```bash
cd unimol_tools/agent-harness
pip install -e .
```

## Documentation

- **SOP**: [UNIMOL_TOOLS.md](../UNIMOL_TOOLS.md)
- **Quick Start**: [docs/guides/02-QUICK-START.md](../docs/guides/02-QUICK-START.md)
- **Full Documentation**: [docs/README.md](../docs/README.md)

## Testing

```bash
cd docs/test
bash run_tests.sh --unit -v    # Unit tests (67 tests)
bash run_tests.sh --full -v    # Full test suite
```

## Performance Tips

- Start with 10 epochs for initial experiments
- Use smaller batch sizes if memory is limited
- Monitor storage with `storage analyze`
- Use `models rank` to identify best performers
- Clean up regularly with `cleanup auto`

## Troubleshooting

- **CUDA errors**: Reduce batch size or use CPU mode
- **CSV not recognized**: Verify SMILES column exists
- **Low accuracy**: Try more epochs or adjust learning rate
- **Storage full**: Run `cleanup auto` to free space

## Related

- **Uni-Mol Tools**: https://github.com/dptech-corp/Uni-Mol/tree/main/unimol_tools
- **Uni-Mol Paper**: https://arxiv.org/abs/2209.11126
- **CLI-Anything**: https://github.com/HKUDS/CLI-Anything
