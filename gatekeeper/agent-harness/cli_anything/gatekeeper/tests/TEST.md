# cli-anything-gatekeeper — Test Plan & Results

## Part 1 — Plan

### Inventory
- `test_core.py` — ~30 unit tests, no network.
- `test_full_e2e.py` — ~20 E2E tests: a local mock of the Gatekeeper API + Supabase
  (full happy path, auth, quota, saved reports), CLI subprocess tests, and **live**
  tests against https://www.gatekeeper.blog.

### Unit plan
| Module | What | Edge cases |
|---|---|---|
| `core/extract.py` | DOCX paragraphs/tabs, XLSX `[Sheet N]` TSV with shared + inline strings, PDF text, TXT | wrong ext, >10 MB, >10 files, corrupt zip, scanned-PDF warning, empty file, folder expansion |
| `core/evaluate.py` | `parse_weights` | defaults → `None`, sum ≠ 100, unknown criterion, bad number, out of range |
| `core/evaluate.py` | `build_payload` | unreadable file rejected |
| `core/session.py` | JWT claims, save/load 0600, env override, refresh when near expiry | corrupt file, no refresh token |
| `core/report.py` | load (3 shapes), summary, compliance filters, pricing discrepancies, risks, markdown | missing sections, non-report JSON |
| `utils/gk_backend.py` | magic-link fragment parsing | no tokens in link |

### E2E plan
1. **Tender evaluation workflow** — simulates a buyer evaluating 2 bids against an RFP:
   extract folder (DOCX RFP, PDF bids, XLSX BOM, TXT) → sign in with code → `evaluate -o`
   → `report summary/compliance --status FAIL --mandatory/pricing/risks/markdown`.
   Verified: payload sent equals extracted text, weights sent only when customised,
   Bearer token present, report saved and re-readable offline, Markdown contains the ranking.
2. **Plan wall** — 402 from `/api/evaluate` → exit code 3 with upgrade URL.
3. **Expired session** — token within 120 s of expiry is refreshed before the call.
4. **History** — `reports list` / `reports get -o` query `evaluations` with the user's email + RLS token.
5. **Magic link** — `auth complete --link` follows `/auth/v1/verify` without redirect and reads tokens.
6. **Live service** — `health` returns 200 from production; `/api/config` exposes Supabase URL;
   `evaluate` with an invalid token returns exit 2 (401, no credit spent); invalid email rejected by
   real Supabase auth. A real paid evaluation runs only when `GATEKEEPER_LIVE_TOKEN` is set.

## Part 2 — Results

