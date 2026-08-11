/**
 * Qualitaetskontrolle der Messung.
 *
 * Prueft die Punkte, die einen Befund unbrauchbar machen koennen: instabiler
 * Probenfluss, Signaldrift waehrend der Messung, gesaettigte Kanaele,
 * Dublettenlast, zu geringe Ereigniszahl und eine unplausible
 * Kompensationsmatrix. Das Ergebnis erscheint als eigener Abschnitt im Befund;
 * ein "fail" blockiert die Freigabe.
 */

import { channelValues, scaledValues, scatterParams, fluorParams, compensationStatus } from './data.js';
import { assessCompensation } from './compensation.js';
import {
  histogram1D,
  smooth1D,
  percentileSorted,
  channelStats,
  valleyThreshold,
  stainIndex,
} from './stats.js';

const PASS = 'ok';
const WARN = 'warnung';
const FAIL = 'kritisch';

function worst(a, b) {
  const rank = { [PASS]: 0, [WARN]: 1, [FAIL]: 2 };
  return rank[b] > rank[a] ? b : a;
}

/* ------------------------------------------------------------------ */
/* Einzelpruefungen                                                    */
/* ------------------------------------------------------------------ */

/** Stabilitaet der Ereignisrate ueber die Messzeit. */
function checkFlowRate(sample) {
  const sc = scatterParams(sample);
  if (sc.time < 0) {
    return { id: 'flussrate', label: 'Flussratenstabilität', status: WARN, value: '–', detail: 'Kein Zeitkanal aufgezeichnet; zeitliche Stabilität nicht prüfbar.' };
  }
  const scaled = scaledValues(sample, sc.time);
  const nBins = 50;
  const { bins } = histogram1D(scaled, null, nBins);
  const used = Array.from(bins).filter((v) => v > 0);
  if (used.length < 5) {
    return { id: 'flussrate', label: 'Flussratenstabilität', status: WARN, value: '–', detail: 'Zu wenige Zeitintervalle für eine Beurteilung.' };
  }
  const sorted = Float64Array.from(used).sort();
  const med = percentileSorted(sorted, 0.5);
  const mean = used.reduce((a, b) => a + b, 0) / used.length;
  const sd = Math.sqrt(used.reduce((a, b) => a + (b - mean) ** 2, 0) / used.length);
  const cv = mean ? (100 * sd) / mean : 0;
  const outliers = used.filter((v) => Math.abs(v - med) > med * 0.5).length;
  const pctOutlier = (100 * outliers) / used.length;

  const status = cv > 40 || pctOutlier > 20 ? FAIL : cv > 20 || pctOutlier > 10 ? WARN : PASS;
  return {
    id: 'flussrate',
    label: 'Flussratenstabilität',
    status,
    value: `CV ${cv.toFixed(1)} %`,
    detail:
      status === PASS
        ? 'Ereignisrate über die Messdauer konstant.'
        : `${pctOutlier.toFixed(0)} % der Zeitintervalle weichen um mehr als 50 % vom Median ab (Luftblase, Teilverstopfung oder Probenwechsel möglich).`,
    metrics: { cv, pctOutlier },
  };
}

/** Drift des Kanalmedians ueber die Messzeit. */
function checkSignalStability(sample) {
  const sc = scatterParams(sample);
  const fluor = fluorParams(sample);
  if (sc.time < 0 || !fluor.length) {
    return { id: 'signaldrift', label: 'Signalstabilität', status: WARN, value: '–', detail: 'Ohne Zeitkanal nicht prüfbar.' };
  }
  const time = channelValues(sample, sc.time);
  let tMin = Infinity;
  let tMax = -Infinity;
  for (let i = 0; i < time.length; i++) {
    if (time[i] < tMin) tMin = time[i];
    if (time[i] > tMax) tMax = time[i];
  }
  const span = tMax - tMin || 1;
  const nSeg = 10;
  const segIdx = Array.from({ length: nSeg }, () => []);
  for (let i = 0; i < sample.nEvents; i++) {
    let s = Math.floor(((time[i] - tMin) / span) * nSeg);
    if (s < 0) s = 0;
    else if (s >= nSeg) s = nSeg - 1;
    segIdx[s].push(i);
  }

  let maxDrift = 0;
  let worstChannel = '';
  for (const p of fluor) {
    const scaled = scaledValues(sample, p);
    const medians = segIdx
      .filter((seg) => seg.length > 50)
      .map((seg) => channelStats(scaled, Int32Array.from(seg)).median);
    if (medians.length < 3) continue;
    const drift = Math.max(...medians) - Math.min(...medians);
    if (drift > maxDrift) {
      maxDrift = drift;
      worstChannel = sample.params[p].label;
    }
  }

  // Drift in Displaykoordinaten: 0,05 entspricht rund einer Viertel-Dekade.
  const status = maxDrift > 0.1 ? FAIL : maxDrift > 0.05 ? WARN : PASS;
  return {
    id: 'signaldrift',
    label: 'Signalstabilität',
    status,
    value: `max. ${(maxDrift * 100).toFixed(1)} % Skala`,
    detail:
      status === PASS
        ? 'Keine relevante Signaldrift während der Messung.'
        : `Größte Drift im Kanal ${worstChannel}. Ursachen: Laserstabilität, Temperatur, Antikörperablösung.`,
    metrics: { maxDrift, worstChannel },
  };
}

