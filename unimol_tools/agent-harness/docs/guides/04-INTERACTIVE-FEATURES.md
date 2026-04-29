# Interactive Features Guide

Complete guide to interactive model management features in Uni-Mol Tools CLI.

---

## Overview

Uni-Mol Tools CLI provides 5 interactive features for intelligent model management:

1. **Storage Analysis** - Visualize space usage and find optimization opportunities
2. **Model Ranking** - Automatically rank models by AUC performance
3. **Performance History** - Track model performance trends over time
4. **Smart Cleanup** - Intelligently delete or archive low-value models
5. **Archive Management** - Compress models (~90% space savings) and restore when needed

---

## 1. Storage Analysis

### Purpose

Understand where your disk space is going and identify optimization opportunities.

### Command

```bash
cli-anything-unimol-tools -p project.json storage
```

### What It Shows

**Components Breakdown**:
- **Models**: Trained model checkpoints (.pth files)
- **Conformers**: Cached 3D molecular structures (.sdf files)
- **Predictions**: Saved prediction results (.csv files)

**Recommendations**:
- Models older than threshold
- Duplicate conformer files
- Potential space savings

### Example Output

```
💾 Storage Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Usage: 549.6MB

Components:
  Models        541.9MB ( 98.6%)  █████████████████████████████░
  Conformers      7.8MB (  1.4%)  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  Predictions     0.0MB (  0.0%)  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Models (3):
  • run_001: 180.6MB (AUC: 0.8723) - 2 days old
  • run_002: 180.6MB (AUC: 0.8954) - 1 day old
  • run_003: 180.7MB (AUC: 0.9123) - 0 days old ⭐

Conformers:
  • 5 unique SDF files (7.8MB)
  • 3 shared across models

⚠️  Recommendations:
   • 2 models are > 1 day old (save 361MB)
   • Conformers are efficiently cached ✓

   Potential savings: 361MB (66%)

💡 Tip: Run 'cleanup --auto' to free up space
```

### Understanding Conformers

**What are conformers?**
- 3D molecular structures generated from SMILES
- Required for Uni-Mol encoding
- Cached as `.sdf` files for reuse

**Why do they show up?**
- First training run: generates conformers from SMILES
- Saves to `conformers/` directory
- Subsequent runs: reuses cached files (faster)

**Cache levels** (controlled by `--conf-cache-level`):
- `0`: No caching - regenerate each time (slow, minimal disk)
- `1`: Smart caching - generate once, reuse (default, recommended)
- `2`: Strict reuse - only use existing cache (fast, requires pre-gen)

### Use Cases

**Before experiments**:
```bash
# Check available space
cli-anything-unimol-tools -p project.json storage
```

**After experiments**:
```bash
# See what accumulated
cli-anything-unimol-tools -p project.json storage

# Clean up based on recommendations
cli-anything-unimol-tools -p project.json cleanup --auto
```

**Monitoring multiple projects**:
```bash
# Generate storage report for all projects
for proj in projects/*.json; do
  echo "=== $(basename $proj) ==="
  cli-anything-unimol-tools -p "$proj" storage
  echo ""
done > storage_report.txt
```

---

## 2. Model Ranking

### Purpose

Automatically rank all trained models by performance to identify the best model for production.

### Command

```bash
cli-anything-unimol-tools -p project.json models rank
```

### Scoring System

**Current scoring: 100% AUC-based**
- Score = AUC × 10
- Range: 0-10 (higher is better)
- Example: AUC 0.8723 → Score 8.7/10

**Status labels**:
- **Best**: AUC ≥ 0.85 and score ≥ 8.5
- **Good**: AUC ≥ 0.85
- **Ok**: AUC ≥ 0.75
- **Weak**: AUC ≥ 0.65
- **Poor**: AUC < 0.65

### Example Output

```
🏆 Model Ranking
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Based on AUC performance

Rank   Run ID       Score    AUC      Duration   Status
──────────────────────────────────────────────────────────────────
🥇 1   run_003      9.1/10   0.9123   26.8s      Best
🥈 2   run_002      9.0/10   0.8954   19.7s      Good
🥉 3   run_001      8.7/10   0.8723   16.3s      Good
   4   run_004      7.8/10   0.7803   18.2s      Ok
   5   run_005      7.2/10   0.7234   15.9s      Weak

💡 Recommendation: Use run_003 for production
   - Highest AUC: 0.9123
   - Consistent performance across metrics
```

### Visual Indicators

| Icon | Meaning |
|------|---------|
| 🥇 | Rank 1 (best model) |
| 🥈 | Rank 2 |
| 🥉 | Rank 3 |
| ⭐ | High AUC (≥ 0.90) |
| ⚡ | Fast training (<20s) |

### Use Cases

