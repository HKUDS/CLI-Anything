/**
 * Integrationstest ueber die gesamte Kette:
 * FCS-Datei -> Kompensation -> Transformation -> Gating -> Panel-Strategie ->
 * Kennzahlen -> Referenzbewertung -> Scores -> Qualitaetskontrolle -> Befund.
 *
 * Die synthetische Probe hat eine bekannte Zusammensetzung; die Auswertung
 * muss sie innerhalb der erwarteten Toleranz wiederfinden.
 */

import { test, expect, describe, beforeEach } from 'bun:test';

import { state, resetWorkspace, addSample, addGate } from '../src/core/store.js';
import { parseFCS } from '../src/core/fcs.js';
import { channelValues, compensatedData, compensationStatus, scaledValues, findParam, invalidateSample } from '../src/core/data.js';
import { gateCount, gateIndices, gateStats, standardPreGating, autoThresholdGate, makeGate, orderedGates } from '../src/core/gating.js';
import { applyPanel, evaluateMetrics, makeContext } from '../src/core/strategy.js';
import { runQC } from '../src/core/qc.js';
import { autoMapMarkers } from '../src/knowledge/markers.js';
import { panelById, scorePanelFit, PANELS } from '../src/knowledge/panels.js';
import { bewertePanel, differentialdiagnose } from '../src/knowledge/rules.js';
import { erzeugeBefund, befundAlsText } from '../src/report/befund.js';
import { alsFHIR } from '../src/report/fhir.js';
import { makeTBNKSample } from './helpers.js';

let probe;
let soll;

beforeEach(() => {
  resetWorkspace();
  const t = makeTBNKSample(40000, 21);
  soll = t.soll;
  probe = parseFCS(t.buffer, 'tbnk.fcs');
  invalidateSample(probe);
  addSample(probe);
  state.markerMap = autoMapMarkers(probe);
});

/* ================================================================== */
describe('Datenschicht', () => {
  test('Probe wird vollstaendig geladen', () => {
    expect(probe.nEvents).toBe(40000);
    expect(probe.nParams).toBe(10);
    expect(state.markerMap['FITC-A']).toBe('CD3');
  });

  test('Kompensation wird angewandt und veraendert die Werte', () => {
    const status = compensationStatus(probe);
    expect(status.applied).toBe(true);
    expect(status.warning).toBeNull();

    const comp = compensatedData(probe);
    expect(comp).not.toBe(probe.data);
    let unterschiede = 0;
    for (let i = 0; i < 4000; i++) if (Math.abs(comp[i] - probe.data[i]) > 1e-3) unterschiede++;
    expect(unterschiede).toBeGreaterThan(100);
  });

  test('abgeschaltete Kompensation liefert die Rohdaten', () => {
    probe.comp.enabled = false;
    invalidateSample(probe);
    expect(compensatedData(probe)).toBe(probe.data);
    expect(compensationStatus(probe).applied).toBe(false);
  });

  test('skalierte Werte liegen im Anzeigebereich', () => {
    const cd3 = findParam(probe, 'CD3', state.markerMap);
    expect(cd3).toBeGreaterThanOrEqual(0);
    const s = scaledValues(probe, cd3);
    for (let i = 0; i < s.length; i += 97) {
      expect(s[i]).toBeGreaterThanOrEqual(0);
      expect(s[i]).toBeLessThanOrEqual(1);
    }
  });

  test('Kanalzugriff ist zwischengespeichert (identische Referenz)', () => {
    const a = scaledValues(probe, 0);
    const b = scaledValues(probe, 0);
    expect(a).toBe(b);
  });

  test('Marker werden ueber Faerbung und Detektorname gefunden', () => {
    expect(findParam(probe, 'CD45', state.markerMap)).toBe(9);
    expect(findParam(probe, 'FSC-A', {})).toBe(0);
    expect(findParam(probe, 'GibtsNicht', {})).toBe(-1);
  });
});

