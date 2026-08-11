/**
 * Entitaetskatalog fuer die Differentialdiagnose.
 *
 * Jede Entitaet beschreibt ihr erwartetes Immunphaenotyp-Muster. Die
 * Regelauswertung vergleicht das gemessene Profil einer auffaelligen
 * Population mit diesen Mustern und erstellt daraus eine gewichtete
 * Differentialdiagnose mit stuetzenden und widersprechenden Befunden.
 *
 * Erwartungswerte:
 *   '++'  stark positiv        '+'  positiv
 *   '+/-' variabel             '-'  negativ
 *   '(+)' schwach positiv
 *
 * Die Liste ist ein Hilfsmittel zur Befundung, keine Klassifikation. Die
 * abschliessende Einordnung erfolgt nach der aktuellen WHO-Klassifikation
 * unter Einbeziehung von Morphologie, Zyto- und Molekulargenetik sowie Klinik.
 */

export const ENTITAETEN = [
  /* --- Reife B-Zell-Neoplasien -------------------------------------- */
  {
    id: 'cll',
    name: 'Chronische lymphatische Leukämie / kleinzelliges lymphozytisches Lymphom',
    kurz: 'CLL/SLL',
    gruppe: 'Reife B-Zell-Neoplasie',
    profil: { CD19: '+', CD20: '(+)', CD5: '+', CD23: '+', CD200: '++', FMC7: '-', CD79b: '(+)', CD22: '(+)', CD10: '-', CD43: '+' },
    sIg: 'schwach',
    schluessel: ['CD5', 'CD23', 'CD200', 'FMC7'],
    zusatz: 'Prognostisch relevant: CD38, CD49d (Grenzwert 30 %), ZAP-70 sowie IGHV-Mutationsstatus und TP53-Status.',
  },
  {
    id: 'mcl',
    name: 'Mantelzelllymphom',
    kurz: 'MCL',
    gruppe: 'Reife B-Zell-Neoplasie',
    profil: { CD19: '+', CD20: '++', CD5: '+', CD23: '-', CD200: '-', FMC7: '+', CD79b: '+', CD10: '-' },
    sIg: 'stark',
    schluessel: ['CD5', 'CD23', 'CD200'],
    zusatz: 'Bestätigung über Cyclin D1 bzw. t(11;14) erforderlich. CD200-negativ ist das wichtigste Unterscheidungsmerkmal zur CLL.',
  },
  {
    id: 'fl',
    name: 'Follikuläres Lymphom',
    kurz: 'FL',
    gruppe: 'Reife B-Zell-Neoplasie',
    profil: { CD19: '+', CD20: '++', CD10: '+', CD5: '-', CD23: '+/-', CD200: '-', FMC7: '+' },
    sIg: 'positiv',
    schluessel: ['CD10', 'CD5'],
    zusatz: 'Bestätigung über BCL2-Überexpression bzw. t(14;18).',
  },
  {
    id: 'mzl',
    name: 'Marginalzonenlymphom',
    kurz: 'MZL',
    gruppe: 'Reife B-Zell-Neoplasie',
    profil: { CD19: '+', CD20: '++', CD5: '-', CD10: '-', CD23: '-', CD103: '-', CD11c: '+/-' },
    sIg: 'positiv',
    schluessel: ['CD5', 'CD10'],
    zusatz: 'Ausschlussdiagnose der CD5- und CD10-negativen B-Zell-Lymphome; Klinik und Histologie sind entscheidend.',
  },
  {
    id: 'hcl',
    name: 'Haarzellleukämie',
    kurz: 'HCL',
    gruppe: 'Reife B-Zell-Neoplasie',
    profil: { CD19: '+', CD20: '++', CD11c: '++', CD25: '+', CD103: '+', CD123: '+', CD200: '++', CD5: '-', CD10: '-' },
    sIg: 'positiv',
    schluessel: ['CD11c', 'CD25', 'CD103', 'CD123'],
    zusatz: 'Die Kombination CD11c, CD25, CD103 und CD123 ist nahezu beweisend. Molekular BRAF V600E.',
  },
  {
    id: 'lpl',
    name: 'Lymphoplasmozytisches Lymphom / Morbus Waldenström',
    kurz: 'LPL',
    gruppe: 'Reife B-Zell-Neoplasie',
    profil: { CD19: '+', CD20: '+', CD5: '-', CD10: '-', CD23: '-', CD38: '+', CD138: '+/-', IgM: '++' },
    sIg: 'positiv',
    schluessel: ['IgM', 'CD5', 'CD10'],
    zusatz: 'Typisch ist eine IgM-Paraproteinämie; molekular MYD88 L265P.',
  },
  {
    id: 'blymphom-aggressiv',
    name: 'Aggressives B-Zell-Lymphom (z. B. DLBCL, Burkitt-Lymphom)',
    kurz: 'aggressives B-NHL',
    gruppe: 'Reife B-Zell-Neoplasie',
    profil: { CD19: '+', CD20: '++', CD10: '+/-', CD38: '+', CD5: '-' },
    sIg: 'positiv',
    grosseZellen: true,
    schluessel: ['CD10', 'CD38'],
    zusatz: 'Große Zellen mit hohem Vorwärtsstreulicht; beim Burkitt-Lymphom CD10+, CD38 stark und sehr hohe Proliferationsrate.',
  },

  /* --- Plasmazellneoplasien ------------------------------------------ */
  {
    id: 'myelom',
    name: 'Plasmazellmyelom',
    kurz: 'Myelom',
    gruppe: 'Plasmazellneoplasie',
    profil: { CD38: '++', CD138: '+', CD19: '-', CD56: '+', CD45: '-', CD27: '(+)', CD81: '(+)', CD117: '+/-' },
    schluessel: ['CD19', 'CD56', 'CD45'],
    zusatz: 'Aberrante Plasmazellen sind typischerweise CD19-negativ und CD56-positiv; die Leichtkettenrestriktion wird intrazellulär bestimmt.',
  },

  /* --- Reife T- und NK-Zell-Neoplasien ------------------------------- */
  {
    id: 'tlgl',
    name: 'T-Zell-Leukämie der großen granulären Lymphozyten',
    kurz: 'T-LGL',
    gruppe: 'Reife T-Zell-Neoplasie',
    profil: { CD3: '+', CD8: '+', CD57: '+', CD16: '+', CD5: '(+)', CD7: '(+)', CD4: '-', CD56: '-' },
    schluessel: ['CD8', 'CD57', 'CD5', 'CD7'],
    zusatz: 'Abschwächung von CD5 und CD7 ist typisch. Klonalitätsnachweis über Vbeta-Repertoire oder TCR-Umlagerung; molekular häufig STAT3-Mutation.',
  },
  {
    id: 'sezary',
    name: 'Sezary-Syndrom / kutanes T-Zell-Lymphom',
    kurz: 'Sezary',
    gruppe: 'Reife T-Zell-Neoplasie',
    profil: { CD3: '+', CD4: '+', CD26: '-', CD7: '-', CD8: '-', CD5: '+' },
    schluessel: ['CD4', 'CD26', 'CD7'],
    zusatz: 'Ein Anteil CD4+CD26-negativer Zellen über 30 % der CD4+ T-Zellen bzw. CD4+CD7-negativer Zellen über 40 % gilt als Kriterium.',
  },
  {
    id: 'ttcl-sonstige',
    name: 'Peripheres T-Zell-Lymphom, nicht weiter spezifiziert',
    kurz: 'PTCL-NOS',
    gruppe: 'Reife T-Zell-Neoplasie',
    profil: { CD3: '+/-', CD2: '+', CD5: '+/-', CD7: '-', CD4: '+/-' },
    schluessel: ['CD7', 'CD5'],
    zusatz: 'Antigenverlust (häufig CD7, seltener CD5, CD2 oder CD3) ist das wesentliche Aberranzkriterium.',
  },
  {
    id: 'nk-neoplasie',
    name: 'NK-Zell-Neoplasie / chronische lymphoproliferative NK-Zell-Erkrankung',
    kurz: 'NK-LPD',
    gruppe: 'NK-Zell-Neoplasie',
    profil: { CD3: '-', CD56: '+', CD16: '+', CD57: '+/-', CD7: '+/-' },
    schluessel: ['CD3', 'CD56'],
    zusatz: 'Klonalität über ein eingeschränktes KIR-Muster (CD158) oder über CD94/NKG2A nahelegbar.',
  },

  /* --- Akute Leukaemien ---------------------------------------------- */
  {
    id: 'b-all',
    name: 'B-Vorläufer-lymphoblastische Leukämie/Lymphom',
    kurz: 'B-ALL',
    gruppe: 'Akute Leukämie',
    profil: { CD19: '+', CD79a: '+', CD10: '+/-', TdT: '+', CD34: '+/-', CD20: '+/-', CD45: '(+)', HLA_DR: '+', MPO: '-', CD3: '-' },
    schluessel: ['CD19', 'CD79a', 'CD10', 'TdT'],
    zusatz: 'Untertypen: Pro-B (CD10-), Common (CD10+), Prä-B (cyIgM+). CD10-negative Fälle sind häufig mit einer KMT2A-Rearrangierung assoziiert.',
  },
  {
    id: 't-all',
    name: 'T-lymphoblastische Leukämie/Lymphom',
    kurz: 'T-ALL',
    gruppe: 'Akute Leukämie',
    profil: { cyCD3: '+', CD7: '++', CD5: '+/-', CD2: '+/-', CD1a: '+/-', CD34: '+/-', TdT: '+', MPO: '-', CD19: '-' },
    schluessel: ['cyCD3', 'CD7', 'CD1a'],
    zusatz: 'Die frühe T-Vorläufer-ALL (ETP-ALL) ist CD1a- und CD8-negativ, CD5 schwach und exprimiert Stamm- oder Myeloidmarker.',
  },
  {
    id: 'aml',
    name: 'Akute myeloische Leukämie',
    kurz: 'AML',
    gruppe: 'Akute Leukämie',
    profil: { MPO: '+', CD13: '+', CD33: '+', CD117: '+', CD34: '+/-', HLA_DR: '+', CD45: '(+)', CD19: '-', cyCD3: '-' },
    schluessel: ['MPO', 'CD13', 'CD33', 'CD117'],
    zusatz: 'Die Einordnung nach WHO erfolgt vorrangig genetisch. Aberrante Expression von CD7, CD56 oder CD19 ist als MRD-Marker (LAIP) zu dokumentieren.',
  },
  {
    id: 'apl',
    name: 'Akute Promyelozytenleukämie',
    kurz: 'APL',
    gruppe: 'Akute Leukämie',
    profil: { MPO: '++', CD13: '+', CD33: '++', CD117: '+', HLA_DR: '-', CD34: '-', CD15: '(+)', CD11b: '-', CD56: '+/-' },
    hohesSSC: true,
    schluessel: ['HLA-DR', 'CD34', 'CD11b'],
    dringend: true,
    zusatz:
      'HLA-DR-negativ, CD34-negativ, hohes Seitwärtsstreulicht: dringender Verdacht. Wegen des Blutungsrisikos ist eine unverzügliche Mitteilung an den Einsender und eine sofortige molekulare Bestätigung (PML::RARA) erforderlich.',
  },
  {
    id: 'ammol',
    name: 'Akute myelomonozytäre / monoblastäre Leukämie',
    kurz: 'AML monozytär',
    gruppe: 'Akute Leukämie',
    profil: { CD14: '+/-', CD64: '++', CD11b: '+', CD4: '(+)', CD33: '++', HLA_DR: '+', CD34: '-', MPO: '+/-' },
    schluessel: ['CD64', 'CD14', 'CD11b'],
    zusatz: 'CD64 stark mit CD11c und CD36 spricht für eine monozytäre Differenzierung; CD34 ist häufig negativ.',
  },
  {
    id: 'mpal',
    name: 'Akute Leukämie mit gemischtem Phänotyp',
    kurz: 'MPAL',
    gruppe: 'Akute Leukämie',
    profil: { MPO: '+', cyCD3: '+', CD19: '+/-', CD79a: '+/-', CD13: '+', CD33: '+' },
    schluessel: ['MPO', 'cyCD3', 'CD19'],
    zusatz: 'Definiert über die WHO-Kriterien: gleichzeitige Erfüllung der Linienkriterien für zwei Linien in einer oder zwei Blastenpopulationen.',
  },
  {
    id: 'bpdcn',
    name: 'Blastische plasmazytoide dendritische Zellneoplasie',
    kurz: 'BPDCN',
    gruppe: 'Akute Leukämie',
    profil: { CD123: '++', CD4: '+', CD56: '+', CD303: '+', HLA_DR: '+', CD34: '-', MPO: '-', CD3: '-', CD19: '-' },
    schluessel: ['CD123', 'CD4', 'CD56', 'CD303'],
    zusatz: 'Charakteristisch ist die Kombination CD4, CD56 und CD123 bei fehlenden linienspezifischen Markern.',
  },
];

export function entitaetById(id) {
  return ENTITAETEN.find((e) => e.id === id) || null;
}

/** Normiert einen Markernamen fuer den Profilabgleich. */
export function profilSchluessel(marker) {
  return String(marker).replace(/-/g, '_');
}

/**
 * Erwartete Auspraegung eines Markers fuer eine Entitaet.
 * @returns {'++'|'+'|'(+)'|'+/-'|'-'|null}
 */
export function erwartung(entitaet, marker) {
  const p = entitaet.profil || {};
  return p[marker] ?? p[profilSchluessel(marker)] ?? null;
}
