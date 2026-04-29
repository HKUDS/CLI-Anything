# Workflow Diagrams

Visual diagrams for common Uni-Mol Tools CLI workflows.

---

## Complete Training Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     START: Raw Data                                  │
│                     (SMILES + Labels)                                │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: Data Preparation                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  • Validate SMILES (RDKit)                                    │  │
│  │  • Remove duplicates                                          │  │
│  │  • Standardize structures                                     │  │
│  │  • Split: train (80%), valid (10%), test (10%)               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: Project Creation                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  $ cli-anything-unimol-tools project new \                    │  │
│  │      -n myproject -t classification                           │  │
│  │                                                                │  │
│  │  $ cli-anything-unimol-tools -p myproject.json \              │  │
│  │      project set-dataset train train.csv                      │  │
│  │  $ ... set-dataset valid valid.csv                            │  │
│  │  $ ... set-dataset test test.csv                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Output: myproject.json (project configuration)                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: Baseline Training                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  $ cli-anything-unimol-tools -p myproject.json \              │  │
│  │      train start --epochs 10 --batch-size 16                  │  │
│  │                                                                │  │
│  │  What happens:                                                 │  │
│  │  1. Generate 3D conformers (if not cached)                    │  │
│  │  2. Encode molecules with Uni-Mol                             │  │
│  │  3. Train classifier/regressor                                │  │
│  │  4. Evaluate on validation set                                │  │
│  │  5. Save checkpoint + metrics                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Output: models/run_001/ (checkpoint, metrics)                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: Evaluate Baseline                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  $ cli-anything-unimol-tools -p myproject.json models rank    │  │
│  │                                                                │  │
│  │  Result: AUC = 0.75 (needs improvement)                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
                    Decision Point
                           │
                ┌──────────┴──────────┐
                │                     │
         AUC < 0.80           AUC >= 0.80
    (Need tuning)           (Good enough)
                │                     │
                ▼                     ▼
┌───────────────────────────┐    ┌──────────────────┐
│  STEP 5a: Hyperparameter  │    │  STEP 5b: Deploy │
│  Tuning                   │    │                  │
│  ┌─────────────────────┐ │    │  Go to Step 7    │
│  │ • More epochs       │ │    └──────────────────┘
│  │ • Different LR      │ │
│  │ • Batch size        │ │
│  │ • Dropout           │ │
│  └─────────────────────┘ │
│                           │
│  Train 5-10 models        │
│  Compare results          │
└─────────────┬─────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 6: Select Best Model                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  $ cli-anything-unimol-tools -p myproject.json models rank    │  │
│  │  $ cli-anything-unimol-tools -p myproject.json models history │  │
│  │                                                                │  │
│  │  Criteria:                                                     │  │
│  │  • Highest validation AUC                                      │  │
│  │  • Stable performance                                          │  │
│  │  • Reasonable training time                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Selected: run_007 (AUC = 0.935)                                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 7: Test Set Evaluation                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  $ BEST=$(... models rank | jq -r '.models[0].run_id')        │  │
│  │  $ cli-anything-unimol-tools -p myproject.json \              │  │
│  │      predict run $BEST test.csv -o test_predictions.csv       │  │
│  │                                                                │  │
│  │  Analyze:                                                      │  │
│  │  • Calculate test AUC                                          │  │
│  │  • Check confusion matrix                                      │  │
│  │  • Plot ROC curve                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Test AUC = 0.923 (production ready!)                               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 8: Cleanup                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  $ cli-anything-unimol-tools -p myproject.json cleanup \      │  │
│  │      --auto --keep-best=2                                      │  │
│  │                                                                │  │
│  │  • Keep run_007 (best model)                                   │  │
│  │  • Keep run_006 (backup)                                       │  │
│  │  • Archive run_003, run_004                                    │  │
│  │  • Delete run_001, run_002 (poor performance)                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Storage: 912MB → 360MB (saved 552MB)                               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 9: Production Deployment                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  $ cli-anything-unimol-tools -p myproject.json predict run \  │  │
│  │      run_007 new_compounds.csv -o predictions.csv              │  │
│  │                                                                │  │
│  │  Monitor:                                                      │  │
│  │  • Prediction distribution                                     │  │
│  │  • Performance over time                                       │  │
│  │  • Retrain with new data periodically                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
                     ┌─────────────┐
                     │   SUCCESS   │
                     └─────────────┘
