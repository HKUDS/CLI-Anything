# TEST.md — cli-anything-alexa

## Test plan

### Unit tests (`test_core.py`, no network)

| Area | What is checked |
|---|---|
| Device model | Amazon records normalized; speakers vs apps; sorting; filtering |
| Device resolution | exact/case-insensitive name, serial, unique substring, ambiguous and missing errors that list valid names |
| Action validation | empty / over-length text, sequence names, music providers and timer, volume range, light entity and brightness, announce targets |
| Smart home | nested `get_network_details` payload flattened; reachability from both field styles |
| Account storage | `account.json` written 0600, load, delete; 8 threads saving at once leave valid JSON and no temp files; `~` in ALEXA_CLI_HOME expands; device cache written atomically (concurrent reader never sees partial JSON), tagged with its account and removed on logout; a session starting during logout never re-creates credentials |
| CLI (Click, backend mocked) | JSON output for every command group, error codes (`not_logged_in`, `ambiguous_device`, `device_not_found`), usage errors, default announce targets (online speakers only), dry-run sends nothing and uses the cache |
| Login robustness | free local port chosen by default; a port already used by another app is refused with a clear error; certifi CA bundle used unless SSL_CERT_FILE is set; TLS certificate failures become an actionable message |
| Amazon site | speech language follows the --domain site; a mismatch between the sign-in site and the account's real site produces one actionable warning (stderr, and `warning` in JSON objects including failures; list-shaped JSON stays a list and the warning goes to stderr) |
| Review fixes | speaker groups listed, targetable only by music/playback/volume and never by speak/command/sequence/routine/announce; actions never target Alexa apps; `--cached` never calls Amazon and accepts an empty cached list; unexpected library errors become `backend_error` JSON; `--dry-run` login/logout touch nothing; REPL keeps `--json`/`--dry-run` and keeps stdout pure JSON in `--json` mode; usage errors are JSON under `--json` (subprocess); `--domain` must be an Amazon domain; `--dry-run` never writes (`auth locale`) or contacts Amazon (`routine list`, `smarthome list`, `auth status --verify`) |
| Backend dispatch | actions on another household member's device pass that owner's customer ID; a failed session start always closes the HTTP session; each action calls the real `alexapy.AlexaAPI` method name with the right arguments (checked against the installed alexapy) |

### E2E tests (`test_full_e2e.py`)

Subprocess tests run the installed `cli-anything-alexa` command via
`_resolve_cli()`:

- help and version
- logged-out JSON status and error code
- dry-run announce from a cached device list
- `auth login` picks a free port, prints it, and the capture proxy answers HTTP 200 there

Live Amazon tests (opt-in, `ALEXA_E2E=1` after `auth login`):

- session verifies against Amazon (`auth status --verify`)
- device list returns real Echo devices with serials
- routine list and smart-home list return lists
- `speak` on `ALEXA_E2E_DEVICE` (also needs `ALEXA_E2E_SPEAK=1`); verified by ear

## Realistic workflows covered

1. Agent checks login, lists devices, speaks on one Echo by partial name.
2. Agent announces to all online Echos, or to an explicit set of rooms.
3. Agent runs a free-text voice command ("turn off the living room lights").
4. Agent validates an action with `--dry-run` before running it.
5. Agent recovers from an ambiguous device name using the error message.

## Results

Environment: Linux, Python 3.13, alexapy 1.36.0 (suite also passes on 1.38.0), no Amazon account (live
tests skipped).

Manual live checks on a real Amazon account (macOS, Python 3.13, amazon.co.uk):

1. First run: `auth login` and `speak` succeeded (Amazon accepted the
   request, `"sent": true`). This surfaced the busy-port, CA-certificate
   and account-domain issues fixed in this branch.
2. Re-test on the final code (head 78b2af0), all passing:
   - `auth logout`, then `auth login --domain amazon.co.uk` through the
     local sign-in page: logged in, speech language en-GB, no domain warning
   - `device list`: Echo Dot, Echo Show 5, a multi-room speaker group and a
     shared-household Echo listed and online; Alexa apps hidden
   - `speak` on the Echo Dot: spoke out loud
   - `speak` on another household member's Echo: spoke out loud

