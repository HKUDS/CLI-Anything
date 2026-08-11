/**
 * Markerlexikon.
 *
 * Dient drei Zwecken: automatische Zuordnung von Kanalnamen zu Markern,
 * Beschriftung von Achsen und Tabellen mit der biologischen Bedeutung und
 * Grundlage der Regelauswertung (Linienzuordnung, Aberranzbewertung).
 */

/** @typedef {'T'|'B'|'NK'|'myeloisch'|'monozytaer'|'erythroid'|'megakaryozytaer'|'Vorläufer'|'plasmazellulaer'|'allgemein'|'funktionell'} Lineage */

export const MARKERS = {
  // --- Allgemein / Gerueststruktur -----------------------------------
  CD45: { lineage: 'allgemein', aliases: ['LCA'], text: 'Leukozyten-gemeinsames Antigen; Grundlage des CD45/SSC-Gatings. Blasten zeigen typischerweise eine schwache Expression.' },
  'HLA-DR': { lineage: 'allgemein', aliases: ['HLADR', 'MHCII'], text: 'MHC-Klasse II; auf B-Zellen, Monozyten, aktivierten T-Zellen und den meisten Blasten. Fehlt charakteristischerweise bei der akuten Promyelozytenleukämie.' },
  CD38: { lineage: 'allgemein', text: 'Aktivierungs- und Reifungsmarker; stark auf Plasmazellen und Vorläuferzellen. Zielstruktur von Daratumumab.' },
  CD71: { lineage: 'erythroid', text: 'Transferrinrezeptor; proliferierende und erythroide Zellen.' },
  CD25: { lineage: 'funktionell', aliases: ['IL2RA'], text: 'IL-2-Rezeptor-Alphakette; Aktivierungsmarker, regulatorische T-Zellen, Haarzellleukämie, Mastozytose.' },
  CD26: { lineage: 'funktionell', text: 'Dipeptidylpeptidase IV; auf aberranten Mastzellen und in der CML-Stammzelldiagnostik.' },
  CD27: { lineage: 'B', text: 'Gedächtnismarker auf B- und T-Zellen; Grundlage der B-Zell-Subpopulationsanalyse.' },
  CD28: { lineage: 'T', text: 'Kostimulator; Verlust bei terminal differenzierten T-Zellen.' },
  CD69: { lineage: 'funktionell', text: 'Früher Aktivierungsmarker.' },
  CD95: { lineage: 'funktionell', aliases: ['FAS'], text: 'Fas-Rezeptor; Apoptoseinduktion, Marker für T-Gedächtnis-Stammzellen.' },
  'Ki-67': { lineage: 'funktionell', aliases: ['KI67', 'MKI67'], text: 'Proliferationsmarker (nur intrazellulär messbar).' },

  // --- T-Linie --------------------------------------------------------
  CD1a: { lineage: 'T', text: 'Kortikaler Thymozytenmarker; kennzeichnet die kortikale T-ALL. Auch auf Langerhans-Zellen.' },
  CD2: { lineage: 'T', text: 'Früher T-/NK-Zellmarker.' },
  CD3: { lineage: 'T', aliases: ['sCD3', 'CD3e'], text: 'Linienspezifisch für die T-Reihe. Zytoplasmatisches CD3 definiert die T-Linie bereits vor der Oberflächenexpression.' },
  cyCD3: { lineage: 'T', aliases: ['cCD3', 'icCD3'], text: 'Zytoplasmatisches CD3; entscheidend für die Linienzuordnung der T-ALL.' },
  CD4: { lineage: 'T', text: 'T-Helferzellen; zusätzlich schwach auf Monozyten.' },
  CD5: { lineage: 'T', text: 'T-Zellmarker; aberrant auf B-Zellen bei CLL und Mantelzelllymphom. Verlust ist ein Aberranzkriterium bei T-Zell-Lymphomen.' },
  CD7: { lineage: 'T', text: 'Frühester T-Zellmarker; häufig aberrant auf myeloischen Blasten. Verlust ist ein Aberranzkriterium.' },
  CD8: { lineage: 'T', text: 'Zytotoxische T-Zellen; schwach auch auf einem Teil der NK-Zellen.' },
  'CD45RA': { lineage: 'T', text: 'Naive T-Zellen und terminal differenzierte Effektorzellen.' },
  'CD45RO': { lineage: 'T', text: 'Gedächtnis-T-Zellen.' },
  CD62L: { lineage: 'T', aliases: ['SELL'], text: 'L-Selektin; zusammen mit CD45RA Definition naiver und zentraler Gedächtnis-T-Zellen.' },
  CD197: { lineage: 'T', aliases: ['CCR7'], text: 'Lymphknoten-Homing; Differenzierung naiver / zentraler / effektorischer Gedächtnis-T-Zellen.' },
  CD127: { lineage: 'T', aliases: ['IL7RA'], text: 'IL-7-Rezeptor; niedrige Expression zusammen mit CD25 kennzeichnet regulatorische T-Zellen.' },
  TCRab: { lineage: 'T', aliases: ['TCRAB', 'TCRALPHABETA'], text: 'Alpha-Beta-T-Zell-Rezeptor; Hauptanteil der peripheren T-Zellen.' },
  TCRgd: { lineage: 'T', aliases: ['TCRGD', 'TCRGAMMADELTA'], text: 'Gamma-Delta-T-Zell-Rezeptor; normal unter 10 % der T-Zellen.' },
  'TCR-Vbeta': { lineage: 'T', aliases: ['VBETA', 'TCRVB'], text: 'Vbeta-Repertoire-Analyse zum Klonalitätsnachweis bei T-Zell-Erkrankungen.' },
  TdT: { lineage: 'Vorläufer', aliases: ['TDT', 'DNTT'], text: 'Terminale Desoxynukleotidyltransferase; unreife lymphatische Vorläuferzellen (nur intrazellulär).' },

  // --- B-Linie --------------------------------------------------------
  CD19: { lineage: 'B', text: 'Panspezifischer B-Zellmarker über alle Reifungsstufen; Zielstruktur von CAR-T-Zellen und Blinatumomab.' },
  CD20: { lineage: 'B', aliases: ['MS4A1'], text: 'Reifer B-Zellmarker; Zielstruktur von Rituximab. Nach Rituximab ist CD20 als Gatingmarker unbrauchbar.' },
  CD21: { lineage: 'B', text: 'Komplementrezeptor 2; CD21-niedrige B-Zellen sind bei CVID und Autoimmunität vermehrt.' },
  CD22: { lineage: 'B', text: 'B-Zellmarker; schwach bei CLL. Bestandteil des Matutes-Scores.' },
  CD23: { lineage: 'B', text: 'Niedrigaffiner IgE-Rezeptor; typischerweise positiv bei CLL, negativ beim Mantelzelllymphom.' },
  CD24: { lineage: 'B', text: 'GPI-verankert; in der PNH-Diagnostik auf Granulozyten eingesetzt.' },
  CD79a: { lineage: 'B', aliases: ['CD79A', 'cyCD79a'], text: 'Zytoplasmatisch bereits in frühen B-Vorläufern; Linienzuordnung der B-ALL.' },
  CD79b: { lineage: 'B', aliases: ['CD79B'], text: 'Oberflächenexpression; schwach bei CLL. Bestandteil des Matutes-Scores.' },
  CD81: { lineage: 'B', text: 'Reifungsabhängig; in der MRD-Diagnostik der B-ALL und beim Myelom verwendet.' },
  FMC7: { lineage: 'B', text: 'Konformationsepitop des CD20; typischerweise negativ bei CLL. Bestandteil des Matutes-Scores.' },
  CD200: { lineage: 'B', text: 'Stark bei CLL, negativ oder schwach beim Mantelzelllymphom -- wichtiges Unterscheidungsmerkmal.' },
  CD10: { lineage: 'B', aliases: ['CALLA', 'MME'], text: 'CALLA; Keimzentrums-B-Zellen, follikuläres Lymphom, common-B-ALL. Auch auf reifen Granulozyten.' },
  CD103: { lineage: 'B', text: 'Zusammen mit CD25, CD11c und CD123 charakteristisch für die Haarzellleukämie.' },
  CD11c: { lineage: 'myeloisch', text: 'Monozyten, dendritische Zellen; stark bei Haarzellleukämie.' },
  CD123: { lineage: 'myeloisch', aliases: ['IL3RA'], text: 'IL-3-Rezeptor; plasmazytoide dendritische Zellen, BPDCN, Haarzellleukämie, leukämische Stammzellen.' },
  Kappa: { lineage: 'B', aliases: ['KAPPA', 'IGK', 'sKappa'], text: 'Leichtkette kappa; im Verhältnis zu lambda Grundlage des Klonalitätsnachweises.' },
  Lambda: { lineage: 'B', aliases: ['LAMBDA', 'IGL', 'sLambda'], text: 'Leichtkette lambda; im Verhältnis zu kappa Grundlage des Klonalitätsnachweises.' },
  IgM: { lineage: 'B', aliases: ['IGM'], text: 'Oberflächen-IgM; Reifungsstadium und Klonalitätsbeurteilung.' },
  IgD: { lineage: 'B', aliases: ['IGD'], text: 'Zusammen mit CD27 Einteilung naiver und geswitchter Gedächtnis-B-Zellen.' },

  // --- NK-Zellen ------------------------------------------------------
  CD16: { lineage: 'NK', aliases: ['FCGR3'], text: 'Fc-gamma-Rezeptor III; NK-Zellen und Granulozyten. CD16b auf Granulozyten ist GPI-verankert (PNH).' },
  CD56: { lineage: 'NK', aliases: ['NCAM'], text: 'NK-Zellen; aberrant auf Myeloblasten, Plasmazellen beim Myelom und bei der APL.' },
  CD57: { lineage: 'NK', text: 'Terminal differenzierte NK- und T-Zellen; große granuläre Lymphozyten.' },
  CD159a: { lineage: 'NK', aliases: ['NKG2A'], text: 'Inhibitorischer NK-Rezeptor; Klonalitätsbeurteilung bei NK-Erkrankungen.' },
  CD158: { lineage: 'NK', aliases: ['KIR'], text: 'KIR-Rezeptorfamilie; eingeschränktes Muster spricht für Klonalität.' },

  // --- Myeloisch / monozytaer ----------------------------------------
  CD11b: { lineage: 'myeloisch', text: 'Reifungsmarker der Granulopoese und Monozyten.' },
  CD13: { lineage: 'myeloisch', text: 'Panmyeloisch; aberrante Expressionsmuster bei MDS.' },
  CD14: { lineage: 'monozytaer', text: 'Reife Monozyten; GPI-verankert und damit zentral in der PNH-Diagnostik.' },
  CD15: { lineage: 'myeloisch', text: 'Granulozytäre Reifung.' },
  CD33: { lineage: 'myeloisch', text: 'Panmyeloisch; Zielstruktur von Gemtuzumab-Ozogamicin.' },
  CD64: { lineage: 'monozytaer', text: 'Fc-gamma-Rezeptor I; Monozyten, aktivierte Granulozyten (Sepsismarker).' },
  CD65: { lineage: 'myeloisch', text: 'Granulozytäre Reifung; in der EGIL-Klassifikation berücksichtigt.' },
  CD66b: { lineage: 'myeloisch', text: 'Granulozytenspezifisch, GPI-verankert (PNH-Alternative).' },
  CD117: { lineage: 'Vorläufer', aliases: ['KIT'], text: 'Stammzellfaktor-Rezeptor; Myeloblasten, Mastzellen, Erythroblasten.' },
  MPO: { lineage: 'myeloisch', aliases: ['cyMPO', 'MYELOPEROXIDASE'], text: 'Myeloperoxidase; definiert die myeloische Linie bei akuten Leukämien (intrazellulär).' },
  CD34: { lineage: 'Vorläufer', text: 'Hämatopoetische Vorläuferzellen; Grundlage der Stammzellzählung nach ISHAGE.' },
  CD135: { lineage: 'Vorläufer', aliases: ['FLT3'], text: 'FLT3-Rezeptor auf Vorläuferzellen.' },
  CD371: { lineage: 'myeloisch', aliases: ['CLL1', 'CLEC12A'], text: 'CLL-1; auf leukämischen Stammzellen exprimiert, nicht auf normalen HSZ -- MRD-relevant.' },
  CD99: { lineage: 'Vorläufer', text: 'Bei MDS und AML überexprimiert; Bestandteil aberranter Vorläuferprofile.' },
  CD36: { lineage: 'monozytaer', text: 'Monozyten, Erythroblasten, Thrombozyten.' },
  CD163: { lineage: 'monozytaer', text: 'Reife Gewebsmakrophagen und Monozyten.' },
  CD304: { lineage: 'myeloisch', aliases: ['NRP1', 'BDCA4'], text: 'Plasmazytoide dendritische Zellen.' },
  CD303: { lineage: 'myeloisch', aliases: ['BDCA2', 'CLEC4C'], text: 'Plasmazytoide dendritische Zellen; BPDCN-Diagnostik.' },

  // --- Erythroid / megakaryozytaer -----------------------------------
  CD235a: { lineage: 'erythroid', aliases: ['GLYCOPHORINA', 'GPA'], text: 'Glykophorin A; Erythrozyten und Erythroblasten. In der PNH-Diagnostik zur Identifikation der Erythrozyten.' },
  CD105: { lineage: 'erythroid', text: 'Endoglin; unreife Erythroblasten.' },
  CD41: { lineage: 'megakaryozytaer', aliases: ['GPIIB', 'ITGA2B'], text: 'GPIIb; Thrombozyten. Fehlt bei Thrombasthenie Glanzmann.' },
  CD42b: { lineage: 'megakaryozytaer', aliases: ['GPIB', 'GP1BA'], text: 'GPIb-alpha; fehlt beim Bernard-Soulier-Syndrom.' },
  CD61: { lineage: 'megakaryozytaer', aliases: ['GPIIIA', 'ITGB3'], text: 'GPIIIa; Thrombozyten und Megakaryoblasten (AML M7).' },
  CD62P: { lineage: 'megakaryozytaer', aliases: ['PSELECTIN'], text: 'P-Selektin; Marker der Thrombozytenaktivierung.' },

  // --- Plasmazellen ---------------------------------------------------
  CD138: { lineage: 'plasmazellulaer', aliases: ['SDC1'], text: 'Syndecan-1; Plasmazellen. Empfindlich gegenüber Probenalterung.' },
  CD319: { lineage: 'plasmazellulaer', aliases: ['SLAMF7', 'CS1'], text: 'Stabiler Plasmazellmarker; Zielstruktur von Elotuzumab.' },
  CD269: { lineage: 'plasmazellulaer', aliases: ['BCMA', 'TNFRSF17'], text: 'BCMA; Zielstruktur moderner Myelomtherapien.' },
  CD269b: { lineage: 'plasmazellulaer', aliases: [], text: 'Reserviert.' },
  CD229: { lineage: 'plasmazellulaer', aliases: ['SLAMF3'], text: 'Alternativer Plasmazellmarker in der MRD-Diagnostik.' },
  CD56p: { lineage: 'plasmazellulaer', aliases: [], text: 'Reserviert.' },

  // --- GPI-verankerte Strukturen (PNH) --------------------------------
  CD55: { lineage: 'funktionell', aliases: ['DAF'], text: 'Decay Accelerating Factor; GPI-verankert, fehlt bei PNH.' },
  CD59: { lineage: 'funktionell', aliases: ['MIRL'], text: 'Membrane Inhibitor of Reactive Lysis; GPI-verankert. Fehlen auf Erythrozyten definiert PNH-Typ-III-Zellen.' },
  CD157: { lineage: 'funktionell', text: 'GPI-verankert; PNH-Diagnostik auf Monozyten und Granulozyten.' },
  FLAER: { lineage: 'funktionell', aliases: ['FLAER-A', 'AEROLYSIN'], text: 'Fluoreszenzmarkiertes inaktives Aerolysin; bindet direkt an den GPI-Anker und ist der Referenzmarker der PNH-Diagnostik.' },

  // --- Funktionell / Allergologie -------------------------------------
  CD63: { lineage: 'funktionell', text: 'Lysosomales Protein; Degranulationsmarker im Basophilen-Aktivierungstest.' },
  CD203c: { lineage: 'funktionell', aliases: ['ENPP3'], text: 'Basophilenspezifisch; Aktivierungsmarker im Basophilen-Aktivierungstest.' },
  CD193: { lineage: 'funktionell', aliases: ['CCR3'], text: 'Identifikation von Basophilen und Eosinophilen.' },
  DHR: { lineage: 'funktionell', aliases: ['DHR123', 'DIHYDRORHODAMIN'], text: 'Dihydrorhodamin-123; Nachweis des oxidativen Bursts, Diagnostik der septischen Granulomatose.' },
  '7-AAD': { lineage: 'funktionell', aliases: ['7AAD', 'VIABILITY'], text: 'Vitalitätsfarbstoff; färbt Zellen mit defekter Membran.' },
  'DAPI': { lineage: 'funktionell', aliases: [], text: 'Vitalitäts- bzw. DNA-Farbstoff.' },
  'PI': { lineage: 'funktionell', aliases: ['PROPIDIUMIODID'], text: 'Propidiumiodid; Vitalität und DNA-Gehalt.' },
  'Zombie': { lineage: 'funktionell', aliases: ['LIVEDEAD', 'VIABILITYDYE'], text: 'Amin-reaktiver Vitalitätsfarbstoff, fixierbar.' },

  // --- Weitere therapierelevante Zielstrukturen -----------------------
  CD52: { lineage: 'allgemein', text: 'Zielstruktur von Alemtuzumab.' },
  CD30: { lineage: 'funktionell', aliases: ['TNFRSF8'], text: 'Zielstruktur von Brentuximab-Vedotin.' },
  CD274: { lineage: 'funktionell', aliases: ['PDL1'], text: 'PD-L1; Immuncheckpoint.' },
  CD279: { lineage: 'funktionell', aliases: ['PD1'], text: 'PD-1; Immuncheckpoint, erhoeht bei erschöpften T-Zellen und beim angioimmunoblastischen T-Zell-Lymphom.' },
  CD326: { lineage: 'allgemein', aliases: ['EPCAM'], text: 'Epitheliales Zelladhäsionsmolekül; Nachweis epithelialer Zellen in Ergussmaterial.' },
  'ZAP-70': { lineage: 'T', aliases: ['ZAP70'], text: 'Prognostisch bei CLL (Surrogat des IGHV-Mutationsstatus).' },
  CD49d: { lineage: 'funktionell', aliases: ['ITGA4'], text: 'Ungünstiger prognostischer Marker bei CLL (Grenzwert 30 %).' },
};

