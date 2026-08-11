/**
 * Unueberwachte Verfahren: PCA, k-Means, FlowSOM (SOM + Metaclustering + MST)
 * und t-SNE.
 *
 * Zweck in der Befundung: aberrante Populationen sichtbar machen, die eine
 * feste Gating-Strategie uebersieht ("different from normal"). Jeder Cluster
 * laesst sich ueber gating.gateFromEvents in ein regulaeres Gate ueberfuehren
 * und wandert damit automatisch in Statistik und Befund.
 */

import { jacobiEigen, dist2 } from './matrix.js';
import { scaledValues } from './data.js';

/* ------------------------------------------------------------------ */
/* Matrixaufbau                                                        */
/* ------------------------------------------------------------------ */

/**
 * Baut die Merkmalsmatrix aus skalierten Kanalwerten.
 * @returns {{rows:Float32Array[], events:Int32Array, params:number[]}}
 */
export function buildMatrix(sample, paramIndices, eventIndices, maxEvents = 30000) {
  const src = eventIndices || Int32Array.from({ length: sample.nEvents }, (_, i) => i);
  const step = src.length > maxEvents ? src.length / maxEvents : 1;
  const count = Math.min(src.length, maxEvents);
  const events = new Int32Array(count);
  for (let i = 0; i < count; i++) events[i] = src[Math.floor(i * step)];

  const cols = paramIndices.map((p) => scaledValues(sample, p));
  const rows = [];
  for (let i = 0; i < count; i++) {
    const row = new Float32Array(paramIndices.length);
    for (let j = 0; j < paramIndices.length; j++) row[j] = cols[j][events[i]];
    rows.push(row);
  }
  return { rows, events, params: paramIndices };
}

/* ------------------------------------------------------------------ */
/* PCA                                                                 */
/* ------------------------------------------------------------------ */

/** Hauptkomponentenanalyse; liefert Projektion und erklaerte Varianz. */
export function pca(rows, nComponents = 2) {
  const n = rows.length;
  const d = rows[0].length;
  const mean = new Float64Array(d);
  for (const r of rows) for (let j = 0; j < d; j++) mean[j] += r[j];
  for (let j = 0; j < d; j++) mean[j] /= n;

  const cov = [];
  for (let i = 0; i < d; i++) cov.push(new Float64Array(d));
  for (const r of rows) {
    for (let i = 0; i < d; i++) {
      const di = r[i] - mean[i];
      for (let j = i; j < d; j++) {
        const v = di * (r[j] - mean[j]);
        cov[i][j] += v;
        if (i !== j) cov[j][i] += v;
      }
    }
  }
  for (let i = 0; i < d; i++) for (let j = 0; j < d; j++) cov[i][j] /= n - 1;

  const { values, vectors } = jacobiEigen(cov);
  const totalVar = values.reduce((a, b) => a + Math.max(b, 0), 0) || 1;

  const proj = [];
  for (const r of rows) {
    const p = new Float32Array(nComponents);
    for (let k = 0; k < nComponents; k++) {
      let s = 0;
      for (let i = 0; i < d; i++) s += (r[i] - mean[i]) * vectors[i][k];
      p[k] = s;
    }
    proj.push(p);
  }
  return {
    projection: proj,
    explained: values.slice(0, nComponents).map((v) => (100 * Math.max(v, 0)) / totalVar),
    loadings: vectors,
    mean,
  };
}

/* ------------------------------------------------------------------ */
/* k-Means                                                             */
/* ------------------------------------------------------------------ */

