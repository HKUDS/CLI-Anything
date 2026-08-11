/**
 * Befunderzeugung.
 *
 * Fuehrt alles zusammen, was die Auswertung ergeben hat: Auftragsdaten,
 * Methodenbeschreibung, Qualitaetskontrolle, die tatsaechlich angewandte
 * Gating-Strategie, Kennzahlen mit Referenzbewertung, Scores,
 * Differentialdiagnose und Limitationen.
 *
 * Der Beurteilungsvorschlag wird aus den Auswertungsergebnissen abgeleitet.
 * Er ersetzt nicht die aerztliche Beurteilung: die Freigabe ist erst moeglich,
 * wenn eine befundende Person eingetragen ist und die Qualitaetskontrolle
 * nicht als kritisch bewertet wurde.
 */

import { gateStats, orderedGates } from '../core/gating.js';
import { gatePath } from '../core/store.js';
import { transformFor, compensationStatus } from '../core/data.js';
import { formatWert } from '../knowledge/rules.js';
import { alterBestimmen } from '../knowledge/reference.js';

export const SOFTWARE = {
  name: 'FlowCyto Befundwerkzeug',
  version: '1.0.0',
  hinweis:
    'Diese Software ist ein Werkzeug zur Entscheidungsunterstützung und kein zertifiziertes In-vitro-Diagnostikum. Alle Auswertungen, Vorschläge und Textbausteine sind vor der Freigabe fachlich zu prüfen und zu verantworten.',
};

function zahl(v, n = 1) {
  return Number.isFinite(v) ? v.toFixed(n).replace('.', ',') : '–';
}

function jetzt() {
  return new Date().toISOString();
}

/* ------------------------------------------------------------------ */
/* Methodenbeschreibung                                                */
/* ------------------------------------------------------------------ */

function methodenblock(sample, panel) {
  const komp = compensationStatus(sample);
  const marker = sample.params
    .filter((p) => !p.isScatter && !p.isTime && p.stain)
    .map((p) => `${p.stain} (${p.name})`);

  // Skalierung: fuer die Zusammenfassung nach Art gruppieren, die genauen
  // Parameter je Kanal aber vollstaendig dokumentieren (Reproduzierbarkeit).
  const nachArt = new Map();
  const skalierungDetails = [];
  for (let i = 0; i < sample.nParams; i++) {
    if (sample.params[i].isTime) continue;
    const tr = transformFor(sample, i);
    nachArt.set(tr.kind, (nachArt.get(tr.kind) || 0) + 1);
    skalierungDetails.push({
      kanal: sample.params[i].label,
      art: tr.kind,
      beschreibung: tr.describe(),
    });
  }
  const artName = { linear: 'linear', log: 'log10', asinh: 'arcsinh', logicle: 'Logicle (biexponentiell)' };

  return {
    verfahren: 'Mehrfarben-Durchflusszytometrie',
    geraet: sample.meta.cytometer || 'nicht angegeben',
    seriennummer: sample.meta.cytometerSN || '',
    software: sample.meta.software || '',
    auswertesoftware: `${SOFTWARE.name} ${SOFTWARE.version}`,
    panel: panel ? panel.name : 'freie Auswertung',
    panelId: panel?.id || null,
    marker,
    ereignisse: sample.nEvents,
    messdatum: sample.meta.date || '',
    messbeginn: sample.meta.btim || '',
    messende: sample.meta.etim || '',
    kompensation: komp.applied
      ? `Spillover-Matrix aus der Messdatei, ${sample.comp.channels.length} Kanäle${sample.comp.tweak ? ', anwenderseitig nachjustiert' : ''}`
      : 'keine Kompensation angewandt',
    kompensationWarnung: komp.warning,
    transformation: [...nachArt.entries()]
      .map(([k, n]) => `${artName[k] || k}: ${n} ${n === 1 ? 'Kanal' : 'Kanäle'}`)
      .join('; '),
    skalierungDetails,
    dateiname: sample.fileName,
    fcsVersion: sample.meta.version,
  };
}

/* ------------------------------------------------------------------ */
/* Gating-Strategie                                                    */
/* ------------------------------------------------------------------ */

/**
 * Dokumentiert die tatsaechlich angewandte Gating-Strategie mit Zellzahlen --
 * die Nachvollziehbarkeit ist Voraussetzung fuer die Befundung.
 */
