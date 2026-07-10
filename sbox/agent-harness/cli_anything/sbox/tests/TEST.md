# Test Plan - cli-anything-sbox

Comprehensive test suite for the s&box CLI harness. All tests are runnable from
the `agent-harness/` directory.

## 1. Test Inventory

| Test File | Coverage | Tests |
|---|---|---|
| `test_core.py` | All 13 core modules: project, scene, prefab, codegen, input_config, collision_config, material, sound, localization, session, export, validate, plus the s&box backend resolver | **157** |
| `test_full_e2e.py` | CLI surface via subprocess invocation, project workflows end-to-end, sbox_backend integration | **50** |
| `test_orchestrator.py` | Map-generation test orchestrator (combo matrix, sentinel polling, RGBA -> PNG conversion, config I/O) | **17** |
| `test_exit_codes.py` | One-shot CLI exit-code contract: failures exit 1 (human + JSON modes), success exits 0, validation failure exits 1, REPL absorbs SystemExit. Plus monkeypatched coverage of audited dict-returning failure paths (asset compile, server info) | **20** |
| **Total** | | **244** |

## 2. Running the Tests

From the `agent-harness/` directory:

```bash
# Unit tests only (fast, no s&box installation required)
python -m pytest cli_anything/sbox/tests/test_core.py -v

# Orchestrator tests (Pillow required - already a hard dependency)
python -m pytest cli_anything/sbox/tests/test_orchestrator.py -v

# Full e2e suite (TestE2EBackend skips automatically when s&box is not installed)
python -m pytest cli_anything/sbox/tests/test_full_e2e.py -v

# Everything
python -m pytest cli_anything/sbox/tests/ -v
```

### Environment

| Variable | Effect |
|---|---|
| `SBOX_PATH` | Points the harness at a non-Steam s&box installation. Required for `TestE2EBackend` if s&box isn't installed in a standard Steam library. |
| `CLI_ANYTHING_FORCE_INSTALLED` | When set to `1`/`true`/`yes`, `TestCLISubprocess` runs against the installed `cli-anything-sbox` console script instead of `python -m`. |

### Skip behavior

- `TestE2EBackend` (3 tests) skips when s&box can't be located on the host. No failure, no error - clean skip with a reason message.
- `test_converts_rgba_bytes_to_png` skips if Pillow is not importable (it should always be importable since Pillow is a hard dependency).

## 3. Test Coverage by Class

### `test_core.py` (157 tests, 36 classes)

