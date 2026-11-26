---
name: "cli-anything-unity-legacy"
description: Use the Unity Legacy CLI bridge (unity-legacy-cli) to inspect and edit an open Unity project, verify compilation, render camera PNGs, or run Editor jobs.
---

# Unity Legacy CLI

Unity Legacy CLI installs the `unity-legacy-cli` executable from either the CLI-Anything monorepo harness or the [standalone repository releases](https://github.com/key-zxy/unity-legacy-cli/releases); both distributions use the same `cli_anything.unity_legacy` module and `cli-anything-unity-legacy` skill name.

Install the Python harness and run `unity-legacy-cli bridge-path` to locate its bridge package. In Unity Package Manager, choose **Add package from disk** and select that `package.json`. Wait for script compilation. Full clean-project validation covers Unity 2020.3.45f1 on Windows. The 2022.3.21f1 run verified compilation, basic reads and scene creation. Editing and rendering on 2022.3 remain experimental. Unity 2020.3 is the package's declared minimum.

- `unity-legacy-cli --project "/path/to/UnityProject" --json status` checks the target project and Editor state.
- `unity-legacy-cli --json scene hierarchy --limit 50` lists scene objects. Use their IDs for edits. Run from inside the target project or pass its absolute path with `--project`.
- `unity-legacy-cli --json console read --type error --limit 10` reads visible errors after Unity compiles.

Place global options before subcommands. Check the response's `ok` field and process exit code. Use `--help` on `scene`, `gameobject`, `component`, `prefab`, `asset`, `camera`, `ui`, `script`, `scriptable-object`, `test`, `build`, `package`, `profiler`, `graphics`, `material`, `particle`, `animator`, `physics` or `primitive` for command details.

`batch -` reads an array of commands from standard input. Use `Command` and PascalCase arguments. The Editor stops after the first failed command. A response with `requested: true` accepts an asynchronous action. Use status, Console, or the matching job query to verify the outcome. For screenshots of scene content, use `camera capture` with the camera ID and a project-relative PNG path.

Confirm with the user before changing Play Mode or running Play Mode tests. After a timeout, inspect Editor state before retrying a write.