function gatingBlock(sample) {
  return orderedGates().map(({ gate, depth }) => {
    const st = gateStats(sample, gate.id);
    return {
      ebene: depth,
      name: gate.name,
      pfad: gatePath(gate.id).join(' > '),
      typ: beschreibeGateTyp(gate),
      verfahren: gate.auto ? gate.auto.method : 'manuell festgelegt',
      vorlaeufig: !!gate.auto?.vorlaeufig,
      anzahl: st.count,
      pctParent: st.pctParent,
      pctTotal: st.pctTotal,
      achsen: achsenBeschriftung(sample, gate),
    };
  });
}

function beschreibeGateTyp(gate) {
  switch (gate.type) {
    case 'rect': return 'Rechteck';
    case 'polygon': return 'Polygon';
    case 'ellipse': return 'Ellipse';
    case 'interval': return 'Intervall';
    case 'quadrant': return 'Quadrant';
    case 'boolean': return `Verknüpfung (${gate.op})`;
    default: return gate.type;
  }
}

function achsenBeschriftung(sample, gate) {
  const n = (i) => (i >= 0 && sample.params[i] ? sample.params[i].stain || sample.params[i].name : '');
  if (gate.type === 'boolean') return '';
  if (gate.type === 'interval') return n(gate.xParam);
  return [n(gate.xParam), n(gate.yParam)].filter(Boolean).join(' / ');
}

/* ------------------------------------------------------------------ */
/* Beurteilungsvorschlag                                               */
/* ------------------------------------------------------------------ */

function beurteilungsvorschlag(panel, bewertung, qc, sample) {
  const teile = [];

  const auffaellig = bewertung.metriken.filter(
    (m) => m.bewertung?.status === 'erhoeht' || m.bewertung?.status === 'erniedrigt',
  );
  if (auffaellig.length) {
    teile.push(
      `Abweichungen vom Referenzbereich: ${auffaellig
        .map((m) => `${m.name} ${formatWert(m)} (${m.bewertung.status})`)
        .join('; ')}.`,
    );
  } else if (bewertung.metriken.some((m) => m.referenz)) {
    teile.push('Alle referenzierten Kennzahlen liegen im altersentsprechenden Referenzbereich.');
  }

  for (const s of bewertung.scores) {
    if (s.text) teile.push(s.text);
  }

  if (bewertung.ddx.length) {
    const best = bewertung.ddx[0];
    if (best.passung >= 0.7) {
      const zweiter = bewertung.ddx[1];
      let satz = `Das Immunphänotyp-Muster ist am ehesten vereinbar mit: ${best.entitaet.name}`;
      satz += best.stuetzend.length ? ` (stützend: ${best.stuetzend.slice(0, 6).join(', ')})` : '';
      satz += '.';
      if (zweiter && zweiter.passung >= best.passung - 0.12) {
        satz += ` Differentialdiagnostisch kommt ebenfalls ${zweiter.entitaet.name} in Betracht.`;
      }
      if (best.widersprechend.length) {
        satz += ` Nicht zum Muster passend: ${best.widersprechend.slice(0, 4).join(', ')}.`;
      }
      teile.push(satz);
    }
  }

  if (qc && qc.overall !== 'ok') {
    teile.push(`Einschränkung durch die Messqualität: ${qc.summary}`);
  }

  if (!teile.length) {
    teile.push('Regelrechter durchflusszytometrischer Befund ohne Hinweis auf eine aberrante Zellpopulation.');
  }
  return teile.join(' ');
}

/* ------------------------------------------------------------------ */
/* Limitationen                                                        */
/* ------------------------------------------------------------------ */

