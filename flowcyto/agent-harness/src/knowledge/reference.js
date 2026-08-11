/**
 * Referenzbereiche.
 *
 * WICHTIG: Referenzbereiche sind methoden-, geraete- und populationsabhaengig.
 * Die hier hinterlegten Werte sind Orientierungswerte aus der Literatur und
 * muessen vor dem Einsatz in der Routine durch laboreigene Bereiche ersetzt
 * werden. Die App unterstuetzt Import und Export als JSON, damit jedes Labor
 * seine eigenen Bereiche einspielen kann.
 */

export const REFERENZ_QUELLE = {
  bezeichnung: 'Orientierungswerte (Voreinstellung)',
  hinweis:
    'Voreingestellte Literaturwerte. Vor Einsatz in der Routinediagnostik durch laboreigene, validierte Referenzbereiche ersetzen.',
  stand: '2026',
};

/**
 * Ein Referenzbereich gilt fuer ein Altersintervall in Jahren [von, bis).
 * `unten`/`oben` sind die Grenzen, `einheit` dient nur der Anzeige.
 */
function bereich(vonJahre, bisJahre, unten, oben) {
  return { vonJahre, bisJahre, unten, oben };
}

export const REFERENZBEREICHE = {
  /* --- T-, B-, NK-Zellen: Anteil an den Lymphozyten ---------------- */
  T_LYMPH_PCT: {
    name: 'T-Zellen (CD3+)',
    einheit: '% der Lymphozyten',
    bereiche: [
      bereich(0, 0.25, 53, 84),
      bereich(0.25, 1, 51, 77),
      bereich(1, 6, 56, 75),
      bereich(6, 18, 60, 76),
      bereich(18, 200, 55, 83),
    ],
  },
  CD4_LYMPH_PCT: {
    name: 'T-Helferzellen (CD3+CD4+)',
    einheit: '% der Lymphozyten',
    bereiche: [
      bereich(0, 0.25, 35, 64),
      bereich(0.25, 1, 35, 56),
      bereich(1, 6, 28, 47),
      bereich(6, 18, 31, 47),
      bereich(18, 200, 28, 57),
    ],
  },
  CD8_LYMPH_PCT: {
    name: 'Zytotoxische T-Zellen (CD3+CD8+)',
    einheit: '% der Lymphozyten',
    bereiche: [
      bereich(0, 0.25, 12, 28),
      bereich(0.25, 1, 12, 24),
      bereich(1, 6, 16, 30),
      bereich(6, 18, 18, 35),
      bereich(18, 200, 10, 39),
    ],
  },
  B_LYMPH_PCT: {
    name: 'B-Zellen (CD19+)',
    einheit: '% der Lymphozyten',
    bereiche: [
      bereich(0, 0.25, 6, 32),
      bereich(0.25, 1, 11, 41),
      bereich(1, 6, 14, 33),
      bereich(6, 18, 10, 31),
      bereich(18, 200, 6, 19),
    ],
  },
  NK_LYMPH_PCT: {
    name: 'NK-Zellen (CD16/CD56+)',
    einheit: '% der Lymphozyten',
    bereiche: [
      bereich(0, 0.25, 2, 14),
      bereich(0.25, 1, 3, 15),
      bereich(1, 6, 4, 17),
      bereich(6, 18, 4, 26),
      bereich(18, 200, 7, 31),
    ],
  },
  CD4_CD8_RATIO: {
    name: 'CD4/CD8-Quotient',
    einheit: '',
    bereiche: [bereich(0, 1, 1.5, 5.0), bereich(1, 18, 0.9, 3.4), bereich(18, 200, 0.9, 3.6)],
  },

  /* --- Absolutwerte ------------------------------------------------ */
  T_ABS: {
    name: 'T-Zellen absolut',
    einheit: '/µl',
    bereiche: [bereich(0, 1, 1900, 5900), bereich(1, 6, 1400, 3700), bereich(6, 18, 1000, 2200), bereich(18, 200, 700, 2100)],
  },
  CD4_ABS: {
    name: 'T-Helferzellen absolut',
    einheit: '/µl',
    bereiche: [bereich(0, 1, 1400, 4300), bereich(1, 6, 700, 2200), bereich(6, 18, 530, 1300), bereich(18, 200, 300, 1400)],
  },
  CD8_ABS: {
    name: 'Zytotoxische T-Zellen absolut',
    einheit: '/µl',
    bereiche: [bereich(0, 1, 500, 1700), bereich(1, 6, 490, 1300), bereich(6, 18, 330, 920), bereich(18, 200, 200, 900)],
  },
  B_ABS: {
    name: 'B-Zellen absolut',
    einheit: '/µl',
    bereiche: [bereich(0, 1, 600, 2700), bereich(1, 6, 390, 1400), bereich(6, 18, 200, 600), bereich(18, 200, 100, 500)],
  },
  NK_ABS: {
    name: 'NK-Zellen absolut',
    einheit: '/µl',
    bereiche: [bereich(0, 1, 160, 950), bereich(1, 6, 130, 720), bereich(6, 18, 70, 480), bereich(18, 200, 90, 600)],
  },

  /* --- B-Zell-Subpopulationen (EUROclass) --------------------------- */
  SWITCHED_MEMORY: {
    name: 'Geswitchte Gedächtnis-B-Zellen (CD27+IgD-)',
    einheit: '% der B-Zellen',
    bereiche: [bereich(0, 6, 1.5, 12), bereich(6, 18, 4, 20), bereich(18, 200, 6.5, 29)],
  },
  CD21_LOW: {
    name: 'CD21-niedrige B-Zellen',
    einheit: '% der B-Zellen',
    bereiche: [bereich(0, 200, 0, 10)],
  },
  TRANSITIONAL: {
    name: 'Transitionale B-Zellen',
    einheit: '% der B-Zellen',
    bereiche: [bereich(0, 200, 0, 9)],
  },
  PLASMABLASTS: {
    name: 'Plasmablasten',
    einheit: '% der B-Zellen',
    bereiche: [bereich(0, 200, 0.4, 3.5)],
  },

  /* --- Weitere ------------------------------------------------------ */
  KAPPA_LAMBDA: {
    name: 'Kappa/Lambda-Quotient (B-Zellen)',
    einheit: '',
    bereiche: [bereich(0, 200, 0.9, 2.6)],
    klonalitaet: { obereGrenze: 3.0, untereGrenze: 0.3 },
  },
  TREG_CD4: {
    name: 'Regulatorische T-Zellen',
    einheit: '% der CD4+ T-Zellen',
    bereiche: [bereich(0, 200, 3, 8)],
  },
  CD34_APHERESE: {
    name: 'CD34+ Zellen im Apheresat',
    einheit: '/µl',
    bereiche: [bereich(0, 200, 10, 100000)],
    hinweis: 'Kein Referenzbereich im eigentlichen Sinn; Zielwert der Apherese ist patientenbezogen.',
  },
};

