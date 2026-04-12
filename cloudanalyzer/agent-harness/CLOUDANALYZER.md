# CloudAnalyzer CLI Harness — Architecture

## Overview

CloudAnalyzer is a **CLI-first** Python package for point cloud QA. Unlike most
CLI-Anything harnesses that bridge a GUI application to the command line,
this harness wraps an existing CLI tool to provide:

1. Standardized Click interface with `--json` on every command
2. Project/session state management with undo/redo
3. SKILL.md for agent discovery
4. REPL mode

## Backend Strategy

Since CloudAnalyzer is a Python package, the backend (`ca_backend.py`) imports
CloudAnalyzer functions directly — no subprocess invocation needed. This makes
the harness faster and more reliable than subprocess-based approaches.

Call paths go through `ca_backend`: handlers in `cloudanalyzer_cli.py` do not
import `ca.*` directly.

## Command Mapping

| Harness Group | CloudAnalyzer Command(s) |
|---|---|
| evaluate run | ca.evaluate.evaluate |
| evaluate compare | ca.compare.run_compare |
| evaluate diff | ca.diff.run_diff |
| evaluate batch | ca.batch.batch_evaluate |
| evaluate ground | ca.ground_evaluate.evaluate_ground_segmentation |
| evaluate pipeline | ca.pipeline.run_pipeline |
| trajectory evaluate | ca.trajectory.evaluate_trajectory |
| trajectory batch | ca.batch.trajectory_batch_evaluate |
| trajectory run-evaluate | ca.run_evaluate.evaluate_run |
| check run | ca.core.run_check_suite |
| check init | ca.core.render_check_scaffold |
| baseline decision | ca.core.summarize_baseline_evolution |
| baseline save / list | ca.baseline_history.* |
| process * | ca.downsample / split / sample / filter / merge / convert |
| inspect view | ca.view.view |
| inspect web / web-export | ca.web.serve / export_static_bundle |
| info show | ca.info.get_info |

## State Model

The project JSON tracks:
- Loaded cloud and trajectory file paths
- QA results from evaluation commands
- Operation history with timestamps
- Session settings

Operations are recorded automatically and support undo/redo via
the Session class.
