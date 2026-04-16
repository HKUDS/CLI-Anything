# Attribution

This harness adapts the CLI-Anything methodology for NotebookLM.

## Acknowledgements

- **CLI-Anything**
  - Project: https://github.com/HKUDS/CLI-Anything
  - Methodology: https://github.com/HKUDS/CLI-Anything/blob/main/cli-anything-plugin/HARNESS.md
  - We follow its agent-native CLI conventions, including REPL-first design, JSON output, package layout, and test documentation patterns.

- **notebooklm-py**
  - Project: https://github.com/teng-lin/notebooklm-py
  - PyPI: https://pypi.org/project/notebooklm-py/
  - This harness is designed to interoperate with the installed `notebooklm` CLI distributed by notebooklm-py.

- **Google NotebookLM**
  - Product help: https://support.google.com/notebooklm/answer/16206563
  - NotebookLM is a Google product. This harness is unofficial and not affiliated with or endorsed by Google.

## Design Boundary

This project prefers composition over copying:

- wrap the installed `notebooklm` CLI
- document upstream dependencies and policies
- avoid vendoring third-party NotebookLM implementation code into this repository

If you extend this harness, preserve these acknowledgements and keep the unofficial / experimental disclaimer intact.