/* ================================================================== */
describe('Gating', () => {
  test('Standard-Vorgating erzeugt eine Hierarchie', () => {
    const gates = standardPreGating(probe);
    expect(gates.length).toBeGreaterThanOrEqual(2);
    // die Gates sind bereits registriert -- das naechste Gate braucht sein Elternteil
    expect(state.gates.length).toBe(gates.length);

    const singlets = state.gates.find((g) => g.name === 'Singlets');
    expect(singlets).toBeDefined();
    expect(singlets.parentId).toBeTruthy();

    const n = gateCount(probe, singlets.id);
    expect(n).toBeGreaterThan(1000);
    expect(n).toBeLessThanOrEqual(probe.nEvents);
  });

  test('Kindgate ist stets Teilmenge des Elterngates', () => {
    standardPreGating(probe);
    for (const { gate } of orderedGates()) {
      if (!gate.parentId) continue;
      const kind = new Set(Array.from(gateIndices(probe, gate.id)));
      const eltern = new Set(Array.from(gateIndices(probe, gate.parentId)));
      for (const e of kind) expect(eltern.has(e)).toBe(true);
    }
  });

  test('Anteilsangaben sind konsistent', () => {
    const gates = standardPreGating(probe);
    const letztes = gates[gates.length - 1];
    const st = gateStats(probe, letztes.id);
    expect(st.pctParent).toBeGreaterThan(0);
    expect(st.pctParent).toBeLessThanOrEqual(100);
    expect(st.count).toBe(Math.round((st.pctParent / 100) * st.parentCount));
  });

  test('Boolesche Gates verknuepfen korrekt', () => {
    const cd3 = findParam(probe, 'CD3', state.markerMap);
    const cd4 = findParam(probe, 'CD4', state.markerMap);
    const gCD3 = addGate(autoThresholdGate(probe, cd3, null, { above: true, name: 'CD3+' }));
    const gCD4 = addGate(autoThresholdGate(probe, cd4, null, { above: true, name: 'CD4+' }));
    const und = addGate(makeGate({ name: 'CD3+CD4+', type: 'boolean', op: 'AND', refs: [gCD3.id, gCD4.id] }));
    const oder = addGate(makeGate({ name: 'CD3+ oder CD4+', type: 'boolean', op: 'OR', refs: [gCD3.id, gCD4.id] }));
    const nicht = addGate(makeGate({ name: 'nicht CD3+', type: 'boolean', op: 'NOT', refs: [gCD3.id] }));

    const nCD3 = gateCount(probe, gCD3.id);
    const nCD4 = gateCount(probe, gCD4.id);
    const nUnd = gateCount(probe, und.id);
    const nOder = gateCount(probe, oder.id);

    expect(nUnd).toBeLessThanOrEqual(Math.min(nCD3, nCD4));
    expect(nOder).toBeGreaterThanOrEqual(Math.max(nCD3, nCD4));
    // Prinzip von Inklusion und Exklusion
    expect(nOder).toBe(nCD3 + nCD4 - nUnd);
    expect(gateCount(probe, nicht.id)).toBe(probe.nEvents - nCD3);
  });

  test('Loeschen eines Gates entfernt die Kindgates', () => {
    const gates = standardPreGating(probe);
    const wurzel = gates[0];
    const vorher = state.gates.length;
    const { removeGate } = require('../src/core/store.js');
    removeGate(wurzel.id);
    expect(state.gates.length).toBeLessThan(vorher);
    expect(state.gates.some((g) => g.id === wurzel.id)).toBe(false);
  });
});

