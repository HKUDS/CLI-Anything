# Test Plan — cli-anything-cloudcompare

## Test Inventory Plan

| File | Purpose | Estimated Tests |
|------|---------|----------------|
| `test_core.py` | Unit tests — synthetic data, no CloudCompare required | 35 |
| `test_full_e2e.py` | E2E tests — real CloudCompare invocations + subprocess CLI tests | 20 |

---

## Unit Test Plan (`test_core.py`)

### Module: `core/project.py`

**Functions to test:**

- `create_project(output_path, name)` — creates valid JSON at path
- `load_project(path)` — loads and validates structure
- `save_project(project, path)` — persists with updated `modified_at`
- `add_cloud(project, path, label)` — appends cloud entry
- `add_mesh(project, path, label)` — appends mesh entry
- `remove_cloud(project, index)` — removes by index, returns entry
- `remove_mesh(project, index)` — removes by index
- `get_cloud(project, index)` — retrieves by index
- `get_mesh(project, index)` — retrieves by index
- `project_info(project)` — returns summary dict
- `record_operation(project, ...)` — appends to history

**Edge cases:**
- `load_project` on non-existent file → `FileNotFoundError`
- `load_project` on invalid JSON → `ValueError`
- `get_cloud` / `remove_cloud` with out-of-range index → `IndexError`
- `add_cloud` with non-existent path → `FileNotFoundError`
- `_locked_save_json` is atomic — file content after write is valid JSON

**Expected: ~18 tests**

### Module: `core/session.py`

**Functions to test:**

- `Session.__init__` — creates new project when file missing
- `Session.__init__` — loads existing project
- `Session.add_cloud` / `add_mesh`
- `Session.remove_cloud` / `remove_mesh`
- `Session.cloud_count` / `mesh_count` properties
- `Session.save()` — persists and clears dirty flag
- `Session.is_modified` — set after mutations, cleared after save
- `Session.history(n)` — returns last n entries
- `Session.undo_last()` — removes last history entry
- `Session.set_export_format` — updates settings dict
- `Session.status()` — returns dict with expected keys

**Edge cases:**
- `undo_last` with empty history → returns None
- `set_export_format` with None values → no-op on those fields

**Expected: ~17 tests**

### Module: `utils/cc_backend.py` (unit-level)

**Functions to test (logic only, no actual CC execution):**

- `find_cloudcompare()` — raises `RuntimeError` when not found (mocked)
- `CLOUD_FORMATS` mapping — all expected extensions present
- `MESH_FORMATS` mapping — all expected extensions present

**Expected: ~3 tests** (logic tests, CC not invoked)

---

## E2E Test Plan (`test_full_e2e.py`)

### Prerequisites
- CloudCompare must be installed (`flatpak run org.cloudcompare.CloudCompare`)
- Tests generate real output files and verify them

### Workflow 1: Format Conversion (LAS → PLY)

**Simulates:** Receiving a LAS scan and converting to PLY for downstream processing

**Operations:**
1. Generate a minimal valid XYZ/ASCII cloud file (synthetic data)
2. Convert to PLY using CloudCompare
3. Verify output: exists, size > 0, starts with "ply"

### Workflow 2: Subsampling Pipeline

**Simulates:** Thinning a dense scan to reduce size while preserving coverage

**Operations:**
1. Create a synthetic XYZ cloud (1000 points on a plane)
2. Subsample using SPATIAL method (min distance 0.1)
3. Verify output: exists, size > 0
4. Subsample using RANDOM method (count 50)
5. Verify output: exists, size > 0

### Workflow 3: Full Project Workflow (CLI subprocess)

**Simulates:** An agent building a processing pipeline via the installed CLI

**Operations:**
1. `cli-anything-cloudcompare project new -o test.json`  → verify JSON created
2. `--project test.json cloud add cloud.xyz` → verify cloud_count=1
3. `--project test.json cloud subsample 0 -o sub.xyz ...` → verify exists
4. `--project test.json project info --json` → verify JSON output
5. `--project test.json session history --json` → verify history recorded
6. `--project test.json export formats` → verify format list

### Workflow 4: SOR Filter (noise removal)

**Simulates:** Cleaning a noisy scan before analysis

**Operations:**
1. Create cloud with deliberately outlier points
2. Run SOR filter
3. Verify output: exists, size > 0, smaller than input (outliers removed)

### Workflow 5: CLI Subprocess (`TestCLISubprocess`)

All operations via the installed `cli-anything-cloudcompare` binary:
- `--help` → exit 0, contains "cloudcompare"
- `info --json` → valid JSON with `cloudcompare_available`
- `project new -o X` → valid project JSON
- `--json project info` → JSON with expected keys
- `cloud subsample` round-trip: new project → add cloud → subsample → verify output
- `export formats --json` → JSON with cloud/mesh keys

