# Cleanup Workflow SOP

Standard Operating Procedure for managing model storage and cleanup in Uni-Mol Tools CLI.

---

## Overview

This SOP provides guidelines for managing disk space and cleaning up experimental models.

**Key Principles**:
- Keep only valuable models
- Archive before deleting
- Regular maintenance prevents bloat
- Document what you keep

**When to Clean Up**:
- After hyperparameter sweeps
- Weekly/monthly maintenance
- Before deploying to production
- When disk space is low

---

## Cleanup Workflow Diagram

```
┌──────────────────┐
│ Check Storage    │
│  - Total usage   │
│  - Per-model size│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Identify Models  │
│  - Rank by AUC   │
│  - Check age     │
│  - Review history│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Categorize       │
│  - Keep (best)   │
│  - Archive (ok)  │
│  - Delete (poor) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Execute Cleanup  │◄───────┐
│  - Interactive   │        │
│  - or Automatic  │        │
└────────┬─────────┘        │
         │                  │
         ▼                  │
┌──────────────────┐        │
│ Review Results   │        │
│  - Space freed   │        │
│  - Models kept   │────────┘
└────────┬─────────┘  Rollback if needed
         │
         ▼
┌──────────────────┐
│ Document         │
│  - What kept     │
│  - Why deleted   │
│  - Space saved   │
└──────────────────┘
```

---

## Stage 1: Assess Current State

### 1.1 Check Storage Usage

```bash
PROJECT="myproject.json"

# View storage breakdown
cli-anything-unimol-tools -p $PROJECT storage
```

**Look for**:
- Total storage usage
- Number of models
- Old models (> 7 days)
- Duplicate conformer files

### 1.2 Review Model Performance

```bash
# Rank all models
cli-anything-unimol-tools -p $PROJECT models rank

# View performance history
cli-anything-unimol-tools -p $PROJECT models history
```

**Identify**:
- Best performing models (keep these)
- Poor performing models (candidates for deletion)
- Redundant models (similar performance)

### 1.3 Document Current State

```bash
# Create snapshot
cat > cleanup_$(date +%Y%m%d).log << EOF
Cleanup Assessment - $(date)
================================

Project: $PROJECT

Storage Before:
$(cli-anything-unimol-tools -p $PROJECT storage)

Model Ranking:
$(cli-anything-unimol-tools -p $PROJECT models rank)
EOF
```

---

## Stage 2: Define Cleanup Strategy

### 2.1 Determine What to Keep

**Default Strategy**:
- Keep top 3 models by performance
- Keep models from last 7 days
- Keep models with AUC > 0.80 (for classification)

**Conservative Strategy** (keep more):
- Keep top 5 models
- Keep models from last 14 days
- Keep models with AUC > 0.75

**Aggressive Strategy** (keep less):
- Keep top 1 model only
- Keep models from last 3 days
- Keep models with AUC > 0.85

### 2.2 Set Parameters

```bash
# Default strategy
KEEP_BEST=3
MIN_AUC=0.80
MAX_AGE_DAYS=7

# Conservative
KEEP_BEST=5
MIN_AUC=0.75
MAX_AGE_DAYS=14

# Aggressive
KEEP_BEST=1
MIN_AUC=0.85
MAX_AGE_DAYS=3
```

---

## Stage 3: Execute Cleanup

### 3.1 Interactive Cleanup (Recommended First Time)

```bash
# Interactive mode - see recommendations before committing
cli-anything-unimol-tools -p $PROJECT cleanup
```

**Process**:
1. CLI shows categorized models (delete/archive/keep)
2. Shows potential space savings
3. Prompts for action choice
4. Asks for confirmation before executing

**Choose action**:
- **Option 1**: Auto-clean (delete suggested, archive rest) - Recommended
- **Option 2**: Delete all suggested - Aggressive
- **Option 3**: Archive all suggested - Conservative
- **Option 4**: Custom selection - Manual control
- **Option 5**: Cancel - Abort

### 3.2 Automatic Cleanup

```bash
# Automatic with default strategy
cli-anything-unimol-tools -p $PROJECT cleanup --auto \
  --keep-best=3 \
  --min-auc=0.80 \
  --max-age-days=7
```

**Use automatic when**:
- Strategy is well-defined
- Running in scripts/cron jobs
- Confident in parameters

### 3.3 Dry Run (Preview Only)

```bash
# See what would be cleaned without executing
cli-anything-unimol-tools -p $PROJECT cleanup --dry-run
```

**Note**: `--dry-run` is not currently implemented but would show recommendations without executing.

---

## Stage 4: Archive Management

### 4.1 Review Archives

```bash
# List all archived models
cli-anything-unimol-tools archive list
```

**Check**:
- Archive location (~/.unimol-archive/)
- Archive sizes
- Archive dates

### 4.2 Restore if Needed

```bash
# If you need a model back
cli-anything-unimol-tools -p $PROJECT archive restore run_002
```