/** Anteil der Ereignisse am Rand des Messbereichs (Saettigung). */
function checkMarginEvents(sample) {
  const issues = [];
  let maxPct = 0;
  for (let p = 0; p < sample.nParams; p++) {
    const param = sample.params[p];
    if (param.isTime) continue;
    const vals = channelValues(sample, p);
    const upper = param.range * 0.995;
    let count = 0;
    for (let i = 0; i < vals.length; i++) if (vals[i] >= upper) count++;
    const pct = (100 * count) / sample.nEvents;
    if (pct > maxPct) maxPct = pct;
    if (pct > 1) issues.push(`${param.label}: ${pct.toFixed(1)} %`);
  }
  const status = maxPct > 5 ? FAIL : maxPct > 1 ? WARN : PASS;
  return {
    id: 'randereignisse',
    label: 'Randereignisse / Sättigung',
    status,
    value: `max. ${maxPct.toFixed(1)} %`,
    detail:
      status === PASS
        ? 'Keine relevante Signalsättigung.'
        : `Ereignisse am oberen Messbereichsende: ${issues.join(', ')}. Verstärkung reduzieren, MFI-Werte dieser Kanäle nicht quantitativ verwerten.`,
    metrics: { maxPct },
  };
}

/** Dublettenanteil aus FSC-A/FSC-H. */
function checkDoublets(sample) {
  const sc = scatterParams(sample);
  if (sc.fscA < 0 || sc.fscH < 0) {
    return { id: 'dubletten', label: 'Dubletten', status: WARN, value: '–', detail: 'FSC-H nicht aufgezeichnet; Dublettenausschluss nicht möglich.' };
  }
  const a = channelValues(sample, sc.fscA);
  const h = channelValues(sample, sc.fscH);
  const ratios = [];
  for (let i = 0; i < sample.nEvents; i++) if (a[i] > 1) ratios.push(h[i] / a[i]);
  if (ratios.length < 100) {
    return { id: 'dubletten', label: 'Dubletten', status: WARN, value: '–', detail: 'Zu wenige auswertbare Ereignisse.' };
  }
  ratios.sort((x, y) => x - y);
  const arr = Float64Array.from(ratios);
  const med = percentileSorted(arr, 0.5);
  const devs = Float64Array.from(ratios.map((r) => Math.abs(r - med))).sort();
  const mad = percentileSorted(devs, 0.5) * 1.4826 || med * 0.05;
  let outside = 0;
  for (const r of ratios) if (Math.abs(r - med) > 3 * mad) outside++;
  const pct = (100 * outside) / ratios.length;

  const status = pct > 20 ? FAIL : pct > 10 ? WARN : PASS;
  return {
    id: 'dubletten',
    label: 'Dublettenanteil',
    status,
    value: `${pct.toFixed(1)} %`,
    detail:
      status === PASS
        ? 'Dublettenanteil im üblichen Bereich.'
        : 'Erhöhter Dublettenanteil: Probe vor Messung filtrieren, Ereignisrate senken.',
    metrics: { pct },
  };
}

/** Ereigniszahl -- Grundlage jeder Aussage zu seltenen Populationen. */
function checkEventCount(sample) {
  const n = sample.nEvents;
  const status = n < 10000 ? FAIL : n < 50000 ? WARN : PASS;
  return {
    id: 'ereigniszahl',
    label: 'Ereigniszahl',
    status,
    value: n.toLocaleString('de-DE'),
    detail:
      n < 10000
        ? 'Zu wenige Ereignisse für eine belastbare Aussage; seltene Populationen sind nicht beurteilbar.'
        : n < 50000
          ? 'Ausreichend für Hauptpopulationen; für seltene Ereignisse (MRD, PNH) zu wenig.'
          : 'Ereigniszahl ausreichend.',
    metrics: { n },
  };
}

