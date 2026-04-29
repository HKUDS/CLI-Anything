# Architecture Design

System architecture and design principles for Uni-Mol Tools CLI.

---

## Overview

Uni-Mol Tools CLI is a command-line harness built on the CLI-Anything framework that provides an interactive interface for molecular property prediction using Uni-Mol.

**Key Components**:
- CLI Interface (Click-based)
- Core Modules (Storage, Models Manager, Cleanup)
- Uni-Mol Backend Integration
- Project Management System
- Interactive Features

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  cli-anything-unimol-tools (Click Framework)         │  │
│  │  - project commands                                  │  │
│  │  - train commands                                    │  │
│  │  - predict commands                                  │  │
│  │  - storage/models/cleanup commands                   │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Modules                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Storage    │  │    Models    │  │   Cleanup    │     │
│  │   Analyzer   │  │   Manager    │  │   Manager    │     │
│  │              │  │              │  │              │     │
│  │ - Size calc  │  │ - Ranking    │  │ - Delete     │     │
│  │ - Duplicates │  │ - History    │  │ - Archive    │     │
│  │ - Recommend  │  │ - Compare    │  │ - Restore    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 Project Management                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  project.json (State Management)                     │  │
│  │  - Configuration                                      │  │
│  │  - Datasets                                           │  │
│  │  - Runs history                                       │  │
│  │  - Metrics tracking                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Uni-Mol Backend                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  unimol_backend.py                                    │  │
│  │  - UniMolClassifier / UniMolRegressor                │  │
│  │  - Conformer generation                               │  │
│  │  - Model training                                     │  │
│  │  - Prediction                                         │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Uni-Mol                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Uni-Mol Library (deepmodeling/Uni-Mol)              │  │
│  │  - Molecular encoder                                  │  │
│  │  - Pre-trained weights                                │  │
│  │  - 3D conformer handling                              │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    File System                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Models     │  │  Conformers  │  │  Predictions │     │
│  │              │  │              │  │              │     │
│  │ run_001/     │  │ *.sdf        │  │ *.csv        │     │
│  │ run_002/     │  │ (cached)     │  │              │     │
│  │ ...          │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  Archive: ~/.unimol-archive/                                │
│  - Compressed models (tar.gz)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. CLI Interface (`unimol_tools_cli.py`)

**Responsibility**: User interaction and command routing

**Framework**: Click (Python CLI framework)

**Command Groups**:
```
cli-anything-unimol-tools
├── project (new, info, set-dataset)
├── train (start)
├── predict (run)
├── storage (analyze disk usage)
├── models (rank, history, compare)
├── cleanup (interactive/automatic cleanup)
└── archive (list, restore)
```

**Design Pattern**: Command pattern with Click decorators

**Key Features**:
- Global options (`-p` project, `--json` output)
- Context passing via Click context
- Input validation
- Error handling

### 2. Storage Analyzer (`core/storage.py`)

**Responsibility**: Disk usage analysis and optimization recommendations

**Key Functions**:
```python
analyze_project_storage(project: Dict) -> Dict:
    """
    Analyzes storage usage:
    - Models: checkpoint files
    - Conformers: SDF cache
    - Predictions: output files

    Returns recommendations for cleanup
    """

get_directory_size(path: str) -> int:
    """Calculate directory size recursively"""

format_size(size_bytes: int) -> str:
    """Human-readable size formatting"""
```

**Design Principles**:
- Fast scanning (no deep file inspection)
- Detects duplicates (SDF files)
- Provides actionable recommendations
- Calculates potential savings

### 3. Models Manager (`core/models_manager.py`)

**Responsibility**: Model ranking, comparison, and history tracking

