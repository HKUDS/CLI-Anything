/**
 * Export als HL7-FHIR-Bundle (R4) fuer die Uebernahme in ein
 * Laborinformationssystem oder eine elektronische Patientenakte.
 *
 * Bewusste Entscheidung zu Kodierungen: Die Software vergibt KEINE
 * LOINC-Codes aus eigenem Antrieb. Falsche Codes waeren in einem
 * Laborinformationssystem schaedlicher als gar keine. Stattdessen erhaelt
 * jede Beobachtung einen lokalen Code aus der Kennzahl-ID; ueber
 * `codeMapping` kann das Labor seine geprueften LOINC- oder hauseigenen
 * Codes zuordnen. Nur zugeordnete Codes erscheinen im Bundle.
 */

const LOKALES_SYSTEM = 'urn:flowcyto:kennzahl';
const LOINC_SYSTEM = 'http://loinc.org';

/** Beispielhafte Struktur einer Zuordnungstabelle. */
export const BEISPIEL_MAPPING = {
  // 'tzell_pct': { loinc: '<vom Labor geprüft>', anzeige: 'CD3+ Zellen / 100 Lymphozyten' },
};

function uid(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function codeFuer(kennzahl, mapping) {
  const coding = [
    { system: LOKALES_SYSTEM, code: kennzahl.id, display: kennzahl.name },
  ];
  const m = mapping?.[kennzahl.id];
  if (m?.loinc) {
    coding.unshift({ system: LOINC_SYSTEM, code: m.loinc, display: m.anzeige || kennzahl.name });
  }
  return { coding, text: kennzahl.name };
}

function interpretation(status) {
  const map = {
    erhoeht: { code: 'H', display: 'High' },
    erniedrigt: { code: 'L', display: 'Low' },
    normal: { code: 'N', display: 'Normal' },
  };
  const m = map[status];
  if (!m) return undefined;
  return [
    {
      coding: [
        { system: 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation', code: m.code, display: m.display },
      ],
    },
  ];
}

/**
 * Wandelt einen Befund in ein FHIR-Bundle.
 * @param {object} befund Ergebnis aus report/befund.js
 * @param {object} optionen {codeMapping, patientId, status}
 */
export function alsFHIR(befund, optionen = {}) {
  const { codeMapping = BEISPIEL_MAPPING } = optionen;
  const patientId = optionen.patientId || uid('pat');
  const specimenId = uid('spec');
  const berichtId = uid('rep');
  const zeit = befund.erstellt;

  const eintraege = [];

  /* --- Patient (pseudonymisiert) --- */
  eintraege.push({
    fullUrl: `urn:uuid:${patientId}`,
    resource: {
      resourceType: 'Patient',
      id: patientId,
      identifier: befund.kopf.pseudonym
        ? [{ system: 'urn:flowcyto:pseudonym', value: befund.kopf.pseudonym }]
        : undefined,
      gender: geschlechtFHIR(befund.kopf.geschlecht),
      extension: Number.isFinite(befund.kopf.alterJahre)
        ? [{ url: 'urn:flowcyto:alterJahre', valueInteger: Math.round(befund.kopf.alterJahre) }]
        : undefined,
    },
  });

  /* --- Probe --- */
  eintraege.push({
    fullUrl: `urn:uuid:${specimenId}`,
    resource: {
      resourceType: 'Specimen',
      id: specimenId,
      subject: { reference: `Patient/${patientId}` },
      type: { text: befund.kopf.material || 'nicht angegeben' },
      receivedTime: befund.kopf.eingang || undefined,
      collection: befund.kopf.entnahme ? { collectedDateTime: befund.kopf.entnahme } : undefined,
      note: [{ text: `Dateiname: ${befund.methode.dateiname}` }],
    },
  });

  /* --- Beobachtungen --- */
  const observationIds = [];
  for (const e of befund.ergebnisse) {
    if (!Number.isFinite(e.wert)) continue;
    const obsId = uid('obs');
    observationIds.push(obsId);
    const referenceRange = e.referenzBereich
      ? [
          {
            low: { value: e.referenzBereich.unten, unit: e.einheit || '1' },
            high: { value: e.referenzBereich.oben, unit: e.einheit || '1' },
            text: e.referenzText,
          },
        ]
      : undefined;

    eintraege.push({
      fullUrl: `urn:uuid:${obsId}`,
      resource: {
        resourceType: 'Observation',
        id: obsId,
        status: befund.signatur.freigabe ? 'final' : 'preliminary',
        category: [
          {
            coding: [
              { system: 'http://terminology.hl7.org/CodeSystem/observation-category', code: 'laboratory', display: 'Laboratory' },
            ],
          },
        ],
        code: codeFuer(e, codeMapping),
        subject: { reference: `Patient/${patientId}` },
        specimen: { reference: `Specimen/${specimenId}` },
        effectiveDateTime: zeit,
        valueQuantity: { value: Number(e.wert.toFixed(4)), unit: e.einheit || '1' },
        interpretation: interpretation(e.status),
        referenceRange,
        note: e.hinweis ? [{ text: e.hinweis }] : undefined,
        component: Number.isFinite(e.absolut)
          ? [
              {
                code: { coding: [{ system: LOKALES_SYSTEM, code: `${e.id}_absolut`, display: `${e.name} absolut` }] },
                valueQuantity: { value: Number(e.absolut.toFixed(2)), unit: '/uL' },
                interpretation: interpretation(e.absStatus),
              },
            ]
          : undefined,
      },
    });
  }

  /* --- Scores als eigene Beobachtungen --- */
  for (const s of befund.scores || []) {
    const obsId = uid('obs');
    observationIds.push(obsId);
    eintraege.push({
      fullUrl: `urn:uuid:${obsId}`,
      resource: {
        resourceType: 'Observation',
        id: obsId,
        status: befund.signatur.freigabe ? 'final' : 'preliminary',
        category: [
          { coding: [{ system: 'http://terminology.hl7.org/CodeSystem/observation-category', code: 'laboratory' }] },
        ],
        code: { coding: [{ system: LOKALES_SYSTEM, code: `score_${s.id}`, display: s.name }], text: s.name },
        subject: { reference: `Patient/${patientId}` },
        specimen: { reference: `Specimen/${specimenId}` },
        effectiveDateTime: zeit,
        valueString: `${s.bewertung}${Number.isFinite(s.punkte) ? ` (${s.punkte}/${s.maximum})` : ''}`,
        note: [{ text: s.text }],
      },
    });
  }

  /* --- Qualitaetskontrolle als Beobachtung --- */
  const qcId = uid('obs');
  observationIds.push(qcId);
  eintraege.push({
    fullUrl: `urn:uuid:${qcId}`,
    resource: {
      resourceType: 'Observation',
      id: qcId,
      status: 'final',
      code: { coding: [{ system: LOKALES_SYSTEM, code: 'qc_gesamt', display: 'Messqualität' }], text: 'Messqualität' },
      subject: { reference: `Patient/${patientId}` },
      specimen: { reference: `Specimen/${specimenId}` },
      effectiveDateTime: zeit,
      valueString: befund.qualitaet.overall,
      note: [{ text: befund.qualitaet.summary }],
      component: (befund.qualitaet.checks || []).map((c) => ({
        code: { coding: [{ system: LOKALES_SYSTEM, code: `qc_${c.id}`, display: c.label }] },
        valueString: `${c.status}: ${c.value}`,
      })),
    },
  });

  /* --- Zusammenfassender Bericht --- */
  eintraege.push({
    fullUrl: `urn:uuid:${berichtId}`,
    resource: {
      resourceType: 'DiagnosticReport',
      id: berichtId,
      status: befund.signatur.freigabe ? 'final' : 'preliminary',
      category: [
        {
          coding: [
            { system: 'http://terminology.hl7.org/CodeSystem/v2-0074', code: 'IMM', display: 'Immunology' },
          ],
        },
      ],
      code: { text: `Durchflusszytometrie: ${befund.methode.panel}` },
      subject: { reference: `Patient/${patientId}` },
      specimen: [{ reference: `Specimen/${specimenId}` }],
      effectiveDateTime: zeit,
      issued: zeit,
      performer: befund.signatur.befunder ? [{ display: befund.signatur.befunder }] : undefined,
      resultsInterpreter: befund.signatur.zweitbefunder ? [{ display: befund.signatur.zweitbefunder }] : undefined,
      result: observationIds.map((id) => ({ reference: `Observation/${id}` })),
      conclusion: befund.beurteilung,
      extension: [
        { url: 'urn:flowcyto:beurteilungIstVorschlag', valueBoolean: !!befund.beurteilungIstVorschlag },
        { url: 'urn:flowcyto:software', valueString: `${befund.software.name} ${befund.software.version}` },
        { url: 'urn:flowcyto:hinweis', valueString: befund.hinweisSoftware },
      ],
      presentedForm: undefined,
    },
  });

  return {
    resourceType: 'Bundle',
    type: 'collection',
    timestamp: zeit,
    entry: eintraege,
  };
}

function geschlechtFHIR(g) {
  const s = String(g || '').toLowerCase();
  if (s.startsWith('w') || s.startsWith('f')) return 'female';
  if (s.startsWith('m')) return 'male';
  if (s.startsWith('d')) return 'other';
  return 'unknown';
}
