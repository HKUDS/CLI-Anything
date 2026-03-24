# FreeCAD Agent Harness Architecture

This harness provides a stateful CLI for FreeCAD, enabling AI agents to perform parametric 3D modeling tasks.

## Architecture

The harness follows the standard CLI-Anything pattern:

1.  **Session State**: Managed in `cli_anything/freecad/core/session.py`. It stores the project as a JSON object, which acts as a "source of truth" for the parametric model.
2.  **Command Logic**: Defined in `cli_anything/freecad/freecad_cli.py` using `click`. Commands modify the JSON state.
3.  **Backend Execution**: Handled in `cli_anything/freecad/utils/freecad_backend.py`. It translates the JSON state into a FreeCAD Python (`bpy`-style but for FreeCAD) script and executes it using `FreeCADCmd`.
4.  **REPL Interface**: Provides an interactive shell for agents to build models step-by-step.

## Capabilities

- **Project Management**: New, Load, Save, Info.
- **Sketcher**: Add basic 2D primitives (circles, lines, etc.) with parameters.
- **Part Design**: 3D operations like `pad` (extrude).
- **Export**: Render the model to industry-standard formats like STEP, STL, and OBJ.

## Development

### Running Tests

```bash
pip install -e .[dev]
python -m pytest
```

### Extending

To add a new command:
1.  Update `Session` in `session.py` to handle the new object type or parameter.
2.  Add a new `@click.command` in `freecad_cli.py`.
3.  Update `generate_freecad_script` in `freecad_cli.py` to translate the new object/parameter into FreeCAD Python code.
