# Installation Guide

Complete installation guide for Uni-Mol Tools CLI.

---

## Prerequisites

Before installing, ensure your system meets these requirements:

### System Requirements
- **Operating System**: Linux (tested on Ubuntu 20.04+)
- **Python**: 3.8 or higher
- **CUDA**: 11.8+ (for GPU support)
- **Disk Space**: ~2GB minimum
  - Uni-Mol model weights: ~1.5GB
  - Dependencies: ~500MB

### Required Software
```bash
# Check Python version
python --version  # Should be 3.8+

# Check CUDA (for GPU users)
nvidia-smi

# Required: git
git --version
```

---

## Installation Steps

### Step 1: Clone Uni-Mol Repository

Uni-Mol Tools provides the underlying molecular property prediction framework.

```bash
# Clone the official Uni-Mol repository
git clone git@github.com:deepmodeling/Uni-Mol.git

# Navigate to unimol_tools directory
cd Uni-Mol/unimol_tools
```

**Directory structure**:
```
Uni-Mol/
├── unimol/              # Core Uni-Mol implementation
├── unimol_tools/        # ← We need this directory
│   ├── unimol_tools/
│   │   ├── weights/     # Model weights location
│   │   ├── models/
│   │   └── ...
│   ├── setup.py
│   └── requirements.txt
└── ...
```

### Step 2: Download Model Weights

Uni-Mol requires pre-trained molecular representation weights.

```bash
# Still in Uni-Mol/unimol_tools directory
python -m unimol_tools.weights.weighthub
```

**What this does**:
- Downloads pre-trained Uni-Mol weights (~1.5GB)
- Saves to `unimol_tools/weights/` directory
- Creates weight files needed for molecular encoding

**Expected output**:
```
Downloading Uni-Mol weights...
[████████████████████████████] 100%
Weights saved to: /path/to/Uni-Mol/unimol_tools/unimol_tools/weights
✓ Download complete
```

**Verify weights**:
```bash
ls unimol_tools/weights/
# Should see: mol_pre_all_h_220816.pt, mol_pre_no_h_220816.pt, etc.
```

### Step 3: Configure Weight Directory

Set the environment variable for the CLI to locate weights.

```bash
# Add to your shell profile (~/.bashrc or ~/.zshrc)
export UNIMOL_WEIGHT_DIR=/path/to/Uni-Mol/unimol_tools/unimol_tools/weights

# Example:
export UNIMOL_WEIGHT_DIR=/home/user/Uni-Mol/unimol_tools/unimol_tools/weights
```

**Make it permanent**:
```bash
# For bash users
echo 'export UNIMOL_WEIGHT_DIR=/path/to/your/Uni-Mol/unimol_tools/unimol_tools/weights' >> ~/.bashrc
source ~/.bashrc

# For zsh users
echo 'export UNIMOL_WEIGHT_DIR=/path/to/your/Uni-Mol/unimol_tools/unimol_tools/weights' >> ~/.zshrc
source ~/.zshrc
```

**Verify**:
```bash
echo $UNIMOL_WEIGHT_DIR
# Should print: /path/to/Uni-Mol/unimol_tools/unimol_tools/weights
```

### Step 4: Clone CLI-Anything Repository

CLI-Anything provides the CLI harness framework.

```bash
# Navigate to your workspace (not inside Uni-Mol)
cd ~/workspace  # or your preferred location

# Clone CLI-Anything
git clone git@github.com:HKUDS/CLI-Anything.git

# Navigate to Uni-Mol Tools harness
cd CLI-Anything/unimol_tools/agent-harness
```

**Directory structure**:
```
CLI-Anything/
├── unimol_tools/
│   ├── agent-harness/         # ← CLI harness
│   │   ├── cli_anything/
│   │   │   └── unimol_tools/
│   │   │       ├── core/      # Core modules
│   │   │       │   ├── storage.py
│   │   │       │   ├── models_manager.py
│   │   │       │   └── cleanup.py
│   │   │       └── unimol_tools_cli.py
│   │   ├── setup.py
│   │   └── pyproject.toml
│   └── examples/
└── ...
```

### Step 5: Install CLI Harness

Install the CLI package in editable mode.

```bash
# Still in CLI-Anything/unimol_tools/agent-harness
pip install -e .
```

**What this does**:
- Installs the `cli-anything-unimol-tools` command
- Links to Uni-Mol Tools as dependency
- Installs required packages (Click, colorama, etc.)

**Expected output**:
```
Processing /path/to/CLI-Anything/unimol_tools/agent-harness
Installing collected packages: cli-anything-unimol-tools
Successfully installed cli-anything-unimol-tools
```

### Step 6: Verify Installation

Test that everything is working correctly.