function limitationen(sample, panel, bewertung, qc, fehlend, warnungen) {
  const out = [];

  if (fehlend?.length) {
    out.push(`Nicht durchführbare Gating-Schritte wegen fehlender Marker: ${fehlend.join('; ')}.`);
  }
  for (const w of warnungen || []) out.push(w);

  const vorlaeufig = orderedGates().filter(({ gate }) => gate.auto?.vorlaeufig);
  if (vorlaeufig.length) {
    out.push(
      `Folgende Gates stammen als Startvorschlag aus der Panel-Vorlage und müssen vor der Freigabe visuell geprüft werden: ${vorlaeufig
        .map(({ gate }) => gate.name)
        .join(', ')}.`,
    );
  }

  if (qc) {
    for (const c of qc.checks) {
      if (c.status !== 'ok') out.push(`${c.label}: ${c.detail}`);
    }
  }

  if (!sample.kalibrierung?.modus && panel?.absolutzahlen) {
    out.push(
      'Keine Kalibrierung hinterlegt: Absolutzahlen konnten nicht berechnet werden. Erforderlich ist entweder eine Zählbead-Bestimmung (Einplattform) oder ein zeitgleiches Blutbild (Zweiplattform).',
    );
  }

  if (panel?.hochsensitiv && sample.nEvents < 100000) {
    out.push(
      `Für eine hochsensitive Analyse werden mindestens 100 000 Ereignisse gefordert; ausgewertet wurden ${sample.nEvents.toLocaleString('de-DE')}. Die Nachweisgrenze ist entsprechend höher.`,
    );
  }

  for (const h of panel?.hinweise || []) out.push(h);

  return out;
}

/* ------------------------------------------------------------------ */
/* Hauptfunktion                                                       */
/* ------------------------------------------------------------------ */

/**
 * @param {object} args
 * @param {object} args.sample      ausgewertete Probe
 * @param {object} args.panel       verwendetes Panel (optional)
 * @param {object} args.bewertung   Ergebnis aus rules.bewertePanel
 * @param {object} args.qc          Ergebnis aus qc.runQC
 * @param {object} args.patient     Auftrags- und Patientendaten
 * @param {object} args.report      Freitextfelder und Signatur
 * @returns {object} strukturierter Befund
 */
export function erzeugeBefund({ sample, panel, bewertung, qc, stepGates, patient, report, fehlend, warnungen }) {
  const alter = alterBestimmen(patient);

  const ergebnisse = bewertung.metriken.map((m) => ({
    id: m.id,
    name: m.name,
    wert: m.wert,
    text: formatWert(m),
    einheit: m.einheit,
    absolut: m.absolut,
    absolutText: Number.isFinite(m.absolut) ? `${zahl(m.absolut, 0)} /µl` : null,
    referenzText: m.bewertung?.text || '',
    referenzBereich: m.bewertung?.bereich || null,
    status: m.bewertung?.status || 'unbekannt',
    absStatus: m.absBewertung?.status || null,
    absReferenzText: m.absBewertung?.text || '',
    hinweis: m.hinweis || null,
    fehler: m.fehler || null,
  }));

  const vorschlag = beurteilungsvorschlag(panel, bewertung, qc, sample);
  const grenzen = limitationen(sample, panel, bewertung, qc, fehlend, warnungen);

  const hindernisse = [];
  if (!report?.befunder) {
    hindernisse.push('Kein Befunder eingetragen: die Freigabe erfordert eine namentlich benannte befundende Person.');
  }
  if (qc?.overall === 'kritisch') hindernisse.push('Die Qualitätskontrolle ist als kritisch bewertet.');
  if (ergebnisse.some((e) => e.fehler)) hindernisse.push('Mindestens eine Kennzahl konnte nicht berechnet werden.');

  return {
    software: SOFTWARE,
    erstellt: jetzt(),
    revision: report?.revision || 1,

    kopf: {
      pseudonym: patient?.pseudonym || '',
      alterJahre: alter,
      geschlecht: patient?.geschlecht || '',
      material: patient?.material || '',
      entnahme: patient?.entnahme || '',
      eingang: patient?.eingang || '',
      auftragsnummer: patient?.auftragsnummer || '',
      einsender: patient?.einsender || '',
      klinik: patient?.klinik || '',
      fragestellung: patient?.fragestellung || '',
      vorbefunde: patient?.vorbefunde || '',
    },

    methode: methodenblock(sample, panel),
    qualitaet: qc || { overall: 'nicht durchgeführt', summary: 'Keine Qualitätskontrolle durchgeführt.', checks: [] },
    gatingStrategie: gatingBlock(sample),
    ergebnisse,
    scores: bewertung.scores,
    ddx: bewertung.ddx.map((d) => ({
      name: d.entitaet.name,
      kurz: d.entitaet.kurz,
      gruppe: d.entitaet.gruppe,
      passung: d.passung,
      stuetzend: d.stuetzend,
      widersprechend: d.widersprechend,
      nichtGemessen: d.nichtGemessen,
      zusatz: d.entitaet.zusatz,
      dringend: !!d.entitaet.dringend,
    })),

    beurteilungVorschlag: vorschlag,
    beurteilung: report?.beurteilung?.trim() || vorschlag,
    beurteilungIstVorschlag: !report?.beurteilung?.trim(),
    empfehlung: report?.empfehlung?.trim() || bewertung.empfehlungen.join(' '),
    empfehlungen: bewertung.empfehlungen,

    limitationen: grenzen,
    hinweisSoftware: SOFTWARE.hinweis,

    signatur: {
      befunder: report?.befunder || '',
      zweitbefunder: report?.zweitbefunder || '',
      freigabe: report?.freigabe || null,
    },
    freigabeMoeglich: hindernisse.length === 0,
    freigabeHindernisse: hindernisse,
    stepGates: stepGates || {},
  };
}

