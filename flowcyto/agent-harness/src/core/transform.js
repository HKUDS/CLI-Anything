/**
 * Skalierungen: linear, log10, arcsinh und Logicle (biexponentiell).
 *
 * Jede Transformation bildet einen Messwert auf eine Displaykoordinate in
 * [0, 1] ab und zurueck. Genau diese eine Abbildung nutzen Plots, Gates,
 * Statistik und Cluster -- damit ist ausgeschlossen, dass ein Gate in einer
 * anderen Skala liegt als der Plot, in dem es gezeichnet wurde.
 *
 * Die Logicle-Implementierung folgt Moore & Parks (Cytometry A, 2012):
 * Loesung der Logicle-Bedingung S''(x1) = 0 per Newton/Bisektion, Taylorreihe
 * um x1 fuer den quasilinearen Bereich, Halley-Iteration fuer die Umkehrung.
 */

const LN10 = Math.LN10;
const EPS = Number.EPSILON;
const TAYLOR_LENGTH = 16;

/* ------------------------------------------------------------------ */
/* Logicle                                                             */
/* ------------------------------------------------------------------ */

/** Loest 2*ln(d/b) + w*(b+d) = 0 nach d (Logicle-Bedingung). */
function solveD(b, w) {
  if (w === 0) return b;
  const tolerance = 2 * b * EPS;
  let dLo = 0;
  let dHi = b;
  let d = (dLo + dHi) / 2;
  let lastDelta = dHi - dLo;
  const fB = -2 * Math.log(b) + w * b;
  let f = 2 * Math.log(d) + w * d + fB;
  let lastF = NaN;

  for (let i = 0; i < 40; i++) {
    const df = 2 / d + w;
    let delta;
    if (
      ((d - dHi) * df - f) * ((d - dLo) * df - f) >= 0 ||
      Math.abs(1.9 * f) > Math.abs(lastDelta * df)
    ) {
      delta = lastDelta;
      lastDelta = (dHi - dLo) / 2;
      d = (dLo + dHi) / 2;
      if (Math.abs(delta) < tolerance) return d;
    } else {
      delta = lastDelta;
      lastDelta = f / df;
      d -= lastDelta;
      if (Math.abs(delta) < tolerance) return d;
    }
    f = 2 * Math.log(d) + w * d + fB;
    if (f === 0 || f === lastF) return d;
    lastF = f;
    if (f < 0) dLo = d;
    else dHi = d;
  }
  return d;
}

export class Logicle {
  /**
   * @param {number} T oberer Skalenwert (z.B. 262144)
   * @param {number} W Breite des linearisierten Bereichs in Dekaden
   * @param {number} M Gesamtzahl der Dekaden
   * @param {number} A zusaetzliche negative Dekaden
   */
  constructor(T = 262144, W = 0.5, M = 4.5, A = 0) {
    if (T <= 0) throw new Error('Logicle: T muss > 0 sein.');
    if (W < 0) throw new Error('Logicle: W muss >= 0 sein.');
    if (M <= 0) throw new Error('Logicle: M muss > 0 sein.');
    if (2 * W > M) throw new Error('Logicle: 2*W darf M nicht überschreiten.');
    if (A < -W || A > M - 2 * W) A = Math.min(Math.max(A, -W), M - 2 * W);

    this.T = T;
    this.W = W;
    this.M = M;
    this.A = A;

    this.w = W / (M + A);
    this.x2 = A / (M + A);
    this.x1 = this.x2 + this.w;
    this.x0 = this.x2 + 2 * this.w;
    this.b = (M + A) * LN10;
    this.d = solveD(this.b, this.w);

    const cA = Math.exp(this.x0 * (this.b + this.d));
    const mfA = Math.exp(this.b * this.x1) - cA / Math.exp(this.d * this.x1);
    this.a = T / (Math.exp(this.b) - mfA - cA / Math.exp(this.d));
    this.c = cA * this.a;
    this.f = this.a * mfA;

    // Taylorreihe um x1 (Koeffizient i entspricht t^(i+1)).
    let posCoef = this.a * Math.exp(this.b * this.x1);
    let negCoef = -this.c / Math.exp(this.d * this.x1);
    this.taylor = new Float64Array(TAYLOR_LENGTH);
    for (let i = 0; i < TAYLOR_LENGTH; i++) {
      posCoef *= this.b / (i + 1);
      negCoef *= -this.d / (i + 1);
      this.taylor[i] = posCoef + negCoef;
    }
    this.taylor[1] = 0; // exakt nach Logicle-Bedingung
    this.xTaylor = this.x1 + this.w / 4;
  }

