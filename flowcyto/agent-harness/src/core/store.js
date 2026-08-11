/**
 * Zentraler Zustandsspeicher + Event-Bus.
 *
 * Grundregel der App: es gibt genau EINE Quelle der Wahrheit. Jede Ansicht
 * (Plots, Statistik, QC, Cluster, Befund, Export) liest ueber Selektoren aus
 * diesem Store. Kein Modul haelt eine eigene Kopie von Ereignisdaten, Gates
 * oder Statistiken vor -- dadurch koennen Ansichten nicht auseinanderlaufen
 * und jede Auswertung erscheint automatisch im Befund.
 */

const listeners = new Map();

export function on(event, fn) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(fn);
  return () => listeners.get(event).delete(fn);
}

export function emit(event, payload) {
  const set = listeners.get(event);
  if (set) for (const fn of [...set]) fn(payload);
  const all = listeners.get('*');
  if (all) for (const fn of [...all]) fn({ event, payload });
}

/** Monoton steigende Versionszaehler -- Basis der Memoisierung. */
export const version = {
  samples: 0,
  gates: 0,
  transforms: 0,
  compensation: 0,
  panel: 0,
  patient: 0,
};

export function bump(...keys) {
  for (const k of keys) version[k] = (version[k] || 0) + 1;
}

export const state = {
  /** @type {Sample[]} geladene Messungen */
  samples: [],
  activeSampleId: null,
  /** Vergleichsprobe (Normalspender / Vorbefund) fuer Overlays */
  referenceSampleId: null,

  /** @type {Gate[]} flache Liste, Hierarchie ueber parentId */
  gates: [],
  activeGateId: null,

  /** Plot-Kacheln des Arbeitsbereichs */
  layout: [],

  /** aktuell gewaehltes Panel-Template (knowledge/panels.js) */
  panelId: null,

  /** Zuordnung Kanalname -> Markername, pro Probe ueberschreibbar */
  markerMap: {},

  /** Patienten- / Auftragsdaten des Befunds (pseudonymisiert) */
  patient: {
    pseudonym: '',
    geburtsjahr: null,
    alterJahre: null,
    geschlecht: '',
    material: 'EDTA-Blut',
    entnahme: '',
    eingang: '',
    auftragsnummer: '',
    einsender: '',
    fragestellung: '',
    klinik: '',
    vorbefunde: '',
  },

  /** Freitextfelder + Freigabe des Befunds */
  report: {
    beurteilung: '',
    empfehlung: '',
    methodenzusatz: '',
    befunder: '',
    zweitbefunder: '',
    freigabe: null,
    revision: 1,
    historie: [],
  },

  /** Analyse-Ergebnisse, die nicht aus Rohdaten ableitbar sind */
  clusters: {},
  ui: {
    theme: 'dark',
    tab: 'plots',
    plotType: 'density',
    eventLimit: 150000,
    showBackgate: false,
  },
};

/* ------------------------------------------------------------------ */
/* Memoisierung                                                        */
/* ------------------------------------------------------------------ */

const memoCache = new Map();

/**
 * Rechnet `fn` nur neu, wenn sich der Abhaengigkeits-Schluessel geaendert hat.
 * Verhindert, dass Plot, Statistiktabelle und Befund dieselbe Auswertung
 * dreimal ausfuehren.
 */
export function memo(key, deps, fn) {
  const sig = deps.join('|');
  const hit = memoCache.get(key);
  if (hit && hit.sig === sig) return hit.value;
  const value = fn();
  memoCache.set(key, { sig, value });
  return value;
}

export function invalidate(prefix) {
  for (const k of [...memoCache.keys()]) {
    if (!prefix || k.startsWith(prefix)) memoCache.delete(k);
  }
}

/* ------------------------------------------------------------------ */
/* Zugriffshilfen                                                      */
/* ------------------------------------------------------------------ */

