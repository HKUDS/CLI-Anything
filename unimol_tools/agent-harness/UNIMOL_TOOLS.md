# Uni-Mol Tools CLI-Anything SOP

## Overview

Uni-Mol Tools is a molecular property prediction framework that provides easy-to-use interfaces for training and inference of molecular models. This CLI-Anything harness enables interactive molecular property prediction through conversational AI.

## Supported Task Types

1. **Binary Classification** - Classify molecules into two categories (e.g., active/inactive)
2. **Regression** - Predict continuous properties (e.g., binding affinity)
3. **Multiclass Classification** - Classify into multiple categories
4. **Multilabel Classification** - Assign multiple binary labels
5. **Multilabel Regression** - Predict multiple continuous values

## Standard Operating Procedures

### 1. Project Management

#### Create a New Project
```bash
python3 -m cli_anything.unimol_tools --json project create --name my_project
```

#### List All Projects
```bash
python3 -m cli_anything.unimol_tools --json project list
```

#### Switch Project
```bash
python3 -m cli_anything.unimol_tools --json project switch --name my_project
```

### 2. Training Models

#### Train a Binary Classification Model
```bash
python3 -m cli_anything.unimol_tools --json train \
  --data-path /path/to/train.csv \
  --target-col target \
  --task-type classification \
  --epochs 10 \
  --learning-rate 0.0001
```

#### Train a Regression Model
```bash
python3 -m cli_anything.unimol_tools --json train \
  --data-path /path/to/train.csv \
  --target-col score \
  --task-type regression \
  --epochs 10 \
  --learning-rate 0.0001
```

### 3. Model Management

#### List All Models
```bash
python3 -m cli_anything.unimol_tools --json models list
```

#### Show Model Details
```bash
python3 -m cli_anything.unimol_tools --json models show --model-id <id>
```

#### Rank Models by Performance
```bash
python3 -m cli_anything.unimol_tools --json models rank
```

### 4. Storage Management

#### Check Storage Usage
```bash
python3 -m cli_anything.unimol_tools --json storage analyze
```

#### Clean Up Poor Performers
```bash
python3 -m cli_anything.unimol_tools --json cleanup auto
```

### 5. Prediction

#### Make Predictions
```bash
python3 -m cli_anything.unimol_tools --json predict \
  --model-id <id> \
  --data-path /path/to/test.csv
```

## Data Format Requirements

### CSV File Structure
- Must contain a `SMILES` column with molecular structures
- Must contain target column(s) for training
- Example:

```csv
SMILES,target
CCO,1
CCCO,0
CC(C)O,1
```

### Task-Specific Formats

**Binary Classification**: Target values are 0/1 or True/False
**Regression**: Target values are floating-point numbers
**Multiclass**: Target values are integers (0, 1, 2, ...)
**Multilabel**: Multiple target columns with 0/1 values
**Multilabel Regression**: Multiple target columns with float values

## Session Management

The CLI maintains session state for:
- Current project
- Recently trained models
- Command history
- Storage statistics

### Interactive Mode
```bash
python3 -m cli_anything.unimol_tools
```

### One-Shot Mode
```bash
python3 -m cli_anything.unimol_tools --json <command> [options]
```

## Best Practices

1. **Create Projects for Different Experiments**: Keep models organized by research goals
2. **Monitor Storage**: Use `storage analyze` regularly to track disk usage
3. **Clean Up Old Models**: Use `cleanup auto` to remove underperforming models
4. **Check Model Rankings**: Use `models rank` to compare performance
5. **Use JSON Mode for Automation**: Add `--json` flag for programmatic access

## Troubleshooting

### Issue: Training fails with "CUDA out of memory"
**Solution**: Reduce batch size or use CPU mode

### Issue: CSV file not recognized
**Solution**: Ensure SMILES column exists and is properly formatted

### Issue: Model not found
**Solution**: Run `models list` to verify model ID

### Issue: Storage full
**Solution**: Run `cleanup auto` or manually delete old models with `models delete`

## Performance Optimization

- **Batch Size**: Default is 32, reduce if memory issues occur
- **Epochs**: Start with 10, increase if underfitting
- **Learning Rate**: Default is 0.0001, adjust based on loss curves
- **Data Split**: Default train/val split is 80/20

## Testing

Run the test suite to verify functionality:

```bash
# Unit tests (no backend required)
cd unimol_tools/agent-harness/docs/test
bash run_tests.sh --unit -v

# Full test suite
bash run_tests.sh --full -v
```

## Additional Resources

- **Quick Start Guide**: [docs/guides/02-QUICK-START.md](docs/guides/02-QUICK-START.md)
- **API Reference**: [docs/architecture/API.md](docs/architecture/API.md)
- **Test Data**: https://github.com/545487677/CLI-Anything-unimol-tools/tree/main/unimol_tools/examples
- **Uni-Mol Paper**: https://arxiv.org/abs/2209.11126