/** Waehlt den zum Alter passenden Bereich. */
export function bereichFuerAlter(schluessel, alterJahre, katalog = REFERENZBEREICHE) {
  const eintrag = katalog[schluessel];
  if (!eintrag) return null;
  const alter = Number.isFinite(alterJahre) ? alterJahre : 30;
  const treffer = eintrag.bereiche.find((b) => alter >= b.vonJahre && alter < b.bisJahre);
  if (!treffer) return null;
  return { ...treffer, name: eintrag.name, einheit: eintrag.einheit, hinweis: eintrag.hinweis };
}

/**
 * Bewertet einen Messwert gegen den Referenzbereich.
 * @returns {{status:'normal'|'erniedrigt'|'erhoeht'|'unbekannt', text:string, bereich:object|null}}
 */
export function bewerte(schluessel, wert, alterJahre, katalog = REFERENZBEREICHE) {
  const b = bereichFuerAlter(schluessel, alterJahre, katalog);
  if (!b || !Number.isFinite(wert)) {
    return { status: 'unbekannt', text: '', bereich: b };
  }
  const spanne = `${formatZahl(b.unten)}–${formatZahl(b.oben)}${b.einheit ? ' ' + b.einheit : ''}`;
  if (wert < b.unten) return { status: 'erniedrigt', text: `erniedrigt (Referenz ${spanne})`, bereich: b };
  if (wert > b.oben) return { status: 'erhoeht', text: `erhoeht (Referenz ${spanne})`, bereich: b };
  return { status: 'normal', text: `im Referenzbereich (${spanne})`, bereich: b };
}

function formatZahl(v) {
  if (!Number.isFinite(v)) return '–';
  if (Math.abs(v) >= 100) return v.toFixed(0);
  if (Math.abs(v) >= 10) return v.toFixed(1);
  return v.toFixed(1);
}

/** Alter in Jahren aus Geburtsjahr oder direkt uebergebenem Alter. */
export function alterBestimmen(patient) {
  if (Number.isFinite(patient?.alterJahre)) return patient.alterJahre;
  if (Number.isFinite(patient?.geburtsjahr)) return new Date().getFullYear() - patient.geburtsjahr;
  return null;
}

/* ------------------------------------------------------------------ */
/* Import und Export laboreigener Bereiche                             */
/* ------------------------------------------------------------------ */

export function exportReferenzen(katalog = REFERENZBEREICHE, quelle = REFERENZ_QUELLE) {
  return JSON.stringify({ quelle, bereiche: katalog }, null, 2);
}

/**
 * Uebernimmt laboreigene Referenzbereiche. Erwartet dieselbe Struktur wie der
 * Export; unbekannte Schluessel werden ergaenzt, bekannte ersetzt.
 */
export function importReferenzen(json) {
  const daten = typeof json === 'string' ? JSON.parse(json) : json;
  if (!daten || typeof daten !== 'object' || !daten.bereiche) {
    throw new Error('Ungültiges Format: Feld "bereiche" fehlt.');
  }
  const katalog = { ...REFERENZBEREICHE };
  let uebernommen = 0;
  for (const [schluessel, eintrag] of Object.entries(daten.bereiche)) {
    if (!eintrag?.bereiche?.length) continue;
    const gueltig = eintrag.bereiche.every(
      (b) => Number.isFinite(b.vonJahre) && Number.isFinite(b.bisJahre) && Number.isFinite(b.unten) && Number.isFinite(b.oben),
    );
    if (!gueltig) throw new Error(`Referenzbereich "${schluessel}" enthält unvollständige Grenzen.`);
    katalog[schluessel] = eintrag;
    uebernommen++;
  }
  return {
    katalog,
    quelle: daten.quelle || { bezeichnung: 'Laboreigene Bereiche', stand: new Date().toISOString().slice(0, 10) },
    uebernommen,
  };
}
