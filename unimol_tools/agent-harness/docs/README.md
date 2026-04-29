# Uni-Mol Tools CLI Documentation

**A CLI-Anything harness for Uni-Mol Tools - Interactive molecular property prediction**

---

## 📚 Documentation Structure

```
docs/
├── README.md                          # This file
├── guides/
│   ├── 01-INSTALLATION.md            # Complete installation guide
│   ├── 02-QUICK-START.md             # Quick start tutorial
│   ├── 03-BASIC-USAGE.md             # Basic commands
│   ├── 04-INTERACTIVE-FEATURES.md    # Interactive features guide
│   └── 05-TROUBLESHOOTING.md         # Common issues
├── tutorials/
│   ├── CLASSIFICATION.md             # Binary classification tutorial
│   ├── REGRESSION.md                 # Regression tutorial
│   └── ADVANCED.md                   # Advanced usage
├── architecture/
│   ├── DESIGN.md                     # Architecture design
│   └── API.md                        # API reference
└── workflows/
    ├── TRAINING-SOP.md               # Training workflow SOP
    ├── CLEANUP-SOP.md                # Cleanup workflow SOP
    └── DIAGRAMS.md                   # Workflow diagrams
```

---

## 🚀 Quick Links

### For First-Time Users
1. [Installation Guide](guides/01-INSTALLATION.md) - Start here
2. [Quick Start](guides/02-QUICK-START.md) - 5-minute tutorial
3. [Basic Usage](guides/03-BASIC-USAGE.md) - Essential commands

### For Regular Users
- [Interactive Features](guides/04-INTERACTIVE-FEATURES.md) - Storage, ranking, cleanup
- [Classification Tutorial](tutorials/CLASSIFICATION.md)
- [Regression Tutorial](tutorials/REGRESSION.md)

### For Developers
- [Architecture Design](architecture/DESIGN.md)
- [API Reference](architecture/API.md)
- [Training SOP](workflows/TRAINING-SOP.md)

---

## 📖 What is Uni-Mol Tools CLI?

Uni-Mol Tools CLI is a command-line interface harness for [Uni-Mol Tools](https://github.com/deepmodeling/Uni-Mol) that provides:

- ✅ **Project-based workflow** - Organize your experiments
- ✅ **Interactive model management** - Storage analysis, ranking, cleanup
- ✅ **5 task types** - Classification, regression, multiclass, multilabel
- ✅ **Automatic model tracking** - Performance history and trends
- ✅ **Smart cleanup** - Intelligent storage management
- ✅ **JSON API** - Automation-friendly

---

## 🎯 Key Features

### Core Features
```bash
# Project management
cli-anything-unimol-tools project new -n myproject -t classification
cli-anything-unimol-tools -p project.json project info

# Training
cli-anything-unimol-tools -p project.json train start --epochs 10

# Prediction
cli-anything-unimol-tools -p project.json predict run run_001 test.csv
```

### Interactive Features (New!)
```bash
# Storage analysis
cli-anything-unimol-tools -p project.json storage

# Model ranking
cli-anything-unimol-tools -p project.json models rank

# Performance history
cli-anything-unimol-tools -p project.json models history

# Smart cleanup
cli-anything-unimol-tools -p project.json cleanup --auto
```

---

## 📋 Prerequisites

- **Python**: 3.8+
- **CUDA**: 11.8+ (for GPU support)
- **Disk Space**: ~2GB (Uni-Mol weights + dependencies)
- **OS**: Linux (tested on Ubuntu 20.04+)

---

## ⚡ Quick Installation

```bash
# 1. Clone Uni-Mol repository
git clone git@github.com:deepmodeling/Uni-Mol.git
cd Uni-Mol/unimol_tools

# 2. Download weights
python -m unimol_tools.weights.weighthub

# 3. Clone CLI-Anything
cd ../..
git clone git@github.com:HKUDS/CLI-Anything.git
cd CLI-Anything/unimol_tools/agent-harness

# 4. Install CLI
pip install -e .

# 5. Configure weights
export UNIMOL_WEIGHT_DIR=/path/to/Uni-Mol/unimol_tools/unimol_tools/weights

# 6. Test installation
cli-anything-unimol-tools --version
```

**See [Complete Installation Guide](guides/01-INSTALLATION.md) for detailed steps.**

---

## 📊 Supported Task Types

| Task Type | Description | Example Use Case |
|-----------|-------------|------------------|
| **Binary Classification** | Two-class prediction | Drug activity (active/inactive) |
| **Regression** | Continuous value prediction | Solubility prediction |
| **Multiclass Classification** | Multiple exclusive classes | Toxicity levels (low/medium/high) |
| **Multilabel Classification** | Multiple binary labels | Multi-target drug properties |
| **Multilabel Regression** | Multiple continuous values | Multiple molecular properties |

---

## 🔄 Typical Workflow

```
1. Create Project → 2. Set Dataset → 3. Train → 4. Evaluate → 5. Predict
```

See [Training SOP](workflows/TRAINING-SOP.md) for detailed workflow.

---

## 💡 Example Session

```bash
# Create a new classification project
cli-anything-unimol-tools project new -n drug_discovery -t classification

# Set training data
cli-anything-unimol-tools -p drug_discovery.json \
  project set-dataset train data/train.csv

# Train model (10 epochs)
cli-anything-unimol-tools -p drug_discovery.json \
  train start --epochs 10 --batch-size 32

# Check performance
cli-anything-unimol-tools -p drug_discovery.json models rank

# Run predictions
cli-anything-unimol-tools -p drug_discovery.json \
  predict run run_001 data/test.csv -o predictions.csv

# Analyze storage
cli-anything-unimol-tools -p drug_discovery.json storage

# Cleanup old models
cli-anything-unimol-tools -p drug_discovery.json cleanup --auto
```

---

## 🆘 Getting Help

```bash
# General help
cli-anything-unimol-tools --help

# Command-specific help
cli-anything-unimol-tools project --help
cli-anything-unimol-tools train --help
cli-anything-unimol-tools cleanup --help
```

---

## 📞 Support

- **Issues**: See [Troubleshooting Guide](guides/05-TROUBLESHOOTING.md)
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Browse all guides in `docs/`

---

## 📄 License

This CLI harness follows the same license as CLI-Anything and Uni-Mol Tools.

---

**Next Steps:**
- 📖 [Complete Installation Guide](guides/01-INSTALLATION.md)
- 🚀 [Quick Start Tutorial](guides/02-QUICK-START.md)
- 🎯 [Training SOP](workflows/TRAINING-SOP.md)