  /** Taylorentwicklung der Biexponentialfunktion nahe x1. */
  series(scale) {
    const t = scale - this.x1;
    let sum = this.taylor[TAYLOR_LENGTH - 1] * t;
    for (let i = TAYLOR_LENGTH - 2; i >= 2; i--) sum = (sum + this.taylor[i]) * t;
    return (sum * t + this.taylor[0]) * t;
  }

  /** Displaykoordinate [0,1] -> Messwert. */
  inverse(scale) {
    const negative = scale < this.x1;
    if (negative) scale = 2 * this.x1 - scale;
    const value =
      scale < this.xTaylor
        ? this.series(scale)
        : this.a * Math.exp(this.b * scale) - this.c / Math.exp(this.d * scale) - this.f;
    return negative ? -value : value;
  }

  /** Messwert -> Displaykoordinate [0,1] (Halley-Iteration, kubisch konvergent). */
  scale(value) {
    if (value === 0) return this.x1;
    const negative = value < 0;
    if (negative) value = -value;

    // Im quasilinearen Bereich (|value| unterhalb des Achsenabschnitts f)
    // ist die lineare Naeherung der bessere Startwert, sonst der Logarithmus.
    const fAbs = Math.abs(this.f);
    let x =
      value < fAbs
        ? this.x1 + value / this.taylor[0]
        : Math.log(value / this.a) / this.b;

    const tolerance = x > 1 ? 3 * x * EPS : 3 * EPS;
    for (let i = 0; i < 30; i++) {
      const ae2bx = this.a * Math.exp(this.b * x);
      const ce2mdx = this.c / Math.exp(this.d * x);
      // Residuum S(x) - value; die Gruppierung haelt gleichnamige
      // Groessenordnungen zusammen und begrenzt den Rundungsfehler.
      const y =
        x < this.xTaylor
          ? this.series(x) - value
          : ae2bx - this.f - (ce2mdx + value);
      const abe2bx = this.b * ae2bx;
      const cde2mdx = this.d * ce2mdx;
      const dy = abe2bx + cde2mdx;
      const ddy = this.b * abe2bx - this.d * cde2mdx;
      const delta = y / (dy * (1 - (y * ddy) / (2 * dy * dy)));
      x -= delta;
      if (!Number.isFinite(x)) break;
      if (Math.abs(delta) < tolerance) break;
    }
    return negative ? 2 * this.x1 - x : x;
  }
}

/**
 * Schaetzt den Parameter W aus den negativen Messwerten eines Kanals
 * (Vorgehen analog flowCore::estimateLogicle): W = (M - log10(T/|r|)) / 2
 * mit r = 5. Perzentil der negativen Werte.
 */
export function estimateW(values, T, M = 4.5) {
  const neg = [];
  for (let i = 0; i < values.length; i++) if (values[i] < 0) neg.push(values[i]);
  if (neg.length < 10) return 0.5;
  neg.sort((a, b) => a - b);
  const r = neg[Math.floor(neg.length * 0.05)];
  if (!r || r === 0) return 0.5;
  let w = (M - Math.log10(T / Math.abs(r))) / 2;
  if (!Number.isFinite(w)) return 0.5;
  return Math.min(Math.max(w, 0.05), M / 2 - 0.01);
}

/* ------------------------------------------------------------------ */
/* Einheitliche Transformations-Schnittstelle                          */
/* ------------------------------------------------------------------ */

const LUT_SIZE = 4096;