Run 2026-10-29 (after the PR #633 Codex review fixes), Python 3.13,
`CLI_ANYTHING_FORCE_INSTALLED=1 pytest -v --tb=no` (live tests hit https://www.gatekeeper.blog):

```
test_core.py::TestExtract::test_docx_paragraphs_and_tabs PASSED
test_core.py::TestExtract::test_xlsx_layout_matches_web PASSED
test_core.py::TestExtract::test_pdf_text PASSED
test_core.py::TestExtract::test_txt PASSED
test_core.py::TestExtract::test_scanned_pdf_warning PASSED
test_core.py::TestExtract::test_rejects_wrong_type PASSED
test_core.py::TestExtract::test_rejects_large_file PASSED
test_core.py::TestExtract::test_missing_file PASSED
test_core.py::TestExtract::test_corrupt_docx_becomes_warning PASSED
test_core.py::TestExtract::test_empty_txt_warns PASSED
test_core.py::TestExtract::test_folder_expansion_skips_unaccepted PASSED
test_core.py::TestExtract::test_max_files PASSED
test_core.py::TestExtract::test_no_inputs PASSED
test_core.py::TestExtract::test_summarize_has_no_text PASSED
test_core.py::TestWeights::test_none PASSED
test_core.py::TestWeights::test_defaults_return_none PASSED
test_core.py::TestWeights::test_custom PASSED
test_core.py::TestWeights::test_sum_must_be_100 PASSED
test_core.py::TestWeights::test_unknown_criterion PASSED
test_core.py::TestWeights::test_bad_number_and_range PASSED
test_core.py::TestWeights::test_payload_rejects_unreadable PASSED
test_core.py::TestWeights::test_payload_shape PASSED
test_core.py::TestSession::test_jwt_claims PASSED
test_core.py::TestSession::test_save_load_permissions PASSED
test_core.py::TestSession::test_env_overrides PASSED
test_core.py::TestSession::test_not_signed_in PASSED
test_core.py::TestSession::test_refresh_near_expiry PASSED
test_core.py::TestSession::test_expired_without_refresh PASSED
test_core.py::TestSession::test_corrupt_session_file PASSED
test_core.py::TestSession::test_clear PASSED
test_core.py::test_fragment_tokens PASSED
test_core.py::TestReport::test_load_shapes PASSED
test_core.py::TestReport::test_summary_sorted_and_counts PASSED
test_core.py::TestReport::test_compliance_filters PASSED
test_core.py::TestReport::test_pricing_discrepancies PASSED
test_core.py::TestReport::test_risks_include_missing_docs PASSED
test_core.py::TestReport::test_markdown PASSED
test_core.py::TestReport::test_empty_report PASSED
test_core.py::TestXlsxCellReferences::test_omitted_blank_cell_keeps_column PASSED
test_core.py::TestXlsxCellReferences::test_leading_gap_and_self_closing PASSED
test_core.py::TestXlsxCellReferences::test_multi_letter_columns PASSED
test_core.py::TestXlsxCellReferences::test_cells_without_reference_are_sequential PASSED
test_core.py::TestXlsxCellReferences::test_out_of_order_reference_does_not_overwrite PASSED
test_core.py::TestXlsxCellReferences::test_sheets_in_numeric_order PASSED
test_core.py::TestFractionalWeights::test_fraction_rejected PASSED
test_core.py::TestFractionalWeights::test_fraction_cannot_sneak_total_to_100 PASSED
test_core.py::TestFractionalWeights::test_integer_valued_float_accepted PASSED
test_core.py::TestRefreshErrorMapping::test_auth_rejection_is_401[400] PASSED
test_core.py::TestRefreshErrorMapping::test_auth_rejection_is_401[401] PASSED
test_core.py::TestRefreshErrorMapping::test_auth_rejection_is_401[403] PASSED
test_core.py::TestRefreshErrorMapping::test_transient_failure_keeps_status[429] PASSED
test_core.py::TestRefreshErrorMapping::test_transient_failure_keeps_status[500] PASSED
test_core.py::TestRefreshErrorMapping::test_transient_failure_keeps_status[503] PASSED
test_core.py::TestRefreshErrorMapping::test_malformed_success_is_not_auth PASSED
test_core.py::TestSessionConcurrency::test_reader_never_sees_partial_file PASSED
test_core.py::TestSessionConcurrency::test_concurrent_refresh_spends_token_once PASSED
test_core.py::TestSessionConcurrency::test_session_file_mode_after_atomic_write PASSED
test_full_e2e.py::TestTenderWorkflow::test_full_evaluation_pipeline PASSED
test_full_e2e.py::TestTenderWorkflow::test_default_weights_not_sent PASSED
test_full_e2e.py::TestTenderWorkflow::test_human_output PASSED
test_full_e2e.py::TestErrors::test_plan_wall_exit_3 PASSED
test_full_e2e.py::TestErrors::test_not_signed_in_exit_2 PASSED
test_full_e2e.py::TestErrors::test_bad_token_exit_2 PASSED
test_full_e2e.py::TestErrors::test_bad_weights_exit_1_no_call PASSED
test_full_e2e.py::TestErrors::test_wrong_code PASSED
test_full_e2e.py::TestErrors::test_dry_run_sends_nothing PASSED
test_full_e2e.py::TestReviewFixes::test_unhealthy_json_is_one_document PASSED
test_full_e2e.py::TestReviewFixes::test_transient_refresh_failure_is_retryable_exit_1 PASSED
test_full_e2e.py::TestReviewFixes::test_fractional_weight_rejected_before_any_call PASSED
test_full_e2e.py::TestSessionLifecycle::test_magic_link_and_refresh PASSED
test_full_e2e.py::TestSessionLifecycle::test_status_verify_logout PASSED
test_full_e2e.py::TestSavedReports::test_list_and_get PASSED
test_full_e2e.py::TestCLIBasics::test_help_and_version PASSED
test_full_e2e.py::TestCLIBasics::test_real_excel_blank_styled_cells PASSED
test_full_e2e.py::TestLive::test_live_health PASSED
test_full_e2e.py::TestLive::test_live_invalid_token_is_401 PASSED
test_full_e2e.py::TestLive::test_live_supabase_auth_reachable PASSED
test_full_e2e.py::TestLive::test_live_real_evaluation SKIPPED
======================== 77 passed, 1 skipped in 16.51s ========================
```

### Summary
- 77 passed, 1 skipped (the credit-consuming live evaluation, gated on `GATEKEEPER_LIVE_TOKEN`), ~17 s.
- Live: production `/api/health` 200; `/api/evaluate` rejects an invalid token with 401 → exit 2;
  production Supabase auth validates the email format.

### Review fixes (PR #633) — each has regression tests that fail on the previous commit
| Finding | Fix | Tests |
|---|---|---|
| XLSX columns dropped when blank cells are omitted | cells placed by their `r="C2"` reference; numeric sheet order | `TestXlsxCellReferences` (6) |
| `health --json` printed two JSON documents when unhealthy | error folded into the single health object | `test_unhealthy_json_is_one_document` |
| session reads could race refresh writes | atomic temp-file + `os.replace`; writers/refresh serialized on `session.lock`; refresh re-checked under the lock so a rotating refresh token is spent once | `TestSessionConcurrency` (3) |
| fractional weights silently truncated | whole percentages only (`25` / `25.0`), else rejected | `TestFractionalWeights` (3), `test_fractional_weight_rejected_before_any_call` |
| transient refresh failures (429/5xx) reported as "sign in again" | only 400/401/403 → exit 2; others keep their status → exit 1, session kept | `TestRefreshErrorMapping` (7), `test_transient_refresh_failure_is_retryable_exit_1` |

### Coverage notes
- The success path of `/api/evaluate` is exercised against a contract-faithful mock (request and
  response shapes taken from the production `evaluate.html`). A live evaluation needs a signed-in
  account and spends a credit — run `GATEKEEPER_LIVE_TOKEN=… pytest -k live_real`.
- The magic-link email itself is not tested end to end (would send real mail).