function mulberry32(seed) {
  let a = seed >>> 0;
  return function rnd() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** k-Means mit k-Means++-Initialisierung, deterministisch ueber `seed`. */
export function kmeans(rows, k, { maxIter = 60, seed = 42 } = {}) {
  const n = rows.length;
  const d = rows[0].length;
  const rnd = mulberry32(seed);
  if (n <= k) {
    return { assignment: Int32Array.from({ length: n }, (_, i) => i), centroids: rows.map((r) => Float64Array.from(r)), inertia: 0 };
  }

  const centroids = [Float64Array.from(rows[Math.floor(rnd() * n)])];
  const dists = new Float64Array(n).fill(Infinity);
  while (centroids.length < k) {
    let sum = 0;
    const last = centroids[centroids.length - 1];
    for (let i = 0; i < n; i++) {
      const dd = dist2(rows[i], last);
      if (dd < dists[i]) dists[i] = dd;
      sum += dists[i];
    }
    let target = rnd() * sum;
    let pick = n - 1;
    for (let i = 0; i < n; i++) {
      target -= dists[i];
      if (target <= 0) {
        pick = i;
        break;
      }
    }
    centroids.push(Float64Array.from(rows[pick]));
  }

  const assignment = new Int32Array(n);
  let inertia = 0;
  for (let iter = 0; iter < maxIter; iter++) {
    let moved = 0;
    inertia = 0;
    for (let i = 0; i < n; i++) {
      let best = 0;
      let bestD = Infinity;
      for (let c = 0; c < k; c++) {
        const dd = dist2(rows[i], centroids[c]);
        if (dd < bestD) {
          bestD = dd;
          best = c;
        }
      }
      inertia += bestD;
      if (assignment[i] !== best) {
        assignment[i] = best;
        moved++;
      }
    }
    if (!moved && iter > 0) break;

    const sums = Array.from({ length: k }, () => new Float64Array(d));
    const counts = new Int32Array(k);
    for (let i = 0; i < n; i++) {
      const c = assignment[i];
      counts[c]++;
      for (let j = 0; j < d; j++) sums[c][j] += rows[i][j];
    }
    for (let c = 0; c < k; c++) {
      if (!counts[c]) continue;
      for (let j = 0; j < d; j++) centroids[c][j] = sums[c][j] / counts[c];
    }
  }
  return { assignment, centroids, inertia };
}

/* ------------------------------------------------------------------ */
/* FlowSOM                                                             */
/* ------------------------------------------------------------------ */

/**
 * Selbstorganisierende Karte auf einem rechteckigen Gitter.
 * @returns {{nodes:Float64Array[], assignment:Int32Array, width:number, height:number}}
 */
export function trainSOM(rows, { width = 10, height = 10, epochs = 10, seed = 7 } = {}) {
  const n = rows.length;
  const d = rows[0].length;
  const nNodes = width * height;
  const rnd = mulberry32(seed);

  // Initialisierung entlang der beiden ersten Hauptkomponenten -> stabiler
  // und schneller konvergent als Zufallsgewichte.
  const { projection, loadings, mean } = pca(rows, 2);
  let p0min = Infinity, p0max = -Infinity, p1min = Infinity, p1max = -Infinity;
  for (const p of projection) {
    if (p[0] < p0min) p0min = p[0];
    if (p[0] > p0max) p0max = p[0];
    if (p[1] < p1min) p1min = p[1];
    if (p[1] > p1max) p1max = p[1];
  }
  const nodes = [];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const a = p0min + ((p0max - p0min) * x) / Math.max(width - 1, 1);
      const b = p1min + ((p1max - p1min) * y) / Math.max(height - 1, 1);
      const w = new Float64Array(d);
      for (let j = 0; j < d; j++) w[j] = mean[j] + a * loadings[j][0] + b * loadings[j][1];
      nodes.push(w);
    }
  }

  const totalSteps = epochs * n;
  const radius0 = Math.max(width, height) / 2;
  let step = 0;
  for (let e = 0; e < epochs; e++) {
    for (let i = 0; i < n; i++) {
      const row = rows[Math.floor(rnd() * n)];
      let bmu = 0;
      let bestD = Infinity;
      for (let c = 0; c < nNodes; c++) {
        const dd = dist2(row, nodes[c]);
        if (dd < bestD) {
          bestD = dd;
          bmu = c;
        }
      }
      const t = step / totalSteps;
      const radius = Math.max(0.7, radius0 * Math.exp(-3 * t));
      const alpha = 0.5 * Math.exp(-3 * t);
      const bx = bmu % width;
      const by = (bmu / width) | 0;
      const r = Math.ceil(radius);
      for (let dy = -r; dy <= r; dy++) {
        const ny = by + dy;
        if (ny < 0 || ny >= height) continue;
        for (let dx = -r; dx <= r; dx++) {
          const nx = bx + dx;
          if (nx < 0 || nx >= width) continue;
          const gd2 = dx * dx + dy * dy;
          const h = alpha * Math.exp(-gd2 / (2 * radius * radius));
          if (h < 1e-4) continue;
          const w = nodes[ny * width + nx];
          for (let j = 0; j < d; j++) w[j] += h * (row[j] - w[j]);
        }
      }
      step++;
    }
  }

  const assignment = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    let bmu = 0;
    let bestD = Infinity;
    for (let c = 0; c < nNodes; c++) {
      const dd = dist2(rows[i], nodes[c]);
      if (dd < bestD) {
        bestD = dd;
        bmu = c;
      }
    }
    assignment[i] = bmu;
  }
  return { nodes, assignment, width, height };
}