| Class | Tests | Module Under Test |
|---|---|---|
| `TestProject` | 7 | `core.project` - create, load/save, info, configure, find_sbproj |
| `TestProjectPackages` | 4 | `core.project` - add/remove package references |
| `TestProjectValidate` | 4 | `core.validate` - broken refs, duplicate GUIDs, malformed inputs |
| `TestScene` | 12 | `core.scene` - create, list, add/remove object & component, find, GUID uniqueness |
| `TestSceneQuery` | 9 | `core.scene.query_objects` - by component / tag / name / regex / bounds / enabled / combined |
| `TestSceneRefs` | 3 | `core.scene.extract_asset_refs` - default scene, dedup/sort, empty scene |
| `TestSceneBulkModify` | 4 | `core.scene.bulk_modify_objects` - position, multi-field, no-match, requires-update |
| `TestSceneCloneAndGet` | 6 | `core.scene.clone_object` + `get_object` |
| `TestSceneModify` | 4 | `core.scene.modify_object` - name, position, scale, tags |
| `TestSceneModifyComponent` | 2 | `core.scene.modify_component_properties` |
| `TestSceneInstantiatePrefab` | 5 | `core.scene.instantiate_prefab` - default name, override name, prefab source ref, parent, invalid parent |
| `TestSceneDiff` | 5 | `core.scene.diff_scenes` - identical, added/removed, position, components, scene-properties |
| `TestPrefab` | 4 | `core.prefab` - create, with components, info, from-scene |
| `TestPrefabComponents` | 2 | `core.prefab` - add/remove component on prefab root |
| `TestPrefabRefs` | 1 | `core.prefab.extract_asset_refs` |
| `TestPrefabModifyComponent` | 5 | `core.prefab.modify_component_properties` - by type, by guid, not-found, requires-id, requires-properties |
| `TestPrefabDiff` | 2 | `core.prefab.diff_prefabs` - identical, root changes |
| `TestCodegen` | 10 | `core.codegen` - component basic, with properties, networked, interfaces, lifecycle methods, gameresource, editor menu, code style (tabs / Allman / CRLF) |
| `TestCodegenRazor` | 5 | `core.codegen.generate_razor` |
| `TestCodegenClass` | 3 | `core.codegen.generate_class` - static class, base class, multiline method body regression |
| `TestCodegenPanelComponent` | 5 | `core.codegen.generate_panel_component` - basic, includes ScreenPanel, namespace, properties, unique GUIDs |
| `TestInputConfig` | 6 | `core.input_config` - get default, add, duplicate, remove, set, list |
| `TestCollisionConfig` | 5 | `core.collision_config` - get default, add layer, remove built-in, add rule, remove rule |
| `TestCollisionRemoveLayer` | 1 | `core.collision_config.remove_layer` |
| `TestMaterial` | 5 | `core.material` - new, load/save, info, list, presets |
| `TestMaterialUpdate` | 2 | `core.material.update_material` - shader, color texture |
| `TestSound` | 4 | `core.sound` - new, info, list, presets |
| `TestSoundUpdate` | 2 | `core.sound.update_sound_event` |
| `TestLocalization` | 5 | `core.localization` - new, set, get, list, remove |
| `TestLocalizationBulkSet` | 1 | `core.localization.bulk_set` |
| `TestSession` | 6 | `core.session` - create, set project, undo/redo, save/load, clear, corrupt-file warning + timestamped backup |
| `TestExport` | 3 | `core.export` - list assets, filtered list, find project dir |
| `TestAssetRefGraph` | 5 | `core.export.find_asset_refs` + `find_unused_assets` |
| `TestAssetRenameMove` | 7 | `core.export.rename_asset` + `move_asset` - both with dry-run, target-exists, source-missing, cross-directory |
| `TestComponentPresets` | 2 | `core.scene.COMPONENT_PRESETS` - count + standard names |
| `TestJointPresets` | 1 | `core.scene.COMPONENT_PRESETS` - joint preset coverage |

### `test_full_e2e.py` (50 tests, 3 classes)

| Class | Tests | Coverage |
|---|---|---|
| `TestCLISubprocess` | 40 | Spawns `cli-anything-sbox` as a subprocess (or `python -m cli_anything.sbox.sbox_cli` when not installed) and asserts `--json` output for every documented command group |
| `TestE2EProjectWorkflow` | 7 | Full project workflows: create -> add objects -> generate code -> validate. Uses the in-process Click runner |
| `TestE2EBackend` | 3 | Real s&box backend integration (`find_sbox_installation`, `get_sbox_version`, `find_server_executable`). Skips cleanly when s&box not installed |

### `test_orchestrator.py` (17 tests, 5 classes)

| Class | Tests | Coverage |
|---|---|---|
| `TestComboMatrix` | 7 | Strategy x size x seed combo matrix used by the map-generation test pipeline |
| `TestSentinelPolling` | 3 | Filesystem-sentinel polling (used to detect when in-engine tests have completed) |
| `TestConfigIO` | 3 | `test_config.json` round-trip (read, validate, write) |
| `TestRgbaConversion` | 2 | RGBA byte-array -> PNG via Pillow |
| `TestDataPathResolution` | 2 | `FileSystem.Data` path resolution across editor and standalone |

### `test_exit_codes.py` (20 tests, 5 classes)

| Class | Tests | Coverage |
|---|---|---|
| `TestOneShotFailureExitsNonZero` | 11 | Failure paths in one-shot mode return exit 1: missing scene/project file (human + JSON), missing localization key, missing required args, invalid JSON in `--properties`, asset compile without s&box install, scene list on missing file (true gate of the bare `except Exception` path), asset info on corrupt JSON (json_info.error surface). Includes the `--help` exit-0 baseline. |
| `TestOneShotSuccessExitsZero` | 2 | Confirms the success path was not regressed by the exit-1-on-failure change |
| `TestProjectValidateExitsNonZero` | 2 | `project validate` exits 1 when `ok=False` (broken refs) so CI can gate on it; clean project still exits 0 |
| `TestAuditedFailurePaths` | 2 | Monkeypatched coverage for dict-returning failure paths: `asset compile` with `success=False` from resourcecompiler, `server info` with `error` field in `get_sbox_version()`. These can't be triggered without s&box installed, so a CliRunner + monkeypatch combination pins the contract. |
| `TestReplModeAbsorbsExit` | 3 | `_output_error` does not call `sys.exit` when `ctx.obj["repl"] = True`; one-shot is the safe default when the key is absent |

