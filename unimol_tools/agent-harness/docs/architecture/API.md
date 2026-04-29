# API Reference

Complete API reference for Uni-Mol Tools CLI modules and functions.

---

## CLI Commands

### Global Options

```bash
cli-anything-unimol-tools [GLOBAL_OPTIONS] COMMAND [ARGS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-p, --project` | Path | None | Path to project JSON file (required for most commands) |
| `--json` | Flag | False | Output in JSON format for automation |
| `--version` | Flag | - | Show version and exit |
| `--help` | Flag | - | Show help message |

---

## Project Commands

### `project new`

Create a new project.

**Syntax**:
```bash
cli-anything-unimol-tools project new -n NAME -t TYPE
```

**Options**:
| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `-n, --name` | String | Yes | Project name |
| `-t, --task-type` | Enum | Yes | Task type: `classification`, `regression`, `multiclass`, `multilabel_cls`, `multilabel_reg` |

**Returns**: Creates `{name}.json` project file

**Example**:
```bash
cli-anything-unimol-tools project new -n drug_activity -t classification
```

---

### `project info`

Display project information.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json project info
```

**Output** (text):
```
📁 Project: drug_activity
Type: classification
Datasets: Train (1000), Valid (200), Test (200)
Models: 5 runs
Storage: 912.3MB
```

**Output** (JSON with `--json`):
```json
{
  "project_name": "drug_activity",
  "task_type": "classification",
  "datasets": {
    "train": {"path": "train.csv", "samples": 1000},
    "valid": {"path": "valid.csv", "samples": 200},
    "test": {"path": "test.csv", "samples": 200}
  },
  "runs": 5,
  "storage_mb": 912.3
}
```

---

### `project set-dataset`

Set dataset path for a split.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json project set-dataset SPLIT PATH
```

**Arguments**:
| Argument | Type | Values |
|----------|------|--------|
| `SPLIT` | String | `train`, `valid`, `test` |
| `PATH` | Path | CSV file path |

**Example**:
```bash
cli-anything-unimol-tools -p project.json project set-dataset train data/train.csv
```

---

## Training Commands

### `train start`

Train a new model.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json train start [OPTIONS]
```

**Options**:
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--epochs` | Integer | 10 | Number of training epochs |
| `--batch-size` | Integer | 16 | Batch size |
| `--learning-rate` | Float | 1e-4 | Learning rate |
| `--dropout` | Float | 0.0 | Dropout rate |
| `--conf-cache-level` | Integer | 1 | Conformer cache level (0=none, 1=cache, 2=reuse) |

**Returns**: Creates `models/run_{N}/` with checkpoint and metrics

**Example**:
```bash
cli-anything-unimol-tools -p project.json train start \
  --epochs 20 \
  --batch-size 32 \
  --learning-rate 5e-5
```

---

## Prediction Commands

### `predict run`

Run predictions using a trained model.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json predict run RUN_ID INPUT_CSV [OPTIONS]
```

**Arguments**:
| Argument | Type | Description |
|----------|------|-------------|
| `RUN_ID` | String | Model run ID (e.g., `run_001`) |
| `INPUT_CSV` | Path | CSV file with SMILES column |

**Options**:
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-o, --output` | Path | `predictions.csv` | Output CSV path |

**Returns**: CSV file with predictions

**Example**:
```bash
cli-anything-unimol-tools -p project.json predict run run_001 test.csv -o results.csv
```

---

## Storage Commands

### `storage`

Analyze storage usage.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json storage
```

**Output** (text):
```
💾 Storage Analysis
Total Usage: 549.6MB
  Models: 541.9MB (98.6%)
  Conformers: 7.8MB (1.4%)
Recommendations: 3 models > 3 days old (save 546MB)
```

**Output** (JSON with `--json`):
```json
{
  "total_mb": 549.6,
  "breakdown": {
    "models": 541.9,
    "conformers": 7.8,
    "predictions": 0.0
  },
  "recommendations": [
    {
      "type": "old_models",
      "count": 3,
      "potential_savings_mb": 546.0
    }
  ]
}
```

---

## Model Management Commands

### `models rank`

Rank all models by performance.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json models rank
```

**Output** (text):
```
🏆 Model Ranking
Rank   Run ID       Score    AUC      Status
──────────────────────────────────────────────
🥇 1   run_003      9.1/10   0.9123   Best
🥈 2   run_002      9.0/10   0.8954   Good
```

**Output** (JSON with `--json`):
```json
{
  "models": [
    {
      "rank": 1,
      "run_id": "run_003",
      "score": 9.1,
      "auc": 0.9123,
      "duration_sec": 26.8,
      "status": "Best",
      "timestamp": "2024-01-15T12:00:00"
    }
  ],
  "recommendation": {
    "run_id": "run_003",
    "reason": "Highest AUC"
  }
}
```

---

### `models history`