/** Agglomerative Clusterung (Average Linkage) der SOM-Knoten zu Metaclustern. */
export function metaCluster(nodes, k) {
  const n = nodes.length;
  const clusters = Array.from({ length: n }, (_, i) => [i]);
  const active = new Set(clusters.keys());
  const dist = [];
  for (let i = 0; i < n; i++) {
    dist.push(new Float64Array(n));
    for (let j = 0; j < n; j++) dist[i][j] = i === j ? Infinity : Math.sqrt(dist2(nodes[i], nodes[j]));
  }

  while (active.size > k) {
    let bi = -1;
    let bj = -1;
    let best = Infinity;
    for (const i of active) {
      for (const j of active) {
        if (j <= i) continue;
        if (dist[i][j] < best) {
          best = dist[i][j];
          bi = i;
          bj = j;
        }
      }
    }
    if (bi < 0) break;
    const ni = clusters[bi].length;
    const nj = clusters[bj].length;
    for (const m of active) {
      if (m === bi || m === bj) continue;
      const nd = (dist[bi][m] * ni + dist[bj][m] * nj) / (ni + nj);
      dist[bi][m] = nd;
      dist[m][bi] = nd;
    }
    clusters[bi] = clusters[bi].concat(clusters[bj]);
    active.delete(bj);
  }

  const label = new Int32Array(n);
  let c = 0;
  for (const i of active) {
    for (const node of clusters[i]) label[node] = c;
    c++;
  }
  return { label, k: c };
}

/** Minimaler Spannbaum ueber die SOM-Knoten (Prim) fuer die Darstellung. */
export function minimumSpanningTree(nodes) {
  const n = nodes.length;
  const inTree = new Uint8Array(n);
  const best = new Float64Array(n).fill(Infinity);
  const parent = new Int32Array(n).fill(-1);
  best[0] = 0;
  const edges = [];
  for (let it = 0; it < n; it++) {
    let u = -1;
    let bu = Infinity;
    for (let i = 0; i < n; i++) if (!inTree[i] && best[i] < bu) { bu = best[i]; u = i; }
    if (u < 0) break;
    inTree[u] = 1;
    if (parent[u] >= 0) edges.push({ a: parent[u], b: u, w: Math.sqrt(bu) });
    for (let v = 0; v < n; v++) {
      if (inTree[v]) continue;
      const d = dist2(nodes[u], nodes[v]);
      if (d < best[v]) {
        best[v] = d;
        parent[v] = u;
      }
    }
  }
  return edges;
}

/**
 * Vollstaendige FlowSOM-Analyse.
 * @returns Cluster je Ereignis, Metaclusterprofile und MST-Kanten
 */
export function flowSOM(sample, paramIndices, eventIndices, opts = {}) {
  const { gridWidth = 10, gridHeight = 10, nMeta = 12, maxEvents = 20000, epochs = 8 } = opts;
  const { rows, events } = buildMatrix(sample, paramIndices, eventIndices, maxEvents);
  if (rows.length < nMeta * 5) return null;

  const som = trainSOM(rows, { width: gridWidth, height: gridHeight, epochs });
  const meta = metaCluster(som.nodes, nMeta);
  const mst = minimumSpanningTree(som.nodes);

  const eventCluster = new Int32Array(rows.length);
  for (let i = 0; i < rows.length; i++) eventCluster[i] = meta.label[som.assignment[i]];

  // Medianprofil je Metacluster -- die Grundlage der Heatmap und der Bewertung.
  const profiles = [];
  for (let c = 0; c < meta.k; c++) {
    const members = [];
    for (let i = 0; i < rows.length; i++) if (eventCluster[i] === c) members.push(i);
    const prof = new Float64Array(paramIndices.length);
    for (let j = 0; j < paramIndices.length; j++) {
      const vals = members.map((i) => rows[i][j]).sort((a, b) => a - b);
      prof[j] = vals.length ? vals[Math.floor(vals.length / 2)] : 0;
    }
    profiles.push({
      cluster: c,
      n: members.length,
      fraction: (100 * members.length) / rows.length,
      profile: prof,
      eventIds: Int32Array.from(members, (i) => events[i]),
    });
  }

  const nodeCounts = new Int32Array(som.nodes.length);
  for (let i = 0; i < rows.length; i++) nodeCounts[som.assignment[i]]++;

  return {
    events,
    eventCluster,
    // Leere Metacluster entstehen, wenn die agglomerative Zusammenfassung
    // Knoten ohne zugeordnete Ereignisse gruppiert -- sie sind keine Population.
    profiles: profiles.filter((p) => p.n > 0).sort((a, b) => b.n - a.n),
    som,
    meta,
    mst,
    nodeCounts,
    params: paramIndices,
  };
}

/* ------------------------------------------------------------------ */
/* t-SNE                                                               */
/* ------------------------------------------------------------------ */

/**
 * Exaktes t-SNE (O(n^2)) auf einer Stichprobe. Fuer die visuelle
 * Gesamtschau eines Panels; nicht fuer quantitative Aussagen gedacht.
 */