**Key Functions**:
```python
calculate_model_score(run: Dict,
                      weight_auc: float = 1.0,
                      weight_time: float = 0.0,
                      weight_recency: float = 0.0) -> float:
    """
    Scoring algorithm (currently 100% AUC-based):
    Score = AUC * 10
    Range: 0-10
    """

rank_models(project: Dict) -> List[Dict]:
    """
    Rank all models by score
    Adds status labels (Best/Good/Ok/Weak/Poor)
    """

get_model_history(project: Dict) -> Dict:
    """
    Timeline of performance
    Trend detection (improving/declining/stable)
    Insights generation
    """

suggest_deletable_models(project: Dict,
                         keep_best_n: int = 3,
                         min_auc: float = 0.75,
                         max_age_days: int = 7) -> Dict:
    """
    Categorize models:
    - delete: Low performance, old
    - archive: Medium performance, old
    - keep: Top N, recent
    """
```

**Design Principles**:
- Transparent scoring (100% AUC for classification)
- Configurable thresholds
- Safe defaults (keep top 3)
- Trend analysis for insights

### 4. Cleanup Manager (`core/cleanup.py`)

**Responsibility**: Safe model deletion and archival

**Key Functions**:
```python
delete_model(project: Dict, run_id: str) -> bool:
    """Permanently delete model directory"""

archive_model(project: Dict, run_id: str,
              archive_dir: str = None) -> str:
    """
    Archive model to tar.gz (~90% compression)
    Location: ~/.unimol-archive/
    """

restore_model(project: Dict, run_id: str,
              archive_dir: str = None) -> bool:
    """Restore archived model to models/ directory"""

batch_cleanup(project: Dict,
              delete_ids: List[str],
              archive_ids: List[str]) -> Dict:
    """Execute bulk cleanup operations"""

list_archives(archive_dir: str = None) -> List[Dict]:
    """List all archived models"""
```

**Design Principles**:
- Safety first (confirm before delete)
- Archive before delete when unsure
- Atomic operations (all or nothing)
- Verification after operations

### 5. Uni-Mol Backend (`unimol_backend.py`)

**Responsibility**: Integration with Uni-Mol library

**Key Components**:
```python
class UniMolBackend:
    """
    Wrapper for Uni-Mol classifier/regressor
    Handles:
    - Data loading from CSV
    - Conformer generation
    - Model training
    - Prediction
    - Metrics extraction
    """

    def train(config: Dict) -> Dict:
        """Train model and return metrics"""

    def predict(config: Dict) -> pd.DataFrame:
        """Run predictions on new data"""
```

**Design Principles**:
- Isolate Uni-Mol specifics
- Handle conformer caching
- Extract and normalize metrics
- Error handling for RDKit/Uni-Mol issues

---

## Data Flow

### Training Flow

```
User Command
    │
    ├─> CLI parses arguments
    │
    ├─> Load project.json
    │
    ├─> Validate datasets exist
    │
    ├─> Generate run_id
    │
    ├─> Create run directory
    │
    ├─> UniMolBackend.train()
    │   │
    │   ├─> Load train/valid datasets
    │   │
    │   ├─> Generate conformers (if not cached)
    │   │   └─> Save to conformers/ directory
    │   │
    │   ├─> Initialize Uni-Mol model
    │   │
    │   ├─> Train for N epochs
    │   │
    │   ├─> Evaluate on validation set
    │   │
    │   └─> Save checkpoint and metrics
    │
    ├─> Load metrics from metric.result
    │
    ├─> Update project.json with run info
    │
    └─> Display results to user
```

### Prediction Flow

```
User Command
    │
    ├─> CLI parses arguments
    │
    ├─> Load project.json
    │
    ├─> Validate run_id exists
    │
    ├─> UniMolBackend.predict()
    │   │
    │   ├─> Load input CSV
    │   │
    │   ├─> Generate conformers
    │   │
    │   ├─> Load model checkpoint
    │   │
    │   ├─> Run inference
    │   │
    │   └─> Return predictions
    │
    ├─> Save predictions to CSV
    │
    └─> Display completion message
```

### Cleanup Flow