/* ------------------------------------------------------------------ */
/* Textausgabe                                                         */
/* ------------------------------------------------------------------ */

/** Erzeugt eine reine Textfassung des Befunds (Archiv, LIS-Freitextfeld). */
export function befundAlsText(b) {
  const z = [];
  const linie = (c = '=') => z.push(c.repeat(72));
  const feld = (k, v) => {
    if (v !== null && v !== undefined && v !== '') z.push(`${(k + ':').padEnd(24)}${v}`);
  };

  linie();
  z.push('DURCHFLUSSZYTOMETRISCHER BEFUND');
  linie();
  z.push('');
  z.push('AUFTRAGSDATEN');
  feld('Pseudonym', b.kopf.pseudonym);
  feld('Auftragsnummer', b.kopf.auftragsnummer);
  feld('Alter', Number.isFinite(b.kopf.alterJahre) ? `${b.kopf.alterJahre} Jahre` : '');
  feld('Geschlecht', b.kopf.geschlecht);
  feld('Material', b.kopf.material);
  feld('Entnahme', b.kopf.entnahme);
  feld('Eingang', b.kopf.eingang);
  feld('Einsender', b.kopf.einsender);
  feld('Fragestellung', b.kopf.fragestellung);
  feld('Vorbefunde', b.kopf.vorbefunde);
  z.push('');

  z.push('METHODE');
  feld('Verfahren', b.methode.verfahren);
  feld('Panel', b.methode.panel);
  feld('Gerät', `${b.methode.geraet}${b.methode.seriennummer ? ' / SN ' + b.methode.seriennummer : ''}`);
  feld('Messdatum', b.methode.messdatum);
  feld('Ereignisse', b.methode.ereignisse.toLocaleString('de-DE'));
  feld('Kompensation', b.methode.kompensation);
  feld('Skalierung', b.methode.transformation);
  for (const d of b.methode.skalierungDetails || []) {
    z.push(`${''.padEnd(24)}  ${d.kanal}: ${d.beschreibung}`);
  }
  feld('Antikörper', b.methode.marker.join(', '));
  feld('Auswertung', b.methode.auswertesoftware);
  z.push('');

  z.push('QUALITÄTSKONTROLLE');
  z.push(`Gesamtbewertung: ${b.qualitaet.overall}`);
  z.push(b.qualitaet.summary);
  for (const c of b.qualitaet.checks || []) {
    z.push(`  [${c.status.toUpperCase().padEnd(9)}] ${c.label}: ${c.value}`);
  }
  z.push('');

  z.push('GATING-STRATEGIE');
  for (const g of b.gatingStrategie) {
    const einzug = '  '.repeat(g.ebene + 1);
    z.push(
      `${einzug}${g.name} [${g.typ}${g.achsen ? ', ' + g.achsen : ''}] -- ${g.anzahl.toLocaleString('de-DE')} Ereignisse (${zahl(g.pctParent)} % der Elternpopulation)${g.vorlaeufig ? '  << Startvorschlag, zu pruefen' : ''}`,
    );
  }
  z.push('');

  z.push('ERGEBNISSE');
  for (const e of b.ergebnisse) {
    let zeile = `  ${e.name.padEnd(38)} ${e.text.padStart(16)}`;
    if (e.absolutText) zeile += `   ${e.absolutText.padStart(12)}`;
    if (e.referenzText) zeile += `   ${e.referenzText}`;
    z.push(zeile);
    if (e.hinweis) z.push(`      Hinweis: ${e.hinweis}`);
    if (e.fehler) z.push(`      Nicht berechenbar: ${e.fehler}`);
  }
  z.push('');

  if (b.scores.length) {
    z.push('SCORES');
    for (const s of b.scores) {
      z.push(`  ${s.name} -- ${s.bewertung}`);
      for (const k of s.kriterien || []) {
        z.push(`     [${k.gemessen ? (k.erfuellt ? 'x' : ' ') : '?'}] ${k.name}: ${k.wert}`);
      }
      z.push(`     ${s.text}`);
      if (s.quelle) z.push(`     Grundlage: ${s.quelle}`);
      z.push('');
    }
  }

  if (b.ddx.length) {
    z.push('DIFFERENTIALDIAGNOSTISCHE EINORDNUNG (Vorschlag der Software)');
    for (const d of b.ddx) {
      z.push(`  ${(d.passung * 100).toFixed(0).padStart(3)} %  ${d.name}`);
      if (d.stuetzend.length) z.push(`         stützend: ${d.stuetzend.join(', ')}`);
      if (d.widersprechend.length) z.push(`         abweichend: ${d.widersprechend.join(', ')}`);
      if (d.nichtGemessen.length) z.push(`         nicht gemessen: ${d.nichtGemessen.join(', ')}`);
    }
    z.push('');
  }

  z.push('BEURTEILUNG');
  z.push(umbruch(b.beurteilung, 72));
  if (b.beurteilungIstVorschlag) {
    z.push('');
    z.push('  [Automatisch erzeugter Vorschlag -- ärztlich zu prüfen und zu ersetzen.]');
  }
  z.push('');

  if (b.empfehlung) {
    z.push('EMPFEHLUNG');
    z.push(umbruch(b.empfehlung, 72));
    z.push('');
  }

  if (b.limitationen.length) {
    z.push('LIMITATIONEN UND HINWEISE');
    for (const l of b.limitationen) z.push(`  - ${umbruch(l, 68, '    ')}`);
    z.push('');
  }

  linie('-');
  z.push(`Befunder: ${b.signatur.befunder || '________________________'}`);
  if (b.signatur.zweitbefunder) z.push(`Zweitbefunder: ${b.signatur.zweitbefunder}`);
  z.push(`Freigabe: ${b.signatur.freigabe || 'nicht freigegeben'}`);
  z.push(`Revision ${b.revision}, erstellt ${new Date(b.erstellt).toLocaleString('de-DE')}`);
  z.push('');
  z.push(umbruch(b.hinweisSoftware, 72));
  linie();
  return z.join('\n');
}

