# Troubleshooting Guide

Common issues and solutions for Uni-Mol Tools CLI.

---

## Installation Issues

### Issue: `cli-anything-unimol-tools: command not found`

**Symptoms**:
```bash
$ cli-anything-unimol-tools --version
bash: cli-anything-unimol-tools: command not found
```

**Cause**: CLI not installed or not in PATH.

**Solution 1**: Reinstall the CLI
```bash
cd /path/to/CLI-Anything/unimol_tools/agent-harness
pip install -e .

# Verify
which cli-anything-unimol-tools
```

**Solution 2**: Add to PATH
```bash
# Find pip install location
pip show cli-anything-unimol-tools | grep Location

# Add bin directory to PATH
export PATH="$HOME/.local/bin:$PATH"

# Make permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Solution 3**: Use python -m
```bash
# Alternative way to run
python -m cli_anything.unimol_tools.unimol_tools_cli --version
```

---

### Issue: Weight files not found

**Symptoms**:
```bash
FileNotFoundError: [Errno 2] No such file or directory: '/path/to/weights/mol_pre_all_h_220816.pt'
```

**Cause**: `UNIMOL_WEIGHT_DIR` not set or pointing to wrong location.

**Solution 1**: Set environment variable
```bash
# Find where you installed Uni-Mol
cd /path/to/Uni-Mol/unimol_tools

# Set weight directory
export UNIMOL_WEIGHT_DIR=$(pwd)/unimol_tools/weights

