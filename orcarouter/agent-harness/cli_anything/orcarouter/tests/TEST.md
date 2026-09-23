# Test coverage — cli-anything-orcarouter

All tests use fake credentials (`sk-orca-test-…`) and a local fake OrcaRouter
service. No live network access and no real account are required. One test in
`test_full_e2e.py` additionally performs a real request when
`ORCAROUTER_API_KEY` is set; it is skipped otherwise.

## How to run

```bash
cd orcarouter/agent-harness
pip install -e ".[dev]"
python -m pytest cli_anything/orcarouter/tests/ -v
```

## What is covered

### `test_core.py` — the credential seam

| Area | Tests |
|------|-------|
| One credential shape for both adapters | `test_api_key_adapter_and_pkce_adapter_produce_the_same_credential_shape`, `test_provider_does_not_care_which_adapter_produced_the_credential` |
| Store / read / clear | `test_store_read_clear_roundtrip`, `test_config_file_is_not_world_readable` |
| Resolution priority (`--api-key` > env > stored) | `test_resolution_priority_cli_then_env_then_stored` |
| Redaction | `test_masking_never_reveals_the_whole_secret`, `test_stored_key_is_never_exposed_by_the_public_view`, `test_error_messages_never_contain_the_key` |
| Input validation | `test_format_check_rejects_obvious_mistakes` |
| Origins | `test_default_origins_are_the_two_public_hosts`, `test_shared_base_url_override`, `test_explicit_overrides_win_over_the_shared_base`, `test_non_loopback_http_is_refused`, `test_loopback_http_is_allowed_for_development` |
| `401` → terminal reauth, generation-safe | `test_401_marks_the_exact_account_and_never_retries`, `test_stale_401_does_not_poison_a_newer_credential`, `test_401_from_an_environment_key_does_not_write_a_stored_secret` |
| Other error semantics | `test_403_and_429_are_reported_without_marking_reauth`, `test_auth_required_error_lists_both_choices` |

### `test_pkce.py` — the connect flow

| Area | Tests |
|------|-------|
| Verifier / challenge / state | `test_challenge_is_base64url_sha256_without_padding`, `test_every_attempt_gets_a_fresh_verifier_and_state` |
| Verifier never leaves the process | `test_verifier_never_appears_on_the_authorize_url`, `test_verifier_never_appears_in_a_failure_message` |
| Authorize URL | `test_authorize_url_targets_the_auth_origin`, `test_flow_b_requires_s256_and_the_adapter_sends_it` |
| Flow A end to end | `test_flow_a_end_to_end_through_the_login_adapter`, `test_exchange_body_carries_the_verifier_and_the_method` |
| Flow B end to end | `test_flow_b_out_of_band_sends_callback_url_oob` |
| Origin discipline | `test_exchange_uses_the_auth_origin_never_the_inference_origin` |
| Failure paths | wrong verifier, code reuse, expired code, unknown code, `400` downgrade, `429`, network failure, denial, state mismatch, timeout |
| Scope handling | `test_scope_downgrade_is_reported_and_blocks_inference`, `test_scope_is_read_from_the_response_not_assumed` |
| Lifecycle / generations | `test_second_login_invalidates_the_first`, `test_a_stale_result_cannot_overwrite_a_newer_login`, `test_cancel_releases_state_and_the_listener`, `test_pagehide_clears_busy_and_hint_without_remounting`, `test_cancelled_login_does_not_issue_a_credential` |

### `test_catalog.py` — discovery and capability filtering

| Area | Tests |
|------|-------|
| Live discovery is the source of options | `test_options_come_from_the_api_not_a_hand_written_list`, `test_discovery_sends_bearer_auth_and_targets_the_api_origin` |
| Namespace and metadata preserved | `test_vendor_namespace_is_preserved_verbatim`, `test_metadata_is_preserved_including_the_reasoning_ladder` |
| Bounds and malformed input | `test_discovery_is_bounded`, `test_oversized_response_is_refused`, `test_malformed_records_are_dropped` |
| Per-capability filters | `test_chat_filter_excludes_non_text_models`, `test_chat_filter_accepts_every_supported_endpoint_type`, `test_embedding_image_video_rerank_filters` |
| Multimodal fail-closed | `test_multimodal_filter_is_fail_closed`, `test_capability_is_never_inferred_from_the_model_name` |
| Stale selection | `test_selected_model_is_cleared_when_it_stops_being_compatible` |
| Fallback seed | `test_live_failure_falls_back_to_the_verified_seed`, `test_seed_keeps_its_verified_metadata`, `test_seed_is_never_mixed_into_a_successful_live_result`, `test_seed_only_models_do_not_leak_into_a_partial_live_catalog`, `test_no_credential_still_offers_the_verified_seed` |
| Provider integration | `test_discover_selectable_filters_the_live_catalog`, `test_modality_guard_blocks_an_incompatible_model`, `test_build_messages_reports_the_uploaded_modality` |