```

---

## Interactive Storage Management Workflow

```
┌──────────────────┐
│ Check Storage    │
└────────┬─────────┘
         │
         ▼
    $ cli-anything-unimol-tools -p project.json storage
         │
         ▼
┌──────────────────────────────────────────┐
│ Output:                                   │
│ Total Usage: 912MB                        │
│   Models: 900MB (98.7%)                   │
│   Conformers: 12MB (1.3%)                 │
│                                           │
│ ⚠️  Recommendations:                      │
│  • 8 models > 7 days old (save 720MB)    │
│  • Potential savings: 720MB (79%)        │
└─────────────────┬────────────────────────┘
                  │
                  ▼
          High usage (>500MB)?
                  │
         ┌────────┴────────┐
         │                 │
        Yes               No
         │                 │
         ▼                 ▼
┌──────────────────┐  ┌──────────────┐
│ Cleanup Needed   │  │ Keep as is   │
└────────┬─────────┘  └──────────────┘
         │
         ▼
    $ cli-anything-unimol-tools -p project.json models rank
         │
         ▼
┌──────────────────────────────────────────┐
│ Ranking:                                  │
│ 🥇 run_010: 9.4/10 (AUC 0.94)            │
│ 🥈 run_009: 9.1/10 (AUC 0.91)            │
│ 🥉 run_008: 8.9/10 (AUC 0.89)            │
│ ... (7 more)                              │
└─────────────────┬────────────────────────┘
                  │
                  ▼
    $ cli-anything-unimol-tools -p project.json cleanup
         │
         ▼
┌──────────────────────────────────────────┐
│ Cleanup Assistant                         │
│                                           │
│ 🗑️  Delete (3 models):                   │
│   • run_001: Low AUC (0.72)              │
│   • run_002: Low AUC (0.68)              │
│   • run_003: Low AUC (0.74)              │
│                                           │
│ 📦 Archive (5 models):                    │
│   • run_004-008: Old but decent          │
│                                           │
│ ✅ Keep (2 models):                       │
│   • run_009: Rank 2                       │
│   • run_010: Rank 1 (best)                │
│                                           │
│ Potential savings: 720MB (79%)            │
│                                           │
│ Actions:                                  │
│   1. Auto-clean (recommended)             │
│   2. Delete all suggested                 │
│   3. Archive all suggested                │
│   4. Cancel                               │
│                                           │
│ Choose [1-4]:                             │
└─────────────────┬────────────────────────┘
                  │
                  ▼
         User selects: 1
                  │
                  ▼
┌──────────────────────────────────────────┐
│ Executing Cleanup...                      │
│                                           │
│ Deleting:                                 │
│   ✓ run_001 (180MB freed)                │
│   ✓ run_002 (180MB freed)                │
│   ✓ run_003 (180MB freed)                │
│                                           │
│ Archiving:                                │
│   ✓ run_004 → archive (162MB saved)      │
│   ✓ run_005 → archive (162MB saved)      │
│   ... (3 more)                            │
│                                           │
│ Keeping:                                  │
│   • run_009 (180MB)                       │
│   • run_010 (180MB)                       │
│                                           │
│ Total freed: 720MB                        │
└─────────────────┬────────────────────────┘
                  │
                  ▼
    $ cli-anything-unimol-tools -p project.json storage
         │
         ▼
┌──────────────────────────────────────────┐
│ After Cleanup:                            │
│ Total Usage: 192MB                        │
│   Models: 180MB (93.8%)                   │
│   Conformers: 12MB (6.2%)                 │
│                                           │
│ ✓ Storage optimized!                     │
└──────────────────────────────────────────┘
```

---

## Conformer Caching Flow

```
                 First Training Run
                         │
                         ▼
┌────────────────────────────────────────────────┐
│  Input: train.csv (1000 molecules)             │
│  SMILES: CC(C)Cc1ccc, CCN(CC)C(=O), ...        │
└──────────────────────┬─────────────────────────┘
                       │
                       ▼
            conf-cache-level = 1 (default)
                       │
                       ▼
