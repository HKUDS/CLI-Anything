---
name: "cli-anything-cloudanalyzer"
description: "Command-line interface for CloudAnalyzer — Agent-friendly harness for CloudAnalyzer, a QA platform for mapping, localization, and perception outputs. Supports 27 commands across 8 groups: point cloud evaluation, trajectory evaluation, ground segmentation QA, config-driven quality gates, baseline evolution, processing, visualization, and interactive REPL."
---

# cli-anything-cloudanalyzer

Agent-friendly command-line harness for [CloudAnalyzer](https://github.com/rsasaki0109/CloudAnalyzer) — a QA platform for mapping, localization, and perception point cloud outputs.

**27 commands** across 8 groups.

## Installation

```bash
pip install cli-anything-cloudanalyzer
```

**Prerequisites:**
- Python 3.10+
- CloudAnalyzer: `pip install cloudanalyzer`

## Global Options

```bash
cli-anything-cloudanalyzer [--project FILE] [--json] COMMAND [ARGS]...
```

| Option | Description |
|---|---|
| `-p, --project TEXT` | Path to project JSON file |
| `--json` | Output results as JSON (for agent consumption) |

## Command Groups

### 1. evaluate — Point Cloud Evaluation (6 commands)

#### evaluate run
Evaluate a point cloud against a reference (Chamfer, F1, AUC, Hausdorff).

```bash
cli-anything-cloudanalyzer evaluate run source.pcd reference.pcd
cli-anything-cloudanalyzer --json evaluate run source.pcd reference.pcd
```

Options: `--plot TEXT`, `--threshold FLOAT`

#### evaluate compare
Compare two point clouds with optional registration.

```bash
cli-anything-cloudanalyzer evaluate compare src.pcd tgt.pcd --register gicp
```

Options: `--register TEXT` (icp/gicp/none)

#### evaluate diff
Quick distance statistics between two point clouds.

```bash
cli-anything-cloudanalyzer evaluate diff a.pcd b.pcd --threshold 0.1
```

#### evaluate batch
Batch evaluation of multiple point clouds against a reference.

```bash
cli-anything-cloudanalyzer --json evaluate batch results/ reference.pcd --min-auc 0.95
```

Options: `--min-auc FLOAT`, `--max-chamfer FLOAT`

#### evaluate ground
Evaluate ground segmentation quality (precision, recall, F1, IoU).

```bash
cli-anything-cloudanalyzer --json evaluate ground est_ground.pcd est_ng.pcd ref_ground.pcd ref_ng.pcd --min-f1 0.9
```

Options: `--voxel-size FLOAT`, `--min-precision FLOAT`, `--min-recall FLOAT`, `--min-f1 FLOAT`, `--min-iou FLOAT`

#### evaluate pipeline
Filter, downsample, evaluate in one command.

```bash
cli-anything-cloudanalyzer evaluate pipeline input.pcd reference.pcd -o output.pcd
```

---

### 2. trajectory — Trajectory Evaluation (3 commands)

#### trajectory evaluate
Evaluate estimated vs reference trajectory (ATE, RPE, drift, lateral, longitudinal).

```bash
cli-anything-cloudanalyzer --json trajectory evaluate est.csv gt.csv --max-ate 0.5 --max-lateral 0.3
```

Options: `--max-ate FLOAT`, `--max-rpe FLOAT`, `--max-drift FLOAT`, `--min-coverage FLOAT`, `--max-lateral FLOAT`, `--max-longitudinal FLOAT`, `--align-origin`, `--align-rigid`

#### trajectory batch
Batch trajectory evaluation.

```bash
cli-anything-cloudanalyzer trajectory batch runs/ --reference-dir gt/ --max-drift 1.0
```

#### trajectory run-evaluate
Integrated map + trajectory evaluation.

```bash
cli-anything-cloudanalyzer trajectory run-evaluate map.pcd map_ref.pcd traj.csv traj_ref.csv
```

Options: `--min-auc FLOAT`, `--max-ate FLOAT`

---

### 3. check — Config-Driven Quality Gate (2 commands)

#### check run
Run unified QA from a config file.

```bash
cli-anything-cloudanalyzer --json check run cloudanalyzer.yaml
```

Options: `--output-json TEXT`

#### check init
Generate a starter config file.

```bash
cli-anything-cloudanalyzer check init cloudanalyzer.yaml --profile integrated
```

Options: `--profile TEXT` (mapping/localization/perception/integrated), `--force`

---

### 4. baseline — Baseline Evolution (3 commands)

#### baseline decision
Decide whether to promote, keep, or reject a candidate baseline.

```bash
cli-anything-cloudanalyzer --json baseline decision qa/summary.json --history-dir qa/history/
```

Options: `--history TEXT` (repeatable), `--history-dir TEXT`, `--output-json TEXT`

#### baseline save
Save a QA summary to the history directory.

```bash
cli-anything-cloudanalyzer baseline save qa/summary.json --history-dir qa/history/ --keep 10
```

Options: `--history-dir TEXT`, `--label TEXT`, `--keep INTEGER`

#### baseline list
List saved baselines.

```bash
cli-anything-cloudanalyzer --json baseline list --history-dir qa/history/
```

---

### 5. process — Point Cloud Processing (6 commands)

#### process downsample
Voxel grid downsampling.

```bash
cli-anything-cloudanalyzer process downsample cloud.pcd -o down.pcd -v 0.05
```

#### process sample
Random point sampling.

```bash
cli-anything-cloudanalyzer process sample cloud.pcd -o sampled.pcd -n 10000
```

#### process filter
Statistical outlier removal.

```bash
cli-anything-cloudanalyzer process filter cloud.pcd -o filtered.pcd
```

#### process split
Split point cloud into grid tiles (writes metadata.yaml).

```bash
cli-anything-cloudanalyzer process split large.pcd -o tiles/ -g 100
```

#### process merge
Merge multiple point clouds.

```bash
cli-anything-cloudanalyzer process merge a.pcd b.pcd -o merged.pcd
```

#### process convert
Convert between point cloud formats.

```bash
cli-anything-cloudanalyzer process convert input.las -o output.pcd
```

---

### 6. inspect — Visualization (3 commands)

#### inspect view
Open a point cloud viewer.

```bash
cli-anything-cloudanalyzer inspect view cloud.pcd
```

#### inspect web
Interactive browser inspection.

```bash
cli-anything-cloudanalyzer inspect web map.pcd ref.pcd --heatmap
```

#### inspect web-export
Export a static HTML inspection bundle.

```bash
cli-anything-cloudanalyzer inspect web-export map.pcd ref.pcd -o bundle/
```

---

### 7. info — Metadata (2 commands)

#### info show
Show point cloud metadata.

```bash
cli-anything-cloudanalyzer --json info show cloud.pcd
```

#### info version
Show CloudAnalyzer version.

---

### 8. session — Session Management (2 commands)

#### session new
Create a new harness project JSON file.

```bash
cli-anything-cloudanalyzer session new -o project.json -n my-run
```

#### session history
Show recent operations for the project given with `-p` / `--project`.

```bash
cli-anything-cloudanalyzer --project project.json session history --last 20
```

---

## Typical Agent Workflows

### Workflow 1: Evaluate and gate a point cloud

```bash
cli-anything-cloudanalyzer --json evaluate run output.pcd reference.pcd
```

### Workflow 2: Config-driven QA pipeline

```bash
cli-anything-cloudanalyzer check init cloudanalyzer.yaml --profile integrated
cli-anything-cloudanalyzer --json check run cloudanalyzer.yaml
```

### Workflow 3: Baseline management

```bash
cli-anything-cloudanalyzer --json check run cloudanalyzer.yaml --output-json qa/summary.json
cli-anything-cloudanalyzer baseline save qa/summary.json --history-dir qa/history/
cli-anything-cloudanalyzer --json baseline decision qa/summary.json --history-dir qa/history/
```

### Workflow 4: Ground segmentation QA

```bash
cli-anything-cloudanalyzer --json evaluate ground \
  est_ground.pcd est_ng.pcd ref_ground.pcd ref_ng.pcd --min-f1 0.9
```
