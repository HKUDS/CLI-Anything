# FlowCyto — Befundwerkzeug für durchflusszytometrische Daten

Vollständige Auswertungskette für Durchflusszytometrie in einer einzigen,
offline lauffähigen HTML-Datei: FCS einlesen, kompensieren, transformieren,
gaten, clustern, Qualität prüfen, Kennzahlen gegen Referenzbereiche bewerten,
Scores berechnen und einen strukturierten Befund erzeugen.

> **Zweckbestimmung.** Werkzeug zur Entscheidungsunterstützung, **kein
> zertifiziertes In-vitro-Diagnostikum**. Jede Auswertung, jeder Textbaustein
> und jeder Vorschlag ist vor der Freigabe fachlich zu prüfen und ärztlich zu
> verantworten. Die mitgelieferten Referenzbereiche sind Literatur-
> Orientierungswerte und müssen vor Routineeinsatz durch laboreigene,
> validierte Bereiche ersetzt werden (Import/Export als JSON ist eingebaut).

---

## Schnellstart

```bash
bun install          # keine Laufzeitabhängigkeiten, nur Entwicklung
bun run build        # erzeugt dist/flowcyto.html
bun test             # 86 Tests, Kern und Auswertungskette
bun run smoke        # Rauchtest im echten Browser (Chromium)
```

`dist/flowcyto.html` per Doppelklick öffnen. Kein Server, keine Installation,
keine Netzverbindung — **Messdaten verlassen den Rechner nicht.**

---

## Warum eine einzige Datei

Patientenbezogene Messdaten dürfen ein Laborsystem nicht verlassen. Deshalb
läuft alles im Browser des Anwenders: Parser, Kompensation, Gating, Clustering
und Befunderstellung. Der Build inliniert sämtliche Module und das CSS; der
Build-Schritt bricht ab, sobald die Datei auf eine externe Ressource verweist.

---

## Aufbau

Es gibt genau **eine** Quelle der Wahrheit. Jede Ansicht liest über Selektoren,
jede Änderung läuft über den Store zurück. Deshalb können Plot, Statistik-
tabelle, Qualitätsbericht und Befund nicht auseinanderlaufen — was im Plot
steht, steht zwangsläufig auch im Befund.

```
                        ┌──────────────────┐
   FCS / CSV ──────────▶│ core/fcs.js      │  Parser (FCS 2.0/3.0/3.1)
                        └────────┬─────────┘
                                 ▼
                        ┌──────────────────┐
                        │ core/store.js    │  Zustand + Versionszähler
                        └────────┬─────────┘
                                 ▼
                        ┌──────────────────┐
                        │ core/data.js     │  ← einzige Datenschicht
                        │ Kompensation →   │    (zwischengespeichert)
                        │ Transformation   │
                        └────────┬─────────┘
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
     │ core/gating  │   │ core/stats   │   │ core/cluster │
     └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
            └──────────────────┼──────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ core/strategy.js    │  führt Panel-Vorlagen aus
                    └──────────┬──────────┘
                               ▼
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
  ┌───────────────┐   ┌────────────────┐   ┌────────────────┐
  │ knowledge/    │   │ core/qc.js     │   │ ui/plot.js     │
  │ rules, panels │   │                │   │ ui/main.js     │
  └───────┬───────┘   └───────┬────────┘   └────────────────┘
          └───────────────────┼───────────────┐
                              ▼               ▼
                   ┌────────────────┐  ┌────────────┐
                   │ report/befund  │  │ report/fhir│
                   └────────────────┘  └────────────┘
```