┌────────────────────────────────────────────────┐
│  Check: conformers/ directory                  │
│                                                 │
│  For each SMILES:                               │
│    hash = MD5(SMILES)                           │
│    file = conformers/{hash}.sdf                 │
│                                                 │
│    if file exists:                              │
│      ✓ Load from cache (fast)                  │
│    else:                                        │
│      ⏳ Generate 3D conformer (slow)            │
│      💾 Save to conformers/{hash}.sdf           │
└──────────────────────┬─────────────────────────┘
                       │
                       ▼
        Conformer Cache Status
                       │
         ┌─────────────┴─────────────┐
         │                           │
    New molecules              Existing molecules
    (not cached)                  (cached)
         │                           │
         ▼                           ▼
   ⏱ 10-30 sec/molecule        ⚡ <0.1 sec/molecule
   Generate + encode             Just encode
         │                           │
         └─────────────┬─────────────┘
                       │
                       ▼
             Training proceeds...
                       │
                       ▼
┌────────────────────────────────────────────────┐
│  Result:                                        │
│  • conformers/: 1000 SDF files (~12MB)         │
│  • models/run_001/: checkpoint + metrics       │
└──────────────────────┬─────────────────────────┘
                       │
                       ▼
              Subsequent Training Runs
                       │
                       ▼
┌────────────────────────────────────────────────┐
│  Same dataset + conformer cache exists         │
│                                                 │
│  Check conformers/:                             │
│    ✓ All 1000 molecules found in cache         │
│    ⚡ Load all conformers (fast)                │
│                                                 │
│  Training time:                                 │
│    Run 1: 5 min (generate conformers)          │
│    Run 2: 2 min (reuse conformers) ⚡           │
│    Run 3: 2 min (reuse conformers) ⚡           │
└────────────────────────────────────────────────┘
```

**Cache Levels**:
- `0`: No caching (regenerate every time, slowest)
- `1`: Smart caching (generate once, reuse, **default**)
- `2`: Strict reuse (only use cache, fail if missing)

---

## Model Lifecycle

```
┌───────────────┐
│   Created     │  train start
│  (run_001)    │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│   Training    │  Epochs running
│  (in progress)│
└───────┬───────┘
        │
        ├─────> [Failed] → Delete or debug
        │
        ▼
┌───────────────┐
│   Trained     │  Checkpoint saved
│ (AUC = 0.85)  │  Metrics recorded
└───────┬───────┘
        │
        ├─────────────────┐
        │                 │
        ▼                 ▼
  Performance      Performance
    Good              Poor
  (AUC ≥ 0.80)    (AUC < 0.75)
        │                 │
        ▼                 ▼
┌───────────────┐   ┌──────────────┐
│  Production   │   │   Archived   │
│  (deployed)   │   │  or Deleted  │
└───────┬───────┘   └──────────────┘
        │
        ├─────> [Predict] → predictions.csv
        │
        ├─────> [Monitor] → performance tracking
        │
        ├─────> [Update] → retrain with new data
        │
        ▼
┌───────────────┐
│   Replaced    │  New model deployed
│  (archived)   │  Old model archived
└───────────────┘
```

---

## Prediction Pipeline

```
New Compounds
     │
     ▼
┌──────────────────────────────────┐
│ Input: compounds.csv              │
│ SMILES,name                       │
│ CC(C)Cc1ccc,compound_A            │
│ CCN(CC)C(=O),compound_B           │
│ ...                               │
└────────────┬─────────────────────┘
             │
             ▼
    $ cli-anything-unimol-tools -p project.json \
        predict run run_007 compounds.csv -o predictions.csv
             │
             ▼
┌──────────────────────────────────┐
│ 1. Load model checkpoint          │
│    models/run_007/checkpoint.pth  │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│ 2. For each SMILES:               │
│    • Generate 3D conformer        │
│      (use cache if available)     │
│    • Encode with Uni-Mol          │
│    • Run inference                │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│ 3. Post-process predictions       │
│    Classification:                │
│      • Probabilities → labels     │
│      • Threshold = 0.5            │
│    Regression:                    │
│      • Direct output              │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│ Output: predictions.csv           │
│ SMILES,prediction,probability     │
│ CC(C)Cc1ccc,1,0.87                │
│ CCN(CC)C(=O),0,0.23               │
│ ...                               │
└───────────────────────────────────┘
```

---

## Archive and Restore Flow

```
Model Cleanup Decision
         │
   ┌─────┴─────┐
   │           │
Archive      Delete
   │           │
   ▼           ▼
