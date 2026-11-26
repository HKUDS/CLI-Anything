# Test plan

- `test_core.py` verifies packaged bridge discovery, project selection, closed-Editor failure, timeout cleanup and request/response isolation without Unity.
- `test_full_e2e.py` uses the installed CLI and a running clean Unity project. The workflow creates a scene with a camera, checks Console and build metadata, saves a Prefab, renders a PNG through Unity and verifies its signature and dimensions. It also verifies that a failed command prevents later commands in a batch, that invalid transforms, non-finite floats and out-of-range float casts are rejected before any scene mutation, and that `component set` keeps exact integers and decimals.
- Set `CLI_ANYTHING_UNITY_PROJECT` to a disposable Unity project already running with the packaged bridge.

## Results

The wheel was built and installed into an isolated test environment. The test project manifest specified only the public bridge, which resolved its declared Unity packages. The CLI-Anything harness and the standalone repository ship the same files, so these results cover both install sources.

Unity 2020.3.45f1 on Windows, installed-command mode

```text
test_packaged_bridge PASSED
test_project_resolution PASSED
test_editor_closed PASSED
test_timeout_leaves_no_request PASSED
test_concurrent_requests_are_isolated PASSED
test_batch_reads_and_stops_at_failure PASSED
test_edit_save_and_render_in_unity PASSED
7 passed in 7.13s
```

Regression run after the numeric-validation changes, Edit Mode only, fresh disposable project:

```text
test_exact_number_text_is_limited_to_bare_numbers PASSED
test_component_set_requests_the_typed_number_text PASSED
test_edit_rejects_non_finite_values PASSED
test_creation_and_float_parsers_reject_invalid_values PASSED
test_component_set_preserves_typed_precision PASSED
test_core.py: 7 passed in 0.50s
test_full_e2e.py: 6 passed in 18.94s
```

`test_component_set_preserves_typed_precision` inspects the bridge's raw reply: the CLI parses replies as binary floats, so a decimal member reads back rounded through the CLI even when the stored value is exact.

Unity 2022.3.21f1 on Windows compiled the bridge. The installed-command run passed batch reads and created a scene in a clean project. The next GameObject creation request timed out, so the 2022.3 render workflow remains unverified. Play Mode, actual player builds, package mutations and versions earlier than 2020.3 were outside this validation run.
