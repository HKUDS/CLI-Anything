# Tesseract CLI-Anything Skill

## Purpose
Provide a REPL-driven interface to Tesseract (tesseract).

## Commands
- `ocr <image>`
- `ocr <image> --lang L`
- `langs`
- `pdf <image>`
- `batch <images...> --output-dir D`

## Usage Pattern
All commands use subprocess to call tesseract.
Session provides undo/redo via snapshots.
