# Demo: 5 Real Examples + All Features Testing

## 🎯 Overview

This demo uses **real example data** from the `examples/` directory to:
1. Train **5 different task types**
2. Select **Task 1** (Binary Classification) with 5 models
3. Test **all 6 new features** on the selected task

## 🚀 Quick Start

```bash
cd /path/to/agent-harness

# Option 1: Provide examples directory path and weights directory
bash demo_real_examples.sh /path/to/examples /path/to/weights

# Option 2: Provide examples only (weights will be downloaded if not found)
bash demo_real_examples.sh /path/to/examples

# Option 3: Use relative path (if examples/ is in parent directory)
bash demo_real_examples.sh ../examples ../Uni-Mol/unimol_tools/weights

# Option 4: Auto-detect (if examples/ exists at ../examples)
bash demo_real_examples.sh
```

## 📝 Usage

```bash
bash demo_real_examples.sh [EXAMPLES_DIR]

Arguments:
  EXAMPLES_DIR  Path to examples directory (optional)
                If not provided, will try ../examples
                If ../examples doesn't exist, will show usage help
```

## 💡 Examples

```bash
# Using absolute path
bash demo_real_examples.sh /home/user/unimol_tools/examples

# Using relative path
bash demo_real_examples.sh ../../unimol_tools/examples

# Using environment variable
EXAMPLES=/opt/data/examples
bash demo_real_examples.sh $EXAMPLES
```

## 📋 What It Does

### Part 1: Train 5 Real Example Tasks

| Task | Type | Data Source | Models Trained |
|------|------|-------------|----------------|
| **Task 1** | **Binary Classification** | `examples/binary_classification/` | **5** |
| Task 2 | Regression | `examples/regression/` | 1 |
| Task 3 | Multiclass (3 classes) | `examples/multiclass/` | 1 |
| Task 4 | Multilabel Classification (3 labels) | `examples/multilabel_classification/` | 1 |
| Task 5 | Multilabel Regression (3 targets) | `examples/multilabel_regression/` | 1 |

**Total**: 9 models across 5 tasks

### Part 2: Test All 6 Features on Task 1

Task 1 is selected because it has **5 trained models**, perfect for testing model management.

#### 1. 💾 Storage Analysis
```
Total: 152.3 MB
├── Models: 145.8 MB (95.7%)
├── Conformers: 5.2 MB (3.4%)
└── Predictions: 1.3 MB (0.9%)
```

#### 2. 🏆 Models Ranking
```
Rank  Run ID      AUC     Score   Status
1     run_003     0.92    9.2     Best
2     run_002     0.85    8.5     Good
3     run_001     0.78    7.8     Ok
4     run_005     0.72    7.2     Weak
5     run_004     0.68    6.8     Poor
```

#### 3. ⭐ Best Model
```
Best Model: run_003
AUC: 0.92
Score: 9.2
```

#### 4. 📈 Model History
```
Trend: Improving (+0.24 AUC)
Best: run_003 (AUC: 0.92)
```

#### 5. 🧹 Cleanup Suggestions
```
DELETE: 2 models (58.2 MB savings)
KEEP: 3 models (top performers + recent)
```

#### 6. ⚖️ Model Comparison
```
Comparing: run_001 vs run_003
Winner: run_003 (4/4 metrics)
```

## 📂 Data Source

All data comes from real examples in the repository:

```
examples/
├── binary_classification/
│   ├── mol_train.csv  (molecular binary classification)
│   └── mol_test.csv
├── regression/
│   ├── train.csv  (molecular property regression)
│   └── test.csv
├── multiclass/
│   ├── train.csv  (3-class classification)
│   └── test.csv
├── multilabel_classification/
│   ├── train.csv  (3 binary labels)
│   └── test.csv
└── multilabel_regression/
    ├── train.csv  (3 continuous targets)
    └── test.csv
```

## ⏱️ Estimated Time

- **GPU**: ~8-12 minutes total
  - Task 1: ~6 min (5 models)
  - Tasks 2-5: ~1-2 min each

