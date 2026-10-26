# COPT harness test plan and results

## Plan

`test_core.py` contains 10 backend-independent tests for attribute parsing, missing values, COPT's seconds suffix, model validation, and supported parameters. `test_full_e2e.py` contains 10 tests that require a licensed COPT installation: installed command resolution, `doctor`, model inspection, LP and MIP optimization, JSON solution export, MPS conversion, infeasible status, IIS export, error detection, and terminal JSON isolation.

The test models in `tests/data/` are small original LP files. The LP workflow minimizes `x+y` subject to `x+2y>=4` and `3x+y>=3`, with expected objective 2.2. The MIP workflow uses two binary variables and has expected objective 2. The infeasible workflow has incompatible bounds and verifies a nonempty IIS. Output files are parsed or inspected instead of relying on a zero process exit code alone. The subprocess suite invokes the installed `cli-anything-copt` from `PATH` when `CLI_ANYTHING_FORCE_INSTALLED=1`.

The terminal regression creates a PTY with `script`. COPT sends command echoes to a controlling terminal while returning attribute values through captured stdout. The test verifies that `--json` output has no `COPT>` echo and that attributes are populated.

## Results (2026-10-26)

Command: `CLI_ANYTHING_FORCE_INSTALLED=1 .venv/bin/python -m pytest cli_anything/copt/tests/ -v --tb=no`

```text
collected 20 items
cli_anything/copt/tests/test_core.py::test_parse_attributes_extracts_numeric_values_and_status PASSED
cli_anything/copt/tests/test_core.py::test_parse_attributes_uses_requested_names_when_copt_echoes_to_terminal PASSED
cli_anything/copt/tests/test_core.py::test_parse_attributes_rejects_missing_requested_value PASSED
cli_anything/copt/tests/test_core.py::test_parse_attributes_accepts_copt_seconds_suffix PASSED
cli_anything/copt/tests/test_core.py::test_validate_model_accepts_existing_lp PASSED
cli_anything/copt/tests/test_core.py::test_validate_model_rejects_missing_file PASSED
cli_anything/copt/tests/test_core.py::test_validate_model_rejects_unsupported_format PASSED
cli_anything/copt/tests/test_core.py::test_validate_parameters_rejects_nonpositive_limit PASSED
cli_anything/copt/tests/test_core.py::test_validate_parameters_rejects_negative_gap PASSED
cli_anything/copt/tests/test_core.py::test_validate_parameters_returns_documented_set_commands PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_doctor PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_inspect_real_model PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_solve_and_export_json_solution PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_convert_to_mps PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_solve_mip PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_infeasible_solve_has_no_objective PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_iis_export PASSED
cli_anything/copt/tests/test_full_e2e.py::TestCLISubprocess::test_terminal_json_has_no_copt_prompt_echo PASSED
cli_anything/copt/tests/test_full_e2e.py::test_copt_unknown_parameter_is_an_error PASSED
20 passed in 4.82s
```

The real COPT backend was 8.0.2 on macOS. The exact user WTA command was also exercised in a PTY with `--time-limit 60` and returned structured timeout status, a feasible incumbent objective, gap, and solve time. Other COPT versions and operating systems remain to be validated by users with those installations.