## 4. Coverage by Source Module

| Module | Unit | E2E | Subprocess |
|---|---|---|---|
| `core/project.py` | 7 + 4 packages | 2 (creation, tower defense) | 1 (project new) |
| `core/scene.py` | 12 + 9 query + 3 refs + 4 bulk + 6 clone/get + 4 modify + 2 modify-comp + 5 instantiate + 5 diff = 50 | 3 (manipulation, tower defense, workflow) | 6 (query, refs, bulk-modify x2, diff x2, instantiate) |
| `core/prefab.py` | 4 + 2 components + 1 refs + 5 modify-comp + 2 diff = 14 | 1 (from_scene in manipulation) | 3 (refs, modify-component, diff) |
| `core/codegen.py` | 10 + 5 razor + 2 class + 5 panel-component = 22 | 1 (codegen workflow) | 3 (panel-component plain + scene append) |
| `core/input_config.py` | 6 | 2 (config workflow, tower defense) | 1 (input list) |
| `core/collision_config.py` | 5 + 1 remove-layer = 6 | 2 (config workflow, tower defense) | 1 (collision list) |
| `core/material.py` | 5 + 2 update = 7 | - | - |
| `core/sound.py` | 4 + 2 update = 6 | - | - |
| `core/localization.py` | 5 + 1 bulk-set = 6 | - | - |
| `core/session.py` | 5 | - | - |
| `core/export.py` | 3 + 5 ref-graph + 7 rename/move = 15 | - | 5 (find-refs, find-unused, rename, rename-dry-run, move) |
| `core/validate.py` | 4 | - | 2 (validate clean, validate broken) |
| `core/test_orchestrator.py` | 17 (full file) | - | - |
| `utils/sbox_backend.py` | - | 3 (installation, version, executable - skipped if no s&box) | - |
| `sbox_cli.py` (CLI) | - | - | 40 (full TestCLISubprocess) + 20 (test_exit_codes: failure exit-code contract + audited-path monkeypatch coverage + REPL absorb) |

## 5. E2E Prerequisites

`TestCLISubprocess` (40 tests) and `TestE2EProjectWorkflow` (7 tests) run without s&box installed - they exercise the CLI against in-memory or temp-directory project state.

`TestE2EBackend` (3 tests) requires s&box to be discoverable:
- Standard Steam install: nothing to do.
- Non-standard location: `export SBOX_PATH=/path/to/sbox` (or set the env var per shell).
- s&box not installed: tests skip with a reason message.

## 6. Coverage Gaps

- `server start` and `launch` commands are tested only via help-text smoke; running an actual s&box server / editor process is out of scope (would require live network sockets and a running game).
- `session undo`/`redo` is tested at the unit level; no E2E workflow exercises the undo journal in a realistic edit-undo-edit sequence.
- `asset compile` is help-tested only; invoking the s&box `resourcecompiler.exe` requires a full s&box install and is left to the upstream maintainers' CI. The non-zero exit-code path on missing/failed compile is exercised by `test_exit_codes.py::test_asset_compile_missing_sbox_exits_one`.

## 7. Known Test-Environment Quirks

- On Windows + Python 3.14 + pytest, `subprocess.Popen` can hit `OSError: [WinError 6] The handle is invalid` before the child process starts because the parent's stdin handle is not inheritable. Both `TestCLISubprocess._run` (in `test_full_e2e.py`) and `_run` in `test_exit_codes.py` pass `stdin=subprocess.DEVNULL` to work around this. If you add new subprocess invocations in tests, mirror that pattern.
- All file I/O is UTF-8 explicit (`open(..., encoding="utf-8")`). Earlier versions defaulted to the platform codec on Windows; that was fixed before upstream submission.
