/**
 * Ausfuehrung der Panel-Strategien.
 *
 * Wandelt die deklarative Beschreibung aus knowledge/panels.js in echte Gates
 * um und stellt den Auswertungskontext bereit, in dem die Kennzahlausdruecke
 * berechnet werden. Das ist die Nahtstelle, an der Panelauswahl, Gating,
 * Statistik, Regelwerk und Befund zusammenlaufen.
 */

import { addGate, state, bump, invalidate } from './store.js';
import { findParam, scatterParams, scaledValues, channelValues } from './data.js';
import {
  autoSingletGate,
  autoTimeGate,
  autoModeGate,
  autoThresholdGate,
  makeGate,
  gateIndices,
  gateCount,
} from './gating.js';
import { channelStats, histogram1D, smooth1D, valleyThreshold, rareEventLimits, poissonCI } from './stats.js';
import { canonicalMarker } from '../knowledge/markers.js';

/* ------------------------------------------------------------------ */
/* Markerbezug                                                         */
/* ------------------------------------------------------------------ */

/** Loest einen Marker- oder Streulichtbezug aus der Strategie zum Kanalindex. */
export function resolveMarker(sample, ref, markerMap) {
  if (ref == null) return -1;
  const sc = scatterParams(sample);
  const upper = String(ref).toUpperCase().replace(/\s/g, '');
  if (upper === 'FSC-A' || upper === 'FSCA') return sc.fscA;
  if (upper === 'FSC-H') return sc.fscH;
  if (upper === 'SSC-A' || upper === 'SSCA') return sc.sscA;
  if (upper === 'SSC-H') return sc.sscH;
  if (upper === 'TIME') return sc.time;

  const canon = canonicalMarker(ref) || ref;
  let i = findParam(sample, canon, markerMap);
  if (i < 0 && canon !== ref) i = findParam(sample, ref, markerMap);
  return i;
}

/* ------------------------------------------------------------------ */
/* Strategie ausfuehren                                                */
/* ------------------------------------------------------------------ */

/**
 * Erzeugt die Gates eines Panels.
 * @returns {{stepGates:Object<string,string>, fehlend:string[], warnungen:string[]}}
 */
export function applyPanel(sample, panel, opts = {}) {
  const markerMap = opts.markerMap || state.markerMap || {};
  const stepGates = {};
  const fehlend = [];
  const warnungen = [];

  for (const step of panel.gating) {
    const parentId = step.parent ? stepGates[step.parent] : opts.rootGateId || null;
    if (step.parent && !parentId) {
      warnungen.push(`Schritt "${step.name}" übersprungen: Elternschritt "${step.parent}" fehlt.`);
      continue;
    }

    let gate = null;
    try {
      gate = buildStep(sample, step, parentId, markerMap);
    } catch (err) {
      warnungen.push(`Schritt "${step.name}" fehlgeschlagen: ${err.message}`);
      continue;
    }

    if (!gate) {
      const mk = step.marker || `${step.x || ''}/${step.y || ''}`;
      fehlend.push(`${step.name} (${mk})`);
      continue;
    }
    gate.panelStep = step.id;
    gate.panelId = panel.id;
    addGate(gate);
    stepGates[step.id] = gate.id;
  }

  invalidate('gate');
  invalidate('idx');
  bump('gates');
  return { stepGates, fehlend, warnungen };
}