/**
 * Bricht Text auf `breite` Zeichen um. `einzug` wird allen Folgezeilen
 * vorangestellt, damit Aufzaehlungen optisch zusammenhaengen.
 */
function umbruch(text, breite, einzug = '') {
  const worte = String(text).split(/\s+/).filter(Boolean);
  const zeilen = [];
  let aktuell = '';
  for (const w of worte) {
    if (aktuell && (aktuell + ' ' + w).length > breite) {
      zeilen.push(aktuell);
      aktuell = w;
    } else {
      aktuell = aktuell ? `${aktuell} ${w}` : w;
    }
  }
  if (aktuell) zeilen.push(aktuell);
  return zeilen.map((z, i) => (i === 0 ? z : einzug + z)).join('\n');
}

/** Kennzahlen als CSV -- fuer Statistik, Studien und LIS-Import. */
export function befundAlsCSV(b) {
  const kopf = ['Kennzahl', 'Wert', 'Einheit', 'Absolut_pro_ul', 'Referenz_unten', 'Referenz_oben', 'Bewertung'];
  const zeilen = b.ergebnisse.map((e) => [
    e.name,
    Number.isFinite(e.wert) ? e.wert.toFixed(4) : '',
    e.einheit,
    Number.isFinite(e.absolut) ? e.absolut.toFixed(1) : '',
    e.referenzBereich ? e.referenzBereich.unten : '',
    e.referenzBereich ? e.referenzBereich.oben : '',
    e.status,
  ]);
  return [kopf, ...zeilen].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
}