### 4.3 Backup Archives (Optional)

```bash
# Backup archive directory to safe location
tar -czf backups/archives_$(date +%Y%m%d).tar.gz ~/.unimol-archive/

# Or sync to remote storage
rsync -av ~/.unimol-archive/ user@backup-server:/backups/unimol-archives/
```

---

## Stage 5: Verify Results

### 5.1 Check Storage After Cleanup

```bash
# View storage again
cli-anything-unimol-tools -p $PROJECT storage

# Compare with before
echo "Storage freed: XYZ MB"
```

### 5.2 Verify Models Kept

```bash
# List remaining models
cli-anything-unimol-tools -p $PROJECT project info

# Ensure best model still present
cli-anything-unimol-tools -p $PROJECT models rank | head -n 5
```

### 5.3 Document Results

```bash
# Append to log
cat >> cleanup_$(date +%Y%m%d).log << EOF

Storage After:
$(cli-anything-unimol-tools -p $PROJECT storage)

Models Kept:
$(cli-anything-unimol-tools -p $PROJECT project info | grep "Models:")

Action Taken:
- Deleted: X models
- Archived: Y models
- Kept: Z models
- Space freed: ABC MB
EOF
```

---

## Automated Cleanup Schedules

### Weekly Cleanup Script

```bash
#!/bin/bash
# weekly_cleanup.sh

PROJECT="production.json"

echo "=== Weekly Cleanup - $(date) ==="

# Before
echo "Before:"
cli-anything-unimol-tools -p $PROJECT storage

# Cleanup (keep best 3, AUC > 0.80, < 7 days)
cli-anything-unimol-tools -p $PROJECT cleanup --auto \
  --keep-best=3 \
  --min-auc=0.80 \
  --max-age-days=7

# After
echo ""
echo "After:"
cli-anything-unimol-tools -p $PROJECT storage

# Archive list
echo ""
echo "Current Archives:"
cli-anything-unimol-tools archive list
```

**Setup cron** (every Sunday at 2am):
```bash
0 2 * * 0 /path/to/weekly_cleanup.sh >> /var/log/unimol_cleanup.log 2>&1
```

### Monthly Deep Clean

```bash
#!/bin/bash
# monthly_deep_clean.sh

PROJECT="production.json"

echo "=== Monthly Deep Clean - $(date) ==="

# More aggressive cleanup
cli-anything-unimol-tools -p $PROJECT cleanup --auto \
  --keep-best=2 \
  --min-auc=0.85 \
  --max-age-days=5

# Clean old archives (older than 90 days)
find ~/.unimol-archive/ -name "*.tar.gz" -mtime +90 -exec rm {} \;

echo "Deep clean complete"
```

---

## Best Practices

### 1. Never Delete Without Looking

```bash
# Always check what will be deleted first
cli-anything-unimol-tools -p $PROJECT cleanup  # Interactive mode

# Or review storage and ranking before automatic cleanup
cli-anything-unimol-tools -p $PROJECT storage
cli-anything-unimol-tools -p $PROJECT models rank
```

### 2. Archive Before Delete

**Preference order**:
1. **Archive** - Compress and save (90% space savings, recoverable)
2. **Delete** - Only for clearly poor models

```bash
# When unsure, archive
# Choose "Archive all suggested" in interactive mode
```

### 3. Keep Production Model

```bash
# Always keep the model currently in production
# Tag it in documentation or naming

# Example: Keep run_005 (production model)
# Set keep-best high enough to include it
```

### 4. Document Decisions

```bash
# Keep cleanup log
mkdir -p logs/cleanup/

# Each cleanup session
DATE=$(date +%Y%m%d)
cli-anything-unimol-tools -p $PROJECT storage > logs/cleanup/before_$DATE.txt
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=3
cli-anything-unimol-tools -p $PROJECT storage > logs/cleanup/after_$DATE.txt

# Document reasoning
cat > logs/cleanup/notes_$DATE.txt << EOF
Kept:
- run_005: Production model (AUC 0.923)
- run_007: Best overall (AUC 0.935)
- run_008: Recent experiment (0 days old)

Archived:
- run_003: Old but decent (AUC 0.812)
- run_004: Backup model (AUC 0.801)

Deleted:
- run_001, run_002: Low AUC < 0.75
EOF
```

### 5. Test Restore Process

```bash
# Periodically verify archives work
cli-anything-unimol-tools archive list

# Test restore
cli-anything-unimol-tools -p test_project.json archive restore run_002

# Verify restored model works
cli-anything-unimol-tools -p test_project.json predict run run_002 test.csv -o out.csv

# Clean up test
rm -rf models/run_002
```

---

## Common Scenarios

### Scenario 1: After Hyperparameter Sweep

**Situation**: Trained 50 models with different hyperparameters

**Action**:
```bash
# Keep top 3, delete rest
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=3

# Or keep top 5 if performance is close
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=5
```