---

## Realistic Workflow Scenarios

### Scenario A: Survey Change Detection

**Simulates:** Comparing before/after scans of a construction site

```
project new → cloud add (before) → cloud add (after) → distance c2c → export
```

### Scenario B: Data Preparation Pipeline

**Simulates:** Preparing a raw scan for downstream use

```
project new → cloud add (raw) → filter-sor → subsample → convert (las→ply) → export
```

### Scenario C: ICP Registration

**Simulates:** Aligning two overlapping scans

```
project new → cloud add (A) → cloud add (B) → transform icp → export
```

---

## Test Results

**Run date:** 2026-03-28
**Environment:** Python 3.10.12, pytest 6.2.5, Linux 6.8.0
**CloudCompare:** v2.13.2 (Flatpak — `flatpak run org.cloudcompare.CloudCompare`)

### Summary

| Suite | Tests | Passed | Failed | Duration |
|-------|-------|--------|--------|----------|
| `test_core.py` (unit) | 49 | 49 | 0 | ~4s |
| `test_full_e2e.py` (E2E) | 39 | 39 | 0 | ~43s |
| **Total** | **88** | **88** | **0** | **42.62s** |

### Full Output

```
============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-6.2.5, py-1.10.0, pluggy-0.13.0
rootdir: /home/taeyoung/Desktop/mapping_agent/cloudcompare/agent-harness

cli_anything/cloudcompare/tests/test_core.py::TestCreateProject::test_creates_file PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCreateProject::test_returns_dict_with_expected_keys PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCreateProject::test_uses_provided_name PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCreateProject::test_derives_name_from_filename PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCreateProject::test_written_json_is_valid PASSED
cli_anything/cloudcompare/tests/test_core.py::TestLoadProject::test_loads_existing_project PASSED
cli_anything/cloudcompare/tests/test_core.py::TestLoadProject::test_raises_on_missing_file PASSED
cli_anything/cloudcompare/tests/test_core.py::TestLoadProject::test_raises_on_invalid_json_structure PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSaveProject::test_saves_and_updates_modified_at PASSED
cli_anything/cloudcompare/tests/test_core.py::TestAddCloud::test_adds_cloud_entry PASSED
cli_anything/cloudcompare/tests/test_core.py::TestAddCloud::test_uses_stem_as_default_label PASSED
cli_anything/cloudcompare/tests/test_core.py::TestAddCloud::test_uses_custom_label PASSED
cli_anything/cloudcompare/tests/test_core.py::TestAddCloud::test_raises_on_missing_file PASSED
cli_anything/cloudcompare/tests/test_core.py::TestAddMesh::test_adds_mesh_entry PASSED
cli_anything/cloudcompare/tests/test_core.py::TestAddMesh::test_raises_on_missing_file PASSED
cli_anything/cloudcompare/tests/test_core.py::TestRemoveCloud::test_removes_cloud_by_index PASSED
cli_anything/cloudcompare/tests/test_core.py::TestRemoveCloud::test_raises_on_out_of_range_index PASSED
cli_anything/cloudcompare/tests/test_core.py::TestRemoveCloud::test_raises_on_negative_index PASSED
cli_anything/cloudcompare/tests/test_core.py::TestGetCloud::test_returns_cloud_by_index PASSED
cli_anything/cloudcompare/tests/test_core.py::TestGetCloud::test_raises_on_invalid_index PASSED
cli_anything/cloudcompare/tests/test_core.py::TestProjectInfo::test_returns_summary PASSED
cli_anything/cloudcompare/tests/test_core.py::TestRecordOperation::test_appends_to_history PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_creates_new_project_when_missing PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_loads_existing_project PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_cloud_count_increments PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_mesh_count_increments PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_is_modified_after_add PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_is_not_modified_after_save PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_remove_cloud PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_get_cloud PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_history_recording PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_history_last_n PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_undo_last_removes_entry PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_undo_last_returns_none_when_empty PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_set_export_format PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_set_export_format_ignores_none PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_status_dict_keys PASSED
cli_anything/cloudcompare/tests/test_core.py::TestSession::test_repr_contains_path PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCCBackendConstants::test_cloud_formats_has_las PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCCBackendConstants::test_mesh_formats_has_obj PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCCBackendConstants::test_find_cloudcompare_raises_when_not_found PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCoordToSFValidation::test_invalid_dimension_raises PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCoordToSFValidation::test_invalid_dimension_in_filter_raises PASSED
cli_anything/cloudcompare/tests/test_core.py::TestNoiseFilterImport::test_noise_filter_importable PASSED
cli_anything/cloudcompare/tests/test_core.py::TestNoiseFilterImport::test_noise_filter_knn_mode PASSED
cli_anything/cloudcompare/tests/test_core.py::TestNoiseFilterImport::test_noise_filter_radius_mode PASSED
cli_anything/cloudcompare/tests/test_core.py::TestNoiseFilterImport::test_color_filter_removed PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCSFFilterValidation::test_invalid_scene_raises PASSED
cli_anything/cloudcompare/tests/test_core.py::TestCSFFilterValidation::test_valid_scenes_accepted PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestBackendAvailability::test_cloudcompare_is_installed PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestFormatConversion::test_xyz_to_ply PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestFormatConversion::test_xyz_to_las PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestSubsampling::test_spatial_subsample PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestSubsampling::test_random_subsample PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestSORFilter::test_sor_removes_outliers PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCSFFilter::test_csf_extracts_ground PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCSFFilter::test_csf_exports_both_layers PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCSFFilter::test_csf_cli_command PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestSFColorOps::test_sf_to_rgb PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestSFColorOps::test_rgb_to_sf PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestNoisePCLFilter::test_noise_filter_knn PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestNoisePCLFilter::test_noise_filter_radius PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestNoisePCLFilter::test_noise_filter_absolute PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestNormalsOps::test_invert_normals PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestDelaunayMesh::test_delaunay_creates_mesh PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestDelaunayMesh::test_delaunay_best_fit PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestDelaunayMesh::test_sample_mesh PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestApplyTransform::test_apply_identity_matrix PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestApplyTransform::test_apply_translation_matrix PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestSegmentCC::test_extract_two_components PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestExportPipeline::test_export_cloud_to_las PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestExportPipeline::test_export_cloud_to_ply PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestExportPipeline::test_export_raises_on_no_overwrite PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestExportPipeline::test_list_presets PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestProjectWorkflow::test_full_project_lifecycle PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_info_json PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_project_new_creates_file PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_project_info_json PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_cloud_add_and_list PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_export_formats_json PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_session_history_json PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_full_subsample_workflow PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_full_export_workflow PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_project_status_json PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_cloud_invert_normals_workflow PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_cloud_mesh_delaunay_workflow PASSED
cli_anything/cloudcompare/tests/test_full_e2e.py::TestCLISubprocess::test_transform_apply_workflow PASSED

============================== 88 passed in 42.62s =============================
```