```
User Command
    │
    ├─> CLI parses arguments
    │
    ├─> Load project.json
    │
    ├─> models_manager.suggest_deletable_models()
    │   │
    │   ├─> Rank all models
    │   │
    │   ├─> Apply thresholds (keep_best_n, min_auc, max_age)
    │   │
    │   └─> Categorize (delete/archive/keep)
    │
    ├─> Display recommendations
    │
    ├─> Prompt user (interactive mode)
    │   or Auto-execute (automatic mode)
    │
    ├─> For each model to delete:
    │   └─> cleanup.delete_model()
    │
    ├─> For each model to archive:
    │   └─> cleanup.archive_model()
    │       ├─> Create tar.gz
    │       ├─> Save to ~/.unimol-archive/
    │       └─> Delete original
    │
    ├─> Update project.json (remove deleted runs)
    │
    └─> Display results (space freed)
```

---

## Design Patterns

### 1. Command Pattern

**Usage**: CLI commands

**Implementation**: Click decorators
```python
@cli.command("train")
@click.option("--epochs", default=10)
def train_start(epochs):
    """Train a model"""
    # Implementation
```

**Benefits**:
- Clear command structure
- Easy to extend
- Consistent argument parsing

### 2. Facade Pattern

**Usage**: UniMolBackend

**Purpose**: Simplify Uni-Mol interaction

**Implementation**:
```python
class UniMolBackend:
    """Facade for Uni-Mol library"""

    def train(self, config):
        # Hide complexity of Uni-Mol setup
        # Provide simple interface
```

**Benefits**:
- Isolates Uni-Mol specifics
- Easier to test
- Can swap backends

### 3. Strategy Pattern

**Usage**: Cleanup strategies

**Implementation**: Different combinations of parameters
```python
# Conservative strategy
cleanup(keep_best=5, min_auc=0.75, max_age_days=14)

# Aggressive strategy
cleanup(keep_best=1, min_auc=0.85, max_age_days=3)
```

**Benefits**:
- Flexible cleanup policies
- Easy to customize
- Reusable strategies

### 4. Repository Pattern

**Usage**: Project state management

**Implementation**: project.json as data store
```python
# Load
project = json.load(open('project.json'))

# Modify
project['runs'].append(new_run)

# Save
json.dump(project, open('project.json', 'w'))
```

**Benefits**:
- Single source of truth
- Easy to backup
- Human-readable

---

## State Management

### Project State (`project.json`)

```json
{
  "project_name": "drug_discovery",
  "task_type": "classification",
  "created": "2024-01-15T10:30:00",
  "project_root": "/path/to/project",
  "datasets": {
    "train": "data/train.csv",
    "valid": "data/valid.csv",
    "test": "data/test.csv"
  },
  "runs": [
    {
      "run_id": "run_001",
      "timestamp": "2024-01-15T11:00:00",
      "config": {
        "epochs": 10,
        "batch_size": 16,
        "learning_rate": 0.0001
      },
      "metrics": {
        "auc": 0.8723,
        "accuracy": 0.85,
        "precision": 0.83,
        "recall": 0.87
      },
      "duration_sec": 18.3,
      "save_path": "models/run_001"
    }
  ]
}
```

**State Transitions**:
```
initialized → training → trained → deployed
                    ↓
                 failed
```

**Persistence**: JSON file (human-readable, version-controllable)

---

## Extension Points

### Adding New Commands

```python
# In unimol_tools_cli.py

@cli.command("my-command")
@click.option("--option", default="value")
@click.pass_context
def my_command(ctx, option):
    """My custom command"""

    project = ctx.obj['project']

    # Implementation

    output("Success!")
```

### Adding New Metrics

```python
# In models_manager.py

def calculate_model_score(run, **weights):
    # Add new metric
    specificity = run['metrics'].get('specificity', 0.5)
    specificity_score = specificity * 10

    # Include in total score
    total_score = (
        auc_score * weight_auc +
        specificity_score * weight_specificity
    )

    return total_score
```