function buildStep(sample, step, parentId, markerMap) {
  switch (step.kind) {
    case 'time':
      return autoTimeGate(sample, parentId);

    case 'singlets':
      return autoSingletGate(sample, parentId);

    case 'mode2d': {
      const xi = resolveMarker(sample, step.x, markerMap);
      const yi = resolveMarker(sample, step.y, markerMap);
      if (xi < 0 || yi < 0) return null;
      return autoModeGate(sample, xi, yi, parentId, {
        which: step.which || 'largest',
        name: step.name,
        nSD: step.nSD ?? 2.2,
        minFsc: step.minFsc ?? 0.08,
      });
    }

    case 'threshold': {
      let pi = resolveMarker(sample, step.marker, markerMap);
      if (pi < 0 && step.altMarker) pi = resolveMarker(sample, step.altMarker, markerMap);
      if (pi < 0) return null;
      return autoThresholdGate(sample, pi, parentId, {
        method: step.method || 'valley',
        quantile: step.quantile,
        above: step.above !== false,
        name: step.name,
      });
    }

    case 'region': {
      const xi = resolveMarker(sample, step.x, markerMap);
      const yi = resolveMarker(sample, step.y, markerMap);
      if (xi < 0 || yi < 0) return null;
      const r = step.region;
      return makeGate({
        name: step.name,
        parentId,
        type: 'rect',
        xParam: xi,
        yParam: yi,
        geom: { x1: r.x1, y1: r.y1, x2: r.x2, y2: r.y2 },
        auto: { method: 'Startvorschlag aus Panel-Vorlage -- vor Freigabe prüfen', vorlaeufig: true },
      });
    }

    case 'boolean': {
      return makeGate({
        name: step.name,
        parentId,
        type: 'boolean',
        op: step.op || 'AND',
        refs: step.refs || [],
      });
    }

    default:
      throw new Error(`Unbekannte Schrittart "${step.kind}".`);
  }
}

/* ------------------------------------------------------------------ */
/* Kalibrierung fuer Absolutzahlen                                     */
/* ------------------------------------------------------------------ */

/**
 * @typedef {object} Kalibrierung
 * @property {'beads'|'blutbild'|null} modus
 * @property {number} [beadEreignisse]  gezaehlte Beads
 * @property {number} [beadsProTest]    Beads laut Chargenzertifikat
 * @property {number} [probenvolumen]   eingesetztes Volumen in µl
 * @property {string} [refStep]         Bezugspopulation bei Zweiplattform
 * @property {number} [refAbsolut]      Absolutwert der Bezugspopulation (/µl)
 */

export function absoluteCount(sample, ctx, stepId) {
  const kal = sample.kalibrierung;
  if (!kal || !kal.modus) return NaN;

  if (kal.modus === 'beads') {
    const { beadEreignisse, beadsProTest, probenvolumen } = kal;
    if (!beadEreignisse || !beadsProTest || !probenvolumen) return NaN;
    const n = ctx.count(stepId);
    return (n / beadEreignisse) * (beadsProTest / probenvolumen);
  }

  if (kal.modus === 'blutbild') {
    const { refStep, refAbsolut } = kal;
    if (!refStep || !Number.isFinite(refAbsolut)) return NaN;
    const refN = ctx.count(refStep);
    if (!refN) return NaN;
    return (ctx.count(stepId) / refN) * refAbsolut;
  }
  return NaN;
}

/* ------------------------------------------------------------------ */
/* Auswertungskontext                                                  */
/* ------------------------------------------------------------------ */

/**
 * Stellt die in den Kennzahlausdruecken verfuegbaren Funktionen bereit.
 * Alle Zahlen stammen aus core/stats.js -- es gibt keine zweite Rechenquelle.
 */