- **CPU**: ~40-60 minutes total
  - Task 1: ~30 min (5 models)
  - Tasks 2-5: ~10 min each

## 📁 Output Structure

```
demo_projects/
├── task1_binary.json           # 5 models ← SELECTED FOR TESTING
├── task2_regression.json       # 1 model
├── task3_multiclass.json       # 1 model
├── task4_multilabel_cls.json   # 1 model
├── task5_multilabel_reg.json   # 1 model
└── predictions.csv             # Test set predictions
```

## 🔧 Manual Testing

After running the demo, test features on any task:

```bash
# Task 1 (Binary Classification) - 5 models
python -m cli_anything.unimol_tools -p demo_projects/task1_binary/project.json storage
python -m cli_anything.unimol_tools -p demo_projects/task1_binary/project.json models rank
python -m cli_anything.unimol_tools -p demo_projects/task1_binary/project.json models best
python -m cli_anything.unimol_tools -p demo_projects/task1_binary/project.json models history
python -m cli_anything.unimol_tools -p demo_projects/task1_binary/project.json cleanup
python -m cli_anything.unimol_tools -p demo_projects/task1_binary/project.json models compare run_001 run_002

# Task 2 (Regression)
python -m cli_anything.unimol_tools -p demo_projects/task2_regression/project.json storage
python -m cli_anything.unimol_tools -p demo_projects/task2_regression/project.json models best

# Task 3 (Multiclass)
python -m cli_anything.unimol_tools -p demo_projects/task3_multiclass/project.json storage

# Task 4 (Multilabel Classification)
python -m cli_anything.unimol_tools -p demo_projects/task4_multilabel_cls/project.json storage

# Task 5 (Multilabel Regression)
python -m cli_anything.unimol_tools -p demo_projects/task5_multilabel_reg/project.json storage

# JSON output
python -m cli_anything.unimol_tools -p demo_projects/task1_binary/project.json storage --json
```

## ✅ Success Criteria

After running, you should see:
- ✅ 5 project JSON files created
- ✅ 9 models trained (5 + 1 + 1 + 1 + 1)
- ✅ All 6 features tested on Task 1
- ✅ Predictions generated for test set
- ✅ Storage breakdown displayed
- ✅ Model rankings with scores
- ✅ Best model identified
- ✅ Performance trends shown
- ✅ Cleanup suggestions provided
- ✅ Model comparison displayed

## 💡 Why Task 1?

Task 1 (Binary Classification) is selected for feature testing because:
- **5 models trained** → Best for model management demos
- **Real molecular data** → Practical drug discovery example
- **Binary classification** → Clear metrics (AUC, accuracy)
- **Has test set** → Can demonstrate prediction

## 🎨 Output Format

The script provides detailed, color-coded output:
- 🔵 **Blue**: Info messages
- 🟢 **Green**: Success messages
- 🟡 **Yellow**: Section headers

## 🔄 Comparison with Other Demos

| Feature | demo_real_examples.sh | demo_5_tasks.sh | demo_complete.sh |
|---------|----------------------|-----------------|------------------|
| Data Source | ✅ Real examples | Generated from real data | Small synthetic data |
| Number of Tasks | 5 | 5 | 4 |
| Models per Task | 5,1,1,1,1 | 5,1,1,1,1 | 5,1,1,1 |
| Features Tested | All 6 | All 6 | All 6 |
| Data Quality | ✅ Production-ready | ✅ Real-derived | Testing only |
| **Recommended** | ✅ **YES** | Yes | For quick tests |

## 🚀 Recommended Usage

**This is the recommended demo** because:
1. Uses actual example data provided with the tool
2. No data generation needed
3. Production-ready data quality
4. Tests all 5 supported task types
5. Comprehensive feature testing

---

**Script**: `demo_real_examples.sh`
**Data**: Real examples from `examples/` directory
**Tasks**: 5 task types
**Models**: 9 total (5 on Task 1)
**Features**: All 6 tested on Task 1
