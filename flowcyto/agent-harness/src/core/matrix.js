/**
 * Kleine lineare Algebra -- gemeinsam genutzt von Kompensation (Matrixinverse),
 * Hauptkomponentenanalyse (Eigenzerlegung) und Clustering (Distanzen).
 * Bewusst eine einzige Implementierung, damit Kompensation und PCA nicht
 * getrennte Solver mitschleppen.
 */

/** Erzeugt eine n x n Einheitsmatrix. */
export function identity(n) {
  const m = [];
  for (let i = 0; i < n; i++) {
    m.push(new Float64Array(n));
    m[i][i] = 1;
  }
  return m;
}

export function cloneMatrix(a) {
  return a.map((row) => Float64Array.from(row));
}

/**
 * Matrixinversion per Gauss-Jordan mit Spaltenpivotisierung.
 * @returns {Array<Float64Array>|null} null bei singulaerer Matrix
 */
export function invert(input) {
  const n = input.length;
  const a = cloneMatrix(input);
  const inv = identity(n);

  for (let col = 0; col < n; col++) {
    let pivot = col;
    let best = Math.abs(a[col][col]);
    for (let r = col + 1; r < n; r++) {
      const v = Math.abs(a[r][col]);
      if (v > best) {
        best = v;
        pivot = r;
      }
    }
    if (best < 1e-12) return null;
    if (pivot !== col) {
      [a[col], a[pivot]] = [a[pivot], a[col]];
      [inv[col], inv[pivot]] = [inv[pivot], inv[col]];
    }
    const d = a[col][col];
    for (let j = 0; j < n; j++) {
      a[col][j] /= d;
      inv[col][j] /= d;
    }
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const f = a[r][col];
      if (f === 0) continue;
      for (let j = 0; j < n; j++) {
        a[r][j] -= f * a[col][j];
        inv[r][j] -= f * inv[col][j];
      }
    }
  }
  return inv;
}

/** Multipliziert Matrix (n x n) mit Vektor (n). Schreibt optional in `out`. */
export function matVec(m, v, out) {
  const n = m.length;
  const res = out || new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let s = 0;
    const row = m[i];
    for (let j = 0; j < n; j++) s += row[j] * v[j];
    res[i] = s;
  }
  return res;
}

export function matMul(a, b) {
  const n = a.length;
  const p = b[0].length;
  const q = b.length;
  const out = [];
  for (let i = 0; i < n; i++) {
    const row = new Float64Array(p);
    for (let k = 0; k < q; k++) {
      const aik = a[i][k];
      if (aik === 0) continue;
      for (let j = 0; j < p; j++) row[j] += aik * b[k][j];
    }
    out.push(row);
  }
  return out;
}

export function transpose(a) {
  const n = a.length;
  const p = a[0].length;
  const out = [];
  for (let j = 0; j < p; j++) {
    const row = new Float64Array(n);
    for (let i = 0; i < n; i++) row[i] = a[i][j];
    out.push(row);
  }
  return out;
}

/**
 * Jacobi-Eigenzerlegung fuer symmetrische Matrizen (Kovarianzmatrix der PCA).
 * @returns {{values:number[], vectors:Array<Float64Array>}} Eigenvektoren als Spalten,
 *          absteigend nach Eigenwert sortiert.
 */
export function jacobiEigen(input, maxSweeps = 100) {
  const n = input.length;
  const a = cloneMatrix(input);
  let v = identity(n);

  for (let sweep = 0; sweep < maxSweeps; sweep++) {
    let off = 0;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) off += a[i][j] * a[i][j];
    if (off < 1e-20) break;

    for (let p = 0; p < n - 1; p++) {
      for (let q = p + 1; q < n; q++) {
        if (Math.abs(a[p][q]) < 1e-18) continue;
        const theta = (a[q][q] - a[p][p]) / (2 * a[p][q]);
        const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let k = 0; k < n; k++) {
          const akp = a[k][p];
          const akq = a[k][q];
          a[k][p] = c * akp - s * akq;
          a[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = a[p][k];
          const aqk = a[q][k];
          a[p][k] = c * apk - s * aqk;
          a[q][k] = s * apk + c * aqk;
        }
        for (let k = 0; k < n; k++) {
          const vkp = v[k][p];
          const vkq = v[k][q];
          v[k][p] = c * vkp - s * vkq;
          v[k][q] = s * vkp + c * vkq;
        }
      }
    }
  }

  const order = Array.from({ length: n }, (_, i) => i).sort((x, y) => a[y][y] - a[x][x]);
  const values = order.map((i) => a[i][i]);
  const vectors = [];
  for (let i = 0; i < n; i++) {
    const row = new Float64Array(n);
    for (let j = 0; j < n; j++) row[j] = v[i][order[j]];
    vectors.push(row);
  }
  return { values, vectors };
}

/** Quadrierte euklidische Distanz zweier gleich langer Vektoren. */
export function dist2(a, b) {
  let s = 0;
  for (let i = 0; i < a.length; i++) {
    const d = a[i] - b[i];
    s += d * d;
  }
  return s;
}