┌──────────────────────────┐    ┌──────────────┐
│ Archive Process           │    │ Delete       │
│                           │    │ (permanent)  │
│ 1. Create tar.gz          │    └──────────────┘
│    ┌─────────────────┐   │
│    │ run_002/        │   │
│    │ ├─checkpoint.pth│   │
│    │ ├─config.json   │   │
│    │ └─metric.result │   │
│    └─────────────────┘   │
│           │               │
│           ▼               │
│    Compress (tar + gzip)  │
│           │               │
│           ▼               │
│    ┌─────────────────┐   │
│    │ project_run002  │   │
│    │ .tar.gz         │   │
│    │ 18MB (90% saved)│   │
│    └─────────────────┘   │
│           │               │
│           ▼               │
│ 2. Save to archive dir    │
│    ~/.unimol-archive/     │
│                           │
│ 3. Delete original        │
│    models/run_002/        │
└───────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Archive Storage           │
│ ~/.unimol-archive/        │
│ ├─ proj1_run002.tar.gz   │
│ ├─ proj2_run001.tar.gz   │
│ └─ ...                    │
└───────────┬───────────────┘
            │
            │ Need model back?
            ▼
┌──────────────────────────┐
│ Restore Process           │
│                           │
│ $ cli-anything-unimol    │
│     -tools -p project.json│
│     archive restore       │
│     run_002               │
│                           │
│ 1. Find archive           │
│    proj_run002.tar.gz     │
│                           │
│ 2. Extract                │
│    Decompress → models/   │
│                           │
│ 3. Verify                 │
│    Check checkpoint.pth   │
│                           │
│ ✓ Model ready to use      │
└───────────────────────────┘
```

---

## Batch Processing Workflow

```
Multiple Projects
      │
      ├─ project1.json (classification)
      ├─ project2.json (regression)
      └─ project3.json (multiclass)
      │
      ▼
┌─────────────────────────────────┐
│ Batch Script                     │
│ #!/bin/bash                      │
│                                  │
│ for project in projects/*.json   │
│ do                               │
│   echo "Processing $project"     │
│                                  │
│   # Check storage                │
│   cli-anything-unimol-tools \    │
│     -p "$project" storage        │
│                                  │
│   # Cleanup if needed            │
│   if [ $USAGE -gt 500 ]; then    │
│     cli-anything-unimol-tools \  │
│       -p "$project" cleanup \    │
│       --auto --keep-best=2       │
│   fi                             │
│                                  │
│   # Get best model               │
│   BEST=$(... models rank ...)    │
│                                  │
│   # Run predictions              │
│   cli-anything-unimol-tools \    │
│     -p "$project" predict run \  │
│     $BEST new_data.csv -o \      │
│     "results/${project%.json}.csv"│
│ done                             │
└─────────────────────────────────┘
         │
         ▼
   Results for all projects
```

---

## Decision Tree: When to Use Each Feature

```
                    What do you need?
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    Check storage    Manage models    Run predictions
          │                │                │
          ▼                ▼                ▼
    ┌─────────┐      ┌─────────┐      ┌──────────┐
    │ storage │      │ models  │      │ predict  │
    │ command │      │ commands│      │  run     │
    └─────────┘      └─────┬───┘      └──────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
       Which model?    Performance   Too many
       to use?         over time?    models?
            │              │              │
            ▼              ▼              ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │  rank    │   │ history  │   │ cleanup  │
      └──────────┘   └──────────┘   └──────────┘
```

---

## Summary

These diagrams illustrate:
1. **Complete Training Workflow** - End-to-end process
2. **Storage Management** - Interactive cleanup flow
3. **Conformer Caching** - How caching speeds up training
4. **Model Lifecycle** - States from creation to deployment
5. **Prediction Pipeline** - How predictions are generated
6. **Archive/Restore** - Model archival and recovery
7. **Batch Processing** - Automating multiple projects
8. **Decision Tree** - Which feature to use when

---

## Next Steps

- **Training SOP**: [TRAINING-SOP.md](TRAINING-SOP.md)
- **Cleanup SOP**: [CLEANUP-SOP.md](CLEANUP-SOP.md)
- **Architecture**: [../architecture/DESIGN.md](../architecture/DESIGN.md)
- **Interactive Features**: [../guides/04-INTERACTIVE-FEATURES.md](../guides/04-INTERACTIVE-FEATURES.md)
