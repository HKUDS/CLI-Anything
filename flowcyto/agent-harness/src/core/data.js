/**
 * Zentrale Datenschicht.
 *
 * Alles, was Ereignisdaten braucht -- Plots, Gates, Statistik, QC, Clustering,
 * Befund --, holt sie hier. Kompensation und Transformation werden je Probe und
 * Kanal genau einmal berechnet und zwischengespeichert. Damit gibt es keine
 * zweite Rechenstrecke, die abweichende Werte liefern koennte.
 */

import { emit } from './store.js';
import { computeCompensated } from './compensation.js';
import { makeTransform, autoTransformSpec } from './transform.js';

const cache = new WeakMap(); // sample -> {compData, compWarning, channels:Map, scaled:Map, transforms:Map}

function entry(sample) {
  let e = cache.get(sample);
  if (!e) {
    e = { compData: null, compWarning: null, channels: new Map(), scaled: new Map(), transforms: new Map() };
    cache.set(sample, e);
  }
  return e;
}

/** Verwirft Zwischenergebnisse -- nach Aenderung der Kompensation. */
export function invalidateSample(sample, what = 'all') {
  const e = entry(sample);
  if (what === 'all' || what === 'comp') {
    e.compData = null;
    e.channels.clear();
    e.scaled.clear();
    e.transforms.clear();
  } else if (what === 'transform') {
    e.scaled.clear();
    e.transforms.clear();
  }
  emit('data:invalidated', { sample, what });
}

/** Kompensierte Rohdaten der gesamten Probe (event-major). */
export function compensatedData(sample) {
  const e = entry(sample);
  if (!e.compData) {
    const r = computeCompensated(sample);
    e.compData = r.data;
    e.compWarning = r.warning;
    e.compApplied = r.applied;
  }
  return e.compData;
}

export function compensationStatus(sample) {
  compensatedData(sample);
  const e = entry(sample);
  return { applied: !!e.compApplied, warning: e.compWarning };
}

/** Kompensierte Werte eines einzelnen Kanals, linear. */
export function channelValues(sample, paramIndex) {
  const e = entry(sample);
  const hit = e.channels.get(paramIndex);
  if (hit) return hit;

  const src = compensatedData(sample);
  const nPar = sample.nParams;
  const out = new Float32Array(sample.nEvents);
  for (let i = 0; i < sample.nEvents; i++) out[i] = src[i * nPar + paramIndex];
  e.channels.set(paramIndex, out);
  return out;
}

/** Transformationsobjekt eines Kanals (Voreinstellung aus den Daten geschaetzt). */
export function transformFor(sample, paramIndex) {
  const e = entry(sample);
  const hit = e.transforms.get(paramIndex);
  if (hit) return hit;

  let spec = sample.transforms[paramIndex];
  if (!spec) {
    spec = autoTransformSpec(sample, paramIndex, channelValues(sample, paramIndex));
    sample.transforms[paramIndex] = spec;
  }
  const tr = makeTransform(spec);
  e.transforms.set(paramIndex, tr);
  return tr;
}

export function setTransform(sample, paramIndex, spec) {
  sample.transforms[paramIndex] = spec;
  const e = entry(sample);
  e.transforms.delete(paramIndex);
  e.scaled.delete(paramIndex);
  emit('data:invalidated', { sample, what: 'transform', paramIndex });
}

/** Auf [0,1] skalierte Werte eines Kanals -- die Anzeige- und Gate-Koordinaten. */
export function scaledValues(sample, paramIndex) {
  const e = entry(sample);
  const hit = e.scaled.get(paramIndex);
  if (hit) return hit;

  const tr = transformFor(sample, paramIndex);
  const raw = channelValues(sample, paramIndex);
  const out = tr.applyArray(raw);
  e.scaled.set(paramIndex, out);
  return out;
}

/* ------------------------------------------------------------------ */
/* Kanalsuche                                                          */
/* ------------------------------------------------------------------ */

/** Normalisiert Marker- und Kanalnamen fuer den Abgleich. */
export function normalizeName(s) {
  return String(s || '')
    .toUpperCase()
    .replace(/\s+/g, '')
    .replace(/[-_.]/g, '')
    .replace(/^CY?D/, 'CD');
}

/**
 * Findet den Parameterindex zu einem Marker ("CD3", "Kappa", "FSC-A").
 * Sucht in $PnS (Faerbung), $PnN (Detektor) und in der manuellen Zuordnung.
 * @returns {number} Index oder -1
 */
export function findParam(sample, marker, markerMap = {}) {
  if (marker == null) return -1;
  const want = normalizeName(marker);
  if (!want) return -1;

  // 1. manuelle Zuordnung hat Vorrang
  for (const [chan, mk] of Object.entries(markerMap)) {
    if (normalizeName(mk) === want) {
      const i = sample.params.findIndex((p) => p.name === chan);
      if (i >= 0) return i;
    }
  }
  // 2. exakter Treffer im Faerbungsfeld
  let i = sample.params.findIndex((p) => normalizeName(p.stain) === want);
  if (i >= 0) return i;
  // 3. exakter Treffer im Detektornamen (FSC-A, SSC-A, Time)
  i = sample.params.findIndex((p) => normalizeName(p.name) === want);
  if (i >= 0) return i;
  // 4. Marker als Wortbestandteil der Faerbung ("CD3 FITC")
  const re = new RegExp(`(^|[^A-Z0-9])${escapeRe(want)}([^A-Z0-9]|$)`);
  i = sample.params.findIndex((p) => re.test(normalizeName(p.stain).replace(/(CD\d+)/g, ' $1 ')));
  if (i >= 0) return i;
  i = sample.params.findIndex((p) => normalizeName(p.stain).startsWith(want));
  if (i >= 0) return i;
  return -1;
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Erste vorhandene Variante aus einer Liste von Synonymen. */
export function findAnyParam(sample, markers, markerMap) {
  for (const m of markers) {
    const i = findParam(sample, m, markerMap);
    if (i >= 0) return i;
  }
  return -1;
}

/** Kanaele, die als Streulicht gelten. */
export function scatterParams(sample) {
  return {
    fscA: findAnyParam(sample, ['FSC-A', 'FSCA', 'FSC'], {}),
    fscH: findAnyParam(sample, ['FSC-H', 'FSCH'], {}),
    fscW: findAnyParam(sample, ['FSC-W', 'FSCW'], {}),
    sscA: findAnyParam(sample, ['SSC-A', 'SSCA', 'SSC'], {}),
    sscH: findAnyParam(sample, ['SSC-H', 'SSCH'], {}),
    time: findAnyParam(sample, ['Time'], {}),
  };
}

/** Indizes aller Fluoreszenzkanaele (ohne Streulicht und Zeit). */
export function fluorParams(sample) {
  const out = [];
  sample.params.forEach((p, i) => {
    if (!p.isScatter && !p.isTime) out.push(i);
  });
  return out;
}