### Notes

- `TestSORFilter::test_sor_removes_outliers`: CloudCompare appends a scalar field (deviation)
  column to ASC/XYZ output, making filtered files larger per-point in bytes even with fewer
  points. Test verifies point reduction via line count rather than file size.
- `TestCSFFilter`: CSF plugin (`libQCSF_PLUGIN.so`) is included in the Flatpak build.
  `-C_EXPORT_FMT` must precede `-CSF` in the argument list so the export format is set
  before CSF internally calls `exportEntity()`. Output filenames are auto-generated by CC
  as `{stem}_ground_points.{ext}` and detected via glob.
- `TestSFColorOps`: `-SF_CONVERT_TO_RGB` requires a boolean argument `TRUE` or `FALSE`
  after the command name (not documented; discovered by running CC and reading stdout).
  `rgb_to_sf` (`-RGB_CONVERT_TO_SF`) takes no extra argument.
- `TestNoisePCLFilter`: CloudCompare's CLI has no Gaussian/Bilateral spatial smoothing
  command. The original `-FILTER` command does not exist in v2.13.2. The PCL wrapper
  plugin's `-NOISE KNN {n} REL/ABS {noisiness}` command is the closest available
  spatial noise-removal operation via CLI. `color_filter()` was replaced by `noise_filter()`.
- `TestDelaunayMesh::test_sample_mesh`: `-SAMPLE_MESH` requires a mode keyword before the
  count: `-SAMPLE_MESH DENSITY {n}` or `-SAMPLE_MESH POINTS {n}`. Bare integer is invalid.
- `TestSegmentCC`: `-EXTRACT_CC` saves component files to the input file's directory (not
  cwd). Files are named `{stem}_COMPONENT_{n}.{ext}` (not `{stem}_CC_{n}`). When
  `output_fmt="xyz"` the CC format is `ASC` and files are saved with `.asc` extension;
  glob uses the actual CC format extension via an internal `_fmt_to_ext` mapping.
- `get_version()` uses `flatpak info org.cloudcompare.CloudCompare` instead of `--version`
  (CloudCompare does not support a `--version` flag).
- All subprocess tests run against the installed `cli-anything-cloudcompare` binary
  (`CLI_ANYTHING_FORCE_INSTALLED=1`), resolving to `/home/taeyoung/.local/bin/cli-anything-cloudcompare`.
