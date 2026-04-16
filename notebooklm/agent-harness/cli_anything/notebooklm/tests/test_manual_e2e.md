# Manual E2E Checklist

1. Run `notebooklm login`.
2. Run `cli-anything-notebooklm auth status`.
3. Run `cli-anything-notebooklm notebook list`.
4. Create a temporary notebook with `cli-anything-notebooklm notebook create "CLI Anything Smoke Test"`.
5. Add a simple text or URL source.
6. Run `cli-anything-notebooklm chat ask "Summarize the notebook."`.
7. Generate one artifact, such as a report.
8. Download the artifact to a temporary local path.
9. Delete the temporary notebook manually after verification.