let idCounter = 0;
export function uid(prefix = 'id') {
  idCounter += 1;
  return `${prefix}_${Date.now().toString(36)}${idCounter.toString(36)}`;
}

export function activeSample() {
  return state.samples.find((s) => s.id === state.activeSampleId) || state.samples[0] || null;
}

export function sampleById(id) {
  return state.samples.find((s) => s.id === id) || null;
}

export function gateById(id) {
  return state.gates.find((g) => g.id === id) || null;
}

export function childGates(parentId) {
  return state.gates.filter((g) => g.parentId === parentId);
}

/** Pfad eines Gates bis zur Wurzel, z.B. ["Zellen", "Singlets", "Lymphozyten"]. */
export function gatePath(gateId) {
  const path = [];
  let g = gateById(gateId);
  let guard = 0;
  while (g && guard++ < 64) {
    path.unshift(g.name);
    g = g.parentId ? gateById(g.parentId) : null;
  }
  return path;
}

export function addSample(sample) {
  state.samples.push(sample);
  if (!state.activeSampleId) state.activeSampleId = sample.id;
  bump('samples');
  emit('samples:changed', sample);
  return sample;
}

export function removeSample(id) {
  const i = state.samples.findIndex((s) => s.id === id);
  if (i < 0) return;
  state.samples.splice(i, 1);
  if (state.activeSampleId === id) state.activeSampleId = state.samples[0]?.id || null;
  invalidate();
  bump('samples');
  emit('samples:changed', null);
}

export function addGate(gate) {
  gate.id = gate.id || uid('gate');
  state.gates.push(gate);
  bump('gates');
  invalidate('gate');
  emit('gates:changed', gate);
  return gate;
}

export function updateGate(id, patch) {
  const g = gateById(id);
  if (!g) return null;
  Object.assign(g, patch);
  bump('gates');
  invalidate('gate');
  emit('gates:changed', g);
  return g;
}

/** Entfernt ein Gate samt aller Kindgates. */
export function removeGate(id) {
  const doomed = new Set([id]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const g of state.gates) {
      if (g.parentId && doomed.has(g.parentId) && !doomed.has(g.id)) {
        doomed.add(g.id);
        grew = true;
      }
    }
  }
  state.gates = state.gates.filter((g) => !doomed.has(g.id));
  if (doomed.has(state.activeGateId)) state.activeGateId = null;
  bump('gates');
  invalidate('gate');
  emit('gates:changed', null);
}

/**
 * Setzt den Arbeitsbereich zurueck. `behalte` erlaubt, Proben zu erhalten und
 * nur Gates, Panel und Befund zu verwerfen (z. B. beim Panelwechsel).
 */
export function resetWorkspace(behalte = {}) {
  if (!behalte.samples) {
    state.samples = [];
    state.activeSampleId = null;
    state.referenceSampleId = null;
    state.markerMap = {};
  }
  state.gates = [];
  state.activeGateId = null;
  state.layout = [];
  state.clusters = {};
  if (!behalte.panel) state.panelId = null;
  if (!behalte.patient) {
    Object.assign(state.patient, {
      pseudonym: '', geburtsjahr: null, alterJahre: null, geschlecht: '',
      material: 'EDTA-Blut', entnahme: '', eingang: '', auftragsnummer: '',
      einsender: '', fragestellung: '', klinik: '', vorbefunde: '',
    });
  }
  if (!behalte.report) {
    Object.assign(state.report, {
      beurteilung: '', empfehlung: '', methodenzusatz: '',
      befunder: '', zweitbefunder: '', freigabe: null, revision: 1, historie: [],
    });
  }
  invalidate();
  bump('samples', 'gates', 'transforms', 'compensation', 'panel', 'patient');
  emit('workspace:reset', null);
}

export function setPatient(patch) {
  Object.assign(state.patient, patch);
  bump('patient');
  emit('patient:changed', state.patient);
}

export function setReport(patch) {
  Object.assign(state.report, patch);
  emit('report:changed', state.report);
}
