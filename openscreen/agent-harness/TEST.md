# Openscreen CLI — Test Results

## Summary

- **Total tests**: 101
- **Passed**: 101
- **Failed**: 0
- **Test suites**: 2 (unit + end-to-end)

## Test Suites

### test_core.py — Unit Tests (78 tests, no ffmpeg required)

| # | Test | Status |
|---|------|--------|
| 1 | TestSession::test_new_session | PASSED |
| 2 | TestSession::test_new_session_with_id | PASSED |
| 3 | TestSession::test_new_project | PASSED |
| 4 | TestSession::test_new_project_with_video | PASSED |
| 5 | TestSession::test_undo_redo | PASSED |
| 6 | TestSession::test_undo_clears_redo | PASSED |
| 7 | TestSession::test_save_load_project | PASSED |
| 8 | TestSession::test_open_nonexistent | PASSED |
| 9 | TestSession::test_save_without_path | PASSED |
| 10 | TestSession::test_status | PASSED |
| 11 | TestSession::test_editor_raises_when_not_open | PASSED |
| 12 | TestSession::test_checkpoint_adds_to_undo | PASSED |
| 13 | TestSession::test_undo_stack_limit_50 | PASSED |
| 14 | TestSession::test_is_modified_after_checkpoint | PASSED |
| 15 | TestSession::test_open_invalid_json_raises | PASSED |
| 16 | TestProject::test_new_project | PASSED |
| 17 | TestProject::test_info | PASSED |
| 18 | TestProject::test_info_without_project | PASSED |
| 19 | TestProject::test_set_setting | PASSED |
| 20 | TestProject::test_set_invalid_setting | PASSED |
| 21 | TestProject::test_set_aspect_ratio_valid | PASSED |
| 22 | TestProject::test_set_aspect_ratio_invalid | PASSED |
| 23 | TestProject::test_set_export_quality_valid | PASSED |
| 24 | TestProject::test_set_export_quality_invalid | PASSED |
| 25 | TestProject::test_set_export_format_valid | PASSED |
| 26 | TestProject::test_set_export_format_invalid | PASSED |
| 27 | TestProject::test_set_padding_valid | PASSED |
| 28 | TestProject::test_set_padding_invalid | PASSED |
| 29 | TestProject::test_set_shadow_intensity_range | PASSED |
| 30 | TestProject::test_set_border_radius_negative | PASSED |
| 31 | TestZoom::test_add_zoom | PASSED |
| 32 | TestZoom::test_list_zoom | PASSED |
| 33 | TestZoom::test_remove_zoom | PASSED |
| 34 | TestZoom::test_remove_nonexistent_zoom | PASSED |
| 35 | TestZoom::test_invalid_depth | PASSED |
| 36 | TestZoom::test_invalid_focus | PASSED |
| 37 | TestZoom::test_invalid_time_range | PASSED |
| 38 | TestZoom::test_zoom_undo | PASSED |
| 39 | TestZoom::test_add_zoom_with_focus | PASSED |
| 40 | TestZoom::test_list_zoom_sorted | PASSED |
| 41 | TestZoom::test_update_zoom_region | PASSED |
| 42 | TestZoom::test_depth_map_values | PASSED |
| 43 | TestZoom::test_add_zoom_calls_checkpoint | PASSED |
| 44 | TestSpeed::test_add_speed | PASSED |
| 45 | TestSpeed::test_invalid_speed | PASSED |
| 46 | TestSpeed::test_list_and_remove | PASSED |
| 47 | TestSpeed::test_all_valid_speed_values | PASSED |
| 48 | TestSpeed::test_list_speed_sorted | PASSED |
| 49 | TestSpeed::test_remove_speed_nonexistent | PASSED |
| 50 | TestTrim::test_add_trim | PASSED |
| 51 | TestTrim::test_list_and_remove | PASSED |
| 52 | TestTrim::test_add_trim_zero_start | PASSED |
| 53 | TestTrim::test_list_trim_sorted | PASSED |
| 54 | TestTrim::test_remove_trim_nonexistent | PASSED |
| 55 | TestCrop::test_default_crop | PASSED |
| 56 | TestCrop::test_set_crop | PASSED |
| 57 | TestCrop::test_invalid_crop | PASSED |
| 58 | TestCrop::test_crop_out_of_bounds | PASSED |
| 59 | TestCrop::test_set_crop_overflow_x | PASSED |
| 60 | TestCrop::test_set_crop_overflow_y | PASSED |
| 61 | TestCrop::test_set_crop_negative_raises | PASSED |
| 62 | TestCrop::test_set_crop_calls_checkpoint | PASSED |
| 63 | TestCrop::test_crop_full_frame_valid | PASSED |
| 64 | TestAnnotation::test_add_text_annotation | PASSED |
| 65 | TestAnnotation::test_list_and_remove | PASSED |
| 66 | TestAnnotation::test_add_annotation_position | PASSED |
| 67 | TestAnnotation::test_list_annotations_sorted | PASSED |
| 68 | TestAnnotation::test_update_annotation_text | PASSED |
| 69 | TestAnnotation::test_update_annotation_nonexistent | PASSED |
| 70 | TestAnnotation::test_annotation_style_fields | PASSED |
| 71 | TestIntegration::test_full_workflow | PASSED |
| 72 | TestIntegration::test_export_presets | PASSED |
| 73 | TestIntegration::test_undo_redo_zoom_workflow | PASSED |
| 74 | TestIntegration::test_multiple_undo_levels | PASSED |
| 75 | TestIntegration::test_timeline_boundaries | PASSED |
| 76 | TestIntegration::test_active_regions_at | PASSED |
| 77 | TestIntegration::test_project_set_triggers_undo | PASSED |
| 78 | TestProject::test_crop_region_overflow_raises | PASSED |