class BaseTransform {
  constructor(kind, opts) {
    this.kind = kind;
    Object.assign(this, opts);
  }
  /** Messwert -> [0,1] */
  scale(v) {
    return v;
  }
  /** [0,1] -> Messwert */
  inverse(s) {
    return s;
  }
  /** Wendet die Skalierung auf ein ganzes Array an (LUT-beschleunigt). */
  applyArray(src, out) {
    const dst = out || new Float32Array(src.length);
    for (let i = 0; i < src.length; i++) dst[i] = this.scale(src[i]);
    return dst;
  }
  /** Achsenbeschriftung: [{pos, label, minor}] */
  ticks() {
    return [];
  }
  describe() {
    return this.kind;
  }
}

class LinearTransform extends BaseTransform {
  constructor(min, max) {
    super('linear', { min, max });
    if (max === min) this.max = min + 1;
  }
  scale(v) {
    return (v - this.min) / (this.max - this.min);
  }
  inverse(s) {
    return this.min + s * (this.max - this.min);
  }
  ticks() {
    const span = this.max - this.min;
    const step = Math.pow(10, Math.floor(Math.log10(span / 5)));
    const mult = [1, 2, 5, 10].find((m) => span / (step * m) <= 6) || 10;
    const dt = step * mult;
    const out = [];
    for (let v = Math.ceil(this.min / dt) * dt; v <= this.max; v += dt) {
      out.push({ pos: this.scale(v), label: formatSI(v), minor: false });
    }
    return out;
  }
  describe() {
    return `linear (${formatSI(this.min)}–${formatSI(this.max)})`;
  }
}

class LogTransform extends BaseTransform {
  constructor(min, max) {
    super('log', { min: Math.max(min, 1e-3), max });
    this.lmin = Math.log10(this.min);
    this.lmax = Math.log10(Math.max(this.max, this.min * 10));
  }
  scale(v) {
    if (v <= this.min) return 0;
    return (Math.log10(v) - this.lmin) / (this.lmax - this.lmin);
  }
  inverse(s) {
    return Math.pow(10, this.lmin + s * (this.lmax - this.lmin));
  }
  ticks() {
    const out = [];
    for (let d = Math.ceil(this.lmin); d <= Math.floor(this.lmax); d++) {
      out.push({ pos: this.scale(Math.pow(10, d)), label: `10^${d}`, minor: false });
      for (let m = 2; m <= 9; m++) {
        const p = this.scale(m * Math.pow(10, d));
        if (p > 0 && p < 1) out.push({ pos: p, label: '', minor: true });
      }
    }
    return out;
  }
  describe() {
    return `log10 (${formatSI(this.min)}–${formatSI(this.max)})`;
  }
}

class AsinhTransform extends BaseTransform {
  constructor(cofactor, min, max) {
    super('asinh', { cofactor: cofactor || 150, min, max });
    this.smin = Math.asinh(this.min / this.cofactor);
    this.smax = Math.asinh(this.max / this.cofactor);
    if (this.smax === this.smin) this.smax = this.smin + 1;
  }
  scale(v) {
    return (Math.asinh(v / this.cofactor) - this.smin) / (this.smax - this.smin);
  }
  inverse(s) {
    return Math.sinh(this.smin + s * (this.smax - this.smin)) * this.cofactor;
  }
  ticks() {
    return decadeTicks(this, this.min, this.max);
  }
  describe() {
    return `arcsinh (Kofaktor ${this.cofactor})`;
  }
}

