/**
 * Statistik und Dichteschaetzung.
 *
 * Diese Funktionen sind die einzige Rechenquelle fuer Zahlen in der App:
 * die Statistiktabelle, die Beschriftung im Plot, die Regelauswertung und der
 * Befundtext greifen alle hierauf zu. Was im Plot steht, steht deshalb
 * zwangslaeufig auch im Befund.
 */

import { jacobiEigen } from './matrix.js';

/* ------------------------------------------------------------------ */
/* Lage- und Streuungsmasse                                            */
/* ------------------------------------------------------------------ */

/** Perzentil aus einem bereits sortierten Array (lineare Interpolation). */
export function percentileSorted(sorted, p) {
  const n = sorted.length;
  if (!n) return NaN;
  const idx = (n - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

export function median(values, indices) {
  const arr = extract(values, indices);
  if (!arr.length) return NaN;
  arr.sort();
  return percentileSorted(arr, 0.5);
}

/** Kopiert die Werte der ausgewaehlten Ereignisse in ein sortierbares Array. */
export function extract(values, indices) {
  if (!indices) return Float64Array.from(values);
  const out = new Float64Array(indices.length);
  for (let i = 0; i < indices.length; i++) out[i] = values[indices[i]];
  return out;
}

/**
 * Vollstaendige Kennzahlen eines Kanals innerhalb einer Population.
 * `mfi` ist der Median (robust, klinischer Standard), `gmfi` das geometrische
 * Mittel der positiven Werte, `rcv` der robuste Variationskoeffizient.
 */
export function channelStats(values, indices) {
  const arr = extract(values, indices);
  const n = arr.length;
  if (!n) {
    return { n: 0, mean: NaN, median: NaN, mfi: NaN, gmfi: NaN, sd: NaN, rsd: NaN, cv: NaN, rcv: NaN, min: NaN, max: NaN, p5: NaN, p95: NaN, iqr: NaN };
  }
  let sum = 0;
  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < n; i++) {
    const v = arr[i];
    sum += v;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  const mean = sum / n;
  let ss = 0;
  for (let i = 0; i < n; i++) {
    const d = arr[i] - mean;
    ss += d * d;
  }
  const sd = Math.sqrt(ss / Math.max(n - 1, 1));

  arr.sort();
  const med = percentileSorted(arr, 0.5);
  const q1 = percentileSorted(arr, 0.25);
  const q3 = percentileSorted(arr, 0.75);
  // Robuste SD aus dem Interquartilsabstand (Normalverteilungsannahme).
  const rsd = (q3 - q1) / 1.349;

  let logSum = 0;
  let logN = 0;
  for (let i = 0; i < n; i++) {
    if (arr[i] > 0) {
      logSum += Math.log(arr[i]);
      logN++;
    }
  }
  const gmfi = logN ? Math.exp(logSum / logN) : NaN;

  return {
    n,
    mean,
    median: med,
    mfi: med,
    gmfi,
    sd,
    rsd,
    cv: mean !== 0 ? (100 * sd) / Math.abs(mean) : NaN,
    rcv: med !== 0 ? (100 * rsd) / Math.abs(med) : NaN,
    min,
    max,
    p5: percentileSorted(arr, 0.05),
    p95: percentileSorted(arr, 0.95),
    q1,
    q3,
    iqr: q3 - q1,
  };
}

/* ------------------------------------------------------------------ */
/* Histogramme und Dichte                                              */
/* ------------------------------------------------------------------ */

/**
 * 1-D-Histogramm ueber skalierte Werte [0,1].
 * @returns {{bins:Float64Array, width:number, total:number}}
 */
export function histogram1D(scaled, indices, nBins = 256) {
  const bins = new Float64Array(nBins);
  const n = indices ? indices.length : scaled.length;
  for (let i = 0; i < n; i++) {
    const v = scaled[indices ? indices[i] : i];
    let b = Math.floor(v * nBins);
    if (b < 0) b = 0;
    else if (b >= nBins) b = nBins - 1;
    bins[b]++;
  }
  return { bins, width: 1 / nBins, total: n };
}

/** Glaettet ein Histogramm mit einem Gauss-Kern (sigma in Bins). */
export function smooth1D(bins, sigma = 2) {
  if (sigma <= 0) return bins;
  const radius = Math.max(1, Math.ceil(sigma * 3));
  const kernel = new Float64Array(2 * radius + 1);
  let ksum = 0;
  for (let i = -radius; i <= radius; i++) {
    const w = Math.exp((-i * i) / (2 * sigma * sigma));
    kernel[i + radius] = w;
    ksum += w;
  }
  for (let i = 0; i < kernel.length; i++) kernel[i] /= ksum;

  const out = new Float64Array(bins.length);
  for (let i = 0; i < bins.length; i++) {
    let s = 0;
    for (let k = -radius; k <= radius; k++) {
      const j = Math.min(bins.length - 1, Math.max(0, i + k));
      s += bins[j] * kernel[k + radius];
    }
    out[i] = s;
  }
  return out;
}

/**
 * 2-D-Dichtegitter ueber skalierte Koordinaten [0,1].
 * Basis fuer Pseudofarben-Plots, Konturen und die automatische Modussuche.
 */
export function densityGrid(xs, ys, indices, nBins = 256, sigma = 1.5) {
  const grid = new Float64Array(nBins * nBins);
  const n = indices ? indices.length : xs.length;
  for (let i = 0; i < n; i++) {
    const e = indices ? indices[i] : i;
    let bx = Math.floor(xs[e] * nBins);
    let by = Math.floor(ys[e] * nBins);
    if (bx < 0) bx = 0;
    else if (bx >= nBins) bx = nBins - 1;
    if (by < 0) by = 0;
    else if (by >= nBins) by = nBins - 1;
    grid[by * nBins + bx]++;
  }
  return { grid: sigma > 0 ? smooth2D(grid, nBins, sigma) : grid, nBins, total: n };
}

/** Separierbare Gauss-Glaettung eines quadratischen Gitters. */
export function smooth2D(grid, nBins, sigma) {
  const radius = Math.max(1, Math.ceil(sigma * 2.5));
  const kernel = new Float64Array(2 * radius + 1);
  let ksum = 0;
  for (let i = -radius; i <= radius; i++) {
    const w = Math.exp((-i * i) / (2 * sigma * sigma));
    kernel[i + radius] = w;
    ksum += w;
  }
  for (let i = 0; i < kernel.length; i++) kernel[i] /= ksum;

  const tmp = new Float64Array(grid.length);
  for (let y = 0; y < nBins; y++) {
    for (let x = 0; x < nBins; x++) {
      let s = 0;
      for (let k = -radius; k <= radius; k++) {
        const xx = Math.min(nBins - 1, Math.max(0, x + k));
        s += grid[y * nBins + xx] * kernel[k + radius];
      }
      tmp[y * nBins + x] = s;
    }
  }
  const out = new Float64Array(grid.length);
  for (let y = 0; y < nBins; y++) {
    for (let x = 0; x < nBins; x++) {
      let s = 0;
      for (let k = -radius; k <= radius; k++) {
        const yy = Math.min(nBins - 1, Math.max(0, y + k));
        s += tmp[yy * nBins + x] * kernel[k + radius];
      }
      out[y * nBins + x] = s;
    }
  }
  return out;
}

/** Dichtewert je Ereignis -- faerbt den Pseudocolor-Plot. */
export function pointDensity(xs, ys, indices, density) {
  const { grid, nBins } = density;
  const n = indices ? indices.length : xs.length;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const e = indices ? indices[i] : i;
    let bx = Math.floor(xs[e] * nBins);
    let by = Math.floor(ys[e] * nBins);
    if (bx < 0) bx = 0;
    else if (bx >= nBins) bx = nBins - 1;
    if (by < 0) by = 0;
    else if (by >= nBins) by = nBins - 1;
    out[i] = grid[by * nBins + bx];
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Schwellenwerte und Modussuche                                       */
/* ------------------------------------------------------------------ */

/** Otsu-Schwelle auf einem Histogramm; liefert die Binposition. */
export function otsuThreshold(bins) {
  const n = bins.length;
  let total = 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    total += bins[i];
    sum += i * bins[i];
  }
  if (!total) return Math.floor(n / 2);

  let sumB = 0;
  let wB = 0;
  let best = 0;
  let bestVar = -1;
  for (let i = 0; i < n; i++) {
    wB += bins[i];
    if (!wB) continue;
    const wF = total - wB;
    if (!wF) break;
    sumB += i * bins[i];
    const mB = sumB / wB;
    const mF = (sum - sumB) / wF;
    const between = wB * wF * (mB - mF) * (mB - mF);
    if (between > bestVar) {
      bestVar = between;
      best = i;
    }
  }
  return best;
}

/** Lokale Maxima eines geglaetteten Histogramms, absteigend nach Hoehe. */
export function findPeaks1D(bins, minProminence = 0.05) {
  let max = 0;
  for (let i = 0; i < bins.length; i++) if (bins[i] > max) max = bins[i];
  const peaks = [];
  for (let i = 1; i < bins.length - 1; i++) {
    if (bins[i] >= bins[i - 1] && bins[i] > bins[i + 1] && bins[i] > max * minProminence) {
      peaks.push({ bin: i, height: bins[i] });
    }
  }
  return peaks.sort((a, b) => b.height - a.height);
}

/** Tiefster Punkt zwischen den beiden hoechsten Gipfeln (klassische Talsuche). */
export function valleyThreshold(bins) {
  const peaks = findPeaks1D(bins, 0.1);
  if (peaks.length < 2) return otsuThreshold(bins);
  const [a, b] = [peaks[0].bin, peaks[1].bin].sort((x, y) => x - y);
  let best = a;
  let bestVal = Infinity;
  for (let i = a; i <= b; i++) {
    if (bins[i] < bestVal) {
      bestVal = bins[i];
      best = i;
    }
  }
  return best;
}

/** Lokale Maxima im 2-D-Dichtegitter. */
export function findPeaks2D(density, minFraction = 0.1) {
  const { grid, nBins } = density;
  let max = 0;
  for (let i = 0; i < grid.length; i++) if (grid[i] > max) max = grid[i];
  const peaks = [];
  for (let y = 1; y < nBins - 1; y++) {
    for (let x = 1; x < nBins - 1; x++) {
      const v = grid[y * nBins + x];
      if (v < max * minFraction) continue;
      let isPeak = true;
      for (let dy = -1; dy <= 1 && isPeak; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (dx === 0 && dy === 0) continue;
          if (grid[(y + dy) * nBins + (x + dx)] > v) {
            isPeak = false;
            break;
          }
        }
      }
      if (isPeak) peaks.push({ x, y, height: v, sx: (x + 0.5) / nBins, sy: (y + 0.5) / nBins });
    }
  }
  return peaks.sort((a, b) => b.height - a.height);
}

/**
 * Fuellt vom Gipfel aus alle zusammenhaengenden Gitterzellen oberhalb eines
 * Bruchteils der Gipfelhoehe -- die Grundlage der automatischen Gates.
 */
export function floodRegion(density, peak, fraction = 0.25) {
  const { grid, nBins } = density;
  const threshold = peak.height * fraction;
  const visited = new Uint8Array(grid.length);
  const stack = [peak.y * nBins + peak.x];
  const cells = [];
  while (stack.length) {
    const idx = stack.pop();
    if (visited[idx]) continue;
    visited[idx] = 1;
    if (grid[idx] < threshold) continue;
    cells.push(idx);
    const x = idx % nBins;
    const y = (idx / nBins) | 0;
    if (x > 0) stack.push(idx - 1);
    if (x < nBins - 1) stack.push(idx + 1);
    if (y > 0) stack.push(idx - nBins);
    if (y < nBins - 1) stack.push(idx + nBins);
  }
  return { cells, mask: visited, threshold };
}

/**
 * Ellipse aus Mittelwert und Kovarianz einer Punktwolke.
 * @returns {{cx,cy,rx,ry,angle}} Radien als Vielfaches der Standardabweichung
 */
export function ellipseFromPoints(xs, ys, indices, nSD = 2) {
  const n = indices ? indices.length : xs.length;
  if (n < 3) return null;
  let mx = 0;
  let my = 0;
  for (let i = 0; i < n; i++) {
    const e = indices ? indices[i] : i;
    mx += xs[e];
    my += ys[e];
  }
  mx /= n;
  my /= n;

  let sxx = 0;
  let syy = 0;
  let sxy = 0;
  for (let i = 0; i < n; i++) {
    const e = indices ? indices[i] : i;
    const dx = xs[e] - mx;
    const dy = ys[e] - my;
    sxx += dx * dx;
    syy += dy * dy;
    sxy += dx * dy;
  }
  sxx /= n - 1;
  syy /= n - 1;
  sxy /= n - 1;

  const cov = [Float64Array.from([sxx, sxy]), Float64Array.from([sxy, syy])];
  const { values, vectors } = jacobiEigen(cov);
  const angle = Math.atan2(vectors[1][0], vectors[0][0]);
  return {
    cx: mx,
    cy: my,
    rx: nSD * Math.sqrt(Math.max(values[0], 1e-12)),
    ry: nSD * Math.sqrt(Math.max(values[1], 1e-12)),
    angle,
  };
}

/* ------------------------------------------------------------------ */
/* Vergleich von Verteilungen                                          */
/* ------------------------------------------------------------------ */

/**
 * Kolmogorow-Smirnow-Statistik zweier skalierter Verteilungen.
 * Wird zum Vergleich Probe gegen Kontrolle/Normalspender genutzt.
 */
export function ksStatistic(binsA, binsB) {
  const n = Math.min(binsA.length, binsB.length);
  let ca = 0;
  let cb = 0;
  let ta = 0;
  let tb = 0;
  for (let i = 0; i < n; i++) {
    ta += binsA[i];
    tb += binsB[i];
  }
  if (!ta || !tb) return { d: NaN, at: NaN };
  let d = 0;
  let at = 0;
  for (let i = 0; i < n; i++) {
    ca += binsA[i] / ta;
    cb += binsB[i] / tb;
    const diff = Math.abs(ca - cb);
    if (diff > d) {
      d = diff;
      at = i / n;
    }
  }
  return { d, at, pApprox: 2 * Math.exp((-2 * d * d * ta * tb) / (ta + tb)) };
}

/**
 * Overton-Subtraktion: Anteil positiver Zellen gegenueber einer Kontrolle
 * (FMO oder Isotyp) durch kumulative Histogrammsubtraktion.
 */
export function overtonPositive(sampleBins, controlBins) {
  const n = Math.min(sampleBins.length, controlBins.length);
  let ts = 0;
  let tc = 0;
  for (let i = 0; i < n; i++) {
    ts += sampleBins[i];
    tc += controlBins[i];
  }
  if (!ts || !tc) return NaN;
  let positive = 0;
  for (let i = n - 1; i >= 0; i--) {
    const s = sampleBins[i] / ts;
    const c = controlBins[i] / tc;
    if (s > c) positive += s - c;
  }
  return Math.min(100, Math.max(0, positive * 100));
}

/**
 * Faerbeindex (Stain Index) = (MFI_positiv - MFI_negativ) / (2 * rSD_negativ).
 * Kennzahl der Panel-Qualitaet; < 5 gilt als schwache Aufloesung.
 */
export function stainIndex(posStats, negStats) {
  if (!posStats?.n || !negStats?.n || !negStats.rsd) return NaN;
  return (posStats.median - negStats.median) / (2 * negStats.rsd);
}

/** Anteil der Ereignisse oberhalb einer skalierten Schwelle, in Prozent. */
export function fractionAbove(scaled, indices, threshold) {
  const n = indices ? indices.length : scaled.length;
  if (!n) return NaN;
  let c = 0;
  for (let i = 0; i < n; i++) if (scaled[indices ? indices[i] : i] >= threshold) c++;
  return (100 * c) / n;
}

/**
 * Nachweisgrenze einer seltenen Population (LOD/LLOQ nach EuroFlow):
 * LOD = 20 Ereignisse, LLOQ = 50 Ereignisse bezogen auf die Referenzpopulation.
 */
export function rareEventLimits(referenceCount) {
  if (!referenceCount) return { lod: NaN, lloq: NaN };
  return {
    lod: (20 / referenceCount) * 100,
    lloq: (50 / referenceCount) * 100,
  };
}

/**
 * Poisson-Vertrauensbereich (95 %) fuer einen Anteil aus `k` von `n`
 * Ereignissen -- unverzichtbar bei kleinen Zellzahlen im MRD-Bereich.
 */
export function poissonCI(k, n) {
  if (!n) return { low: NaN, high: NaN };
  const lowK = k === 0 ? 0 : k * Math.pow(1 - 1 / (9 * k) - 1.96 / (3 * Math.sqrt(k)), 3);
  const hk = k + 1;
  const highK = hk * Math.pow(1 - 1 / (9 * hk) + 1.96 / (3 * Math.sqrt(hk)), 3);
  return { low: (100 * Math.max(0, lowK)) / n, high: (100 * highK) / n };
}