| Modul | Aufgabe |
|---|---|
| `core/store.js` | Zustand, Event-Bus, Memoisierung über Versionszähler |
| `core/fcs.js` | FCS 2.0/3.0/3.1 (I/F/D/A, beide Byte-Ordnungen, `$PnE`-Linearisierung, Supplemental-TEXT), CSV-Import |
| `core/matrix.js` | Inversion, Jacobi-Eigenzerlegung — von Kompensation **und** PCA genutzt |
| `core/transform.js` | linear, log10, arcsinh, **Logicle** (Moore & Parks) mit LUT-Beschleunigung |
| `core/compensation.js` | Spillover-Zuordnung, Inversion, Feinjustage, Plausibilitätsprüfung |
| `core/data.js` | zentrale Datenschicht: kompensierte und skalierte Kanalwerte, zwischengespeichert |
| `core/gating.js` | Rechteck/Polygon/Ellipse/Intervall/Quadrant/Boolesch, Hierarchie, Auto-Gates |
| `core/stats.js` | Perzentile, MFI, rCV, Histogramme, 2-D-Dichte, Otsu, KS, Overton, Poisson-CI, LOD/LLOQ |
| `core/cluster.js` | PCA, k-Means, FlowSOM (SOM + Metacluster + Spannbaum), t-SNE |
| `core/qc.js` | 7 Prüfungen der Messqualität mit Gesamtbewertung |
| `core/strategy.js` | führt Panel-Vorlagen aus, stellt den Auswertungskontext bereit |
| `knowledge/markers.js` | ~120 Marker mit Linie und klinischer Bedeutung |
| `knowledge/panels.js` | 13 Panel-Vorlagen mit **ausführbarer** Gating-Strategie |
| `knowledge/reference.js` | altersgestaffelte Referenzbereiche, laboreigene importierbar |
| `knowledge/entities.js` | Entitätskatalog für die Differentialdiagnose |
| `knowledge/rules.js` | Scores und Regelauswertung |
| `report/befund.js` | strukturierter Befund + Textfassung + CSV |
| `report/fhir.js` | HL7-FHIR-Bundle (R4) |

---

## Was das Werkzeug kann

### Einlesen
FCS 2.0 / 3.0 / 3.1 in allen Standard-Datentypen (Integer beliebiger Bitbreite
mit `$PnR`-Maskierung, 32-Bit-Float, 64-Bit-Double, ASCII), beide Byte-
Ordnungen, Supplemental-TEXT, Offsets jenseits der Header-Grenze,
Rücklinearisierung gerätelogarithmierter Kanäle (`$PnE`) und Verstärkung
(`$PnG`). Zusätzlich CSV-Ereignistabellen mit automatischer Trennzeichen- und
Markererkennung.

### Kompensation
Spillover-Matrix aus `$SPILLOVER`/`$SPILL` oder als CSV aus der Gerätesoftware.
Inversion per Gauss-Jordan, Feinjustage einzelner Paare im Prozentraster,
Plausibilitätsprüfung (Diagonale, negativer oder >100 % Spillover, Singularität).
Kompensation wird zwingend **vor** jeder Transformation angewandt.

### Skalierung
Vollständige Logicle-Implementierung: Lösung der Logicle-Bedingung
`2·ln(d/b) + w·(b+d) = 0` per Newton/Bisektion, Taylorreihe im quasilinearen
Bereich, Halley-Iteration für die Umkehrung, W-Schätzung aus dem 5. Perzentil
der negativen Messwerte. Der Roundtrip ist auf 1e-12 relativ genau (Test).
Alternativ linear, log10 und arcsinh mit einstellbarem Kofaktor.

### Gating
Alle üblichen Formen plus boolesche Verknüpfung (UND/ODER/NICHT), beliebig
tiefe Hierarchie, Zeichnen per Maus, Tastenkürzel `V R P E I Q`.

Automatische Gates erzeugen immer eine **sichtbare, editierbare Form** — eine
Blackbox wäre nicht befundfähig:
- Singlets über das robuste FSC-A/FSC-H-Verhältnis (Median ± k·MAD)
- Zell- und Lymphozytengate über 2-D-Dichtemodus mit Flutfüllung und Kovarianzellipse
- 1-D-Schwellen über Otsu, Talsuche oder Quantil
- Quadranten aus automatisch bestimmten Schwellen
- Zeitfenster mit stabiler Ereignisrate
- Cluster → konvexe Hülle → reguläres Gate