/* ================================================================== */
describe('Panel-Auswertung TBNK', () => {
  function auswerten() {
    const panel = panelById('tbnk');
    const { stepGates, fehlend } = applyPanel(probe, panel, { markerMap: state.markerMap });
    const { metriken, ctx } = evaluateMetrics(probe, panel, stepGates, state.markerMap);
    return { panel, stepGates, fehlend, metriken, ctx };
  }

  test('Panel wird als passend erkannt', () => {
    const marker = Object.values(state.markerMap);
    const treffer = PANELS.map((p) => scorePanelFit(p, marker)).sort((a, b) => b.score - a.score);
    expect(treffer[0].panel.id).toBe('tbnk');
  });

  test('alle Gating-Schritte lassen sich anlegen', () => {
    const { stepGates, fehlend } = auswerten();
    // CD16 fehlt im Testpanel; CD56 dient als Ersatzmarker
    expect(fehlend.length).toBe(0);
    for (const step of panelById('tbnk').gating) {
      expect(stepGates[step.id], `Schritt ${step.id} fehlt`).toBeTruthy();
    }
  });

  test('Subpopulationen entsprechen der bekannten Zusammensetzung', () => {
    const { metriken } = auswerten();
    const wert = (id) => metriken.find((m) => m.id === id)?.wert;

    expect(wert('tzell_pct')).toBeGreaterThan(soll.tPct - 6);
    expect(wert('tzell_pct')).toBeLessThan(soll.tPct + 6);
    expect(wert('b_pct')).toBeGreaterThan(soll.bPct - 5);
    expect(wert('b_pct')).toBeLessThan(soll.bPct + 5);
    expect(wert('nk_pct')).toBeGreaterThan(soll.nkPct - 5);
    expect(wert('nk_pct')).toBeLessThan(soll.nkPct + 5);
    expect(wert('cd4cd8')).toBeGreaterThan(soll.cd4cd8 - 0.5);
    expect(wert('cd4cd8')).toBeLessThan(soll.cd4cd8 + 0.5);
  });

  test('Plausibilitaetspruefung: Summe T + B + NK ergibt rund 100 %', () => {
    const { metriken } = auswerten();
    const summe = metriken.find((m) => m.id === 'summe').wert;
    expect(summe).toBeGreaterThan(90);
    expect(summe).toBeLessThan(110);
  });

  test('Referenzbewertung erkennt einen auffaelligen Wert', () => {
    const { panel, metriken, ctx } = auswerten();
    const jung = { alterJahre: 40 };
    const normal = bewertePanel(probe, panel, ctx, metriken, jung);
    const cd4 = normal.metriken.find((m) => m.id === 'cd4_pct');
    expect(['normal', 'erhoeht', 'erniedrigt']).toContain(cd4.bewertung.status);

    // Kuenstlich erniedrigter Wert muss als erniedrigt erkannt werden
    const manipuliert = metriken.map((m) => (m.id === 'cd4_pct' ? { ...m, wert: 5 } : m));
    const auffaellig = bewertePanel(probe, panel, ctx, manipuliert, jung);
    const cd4b = auffaellig.metriken.find((m) => m.id === 'cd4_pct');
    expect(cd4b.bewertung.status).toBe('erniedrigt');
    expect(auffaellig.auffaelligkeiten.some((a) => a.includes('T-Helferzellen'))).toBe(true);
  });

  test('Absolutzahlen ueber das Blutbild (Zweiplattform)', () => {
    const { panel, stepGates, metriken } = auswerten();
    probe.kalibrierung = { modus: 'blutbild', refStep: 'lymph', refAbsolut: 2000 };
    const neu = evaluateMetrics(probe, panel, stepGates, state.markerMap);
    const t = neu.metriken.find((m) => m.id === 'tzell_pct');
    expect(Number.isFinite(t.absolut)).toBe(true);
    // T-Zellen absolut muessen dem Anteil an 2000 Lymphozyten/µl entsprechen
    expect(t.absolut).toBeCloseTo((t.wert / 100) * 2000, 0);
  });

  test('Absolutzahlen ueber Zaehlbeads (Einplattform)', () => {
    const { panel, stepGates } = auswerten();
    probe.kalibrierung = { modus: 'beads', beadEreignisse: 5000, beadsProTest: 50000, probenvolumen: 50 };
    const neu = evaluateMetrics(probe, panel, stepGates, state.markerMap);
    const t = neu.metriken.find((m) => m.id === 'tzell_pct');
    const ctx = makeContext(probe, stepGates, state.markerMap);
    const erwartet = (ctx.count('tzell') / 5000) * (50000 / 50);
    expect(t.absolut).toBeCloseTo(erwartet, 6);
  });

  test('ohne Kalibrierung bleiben Absolutzahlen leer', () => {
    const { metriken } = auswerten();
    expect(metriken.find((m) => m.id === 'tzell_pct').absolut).toBeUndefined();
  });
});