export function makeContext(sample, stepGates, markerMap = {}) {
  const gateOf = (step) => stepGates[step] || null;
  const posCache = new Map();

  const ctx = {
    sample,
    stepGates,

    count(step) {
      const g = gateOf(step);
      if (g === null && step !== 'root') return NaN;
      return gateCount(sample, g);
    },

    total() {
      return sample.nEvents;
    },

    pctOf(step, ref) {
      const a = ctx.count(step);
      const b = ctx.count(ref);
      return b ? (100 * a) / b : NaN;
    },

    ratio(a, b) {
      const na = ctx.count(a);
      const nb = ctx.count(b);
      return nb ? na / nb : NaN;
    },

    /** Median-Fluoreszenzintensitaet in linearen Einheiten. */
    mfi(step, marker) {
      const g = gateOf(step);
      const pi = resolveMarker(sample, marker, markerMap);
      if (pi < 0) return NaN;
      const idx = gateIndices(sample, g);
      return channelStats(channelValues(sample, pi), idx).median;
    },

    /** Median in Displaykoordinaten -- geraeteunabhaengiger Vergleich. */
    mfiScaled(step, marker) {
      const g = gateOf(step);
      const pi = resolveMarker(sample, marker, markerMap);
      if (pi < 0) return NaN;
      const idx = gateIndices(sample, g);
      return channelStats(scaledValues(sample, pi), idx).median;
    },

    mfiRatio(a, b, marker) {
      const ma = ctx.mfi(a, marker);
      const mb = ctx.mfi(b, marker);
      return mb ? ma / mb : NaN;
    },

    /** Anteil positiver Zellen anhand einer automatisch bestimmten Schwelle. */
    posPct(step, marker) {
      const key = `${step}|${marker}`;
      if (posCache.has(key)) return posCache.get(key);
      const g = gateOf(step);
      const pi = resolveMarker(sample, marker, markerMap);
      if (pi < 0) {
        posCache.set(key, NaN);
        return NaN;
      }
      const scaled = scaledValues(sample, pi);
      const idx = gateIndices(sample, g);
      if (!idx.length) {
        posCache.set(key, NaN);
        return NaN;
      }
      const { bins } = histogram1D(scaled, null, 256);
      const thr = valleyThreshold(smooth1D(bins, 2.5)) / 256;
      let c = 0;
      for (let i = 0; i < idx.length; i++) if (scaled[idx[i]] >= thr) c++;
      const v = (100 * c) / idx.length;
      posCache.set(key, v);
      return v;
    },

    /**
     * Auspraegungsklasse eines Markers in einer Population.
     *
     * Bezugspunkt ist die interne Negativpopulation derselben Messung (alle
     * Ereignisse unterhalb der automatisch bestimmten Schwelle). `delta` ist
     * der Abstand der Mediane in Displaykoordinaten; 1,0 entspricht dem
     * gesamten Messbereich, bei 4,5 Dekaden also rund 0,22 je Dekade.
     *
     * Die Klassengrenzen sind eine Konvention dieser Software und ersetzen
     * nicht die visuelle Kontrolle im Histogramm.
     */
    expression(step, marker) {
      const key = `expr|${step}|${marker}`;
      if (posCache.has(key)) return posCache.get(key);
      const pi = resolveMarker(sample, marker, markerMap);
      const leer = { vorhanden: false, pct: NaN, delta: NaN, level: 'nicht gemessen', mfi: NaN };
      if (pi < 0) {
        posCache.set(key, leer);
        return leer;
      }
      const scaled = scaledValues(sample, pi);
      const idx = gateIndices(sample, gateOf(step));
      if (idx.length < 20) {
        posCache.set(key, { ...leer, vorhanden: true, level: 'zu wenige Ereignisse' });
        return posCache.get(key);
      }
      const { bins } = histogram1D(scaled, null, 256);
      const thr = valleyThreshold(smooth1D(bins, 2.5)) / 256;

      const negIdx = [];
      for (let i = 0; i < sample.nEvents; i++) if (scaled[i] < thr) negIdx.push(i);
      const medNeg = negIdx.length > 20 ? channelStats(scaled, Int32Array.from(negIdx)).median : thr * 0.5;
      const medPos = channelStats(scaled, idx).median;
      const delta = medPos - medNeg;

      let c = 0;
      for (let i = 0; i < idx.length; i++) if (scaled[idx[i]] >= thr) c++;
      const pct = (100 * c) / idx.length;

      let level;
      if (pct < 20 || delta < 0.06) level = 'negativ';
      else if (delta < 0.20) level = 'schwach';
      else if (delta < 0.42) level = 'positiv';
      else level = 'stark';

      const res = {
        vorhanden: true,
        pct,
        delta,
        level,
        schwelle: thr,
        mfi: channelStats(channelValues(sample, pi), idx).median,
        param: pi,
      };
      posCache.set(key, res);
      return res;
    },

    abs(step) {
      return absoluteCount(sample, ctx, step);
    },

    lod(step) {
      return rareEventLimits(ctx.count(step)).lod;
    },

    lloq(step) {
      return rareEventLimits(ctx.count(step)).lloq;
    },

    /** 95-%-Vertrauensbereich eines Anteils (Poisson). */
    ci(step, ref) {
      return poissonCI(ctx.count(step), ctx.count(ref));
    },

    /** Vorhandensein eines Markers im Panel pruefen. */
    hasMarker(marker) {
      return resolveMarker(sample, marker, markerMap) >= 0;
    },

    /** Kanalindex -- fuer die Regelauswertung. */
    param(marker) {
      return resolveMarker(sample, marker, markerMap);
    },

    gateId: gateOf,
  };
  return ctx;
}