### Darstellung
Punkt-, Dichte- (wahrnehmungsgleichmäßige Skala, Wurzelstauchung für seltene
Ereignisse), Kontur- (Marching Squares) und Histogrammdarstellung mit Overlays,
Backgating, korrekte Dekadenachsen mit Kollisionsvermeidung, Gate-Beschriftung
mit Anteilen, helles und dunkles Design.

### Unüberwachte Analyse
FlowSOM (selbstorganisierende Karte mit PCA-Initialisierung, agglomeratives
Metaclustering, minimaler Spannbaum), t-SNE, PCA, k-Means. Ergebnis: Heatmap
der Medianexpression, SOM-Darstellung und Clustertabelle. Jeder Cluster ist per
Klick in ein Gate überführbar und erscheint dann in Statistik und Befund.

### Qualitätskontrolle
Ereigniszahl, Flussratenstabilität, Signaldrift über die Messzeit,
Randereignisse/Sättigung, Dublettenanteil, Kompensationsplausibilität und
Färbeauflösung (Stain Index). Eine als *kritisch* bewertete Messung **blockiert
die Befundfreigabe**.

### Panel-Vorlagen

Jede Vorlage beschreibt deklarativ Marker, Gating-Strategie, Kennzahlen, Scores
und fachliche Hinweise. Ein Klick erzeugt daraus Gates, Statistik,
Regelbewertung und Befundtext.

| Panel | Indikation | Score |
|---|---|---|
| Lymphozyten-Subpopulationen (TBNK) | Immunstatus, HIV-Verlauf | Plausibilität T+B+NK |
| Akute Leukämie | Linienzuordnung | WHO-MPAL-Kriterien + EGIL |
| CLL / B-LPD | Lymphozytose | Matutes |
| B-Zell-Klonalität | Lymphomverdacht | Kappa/Lambda |
| MDS | Zytopenie | Ogata |
| PNH | Hämolyse, aplastische Anämie | Klongröße |
| CD34-Stammzellen | Apherese | ISHAGE |
| MRD B-ALL | Therapiemonitoring | LOD/LLOQ |
| Plasmazellen / Myelom | Gammopathie | — |
| B-Zell-Subpopulationen | Immundefekt | EUROclass |
| Regulatorische T-Zellen | Autoimmunität | — |
| Basophilen-Aktivierungstest | Allergie | — |
| Granulozytenfunktion (DHR) | CGD | — |
| Thrombozytäre Glykoproteine | Blutungsneigung | — |
| T-Zell-Aberranz | T-LPD | Antigenverlust |

### Befundung
- Auftrags- und Patientendaten (pseudonymisiert)
- vollständige Methodenbeschreibung inklusive Skalierung **je Kanal** (Reproduzierbarkeit)
- Qualitätskontrolle
- angewandte Gating-Strategie mit Zellzahlen und dem jeweils genutzten Verfahren
- Kennzahlen mit altersabhängigem Referenzbereich, Absolutzahlen und Hinweisen
- Scores mit Einzelkriterien und Quellenangabe
- Differentialdiagnose mit stützenden, widersprechenden und **nicht gemessenen** Markern
- Beurteilungsvorschlag, vom Anwender überschreibbar
- Limitationen (fehlende Marker, vorläufige Gates, QC-Auffälligkeiten, fehlende Kalibrierung)
- Freigabe mit Vier-Augen-Prinzip und Revisionszählung

Export als Text, CSV, JSON, **HL7-FHIR-Bundle** und Druck/PDF.

### Absolutzahlen
Ein- und Zweiplattformverfahren:
- **Zählbeads:** `Zellen/µl = (Zellereignisse / Beadereignisse) × (Beads pro Test / Probenvolumen)`
- **Blutbild:** Anteil an einer Bezugspopulation × deren Absolutwert

Ohne Kalibrierung erscheint eine ausdrückliche Limitation im Befund statt einer
stillschweigend fehlenden Zahl.

---

## Bewusste Entscheidungen

