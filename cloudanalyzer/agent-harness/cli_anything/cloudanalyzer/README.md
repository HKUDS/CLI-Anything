# cli-anything-cloudanalyzer

Agent-friendly CLI harness for [CloudAnalyzer](https://github.com/rsasaki0109/CloudAnalyzer) — a QA platform for mapping, localization, and perception point cloud outputs.

## Quick Start

```bash
pip install cli-anything-cloudanalyzer

# Evaluate a point cloud
cli-anything-cloudanalyzer --json evaluate run output.pcd reference.pcd

# Run config-driven QA
cli-anything-cloudanalyzer --json check run cloudanalyzer.yaml

# Trajectory evaluation with quality gate
cli-anything-cloudanalyzer --json trajectory evaluate est.csv gt.csv --max-ate 0.5

# Ground segmentation QA
cli-anything-cloudanalyzer --json evaluate ground est_g.pcd est_ng.pcd ref_g.pcd ref_ng.pcd --min-f1 0.9

# Baseline management
cli-anything-cloudanalyzer baseline save qa/summary.json --history-dir qa/history/
cli-anything-cloudanalyzer --json baseline decision qa/summary.json --history-dir qa/history/

# Interactive REPL
cli-anything-cloudanalyzer
```

## Why a Harness?

CloudAnalyzer is already CLI-first, but this harness adds:

- **Structured `--json` output** on every command for agent consumption
- **REPL mode** for interactive exploration
- **Project/session management** with operation history and undo
- **SKILL.md** for agent auto-discovery via CLI-Anything ecosystem
- **Unified Click interface** grouping 27 commands into logical groups

## Commands

See [SKILL.md](cli_anything/cloudanalyzer/skills/SKILL.md) for the full command reference.

| Group | Commands | Description |
|---|---:|---|
| evaluate | 6 | Point cloud evaluation (Chamfer, F1, AUC, ground segmentation) |
| trajectory | 3 | Trajectory QA (ATE, RPE, drift, lateral, longitudinal) |
| check | 2 | Config-driven quality gates |
| baseline | 3 | Baseline evolution (promote/keep/reject) |
| process | 6 | Downsample, split, filter, merge, convert |
| inspect | 3 | Visualization and browser inspection |
| info | 2 | Metadata and version |
| session | 2 | Project and session management |

## Requirements

- Python 3.10+
- CloudAnalyzer (`pip install cloudanalyzer`)