/* ================================================================== */
describe('Qualitaetskontrolle', () => {
  test('erkennt eine saubere Messung', () => {
    const qc = runQC(probe);
    expect(qc.checks.length).toBeGreaterThanOrEqual(6);
    expect(['ok', 'warnung']).toContain(qc.overall);
    const rate = qc.checks.find((c) => c.id === 'flussrate');
    expect(rate.status).toBe('ok');
    expect(qc.summary).toBeTruthy();
  });

  test('erkennt eine zu geringe Ereigniszahl', () => {
    const klein = makeTBNKSample(4000, 5);
    const s = parseFCS(klein.buffer, 'klein.fcs');
    const qc = runQC(s);
    const anzahl = qc.checks.find((c) => c.id === 'ereigniszahl');
    expect(anzahl.status).toBe('kritisch');
    expect(qc.overall).toBe('kritisch');
  });

  test('erkennt eine fehlende Kompensation', () => {
    probe.comp.matrix = null;
    probe.comp.enabled = false;
    invalidateSample(probe);
    const qc = runQC(probe);
    const komp = qc.checks.find((c) => c.id === 'kompensation');
    expect(komp.status).toBe('warnung');
  });
});

/* ================================================================== */
describe('Regelwerk', () => {
  test('Differentialdiagnose liefert eine sortierte Trefferliste', () => {
    const panel = panelById('tbnk');
    const { stepGates } = applyPanel(probe, panel, { markerMap: state.markerMap });
    const ctx = makeContext(probe, stepGates, state.markerMap);
    const ddx = differentialdiagnose(ctx, 'tzell');
    if (ddx.length > 1) {
      for (let i = 1; i < ddx.length; i++) {
        expect(ddx[i - 1].passung).toBeGreaterThanOrEqual(ddx[i].passung);
      }
      expect(ddx[0].passung).toBeLessThanOrEqual(1);
    }
  });

  test('Auspraegungsklassen sind plausibel', () => {
    const panel = panelById('tbnk');
    const { stepGates } = applyPanel(probe, panel, { markerMap: state.markerMap });
    const ctx = makeContext(probe, stepGates, state.markerMap);

    // T-Zellen sind CD3-positiv und CD19-negativ
    expect(['positiv', 'stark']).toContain(ctx.expression('tzell', 'CD3').level);
    expect(ctx.expression('tzell', 'CD19').level).toBe('negativ');
    // B-Zellen umgekehrt
    expect(['positiv', 'stark']).toContain(ctx.expression('bzell', 'CD19').level);
    expect(ctx.expression('bzell', 'CD3').level).toBe('negativ');
    // nicht gemessener Marker
    expect(ctx.expression('tzell', 'CD103').vorhanden).toBe(false);
  });
});