### test_full_e2e.py — End-to-End Tests (23 tests, requires ffmpeg)

| # | Test | Status |
|---|------|--------|
| 79 | TestMediaE2E::test_probe_real_video | PASSED |
| 80 | TestMediaE2E::test_check_video | PASSED |
| 81 | TestMediaE2E::test_check_invalid_video | PASSED |
| 82 | TestMediaE2E::test_extract_thumbnail | PASSED |
| 83 | TestMediaE2E::test_extract_thumbnail_at_zero | PASSED |
| 84 | TestMediaE2E::test_extract_frames | PASSED |
| 85 | TestMediaE2E::test_ffmpeg_and_ffprobe_found | PASSED |
| 86 | TestExportE2E::test_basic_export | PASSED |
| 87 | TestExportE2E::test_export_with_zoom | PASSED |
| 88 | TestExportE2E::test_export_with_speed | PASSED |
| 89 | TestExportE2E::test_export_with_trim | PASSED |
| 90 | TestExportE2E::test_export_complex | PASSED |
| 91 | TestExportE2E::test_export_no_video_raises | PASSED |
| 92 | TestExportE2E::test_export_missing_video_raises | PASSED |
| 93 | TestCLISubprocess::test_cli_help | PASSED |
| 94 | TestCLISubprocess::test_cli_version | PASSED |
| 95 | TestCLISubprocess::test_cli_export_presets | PASSED |
| 96 | TestCLISubprocess::test_cli_media_probe | PASSED |
| 97 | TestCLISubprocess::test_cli_project_new_json | PASSED |
| 98 | TestCLISubprocess::test_cli_zoom_add | PASSED |
| 99 | TestCLISubprocess::test_cli_full_workflow | PASSED |
| 100 | TestCLISubprocess::test_cli_media_check_valid | PASSED |
| 101 | TestCLISubprocess::test_cli_session_status | PASSED |

## Raw pytest output

```
============================= test session starts ==============================
platform linux -- Python 3.11.2, pytest-9.0.2, pluggy-1.6.0
collected 101 items

cli_anything/openscreen/tests/test_core.py ............................................... [ 76%]
...............................                                                            [ 77%]
cli_anything/openscreen/tests/test_full_e2e.py .......................                     [100%]

============================= 101 passed in 35.19s =============================
```

## Environment

- Python: 3.11.2
- pytest: 9.0.2
- ffmpeg: 5.1.6
- OS: Linux (Debian)