/* ------------------------------------------------------------------ */
/* Ausdrucksauswertung                                                 */
/* ------------------------------------------------------------------ */

/**
 * Winziger rekursiver Parser fuer die Kennzahlausdruecke.
 * Funktionsargumente werden als rohe Bezeichner gelesen, damit Kanalnamen
 * wie "SSC-A" oder "7-AAD" verwendbar sind.
 */
export function evaluateExpression(expr, ctx) {
  let pos = 0;
  const s = String(expr);

  const skipSpace = () => {
    while (pos < s.length && /\s/.test(s[pos])) pos++;
  };

  function parseExpr() {
    let value = parseTerm();
    for (;;) {
      skipSpace();
      const op = s[pos];
      if (op === '+' || op === '-') {
        pos++;
        const rhs = parseTerm();
        value = op === '+' ? value + rhs : value - rhs;
      } else break;
    }
    return value;
  }

  function parseTerm() {
    let value = parseFactor();
    for (;;) {
      skipSpace();
      const op = s[pos];
      if (op === '*' || op === '/') {
        pos++;
        const rhs = parseFactor();
        value = op === '*' ? value * rhs : value / rhs;
      } else break;
    }
    return value;
  }

  function parseFactor() {
    skipSpace();
    if (s[pos] === '-') {
      pos++;
      return -parseFactor();
    }
    if (s[pos] === '(') {
      pos++;
      const v = parseExpr();
      skipSpace();
      if (s[pos] === ')') pos++;
      return v;
    }
    const numMatch = /^\d+(\.\d+)?/.exec(s.slice(pos));
    if (numMatch) {
      pos += numMatch[0].length;
      return parseFloat(numMatch[0]);
    }
    const idMatch = /^[A-Za-z_][A-Za-z0-9_]*/.exec(s.slice(pos));
    if (!idMatch) throw new Error(`Unerwartetes Zeichen "${s[pos]}" in "${s}".`);
    const name = idMatch[0];
    pos += name.length;
    skipSpace();
    if (s[pos] !== '(') throw new Error(`Funktionsaufruf erwartet bei "${name}".`);
    pos++;
    const args = [];
    let depth = 0;
    let current = '';
    while (pos < s.length) {
      const ch = s[pos];
      if (ch === '(') depth++;
      if (ch === ')') {
        if (depth === 0) break;
        depth--;
      }
      if (ch === ',' && depth === 0) {
        args.push(current.trim());
        current = '';
        pos++;
        continue;
      }
      current += ch;
      pos++;
    }
    if (current.trim()) args.push(current.trim());
    if (s[pos] === ')') pos++;

    const fn = ctx[name];
    if (typeof fn !== 'function') throw new Error(`Unbekannte Funktion "${name}".`);
    return fn.apply(ctx, args);
  }

  const result = parseExpr();
  return result;
}

/**
 * Berechnet alle Kennzahlen eines Panels.
 * @returns {Array<{id,name,wert,einheit,...}>}
 */
export function evaluateMetrics(sample, panel, stepGates, markerMap) {
  const ctx = makeContext(sample, stepGates, markerMap);
  const out = [];
  for (const m of panel.metriken || []) {
    let wert = NaN;
    let fehler = null;
    try {
      wert = evaluateExpression(m.ausdruck, ctx);
    } catch (err) {
      fehler = err.message;
    }
    const eintrag = {
      id: m.id,
      name: m.name,
      wert,
      einheit: m.einheit || '',
      nachkomma: m.nachkomma ?? 1,
      referenz: m.referenz || null,
      schwellen: m.schwellen || null,
      plausibilitaet: m.plausibilitaet || null,
      fehler,
    };
    if (m.absolutVon && sample.kalibrierung?.modus) {
      eintrag.absolut = absoluteCount(sample, ctx, m.absolutVon);
    }
    out.push(eintrag);
  }
  return { metriken: out, ctx };
}