**After training multiple models**:
```bash
# Compare all models
cli-anything-unimol-tools -p project.json models rank
```

**Select best model for prediction**:
```bash
# Get best model ID
BEST=$(cli-anything-unimol-tools --json -p project.json models rank | \
       jq -r '.models[0].run_id')

# Run predictions with best model
cli-anything-unimol-tools -p project.json predict run $BEST test.csv
```

**Identify underperforming models**:
```bash
# Rank models
cli-anything-unimol-tools -p project.json models rank

# Delete models with status "Poor" or "Weak"
cli-anything-unimol-tools -p project.json cleanup --auto --min-auc=0.75
```

### JSON Output

For automation:
```bash
cli-anything-unimol-tools --json -p project.json models rank | jq
```

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
      "timestamp": "2024-01-15T12:34:56"
    },
    {
      "rank": 2,
      "run_id": "run_002",
      "score": 9.0,
      "auc": 0.8954,
      "duration_sec": 19.7,
      "status": "Good",
      "timestamp": "2024-01-14T10:20:30"
    }
  ],
  "recommendation": {
    "run_id": "run_003",
    "reason": "Highest AUC (0.9123)"
  }
}
```

---

## 3. Performance History

### Purpose

Visualize model performance trends over time to track experimental progress.

### Command

```bash
cli-anything-unimol-tools -p project.json models history
```

### What It Shows

**Timeline**:
- Chronological order of training runs
- AUC progression
- Training time evolution

**Trend Analysis**:
- **Improving**: Latest AUC > first AUC by 0.05+
- **Declining**: Latest AUC < first AUC by 0.05+
- **Stable**: Change < 0.05
- **Insufficient data**: < 2 models

**Insights**:
- Best model identification
- Performance improvements
- Recent performance drops (warnings)

### Example Output

```
📊 Model Performance History
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total runs: 5
Trend: improving

AUC Progress:
  run_001  (01/12) │███████████████████████████████████████ 0.7893
  run_002  (01/13) │████████████████████████████████████████████ 0.8123
  run_003  (01/14) │████████████████████████████████████████████ 0.8295
  run_004  (01/14) │████████████████████████████████████████████████ 0.8954
  run_005  (01/15) │████████████████████████████████████████████████ 0.9123

Training Time:
  run_001  (01/12) │█████████████████████ 16.3s
  run_002  (01/13) │██████████████████████ 17.1s
  run_003  (01/14) │██████████████████████████ 19.2s
  run_004  (01/14) │████████████████████████████ 19.7s
  run_005  (01/15) │██████████████████████████████████ 26.8s

💡 Insights:
   ✓ Best model: run_005 (AUC: 0.9123)
   ✓ Improving trend (+0.123 AUC over 5 runs)
   ⚠ Training time increasing (16.3s → 26.8s)
```

### Interpreting the Charts

**AUC Progress Chart**:
- Each bar represents one model
- Length = AUC value
- Longer bars = better performance
- Shows if you're making progress

**Training Time Chart**:
- Each bar represents training duration
- Helps identify if experiments are getting slower
- Useful for cost/performance tradeoffs

### Use Cases

**Track experimental progress**:
```bash
# After each training run
cli-anything-unimol-tools -p project.json train start --epochs 20
cli-anything-unimol-tools -p project.json models history
```

**Identify plateaus**:
```bash
# Check if performance is still improving
cli-anything-unimol-tools -p project.json models history

# If trend is "stable", might be time to:
# - Try different hyperparameters
# - Add more training data
# - Use a different architecture
```

**Performance regression detection**:
```bash
# Automatic check
TREND=$(cli-anything-unimol-tools --json -p project.json models history | \
        jq -r '.trend')

if [ "$TREND" = "declining" ]; then
  echo "⚠️  Warning: Performance declining!"
  echo "Last few models performed worse than earlier ones"
