---
name: "cli-anything-flowcyto"
description: >-
  Command-line and browser tool for flow cytometry analysis and clinical reporting - parse FCS 2.0/3.0/3.1 files, apply compensation and Logicle scaling, run gating strategies from 15 clinical panel templates, cluster with FlowSOM/t-SNE/PCA, check acquisition quality, compare metrics against age-stratified reference ranges, compute established scores (Matutes, Ogata, WHO/EGIL, EUROclass, PNH, MRD) and produce a structured German report exportable as text, CSV, JSON or HL7 FHIR.
---

# flowcyto

Analyse und Befundung durchflusszytometrischer Daten. Dieselbe Engine treibt
die Kommandozeile und die Browseroberfläche — beide liefern per Konstruktion
identische Zahlen.

> **Zweckbestimmung:** Werkzeug zur Entscheidungsunterstützung, **kein
> zertifiziertes In-vitro-Diagnostikum**. Jede Ausgabe ist vor der Freigabe
> fachlich zu prüfen. Die voreingestellten Referenzbereiche sind
> Literaturwerte und müssen durch laboreigene, validierte Bereiche ersetzt
> werden.

## Installation

```bash
git clone https://github.com/xhuljanoshehu/CLI-Anything.git
cd CLI-Anything/flowcyto/agent-harness
bun install        # nur Entwicklungsabhängigkeiten
```

**Voraussetzungen:** Bun 1.0+ (oder Node 22+). Keine Laufzeitabhängigkeiten,
keine Netzverbindung — Messdaten verlassen den Rechner nicht.

## Nutzung

### Kommandozeile

```bash
bun cli.mjs --help
```

| Befehl | Beschreibung |
|--------|-------------|
| `info <datei>` | Metadaten, Kanäle, Markerzuordnung, Spillover-Matrix |
| `qc <datei>` | Qualitätskontrolle der Messung (7 Prüfungen) |
| `analyse <datei>` | Vollständige Auswertung und Befund |
| `batch <datei...>` | Mehrere Proben, gemeinsame Vergleichstabelle |
| `panels [--marker LISTE]` | Panel-Vorlagen, nach Passung sortiert |
| `marker <name>` | Marker im Lexikon nachschlagen |

**Optionen für `analyse` und `batch`**

| Option | Beschreibung |
|--------|-------------|
| `--panel <id>` | Panel-Vorlage; ohne Angabe wird die beste Passung gewählt |
| `--format text\|json\|csv\|fhir` | Ausgabeformat (Vorgabe `text`) |
| `--ausgabe <datei>` | In Datei schreiben statt auf die Standardausgabe |
| `--alter <jahre>` | steuert die altersabhängigen Referenzbereiche |
| `--pseudonym`, `--geschlecht`, `--material`, `--fragestellung`, `--einsender` | Auftragsdaten |
| `--befunder <name>` | ohne Eintrag bleibt die Freigabe gesperrt |
| `--referenzen <datei.json>` | laboreigene Referenzbereiche einspielen |
| `--beads <n,beadsProTest,volumen>` | Absolutzahlen, Einplattformverfahren |
| `--blutbild <schritt,wert>` | Absolutzahlen, Zweiplattformverfahren |
| `--ohne-kompensation` | Spillover-Korrektur abschalten |

### Beispiele

```bash
# Datei sichten
bun cli.mjs info probe.fcs

# Befund mit Referenzbewertung für einen 45-Jährigen
bun cli.mjs analyse probe.fcs --panel tbnk --alter 45 --befunder "Dr. Muster"

# Maschinenlesbar für ein Laborinformationssystem
bun cli.mjs analyse probe.fcs --format fhir --ausgabe befund.json

# Verlaufsreihe als Vergleichstabelle
bun cli.mjs batch lauf/*.fcs --panel pnh --format csv --ausgabe verlauf.csv

# Absolutzahlen über Zählbeads
bun cli.mjs analyse probe.fcs --panel tbnk --beads 5000,50000,50
```

### Browseroberfläche

```bash
bun run build      # erzeugt dist/flowcyto.html
```

Die erzeugte Datei ist in sich geschlossen und wird per Doppelklick geöffnet.
Sie bietet interaktives Gating, Dichte-, Kontur- und Histogrammdarstellungen,
Clusteranalyse, Qualitätsbericht und den Befundeditor mit Freigabe nach dem
Vier-Augen-Prinzip.

## Panel-Vorlagen

`tbnk`, `akute-leukaemie`, `cll`, `klonalitaet-b`, `mds`, `pnh`, `cd34`,
`mrd-all`, `plasmazellen`, `euroclass`, `treg`, `bat`, `dhr`, `thrombozyten`,
`tzell-aberranz`

Jede Vorlage beschreibt Marker, Gating-Strategie, Kennzahlen, Scores und
fachliche Hinweise. `bun cli.mjs panels --marker CD45,CD3,CD4,...` zeigt, welche
Vorlage zu einem gemessenen Panel passt.

## Eingabeformate

- FCS 2.0 / 3.0 / 3.1 — Integer (beliebige Bitbreite, `$PnR`-Maskierung),
  32-Bit-Float, 64-Bit-Double, ASCII; beide Byte-Ordnungen; Supplemental-TEXT;
  Rücklinearisierung logarithmisch aufgezeichneter Kanäle (`$PnE`, `$PnG`)
- CSV/TSV-Ereignistabellen mit automatischer Trennzeichen- und Markererkennung
- Kompensationsmatrizen als CSV aus der Gerätesoftware
- Referenzbereiche als JSON

## Ausgabeformate

Text (Archiv, LIS-Freitext), CSV (Kennzahlen), JSON (vollständiger Befund),
HL7-FHIR-R4-Bundle (DiagnosticReport, Observations, Specimen, Patient).
LOINC-Codes werden **nicht** erraten: jede Beobachtung erhält einen lokalen
Code, den das Labor über `codeMapping` auf geprüfte LOINC-Codes abbildet.

## Rückgabewerte

`0` bei Erfolg, `1` bei Fehler (unlesbare Datei, unbekanntes Panel, unbekannter
Befehl). `batch` überspringt fehlerhafte Dateien, meldet sie auf der
Standardfehlerausgabe und gibt weiterhin `0` zurück.

## Tests

```bash
bun test          # 105 Tests: Kern, Auswertungskette, CLI
bun run smoke     # Rauchtest im echten Browser (Chromium)
```