Show model performance history.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json models history
```

**Output** (text):
```
📊 Model Performance History
Total runs: 3
Trend: improving

AUC Progress:
  run_001  │███████████████████████████████████ 0.8723
  run_002  │████████████████████████████████████████ 0.8954
  run_003  │████████████████████████████████████████████ 0.9123
```

**Output** (JSON with `--json`):
```json
{
  "total_runs": 3,
  "trend": "improving",
  "timeline": [
    {
      "run_id": "run_001",
      "timestamp": "2024-01-15T10:00:00",
      "auc": 0.8723,
      "duration_sec": 16.3
    }
  ],
  "insights": [
    {
      "type": "best_model",
      "message": "Best model: run_003 (AUC: 0.9123)"
    }
  ]
}
```

---

## Cleanup Commands

### `cleanup`

Clean up old models.

**Syntax**:
```bash
# Interactive mode
cli-anything-unimol-tools -p PROJECT.json cleanup

# Automatic mode
cli-anything-unimol-tools -p PROJECT.json cleanup --auto [OPTIONS]
```

**Options**:
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--auto` | Flag | False | Automatic cleanup without prompts |
| `--keep-best` | Integer | 3 | Number of best models to keep |
| `--min-auc` | Float | 0.75 | Minimum AUC threshold |
| `--max-age-days` | Integer | 7 | Maximum age in days |

**Example**:
```bash
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=2 --min-auc=0.80
```

---

## Archive Commands

### `archive list`

List all archived models.

**Syntax**:
```bash
cli-anything-unimol-tools archive list
```

**Output**:
```
📦 Archived Models
Total: 3 archives

  • drug_activity_run_002.tar.gz (18.2MB) - 2024-01-15
  • solubility_run_001.tar.gz (18.1MB) - 2024-01-14
```

---

### `archive restore`

Restore an archived model.

**Syntax**:
```bash
cli-anything-unimol-tools -p PROJECT.json archive restore RUN_ID
```

**Arguments**:
| Argument | Type | Description |
|----------|------|-------------|
| `RUN_ID` | String | Run ID to restore |

**Example**:
```bash
cli-anything-unimol-tools -p project.json archive restore run_002
```

---

## Python API

### Core Modules

#### storage.py

```python
def analyze_project_storage(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze storage usage for a project.

    Args:
        project: Project dictionary from JSON

    Returns:
        {
            'total_mb': float,
            'breakdown': {
                'models': float,
                'conformers': float,
                'predictions': float
            },
            'models_detail': [
                {
                    'run_id': str,
                    'size_mb': float,
                    'auc': float,
                    'age_days': int
                }
            ],
            'recommendations': [
                {
                    'type': str,
                    'message': str,
                    'potential_savings_mb': float
                }
            ]
        }
    """
```

```python
def get_directory_size(path: str) -> int:
    """
    Calculate directory size recursively.

    Args:
        path: Directory path

    Returns:
        Size in bytes
    """
```

```python
def format_size(size_bytes: int) -> str:
    """
    Format bytes to human-readable size.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., '123.45MB')
    """
```

---

#### models_manager.py

```python
def calculate_model_score(run: Dict[str, Any],
                          weight_auc: float = 1.0,
                          weight_time: float = 0.0,
                          weight_recency: float = 0.0) -> float:
    """
    Calculate composite score for a model.

    Current implementation: 100% AUC-based
    Score = AUC * 10

    Args:
        run: Run dictionary with metrics
        weight_auc: Weight for AUC metric (default 1.0)
        weight_time: Weight for training time (default 0.0)
        weight_recency: Weight for recency (default 0.0)

    Returns:
        Score from 0-10
    """
```

```python
def rank_models(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Rank all models in a project.

    Args:
        project: Project dictionary

    Returns:
        List of runs with scores, sorted by score (best first)
        [
            {
                'rank': int,
                'run_id': str,
                'score': float,
                'auc': float,
                'duration_sec': float,
                'status': str,  # Best/Good/Ok/Weak/Poor
                'timestamp': str,
                'metrics': dict
            }
        ]
    """
```

```python
def get_model_history(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get model performance history over time.

    Args:
        project: Project dictionary

    Returns:
        {
            'timeline': [
                {
                    'run_id': str,
                    'timestamp': str,
                    'auc': float,
                    'duration_sec': float
                }
            ],
            'trend': str,  # improving/declining/stable/insufficient_data
            'insights': [
                {
                    'type': str,
                    'message': str
                }
            ],
            'total_runs': int
        }
    """
```