/* ================================================================== */
describe('Befund', () => {
  function volleAuswertung() {
    const panel = panelById('tbnk');
    const { stepGates, fehlend, warnungen } = applyPanel(probe, panel, { markerMap: state.markerMap });
    const { metriken, ctx } = evaluateMetrics(probe, panel, stepGates, state.markerMap);
    const bewertung = bewertePanel(probe, panel, ctx, metriken, state.patient);
    const qc = runQC(probe);
    return { panel, stepGates, fehlend, warnungen, metriken, ctx, bewertung, qc };
  }

  test('Befund enthaelt alle Pflichtabschnitte', () => {
    state.patient.pseudonym = 'TEST-001';
    state.patient.alterJahre = 45;
    state.patient.fragestellung = 'Immunstatus bei rezidivierenden Infekten';
    const { panel, bewertung, qc, stepGates } = volleAuswertung();
    const befund = erzeugeBefund({ sample: probe, panel, bewertung, qc, stepGates, patient: state.patient, report: state.report });

    expect(befund.kopf.pseudonym).toBe('TEST-001');
    expect(befund.methode.geraet).toBe('Testzytometer');
    expect(befund.ergebnisse.length).toBeGreaterThan(3);
    expect(befund.gatingStrategie.length).toBeGreaterThan(3);
    expect(befund.qualitaet.overall).toBeTruthy();
    expect(befund.limitationen.length).toBeGreaterThan(0);
    expect(befund.hinweisSoftware).toMatch(/Entscheidungsunterstützung/i);
  });

  test('Beurteilungsvorschlag benennt Abweichungen vom Referenzbereich', () => {
    // Deckt den Zweig ab, der nur bei auffaelligen Werten durchlaufen wird.
    const { panel, metriken, ctx, qc, stepGates } = volleAuswertung();
    const manipuliert = metriken.map((m) => (m.id === 'cd4_pct' ? { ...m, wert: 4 } : m));
    const bewertung = bewertePanel(probe, panel, ctx, manipuliert, { alterJahre: 40 });
    const befund = erzeugeBefund({ sample: probe, panel, bewertung, qc, stepGates, patient: { alterJahre: 40 }, report: state.report });

    expect(befund.beurteilungVorschlag).toContain('Abweichungen vom Referenzbereich');
    expect(befund.beurteilungVorschlag).toContain('T-Helferzellen');
    expect(befund.beurteilungVorschlag).toContain('erniedrigt');
    // Der Vorschlag muss auch im Textbefund landen
    expect(befundAlsText(befund)).toContain('Abweichungen vom Referenzbereich');
  });

  test('Textausgabe enthaelt die Kennzahlen', () => {
    state.patient.pseudonym = 'TEST-002';
    const { panel, bewertung, qc, stepGates } = volleAuswertung();
    const befund = erzeugeBefund({ sample: probe, panel, bewertung, qc, stepGates, patient: state.patient, report: state.report });
    const text = befundAlsText(befund);
    expect(text).toContain('TEST-002');
    expect(text).toContain('T-Zellen');
    expect(text).toContain('BEURTEILUNG');
    expect(text).toContain('METHODE');
    expect(text).toContain('GATING-STRATEGIE');
  });

  test('Freigabe wird ohne Befunder verweigert', () => {
    const { panel, bewertung, qc, stepGates } = volleAuswertung();
    const befund = erzeugeBefund({ sample: probe, panel, bewertung, qc, stepGates, patient: state.patient, report: state.report });
    expect(befund.freigabeMoeglich).toBe(false);
    expect(befund.freigabeHindernisse.some((h) => /Befunder/i.test(h))).toBe(true);
  });

  test('FHIR-Export erzeugt gueltige Ressourcen', () => {
    state.patient.pseudonym = 'TEST-003';
    const { panel, bewertung, qc, stepGates } = volleAuswertung();
    const befund = erzeugeBefund({ sample: probe, panel, bewertung, qc, stepGates, patient: state.patient, report: state.report });
    const bundle = alsFHIR(befund);

    expect(bundle.resourceType).toBe('Bundle');
    expect(bundle.type).toBe('collection');
    const typen = bundle.entry.map((e) => e.resource.resourceType);
    expect(typen).toContain('DiagnosticReport');
    expect(typen).toContain('Observation');

    const bericht = bundle.entry.find((e) => e.resource.resourceType === 'DiagnosticReport').resource;
    expect(bericht.status).toBe('preliminary');
    expect(bericht.result.length).toBeGreaterThan(0);

    const beobachtung = bundle.entry.find((e) => e.resource.resourceType === 'Observation').resource;
    expect(beobachtung.valueQuantity || beobachtung.valueString).toBeTruthy();
    expect(beobachtung.subject.reference).toContain('Patient/');
  });
});