export function tsne(rows, { perplexity = 30, iterations = 400, seed = 3, eta = 200 } = {}) {
  const n = rows.length;
  if (n < 10) return rows.map(() => new Float32Array(2));
  const rnd = mulberry32(seed);

  const D = [];
  for (let i = 0; i < n; i++) {
    const row = new Float64Array(n);
    for (let j = 0; j < n; j++) row[j] = i === j ? 0 : dist2(rows[i], rows[j]);
    D.push(row);
  }

  // Bandbreite je Punkt so waehlen, dass die Entropie der Perplexitaet entspricht.
  const P = [];
  const logU = Math.log(perplexity);
  for (let i = 0; i < n; i++) {
    let beta = 1;
    let betaMin = -Infinity;
    let betaMax = Infinity;
    const row = new Float64Array(n);
    for (let tries = 0; tries < 50; tries++) {
      let sum = 0;
      for (let j = 0; j < n; j++) {
        row[j] = i === j ? 0 : Math.exp(-D[i][j] * beta);
        sum += row[j];
      }
      if (sum === 0) sum = 1e-12;
      let H = 0;
      for (let j = 0; j < n; j++) {
        const p = row[j] / sum;
        if (p > 1e-12) H -= p * Math.log(p);
      }
      const diff = H - logU;
      if (Math.abs(diff) < 1e-5) break;
      if (diff > 0) {
        betaMin = beta;
        beta = betaMax === Infinity ? beta * 2 : (beta + betaMax) / 2;
      } else {
        betaMax = beta;
        beta = betaMin === -Infinity ? beta / 2 : (beta + betaMin) / 2;
      }
    }
    let sum = 0;
    for (let j = 0; j < n; j++) sum += row[j];
    for (let j = 0; j < n; j++) row[j] /= sum || 1;
    P.push(row);
  }
  // Symmetrisieren und normieren
  let psum = 0;
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const v = (P[i][j] + P[j][i]) / (2 * n);
      P[i][j] = v;
      P[j][i] = v;
      psum += 2 * v;
    }
  }
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) P[i][j] /= psum || 1;

  const Y = [];
  for (let i = 0; i < n; i++) Y.push(new Float64Array([(rnd() - 0.5) * 1e-4, (rnd() - 0.5) * 1e-4]));
  const gains = Y.map(() => new Float64Array([1, 1]));
  const inc = Y.map(() => new Float64Array(2));

  const Q = [];
  for (let i = 0; i < n; i++) Q.push(new Float64Array(n));

  for (let iter = 0; iter < iterations; iter++) {
    const exaggeration = iter < 100 ? 4 : 1;
    let qsum = 0;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dx = Y[i][0] - Y[j][0];
        const dy = Y[i][1] - Y[j][1];
        const q = 1 / (1 + dx * dx + dy * dy);
        Q[i][j] = q;
        Q[j][i] = q;
        qsum += 2 * q;
      }
    }
    qsum = qsum || 1e-12;

    const momentum = iter < 250 ? 0.5 : 0.8;
    for (let i = 0; i < n; i++) {
      let gx = 0;
      let gy = 0;
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        const mult = (P[i][j] * exaggeration - Q[i][j] / qsum) * Q[i][j];
        gx += 4 * mult * (Y[i][0] - Y[j][0]);
        gy += 4 * mult * (Y[i][1] - Y[j][1]);
      }
      const g = [gx, gy];
      for (let k = 0; k < 2; k++) {
        gains[i][k] = Math.max(0.01, Math.sign(g[k]) === Math.sign(inc[i][k]) ? gains[i][k] * 0.8 : gains[i][k] + 0.2);
        inc[i][k] = momentum * inc[i][k] - eta * gains[i][k] * g[k];
        Y[i][k] += inc[i][k];
      }
    }
    // Zentrieren
    const mx = Y.reduce((a, y) => a + y[0], 0) / n;
    const my = Y.reduce((a, y) => a + y[1], 0) / n;
    for (let i = 0; i < n; i++) {
      Y[i][0] -= mx;
      Y[i][1] -= my;
    }
  }
  return Y.map((y) => Float32Array.from(y));
}

/** Skaliert eine 2-D-Einbettung auf den Anzeigebereich [0,1]. */
export function normalizeEmbedding(points) {
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const p of points) {
    if (p[0] < xmin) xmin = p[0];
    if (p[0] > xmax) xmax = p[0];
    if (p[1] < ymin) ymin = p[1];
    if (p[1] > ymax) ymax = p[1];
  }
  const sx = xmax - xmin || 1;
  const sy = ymax - ymin || 1;
  return points.map((p) => Float32Array.from([0.05 + (0.9 * (p[0] - xmin)) / sx, 0.05 + (0.9 * (p[1] - ymin)) / sy]));
}
