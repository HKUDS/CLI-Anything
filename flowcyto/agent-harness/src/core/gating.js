/**
 * Gating: Geometrie, Hierarchie, Boolesche Verknuepfung und Automatik.
 *
 * Gates werden in Displaykoordinaten [0,1] gespeichert -- also exakt in der
 * Skala, in der sie gezeichnet wurden. Die Zugehoerigkeit eines Ereignisses
 * wird pro Probe zwischengespeichert und von Plot, Statistik, Cluster und
 * Befund gemeinsam genutzt.
 *
 * Automatische Gates erzeugen immer eine sichtbare, nachtraeglich
 * veraenderbare Form. Eine Blackbox waere fuer eine Befundung nicht
 * nachvollziehbar.
 */

import { memo, version, gateById, state, uid, addGate } from './store.js';
import { scaledValues, channelValues, transformFor, scatterParams } from './data.js';
import {
  densityGrid,
  findPeaks2D,
  floodRegion,
  histogram1D,
  smooth1D,
  otsuThreshold,
  valleyThreshold,
  ellipseFromPoints,
  percentileSorted,
} from './stats.js';

/* ------------------------------------------------------------------ */
/* Geometrietests                                                      */
/* ------------------------------------------------------------------ */

export function pointInPolygon(px, py, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const xi = points[i][0];
    const yi = points[i][1];
    const xj = points[j][0];
    const yj = points[j][1];
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function pointInEllipse(px, py, g) {
  const cos = Math.cos(-g.angle || 0);
  const sin = Math.sin(-g.angle || 0);
  const dx = px - g.cx;
  const dy = py - g.cy;
  const rx = (dx * cos - dy * sin) / (g.rx || 1e-9);
  const ry = (dx * sin + dy * cos) / (g.ry || 1e-9);
  return rx * rx + ry * ry <= 1;
}

/* ------------------------------------------------------------------ */
/* Zugehoerigkeit                                                      */
/* ------------------------------------------------------------------ */

/** Maske allein aus der eigenen Geometrie eines Gates (ohne Elternkette). */
function ownMask(sample, gate) {
  const n = sample.nEvents;
  const mask = new Uint8Array(n);

  if (gate.type === 'boolean') {
    const parts = (gate.refs || []).map((id) => resolveGate(sample, id));
    if (!parts.length) return mask;
    if (gate.op === 'NOT') {
      const a = parts[0];
      for (let i = 0; i < n; i++) mask[i] = a[i] ? 0 : 1;
    } else if (gate.op === 'OR') {
      for (let i = 0; i < n; i++) {
        let v = 0;
        for (const p of parts) if (p[i]) { v = 1; break; }
        mask[i] = v;
      }
    } else {
      for (let i = 0; i < n; i++) {
        let v = 1;
        for (const p of parts) if (!p[i]) { v = 0; break; }
        mask[i] = v;
      }
    }
    return mask;
  }

  if (gate.type === 'all') {
    mask.fill(1);
    return mask;
  }

  if (gate.type === 'interval') {
    const xs = scaledValues(sample, gate.xParam);
    const { min, max } = gate.geom;
    for (let i = 0; i < n; i++) mask[i] = xs[i] >= min && xs[i] <= max ? 1 : 0;
    return mask;
  }

  const xs = scaledValues(sample, gate.xParam);
  const ys = scaledValues(sample, gate.yParam);

  if (gate.type === 'rect') {
    const { x1, y1, x2, y2 } = gate.geom;
    const xa = Math.min(x1, x2);
    const xb = Math.max(x1, x2);
    const ya = Math.min(y1, y2);
    const yb = Math.max(y1, y2);
    for (let i = 0; i < n; i++) {
      mask[i] = xs[i] >= xa && xs[i] <= xb && ys[i] >= ya && ys[i] <= yb ? 1 : 0;
    }
  } else if (gate.type === 'ellipse') {
    for (let i = 0; i < n; i++) mask[i] = pointInEllipse(xs[i], ys[i], gate.geom) ? 1 : 0;
  } else if (gate.type === 'polygon') {
    const pts = gate.geom.points;
    for (let i = 0; i < n; i++) mask[i] = pointInPolygon(xs[i], ys[i], pts) ? 1 : 0;
  } else if (gate.type === 'quadrant') {
    const { x, y, quadrant } = gate.geom;
    for (let i = 0; i < n; i++) {
      const right = xs[i] >= x;
      const up = ys[i] >= y;
      let hit;
      if (quadrant === 'Q1') hit = !right && up;
      else if (quadrant === 'Q2') hit = right && up;
      else if (quadrant === 'Q3') hit = !right && !up;
      else hit = right && !up;
      mask[i] = hit ? 1 : 0;
    }
  }
  return mask;
}

/** Vollstaendige Maske eines Gates einschliesslich aller Elterngates. */
export function resolveGate(sample, gateId) {
  if (!gateId) {
    const all = new Uint8Array(sample.nEvents);
    all.fill(1);
    return all;
  }
  return memo(
    `gate:${sample.id}:${gateId}`,
    [version.gates, version.compensation, version.transforms, sample.nEvents],
    () => {
      const gate = gateById(gateId);
      if (!gate) {
        const empty = new Uint8Array(sample.nEvents);
        return empty;
      }
      const mine = ownMask(sample, gate);
      if (!gate.parentId) return mine;
      const parent = resolveGate(sample, gate.parentId);
      const out = new Uint8Array(sample.nEvents);
      for (let i = 0; i < sample.nEvents; i++) out[i] = mine[i] && parent[i] ? 1 : 0;
      return out;
    },
  );
}

/** Ereignisindizes einer Population -- Eingabe fuer Plots und Statistik. */
export function gateIndices(sample, gateId) {
  return memo(
    `idx:${sample.id}:${gateId || 'root'}`,
    [version.gates, version.compensation, version.transforms, sample.nEvents],
    () => {
      const mask = resolveGate(sample, gateId);
      let count = 0;
      for (let i = 0; i < mask.length; i++) if (mask[i]) count++;
      const out = new Int32Array(count);
      let k = 0;
      for (let i = 0; i < mask.length; i++) if (mask[i]) out[k++] = i;
      return out;
    },
  );
}

export function gateCount(sample, gateId) {
  return gateIndices(sample, gateId).length;
}

/** Kennzahlen einer Population inklusive Anteil an Eltern- und Gesamtpopulation. */
export function gateStats(sample, gateId) {
  const gate = gateById(gateId);
  const count = gateCount(sample, gateId);
  const parentCount = gate?.parentId ? gateCount(sample, gate.parentId) : sample.nEvents;
  return {
    id: gateId,
    name: gate?.name || 'Alle Ereignisse',
    count,
    parentCount,
    total: sample.nEvents,
    pctParent: parentCount ? (100 * count) / parentCount : NaN,
    pctTotal: sample.nEvents ? (100 * count) / sample.nEvents : NaN,
  };
}

/** Alle Gates in hierarchischer Reihenfolge (Elternteil vor Kind). */
export function orderedGates() {
  const out = [];
  const visit = (parentId, depth) => {
    for (const g of state.gates.filter((x) => (x.parentId || null) === parentId)) {
      out.push({ gate: g, depth });
      visit(g.id, depth + 1);
    }
  };
  visit(null, 0);
  return out;
}

/* ------------------------------------------------------------------ */
/* Automatische Gates                                                  */
/* ------------------------------------------------------------------ */

const PALETTE = ['#4cc9f0', '#f72585', '#4895ef', '#ffd166', '#06d6a0', '#b5179e', '#fb8500', '#8ecae6'];
let colorIdx = 0;
export function nextColor() {
  return PALETTE[colorIdx++ % PALETTE.length];
}

function makeGate(props) {
  return {
    id: uid('gate'),
    color: nextColor(),
    parentId: null,
    ...props,
  };
}

/**
 * Singlet-Gate ueber FSC-A/FSC-H: Dubletten weichen vom linearen Zusammenhang
 * ab. Es wird ein robustes Band um die Hauptdiagonale gelegt (Median +/- k*MAD
 * des Verhaeltnisses H/A).
 */
export function autoSingletGate(sample, parentId = null, k = 3) {
  const sc = scatterParams(sample);
  const xi = sc.fscA;
  const yi = sc.fscH >= 0 ? sc.fscH : sc.sscH;
  if (xi < 0 || yi < 0) return null;

  const xv = channelValues(sample, xi);
  const yv = channelValues(sample, yi);
  const ratios = [];
  for (let i = 0; i < sample.nEvents; i++) {
    if (xv[i] > 1) ratios.push(yv[i] / xv[i]);
  }
  if (ratios.length < 50) return null;
  ratios.sort((a, b) => a - b);
  const med = percentileSorted(ratios, 0.5);
  const devs = ratios.map((r) => Math.abs(r - med)).sort((a, b) => a - b);
  const mad = percentileSorted(devs, 0.5) * 1.4826 || med * 0.05;

  const lo = med - k * mad;
  const hi = med + k * mad;
  const trX = transformFor(sample, xi);
  const trY = transformFor(sample, yi);
  const xMaxVal = trX.inverse(1);

  // Band im Datenraum als Polygon, danach in Displaykoordinaten ueberfuehrt.
  const steps = 24;
  const upper = [];
  const lower = [];
  for (let s = 0; s <= steps; s++) {
    const xVal = (xMaxVal * s) / steps;
    upper.push([trX.scale(xVal), trY.scale(xVal * hi)]);
    lower.push([trX.scale(xVal), trY.scale(xVal * lo)]);
  }
  const points = [...upper, ...lower.reverse()];

  return makeGate({
    name: 'Singlets',
    parentId,
    type: 'polygon',
    xParam: xi,
    yParam: yi,
    geom: { points },
    auto: { method: 'FSC-A/FSC-H-Verhältnis', k, median: med, mad },
  });
}

/**
 * Findet den dominanten Zellmodus in FSC/SSC und legt eine Ellipse darum.
 * `which` waehlt aus: 'lymph' bevorzugt niedriges SSC, 'largest' den groessten
 * Gipfel, 'blast' den Bereich mittleres FSC / niedriges SSC.
 */
export function autoModeGate(sample, xParam, yParam, parentId, opts = {}) {
  const { which = 'largest', name = 'Population', nSD = 2.2, minFsc = 0.08 } = opts;
  const xs = scaledValues(sample, xParam);
  const ys = scaledValues(sample, yParam);
  const idx = gateIndices(sample, parentId);
  if (idx.length < 100) return null;

  const dens = densityGrid(xs, ys, idx, 128, 2);
  let peaks = findPeaks2D(dens, 0.08).filter((p) => p.sx > minFsc);
  if (!peaks.length) return null;

  if (which === 'lymph') {
    // Lymphozyten: geringstes Seitwaertsstreulicht unter den kraeftigen Gipfeln
    const strong = peaks.filter((p) => p.height > peaks[0].height * 0.25);
    peaks = strong.sort((a, b) => a.sy - b.sy);
  } else if (which === 'blast') {
    const strong = peaks.filter((p) => p.height > peaks[0].height * 0.1);
    peaks = strong.sort((a, b) => Math.abs(a.sy - 0.28) - Math.abs(b.sy - 0.28));
  }

  const peak = peaks[0];
  const { mask } = floodRegion(dens, peak, 0.3);
  const nBins = dens.nBins;
  const member = [];
  for (let i = 0; i < idx.length; i++) {
    const e = idx[i];
    let bx = Math.floor(xs[e] * nBins);
    let by = Math.floor(ys[e] * nBins);
    if (bx < 0) bx = 0;
    else if (bx >= nBins) bx = nBins - 1;
    if (by < 0) by = 0;
    else if (by >= nBins) by = nBins - 1;
    if (mask[by * nBins + bx]) member.push(e);
  }
  if (member.length < 30) return null;

  const ell = ellipseFromPoints(xs, ys, Int32Array.from(member), nSD);
  if (!ell) return null;

  return makeGate({
    name,
    parentId,
    type: 'ellipse',
    xParam,
    yParam,
    geom: ell,
    auto: { method: `Dichtemodus (${which})`, peakDensity: peak.height, nSD },
  });
}

/**
 * Eindimensionale Schwelle auf einem Kanal.
 * @param {'otsu'|'valley'|'quantile'|'value'} method
 */
export function autoThresholdGate(sample, param, parentId, opts = {}) {
  const { method = 'valley', quantile = 0.99, above = true, name, value } = opts;
  const scaled = scaledValues(sample, param);
  const idx = gateIndices(sample, parentId);
  if (!idx.length) return null;

  let threshold;
  if (method === 'value') {
    threshold = value;
  } else if (method === 'quantile') {
    const arr = new Float64Array(idx.length);
    for (let i = 0; i < idx.length; i++) arr[i] = scaled[idx[i]];
    arr.sort();
    threshold = percentileSorted(arr, quantile);
  } else {
    const { bins } = histogram1D(scaled, idx, 256);
    const sm = smooth1D(bins, 2.5);
    const b = method === 'otsu' ? otsuThreshold(sm) : valleyThreshold(sm);
    threshold = b / 256;
  }

  const p = sample.params[param];
  return makeGate({
    name: name || `${p.stain || p.name} ${above ? 'positiv' : 'negativ'}`,
    parentId,
    type: 'interval',
    xParam: param,
    geom: above ? { min: threshold, max: 1 } : { min: 0, max: threshold },
    auto: { method: `Schwelle (${method})`, threshold },
  });
}

/** Vier Quadranten-Gates aus einem Kreuz. */
export function autoQuadrants(sample, xParam, yParam, parentId, opts = {}) {
  const { xThreshold, yThreshold, labels } = opts;
  const px = sample.params[xParam];
  const py = sample.params[yParam];
  const nx = px.stain || px.name;
  const ny = py.stain || py.name;

  const thr = (param, given) => {
    if (Number.isFinite(given)) return given;
    const scaled = scaledValues(sample, param);
    const idx = gateIndices(sample, parentId);
    const { bins } = histogram1D(scaled, idx, 256);
    return valleyThreshold(smooth1D(bins, 2.5)) / 256;
  };
  const x = thr(xParam, xThreshold);
  const y = thr(yParam, yThreshold);

  const names = labels || [
    `${nx}- ${ny}+`,
    `${nx}+ ${ny}+`,
    `${nx}- ${ny}-`,
    `${nx}+ ${ny}-`,
  ];
  return ['Q1', 'Q2', 'Q3', 'Q4'].map((q, i) =>
    makeGate({
      name: names[i],
      parentId,
      type: 'quadrant',
      xParam,
      yParam,
      geom: { x, y, quadrant: q },
      auto: { method: 'Quadranten', x, y },
    }),
  );
}

/**
 * Zeitfenster mit stabiler Ereignisrate. Instabile Abschnitte (Luftblasen,
 * Verstopfung) werden ausgeschlossen -- Voraussetzung fuer belastbare
 * Absolutzahlen und seltene Ereignisse.
 */
export function autoTimeGate(sample, parentId = null, tolerance = 0.35) {
  const sc = scatterParams(sample);
  if (sc.time < 0) return null;
  const scaled = scaledValues(sample, sc.time);
  const nBins = 100;
  const { bins } = histogram1D(scaled, null, nBins);
  const sm = smooth1D(bins, 1.5);

  const nonEmpty = Array.from(sm).filter((v) => v > 0).sort((a, b) => a - b);
  if (nonEmpty.length < 10) return null;
  const med = percentileSorted(Float64Array.from(nonEmpty), 0.5);

  let start = 0;
  while (start < nBins && Math.abs(sm[start] - med) > med * tolerance) start++;
  let end = nBins - 1;
  while (end > start && Math.abs(sm[end] - med) > med * tolerance) end--;
  if (end - start < nBins * 0.2) return null;

  return makeGate({
    name: 'Zeitfenster stabil',
    parentId,
    type: 'interval',
    xParam: sc.time,
    geom: { min: start / nBins, max: (end + 1) / nBins },
    auto: { method: 'Ereignisratenstabilität', tolerance, medianRate: med },
  });
}

/**
 * Erzeugt aus einer Ereignisliste (z.B. einem Metacluster) ein Polygon-Gate --
 * so wird ein Clusterergebnis zu einer pruefbaren, befundfaehigen Population.
 */
export function gateFromEvents(sample, eventIndices, xParam, yParam, parentId, name) {
  const xs = scaledValues(sample, xParam);
  const ys = scaledValues(sample, yParam);
  const pts = [];
  for (let i = 0; i < eventIndices.length; i++) pts.push([xs[eventIndices[i]], ys[eventIndices[i]]]);
  const hull = convexHull(pts);
  if (hull.length < 3) return null;
  return makeGate({
    name: name || 'Cluster',
    parentId,
    type: 'polygon',
    xParam,
    yParam,
    geom: { points: hull },
    auto: { method: 'Konvexe Hülle eines Clusters', n: eventIndices.length },
  });
}

/** Konvexe Huelle (Andrews Monotone Chain). */
export function convexHull(points) {
  if (points.length < 3) return points;
  const pts = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

/**
 * Standard-Vorgating fuer jede Probe: Zeitfenster, Zellen, Singlets.
 *
 * Jedes Gate wird sofort registriert, weil das jeweils naechste Gate die
 * Ereignisse seines Elterngates auswertet -- ein noch nicht eingefuegtes
 * Elterngate haette eine leere Population.
 *
 * @returns {Gate[]} die angelegten Gates in Reihenfolge
 */
export function standardPreGating(sample) {
  const created = [];
  const anlegen = (gate) => {
    if (!gate) return null;
    addGate(gate);
    created.push(gate);
    return gate;
  };

  const time = anlegen(autoTimeGate(sample, null));
  const parentAfterTime = time ? time.id : null;

  const sc = scatterParams(sample);
  if (sc.fscA >= 0 && sc.sscA >= 0) {
    const cells = anlegen(
      autoModeGate(sample, sc.fscA, sc.sscA, parentAfterTime, {
        which: 'largest',
        name: 'Zellen (ohne Debris)',
        nSD: 3,
        minFsc: 0.1,
      }),
    );
    if (cells) anlegen(autoSingletGate(sample, cells.id));
  }
  return created;
}

export { makeGate };