fi
```

---

## 4. Smart Cleanup

### Purpose

Intelligently identify and remove low-value models to save disk space while preserving important runs.

### Commands

**Interactive mode** (recommended first time):
```bash
cli-anything-unimol-tools -p project.json cleanup
```

**Automatic mode**:
```bash
cli-anything-unimol-tools -p project.json cleanup --auto [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--keep-best` | 3 | Number of top models to preserve |
| `--min-auc` | 0.75 | Minimum AUC threshold (below = delete) |
| `--max-age-days` | 7 | Keep recent models within N days |

### Cleanup Strategy

Models are categorized into three groups:

**1. Delete** (removed permanently):
- Low AUC < min_auc threshold
- Old (> max_age_days)
- Not in top N

**2. Archive** (compressed ~90%):
- Medium performance (AUC ≥ min_auc)
- Old (> max_age_days)
- Not in top N
- Might be useful later

**3. Keep** (unchanged):
- Top N best models by score
- Recent models (≤ max_age_days)
- Always preserves best performers

### Interactive Mode

**Example session**:
```
🧹 Model Cleanup Assistant
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found 6 models

🗑️  Suggested for deletion (2 models):
   • run_001: Low AUC (0.720 < 0.75) - saves 180MB
   • run_004: Low AUC (0.680 < 0.75) - saves 181MB

📦 Suggested for archival (1 model):
   • run_002: Old but decent (AUC: 0.820, 8 days old) - saves 163MB

✅ Will keep (3 models):
   • run_003: Top 3 model (rank 1, AUC: 0.912)
   • run_005: Top 3 model (rank 2, AUC: 0.895)
   • run_006: Recent (0 days old)

Potential savings: 524MB (96%)

Actions:
  1. Auto-clean (delete suggested, archive rest)
  2. Delete all suggested
  3. Archive all suggested
  4. Custom selection
  5. Cancel

Choose action [1-5]: 1

Confirm deletion of run_001, run_004? [yes/no]: yes

Processing...
  ✓ Deleted run_001 (180MB freed)
  ✓ Deleted run_004 (181MB freed)
  ✓ Archived run_002 → ~/.unimol-archive/ (163MB saved)

Total freed: 524MB

✓ Cleanup complete!
```

### Automatic Mode

**Examples**:

**Keep best 2 models**:
```bash
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=2
```

**Delete models with AUC < 0.80**:
```bash
cli-anything-unimol-tools -p project.json cleanup --auto --min-auc=0.80
```

**Aggressive cleanup (keep only #1)**:
```bash
cli-anything-unimol-tools -p project.json cleanup --auto \
  --keep-best=1 \
  --min-auc=0.85 \
  --max-age-days=3
```

**Conservative cleanup (keep more)**:
```bash
cli-anything-unimol-tools -p project.json cleanup --auto \
  --keep-best=5 \
  --min-auc=0.70 \
  --max-age-days=14
```

### Use Cases

**After hyperparameter sweep**:
```bash
# Train many configurations
for lr in 1e-5 5e-5 1e-4 5e-4; do
  cli-anything-unimol-tools -p project.json train start --learning-rate $lr
done

# Clean up, keep best 2
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=2
```

**Regular maintenance**:
```bash
# Weekly cleanup script
cli-anything-unimol-tools -p project.json cleanup --auto \
  --keep-best=3 \
  --min-auc=0.80
```

**Production deployment prep**:
```bash
# Keep only the absolute best model
cli-anything-unimol-tools -p project.json cleanup --auto \
  --keep-best=1 \
  --min-auc=0.90
```

---

## 5. Archive Management

### Purpose

Compress models to ~10% of original size (90% savings) without losing them permanently.

### Commands

**List archives**:
```bash
cli-anything-unimol-tools archive list
```

**Restore archived model**:
```bash
cli-anything-unimol-tools -p project.json archive restore RUN_ID
```

### How Archiving Works

**Compression**:
- Uses tar.gz compression
- Compresses model checkpoint, configs, metrics
- Typical: 180MB → 18MB (~90% reduction)

**Storage location**:
- Default: `~/.unimol-archive/`
- Organized by project name
- Format: `{project_name}_{run_id}.tar.gz`

**Safety**:
- Original model deleted only after successful archive
- Archive integrity verified before deletion

### List Archives

**Example**:
```bash
cli-anything-unimol-tools archive list
```

**Output**:
```
📦 Archived Models
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total: 4 archives
Location: ~/.unimol-archive/

  • drug_activity_run_002.tar.gz (18.2MB) - 2024-01-15 10:30
     Project: drug_activity, AUC: 0.8123

  • solubility_run_001.tar.gz (18.1MB) - 2024-01-14 08:20
     Project: solubility, MSE: 0.245

  • toxicity_run_003.tar.gz (18.3MB) - 2024-01-13 14:45
     Project: toxicity, AUC: 0.7945

  • properties_run_005.tar.gz (18.2MB) - 2024-01-12 16:10
     Project: properties, Metrics: multilabel

Total size: 72.8MB
Original size (estimated): 720MB
Space saved: 647MB (90%)

💡 Use 'archive restore RUN_ID' to restore an archive
```

### Restore Archive

**Example**:
```bash
cli-anything-unimol-tools -p drug_activity.json archive restore run_002
```

**Output**:
```
📦 Restoring Archive
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Archive: drug_activity_run_002.tar.gz
Location: ~/.unimol-archive/drug_activity_run_002.tar.gz
Compressed size: 18.2MB
Original size: 180.6MB

Extracting... ━━━━━━━━━━━━━━━━━━ 100%

✓ Restored: models/run_002/

Contents:
  • checkpoint.pth (179.3MB)
  • config.json (1.2KB)
  • metric.result (0.8KB)

✓ Model ready for use!

You can now:
  • Run predictions: predict run run_002 data.csv
  • View metrics: train info run_002
  • Re-archive: cleanup (will suggest archiving again if old)
```

### Use Cases

**Archive old experiments**:
```bash
# Interactive cleanup will suggest archiving
cli-anything-unimol-tools -p project.json cleanup

# Or manually via automatic mode
cli-anything-unimol-tools -p project.json cleanup --auto \
  --keep-best=2 \
  --max-age-days=7
```

**Restore for comparison**:
```bash
# Restore old model
cli-anything-unimol-tools -p project.json archive restore run_002

# Compare with current best
cli-anything-unimol-tools -p project.json models rank

# Run predictions with both
cli-anything-unimol-tools -p project.json predict run run_002 test.csv -o old.csv
cli-anything-unimol-tools -p project.json predict run run_005 test.csv -o new.csv
```

**Long-term storage**:
```bash
# Archive all but top 1
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=1

# List what's archived
cli-anything-unimol-tools archive list

# Backup archive directory
tar -czf backup_$(date +%Y%m%d).tar.gz ~/.unimol-archive/
```

---

## Workflow Examples

### Workflow 1: Experiment → Select → Deploy

```bash
# 1. Run multiple experiments
for epochs in 10 20 30; do
  cli-anything-unimol-tools -p project.json train start --epochs $epochs
done

# 2. Check results
cli-anything-unimol-tools -p project.json models history
cli-anything-unimol-tools -p project.json models rank

# 3. Select best model
BEST=$(cli-anything-unimol-tools --json -p project.json models rank | \
       jq -r '.models[0].run_id')

# 4. Clean up rest
cli-anything-unimol-tools -p project.json cleanup --auto --keep-best=1

# 5. Deploy
cli-anything-unimol-tools -p project.json predict run $BEST production_data.csv
```

### Workflow 2: Regular Maintenance

```bash
#!/bin/bash
# weekly_maintenance.sh

PROJECT="my_project.json"

echo "Weekly Maintenance Report"
echo "=========================="
echo ""

# Storage before
echo "Storage Before:"
cli-anything-unimol-tools -p $PROJECT storage
echo ""

# Cleanup
echo "Running cleanup..."
cli-anything-unimol-tools -p $PROJECT cleanup --auto \
  --keep-best=3 \
  --min-auc=0.80 \
  --max-age-days=14
echo ""

# Storage after
echo "Storage After:"
cli-anything-unimol-tools -p $PROJECT storage
echo ""

# Current best
echo "Current Best Model:"
cli-anything-unimol-tools -p $PROJECT models rank | head -n 5
```

### Workflow 3: Hyperparameter Tuning

```bash
#!/bin/bash
# hyperparam_sweep.sh

PROJECT="tuning.json"

# Grid search
for lr in 1e-5 5e-5 1e-4; do
  for bs in 8 16 32; do
    for dropout in 0.0 0.1 0.2; do
      echo "Training: LR=$lr BS=$bs Dropout=$dropout"

      cli-anything-unimol-tools -p $PROJECT train start \
        --epochs 20 \
        --learning-rate $lr \
        --batch-size $bs \
        --dropout $dropout

      # Check progress
      cli-anything-unimol-tools -p $PROJECT models history | tail -n 5
    done
  done
done

# Analyze results
echo "=== Final Results ==="
cli-anything-unimol-tools -p $PROJECT models rank

# Keep top 3, archive rest
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=3
```

---

## Best Practices

### 1. Monitor Storage Regularly

```bash
# Add to weekly routine
cli-anything-unimol-tools -p project.json storage
```

### 2. Clean Up After Experiments

```bash
# After hyperparameter sweep
cli-anything-unimol-tools -p project.json cleanup --auto
```

### 3. Use Ranking to Select Models

```bash
# Don't guess - use ranking
BEST=$(cli-anything-unimol-tools --json -p project.json models rank | \
       jq -r '.models[0].run_id')
```

### 4. Archive Instead of Delete

```bash
# When unsure, archive (can restore later)
cli-anything-unimol-tools -p project.json cleanup  # Interactive mode
# Choose "Archive" option
```

### 5. Track Trends

```bash
# Check if you're making progress
cli-anything-unimol-tools -p project.json models history
```

---

## Next Steps

- **Troubleshooting**: See [Troubleshooting Guide](05-TROUBLESHOOTING.md)
- **Training Workflows**: See [Training SOP](../workflows/TRAINING-SOP.md)
- **Cleanup Workflows**: See [Cleanup SOP](../workflows/CLEANUP-SOP.md)
- **Architecture**: See [Design Documentation](../architecture/DESIGN.md)
