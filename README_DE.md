<h1 align="center"><img src="assets/icon.png" alt="" width="64" style="vertical-align: middle;">&nbsp; CLI-Anything: Jede Software Agent-Native machen</h1>

<div align="center">
<a href="https://trendshift.io/repositories/22991" target="_blank"><img src="https://trendshift.io/api/badge/repositories/22991" alt="HKUDS%2FCLI-Anything | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>

<p align="center">
  <strong>Die Software von heute ist für Menschen👨‍💻. Die Nutzer von morgen sind Agenten🤖.<br>
CLI-Anything: Die Brücke zwischen KI-Agenten und der Software der Welt</strong><br>
</p>

**🌐 [CLI-Hub](https://hkuds.github.io/CLI-Anything/)**: Alle von der Community gebauten CLIs auf **[CLI-Hub](https://hkuds.github.io/CLI-Anything/)** entdecken — mit einem Befehl installieren. Du willst dein eigenes CLI beitragen? [PR einreichen](https://github.com/HKUDS/CLI-Anything/blob/main/CONTRIBUTING.md) — der Hub aktualisiert sich sofort.

<p align="center">
  <a href="#-schnellstart"><img src="https://img.shields.io/badge/Quick_Start-5_min-blue?style=for-the-badge" alt="Schnellstart"></a>
  <a href="#-demonstrationen"><img src="https://img.shields.io/badge/Demos-18_Apps-green?style=for-the-badge" alt="Demos"></a>
  <a href="#-testergebnisse"><img src="https://img.shields.io/badge/Tests-2%2C269_Passing-brightgreen?style=for-the-badge" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-yellow?style=for-the-badge" alt="Lizenz"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/click-≥8.0-green" alt="Click">
  <img src="https://img.shields.io/badge/pytest-100%25_pass-brightgreen" alt="Pytest">
  <img src="https://img.shields.io/badge/coverage-unit_%2B_e2e-orange" alt="Coverage">
  <img src="https://img.shields.io/badge/output-JSON_%2B_Human-blueviolet" alt="Output">
  <a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
<a href="https://github.com/HKUDS/.github/blob/main/profile/README.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
</p>

**Ein Befehl**: Mache jede Software agent-bereit für Pi, OpenClaw, nanobot, Cursor, Claude Code usw.&nbsp;&nbsp;[**English**](README.md) | [**中文文档**](README_CN.md) | [**日本語ドキュメント**](README_JA.md)

<p align="center">
  <img src="assets/cli-typing.gif" alt="CLI-Anything Tipp-Demo" width="800">
</p>

<p align="center">
  <img src="assets/teaser.png" alt="CLI-Anything Teaser" width="800">
</p>

---

## 📰 Neuigkeiten

> Danke an die Community für die unschätzbaren Beiträge! Täglich kommen weitere Updates dazu.

- **2026-05-20** 🎛️ **Rekordbox CLI** gemerged (#252) mit abgesicherten SQLCipher-Schreibpfaden, Backup-Pflicht bei erzwungenen Schreibvorgängen, Smoke-Coverage und Root-Skill-Sync. 📚 **Calibre CLI** gemerged (#223) mit Library-/Suche-/Metadaten-/Konvertierungs-/Export-Workflows, 41 Unit-Tests, echtem Calibre-E2E-Nachweis und Root-Skill-Validierung. 🧊 **3MF CLI** gemerged (#209) mit Mesh-Inspektion, Hole-Resizing, Reparatur, Vergleich und erhaltenen Triangle-Attributen. 🎙️ **MiniMax CLI** gemerged (#189) mit Chat-/TTS-Workflows, JSON-sicherem Modell-/Voice-Listing, REPL-Quote-Handling und Smoke-/E2E-Coverage. 🎮 **UEAtelier** in der Registry aufgenommen (#297) als Unreal-Editor-MCP-Self-Extension-Workbench mit Python-CLI-Proxy.

- **2026-05-19** 🛠️ Bestehende Harnesses haben einen Quality-/Security-Pass bekommen — **Zoom** lädt Recordings über direkte URLs herunter (#294), **Obsidian**-Suche nutzt jetzt die Vendor-Content-Types der Local REST API (#289), **LibreOffice** Headless-Konvertierung läuft robuster auf macOS (#290), und XML-/SVG-/ODF-/MLT-/MusicXML-/CSL-Parsing routet untrusted Input nun durch `defusedxml` (#296).

- **2026-05-18** 📈 README-Präsentation aufgefrischt mit dem Trendshift-Badge und zentriertem Projekt-Header-Feinschliff (#285, #286); der Landing-Bereich bleibt auf Discovery und Projektdynamik fokussiert.

- **2026-05-17** 🌐 **CLI-Hub**-Registry-Handling wurde gehärtet (#281) — Registry-Einträge werden jetzt vor dem `_source`-Tagging kopiert, damit gecachte oder gemockte Registry-Daten nicht mehr in-place mutiert werden.

- **2026-05-16** 🔧 **n8n** hat den REPL-Banner-Crash-Fix bekommen, der später nach main gemerged wurde (#280), womit der Start-Pfad ohne Subcommand interaktiv wieder funktioniert — inklusive Regression-Coverage.

<details>
<summary>Frühere Neuigkeiten (10.–18. April)</summary>

- **2026-04-18** 🧩 **Alle SKILL.md-Dateien werden jetzt unter dem Top-Level-Verzeichnis `skills/` vereinheitlicht** — jeder CLI-Skill lässt sich aus einer einzigen kanonischen Quelle installieren via `npx skills add HKUDS/CLI-Anything --skill <skill-name> -g -y`. Außerdem haben wir Root-Skill-Validierungs-CI ergänzt, Contribution-/PR-Docs sowie REPL-Skill-Path-Hinweise auf das neue Layout angepasst und das **CLI-Hub**-Install-First-Frontend rund um den neuen `npx skills`-Flow überarbeitet.

- **2026-04-17** 🌐 **CLI-Hub** hat einen weiteren Install-UX-Pass bekommen — öffentliche Registry-Metadaten und Skill-Coverage wurden geschärft, das Visit-Counting korrigiert und das Web-Hub weiter verfeinert. 🧪 **Shotcut**-Render-Output-Dauer wurde gefixt (#92). 📝 **SKILL**-Contribution-Pfade wurden für den neuen Docs-Flow korrigiert (#224), und der Skill-Generator behandelt leere Intros jetzt sicher (#203).

- **2026-04-16** 🗺️ **QGIS CLI** gemerged (#207) — ein vollständiges GIS-/Map-Authoring-Harness ist gelandet. 🧬 **UniMol Tools CLI** gemerged (#219) für Molekül-Modelling-Workflows. 🌐 **CLI-Hub** hat zudem weitere öffentliche CLIs aufgenommen, darunter **py4csr**, seinen generierten Meta-Skill aufgefrischt, SKILL-Contribution-Docs korrigiert und die `apt-get`-Paket-Extraktion in der Skill-Generierung gefixt (#204).

- **2026-04-16** 📈 **Unreal Insights CLI** ausgebaut — Background-Capture-Session-Steuerung ergänzt (`capture start/status/snapshot/stop`), Engine-Root-passende `UnrealInsights.exe`-Resolution-/Build-Flows hinzugefügt und Docs/Tests für den neuen Orchestrierungs-Workflow überarbeitet.

- **2026-04-15** 🌐 **CLI-Hub** auf **v0.2.0** aktualisiert — das PyPI-Paket unterstützt jetzt öffentliche CLIs aus mehreren Install-Quellen (`pip`, `npm`, `brew`, gebündelte/Systemtools), gestützt auf eine neue `public_registry.json`. Das Hub-Frontend wurde mit getrennten Decks für **CLI-Anything CLIs** und **Public CLIs** neu gestaltet, und Live-End-to-End-Checks decken jetzt echte Install-, Update- und Uninstall-Flows über pip- und npm-Pakete hinweg ab.

- **2026-04-14** 🧭 **Safari CLI** gemerged (#212) und in die Hub-Registry aufgenommen — Browser-Automation via `safari-mcp`. 🎬 **Kdenlive** hat zudem Kompatibilitäts-Fixes für Gen-5-Project-Output und ungültige Projekt-Generierung bekommen.

- **2026-04-13** 📓 **Obsidian CLI** gemerged (#211) — Knowledge-Management-Harness via Local REST API mit 48 Unit-Tests und 7 E2E-Tests. ⛓️ **Eth2-Quickstart CLI** gemerged (#195) — Ethereum-Staking-Node-Management-Harness. 📚 **Zotero CLI** auf v0.4.1 aktualisiert (#201) — wird jetzt aus seinem Standalone-Repo geliefert, und CLI-Hub unterstützt jetzt remote `skill_md`-URLs.

- **2026-04-11** 🔗 **n8n CLI** gemerged (#188) — Workflow-Automation-Harness für selbst gehostete Automation-Flows. 🔧 **Exa CLI**-Fix (#205) ergänzt den `x-exa-integration`-Header für Usage-Tracking. 📦 **CLI-Hub** hat zudem seinen PyPI-Auto-Publish-Workflow und eine Package-Refresh-Pipeline bekommen.

- **2026-04-10** 📦 **CLI-Hub Package Manager** gelauncht — `pip install cli-anything-hub`, um CLI-Anything-Harnesses aus einem Befehl heraus zu browsen, zu suchen, zu installieren, zu aktualisieren und zu deinstallieren. Das Web-Hub hat zudem seinen ersten Install-fokussierten Frontend-Refresh und die „Empower yourself"-Toolkit-Karte bekommen.

</details>

<details>
<summary>Frühere Neuigkeiten (1.–9. April)</summary>

- **2026-04-09** 🧹 Cleanup- und Docs-Pass (#200) — Openscreen-Test-Zwischensummen gefixt, Openscreen ins chinesische README und die Projektstruktur aufgenommen und die `/cli-anything`-Befehlssyntax in den Docs klargestellt.

- **2026-04-08** 🎬 **Openscreen CLI** gemerged (#183) — Screen-Recording-Editor-Harness mit 101 Tests. ☁️ **CloudAnalyzer CLI** gemerged (#181) — Cloud-Cost-Analysis-Harness mit 27 Befehlen. 🌊 **SeaClip / PM2 / ChromaDB**-Harnesses gemerged (#129).

- **2026-04-07** 🔄 **Dify Workflow CLI** gemerged (#191) — Workflow-Automation-Wrapper. 🔧 **Inkscape** Auto-Save-Fix (#193, behebt #182). 🛡️ **DomShell-Security-Hardening** (#156) — URL-Validierung und DOM-Sanitization für das Browser-CLI. 🥧 **Pi Coding Agent**-Extension gemerged (#178).

- **2026-04-06** 🔍 **Exa CLI** gemerged (#172) — KI-gestütztes Web-Search-und-Answers-Harness. 🎮 **Godot CLI** gemerged (#140) — Game-Engine-Harness mit voller Demo-Game-E2E-Pipeline. ☁️ **CloudAnalyzer** Review-Fixes und Frontend-Verbesserungen sind ebenfalls gelandet.

- **2026-04-03** 🧪 **WireMock CLI** gemerged (#170) — HTTP-Mock-Server-Harness für API-Tests. 🥧 **Pi Coding Agent**-Extension-Support ist ebenfalls gelandet, und CLI-Demo-Aufzeichnungen wurden den Docs hinzugefügt.

- **2026-04-01** ⚔️ **Slay the Spire II CLI** gemerged (#148) — Deck-Building-Roguelike-Harness. 🎥 **VideoCaptioner CLI** gemerged (#166) — KI-gestütztes Video-Captioning-Harness. 🛰️ **IntelWatch** wurde der Registry für B2B-OSINT-Workflows hinzugefügt.

</details>

<details>
<summary>Frühere Neuigkeiten (23.–30. März)</summary>

- **2026-03-30** 🏗️ **CLI-Anything v0.2.0** — HARNESS.md Progressive-Disclosure-Redesign. Detaillierte Guides nach `guides/` ausgelagert für On-Demand-Loading. Phasen 1–7 sind jetzt durchgehend. Key Principles und Rules in einem einzigen autoritativen Abschnitt zusammengeführt.

- **2026-03-29** 📐 Blender-Skill-Docs aktualisiert — absolute Render-Pfade werden erzwungen und Voraussetzungen korrigiert.

- **2026-03-28** 🌐 **CLIBrowser** in die CLI-Hub-Registry aufgenommen für agent-zugängliche Browser-Automation.

- **2026-03-27** 📚 Zotero-SKILL.md mit Agent-orientierten Constraints erweitert; REPL-Config- und Executable-Resolution-Fixes.

- **2026-03-26** 📖 **Zotero CLI**-Harness für Zotero Desktop gelandet (Library-Management, Sammlungen, Zitationen). Draw.io Custom-ID-Bugfix (#132) und registry.json-Syntax-Fix.

- **2026-03-25** 🎮 **RenderDoc CLI** gemerged für GPU-Frame-Capture-Analyse. FreeCAD für v1.1 aktualisiert. Blender EEVEE-Engine-Name korrigiert. Zoom-Token-Permissions gehärtet.

- **2026-03-24** 🏭 **FreeCAD CLI** ergänzt mit 258 Befehlen über 17 Gruppen. **iTerm2**- und **Teltonika RMS**-Harnesses in die Registry aufgenommen.

- **2026-03-23** 🤖 **CLI-Hub Meta-Skill** gelauncht — Agenten können CLIs jetzt autonom entdecken und installieren. **Krita CLI**-Harness gemerged für Digital Painting.

</details>

<details>
<summary>Frühere Neuigkeiten (11.–22. März)</summary>

- **2026-03-22** 🎵 **MuseScore CLI** gemerged mit Transponieren, Export und Instrument-Management.

- **2026-03-21** 🔧 Infrastruktur-Verbesserungen — Test-Harnesses und Dokumentation über mehrere CLIs hinweg überarbeitet. Erweiterte Windows-Kompatibilität für mehrere Backends.

- **2026-03-20** 🌐 **Novita AI** CLI ergänzt für OpenAI-kompatiblen API-Zugang. Registry-Metadaten-Verbesserungen für bessere Hub-Discovery.

- **2026-03-19** 📦 Verfeinerungen der Paketstruktur über die Harnesses hinweg. Verbesserte SKILL.md-Generierung mit besserer Befehlsdokumentation.

- **2026-03-18** 🧪 Erweiterung der Test-Coverage — zusätzliche E2E-Szenarien und Edge-Case-Validierung über mehrere CLIs hinweg.

- **2026-03-17** 🌐 Den **[CLI-Hub](https://hkuds.github.io/CLI-Anything/)** gelauncht — eine zentrale Registry, in der jedes CLI mit einem einzigen `pip`-Befehl gebrowst, gesucht und installiert werden kann.

- **2026-03-16** 🤖 **SKILL.md-Generierung** ergänzt (Phase 6.5) — jedes generierte CLI bringt jetzt eine KI-entdeckbare Skill-Definition mit.

- **2026-03-15** 🐾 Support für **OpenClaw** aus der Community! Windows-`cygpath`-Guard für plattformübergreifenden Support gemerged.

- **2026-03-14** 🔒 Eine GIMP Script-Fu-Path-Injection-Vulnerability gefixt und die **japanische README**-Übersetzung ergänzt.

- **2026-03-13** 🔌 **Qodercli**-Plugin offiziell als Community-Beitrag gemerged inkl. dedizierter Setup-Skripte.

- **2026-03-12** 📦 **Codex-Skill**-Integration gelandet — CLI-Anything erreicht damit eine weitere KI-Coding-Plattform.

- **2026-03-11** 📞 **Zoom**-Videokonferenz-Harness als 11. unterstützte Anwendung hinzugefügt.

</details>

---

## 🤔 Warum CLI?

Die Kommandozeile ist die universelle Schnittstelle — gleichermaßen für Menschen und KI-Agenten:

• **Strukturiert & komponierbar** — Textbefehle passen perfekt zum Ausgabeformat von LLMs und lassen sich zu komplexen Workflows verketten

• **Leichtgewichtig & universell** — minimaler Overhead, läuft auf jedem System ohne Abhängigkeiten

• **Selbsterklärend** — der `--help`-Flag liefert automatische, vom Agenten entdeckbare Dokumentation

• **Bewährt im Einsatz** — Claude Code führt täglich Tausende reale Workflows über CLIs aus

• **Agent-First-Design** — strukturierte JSON-Ausgaben ersparen jedes Parser-Theater

• **Deterministisch & zuverlässig** — konsistente Ergebnisse machen das Verhalten des Agenten vorhersehbar

## 🚀 Schnellstart

### Voraussetzungen

- **Python 3.10+**
- Die Zielsoftware muss installiert sein (z. B. GIMP, Blender, LibreOffice oder deine eigene Anwendung)
- Unterstützte KI-Coding-Agenten: [Claude Code](#-claude-code) | [OpenClaw](#-openclaw) | [OpenCode](#-opencode) | [Codex](#-codex) | [Qodercli](#-qodercli) | [GitHub Copilot CLI](#-github-copilot-cli) | [Weitere Plattformen](#-weitere-plattformen-bald)

### Wähle deine Agent-Plattform

<details open>
<summary><h4 id="-claude-code">⚡ Claude Code</h4></summary>

**Schritt 1: Marketplace hinzufügen**

CLI-Anything wird als Claude-Code-Plugin-Marketplace auf GitHub bereitgestellt.

```bash
# CLI-Anything-Marketplace hinzufügen
/plugin marketplace add HKUDS/CLI-Anything
```

**Schritt 2: Plugin installieren**

```bash
# cli-anything-Plugin aus dem Marketplace installieren
/plugin install cli-anything
```

Fertig. Das Plugin steht in deinen Claude-Code-Sessions zur Verfügung.

**Schritt 3: Mit einem Befehl ein CLI bauen**

```bash
# /cli-anything:cli-anything <Software-Pfad-oder-Repo>
# Komplettes CLI für GIMP generieren (alle 7 Phasen)
/cli-anything:cli-anything ./gimp

# Hinweis: bei Claude Code < 2.x stattdessen "/cli-anything" verwenden.
```

Das fährt die komplette Pipeline durch:
1. 🔍 **Analyse** — Source-Code scannen, GUI-Aktionen auf APIs mappen
2. 📐 **Design** — Befehlsgruppen, State-Modell und Ausgabeformate entwerfen
3. 🔨 **Implementierung** — Click-CLI mit REPL, JSON-Output, Undo/Redo bauen
4. 📋 **Testplan** — TEST.md mit Unit- und E2E-Testplan erstellen
5. 🧪 **Tests schreiben** — vollständige Test-Suite implementieren
6. 📝 **Dokumentation** — TEST.md mit Ergebnissen aktualisieren
7. 📦 **Veröffentlichung** — `setup.py` anlegen, ins PATH installieren

**Schritt 4 (optional): CLI verfeinern und erweitern**

Nach dem ersten Build lässt sich das CLI iterativ verfeinern — Abdeckung erweitern, fehlende Funktionen ergänzen:

```bash
# Breite Verfeinerung — der Agent analysiert Lücken über alle Funktionen
/cli-anything:refine ./gimp

# Fokussierte Verfeinerung — gezielt auf einen Funktionsbereich
/cli-anything:refine ./gimp "Ich möchte CLI-Unterstützung für Batch-Bildverarbeitung und Filter"
```

Der `refine`-Befehl macht eine Gap-Analyse zwischen vollständiger Software-Funktionalität und aktueller CLI-Abdeckung und implementiert neue Befehle, Tests und Doku für die gefundenen Lücken. Mehrfach ausführbar, um die Abdeckung schrittweise zu erweitern — jeder Lauf ist inkrementell und nicht-destruktiv.

<details>
<summary><strong>Alternative: manuelle Installation</strong></summary>

Wenn du den Marketplace nicht nutzen willst:

```bash
# Repo klonen
git clone https://github.com/HKUDS/CLI-Anything.git

# Plugin in das Plugin-Verzeichnis von Claude Code kopieren
cp -r CLI-Anything/cli-anything-plugin ~/.claude/plugins/cli-anything

# Plugins neu laden
/reload-plugins
```

</details>

</details>

<details>
<summary><h4 id="-opencode">⚡ OpenCode (experimentell)</h4></summary>

**Schritt 1: Commands installieren**

Kopiere die CLI-Anything-Commands **und** die `HARNESS.md` in das Command-Verzeichnis von OpenCode:

```bash
# Repo klonen
git clone https://github.com/HKUDS/CLI-Anything.git

# Globale Installation (in allen Projekten verfügbar)
cp CLI-Anything/opencode-commands/*.md ~/.config/opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md ~/.config/opencode/commands/

# Oder projektweite Installation
cp CLI-Anything/opencode-commands/*.md .opencode/commands/
cp CLI-Anything/cli-anything-plugin/HARNESS.md .opencode/commands/
```

> **Hinweis:** Die `HARNESS.md` ist die Methodik-Spezifikation, auf die alle Commands verweisen. Sie muss im selben Verzeichnis wie die Commands liegen.

Damit kommen fünf Slash-Commands hinzu: `/cli-anything`, `/cli-anything-refine`, `/cli-anything-test`, `/cli-anything-validate`, `/cli-anything-list`.

**Schritt 2: Mit einem Befehl ein CLI bauen**

```bash
# Komplettes CLI für GIMP generieren (alle 7 Phasen)
/cli-anything ./gimp

# Aus einem GitHub-Repo bauen
/cli-anything https://github.com/blender/blender
```

Die Commands laufen als Sub-Tasks und folgen derselben 7-Phasen-Methodik wie in Claude Code.

**Schritt 3 (optional): CLI verfeinern und erweitern**

```bash
# Breite Verfeinerung — der Agent analysiert Lücken über alle Funktionen
/cli-anything-refine ./gimp

# Fokussierte Verfeinerung — gezielt auf einen Funktionsbereich
/cli-anything-refine ./gimp "Batch-Verarbeitung und Filter"
```

</details>

<details>

<summary><h4 id="-qodercli">⚡ Qodercli <sup><code>Community</code></sup></h4></summary>

**Schritt 1: Plugin registrieren**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
bash CLI-Anything/qoder-plugin/setup-qodercli.sh
```

Damit wird das cli-anything-Plugin in `~/.qoder.json` eingetragen. Starte danach eine neue Qodercli-Session.

**Schritt 2: CLI-Anything aus Qodercli nutzen**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "Batch-Verarbeitung und Filter"
/cli-anything:validate ./gimp
```
</details>

<details>

<summary><h4 id="-openclaw">⚡ OpenClaw</h4></summary>

**Schritt 1: Skill installieren**

CLI-Anything stellt eine native OpenClaw-`SKILL.md` bereit. Kopiere sie in das Skill-Verzeichnis von OpenClaw:

```bash
# Repo klonen
git clone https://github.com/HKUDS/CLI-Anything.git

# In den globalen Skill-Ordner installieren
mkdir -p ~/.openclaw/skills/cli-anything
cp CLI-Anything/openclaw-skill/SKILL.md ~/.openclaw/skills/cli-anything/SKILL.md
```

**Schritt 2: CLI bauen**

Nach der Installation lässt sich der Skill in OpenClaw so aufrufen:

`@cli-anything build a CLI for ./gimp`

Der Skill folgt derselben 7-Phasen-Methodik wie Claude Code und OpenCode.

</details>

<details>

<summary><h4 id="-codex">⚡ Codex <sup><code>experimentell</code></sup> <sup><code>Community</code></sup></h4></summary>

**Schritt 1: Skill installieren**

Mitgelieferten Installer ausführen:

```bash
# Repo klonen
git clone https://github.com/HKUDS/CLI-Anything.git

# Skill installieren
bash CLI-Anything/codex-skill/scripts/install.sh
```

Unter Windows PowerShell:

```powershell
.\CLI-Anything\codex-skill\scripts\install.ps1
```

Der Skill landet unter `$CODEX_HOME/skills/cli-anything` (bzw. `~/.codex/skills/cli-anything`, falls `CODEX_HOME` nicht gesetzt ist).

Starte Codex danach neu, damit der Skill erkannt wird.

**Schritt 2: CLI-Anything aus Codex nutzen**

Beschreibe deine Aufgabe in natürlicher Sprache. Zum Beispiel:

```text
Bau mir mit CLI-Anything ein Harness für ./gimp
Verfeinere mit CLI-Anything den Picture-in-Picture-Workflow für ./shotcut
Validiere ./libreoffice mit CLI-Anything
```

Der Codex-Skill wendet dieselbe Methodik an wie das Claude-Code-Plugin und die OpenCode-Commands; das Format der generierten Python-Harnesses bleibt unverändert.
</details>

<details>

<summary><h4 id="-github-copilot-cli">⚡ GitHub Copilot CLI <sup><code>Community</code></sup></h4></summary>

**Schritt 1: Plugin installieren**

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything
copilot plugin install ./cli-anything-plugin
```

Damit ist das CLI-Anything-Plugin im GitHub Copilot CLI installiert und in deinen Copilot-CLI-Sessions sofort verfügbar.

**Schritt 2: CLI-Anything aus dem GitHub Copilot CLI nutzen**

```bash
/cli-anything:cli-anything ./gimp
/cli-anything:refine ./gimp "Batch-Verarbeitung und Filter"
/cli-anything:validate ./gimp
```

</details>

<details>
<summary><h4 id="-weitere-plattformen-bald">🔮 Weitere Plattformen (bald)</h4></summary>

CLI-Anything ist plattformunabhängig konzipiert. Unterstützung für weitere KI-Coding-Agenten ist geplant:

- **Codex** — verfügbar über den mitgelieferten Skill in `codex-skill/`
- **Cursor** — bald
- **Windsurf** — bald
- **Dein Lieblingstool** — Beiträge willkommen! Eine Referenzimplementierung findest du im Verzeichnis `opencode-commands/`.

</details>

### Das generierte CLI nutzen

Egal auf welcher Plattform du es baust — die generierten CLIs funktionieren überall gleich:

```bash
# Ins PATH installieren
cd gimp/agent-harness && pip install -e .

# Von überall aufrufbar
cli-anything-gimp --help
cli-anything-gimp project new --width 1920 --height 1080 -o poster.json
cli-anything-gimp --json layer add -n "Background" --type solid --color "#1a1a2e"

# In die interaktive REPL einsteigen
cli-anything-gimp
```

---

## 🤖 Stärke deine Agenten mit CLI-Hub

CLI-Hub lässt Agenten autonom die CLIs entdecken, installieren und nutzen, die sie für eine Aufgabe brauchen.

```bash
npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y
```

**Ebenfalls verfügbar auf:** [ClawHub](https://clawhub.ai/yuh-yang/cli-anything-hub), [SkillHub](https://www.skillhub.club/web/skills/itsyuhao-cli-anything-hub), [SkillHub.cn](https://skillhub.cn/skills/cli-hub-meta-skill)

Dann prompten:

```text
Finde passende CLI-Software im CLI-Hub und erledige die Aufgabe: ...
```

Der Meta-Skill verweist Agenten auf den Live-Katalog von CLI-Hub, wo sie ein CLI auswählen, es installieren und seine eigene `SKILL.md` für die aufgabenspezifische Nutzung lesen können.

---

## 💡 Die Vision von CLI-Anything: Agent-Native Software bauen

• 🌐 **Universeller Zugang** — jede Software wird über strukturierte CLIs sofort agent-steuerbar.

• 🔗 **Nahtlose Integration** — Agenten steuern jede Anwendung ohne API-Akrobatik, GUI-Hacks, Umbauten oder fragile Wrapper.

• 🚀 **Zukunftsorientiertes Ökosystem** — ein Befehl verwandelt für Menschen gemachte Software in agent-native Werkzeuge.

---

## 🔧 Wann CLI-Anything nutzen?

| Kategorie | So wird es Agent-Native | Repräsentative Beispiele |
|----------|----------------------|----------|
| **📂 GitHub-Repositories** | Jedes Open-Source-Projekt mit automatischer CLI-Generierung in ein agent-steuerbares Tool verwandeln | VSCodium, WordPress, Calibre, Zotero, Joplin, Logseq, Penpot, Super Productivity |
| **🤖 AI/ML-Plattformen** | Mit strukturierten Befehlen Modell-Training, Inferenz-Pipelines und Hyperparameter-Tuning automatisieren | Stable Diffusion WebUI, ComfyUI, InvokeAI, Text-generation-webui, Open WebUI, Fooocus, Kohya_ss, AnythingLLM, SillyTavern |
| **📊 Daten & Analytics** | Programmatische Datenverarbeitung, Visualisierung und statistische Analyse-Workflows | JupyterLab, Apache Superset, Metabase, Redash, DBeaver, KNIME, Orange, OpenSearch Dashboards, Lightdash |
| **💻 Entwickler-Tools** | Code-Editor, Build, Test und Deployment-Prozesse über Command-Interfaces streamlinen | Jenkins, Gitea, Hoppscotch, Portainer, pgAdmin, SonarQube, ArgoCD, OpenLens, Insomnia, Beekeeper Studio |
| **🎨 Kreativ & Medien** | Content-Erstellung, Editing und Rendering-Workflows programmatisch steuern | Blender, GIMP, OBS Studio, Audacity, Krita, Kdenlive, Shotcut, Inkscape, Darktable, LMMS, Ardour |
| **🔬 Wissenschaftliches Rechnen** | Forschungs-Workflows, Simulationen und aufwendige Berechnungen automatisieren | ImageJ, FreeCAD, QGIS, ParaView, Gephi, LibreCAD, Stellarium, KiCad, JASP, Jamovi |
| **🏢 Enterprise & Office** | Business-Anwendungen und Produktivitäts-Tools in agent-zugängliche Systeme verwandeln | NextCloud, GitLab, Grafana, Mattermost, LibreOffice, AppFlowy, NocoDB, Odoo (Community), Plane, ERPNext |
| **📞 Kommunikation & Zusammenarbeit** | Mit strukturierten CLIs Meeting-Scheduling, Teilnehmer-Verwaltung, Aufzeichnungen und Reports automatisieren | Zoom, Jitsi Meet, BigBlueButton, Mattermost |
| **📐 Diagramme & Visualisierung** | Diagramme, Flowcharts, Architekturskizzen und visuelle Dokumente programmatisch erzeugen und bearbeiten | Draw.io (diagrams.net), Mermaid, PlantUML, Excalidraw, yEd |
| **✨ AI-Content-Generation** | Über AI-gestützte Cloud-APIs professionelle Artefakte erzeugen (Slides, Dokumente, Diagramme, Websites, Research Reports) | [AnyGen](https://www.anygen.io), Gamma, Beautiful.ai, Tome |

---

## Hauptmerkmale von CLI-Anything

### Die Lücke zwischen Agent und Software
KI-Agenten können hervorragend schlussfolgern, scheitern aber regelmäßig daran, professionelle Software wirklich zu bedienen. Aktuelle Ansätze sind entweder brüchige UI-Automation, eingeschränkte APIs oder vereinfachte Re-Implementierungen, die 90 % der Funktionen verlieren.

**Die Lösung von CLI-Anything**: Jede professionelle Software in ein agent-natives Werkzeug verwandeln — ohne Funktion einzubüßen.

| **Aktuelle Herausforderung** | **Lösung von CLI-Anything** |
|----------|----------------------|
| 🤖 „KI kann keine echten Tools bedienen" | Direkte Integration mit echten Software-Backends (Blender, LibreOffice, FFmpeg) — voller Funktionsumfang, null Kompromisse |
| 💸 „UI-Automation bricht ständig" | Keine Screenshots, keine Klicks, keine RPA-Fragilität. Reine, strukturierte Kommandozeilen-Zuverlässigkeit |
| 📊 „Agenten brauchen strukturierte Daten" | Eingebautes JSON-Output für nahtlose Agent-Nutzung + menschenlesbares Format zum Debuggen |
| 🔧 „Custom-Integrationen sind teuer" | Ein Claude-Plugin generiert über eine bewährte 7-Phasen-Pipeline automatisch ein CLI für beliebige Codebases |
| ⚡ „Lücke zwischen Prototyp und Produktion" | Über 1.508 Tests und Validierung gegen echte Software. Erprobt an 11 professionellen Anwendungen |

---

## 🎯 Was kannst du mit CLI-Anything machen?

<table>
<tr>
<td width="33%">

### 🛠️ Lass Agenten deine Workflows übernehmen

Egal ob professionell oder Alltag — gib einfach eine Codebase an `/cli-anything`. Für Kreatives: GIMP, Blender, Shotcut. Für den Alltag: LibreOffice, OBS Studio. Keine Quellen? Such eine Open-Source-Alternative und übergib die. Heraus kommt ein vollständiges, agent-taugliches CLI — sofort.

</td>
<td width="33%">

### 🔗 Verstreute APIs zu einem CLI bündeln

Genervt davon, fragmentierte Web-Service-APIs zu jonglieren? Gib die Doku oder das SDK-Manuskript an `/cli-anything`, und der Agent baut dir ein **leistungsstarkes, zustandsbehaftetes CLI**, das einzelne Endpoints zu kohärenten Befehlsgruppen verschmilzt. Statt Dutzenden API-Aufrufen ein Tool — token-sparender und schlagkräftiger zugleich.

</td>
<td width="33%">

### 🚀 GUI-Agenten ersetzen oder verstärken

CLI-Anything **ersetzt GUI-basierte Agenten komplett** — keine Screenshots, kein brüchiges Pixel-Klicken nötig. Noch spannender: Wenn du eine Software per `/cli-anything` durchläufst, kannst du allein mit Code und Terminal **Agent-Tasks, Evaluatoren und Benchmarks synthetisieren** — vollautomatisch, iterativ verbesserbar, deutlich effizienter.

</td>
</tr>
</table>

---

## ✨ ⚙️ So funktioniert CLI-Anything

<table>
<tr>
<td width="50%">

### 🏗️ Vollautomatische 7-Phasen-Pipeline
Von der Codebase-Analyse bis zur PyPI-Veröffentlichung — das Plugin erledigt Architektur-Design, Implementierung, Testplanung, Test-Schreiben und Dokumentation komplett automatisch.

</td>
<td width="50%">

### 🎯 Echte Software-Integration
Direkte Aufrufe in die tatsächliche Anwendung für echtes Rendering. LibreOffice erzeugt PDFs, Blender rendert 3D-Szenen, Audacity verarbeitet Audio über sox. **Null Kompromisse**, **keine Spielzeug-Implementierungen**.

</td>
</tr>
<tr>
<td width="50%">

### 🔁 Smartes Session-Management
Persistenter Projekt-State mit Undo/Redo und eine vereinheitlichte REPL-Oberfläche (ReplSkin) für ein konsistentes interaktives Erlebnis über alle CLIs hinweg.

</td>
<td width="50%">

### 📦 Installation ohne Konfiguration
Ein simples `pip install -e .` fügt `cli-anything-<software>` direkt zum PATH hinzu. Agenten finden die Tools über das Standard-`which`-Kommando. Kein Setup, kein Wrapper.

</td>
</tr>
<tr>
<td width="50%">

### 🧪 Tests auf Produktionsniveau
Mehrschichtige Validierung: Unit-Tests mit synthetischen Daten, End-to-End-Tests gegen echte Dateien und Software, plus CLI-Subprozess-Verifikation der installierten Befehle.

</td>
<td width="50%">

### 🐍 Saubere Paket-Architektur
Alle CLIs leben im `cli_anything.*`-Namespace — kein Konflikt, pip-installierbar, einheitliches Naming: `cli-anything-gimp`, `cli-anything-blender` usw.

</td>
</tr>
</table>

### 🤖 SKILL.md-Generierung

Jedes generierte CLI hat jetzt eine kanonische `SKILL.md` unter `skills/cli-anything-<software>/SKILL.md`. Damit wird das aktuelle Monorepo direkt von `npx skills` konsumierbar, während eine paketierte Kompatibilitätskopie unter `cli_anything/<software>/skills/SKILL.md` das Verhalten installierter Harnesses bewahrt.

**Was SKILL.md bereitstellt:**
- **YAML-Frontmatter** mit Name und Beschreibung für die Agent-Skill-Discovery
- **Befehlsgruppen** mit allen verfügbaren Subcommands dokumentiert
- **Nutzungsbeispiele** für gängige Workflows
- **Agent-spezifische Hinweise** für JSON-Output, Fehlerbehandlung und programmatische Nutzung

SKILL.md-Dateien werden während Phase 6.5 der Pipeline automatisch über `skill_generator.py` erzeugt, der die Metadaten direkt aus den Click-Decoratoren des CLIs, aus `setup.py` und aus dem README extrahiert. Der Generator schreibt jetzt die kanonische Repo-Root-Skill-Datei und frischt die paket-lokale Kompatibilitätskopie auf, die installierte Harnesses nutzen. Innerhalb dieses Repos verweist das REPL-Banner Agenten auf den kanonischen Root-Skill-Pfad; nach `pip install` fällt es auf die paketierte Kopie zurück.

---

## 🎬 Demos aus der Praxis

KI-Agenten nutzen generierte CLIs, um vollständige, brauchbare Artefakte zu produzieren — ganz ohne GUI.

### FreeCAD &mdash; Curiosity Rover via Preview, Live Preview und Trajektorie

> **Harness:** `cli-anything-freecad` | **Preview-Stack:** `preview` + `preview live` + `trajectory.json` | **Artefakt:** Agent-gebauter Curiosity-artiger Rover

Ein Agent baut Schritt für Schritt einen Curiosity-inspirierten Rover auf und veröffentlicht dabei echte FreeCAD-Preview-Bundles, frischt eine Live-Preview-Session auf und protokolliert die Command-zu-Preview-Historie für späteres Replay. Das resultierende Demo zeigt, wie das Artefakt vor dem finalen Showcase Stück für Stück wächst.

<p align="center">
  <img src="assets/demos/freecad-curiosity-preview-trajectory.gif" alt="FreeCAD Curiosity Rover Demo angetrieben von Preview, Live Preview und Trajektorien-Historie" width="860" />
</p>

<p align="center">
  <sub>Das README-GIF wurde aus dem vollständigen lokalen Demo-Video über einen Speed-angepassten, qualitätshohen ffmpeg-Palette-Workflow erzeugt.</sub>
</p>

### Blender &mdash; Orbital Relay Drone via Preview, Live Preview und Trajektorie

> **Harness:** `cli-anything-blender` | **Preview-Stack:** `preview` + `preview live` + `trajectory.json` | **Artefakt:** Agent-gebaute Orbital-Relay-Drohne

Ein Agent nutzt das Blender-Harness, um in einem echten Preview-Loop eine Hard-Surface-Orbital-Relay-Drohne wachsen zu lassen: jede Stufe pusht neue render-gestützte Bundles, die Live-Session verfolgt den aktuellen Head, und die Trajektorie verknüpft jedes Kommando mit dem passenden visuellen Stand. Das Demo endet mit der fertigen Szene, bereit für eine polierte Turntable-Aufnahme.

<p align="center">
  <img src="assets/demos/blender-orbital-relay-drone-preview-trajectory.gif" alt="Blender Orbital-Relay-Drohne Demo angetrieben von Preview, Live Preview und Trajektorien-Historie" width="860" />
</p>

<p align="center">
  <sub>Das README-GIF wurde aus dem vollständigen lokalen Demo-Video über einen Speed-angepassten, qualitätshohen ffmpeg-Palette-Workflow erzeugt.</sub>
</p>

### Draw.io &mdash; HTTPS-Handshake-Diagramm

> **Harness:** `cli-anything-drawio` | **Zeit:** ~4 Min. | **Artefakt:** `.drawio` + `.png`

Ein Agent erstellt von Grund auf ein vollständiges Diagramm zum Lebenszyklus einer HTTPS-Verbindung — TCP-Three-Way-Handshake, TLS-Aushandlung, verschlüsselter Datenaustausch und TCP-Four-Way-Termination — ausschließlich über CLI-Befehle.

<p align="center">
  <img src="assets/demos/drawio-demo.gif" alt="Draw.io-CLI-Demo: Aufbau eines HTTPS-Handshake-Diagramms" width="720" />
</p>

<details>
<summary>Finales Artefakt</summary>
<p align="center">
  <img src="assets/demos/drawio-https-handshake.png" alt="HTTPS-Handshake-Sequenzdiagramm" width="600" />
</p>
</details>

*Beigesteuert von [@zhangxilong-43](https://github.com/zhangxilong-43)*

### Slay the Spire II &mdash; Game-Automatisierung

> **Harness:** `cli-anything-slay-the-spire-ii` | **Artefakt:** Automatisierte Spielsession

Ein Agent spielt über das CLI-Harness einen kompletten Slay-the-Spire-II-Run durch — liest den Spielzustand, wählt Karten, wählt Pfade und trifft strategische Entscheidungen in Echtzeit.

<p align="center">
  <img src="assets/demos/slay-the-spire-ii-gameplay.gif" alt="Slay the Spire II CLI-Gameplay-Demo" width="720" />
</p>

*Beigesteuert von [@TianyuFan0504](https://github.com/TianyuFan0504)*

### VideoCaptioner &mdash; automatisch generierte Untertitel

> **Harness:** `cli-anything-videocaptioner` | **Artefakt:** Untertitelte Videoframes

Ein Agent nutzt das VideoCaptioner-CLI, um automatisch gestaltete Untertitel zu generieren und in Videoinhalte einzublenden — inklusive zweisprachiger Text-Wiedergabe und individueller Formatierung.

<table align="center">
<tr>
<td align="center"><strong>Sub A</strong></td>
<td align="center"><strong>Sub B</strong></td>
</tr>
<tr>
<td><img src="assets/demos/videocaptioner-before.png" alt="Videoframe vor dem Captioning" width="380" /></td>
<td><img src="assets/demos/videocaptioner-after.png" alt="Videoframe nach dem Captioning" width="380" /></td>
</tr>
</table>

*Beigesteuert von [@WEIFENG2333](https://github.com/WEIFENG2333)*

*Weitere CLI-Demos folgen in Kürze.*

---

## 🎬 Demonstrationen

### 🎯 Universell einsetzbar
CLI-Anything funktioniert mit jeder Software, die eine Codebase hat — keine Domänen-Beschränkungen, keine Architektur-Einschränkungen.

### 🏭 Tests auf Professional-Niveau
Getestet an 12 vielfältigen, anspruchsvollen Anwendungen, die für KI-Agenten zuvor unzugänglich waren — von Kreativ-, Produktivitäts-, Kommunikations-, Diagramm- und AI-Content-Bereichen bis hin zu GPU-Debugging.

### 🎨 Breite Domänen-Abdeckung
Von Kreativ-Workflows (Bildbearbeitung, 3D-Modeling, Vektorgrafik) bis zu Produktionstools (Audio, Office, Live-Streaming, Video-Editing).

### ✅ Vollständige CLI-Generierung
Für jede Anwendung wird ein komplettes, produktionsreifes CLI-Interface erzeugt — keine Demo, sondern umfassender Tool-Zugriff, der den vollen Funktionsumfang erhält.

<table>
<tr>
<th align="center">Software</th>
<th align="center">Domäne</th>
<th align="center">CLI-Befehl</th>
<th align="center">Backend</th>
<th align="center">Tests</th>
</tr>
<tr>
<td align="center"><strong>🎨 GIMP</strong></td>
<td>Bildbearbeitung</td>
<td><code>cli-anything-gimp</code></td>
<td>Pillow + GEGL/Script-Fu</td>
<td align="center">✅ 107</td>
</tr>
<tr>
<td align="center"><strong>🧊 Blender</strong></td>
<td>3D-Modeling & Rendering</td>
<td><code>cli-anything-blender</code></td>
<td>bpy (Python-Scripting)</td>
<td align="center">✅ 208</td>
</tr>
<tr>
<td align="center"><strong>✏️ Inkscape</strong></td>
<td>Vektorgrafik</td>
<td><code>cli-anything-inkscape</code></td>
<td>Direkte SVG/XML-Manipulation</td>
<td align="center">✅ 202</td>
</tr>
<tr>
<td align="center"><strong>🎵 Audacity</strong></td>
<td>Audio-Produktion</td>
<td><code>cli-anything-audacity</code></td>
<td>Python wave + sox</td>
<td align="center">✅ 161</td>
</tr>
<tr>
<td align="center"><strong>📄 LibreOffice</strong></td>
<td>Office-Suite (Writer, Calc, Impress)</td>
<td><code>cli-anything-libreoffice</code></td>
<td>ODF-Generierung + Headless-LO</td>
<td align="center">✅ 158</td>
</tr>
<tr>
<td align="center"><strong>📹 OBS Studio</strong></td>
<td>Live-Streaming & Aufnahme</td>
<td><code>cli-anything-obs-studio</code></td>
<td>JSON-Szenen + obs-websocket</td>
<td align="center">✅ 153</td>
</tr>
<tr>
<td align="center"><strong>🎞️ Kdenlive</strong></td>
<td>Video-Editing</td>
<td><code>cli-anything-kdenlive</code></td>
<td>MLT XML + melt-Renderer</td>
<td align="center">✅ 155</td>
</tr>
<tr>
<td align="center"><strong>🎬 Shotcut</strong></td>
<td>Video-Editing</td>
<td><code>cli-anything-shotcut</code></td>
<td>Direktes MLT XML + melt</td>
<td align="center">✅ 154</td>
</tr>
<tr>
<td align="center"><strong>📞 Zoom</strong></td>
<td>Videokonferenzen</td>
<td><code>cli-anything-zoom</code></td>
<td>Zoom REST API (OAuth2)</td>
<td align="center">✅ 22</td>
</tr>
<tr>
<td align="center"><strong>📐 Draw.io</strong></td>
<td>Diagramme</td>
<td><code>cli-anything-drawio</code></td>
<td>mxGraph XML + draw.io CLI</td>
<td align="center">✅ 138</td>
</tr>
<tr>
<td align="center"><strong>✨ AnyGen</strong></td>
<td>AI-Content-Generation</td>
<td><code>cli-anything-anygen</code></td>
<td>AnyGen REST API (anygen.io)</td>
<td align="center">✅ 50</td>
</tr>
<tr>
<td align="center"><strong>🟩 <a href="nsight-graphics/agent-harness/">Nsight Graphics CLI</a></strong></td>
<td>GPU-Debugging & -Profiling</td>
<td><code>cli-anything-nsight-graphics</code></td>
<td>Offizielle ngfx-/ngfx-capture-Orchestrierung + GPU-Trace-Summary</td>
<td align="center">✅ 40</td>
</tr>
<tr>
<td align="center" colspan="4"><strong>Gesamt</strong></td>
<td align="center"><strong>✅ 1.547</strong></td>
</tr>
</table>

> **Alle 1.547 Tests grün — 100 %** — 1.108 Unit-Tests + 439 End-to-End-Tests.

---

## 📊 Testergebnisse

Jedes CLI-Harness durchläuft eine strenge, mehrschichtige Test-Pipeline für Produktions-Zuverlässigkeit:

| Schicht | Was getestet wird | Beispiel |
|-------|---------------|---------|
| **Unit-Tests** | Alle Kern-Funktionen isoliert, mit synthetischen Daten | `test_core.py` — Projekt erstellen, Layer-Operationen, Filter-Parameter |
| **E2E-Tests (nativ)** | Projektdatei-Generierungs-Pipelines | Gültige ODF-ZIP-Struktur, korrektes MLT-XML, wohlgeformtes SVG |
| **E2E-Tests (echtes Backend)** | Echte Software-Aufrufe + Output-Verifikation | LibreOffice → PDF mit `%PDF-`-Magic-Bytes, Blender → gerendertes PNG |
| **CLI-Subprozess-Tests** | Installierte Befehle via `subprocess.run` | `cli-anything-gimp --json project new` → gültiges JSON-Output |

```
================================ Test-Zusammenfassung ================================
gimp          107 passed  ✅   (64 unit + 43 e2e)
blender       208 passed  ✅   (150 unit + 58 e2e)
inkscape      202 passed  ✅   (148 unit + 54 e2e)
audacity      161 passed  ✅   (107 unit + 54 e2e)
libreoffice   158 passed  ✅   (89 unit + 69 e2e)
obs-studio    153 passed  ✅   (116 unit + 37 e2e)
kdenlive      155 passed  ✅   (111 unit + 44 e2e)
shotcut       154 passed  ✅   (110 unit + 44 e2e)
zoom           22 passed  ✅   (22 unit + 0 e2e)
drawio        138 passed  ✅   (116 unit + 22 e2e)
anygen         50 passed  ✅   (40 unit + 10 e2e)
nsight-graphics 40 passed ✅   (36 unit + 4 e2e)
──────────────────────────────────────────────────────────────────────────────
Gesamt       1.547 passed  ✅   100 % Pass-Rate
```

---

## 🏗️ Die Architektur von CLI-Anything

<p align="center">
  <img src="assets/architecture.png" alt="CLI-Anything-Architektur" width="750">
</p>

### 🎯 Zentrale Design-Prinzipien

1. **Echte Software-Integration** — CLIs erzeugen gültige Projektdateien (ODF, MLT XML, SVG) und delegieren das Rendering an die echte Anwendung. **Wir bauen strukturierte Schnittstellen zur Software, keinen Ersatz für sie**.

2. **Flexibles Interaktionsmodell** — alle CLIs laufen im Dual-Mode: zustandsbehaftete REPL für interaktive Agent-Sessions + Sub-Command-Interface für Scripting und Pipelines. **Befehl ohne Argumente ausführen → REPL-Modus**.

3. **Einheitliche User-Experience** — alle generierten CLIs teilen sich dieselbe REPL-Oberfläche (`repl_skin.py`) mit Brand-Banner, gestaltetem Prompt, Command-History, Fortschrittsanzeigen und standardisiertem Formatting.

4. **Agent-Native Design** — jeder Befehl hat einen eingebauten `--json`-Flag für maschinen-strukturierte Daten, dazu menschenlesbare Tabellen für interaktive Nutzung. **Agenten entdecken Funktionen über das Standard-`--help` und `which`**.

5. **Keine Kompromisse bei Abhängigkeiten** — echte Software ist Pflichtvoraussetzung — keine Fallbacks, keine Graceful Degradation. **Fehlt das Backend, scheitern die Tests statt sie zu überspringen — so bleiben echte Funktionen garantiert.**

---

## 📂 Projektstruktur

```
cli-anything/
├── 📄 README.md                          # Englisches README
├── 📁 assets/                            # Bilder und Medien
│   ├── icon.png                          # Projekt-Icon
│   └── teaser.png                        # Teaser-Bild
│
├── 🔌 cli-anything-plugin/               # Claude-Code-Plugin
│   ├── HARNESS.md                        # Methodik-SOP (Single Source of Truth)
│   ├── README.md                         # Plugin-Dokumentation
│   ├── QUICKSTART.md                     # 5-Minuten-Einstieg
│   ├── PUBLISHING.md                     # Publishing-Guide
│   ├── repl_skin.py                      # Vereinheitlichte REPL-Oberfläche
│   ├── commands/                         # Plugin-Command-Definitionen
│   │   ├── cli-anything.md               # Haupt-Build-Befehl
│   │   ├── refine.md                     # Coverage bestehender Harnesses erweitern
│   │   ├── test.md                       # Test-Runner
│   │   └── validate.md                   # Standard-Validierung
│   └── scripts/
│       └── setup-cli-anything.sh         # Setup-Skript
│
├── 🤖 codex-skill/                      # Codex-Skill-Einstiegspunkt
├── 🎨 gimp/agent-harness/               # GIMP CLI (107 Tests)
├── 🧊 blender/agent-harness/            # Blender CLI (208 Tests)
├── ✏️ inkscape/agent-harness/            # Inkscape CLI (202 Tests)
├── 🎵 audacity/agent-harness/           # Audacity CLI (161 Tests)
├── 📄 libreoffice/agent-harness/        # LibreOffice CLI (158 Tests)
├── 📹 obs-studio/agent-harness/         # OBS Studio CLI (153 Tests)
├── 🎞️ kdenlive/agent-harness/           # Kdenlive CLI (155 Tests)
├── 🎬 shotcut/agent-harness/            # Shotcut CLI (154 Tests)
├── 📞 zoom/agent-harness/               # Zoom CLI (22 Tests)
├── 📐 drawio/agent-harness/             # Draw.io CLI (138 Tests)
├── ✨ anygen/agent-harness/             # AnyGen CLI (50 Tests)
└── 🟩 nsight-graphics/agent-harness/    # Nsight Graphics CLI (40 Tests)
```

Jedes `agent-harness/` enthält ein pip-installierbares Python-Paket unter `cli_anything.<software>/` mit Click-CLI, Core-Modulen, Utilities (inklusive `repl_skin.py` und Backend-Wrappern) und einer umfassenden Test-Suite.

---

## 🎯 Plugin-Befehle

| Befehl | Beschreibung |
|---------|-------------|
| `/cli-anything <Software-Pfad-oder-Repo>` | Komplettes CLI-Harness bauen — alle 7 Phasen |
| `/cli-anything:refine <Software-Pfad> [Fokus]` | Bestehendes Harness verfeinern — Gap-Analyse, mehr Coverage |
| `/cli-anything:test <Software-Pfad-oder-Repo>` | Tests laufen lassen und TEST.md mit Ergebnissen aktualisieren |
| `/cli-anything:validate <Software-Pfad-oder-Repo>` | Gegen den HARNESS.md-Standard validieren |

### Beispiele

```bash
# Komplettes CLI für GIMP aus lokaler Quelle bauen
/cli-anything /home/user/gimp

# Aus einem GitHub-Repo bauen
/cli-anything https://github.com/blender/blender

# Bestehendes Harness verfeinern — breite Gap-Analyse
/cli-anything:refine /home/user/gimp

# Mit einem spezifischen Fokus verfeinern
/cli-anything:refine /home/user/shotcut "Video-in-Video- und Picture-in-Picture-Compositing"

# Tests laufen lassen und TEST.md aktualisieren
/cli-anything:test /home/user/inkscape

# Gegen den HARNESS.md-Standard validieren
/cli-anything:validate /home/user/audacity
```

---

## 🎮 Demo: Generiertes CLI im Einsatz

Beispiel dafür, was ein Agent mit `cli-anything-libreoffice` tun kann:

```bash
# Neues Writer-Dokument anlegen
$ cli-anything-libreoffice document new -o report.json --type writer
✓ Writer-Dokument erstellt: report.json

# Inhalt hinzufügen
$ cli-anything-libreoffice --project report.json writer add-heading -t "Q1-Bericht" --level 1
✓ Überschrift hinzugefügt: "Q1-Bericht"

$ cli-anything-libreoffice --project report.json writer add-table --rows 4 --cols 3
✓ 4×3-Tabelle hinzugefügt

# In echtes PDF exportieren via LibreOffice headless
$ cli-anything-libreoffice --project report.json export render output.pdf -p pdf --overwrite
✓ Export abgeschlossen: output.pdf (42.831 Bytes) via libreoffice-headless

# JSON-Modus für Agenten
$ cli-anything-libreoffice --json document info --project report.json
{
  "name": "Q1 Report",
  "type": "writer",
  "pages": 1,
  "elements": 2,
  "modified": true
}
```

### REPL-Modus

```
$ cli-anything-blender
╔══════════════════════════════════════════╗
║       cli-anything-blender v1.0.0       ║
║     Blender CLI for AI Agents           ║
╚══════════════════════════════════════════╝

blender> scene new --name ProductShot
✓ Szene erstellt: ProductShot

blender[ProductShot]> object add-mesh --type cube --location 0 0 1
✓ Mesh hinzugefügt: Cube bei (0, 0, 1)

blender[ProductShot]*> render execute --output render.png --engine CYCLES
✓ Rendering abgeschlossen: render.png (1920×1080, 2,3 MB) via blender --background

blender[ProductShot]> exit
Goodbye! 👋
```

---

## 📖 Das Standard-Playbook: HARNESS.md

`HARNESS.md` ist die definitive SOP, um jede Software über automatische CLI-Generierung agent-zugänglich zu machen.

Sie kodifiziert die bewährten Muster und Methoden, die im Zuge der automatischen Generierung herausgearbeitet wurden.

Das Playbook bündelt die zentralen Erkenntnisse aus dem Bau von 11 unterschiedlichen, produktionsreifen Harnesses.

### Wichtige Lessons-Learned

| Lektion | Beschreibung |
|--------|-------------|
| **Echte Software nutzen** | CLIs müssen die echte Anwendung zum Rendern aufrufen. Nicht Pillow statt GIMP, kein eigener Renderer statt Blender. Gültige Projektdateien generieren → echtes Backend anstoßen. |
| **Render-Lücke** | GUI-Apps wenden Effekte beim Rendern an. Wenn das CLI Projektdateien manipuliert, aber ein naiver Export-Tool verwendet, gehen Effekte stillschweigend verloren. Lösung: nativer Renderer → Filter-Konvertierung → Render-Skript. |
| **Filter-Konvertierung** | Beim Mapping von Effekten zwischen Formaten (MLT → ffmpeg) auf das achten: doppelte Filter zusammenführen, verschachtelte Stream-Reihenfolge, Parameter-Raum-Unterschiede, nicht abbildbare Effekte. |
| **Timecode-Präzision** | Nicht-ganzzahlige Frameraten (29,97 fps) erzeugen kumulative Rundungsfehler. `round()` statt `int()`, Integer-Arithmetik für die Anzeige, ±1-Frame-Toleranz in Tests. |
| **Output-Validierung** | Exit-Code 0 ≠ erfolgreicher Export. Stattdessen prüfen: Magic-Bytes, ZIP-/OOXML-Struktur, Pixel-Analyse, Audio-RMS-Pegel, Längen-Checks. |

> Vollständige Methodik hier: [`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md)

---

## 📦 Installation & Nutzung

### Für CLI-Hub-Nutzer

```bash
# Package Manager installieren
pip install cli-anything-hub

# CLIs browsen, suchen, inspizieren und installieren
cli-hub list
cli-hub search <query>
cli-hub info <name>
cli-hub install <name>

# Installierte CLIs verwalten
cli-hub update <name>
cli-hub uninstall <name>
cli-hub launch <name> [args...]
```

### Für Plugin-Nutzer (Claude Code)

```bash
# Marketplace hinzufügen und installieren (empfohlen)
/plugin marketplace add HKUDS/CLI-Anything
/plugin install cli-anything

# CLI für eine Software mit Codebase bauen
/cli-anything <Software-Name>
```

### Für die generierten CLIs

```bash
# Generiertes CLI installieren
cd <software>/agent-harness
pip install -e .

# Verifizieren
which cli-anything-<software>

# Nutzen
cli-anything-<software> --help
cli-anything-<software>                    # REPL starten
cli-anything-<software> --json <command>   # JSON-Output für Agenten
```

### Tests ausführen

```bash
# Tests für ein bestimmtes CLI laufen lassen
cd <software>/agent-harness
python3 -m pytest cli_anything/<software>/tests/ -v

# Force-Installed-Modus (empfohlen für Verifikation)
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/<software>/tests/ -v -s
```

---

## 🤝 Mitwirken

Beiträge sind willkommen! CLI-Anything ist auf Erweiterbarkeit ausgelegt:

- **Neue Software-Targets** — generiere mit dem Plugin ein CLI für eine beliebige Codebase und reiche das Harness über [`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md) ein.
- **Methodik-Verbesserungen** — PRs gegen `HARNESS.md` mit neuen Lessons-Learned
- **Plugin-Erweiterungen** — neue Befehle, bessere Phasen, robustere Validierung
- **Test-Coverage** — mehr E2E-Szenarien, Edge-Cases, Workflow-Tests

### Einschränkungen

- **Starkes Foundation-Modell nötig** — CLI-Anything braucht ein Modell der Frontier-Klasse (z. B. Claude Opus 4.6, Claude Sonnet 4.6, GPT-5.4), damit die Harness-Generierung zuverlässig ist. Schwächere oder kleinere Modelle erzeugen ggf. unvollständige oder fehlerhafte CLIs, die viel manuelle Nacharbeit erfordern.
- **Abhängig von verfügbarem Quellcode** — die 7-Phasen-Pipeline analysiert und generiert auf Basis des Source-Codes. Liefert die Zielsoftware nur kompilierte Binaries (Decompilation nötig), sinken Qualität und Abdeckung des Harness deutlich.
- **Iterative Verfeinerung kann nötig sein** — ein einzelner `/cli-anything`-Lauf deckt nicht zwangsläufig alle Funktionen vollständig ab. Ein oder mehrere `/refine`-Läufe sind oft erforderlich, um Performance und Coverage des CLIs auf Produktionsniveau zu bringen.

### Roadmap

- [ ] Unterstützung für weitere Anwendungs-Kategorien (CAD, DAW, IDE, EDA, Science-Tools)
- [ ] Benchmark-Suite für Agent-Task-Completion-Rates
- [ ] Community-beigesteuerte CLI-Harnesses für In-House- bzw. Custom-Software
- [ ] Integration mit zusätzlichen Agent-Frameworks neben Claude Code
- [ ] Unterstützung, Closed-Source-Software und Web-Service-APIs in CLIs zu verpacken
- [ ] Zusätzlich zum CLI eine `SKILL.md` für Agent-Skill-Discovery und -Orchestrierung mitgenerieren

---

## 📖 Dokumentation

| Dokument | Beschreibung |
|----------|-------------|
| [`cli-anything-plugin/HARNESS.md`](cli-anything-plugin/HARNESS.md) | Methodik-SOP — Single Source of Truth |
| [`cli-anything-plugin/README.md`](cli-anything-plugin/README.md) | Plugin-Dokumentation — Befehle, Optionen, Phasen |
| [`cli-anything-plugin/QUICKSTART.md`](cli-anything-plugin/QUICKSTART.md) | 5-Minuten-Einstieg |
| [`cli-anything-plugin/PUBLISHING.md`](cli-anything-plugin/PUBLISHING.md) | Distribution- und Publishing-Guide |

Jedes generierte Harness enthält zusätzlich:
- `<SOFTWARE>.md` — die anwendungsspezifische Architektur-SOP
- `tests/TEST.md` — Testplan und Ergebnis-Dokumentation

---

## ⭐ Star-Verlauf

Wenn CLI-Anything dir hilft, deine Software agent-native zu machen, freuen wir uns über einen Stern! ⭐

<div align="center">
  <a href="https://star-history.com/#HKUDS/CLI-Anything&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
      <img alt="Star-History-Diagramm" src="https://api.star-history.com/svg?repos=HKUDS/CLI-Anything&type=Date" />
    </picture>
  </a>
</div>

---

## 📄 Lizenz

Apache License 2.0 — frei nutzbar, modifizierbar und verteilbar.

---

<div align="center">

**CLI-Anything** — *Jede Software mit Codebase agent-native machen.*

<sub>Methodik für das Zeitalter der KI-Agenten | 11 professionelle Software-Demos | 1.508 bestandene Tests</sub>

<br>

<img src="assets/icon.png" alt="CLI-Anything-Icon" width="80">

</div>

<p align="center">
  <em>Danke, dass du dir CLI-Anything ansiehst ✨</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.CLI-Anything&style=for-the-badge&color=00d4ff" alt="Views">
</p>