/** Normalisierte Suchtabelle inklusive aller Synonyme. */
const LOOKUP = new Map();
for (const [name, def] of Object.entries(MARKERS)) {
  const keys = [name, ...(def.aliases || [])];
  for (const k of keys) LOOKUP.set(normalize(k), name);
}

export function normalize(s) {
  return String(s || '').toUpperCase().replace(/[\s\-_.]/g, '');
}

/** Findet den kanonischen Markernamen zu einer beliebigen Schreibweise. */
export function canonicalMarker(text) {
  if (!text) return null;
  const n = normalize(text);
  if (LOOKUP.has(n)) return LOOKUP.get(n);
  // Marker aus einem zusammengesetzten Kanalnamen extrahieren ("CD3 FITC-A")
  const m = n.match(/CD\d+[A-Z]?/);
  if (m && LOOKUP.has(m[0])) return LOOKUP.get(m[0]);
  for (const [key, val] of LOOKUP) {
    if (key.length >= 3 && n.startsWith(key)) return val;
  }
  return null;
}

export function markerInfo(name) {
  const c = canonicalMarker(name);
  return c ? { name: c, ...MARKERS[c] } : null;
}

/**
 * Leitet aus den Kanalnamen einer Probe eine Marker-Zuordnung ab.
 * @returns {Object<string,string>} Kanalname -> Markername
 */
export function autoMapMarkers(sample) {
  const map = {};
  for (const p of sample.params) {
    if (p.isScatter || p.isTime) continue;
    const fromStain = canonicalMarker(p.stain);
    const fromName = canonicalMarker(p.name);
    const marker = fromStain || fromName;
    if (marker) map[p.name] = marker;
  }
  return map;
}

/** Alle im Panel vorhandenen Marker, gruppiert nach Linie. */
export function groupByLineage(markerNames) {
  const groups = {};
  for (const m of markerNames) {
    const info = markerInfo(m);
    const lin = info?.lineage || 'allgemein';
    (groups[lin] = groups[lin] || []).push(m);
  }
  return groups;
}