**Keine erfundenen LOINC-Codes.** Der FHIR-Export vergibt lokale Codes aus der
Kennzahl-ID. Über `codeMapping` trägt das Labor seine geprüften LOINC-Codes
nach. Ein falscher Code in einem Laborinformationssystem wäre schädlicher als
gar keiner.

**Referenzbereiche sind Voreinstellung, nicht Wahrheit.** Sie sind methoden-,
geräte- und populationsabhängig. Import/Export als JSON ist eingebaut, die
Quelle steht im Befund.

**Automatik bleibt sichtbar.** Jedes automatisch gesetzte Gate hat eine
editierbare Form und dokumentiert sein Verfahren im Befund. Aus Panel-Vorlagen
stammende Startvorschläge werden gestrichelt gezeichnet, mit `?` markiert und
als Limitation ausgewiesen, bis sie geprüft wurden.

**Auspägungsklassen sind eine Konvention.** „negativ / schwach / positiv /
stark" ergibt sich aus dem Abstand zur internen Negativpopulation in
Displaykoordinaten. Die Grenzen sind dokumentiert und ersetzen nicht die
visuelle Kontrolle im Histogramm.

**Sitzungsdateien enthalten keine Messdaten.** Gesichert werden Gates,
Skalierung, Panel, Patientenfelder und Befundtext — nicht die Ereignisse. Beim
Laden wird die Ereigniszahl gegen die geöffnete Datei geprüft.

---

## Tests

```
bun test                       86 Tests
  Lineare Algebra              Inversion, Singularität, Eigenwerte
  Logicle                      Nullpunkt, Skalenende, Roundtrip, Monotonie,
                               Logicle-Bedingung, LUT gegen exakt, Klemmung
  FCS-Parser                   Float/Integer/ASCII, Endianness, $PnE, Spillover,
                               CSV, Ablehnung fremder Formate
  Gate-Geometrie               konvex/konkav, gedrehte Ellipse, konvexe Hülle
  Statistik                    Perzentile, Kennzahlen, Otsu, Dichte, Ellipsenfit,
                               Massenerhaltung, LOD/LLOQ, Poisson, Overton, KS
  Ausdrucksauswertung          Funktionen, Arithmetik, Bindestrich-Argumente
  Clustering                   k-Means-Trennung + Reproduzierbarkeit, PCA,
                               Metacluster, Spannbaum
  Markerlexikon                Synonyme, zusammengesetzte Kanalnamen
  Referenzbereiche             Altersstaffelung, Bewertung, Import/Export
  Panel-Vorlagen               Schlüssigkeit aller 15 Vorlagen
  Integrationstest             synthetische Probe mit bekannter Zusammensetzung
                               durch die vollständige Kette

bun run smoke                  Rauchtest im echten Browser
```

Der Integrationstest erzeugt eine synthetische FCS-Datei mit bekannter
Zusammensetzung und prüft, dass die Auswertung sie wiederfindet:

| Kennzahl | Sollwert | gemessen |
|---|---|---|
| T-Zellen | 71,4 % | 71,7 % |
| B-Zellen | 12,5 % | 12,4 % |
| NK-Zellen | 16,1 % | 15,9 % |
| CD4/CD8 | 1,64 | 1,67 |
| Summe T+B+NK | 100 % | 100,0 % |

---

## Fachliche Grundlagen

- Moore & Parks, *Update for the logicle data scale including operational code implementations*, Cytometry A 2012
- Matutes et al. 1994; Moreau et al. 1997 — CLL-Score
- Ogata et al. 2009; Della Porta et al. 2012 — MDS-Score
- WHO-Klassifikation (MPAL-Kriterien); EGIL, Bene et al. 1995 — Linienzuordnung
- Wehr et al. 2008 — EUROclass
- ISHAGE-Protokoll — CD34-Zählung
- ICCS/ESCCA — PNH-Diagnostik
- EuroFlow — MRD, LOD und LLOQ
- Van Gassen et al. 2015 — FlowSOM