### Scenario 2: Low Disk Space Emergency

**Situation**: Disk almost full, need space immediately

**Action**:
```bash
# Aggressive cleanup - keep only best model
cli-anything-unimol-tools -p $PROJECT cleanup --auto \
  --keep-best=1 \
  --min-auc=0.90

# Delete conformer cache if not needed
rm -rf conformers/

# Check space freed
df -h .
```

### Scenario 3: Project Archival

**Situation**: Project completed, need to archive everything

**Action**:
```bash
PROJECT="completed_project.json"

# Keep only best model
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=1

# Archive entire project
tar -czf completed_project_$(date +%Y%m%d).tar.gz \
  $PROJECT \
  models/ \
  predictions/ \
  conformers/

# Move to long-term storage
mv completed_project_*.tar.gz /archive/completed_projects/

# Clean up working directory
rm -rf models/ conformers/ predictions/
```

### Scenario 4: Pre-Production Deployment

**Situation**: Deploying to production, clean up experiments

**Action**:
```bash
# 1. Identify production model
PROD_MODEL="run_007"  # Best validated model

# 2. Document
echo "Production Model: $PROD_MODEL (AUC 0.935)" > PRODUCTION_MODEL.txt

# 3. Keep production + backup
cli-anything-unimol-tools -p $PROJECT cleanup --auto --keep-best=2

# 4. Verify production model still present
cli-anything-unimol-tools -p $PROJECT project info | grep $PROD_MODEL

# 5. Test production model
cli-anything-unimol-tools -p $PROJECT predict run $PROD_MODEL validation.csv -o val_preds.csv
```

---

## Rollback Procedures

### If Deleted Wrong Model

**If not archived**:
- Model is permanently lost
- Retrain from scratch
- **Prevention**: Always use interactive mode first

**If archived**:
```bash
# Restore from archive
cli-anything-unimol-tools -p $PROJECT archive restore run_002

# Verify restored
ls models/run_002/
cli-anything-unimol-tools -p $PROJECT project info
```

### If Cleanup Was Too Aggressive

```bash
# Restore all recent archives
cli-anything-unimol-tools archive list

# Restore needed models
cli-anything-unimol-tools -p $PROJECT archive restore run_003
cli-anything-unimol-tools -p $PROJECT archive restore run_004

# Re-evaluate strategy
cli-anything-unimol-tools -p $PROJECT models rank
```

---

## Cleanup Checklist

Before cleanup:
- [ ] Check current storage usage
- [ ] Review model rankings
- [ ] Identify production model (if any)
- [ ] Document current state
- [ ] Choose cleanup strategy

During cleanup:
- [ ] Use interactive mode (first time)
- [ ] Review recommendations
- [ ] Verify what will be deleted/archived
- [ ] Confirm production model is preserved
- [ ] Execute cleanup

After cleanup:
- [ ] Verify storage freed
- [ ] Check remaining models
- [ ] Test best model still works
- [ ] Document what was kept/deleted
- [ ] Update production notes if needed

---

## Troubleshooting

### Issue: Cleanup deletes everything

**Cause**: Too aggressive parameters

**Prevention**:
```bash
# Use interactive mode first
cli-anything-unimol-tools -p $PROJECT cleanup

# Review before confirming
```

### Issue: Can't restore archive

**Cause**: Archive corrupted or deleted

**Prevention**:
```bash
# Backup archives regularly
tar -czf archive_backup_$(date +%Y%m%d).tar.gz ~/.unimol-archive/
```

### Issue: Storage not decreasing after cleanup

**Cause**: Conformer cache still present

**Solution**:
```bash
# Check conformer size
du -sh conformers/

# Delete if not needed
rm -rf conformers/
```

---

## Summary

**Key Takeaways**:
1. **Check before clean** - Use `storage` and `rank` commands
2. **Archive first** - Archive before deleting when unsure
3. **Keep best models** - Always preserve top performers
4. **Document decisions** - Record what you kept and why
5. **Test restores** - Verify archives work periodically
6. **Automate routine cleanup** - Weekly/monthly scripts
7. **Never delete production model** - Tag and protect

**Recommended Cleanup Frequency**:
- **After experiments**: Immediate (keep top 3-5)
- **Weekly**: Routine cleanup (keep best 3, < 7 days)
- **Monthly**: Deep clean (keep best 2, < 5 days, AUC > 0.85)
- **Before deployment**: Final cleanup (keep production + 1 backup)

---

## Next Steps

- **Training SOP**: [TRAINING-SOP.md](TRAINING-SOP.md)
- **Interactive Features**: [../guides/04-INTERACTIVE-FEATURES.md](../guides/04-INTERACTIVE-FEATURES.md)
- **Storage Analysis**: [../guides/03-BASIC-USAGE.md#storage-analysis](../guides/03-BASIC-USAGE.md)
- **Workflow Diagrams**: [DIAGRAMS.md](DIAGRAMS.md)