```
test_core.py::TestDevices::test_normalize_fields PASSED [  0%]
test_core.py::TestDevices::test_app_is_not_speaker PASSED [  1%]
test_core.py::TestDevices::test_filter_hides_non_speakers_and_sorts PASSED [  2%]
test_core.py::TestDevices::test_resolve_exact_case_insensitive PASSED [  3%]
test_core.py::TestDevices::test_resolve_by_serial PASSED [  4%]
test_core.py::TestDevices::test_resolve_unique_substring PASSED [  5%]
test_core.py::TestDevices::test_resolve_ambiguous PASSED [  5%]
test_core.py::TestDevices::test_resolve_missing_lists_known PASSED [  6%]
test_core.py::TestDevices::test_resolve_empty PASSED [  7%]
test_core.py::TestActions::test_speak_strips_text PASSED [  8%]
test_core.py::TestActions::test_empty_text_rejected PASSED [  9%]
test_core.py::TestActions::test_long_text_rejected PASSED [ 10%]
test_core.py::TestActions::test_sequence_maps_to_amazon_name PASSED [ 11%]
test_core.py::TestActions::test_sequence_unknown PASSED [ 11%]
test_core.py::TestActions::test_music_provider_mapping PASSED [ 12%]
test_core.py::TestActions::test_music_bad_timer PASSED [ 13%]
test_core.py::TestActions::test_volume_range[-1] PASSED [ 14%]
test_core.py::TestActions::test_volume_range[101] PASSED [ 15%]
test_core.py::TestActions::test_volume_range[5.5] PASSED [ 16%]
test_core.py::TestActions::test_announce_needs_targets PASSED [ 17%]
test_core.py::TestActions::test_light_validation PASSED [ 17%]
test_core.py::TestActions::test_describe_reduces_devices PASSED [ 18%]
test_core.py::test_flatten_network_nested PASSED [ 19%]
test_core.py::test_account_saved_owner_only PASSED [ 20%]
test_core.py::TestCLI::test_status_logged_out PASSED [ 21%]
test_core.py::TestCLI::test_device_list_json PASSED [ 22%]
test_core.py::TestCLI::test_speak_sends_action PASSED [ 23%]
test_core.py::TestCLI::test_command_sends_text PASSED [ 23%]
test_core.py::TestCLI::test_announce_defaults_to_online_speakers PASSED [ 24%]
test_core.py::TestCLI::test_announce_explicit_targets PASSED [ 25%]
test_core.py::TestCLI::test_ambiguous_device_error_code PASSED [ 26%]
test_core.py::TestCLI::test_not_logged_in_error_code PASSED [ 27%]
test_core.py::TestCLI::test_volume_out_of_range_is_usage_error PASSED [ 28%]
test_core.py::TestCLI::test_music_resume_maps_to_play_op PASSED [ 29%]
test_core.py::TestCLI::test_sequence_choice PASSED [ 29%]
test_core.py::TestCLI::test_dry_run_uses_cache_and_sends_nothing PASSED [ 30%]
test_core.py::TestCLI::test_dry_run_without_cache_fails_cleanly PASSED [ 31%]
test_core.py::TestCLI::test_logout PASSED       [ 32%]
test_core.py::TestCLI::test_locale PASSED       [ 33%]
test_core.py::test_execute_dispatch[action0-expected0] PASSED [ 34%]
test_core.py::test_execute_dispatch[action1-expected1] PASSED [ 35%]
test_core.py::test_execute_dispatch[action2-expected2] PASSED [ 35%]
test_core.py::test_execute_dispatch[action3-expected3] PASSED [ 36%]
test_core.py::test_execute_dispatch[action4-expected4] PASSED [ 37%]
test_core.py::test_execute_dispatch[action5-expected5] PASSED [ 38%]
test_core.py::test_execute_dispatch[action6-expected6] PASSED [ 39%]
test_core.py::test_execute_dispatch[action7-expected7] PASSED [ 40%]
test_core.py::test_execute_announce_targets_all PASSED [ 41%]
test_core.py::test_execute_light PASSED         [ 41%]
test_core.py::test_choose_port_picks_free_port_by_default PASSED [ 42%]
test_core.py::test_choose_port_rejects_port_used_by_another_app PASSED [ 43%]
test_core.py::test_certifi_bundle_used_when_unset PASSED [ 44%]
test_core.py::test_certifi_bundle_respects_user_setting PASSED [ 45%]
test_core.py::test_cert_error_becomes_actionable_message PASSED [ 46%]
test_core.py::test_cli_login_busy_port_is_clean_json_error PASSED [ 47%]
test_core.py::test_locale_for_domain[amazon.co.uk-en-GB] PASSED [ 47%]
test_core.py::test_locale_for_domain[amazon.de-de-DE] PASSED [ 48%]
test_core.py::test_locale_for_domain[amazon.in-en-IN] PASSED [ 49%]
test_core.py::test_locale_for_domain[amazon.com-en-US] PASSED [ 50%]
test_core.py::test_locale_for_domain[amazon.example-en-US] PASSED [ 51%]
test_core.py::test_domain_warning_only_on_mismatch PASSED [ 52%]
test_core.py::test_cli_surfaces_domain_warning PASSED [ 52%]
test_core.py::test_group_is_listed_but_not_a_speaker PASSED [ 53%]
test_core.py::test_announce_default_skips_groups PASSED [ 54%]
test_core.py::test_music_can_target_group PASSED [ 55%]
test_core.py::test_actions_ignore_alexa_apps PASSED [ 56%]
test_core.py::test_cached_without_cache_does_not_call_amazon PASSED [ 57%]
test_core.py::test_unexpected_backend_error_is_json PASSED [ 58%]
test_core.py::test_logout_dry_run_keeps_credentials PASSED [ 58%]
test_core.py::test_login_dry_run_starts_nothing PASSED [ 59%]
test_core.py::test_repl_keeps_dry_run_and_json PASSED [ 60%]
test_core.py::test_valid_domain[amazon.com-True] PASSED [ 61%]
test_core.py::test_valid_domain[amazon.co.uk-True] PASSED [ 62%]
test_core.py::test_valid_domain[amazon.com.au-True] PASSED [ 63%]
test_core.py::test_valid_domain[amazon.de-True] PASSED [ 64%]
test_core.py::test_valid_domain[AMAZON.IN-True] PASSED [ 64%]
test_core.py::test_valid_domain[evil.example-False] PASSED [ 65%]
test_core.py::test_valid_domain[amazon.com.evil.io-False] PASSED [ 66%]
test_core.py::test_valid_domain[-False] PASSED  [ 67%]
test_core.py::test_login_rejects_non_amazon_domain PASSED [ 68%]
test_core.py::test_locale_dry_run_does_not_write PASSED [ 69%]
test_core.py::test_read_commands_do_not_contact_amazon_in_dry_run[args0-fetch_routines] PASSED [ 70%]
test_core.py::test_read_commands_do_not_contact_amazon_in_dry_run[args1-fetch_network] PASSED [ 70%]
test_core.py::test_read_commands_do_not_contact_amazon_in_dry_run[args2-verify] PASSED [ 71%]
test_core.py::test_config_dir_expands_tilde PASSED [ 72%]
test_core.py::test_concurrent_account_saves_stay_valid PASSED [ 73%]
test_core.py::test_speech_commands_reject_speaker_groups[args0] PASSED [ 74%]
test_core.py::test_speech_commands_reject_speaker_groups[args1] PASSED [ 75%]
test_core.py::test_speech_commands_reject_speaker_groups[args2] PASSED [ 76%]
test_core.py::test_speech_commands_reject_speaker_groups[args3] PASSED [ 76%]
test_core.py::test_speech_commands_reject_speaker_groups[args4] PASSED [ 77%]
test_core.py::test_media_commands_accept_speaker_groups[args0] PASSED [ 78%]
test_core.py::test_media_commands_accept_speaker_groups[args1] PASSED [ 79%]
test_core.py::test_device_cache_written_atomically PASSED [ 80%]
test_core.py::test_failure_output_keeps_domain_warning PASSED [ 81%]
test_core.py::test_list_json_warning_goes_to_stderr PASSED [ 82%]
test_core.py::test_empty_cache_is_valid PASSED  [ 82%]
test_core.py::test_missing_cache_is_none PASSED [ 83%]
test_core.py::test_actions_act_as_device_owner PASSED [ 84%]
test_core.py::test_session_closed_when_startup_raises PASSED [ 85%]
test_core.py::test_device_cache_scoped_to_account PASSED [ 86%]
test_core.py::test_logout_removes_device_cache PASSED [ 87%]
test_core.py::test_session_start_does_not_resurrect_logged_out_account PASSED [ 88%]
test_core.py::test_json_repl_keeps_stdout_pure_json PASSED [ 88%]
test_full_e2e.py::TestCLISubprocess::test_help_lists_command_groups PASSED [ 89%]
test_full_e2e.py::TestCLISubprocess::test_version PASSED [ 90%]
test_full_e2e.py::TestCLISubprocess::test_status_logged_out_json PASSED [ 91%]
test_full_e2e.py::TestCLISubprocess::test_logged_out_action_fails_with_code PASSED [ 92%]
test_full_e2e.py::TestCLISubprocess::test_dry_run_from_cached_devices PASSED [ 93%]
test_full_e2e.py::TestCLISubprocess::test_login_proxy_serves_http PASSED [ 94%]
test_full_e2e.py::TestLiveAmazon::test_session_verifies SKIPPED [ 94%]
test_full_e2e.py::TestLiveAmazon::test_device_list_has_speakers SKIPPED [ 95%]
test_full_e2e.py::TestLiveAmazon::test_routine_list SKIPPED [ 96%]
test_full_e2e.py::TestLiveAmazon::test_smarthome_list SKIPPED [ 97%]
test_full_e2e.py::TestLiveAmazon::test_speak_out_loud SKIPPED [ 98%]
test_full_e2e.py::TestUsageErrorsSubprocess::test_usage_error_is_json_with_json_flag PASSED [ 99%]
test_full_e2e.py::TestUsageErrorsSubprocess::test_usage_error_is_text_without_json PASSED [100%]
======================== 112 passed, 5 skipped in 2.27s ========================
```