```bash
# Check CLI is installed
cli-anything-unimol-tools --version

# Should output: cli-anything-unimol-tools, version X.X.X
```

**Run help command**:
```bash
cli-anything-unimol-tools --help
```

**Expected output**:
```
Usage: cli-anything-unimol-tools [OPTIONS] COMMAND [ARGS]...

  Uni-Mol Tools CLI - Molecular property prediction

Options:
  -p, --project PATH  Path to project JSON file
  --json             Output in JSON format
  --version          Show version
  --help             Show this message and exit

Commands:
  archive   Manage archived models
  cleanup   Clean up old models
  models    Model management
  predict   Run predictions
  project   Project management
  storage   Storage analysis
  train     Training commands
```

---

## Configuration

### Optional: GPU Configuration

If using GPU acceleration:

```bash
# Check CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Set CUDA device (optional)
export CUDA_VISIBLE_DEVICES=0  # Use GPU 0
```

### Optional: Set Default Project Path

To avoid typing `-p project.json` every time:

```bash
# Create alias in shell profile
alias unimol-cli='cli-anything-unimol-tools -p ~/my_projects/current.json'

# Usage
unimol-cli storage
unimol-cli models rank
```

---

## Troubleshooting

### Issue: `cli-anything-unimol-tools: command not found`

**Cause**: CLI not in PATH after installation.

**Solution**:
```bash
# Check pip install location
pip show cli-anything-unimol-tools

# Add to PATH if needed
export PATH="$HOME/.local/bin:$PATH"

# Or reinstall with --user flag
pip install --user -e .
```

### Issue: Weight files not found

**Cause**: `UNIMOL_WEIGHT_DIR` not set correctly.

**Solution**:
```bash
# Verify environment variable
echo $UNIMOL_WEIGHT_DIR

# Should point to directory containing .pt files
ls $UNIMOL_WEIGHT_DIR/*.pt

# If not set, add to shell profile
export UNIMOL_WEIGHT_DIR=/correct/path/to/weights
source ~/.bashrc  # or ~/.zshrc
```

### Issue: CUDA errors

**Cause**: CUDA version mismatch or GPU not available.

**Solution**:
```bash
# Check PyTorch CUDA version
python -c "import torch; print(torch.version.cuda)"

# Install correct PyTorch version
pip install torch==2.0.0+cu118 -f https://download.pytorch.org/whl/torch_stable.html

# Or use CPU-only mode (slower)
export CUDA_VISIBLE_DEVICES=""
```

### Issue: Import errors for `unimol_tools`

**Cause**: Uni-Mol not properly installed.

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

## Verification Checklist

Before proceeding, verify all steps completed:

- [ ] Uni-Mol repository cloned
- [ ] Model weights downloaded (~1.5GB in `weights/` directory)
- [ ] `UNIMOL_WEIGHT_DIR` environment variable set
- [ ] CLI-Anything repository cloned
- [ ] CLI harness installed (`cli-anything-unimol-tools` command available)
- [ ] `cli-anything-unimol-tools --version` works
- [ ] `cli-anything-unimol-tools --help` shows all commands

---

## Next Steps

Once installation is complete:

1. **Quick Start**: See [Quick Start Guide](02-QUICK-START.md) for a 5-minute tutorial
2. **Create Your First Project**: Follow [Basic Usage](03-BASIC-USAGE.md)
3. **Run Demo**: Try the interactive features demo:
   ```bash
   cd CLI-Anything/unimol_tools/examples/scripts
   bash demo_interactive_features.sh
   ```

---

## Directory Layout Summary

After installation, your directories should look like:

```
~/workspace/
├── Uni-Mol/                           # Uni-Mol repository
│   └── unimol_tools/
│       └── unimol_tools/
│           ├── weights/               # ← Model weights here
│           │   ├── mol_pre_all_h_220816.pt
│           │   └── ...
│           └── ...
│
└── CLI-Anything/                      # CLI-Anything repository
    └── unimol_tools/
        └── agent-harness/             # ← CLI harness
            ├── cli_anything/
            │   └── unimol_tools/      # ← CLI code
            └── setup.py
```

**Environment variables**:
```bash
export UNIMOL_WEIGHT_DIR=/path/to/Uni-Mol/unimol_tools/unimol_tools/weights
export CUDA_VISIBLE_DEVICES=0  # Optional, for GPU
```

---

## Installation Complete! 🎉

You're now ready to use Uni-Mol Tools CLI for molecular property prediction.

**Quick test**:
```bash
# Create a test project
cli-anything-unimol-tools project new -n test_project -t classification

# Should create: test_project.json
ls test_project.json
```

If this works, your installation is successful!

**Proceed to**: [Quick Start Guide](02-QUICK-START.md)