# Verify
ls $UNIMOL_WEIGHT_DIR/*.pt
```

**Solution 2**: Make permanent
```bash
# Add to shell profile
echo 'export UNIMOL_WEIGHT_DIR=/path/to/Uni-Mol/unimol_tools/unimol_tools/weights' >> ~/.bashrc
source ~/.bashrc

# Verify
echo $UNIMOL_WEIGHT_DIR
```

**Solution 3**: Re-download weights
```bash
cd /path/to/Uni-Mol/unimol_tools
python -m unimol_tools.weights.weighthub

# Check downloaded
ls unimol_tools/weights/
# Should see: mol_pre_all_h_220816.pt, mol_pre_no_h_220816.pt, etc.
```

---

### Issue: Import errors for `unimol_tools`

**Symptoms**:
```python
ModuleNotFoundError: No module named 'unimol_tools'
```

**Cause**: Uni-Mol Tools package not installed.

**Solution**:
```bash
# Navigate to Uni-Mol/unimol_tools
cd /path/to/Uni-Mol/unimol_tools

# Install in editable mode
pip install -e .

# Verify
python -c "import unimol_tools; print(unimol_tools.__version__)"
```

---

## CUDA and GPU Issues

### Issue: CUDA out of memory

**Symptoms**:
```
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB
```

**Cause**: Batch size too large for GPU memory.

**Solution 1**: Reduce batch size
```bash
# Try smaller batch size
cli-anything-unimol-tools -p project.json train start --batch-size 8

# If still fails, try even smaller
cli-anything-unimol-tools -p project.json train start --batch-size 4
```

**Solution 2**: Use CPU instead
```bash
# Disable GPU
export CUDA_VISIBLE_DEVICES=""

# Train on CPU (slower but works)
cli-anything-unimol-tools -p project.json train start --batch-size 16
```

**Solution 3**: Clear GPU memory
```bash
# Kill other processes using GPU
nvidia-smi

# Find PID of process using GPU
# Kill it: kill -9 <PID>

# Try training again
cli-anything-unimol-tools -p project.json train start
```

---

### Issue: CUDA version mismatch

**Symptoms**:
```
RuntimeError: The NVIDIA driver on your system is too old
CUDA driver version is insufficient for CUDA runtime version
```

**Cause**: PyTorch CUDA version doesn't match system CUDA.

**Solution 1**: Check versions
```bash
# Check system CUDA
nvidia-smi | grep "CUDA Version"

# Check PyTorch CUDA
python -c "import torch; print(f'PyTorch CUDA: {torch.version.cuda}')"
```

**Solution 2**: Reinstall matching PyTorch
```bash
# For CUDA 11.8
pip install torch==2.0.0+cu118 -f https://download.pytorch.org/whl/torch_stable.html

# For CUDA 12.1
pip install torch==2.1.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
```

**Solution 3**: Use CPU version
```bash
# Install CPU-only PyTorch (no CUDA required)
pip install torch==2.0.0+cpu -f https://download.pytorch.org/whl/torch_stable.html

export CUDA_VISIBLE_DEVICES=""
```

---

## Training Issues

### Issue: Training very slow

**Symptoms**:
- First epoch takes 10+ minutes
- Conformer generation stuck

**Cause**: Conformer generation from scratch, no GPU, or large batch size.

**Solution 1**: Enable conformer caching (default)
```bash
# First run will be slow (generates conformers)
cli-anything-unimol-tools -p project.json train start --epochs 10

# Subsequent runs will be fast (reuses conformers)
cli-anything-unimol-tools -p project.json train start --epochs 20
```

**Solution 2**: Use GPU
```bash
# Check CUDA is available
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# If False, check CUDA installation
nvidia-smi
```

**Solution 3**: Reduce data size for testing
```bash
# Create small test dataset (first 50 rows)
head -n 51 train.csv > train_small.csv

# Test training on small dataset
cli-anything-unimol-tools -p test.json project set-dataset train train_small.csv
cli-anything-unimol-tools -p test.json train start --epochs 5
```

---

### Issue: Metrics showing as empty `{}`

**Symptoms**:
```json
{
  "metrics": {}
}
```

**Cause**: Metrics file not found or failed to save.

**Solution**: Check metric.result file
```bash
# Look for metric.result in model directory
ls models/run_001/metric.result

# If missing, re-run training
cli-anything-unimol-tools -p project.json train start --epochs 10

# Check again
cat models/run_001/metric.result
```

---

### Issue: Training crashes with pickle error

**Symptoms**:
```python
pickle.UnpicklingError: invalid load key, '\x00'
```

**Cause**: Corrupted checkpoint or metric file.

**Solution 1**: Delete corrupted run and retrain
```bash
# Remove corrupted run
rm -rf models/run_001/

# Retrain
cli-anything-unimol-tools -p project.json train start --epochs 10
```

**Solution 2**: Clear all models and start fresh
```bash
# Backup project.json
cp project.json project.json.backup

# Remove all models
rm -rf models/*

# Retrain
cli-anything-unimol-tools -p project.json train start --epochs 10
```

---

## Prediction Issues

### Issue: Prediction file saved to wrong location

**Symptoms**:
- Expected: `predictions.csv`
- Actual: `predictions/predictions/predict.csv`

**Cause**: Uni-Mol treats output path as directory.

**Solution**: This is now handled automatically by the CLI
```bash
# CLI automatically detects .csv extension and moves file
cli-anything-unimol-tools -p project.json predict run run_001 test.csv -o results.csv

# File will be at: results.csv (not results/predict.csv)
```

If you still see this issue:
```bash
# Find the actual output
find . -name "predict.csv"

# Move it manually
mv path/to/predict.csv desired_location.csv
```

---

### Issue: Predictions fail with "No checkpoint found"

**Symptoms**:
```
FileNotFoundError: No checkpoint found in models/run_001/
```

**Cause**: Model checkpoint missing or corrupted.

**Solution 1**: Check if checkpoint exists
```bash
ls models/run_001/checkpoint.pth
```

**Solution 2**: Use different run
```bash
# List all available runs
cli-anything-unimol-tools -p project.json project info

# Use a different run
cli-anything-unimol-tools -p project.json predict run run_002 test.csv
```

**Solution 3**: Retrain the model
```bash
cli-anything-unimol-tools -p project.json train start --epochs 10
```

---

## Data Issues

### Issue: "SMILES column not found"

**Symptoms**:
```
KeyError: 'SMILES'
```

**Cause**: CSV missing SMILES column or wrong column name.

**Solution**: Check CSV format
```bash
# View first few lines
head train.csv

# Should have SMILES column (case-sensitive)
SMILES,label
CC(C)Cc1ccc,1
CCN(CC)C(=O),0
```

**Fix CSV**:
```bash
# If column is named differently (e.g., "smiles" lowercase)
# Rename it to "SMILES" (uppercase)

# Using sed
sed -i '1s/smiles/SMILES/' train.csv

# Or edit manually
nano train.csv
```

---

### Issue: Invalid SMILES causing errors

**Symptoms**:
```
ValueError: Cannot parse SMILES: ...
RDKit ERROR: Can't kekulize mol
```

**Cause**: Invalid or malformed SMILES strings.

**Solution 1**: Validate SMILES with RDKit
```python
from rdkit import Chem

def validate_smiles(smiles_list):
    valid = []
    invalid = []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is not None:
            valid.append(smi)
        else:
            invalid.append(smi)
    return valid, invalid

# Read your CSV
import pandas as df
data = pd.read_csv('train.csv')

valid, invalid = validate_smiles(data['SMILES'])
print(f"Valid: {len(valid)}, Invalid: {len(invalid)}")
print(f"Invalid SMILES: {invalid}")

# Save cleaned data
data_clean = data[data['SMILES'].isin(valid)]
data_clean.to_csv('train_clean.csv', index=False)
```

**Solution 2**: Use cleaned dataset
```bash
cli-anything-unimol-tools -p project.json project set-dataset train train_clean.csv
```

---

## Storage and Cleanup Issues

### Issue: `storage` command shows 0B usage

**Symptoms**:
```
Total Usage: 0B
```

**Cause**: No models trained yet, or wrong project path.

**Solution 1**: Train a model first
```bash
cli-anything-unimol-tools -p project.json train start --epochs 10
cli-anything-unimol-tools -p project.json storage
```

**Solution 2**: Check project path
```bash
# Make sure project.json is correct
cat project.json | jq '.project_root'

# Should show correct directory
# If not, you may be using wrong project file
```

---

### Issue: Cleanup deletes everything

**Symptoms**:
- All models deleted
- No runs left

**Cause**: Too aggressive cleanup settings.

**Solution**: Use conservative settings
```bash
# Keep more models
cli-anything-unimol-tools -p project.json cleanup --auto \
  --keep-best=5 \
  --min-auc=0.60 \
  --max-age-days=30
```

**Prevention**: Use interactive mode first
```bash
# Interactive mode shows what will be deleted
cli-anything-unimol-tools -p project.json cleanup

# Review suggestions before confirming
```

---

### Issue: Archive restore fails

**Symptoms**:
```
FileNotFoundError: Archive not found: run_002
```

**Cause**: Archive doesn't exist or wrong run ID.

**Solution 1**: List available archives
```bash
cli-anything-unimol-tools archive list

# Use exact run_id from list
cli-anything-unimol-tools -p project.json archive restore run_002
```

**Solution 2**: Check archive directory
```bash
ls ~/.unimol-archive/

# Look for project_name_run_id.tar.gz files
```

---

## Project Issues

### Issue: "Project already exists"

**Symptoms**:
```
Error: Project file drug_activity.json already exists
```

**Cause**: Trying to create project with existing name.

**Solution 1**: Use different name
```bash
cli-anything-unimol-tools project new -n drug_activity_v2 -t classification
```

**Solution 2**: Delete old project
```bash
# Backup first
cp drug_activity.json drug_activity.json.backup

# Delete
rm drug_activity.json

# Create new
cli-anything-unimol-tools project new -n drug_activity -t classification
```

**Solution 3**: Continue with existing project
```bash
# Just use existing project
cli-anything-unimol-tools -p drug_activity.json project info
```

---

### Issue: Wrong task type

**Symptoms**:
- Created regression project but have classification data
- Need to change task type

**Cause**: Wrong task type specified during project creation.

**Solution**: Create new project with correct type
```bash
# Can't change task type of existing project
# Create new project
cli-anything-unimol-tools project new -n project_correct -t classification

# Copy dataset settings
cli-anything-unimol-tools -p project_correct.json project set-dataset train train.csv
```

---

## Performance Issues

### Issue: Models take up too much space

**Symptoms**:
- Each model is ~180MB
- Disk filling up fast

**Solution 1**: Regular cleanup
```bash
# Keep only top 2 models
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=2
```

**Solution 2**: Archive old models
```bash
# Archive instead of delete (saves 90% space)
cli-anything-unimol-tools -p project.json cleanup  # Choose "Archive" option
```

**Solution 3**: Delete conformer cache if not needed
```bash
# If not training more models, can delete conformers
rm -rf conformers/

# Saves disk space but conformers will need regeneration if training again
```

---

## Common Mistakes

### Mistake 1: Not setting datasets before training

**Wrong**:
```bash
cli-anything-unimol-tools project new -n myproject -t classification
cli-anything-unimol-tools -p myproject.json train start  # ERROR: No dataset
```

**Correct**:
```bash
cli-anything-unimol-tools project new -n myproject -t classification
cli-anything-unimol-tools -p myproject.json project set-dataset train train.csv
cli-anything-unimol-tools -p myproject.json train start  # OK
```

---

### Mistake 2: Forgetting `-p` flag

**Wrong**:
```bash
cli-anything-unimol-tools train start  # ERROR: No project specified
```

**Correct**:
```bash
cli-anything-unimol-tools -p project.json train start
```

**Or use alias**:
```bash
alias umol='cli-anything-unimol-tools -p project.json'
umol train start
```

---

### Mistake 3: Using wrong data format

**Wrong** (for classification):
```csv
SMILES,activity
CC(C)Cc1ccc,active    # Should be 0 or 1, not text
CCN(CC)C(=O),inactive
```

**Correct**:
```csv
SMILES,label
CC(C)Cc1ccc,1
CCN(CC)C(=O),0
```

---

## Getting More Help

### Check logs

Training logs are saved in model directories:
```bash
cat models/run_001/train.log
```

### Enable debug mode

```bash
# Set environment variable for verbose output
export UNIMOL_DEBUG=1

cli-anything-unimol-tools -p project.json train start
```

### Check system information

```bash
# Python version
python --version

# CUDA version
nvidia-smi

# PyTorch info
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}')"

# Disk space
df -h .
```

### Report issues

If you encounter a bug:

1. **Check this guide** for common solutions
2. **Check existing issues** on GitHub
3. **Gather information**:
   ```bash
   # Version
   cli-anything-unimol-tools --version

   # System info
   uname -a
   python --version

   # Error message (full traceback)
   ```
4. **Create issue** on GitHub with details

---

## Quick Diagnosis

Run this script to check your setup:

```bash
#!/bin/bash
# diagnose.sh - Check Uni-Mol Tools CLI setup

echo "=== Uni-Mol Tools CLI Diagnostics ==="
echo ""

# CLI installation
echo "1. CLI Installation:"
which cli-anything-unimol-tools
cli-anything-unimol-tools --version
echo ""

# Weight directory
echo "2. Weight Directory:"
echo "UNIMOL_WEIGHT_DIR=$UNIMOL_WEIGHT_DIR"
if [ -d "$UNIMOL_WEIGHT_DIR" ]; then
  ls -lh $UNIMOL_WEIGHT_DIR/*.pt 2>/dev/null || echo "No weight files found"
else
  echo "Directory not found!"
fi
echo ""

# Python environment
echo "3. Python Environment:"
python --version
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import unimol_tools; print(f'Uni-Mol Tools: OK')" 2>&1
echo ""

# CUDA
echo "4. CUDA:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv 2>/dev/null || echo "No CUDA GPU found (will use CPU)"
echo ""

# Disk space
echo "5. Disk Space:"
df -h . | grep -v "Filesystem"
echo ""

echo "=== End Diagnostics ==="
```

Run with:
```bash
bash diagnose.sh
```

---

## Summary

Most common issues and solutions:

| Issue | Quick Fix |
|-------|-----------|
| Command not found | `pip install -e .` |
| No weights | `export UNIMOL_WEIGHT_DIR=/path/to/weights` |
| CUDA OOM | `--batch-size 4` or `export CUDA_VISIBLE_DEVICES=""` |
| Slow training | Enable conformer caching (default) |
| No metrics | Check `models/run_001/metric.result` |
| Wrong predictions location | Now auto-handled by CLI |
| Invalid SMILES | Validate and clean data with RDKit |
| Too much disk usage | `cleanup --auto --keep-best=2` |

---

## Next Steps

- **Installation**: See [Installation Guide](01-INSTALLATION.md)
- **Quick Start**: See [Quick Start Guide](02-QUICK-START.md)
- **Full Reference**: See [Basic Usage](03-BASIC-USAGE.md)
- **Features**: See [Interactive Features](04-INTERACTIVE-FEATURES.md)
