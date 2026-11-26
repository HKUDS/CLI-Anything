# Unity Legacy CLI harness architecture

The Python package provides one-shot Click commands and an interactive REPL. It resolves a Unity project from `--project` or the nearest ancestor with `ProjectSettings/ProjectVersion.txt`. Each request is published atomically in a unique directory under that project's `Library/UnityCli`. The Unity package dispatches supported requests on the Editor thread and atomically publishes the JSON reply. The Python client removes its request directory on success or timeout.

The Unity project and its running Editor own scene state, Undo, Prefab Mode, imported assets and the Console. There is no second session file, proxy server or network port. Writes require explicit commands. Batch requests run in order and stop at the first failure. A client timeout does not cancel an operation that already started.

The packaged bridge uses Unity's public scene, object, Prefab, asset, compilation and rendering APIs. Console and some profiler capabilities probe version-specific Unity internals. Shader and camera output comes from Unity itself. Camera capture renders a scene camera and returns a PNG, so it covers rendered scene content.

The Editor assembly depends on the official Unity Newtonsoft JSON, uGUI and Unity Test Framework packages. It can be loaded in an empty Unity project. The Python wheel includes the bridge, CLI and agent skill. See [the README](README.md) for installation and the version matrix.