### Custom Cleanup Strategies

```python
# Define custom strategy
def custom_cleanup_strategy(project):
    """Keep models for peer review"""

    runs = project['runs']

    # Keep all models with AUC > 0.90
    keep = [r for r in runs if r['metrics']['auc'] > 0.90]

    # Archive rest
    archive = [r for r in runs if r['metrics']['auc'] <= 0.90]

    return {'keep': keep, 'archive': archive, 'delete': []}
```

---

## Performance Considerations

### Storage Analysis

- **Fast scanning**: Use `os.walk()` instead of deep inspection
- **Caching**: Store sizes in memory during traversal
- **Lazy loading**: Only read files when needed

### Model Ranking

- **In-memory**: All ranking done on project.json data
- **No disk I/O**: Metrics already loaded
- **Fast sorting**: Python's built-in sort is O(n log n)

### Archival

- **Streaming compression**: Use tarfile streaming mode
- **No temporary files**: Direct tar.gz creation
- **Background option**: Could add async archival for large models

### Conformer Caching

- **Default caching**: Saves hours on subsequent runs
- **Shared cache**: Multiple projects can share conformers
- **Smart reuse**: Only generates new conformers for new molecules

---

## Testing Strategy

### Unit Tests

```python
def test_calculate_model_score():
    run = {'metrics': {'auc': 0.8723}}
    score = calculate_model_score(run)
    assert score == 8.723

def test_rank_models():
    project = {'runs': [
        {'run_id': 'run_001', 'metrics': {'auc': 0.8}},
        {'run_id': 'run_002', 'metrics': {'auc': 0.9}}
    ]}
    ranked = rank_models(project)
    assert ranked[0]['run_id'] == 'run_002'
```

### Integration Tests

```bash
# Test full workflow
cli-anything-unimol-tools project new -n test -t classification
cli-anything-unimol-tools -p test.json project set-dataset train data.csv
cli-anything-unimol-tools -p test.json train start --epochs 2
cli-anything-unimol-tools -p test.json models rank
cli-anything-unimol-tools -p test.json cleanup --auto --keep-best=1
```

### Manual Testing

See `examples/scripts/demo_interactive_features.sh` for comprehensive demo

---

## Security Considerations

### Input Validation

- SMILES validation (RDKit)
- File path sanitization
- JSON schema validation

### File Operations

- Check paths are within project directory
- Prevent path traversal attacks
- Verify file types before loading

### Archive Safety

- Verify tar.gz integrity before extract
- Extract to known safe location
- Check archive size before restoring

---

## Future Enhancements

### Planned Features

1. **Web Dashboard**: Interactive UI for visualization
2. **Remote Training**: Submit jobs to remote cluster
3. **Auto-tuning**: Automated hyperparameter optimization
4. **Model Serving**: REST API for predictions
5. **Distributed Training**: Multi-GPU support

### Extension Ideas

1. **Custom Backends**: Support other molecular encoders
2. **External Data**: Integration with ChEMBL, PubChem
3. **Advanced Visualization**: 3D structure viewer
4. **Collaboration**: Shared projects and models
5. **CI/CD Integration**: Automated model validation

---

## Dependencies

### Core Dependencies

```
unimol_tools >= 1.0.0       # Uni-Mol library
click >= 8.0.0              # CLI framework
colorama >= 0.4.0           # Terminal colors
```

### Optional Dependencies

```
matplotlib >= 3.5.0         # Visualization
seaborn >= 0.12.0           # Statistical plots
scikit-learn >= 1.0.0       # ML metrics
rdkit >= 2022.09.1          # Chemistry toolkit
```

---

## Next Steps

- **API Reference**: [API.md](API.md)
- **Implementation**: See source code in `cli_anything/unimol_tools/`
- **Examples**: See `examples/scripts/` for usage examples