```python
def suggest_deletable_models(project: Dict[str, Any],
                             keep_best_n: int = 3,
                             min_auc: float = 0.75,
                             max_age_days: int = 7) -> Dict[str, Any]:
    """
    Suggest which models can be safely deleted.

    Args:
        project: Project dictionary
        keep_best_n: Number of best models to keep
        min_auc: Minimum AUC to keep
        max_age_days: Maximum age in days to keep recent models

    Returns:
        {
            'delete': [
                {
                    'run_id': str,
                    'reason': str,
                    'auc': float,
                    'age_days': int
                }
            ],
            'archive': [...],
            'keep': [...]
        }
    """
```

---

#### cleanup.py

```python
def delete_model(project: Dict[str, Any],
                run_id: str,
                confirm: bool = True) -> bool:
    """
    Delete a model directory.

    Args:
        project: Project dictionary
        run_id: Run ID to delete
        confirm: Require user confirmation (default True)

    Returns:
        True if deleted, False if cancelled or error

    Raises:
        FileNotFoundError: If model directory doesn't exist
    """
```

```python
def archive_model(project: Dict[str, Any],
                 run_id: str,
                 archive_dir: Optional[str] = None) -> str:
    """
    Archive a model to tar.gz.

    Args:
        project: Project dictionary
        run_id: Run ID to archive
        archive_dir: Archive directory (default: ~/.unimol-archive/)

    Returns:
        Path to created archive

    Raises:
        FileNotFoundError: If model directory doesn't exist
        IOError: If archive creation fails
    """
```

```python
def restore_model(project: Dict[str, Any],
                 run_id: str,
                 archive_dir: Optional[str] = None) -> bool:
    """
    Restore an archived model.

    Args:
        project: Project dictionary
        run_id: Run ID to restore
        archive_dir: Archive directory (default: ~/.unimol-archive/)

    Returns:
        True if restored successfully

    Raises:
        FileNotFoundError: If archive doesn't exist
        IOError: If extraction fails
    """
```

```python
def batch_cleanup(project: Dict[str, Any],
                 delete_ids: List[str],
                 archive_ids: List[str]) -> Dict[str, Any]:
    """
    Execute bulk cleanup operations.

    Args:
        project: Project dictionary
        delete_ids: List of run IDs to delete
        archive_ids: List of run IDs to archive

    Returns:
        {
            'deleted': List[str],  # Successfully deleted run IDs
            'archived': List[str],  # Successfully archived run IDs
            'failed': List[Dict[str, str]],  # Failed operations
            'space_freed_mb': float
        }
    """
```

```python
def list_archives(archive_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all archived models.

    Args:
        archive_dir: Archive directory (default: ~/.unimol-archive/)

    Returns:
        [
            {
                'filename': str,
                'project': str,
                'run_id': str,
                'size_mb': float,
                'created': str,  # ISO format timestamp
                'path': str
            }
        ]
    """
```

---

## Data Structures

### Project JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "project_name": {"type": "string"},
    "task_type": {
      "type": "string",
      "enum": ["classification", "regression", "multiclass", "multilabel_cls", "multilabel_reg"]
    },
    "created": {"type": "string", "format": "date-time"},
    "project_root": {"type": "string"},
    "datasets": {
      "type": "object",
      "properties": {
        "train": {"type": "string"},
        "valid": {"type": "string"},
        "test": {"type": "string"}
      }
    },
    "runs": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "run_id": {"type": "string"},
          "timestamp": {"type": "string", "format": "date-time"},
          "config": {
            "type": "object",
            "properties": {
              "epochs": {"type": "integer"},
              "batch_size": {"type": "integer"},
              "learning_rate": {"type": "number"},
              "dropout": {"type": "number"}
            }
          },
          "metrics": {
            "type": "object",
            "properties": {
              "auc": {"type": "number"},
              "accuracy": {"type": "number"},
              "precision": {"type": "number"},
              "recall": {"type": "number"}
            }
          },
          "duration_sec": {"type": "number"},
          "save_path": {"type": "string"}
        }
      }
    }
  }
}
```

---

## Error Codes

| Code | Message | Cause |
|------|---------|-------|
| 1 | `Project file not found` | Invalid -p path |
| 2 | `Dataset file not found` | Invalid dataset path |
| 3 | `Model not found` | Invalid run_id |
| 4 | `Training failed` | Uni-Mol error |
| 5 | `Prediction failed` | Missing checkpoint or invalid input |
| 6 | `Archive not found` | Invalid run_id for restore |
| 7 | `Permission denied` | Cannot write to directory |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIMOL_WEIGHT_DIR` | Required | Path to Uni-Mol model weights |
| `CUDA_VISIBLE_DEVICES` | All GPUs | GPU device selection |
| `UNIMOL_ARCHIVE_DIR` | `~/.unimol-archive/` | Archive directory |
| `UNIMOL_DEBUG` | False | Enable debug logging |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | File not found |
| 4 | Operation failed |

---

## Next Steps

- **Architecture**: [DESIGN.md](DESIGN.md)
- **Tutorials**: [../tutorials/](../tutorials/)
- **Guides**: [../guides/](../guides/)