class LogicleTransform extends BaseTransform {
  constructor(T, W, M, A) {
    super('logicle', { T, W, M, A });
    this.lg = new Logicle(T, W, M, A);
    // Nachschlagetabelle: gleichmaessige Displaykoordinaten -> Messwerte.
    // Die Werte sind streng monoton, daher genuegt eine Binaersuche.
    this.lutValues = new Float64Array(LUT_SIZE + 1);
    for (let i = 0; i <= LUT_SIZE; i++) this.lutValues[i] = this.lg.inverse(i / LUT_SIZE);
    this.vMin = this.lutValues[0];
    this.vMax = this.lutValues[LUT_SIZE];
  }
  scale(v) {
    if (v <= this.vMin) return 0;
    if (v >= this.vMax) return 1;
    const lut = this.lutValues;
    let lo = 0;
    let hi = LUT_SIZE;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (lut[mid] <= v) lo = mid;
      else hi = mid;
    }
    const a = lut[lo];
    const b = lut[hi];
    const frac = b > a ? (v - a) / (b - a) : 0;
    return (lo + frac) / LUT_SIZE;
  }
  /** Exakte Umkehrung ohne Tabelle -- fuer Achsen und Gate-Geometrie. */
  scaleExact(v) {
    return this.lg.scale(v);
  }
  inverse(s) {
    return this.lg.inverse(s);
  }
  ticks() {
    return decadeTicks(this, this.vMin, this.vMax, true);
  }
  describe() {
    return `Logicle (T=${formatSI(this.T)}, W=${this.W.toFixed(2)}, M=${this.M})`;
  }
}

/** Dekadenticks inkl. Null und negativen Dekaden fuer bi-exponentielle Achsen. */
function decadeTicks(tr, vMin, vMax, includeZero = false) {
  const out = [];
  const maxDec = Math.floor(Math.log10(Math.max(vMax, 10)));
  const minDec = vMin < -10 ? Math.floor(Math.log10(-vMin)) : -1;

  if (includeZero || vMin < 0) {
    const p0 = tr.scale(0);
    if (p0 >= 0 && p0 <= 1) out.push({ pos: p0, label: '0', minor: false });
  }
  for (let d = 1; d <= maxDec; d++) {
    const v = Math.pow(10, d);
    const p = tr.scale(v);
    if (p > 0.001 && p < 0.999) out.push({ pos: p, label: `10^${d}`, minor: false });
    for (let m = 2; m <= 9; m++) {
      const pm = tr.scale(m * Math.pow(10, d - 1));
      if (pm > 0.001 && pm < 0.999) out.push({ pos: pm, label: '', minor: true });
    }
  }
  for (let d = 2; d <= minDec; d++) {
    const p = tr.scale(-Math.pow(10, d));
    if (p > 0.001 && p < 0.999) out.push({ pos: p, label: `-10^${d}`, minor: false });
  }
  return out.sort((a, b) => a.pos - b.pos);
}

export function formatSI(v) {
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a >= 1e6) return `${(v / 1e6).toFixed(a >= 1e7 ? 0 : 1)}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(a >= 1e4 ? 0 : 1)}K`;
  if (a >= 10) return v.toFixed(0);
  if (a >= 1) return v.toFixed(1);
  return v.toPrecision(2);
}

/* ------------------------------------------------------------------ */
/* Fabrik + Automatik                                                  */
/* ------------------------------------------------------------------ */

export function makeTransform(spec) {
  switch (spec.kind) {
    case 'linear':
      return new LinearTransform(spec.min ?? 0, spec.max ?? 262144);
    case 'log':
      return new LogTransform(spec.min ?? 1, spec.max ?? 262144);
    case 'asinh':
      return new AsinhTransform(spec.cofactor ?? 150, spec.min ?? -1000, spec.max ?? 262144);
    case 'logicle':
    default:
      return new LogicleTransform(spec.T ?? 262144, spec.W ?? 0.5, spec.M ?? 4.5, spec.A ?? 0);
  }
}

/**
 * Waehlt eine sinnvolle Voreinstellung: Streulicht und Zeit linear,
 * Fluoreszenzkanaele Logicle mit aus den Daten geschaetztem W.
 */
export function autoTransformSpec(sample, paramIndex, values) {
  const p = sample.params[paramIndex];
  if (p.isTime) {
    let max = 0;
    for (let i = 0; i < values.length; i++) if (values[i] > max) max = values[i];
    return { kind: 'linear', min: 0, max: max || 1 };
  }
  if (p.isScatter) {
    return { kind: 'linear', min: 0, max: p.range || 262144 };
  }
  const T = Math.max(p.range || 262144, 1024);
  const M = 4.5;
  const W = estimateW(values, T, M);
  return { kind: 'logicle', T, W, M, A: 0 };
}
