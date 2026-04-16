# Test Results — Shotcut CLI Harness

## Test Results

Last run: 2026-03-06

```
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_plain_frame_number PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_hh_mm_ss_mmm PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_hh_mm_ss PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_seconds_decimal PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_roundtrip PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_invalid_timecode PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_negative_frames PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_frames_to_seconds PASSED
cli_anything/shotcut/tests/test_core.py::TestTimecode::test_seconds_to_frames PASSED
cli_anything/shotcut/tests/test_core.py::TestMltXml::test_create_blank_project PASSED
cli_anything/shotcut/tests/test_core.py::TestMltXml::test_write_and_parse PASSED
cli_anything/shotcut/tests/test_core.py::TestMltXml::test_properties PASSED
cli_anything/shotcut/tests/test_core.py::TestMltXml::test_mlt_to_string PASSED
cli_anything/shotcut/tests/test_core.py::TestSession::test_new_session PASSED
cli_anything/shotcut/tests/test_core.py::TestSession::test_new_project PASSED
cli_anything/shotcut/tests/test_core.py::TestSession::test_save_and_open PASSED
cli_anything/shotcut/tests/test_core.py::TestSession::test_undo_redo PASSED
cli_anything/shotcut/tests/test_core.py::TestSession::test_open_nonexistent PASSED
cli_anything/shotcut/tests/test_core.py::TestSession::test_save_without_project PASSED
cli_anything/shotcut/tests/test_core.py::TestSession::test_status PASSED
cli_anything/shotcut/tests/test_core.py::TestProject::test_new_project PASSED
cli_anything/shotcut/tests/test_core.py::TestProject::test_new_project_invalid_profile PASSED
cli_anything/shotcut/tests/test_core.py::TestProject::test_project_info PASSED
cli_anything/shotcut/tests/test_core.py::TestProject::test_list_profiles PASSED
cli_anything/shotcut/tests/test_core.py::TestProject::test_save_project PASSED
cli_anything/shotcut/tests/test_core.py::TestProject::test_open_and_info PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_list_tracks_initial PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_add_video_track PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_add_audio_track PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_add_invalid_track_type PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_remove_track PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_remove_background_track_fails PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_add_clip_file_not_found PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_add_and_list_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_remove_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_trim_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_split_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_move_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_set_track_name PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_mute_unmute PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_show_timeline PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_add_blank PASSED
cli_anything/shotcut/tests/test_core.py::TestTimeline::test_undo_add_track PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_list_available_filters PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_list_by_category PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_get_filter_info PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_get_unknown_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_add_filter_to_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_add_filter_to_track PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_add_global_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_remove_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_set_filter_param PASSED
cli_anything/shotcut/tests/test_core.py::TestFilters::test_undo_add_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestMedia::test_probe_nonexistent PASSED
cli_anything/shotcut/tests/test_core.py::TestMedia::test_probe_basic PASSED
cli_anything/shotcut/tests/test_core.py::TestMedia::test_list_media_empty PASSED
cli_anything/shotcut/tests/test_core.py::TestMedia::test_list_media_with_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestMedia::test_check_media_files PASSED
cli_anything/shotcut/tests/test_core.py::TestExport::test_list_presets PASSED
cli_anything/shotcut/tests/test_core.py::TestExport::test_get_preset_info PASSED
cli_anything/shotcut/tests/test_core.py::TestExport::test_unknown_preset PASSED
cli_anything/shotcut/tests/test_core.py::TestExport::test_render_no_project PASSED
cli_anything/shotcut/tests/test_core.py::TestExport::test_render_no_overwrite PASSED
cli_anything/shotcut/tests/test_core.py::TestIntegration::test_full_workflow PASSED
cli_anything/shotcut/tests/test_core.py::TestIntegration::test_save_load_roundtrip_preserves_filters PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_list_available_transitions PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_list_by_category_video PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_list_by_category_audio PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_get_transition_info PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_get_transition_info_invalid PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_add_transition PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_add_transition_with_params PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_add_wipe_transition PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_add_transition_invalid_track PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_add_raw_service_transition PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_list_transitions_empty PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_list_transitions_after_add PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_remove_transition PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_remove_transition_invalid_index PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_set_transition_param PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_undo_add_transition PASSED
cli_anything/shotcut/tests/test_core.py::TestTransitions::test_multiple_transitions PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_list_blend_modes PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_set_track_blend_mode PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_set_blend_mode_invalid PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_set_blend_mode_background_track PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_get_track_blend_mode_default PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_get_track_blend_mode_after_set PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_set_track_opacity PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_set_track_opacity_invalid_range PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_set_track_opacity_invalid_index PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_set_track_opacity_update_existing PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_pip_position PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_pip_position_defaults PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_pip_position_invalid_track PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_pip_position_invalid_clip PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_pip_update_existing PASSED
cli_anything/shotcut/tests/test_core.py::TestCompositing::test_undo_set_blend_mode PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_filter_categories PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_chroma_key_filter_exists PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_color_grading_filters_exist PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_distortion_filters_exist PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_transform_filters_exist PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_audio_filters_exist PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_add_sharpen_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_add_vignette_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_add_grayscale_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_add_invert_filter PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_total_filter_count PASSED
cli_anything/shotcut/tests/test_core.py::TestExpandedFilters::test_filter_info_has_params PASSED
```

**Summary**: 110 passed in 0.23s

## Test Breakdown

| Module | Tests | Status |
|--------|-------|--------|
| Timecode | 9 | All pass |
| MLT XML | 4 | All pass |
| Session | 7 | All pass |
| Project | 6 | All pass |
| Timeline | 17 | All pass |
| Filters | 10 | All pass |
| Media | 5 | All pass |
| Export | 5 | All pass |
| Integration | 2 | All pass |
| Transitions | 16 | All pass |
| Compositing | 16 | All pass |
| Expanded Filters | 13 | All pass |
| **Total** | **110** | **100% pass** |
