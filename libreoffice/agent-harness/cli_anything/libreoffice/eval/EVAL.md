# LibreOffice CLI — Eval Tasks

```bash
cli-anything-eval run --harness cli_anything.libreoffice.eval.tasks --name LibreOffice
```

## Tasks

| ID | Name | Backend | Notes |
| --- | --- | --- | --- |
| export_odt | ODT export | none (native ODF) | create -> paragraph -> export ODT; verify file_size > 0 |
| export_pdf | PDF export | libreoffice (skipped if missing) | headless conversion; verify %PDF- magic bytes |