### `test_server.py` — the loopback settings UI

| Area | Tests |
|------|-------|
| Page and assets | `test_page_and_assets_are_served` (includes the official PNG logo), `test_page_hides_the_key_input_and_masks_the_stored_secret` |
| API-key choice | `test_api_key_choice_stores_reads_and_clears`, `test_api_key_choice_rejects_a_malformed_key` |
| PKCE choice | `test_pkce_choice_authorizes_through_the_page`, `test_pkce_out_of_band_accepts_a_pasted_code` |
| Cancellation | `test_cancel_releases_the_login_lock`, `test_pagehide_cancels_server_side_work_and_a_new_login_can_start`, `test_pagehide_handler_is_present_in_the_client_and_clears_state`, `test_starting_a_second_login_while_the_first_is_in_flight` |
| Catalog endpoint | `test_model_endpoint_filters_by_capability_and_modality`, `test_model_endpoint_reports_degraded_when_discovery_fails`, `test_model_endpoint_returns_minimal_metadata` |
| Key hygiene | `test_no_response_body_ever_contains_the_api_key`, `test_login_state_never_contains_the_verifier`, `test_server_only_binds_loopback` |

### `test_cli.py` — commands through the provider path

| Area | Tests |
|------|-------|
| Both choices discoverable and independent | `test_help_exposes_both_authentication_choices`, `test_api_key_choice_works_without_any_login`, `test_pkce_choice_works_without_a_preexisting_key`, `test_the_two_choices_are_independently_usable` |
| Inference | `test_chat_goes_through_the_configured_api_origin`, `test_test_command_reports_the_origin_and_model`, `test_chat_with_an_image_uses_a_model_that_declares_image_input`, `test_an_image_with_an_incompatible_model_is_refused_before_sending` |
| Catalog commands | `test_models_command_lists_only_compatible_models`, `test_models_command_multimodal_filter`, `test_models_command_capability_filter`, `test_models_command_reports_degraded_without_credentials`, `test_catalog_command_shows_provenance_and_reasoning` |
| Redaction | `test_config_show_masks_the_stored_key`, `test_no_command_output_ever_contains_the_stored_key` |
| Origins | `test_auth_and_api_origins_are_independent`, `test_default_origins_are_never_derived_from_each_other` |

### `test_full_e2e.py` — both choices over real loopback HTTP

| Area | Tests |
|------|-------|
| API-key choice end to end | `test_api_key_sign_in_then_chat_and_models` |
| PKCE choice end to end, then chat on the same path | `test_pkce_sign_in_then_chat_uses_the_same_provider_path` |
| One credential type, whichever adapter produced it | `test_both_choices_produce_a_credential_the_provider_cannot_tell_apart` |
| Capability filtering over the wire | `test_multimodal_selector_over_the_wire_keeps_only_image_models` |
| Relay rejection | `test_unknown_credential_is_rejected_by_the_relay` |
| Live service (opt-in) | `test_live_catalog_and_inference_through_the_provider_path` (skipped without `ORCAROUTER_API_KEY`) |

## Live checks (not part of the unit suite)

Run with a real `ORCAROUTER_API_KEY` to exercise the same code path against the
real service:

```bash
export ORCAROUTER_API_KEY=sk-orca-…
cli-anything-orcarouter models                       # live catalog
cli-anything-orcarouter models --modalities image    # multimodal filter
cli-anything-orcarouter test                         # one real completion
cli-anything-orcarouter chat --prompt "hi" --image shot.png
```

A real browser sign-in needs human consent and is therefore not automated; the
PKCE adapter is covered end to end against the local fake auth server instead.

## Summary

```
119 passed
```
