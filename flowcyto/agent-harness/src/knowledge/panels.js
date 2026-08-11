/**
 * Panel-Vorlagen mit ausfuehrbarer Gating-Strategie.
 *
 * Jede Vorlage beschreibt deklarativ, welche Marker erwartet werden, wie
 * gegatet wird, welche Kennzahlen daraus entstehen und welche Abschnitte im
 * Befund erscheinen. core/strategy.js fuehrt diese Beschreibung aus. Dadurch
 * erzeugt die Panelauswahl in einem Schritt: Gates, Statistik, Regelbewertung
 * und Befundtext.
 *
 * Schrittarten:
 *   time       Zeitfenster mit stabiler Ereignisrate
 *   singlets   Dublettenausschluss ueber FSC-A/FSC-H
 *   mode2d     Dichtemodus in zwei Kanaelen (which: largest | lymph | blast)
 *   threshold  eindimensionale Schwelle auf einem Marker
 *   quadrants  Vierfeldertafel aus zwei Markern
 *   boolean    Verknuepfung bestehender Schritte (AND | OR | NOT)
 *   region     benannter rechteckiger Bereich in zwei Markern (Startvorschlag)
 */

export const PANELS = [
  /* ================================================================ */
  {
    id: 'tbnk',
    name: 'Lymphozyten-Subpopulationen (TBNK)',
    kategorie: 'Immunstatus',
    indikation:
      'Immundefekt, HIV-Verlauf, Immunsuppression, Lymphozytose unklarer Ursache, Therapiemonitoring.',
    material: 'EDTA-Blut, möglichst innerhalb von 24 h verarbeitet',
    marker: ['CD45', 'CD3', 'CD4', 'CD8', 'CD19', 'CD16', 'CD56'],
    optional: ['CD45RA', 'CD45RO', 'HLA-DR', 'CD25', 'CD127', 'TCRgd'],
    absolutzahlen: true,
    gating: [
      { id: 'time', kind: 'time', name: 'Zeitfenster stabil' },
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', parent: 'time', nSD: 3 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'Leukozyten (CD45+)', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'lymph', kind: 'mode2d', name: 'Lymphozyten', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'leuko', nSD: 2.4 },
      { id: 'tzell', kind: 'threshold', name: 'T-Zellen (CD3+)', marker: 'CD3', above: true, parent: 'lymph' },
      { id: 'cd4', kind: 'threshold', name: 'T-Helferzellen (CD3+CD4+)', marker: 'CD4', above: true, parent: 'tzell' },
      { id: 'cd8', kind: 'threshold', name: 'Zytotoxische T-Zellen (CD3+CD8+)', marker: 'CD8', above: true, parent: 'tzell' },
      { id: 'nonT', kind: 'threshold', name: 'CD3-negative Lymphozyten', marker: 'CD3', above: false, parent: 'lymph' },
      { id: 'bzell', kind: 'threshold', name: 'B-Zellen (CD19+)', marker: 'CD19', above: true, parent: 'nonT' },
      { id: 'nk', kind: 'threshold', name: 'NK-Zellen (CD16/56+)', marker: 'CD56', altMarker: 'CD16', above: true, parent: 'nonT' },
    ],
    metriken: [
      { id: 'tzell_pct', name: 'T-Zellen', ausdruck: 'pctOf(tzell, lymph)', einheit: '% der Lymphozyten', referenz: 'T_LYMPH_PCT', absolutVon: 'tzell' },
      { id: 'cd4_pct', name: 'T-Helferzellen', ausdruck: 'pctOf(cd4, lymph)', einheit: '% der Lymphozyten', referenz: 'CD4_LYMPH_PCT', absolutVon: 'cd4' },
      { id: 'cd8_pct', name: 'Zytotoxische T-Zellen', ausdruck: 'pctOf(cd8, lymph)', einheit: '% der Lymphozyten', referenz: 'CD8_LYMPH_PCT', absolutVon: 'cd8' },
      { id: 'b_pct', name: 'B-Zellen', ausdruck: 'pctOf(bzell, lymph)', einheit: '% der Lymphozyten', referenz: 'B_LYMPH_PCT', absolutVon: 'bzell' },
      { id: 'nk_pct', name: 'NK-Zellen', ausdruck: 'pctOf(nk, lymph)', einheit: '% der Lymphozyten', referenz: 'NK_LYMPH_PCT', absolutVon: 'nk' },
      { id: 'cd4cd8', name: 'CD4/CD8-Quotient', ausdruck: 'ratio(cd4, cd8)', einheit: '', referenz: 'CD4_CD8_RATIO', nachkomma: 2 },
      { id: 'summe', name: 'Summe T + B + NK', ausdruck: 'pctOf(tzell, lymph) + pctOf(bzell, lymph) + pctOf(nk, lymph)', einheit: '%', plausibilitaet: [95, 105] },
    ],
    hinweise: [
      'Die Summe aus T-, B- und NK-Zellen muss 100 % (+/- 5 %) ergeben; größere Abweichungen weisen auf ein fehlerhaftes Lymphozytengate hin.',
      'Absolutwerte erfordern entweder Zählbeads (Einplattform) oder ein zeitgleiches Blutbild (Zweiplattform).',
    ],
  },

  /* ================================================================ */
  {
    id: 'akute-leukämie',
    name: 'Akute Leukämie -- Linienzuordnung',
    kategorie: 'Hämato-Onkologie',
    indikation: 'Blastenvermehrung in Blut oder Knochenmark, Verdacht auf akute Leukämie.',
    material: 'EDTA- oder Heparin-Knochenmark, alternativ EDTA-Blut',
    marker: ['CD45', 'CD34', 'CD117', 'HLA-DR', 'CD13', 'CD33', 'MPO', 'cyCD3', 'CD79a', 'CD19', 'CD10', 'CD7', 'TdT'],
    optional: ['CD3', 'CD2', 'CD5', 'CD4', 'CD8', 'CD1a', 'CD20', 'CD14', 'CD64', 'CD11b', 'CD15', 'CD56', 'CD41', 'CD61', 'CD235a', 'CD123', 'CD371'],
    gating: [
      { id: 'time', kind: 'time', name: 'Zeitfenster stabil' },
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', parent: 'time', nSD: 3.2 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'Leukozyten (CD45+)', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'blasten', kind: 'region', name: 'Blastenregion (CD45 schwach / SSC niedrig)', x: 'CD45', y: 'SSC-A', parent: 'leuko', region: { x1: 0.18, x2: 0.62, y1: 0.02, y2: 0.45 } },
      { id: 'cd34p', kind: 'threshold', name: 'CD34+ Blasten', marker: 'CD34', above: true, parent: 'blasten' },
      { id: 'lymphozyten', kind: 'mode2d', name: 'Restlymphozyten (interne Kontrolle)', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'leuko', nSD: 2.2 },
    ],
    metriken: [
      { id: 'blasten_pct', name: 'Blastenanteil', ausdruck: 'pctOf(blasten, leuko)', einheit: '% der Leukozyten', schwellen: { auffaellig: 20 } },
      { id: 'cd34_pct', name: 'CD34-positive Blasten', ausdruck: 'pctOf(cd34p, blasten)', einheit: '% der Blasten' },
      { id: 'mpo', name: 'MPO', ausdruck: 'posPct(blasten, MPO)', einheit: '% positiv' },
      { id: 'cycd3', name: 'zytoplasmatisches CD3', ausdruck: 'posPct(blasten, cyCD3)', einheit: '% positiv' },
      { id: 'cd79a', name: 'CD79a', ausdruck: 'posPct(blasten, CD79a)', einheit: '% positiv' },
      { id: 'cd19', name: 'CD19', ausdruck: 'posPct(blasten, CD19)', einheit: '% positiv' },
    ],
    scores: ['egil'],
    hinweise: [
      'Die Linienzuordnung folgt den EGIL-Kriterien; die abschließende Einordnung erfolgt nach der aktuellen WHO-Klassifikation unter Einbeziehung von Zytogenetik und Molekulargenetik.',
      'MPO, cyCD3, CD79a und TdT sind intrazelluläre Marker und erfordern eine Permeabilisierung.',
      'Ein Blastenanteil ab 20 % der kernhaltigen Zellen definiert formal eine akute Leukämie; genetisch definierte Entitäten können davon abweichen.',
    ],
  },

  /* ================================================================ */
  {
    id: 'cll',
    name: 'Chronische lymphatische Leukämie / B-LPD',
    kategorie: 'Hämato-Onkologie',
    indikation: 'Lymphozytose, Verdacht auf chronische lymphoproliferative B-Zell-Erkrankung.',
    material: 'EDTA-Blut',
    marker: ['CD45', 'CD19', 'CD5', 'CD23', 'CD20', 'CD79b', 'FMC7', 'CD22', 'Kappa', 'Lambda'],
    optional: ['CD200', 'CD10', 'CD103', 'CD25', 'CD11c', 'CD123', 'CD38', 'CD49d', 'ZAP-70', 'CD43', 'IgM'],
    gating: [
      { id: 'time', kind: 'time', name: 'Zeitfenster stabil' },
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', parent: 'time', nSD: 3 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'Leukozyten (CD45+)', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'lymph', kind: 'mode2d', name: 'Lymphozyten', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'leuko', nSD: 2.4 },
      { id: 'bzell', kind: 'threshold', name: 'B-Zellen (CD19+)', marker: 'CD19', above: true, parent: 'lymph' },
      { id: 'cd5b', kind: 'threshold', name: 'CD5+ B-Zellen', marker: 'CD5', above: true, parent: 'bzell' },
      { id: 'kappa', kind: 'threshold', name: 'Kappa-restringiert', marker: 'Kappa', above: true, parent: 'bzell' },
      { id: 'lambda', kind: 'threshold', name: 'Lambda-restringiert', marker: 'Lambda', above: true, parent: 'bzell' },
      { id: 'tzell', kind: 'threshold', name: 'T-Zellen (interne Kontrolle)', marker: 'CD3', above: true, parent: 'lymph' },
    ],
    metriken: [
      { id: 'b_pct', name: 'B-Zellen', ausdruck: 'pctOf(bzell, lymph)', einheit: '% der Lymphozyten' },
      { id: 'cd5b_pct', name: 'CD5+ B-Zellen', ausdruck: 'pctOf(cd5b, bzell)', einheit: '% der B-Zellen' },
      { id: 'kl_ratio', name: 'Kappa/Lambda-Quotient', ausdruck: 'ratio(kappa, lambda)', einheit: '', referenz: 'KAPPA_LAMBDA', nachkomma: 2 },
      { id: 'b_abs', name: 'Klonale B-Zellen absolut', ausdruck: 'abs(cd5b)', einheit: '/µl', schwellen: { auffaellig: 5000 } },
    ],
    scores: ['matutes'],
    hinweise: [
      'Der Matutes-Score dient der Abgrenzung der CLL von anderen B-Zell-Lymphomen; 4-5 Punkte sprechen für eine CLL, 0-2 Punkte dagegen.',
      'Ab 5000 klonalen B-Zellen/µl im peripheren Blut liegt definitionsgemäß eine CLL vor, darunter bei fehlender Organbeteiligung eine monoklonale B-Lymphozytose (MBL).',
      'CD200 stark positiv spricht für CLL, negativ bzw. schwach für ein Mantelzelllymphom.',
    ],
  },

  /* ================================================================ */
  {
    id: 'klonalitaet-b',
    name: 'B-Zell-Klonalität (Leichtkettenrestriktion)',
    kategorie: 'Hämato-Onkologie',
    indikation: 'Verdacht auf B-Zell-Lymphom, Lymphknoten-, Erguss- oder Liquormaterial.',
    material: 'EDTA-Blut, Knochenmark, Gewebesuspension, Punktat',
    marker: ['CD45', 'CD19', 'CD20', 'Kappa', 'Lambda'],
    optional: ['CD5', 'CD10', 'CD23', 'CD200', 'CD38', 'CD103', 'CD25', 'CD11c', 'IgM', 'IgD', 'CD43'],
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'CD45+ Zellen', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'lymph', kind: 'mode2d', name: 'Lymphozyten', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'leuko', nSD: 2.5 },
      { id: 'bzell', kind: 'threshold', name: 'B-Zellen (CD19+)', marker: 'CD19', above: true, parent: 'lymph' },
      { id: 'kappa', kind: 'threshold', name: 'Kappa+', marker: 'Kappa', above: true, parent: 'bzell' },
      { id: 'lambda', kind: 'threshold', name: 'Lambda+', marker: 'Lambda', above: true, parent: 'bzell' },
      { id: 'cd10p', kind: 'threshold', name: 'CD10+ B-Zellen', marker: 'CD10', above: true, parent: 'bzell' },
    ],
    metriken: [
      { id: 'kl_ratio', name: 'Kappa/Lambda-Quotient', ausdruck: 'ratio(kappa, lambda)', einheit: '', referenz: 'KAPPA_LAMBDA', nachkomma: 2 },
      { id: 'b_pct', name: 'B-Zellanteil', ausdruck: 'pctOf(bzell, lymph)', einheit: '% der Lymphozyten' },
      { id: 'lk_negativ', name: 'Leichtketten-negative B-Zellen', ausdruck: '100 - pctOf(kappa, bzell) - pctOf(lambda, bzell)', einheit: '% der B-Zellen', schwellen: { auffaellig: 25 } },
    ],
    scores: ['klonalitaet'],
    hinweise: [
      'Ein Kappa/Lambda-Quotient über 3,0 oder unter 0,3 gilt als Hinweis auf Klonalität.',
      'Ein hoher Anteil leichtkettennegativer B-Zellen kann ebenfalls klonal sein (Leichtkettenverlust) und erfordert eine molekulare Abklärung.',
      'Bei geringer B-Zellzahl ist der Quotient nur eingeschränkt beurteilbar; mindestens 100 B-Zellen sind erforderlich.',
    ],
  },

  /* ================================================================ */
  {
    id: 'mds',
    name: 'Myelodysplastisches Syndrom (Ogata-Score)',
    kategorie: 'Hämato-Onkologie',
    indikation: 'Zytopenie unklarer Ursache, Verdacht auf MDS.',
    material: 'EDTA-Knochenmark',
    marker: ['CD45', 'CD34', 'CD10', 'CD19', 'SSC-A'],
    optional: ['CD117', 'CD13', 'CD33', 'HLA-DR', 'CD11b', 'CD15', 'CD16', 'CD14', 'CD64', 'CD56', 'CD7'],
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3.2 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'Kernhaltige Zellen (CD45+)', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'cd34p', kind: 'threshold', name: 'CD34+ Vorläuferzellen', marker: 'CD34', above: true, parent: 'leuko' },
      { id: 'bvorl', kind: 'threshold', name: 'B-Vorläufer (CD34+CD10+)', marker: 'CD10', above: true, parent: 'cd34p' },
      { id: 'lymph', kind: 'mode2d', name: 'Lymphozyten', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'leuko', nSD: 2.2 },
      { id: 'granulo', kind: 'mode2d', name: 'Granulozyten', x: 'CD45', y: 'SSC-A', which: 'largest', parent: 'leuko', nSD: 2.5, minFsc: 0.2 },
    ],
    metriken: [
      { id: 'cd34_pct', name: 'CD34+ Zellen', ausdruck: 'pctOf(cd34p, leuko)', einheit: '% der kernhaltigen Zellen', schwellen: { auffaellig: 2 } },
      { id: 'bvorl_pct', name: 'B-Vorläufer an CD34+', ausdruck: 'pctOf(bvorl, cd34p)', einheit: '% der CD34+ Zellen', schwellen: { niedrig: 5 } },
      { id: 'ssc_ratio', name: 'SSC-Quotient Granulozyten/Lymphozyten', ausdruck: 'mfiRatio(granulo, lymph, SSC-A)', einheit: '', nachkomma: 2 },
      { id: 'cd45_ratio', name: 'CD45-Quotient Lymphozyten/Blasten', ausdruck: 'mfiRatio(lymph, cd34p, CD45)', einheit: '', nachkomma: 2 },
    ],
    scores: ['ogata'],
    hinweise: [
      'Der Ogata-Score bewertet vier Parameter mit je einem Punkt; ab 2 Punkten besteht ein Hinweis auf ein MDS.',
      'Der Score ersetzt weder Zytomorphologie noch Zytogenetik, sondern ergänzt sie.',
      'Voraussetzung ist eine wenig verdünnte Knochenmarkprobe; eine Blutbeimengung verfälscht alle vier Parameter.',
    ],
  },

  /* ================================================================ */
  {
    id: 'pnh',
    name: 'Paroxysmale nächtliche Hämoglobinurie (PNH)',
    kategorie: 'Spezialdiagnostik',
    indikation: 'Hämolyse mit negativem Coombs-Test, aplastische Anämie, Thrombose atypischer Lokalisation, MDS.',
    material: 'EDTA-Blut, möglichst frisch (< 48 h)',
    marker: ['CD45', 'FLAER', 'CD24', 'CD14', 'CD15', 'CD64', 'CD235a', 'CD59'],
    optional: ['CD157', 'CD55', 'CD16', 'CD66b'],
    hochsensitiv: true,
    gating: [
      { id: 'time', kind: 'time', name: 'Zeitfenster stabil' },
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', parent: 'time', nSD: 3.2 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'Leukozyten (CD45+)', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'granulo', kind: 'threshold', name: 'Granulozyten (CD15+)', marker: 'CD15', above: true, parent: 'leuko' },
      { id: 'gran_pnh', kind: 'threshold', name: 'PNH-Klon Granulozyten (FLAER-/CD24-)', marker: 'FLAER', above: false, parent: 'granulo' },
      { id: 'mono', kind: 'threshold', name: 'Monozyten (CD64+)', marker: 'CD64', altMarker: 'CD14', above: true, parent: 'leuko' },
      { id: 'mono_pnh', kind: 'threshold', name: 'PNH-Klon Monozyten (FLAER-/CD14-)', marker: 'FLAER', above: false, parent: 'mono' },
      { id: 'ery', kind: 'threshold', name: 'Erythrozyten (CD235a+)', marker: 'CD235a', above: true, parent: 'singlets' },
      { id: 'ery_typ3', kind: 'threshold', name: 'Erythrozyten Typ III (CD59 negativ)', marker: 'CD59', above: false, parent: 'ery' },
    ],
    metriken: [
      { id: 'gran_klon', name: 'PNH-Klon Granulozyten', ausdruck: 'pctOf(gran_pnh, granulo)', einheit: '% der Granulozyten', nachkomma: 3, schwellen: { auffaellig: 0.1 } },
      { id: 'mono_klon', name: 'PNH-Klon Monozyten', ausdruck: 'pctOf(mono_pnh, mono)', einheit: '% der Monozyten', nachkomma: 3, schwellen: { auffaellig: 0.1 } },
      { id: 'ery_klon', name: 'PNH-Klon Erythrozyten (Typ III)', ausdruck: 'pctOf(ery_typ3, ery)', einheit: '% der Erythrozyten', nachkomma: 3 },
      { id: 'lod_gran', name: 'Nachweisgrenze Granulozyten', ausdruck: 'lod(granulo)', einheit: '%', nachkomma: 4 },
    ],
    scores: ['pnh'],
    hinweise: [
      'Der Granulozytenklon ist der maßgebliche Wert; Erythrozytenklone werden durch Hämolyse und Transfusionen unterschätzt.',
      'Für die hochsensitive Analyse sind mindestens 100 000 Granulozyten zu messen (Nachweisgrenze etwa 0,01 %).',
      'Klone unter 1 % gelten als kleine Klone und erfordern eine Verlaufskontrolle statt einer sofortigen Therapie.',
    ],
  },

  /* ================================================================ */
  {
    id: 'cd34',
    name: 'CD34-Stammzellzählung (ISHAGE)',
    kategorie: 'Transplantation',
    indikation: 'Steuerung der Stammzellapherese, Qualitätskontrolle des Transplantats.',
    material: 'Apheresat, EDTA-Blut, Knochenmark',
    marker: ['CD45', 'CD34', '7-AAD'],
    optional: ['CD133', 'CD38', 'CD90'],
    absolutzahlen: true,
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Alle Ereignisse', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3.5 },
      { id: 'vital', kind: 'threshold', name: 'Vitale Zellen (7-AAD negativ)', marker: '7-AAD', above: false, parent: 'zellen' },
      { id: 'cd45p', kind: 'threshold', name: 'CD45+ Leukozyten', marker: 'CD45', above: true, parent: 'vital' },
      { id: 'cd34p', kind: 'threshold', name: 'CD34+ Zellen', marker: 'CD34', above: true, parent: 'cd45p' },
      { id: 'cd34_blast', kind: 'region', name: 'CD34+ mit Blastenstreulicht', x: 'SSC-A', y: 'CD45', parent: 'cd34p', region: { x1: 0.0, x2: 0.45, y1: 0.25, y2: 0.7 } },
    ],
    metriken: [
      { id: 'cd34_pct', name: 'CD34+ Zellen', ausdruck: 'pctOf(cd34_blast, cd45p)', einheit: '% der Leukozyten', nachkomma: 2 },
      { id: 'cd34_abs', name: 'CD34+ Zellen absolut', ausdruck: 'abs(cd34_blast)', einheit: '/µl', nachkomma: 1 },
      { id: 'vitalitaet', name: 'Vitalität', ausdruck: 'pctOf(vital, zellen)', einheit: '%', schwellen: { niedrig: 90 } },
    ],
    hinweise: [
      'Das ISHAGE-Protokoll verlangt die sequentielle Auswertung: CD45 gegen CD34, danach Streulichtkontrolle und Ausschluss toter Zellen.',
      'Für eine autologe Transplantation werden mindestens 2 x 10^6 CD34+ Zellen pro kg Körpergewicht angestrebt.',
      'Mindestens 100 CD34+ Ereignisse sollten erfasst werden; darunter ist der Variationskoeffizient zu hoch.',
    ],
  },

  /* ================================================================ */
  {
    id: 'mrd-all',
    name: 'MRD B-Vorläufer-ALL',
    kategorie: 'Hämato-Onkologie',
    indikation: 'Therapiemonitoring der B-Vorläufer-ALL an definierten Zeitpunkten.',
    material: 'EDTA-Knochenmark, erster Aspirationszug',
    marker: ['CD45', 'CD19', 'CD10', 'CD20', 'CD34', 'CD38', 'CD58', 'CD81', 'CD123'],
    optional: ['CD22', 'CD24', 'CD73', 'CD304', 'TdT', 'CD9'],
    hochsensitiv: true,
    gating: [
      { id: 'time', kind: 'time', name: 'Zeitfenster stabil' },
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', parent: 'time', nSD: 3.2 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'Kernhaltige Zellen (CD45+)', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'cd19p', kind: 'threshold', name: 'CD19+ B-Reihe', marker: 'CD19', above: true, parent: 'leuko' },
      { id: 'blasten', kind: 'region', name: 'B-Vorläufer (CD10+CD45 schwach)', x: 'CD10', y: 'CD45', parent: 'cd19p', region: { x1: 0.5, x2: 1.0, y1: 0.1, y2: 0.6 } },
    ],
    metriken: [
      { id: 'mrd', name: 'MRD-Anteil', ausdruck: 'pctOf(blasten, leuko)', einheit: '% der kernhaltigen Zellen', nachkomma: 4, schwellen: { auffaellig: 0.01 } },
      { id: 'lod', name: 'Nachweisgrenze (LOD)', ausdruck: 'lod(leuko)', einheit: '%', nachkomma: 4 },
      { id: 'lloq', name: 'Bestimmungsgrenze (LLOQ)', ausdruck: 'lloq(leuko)', einheit: '%', nachkomma: 4 },
      { id: 'events', name: 'Ausgewertete Ereignisse', ausdruck: 'count(leuko)', einheit: '' },
    ],
    scores: ['mrd'],
    hinweise: [
      'Die Bewertung erfolgt nach dem Prinzip "different from normal" im Abgleich mit dem regelhaften Reifungsmuster der B-Vorläuferzellen (Hardy-Stadien).',
      'Für eine Sensitivität von 0,01 % sind mindestens 500 000 kernhaltige Zellen zu messen; LOD entspricht 20, LLOQ 50 Ereignissen im Cluster.',
      'Nach CD19-gerichteter Therapie ist ein CD19-unabhängiges Gating erforderlich (z. B. CD22, CD24).',
      'Eine Hämodilution des Aspirats führt zu falsch niedrigen Werten und ist im Befund zu vermerken.',
    ],
  },

  /* ================================================================ */
  {
    id: 'plasmazellen',
    name: 'Plasmazellen / Multiples Myelom',
    kategorie: 'Hämato-Onkologie',
    indikation: 'Monoklonale Gammopathie, Verdacht auf Myelom, MRD-Bestimmung.',
    material: 'EDTA-Knochenmark',
    marker: ['CD45', 'CD38', 'CD138', 'CD19', 'CD56', 'CD27', 'CD81', 'CD117'],
    optional: ['CD200', 'CD28', 'CD269', 'CD319', 'Kappa', 'Lambda'],
    hochsensitiv: true,
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3.2 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'leuko', kind: 'threshold', name: 'Kernhaltige Zellen (CD45+)', marker: 'CD45', above: true, parent: 'singlets' },
      { id: 'pz', kind: 'region', name: 'Plasmazellen (CD38 stark / CD138+)', x: 'CD38', y: 'CD138', parent: 'leuko', region: { x1: 0.6, x2: 1.0, y1: 0.45, y2: 1.0 } },
      { id: 'pz_aberrant', kind: 'threshold', name: 'Aberrante Plasmazellen (CD19 negativ)', marker: 'CD19', above: false, parent: 'pz' },
      { id: 'pz_normal', kind: 'threshold', name: 'Regelhafte Plasmazellen (CD19+)', marker: 'CD19', above: true, parent: 'pz' },
    ],
    metriken: [
      { id: 'pz_pct', name: 'Plasmazellen gesamt', ausdruck: 'pctOf(pz, leuko)', einheit: '% der kernhaltigen Zellen', nachkomma: 3 },
      { id: 'aberrant_pct', name: 'Aberranter Anteil', ausdruck: 'pctOf(pz_aberrant, pz)', einheit: '% der Plasmazellen', nachkomma: 1 },
      { id: 'aberrant_abs', name: 'Aberrante Plasmazellen', ausdruck: 'pctOf(pz_aberrant, leuko)', einheit: '% der kernhaltigen Zellen', nachkomma: 4 },
      { id: 'lod', name: 'Nachweisgrenze (LOD)', ausdruck: 'lod(leuko)', einheit: '%', nachkomma: 4 },
    ],
    hinweise: [
      'Ein Plasmazellanteil ab 10 % der kernhaltigen Zellen ist ein Kriterium des multiplen Myeloms; die Durchflusszytometrie unterschätzt den Anteil regelmäßig gegenüber der Zytomorphologie.',
      'Aberrant sind Plasmazellen typischerweise CD19-negativ, CD56-positiv, CD27-schwach und CD81-schwach.',
      'CD138 ist empfindlich gegenüber Probenalterung; die Messung sollte innerhalb von 24 h erfolgen.',
    ],
  },

  /* ================================================================ */
  {
    id: 'euroclass',
    name: 'B-Zell-Subpopulationen (Immundefektabklärung)',
    kategorie: 'Immunstatus',
    indikation: 'Variables Immundefektsyndrom (CVID), Antikörpermangel, rezidivierende Infekte.',
    material: 'EDTA-Blut',
    marker: ['CD45', 'CD19', 'CD27', 'IgD', 'CD21', 'CD38'],
    optional: ['IgM', 'CD24', 'CD10'],
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'lymph', kind: 'mode2d', name: 'Lymphozyten', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'singlets', nSD: 2.4 },
      { id: 'bzell', kind: 'threshold', name: 'B-Zellen (CD19+)', marker: 'CD19', above: true, parent: 'lymph' },
      { id: 'gedaechtnis', kind: 'threshold', name: 'Gedächtnis-B-Zellen (CD27+)', marker: 'CD27', above: true, parent: 'bzell' },
      { id: 'switched', kind: 'threshold', name: 'Geswitchte Gedächtniszellen (IgD-)', marker: 'IgD', above: false, parent: 'gedaechtnis' },
      { id: 'marginal', kind: 'threshold', name: 'Marginalzonenähnlich (IgD+CD27+)', marker: 'IgD', above: true, parent: 'gedaechtnis' },
      { id: 'naiv', kind: 'threshold', name: 'Naive B-Zellen (CD27-)', marker: 'CD27', above: false, parent: 'bzell' },
      { id: 'cd21low', kind: 'threshold', name: 'CD21-niedrige B-Zellen', marker: 'CD21', above: false, parent: 'bzell' },
      { id: 'transitional', kind: 'threshold', name: 'Transitionale B-Zellen (CD38 stark)', marker: 'CD38', above: true, parent: 'naiv' },
      { id: 'plasmablasten', kind: 'threshold', name: 'Plasmablasten', marker: 'CD38', above: true, parent: 'gedaechtnis' },
    ],
    metriken: [
      { id: 'b_pct', name: 'B-Zellen', ausdruck: 'pctOf(bzell, lymph)', einheit: '% der Lymphozyten', referenz: 'B_LYMPH_PCT' },
      { id: 'switched_pct', name: 'Geswitchte Gedächtnis-B-Zellen', ausdruck: 'pctOf(switched, bzell)', einheit: '% der B-Zellen', referenz: 'SWITCHED_MEMORY' },
      { id: 'cd21low_pct', name: 'CD21-niedrige B-Zellen', ausdruck: 'pctOf(cd21low, bzell)', einheit: '% der B-Zellen', referenz: 'CD21_LOW' },
      { id: 'transitional_pct', name: 'Transitionale B-Zellen', ausdruck: 'pctOf(transitional, bzell)', einheit: '% der B-Zellen', referenz: 'TRANSITIONAL' },
      { id: 'plasmablasten_pct', name: 'Plasmablasten', ausdruck: 'pctOf(plasmablasten, bzell)', einheit: '% der B-Zellen', referenz: 'PLASMABLASTS' },
    ],
    scores: ['euroclass'],
    hinweise: [
      'Die Einteilung folgt der EUROclass-Klassifikation; sie ist bei gesicherter CVID-Diagnose prognostisch relevant.',
      'Geswitchte Gedächtnis-B-Zellen unter 2 % der B-Zellen sind mit einem höheren Risiko für Granulome und Splenomegalie verbunden.',
    ],
  },

  /* ================================================================ */
  {
    id: 'treg',
    name: 'Regulatorische T-Zellen',
    kategorie: 'Immunstatus',
    indikation: 'Autoimmunerkrankung, IPEX-Verdacht, Transplantationsmonitoring.',
    material: 'EDTA-Blut',
    marker: ['CD45', 'CD3', 'CD4', 'CD25', 'CD127'],
    optional: ['FOXP3', 'CD45RA', 'HLA-DR'],
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'lymph', kind: 'mode2d', name: 'Lymphozyten', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'singlets', nSD: 2.4 },
      { id: 'tzell', kind: 'threshold', name: 'T-Zellen (CD3+)', marker: 'CD3', above: true, parent: 'lymph' },
      { id: 'cd4', kind: 'threshold', name: 'CD4+ T-Zellen', marker: 'CD4', above: true, parent: 'tzell' },
      { id: 'cd25hi', kind: 'threshold', name: 'CD25 stark positiv', marker: 'CD25', above: true, parent: 'cd4', method: 'quantile', quantile: 0.9 },
      { id: 'treg', kind: 'threshold', name: 'Treg (CD25+CD127 schwach)', marker: 'CD127', above: false, parent: 'cd25hi' },
    ],
    metriken: [
      { id: 'treg_pct', name: 'Regulatorische T-Zellen', ausdruck: 'pctOf(treg, cd4)', einheit: '% der CD4+ T-Zellen', referenz: 'TREG_CD4' },
    ],
    hinweise: ['Regulatorische T-Zellen sind definiert als CD4+CD25+CD127 schwach; die FOXP3-Färbung erfordert eine Permeabilisierung.'],
  },

  /* ================================================================ */
  {
    id: 'bat',
    name: 'Basophilen-Aktivierungstest',
    kategorie: 'Allergologie',
    indikation: 'Verdacht auf Soforttypallergie, Abklärung bei nicht eindeutiger IgE-Diagnostik.',
    material: 'Heparin- oder EDTA-Blut, Verarbeitung innerhalb von 4 h',
    marker: ['CD45', 'CD123', 'HLA-DR', 'CD63', 'CD203c'],
    optional: ['CD193', 'IgE'],
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3.2 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'cd123p', kind: 'threshold', name: 'CD123+ Zellen', marker: 'CD123', above: true, parent: 'singlets' },
      { id: 'baso', kind: 'threshold', name: 'Basophile (CD123+ HLA-DR negativ)', marker: 'HLA-DR', above: false, parent: 'cd123p' },
      { id: 'aktiviert', kind: 'threshold', name: 'Aktivierte Basophile (CD63+)', marker: 'CD63', above: true, parent: 'baso' },
    ],
    metriken: [
      { id: 'baso_n', name: 'Erfasste Basophile', ausdruck: 'count(baso)', einheit: 'Ereignisse', schwellen: { niedrig: 300 } },
      { id: 'aktivierung', name: 'CD63-positive Basophile', ausdruck: 'pctOf(aktiviert, baso)', einheit: '%', schwellen: { auffaellig: 15 } },
      { id: 'cd203c_mfi', name: 'CD203c-Intensität', ausdruck: 'mfi(baso, CD203c)', einheit: 'MFI' },
    ],
    hinweise: [
      'Jeder Ansatz erfordert eine Negativkontrolle (Puffer) und eine Positivkontrolle (anti-IgE oder fMLP).',
      'Mindestens 300 Basophile pro Ansatz sind erforderlich; bei Nichtansprechen der Positivkontrolle ist der Test nicht verwertbar (Non-Responder, etwa 10 % der Personen).',
      'Der Stimulationsindex bezieht sich stets auf die mitgeführte Negativkontrolle.',
    ],
  },

  /* ================================================================ */
  {
    id: 'dhr',
    name: 'Granulozytenfunktion (DHR-Test)',
    kategorie: 'Spezialdiagnostik',
    indikation: 'Verdacht auf septische Granulomatose (CGD), rezidivierende bakterielle und mykotische Infektionen.',
    material: 'Heparin-Blut, Verarbeitung innerhalb von 6 h',
    marker: ['CD45', 'DHR', 'FSC-A', 'SSC-A'],
    optional: ['CD15', 'CD11b'],
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3.2 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'granulo', kind: 'mode2d', name: 'Granulozyten', x: 'FSC-A', y: 'SSC-A', which: 'largest', parent: 'singlets', nSD: 2.4, minFsc: 0.25 },
      { id: 'burst', kind: 'threshold', name: 'Zellen mit oxidativem Burst', marker: 'DHR', above: true, parent: 'granulo' },
    ],
    metriken: [
      { id: 'burst_pct', name: 'Granulozyten mit oxidativem Burst', ausdruck: 'pctOf(burst, granulo)', einheit: '%', schwellen: { niedrig: 95 } },
      { id: 'si', name: 'Stimulationsindex', ausdruck: 'mfi(granulo, DHR)', einheit: 'MFI' },
    ],
    hinweise: [
      'Unstimulierte Kontrolle und PMA-stimulierter Ansatz sind zwingend parallel zu messen.',
      'Ein bimodales Muster mit zwei Granulozytenpopulationen ist typisch für Konduktorinnen der X-chromosomalen CGD.',
    ],
  },

  /* ================================================================ */
  {
    id: 'thrombozyten',
    name: 'Thrombozytäre Glykoproteine',
    kategorie: 'Spezialdiagnostik',
    indikation: 'Verdacht auf Thrombasthenie Glanzmann oder Bernard-Soulier-Syndrom, Blutungsneigung.',
    material: 'Citrat-Blut, Verarbeitung innerhalb von 4 h',
    marker: ['CD41', 'CD42b', 'CD61'],
    optional: ['CD62P', 'CD63', 'CD49b'],
    gating: [
      { id: 'thrombo', kind: 'threshold', name: 'Thrombozyten (CD41+)', marker: 'CD41', altMarker: 'CD61', above: true },
    ],
    metriken: [
      { id: 'cd41', name: 'CD41 (GPIIb)', ausdruck: 'mfi(thrombo, CD41)', einheit: 'MFI' },
      { id: 'cd61', name: 'CD61 (GPIIIa)', ausdruck: 'mfi(thrombo, CD61)', einheit: 'MFI' },
      { id: 'cd42b', name: 'CD42b (GPIb-alpha)', ausdruck: 'mfi(thrombo, CD42b)', einheit: 'MFI' },
      { id: 'cd42b_pos', name: 'CD42b-positive Thrombozyten', ausdruck: 'posPct(thrombo, CD42b)', einheit: '%', schwellen: { niedrig: 90 } },
    ],
    hinweise: [
      'Die Beurteilung erfolgt stets im Vergleich zu einer parallel gemessenen Normalkontrolle; absolute MFI-Werte sind geräteabhängig.',
      'Ein Fehlen von CD41 und CD61 spricht für eine Thrombasthenie Glanzmann, ein Fehlen von CD42b für ein Bernard-Soulier-Syndrom.',
    ],
  },

  /* ================================================================ */
  {
    id: 'tzell-aberranz',
    name: 'T-Zell-Aberranz / T-LPD',
    kategorie: 'Hämato-Onkologie',
    indikation: 'Verdacht auf T-Zell-Lymphom, T-LGL-Leukämie, Sezary-Syndrom.',
    material: 'EDTA-Blut, Knochenmark, Gewebesuspension',
    marker: ['CD45', 'CD3', 'CD2', 'CD4', 'CD5', 'CD7', 'CD8', 'CD26'],
    optional: ['TCRab', 'TCRgd', 'CD57', 'CD16', 'CD56', 'CD25', 'CD30', 'TCR-Vbeta', 'CD279'],
    gating: [
      { id: 'zellen', kind: 'mode2d', name: 'Zellen', x: 'FSC-A', y: 'SSC-A', which: 'largest', nSD: 3 },
      { id: 'singlets', kind: 'singlets', name: 'Singlets', parent: 'zellen' },
      { id: 'lymph', kind: 'mode2d', name: 'Lymphozyten', x: 'CD45', y: 'SSC-A', which: 'lymph', parent: 'singlets', nSD: 2.4 },
      { id: 'tzell', kind: 'threshold', name: 'T-Zellen (CD3+)', marker: 'CD3', above: true, parent: 'lymph' },
      { id: 'cd4', kind: 'threshold', name: 'CD4+ T-Zellen', marker: 'CD4', above: true, parent: 'tzell' },
      { id: 'cd8', kind: 'threshold', name: 'CD8+ T-Zellen', marker: 'CD8', above: true, parent: 'tzell' },
      { id: 'cd7neg', kind: 'threshold', name: 'CD7-negative T-Zellen', marker: 'CD7', above: false, parent: 'tzell' },
      { id: 'cd26neg', kind: 'threshold', name: 'CD26-negative T-Zellen', marker: 'CD26', above: false, parent: 'cd4' },
    ],
    metriken: [
      { id: 'cd4cd8', name: 'CD4/CD8-Quotient', ausdruck: 'ratio(cd4, cd8)', einheit: '', referenz: 'CD4_CD8_RATIO', nachkomma: 2 },
      { id: 'cd7neg_pct', name: 'CD7-Verlust', ausdruck: 'pctOf(cd7neg, tzell)', einheit: '% der T-Zellen', schwellen: { auffaellig: 20 } },
      { id: 'cd26neg_pct', name: 'CD26-Verlust (CD4+)', ausdruck: 'pctOf(cd26neg, cd4)', einheit: '% der CD4+ T-Zellen', schwellen: { auffaellig: 30 } },
    ],
    scores: ['tzell_aberranz'],
    hinweise: [
      'Ein Antigenverlust (CD7, CD26, CD5) ist ein Aberranzkriterium, aber nicht beweisend für Klonalität.',
      'Der Klonalitätsnachweis erfolgt über die Vbeta-Repertoire-Analyse oder molekulargenetisch über die TCR-Umlagerung.',
      'CD4+CD26-negative Zellen über 30 % der CD4+ T-Zellen sind ein etabliertes Kriterium beim Sezary-Syndrom.',
    ],
  },
];

export function panelById(id) {
  return PANELS.find((p) => p.id === id) || null;
}

export function panelKategorien() {
  const out = new Map();
  for (const p of PANELS) {
    if (!out.has(p.kategorie)) out.set(p.kategorie, []);
    out.get(p.kategorie).push(p);
  }
  return out;
}

/**
 * Bewertet, wie gut ein Panel zu den Kanaelen einer Probe passt.
 * Grundlage des Vorschlags "Passendes Panel" beim Laden einer Datei.
 */
export function scorePanelFit(panel, verfuegbareMarker) {
  const set = new Set(verfuegbareMarker);
  const pflicht = panel.marker.filter((m) => !/^(FSC|SSC)/i.test(m));
  const treffer = pflicht.filter((m) => set.has(m));
  const optional = (panel.optional || []).filter((m) => set.has(m));
  return {
    panel,
    treffer: treffer.length,
    pflicht: pflicht.length,
    fehlend: pflicht.filter((m) => !set.has(m)),
    optional: optional.length,
    score: pflicht.length ? treffer.length / pflicht.length + optional.length * 0.02 : 0,
  };
}