/** Plausibilitaet der Kompensationsmatrix. */
function checkCompensation(sample) {
  const status0 = compensationStatus(sample);
  if (!sample.comp?.matrix) {
    const hasFluor = fluorParams(sample).length > 1;
    return {
      id: 'kompensation',
      label: 'Kompensation',
      status: hasFluor ? WARN : PASS,
      value: 'keine Matrix',
      detail: hasFluor
        ? 'Keine Spillover-Matrix in der Datei. Mehrfarbmessungen ohne Kompensation sind nicht quantitativ auswertbar.'
        : 'Einfarbmessung, Kompensation nicht erforderlich.',
    };
  }
  const a = assessCompensation(sample);
  const status = !status0.applied ? FAIL : a.ok ? PASS : WARN;
  return {
    id: 'kompensation',
    label: 'Kompensation',
    status,
    value: status0.applied ? `${sample.comp.channels.length} Kanäle` : 'nicht angewandt',
    detail: status0.warning || (a.ok ? 'Spillover-Matrix plausibel und angewandt.' : a.issues.slice(0, 4).join(' ')),
    metrics: { issues: a.issues },
  };
}

/** Aufloesung der Faerbungen ueber den Faerbeindex. */
function checkResolution(sample) {
  const fluor = fluorParams(sample);
  const weak = [];
  const indices = [];
  for (const p of fluor) {
    const scaled = scaledValues(sample, p);
    const { bins } = histogram1D(scaled, null, 256);
    const thr = valleyThreshold(smooth1D(bins, 2.5)) / 256;
    const neg = [];
    const pos = [];
    for (let i = 0; i < scaled.length; i++) (scaled[i] < thr ? neg : pos).push(i);
    if (neg.length < 100 || pos.length < 100) continue;
    const si = stainIndex(
      channelStats(scaled, Int32Array.from(pos)),
      channelStats(scaled, Int32Array.from(neg)),
    );
    if (Number.isFinite(si)) {
      indices.push({ channel: sample.params[p].label, si });
      if (si < 3) weak.push(`${sample.params[p].label} (SI ${si.toFixed(1)})`);
    }
  }
  if (!indices.length) {
    return { id: 'aufloesung', label: 'Färbeauflösung', status: WARN, value: '–', detail: 'Keine bimodale Verteilung gefunden; Färbeindex nicht berechenbar.' };
  }
  const status = weak.length > fluor.length / 2 ? FAIL : weak.length ? WARN : PASS;
  return {
    id: 'aufloesung',
    label: 'Färbeauflösung (Stain Index)',
    status,
    value: `Median ${percentileSorted(Float64Array.from(indices.map((i) => i.si)).sort(), 0.5).toFixed(1)}`,
    detail: weak.length
      ? `Schwache Trennung: ${weak.slice(0, 5).join(', ')}. Titration, Fluorochromwahl oder Verstärkung prüfen.`
      : 'Alle Kanäle mit ausreichender Positiv-/Negativ-Trennung.',
    metrics: { indices },
  };
}

/* ------------------------------------------------------------------ */
/* Gesamtauswertung                                                    */
/* ------------------------------------------------------------------ */

/**
 * Fuehrt alle Pruefungen aus.
 * @returns {{checks:object[], overall:string, summary:string}}
 */
export function runQC(sample) {
  const checks = [
    checkEventCount(sample),
    checkFlowRate(sample),
    checkSignalStability(sample),
    checkMarginEvents(sample),
    checkDoublets(sample),
    checkCompensation(sample),
    checkResolution(sample),
  ];
  const overall = checks.reduce((acc, c) => worst(acc, c.status), PASS);
  const failed = checks.filter((c) => c.status === FAIL);
  const warned = checks.filter((c) => c.status === WARN);

  let summary;
  if (overall === PASS) summary = 'Messqualität ohne Beanstandung. Befundung uneingeschränkt möglich.';
  else if (overall === WARN)
    summary = `Messqualität mit Einschränkungen: ${warned.map((c) => c.label).join(', ')}. Befundung möglich, betroffene Kennzahlen mit Vorbehalt.`;
  else
    summary = `Messqualität unzureichend: ${failed.map((c) => c.label).join(', ')}. Vor Freigabe prüfen, ggf. Wiederholungsmessung.`;

  sample.qc = { checks, overall, summary, timestamp: new Date().toISOString() };
  return sample.qc;
}

export { PASS, WARN, FAIL };
